"""
src/ingestion/db.py
===================
SQLite raw data store — the single source of truth for the pipeline.

Responsibilities:
  - Creates the `reviews` table with the canonical schema on first run.
  - Provides insert (with idempotency via text hash) and read operations.
  - Never modified by Phase 2+ — this store is append-only after Phase 1.

The schema matches the canonical review schema defined in config/sources.json.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Schema ──────────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reviews (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    app         TEXT NOT NULL,
    text        TEXT NOT NULL,
    text_hash   TEXT NOT NULL UNIQUE,
    rating      INTEGER,
    created_at  TEXT,
    url         TEXT,
    language    TEXT,
    platform    TEXT,
    metadata    TEXT,
    inserted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reviews_source  ON reviews(source);
CREATE INDEX IF NOT EXISTS idx_reviews_app     ON reviews(app);
CREATE INDEX IF NOT EXISTS idx_reviews_rating  ON reviews(rating);
CREATE INDEX IF NOT EXISTS idx_reviews_date    ON reviews(created_at);
CREATE INDEX IF NOT EXISTS idx_reviews_url     ON reviews(url);
CREATE INDEX IF NOT EXISTS idx_reviews_platform ON reviews(platform);
"""


# ── Connection context manager ───────────────────────────────────────────────
@contextmanager
def get_connection(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """Yields a SQLite connection. Creates the DB file if it does not exist."""
    path = db_path or settings.sqlite_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Initialise schema ────────────────────────────────────────────────────────
def init_db(db_path: Optional[Path] = None) -> None:
    """Creates the reviews table and indexes if they do not exist."""
    with get_connection(db_path) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        _migrate_schema(conn)
    logger.info(f"Database initialised at [bold]{db_path or settings.sqlite_db_path}[/bold]")


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Add new columns to the reviews table if they are missing."""
    existing_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(reviews)")
    }
    migrations = [
        ("created_at", "TEXT"),
        ("url", "TEXT"),
        ("platform", "TEXT"),
    ]
    for col_name, col_type in migrations:
        if col_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE reviews ADD COLUMN {col_name} {col_type}"
            )
            logger.info("Migrated: added column %s to reviews table", col_name)

    # Backfill created_at from legacy date column
    if "created_at" in existing_columns and "date" in existing_columns:
        conn.execute(
            "UPDATE reviews SET created_at = date WHERE created_at IS NULL AND date IS NOT NULL"
        )
        logger.info("Migrated: backfilled created_at from legacy date column")


# ── Record model ─────────────────────────────────────────────────────────────
def _text_hash(text: str) -> str:
    """SHA-256 hash of the review text — used for idempotent inserts."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def insert_review(
    conn: sqlite3.Connection,
    *,
    source: str,
    app: str,
    text: str,
    rating: Optional[int] = None,
    created_at: Optional[str] = None,
    url: Optional[str] = None,
    language: Optional[str] = None,
    platform: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[str]:
    """
    Inserts a single review record. Returns the new record UUID, or None if
    a record with the same text already exists (idempotent by text_hash).

    Args:
        conn:         Active SQLite connection (from get_connection()).
        source:       One of the canonical source enum values.
        app:          One of the canonical app enum values.
        text:         Raw review/post body. Must be non-empty.
        rating:       Integer 1–5, or None for forum/Twitter/blog posts.
        created_at:   ISO 8601 date string (YYYY-MM-DD) from the source, or None.
        url:          Source URL linking to the original review/post, or None.
        language:     BCP 47 language code, or None.
        platform:     Platform identifier (e.g., 'google_play', 'apple_app_store'), or None.
        metadata:     Dict of source-specific fields, or None.

    Returns:
        The UUID of the inserted record, or None if already exists.
    """
    if not text or not text.strip():
        logger.warning(f"Skipping empty text record from source={source}, app={app}")
        return None

    record_id = str(uuid.uuid4())
    text_hash = _text_hash(text.strip())

    try:
        conn.execute(
            """
            INSERT INTO reviews (id, source, app, text, text_hash, rating, created_at, url, language, platform, metadata, inserted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                record_id,
                source,
                app,
                text.strip(),
                text_hash,
                rating,
                created_at,
                url,
                language,
                platform,
                json.dumps(metadata) if metadata else None,
            ),
        )
        return record_id
    except sqlite3.IntegrityError:
        # UNIQUE constraint on text_hash — exact duplicate, silently skip
        return None


def count_reviews(
    conn: sqlite3.Connection,
    source: Optional[str] = None,
    app: Optional[str] = None,
) -> int:
    """Returns count of records, optionally filtered by source and/or app."""
    where_clauses = []
    params = []
    if source:
        where_clauses.append("source = ?")
        params.append(source)
    if app:
        where_clauses.append("app = ?")
        params.append(app)

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    row = conn.execute(f"SELECT COUNT(*) FROM reviews {where}", params).fetchone()
    return row[0]


def get_date_range(conn: sqlite3.Connection) -> tuple[Optional[str], Optional[str]]:
    """Returns (earliest_date, latest_date) of non-null created_at records."""
    row = conn.execute(
        "SELECT MIN(created_at), MAX(created_at) FROM reviews WHERE created_at IS NOT NULL"
    ).fetchone()
    return (row[0], row[1])
