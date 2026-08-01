"""
src/ingestion/csv_connector.py
===================================
CSV upload connector for Zepto AI Review Engine.

Reads CSV files from a configurable upload directory and
normalizes each row into the canonical review schema.

Designed for survey responses, interview transcripts, and
manually collected community discussions.

Connector interface:
    connect(config: dict) -> list[dict]
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

REQUIRED_COLUMNS = ["text"]
OPTIONAL_COLUMNS = [
    "rating", "created_at", "url", "language", "platform",
    "app", "source", "id",
]

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
]


def _resolve_csv_date(date_val) -> str:
    """Convert a CSV date value to ISO 8601 date string."""
    if date_val is None:
        return ""
    date_str = str(date_val).strip()
    if not date_str:
        return ""
    if len(date_str) == 10 and date_str[:4].isdigit() and date_str[4] == "-":
        return date_str

    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

    return ""


def _is_within_date_range(
    date_str: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> bool:
    """Check if a date string falls within the configured range."""
    if not date_str:
        return False
    if start_date and date_str < start_date:
        return False
    if end_date and end_date != "current" and date_str > end_date:
        return False
    return True


def _read_csv_file(csv_path: Path, start_date: str, end_date: str, max_documents: int) -> list[dict]:
    """Read a single CSV file and return normalized records."""
    records: list[dict] = []

    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                logger.warning("CSV file %s has no header row, skipping", csv_path.name)
                return records

            for row in reader:
                if max_documents > 0 and len(records) >= max_documents:
                    break

                text = row.get("text", "").strip()
                if not text:
                    continue

                created_at = _resolve_csv_date(row.get("created_at", row.get("date", "")))
                if not _is_within_date_range(created_at, start_date, end_date):
                    continue

                rating = None
                rating_val = row.get("rating", "")
                if rating_val:
                    try:
                        rating = int(float(rating_val))
                        if rating < 1 or rating > 5:
                            rating = None
                    except (ValueError, TypeError):
                        rating = None

                record: dict[str, Any] = {
                    "id": str(uuid.uuid4()),
                    "source": "csv",
                    "app": row.get("app", "zepto"),
                    "text": text,
                    "rating": rating,
                    "created_at": created_at,
                    "url": row.get("url", ""),
                    "language": row.get("language", "en"),
                    "platform": row.get("platform", "csv_upload"),
                    "metadata": {
                        "csv_file": csv_path.name,
                        "original_row": {k: v for k, v in row.items() if k not in ("text",)},
                    },
                }
                records.append(record)

    except Exception as exc:
        logger.error("Failed to read CSV file %s: %s", csv_path.name, exc)

    return records


def connect(config: dict) -> list[dict]:
    """
    Read CSV files from the configured upload directory.

    Args:
        config: Source configuration dict from sources.json with keys:
            - config: dict with start_date, end_date, max_documents, upload_dir, encoding, delimiter

    Returns:
        List of normalized records from all CSV files in the upload directory.
    """
    source_config = config.get("config", {})
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_csv)
    upload_dir = source_config.get("upload_dir", str(settings.csv_upload_dir))
    encoding = source_config.get("encoding", "utf-8")
    delimiter = source_config.get("delimiter", ",")

    upload_path = Path(upload_dir)
    if not upload_path.exists():
        logger.info("CSV upload directory does not exist: %s", upload_path)
        return []

    all_records: list[dict] = []
    seen_text_hashes: set[str] = set()

    csv_files = sorted(upload_path.glob("*.csv"))
    if not csv_files:
        logger.info("No CSV files found in %s", upload_path)
        return []

    logger.info("Found %d CSV file(s) in %s", len(csv_files), upload_path)

    for csv_file in csv_files:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for CSV, stopping", max_documents
            )
            break

        logger.info("Reading CSV file: %s", csv_file.name)
        records = _read_csv_file(csv_file, start_date, end_date, max_documents)

        for record in records:
            text_hash = hashlib.sha256(
                record["text"].encode("utf-8")
            ).hexdigest()
            if text_hash not in seen_text_hashes:
                seen_text_hashes.add(text_hash)
                all_records.append(record)

    logger.info("Total CSV records collected: %d", len(all_records))
    return all_records