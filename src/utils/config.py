"""
src/utils/config.py
===================
Central config loader. Reads .env and both JSON config files once at
import time. All other modules import from here — no module reads
.env or config/*.json directly.

Usage:
    from src.utils.config import settings, load_research_questions, load_sources
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# ── Locate project root (two levels up from this file) ─────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_DIR = PROJECT_ROOT / "config"

# Load .env into os.environ before reading any env vars
load_dotenv(ENV_FILE)


# ── Typed settings object ───────────────────────────────────────────────────
class Settings:
    """
    Centralises all env-var access with sensible defaults.
    Raises ValueError at startup if a required credential is missing.
    """

    # LLM / Embedding
    # Gemini API key — free tier via Google AI Studio
    # Get key at: https://aistudio.google.com/app/apikey
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")

    # gemini-2.5-flash is the current free-tier model
    llm_model: str = os.environ.get("LLM_MODEL", "gemini-2.5-flash")

    # Embedding runs locally via sentence-transformers — no API cost
    # all-MiniLM-L6-v2 produces 384-dimensional vectors
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Vector DB
    vector_db_backend: str = os.environ.get("VECTOR_DB_BACKEND", "chromadb")
    chroma_persist_dir: Path = PROJECT_ROOT / os.environ.get(
        "CHROMA_PERSIST_DIR", "data/embeddings/chroma"
    )

    # Data paths
    sqlite_db_path: Path = PROJECT_ROOT / os.environ.get(
        "SQLITE_DB_PATH", "data/raw/reviews.db"
    )
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    outputs_dir: Path = PROJECT_ROOT / "outputs"

    # Scraping / ingestion config
    scrape_lookback_months: int = int(os.environ.get("SCRAPE_LOOKBACK_MONTHS", "24"))
    ingestion_start_date: str = os.environ.get("INGESTION_START_DATE", "2024-01-01")
    ingestion_end_date: str = os.environ.get("INGESTION_END_DATE", "current")
    include_hinglish: bool = (
        os.environ.get("INCLUDE_HINGLISH", "false").lower() == "true"
    )
    min_review_word_count: int = int(os.environ.get("MIN_REVIEW_WORD_COUNT", "15"))

    # Max documents per source (-1 = unlimited)
    max_documents_play_store: int = int(os.environ.get("MAX_DOCUMENTS_PLAY_STORE", "10000"))
    max_documents_app_store: int = int(os.environ.get("MAX_DOCUMENTS_APP_STORE", "10000"))
    max_documents_quora: int = int(os.environ.get("MAX_DOCUMENTS_QUORA", "5000"))
    max_documents_blog: int = int(os.environ.get("MAX_DOCUMENTS_BLOG", "5000"))
    max_documents_product_review: int = int(os.environ.get("MAX_DOCUMENTS_PRODUCT_REVIEW", "5000"))
    max_documents_forum: int = int(os.environ.get("MAX_DOCUMENTS_FORUM", "5000"))
    max_documents_twitter: int = int(os.environ.get("MAX_DOCUMENTS_TWITTER", "1000"))
    max_documents_csv: int = int(os.environ.get("MAX_DOCUMENTS_CSV", "-1"))

    # CSV upload directory
    csv_upload_dir: Path = PROJECT_ROOT / os.environ.get(
        "CSV_UPLOAD_DIR", "data/csv_uploads"
    )

    # RAG
    rag_top_k: int = int(os.environ.get("RAG_TOP_K", "10"))

    # Validation
    faithfulness_threshold: float = float(
        os.environ.get("FAITHFULNESS_THRESHOLD", "0.7")
    )

    def validate_required(self) -> list[str]:
        """
        Returns a list of missing required credentials.
        GEMINI_API_KEY is the only external credential this project needs.
        Community forums and app stores use public scraping or free access paths.
        """
        missing = []
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY  (free at https://aistudio.google.com/app/apikey)")
        return missing


# Singleton instance
settings = Settings()


# ── JSON config loaders ─────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_research_questions() -> dict:
    """Load and cache config/research_questions.json."""
    path = CONFIG_DIR / "research_questions.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_sources() -> dict:
    """Load and cache config/sources.json."""
    path = CONFIG_DIR / "sources.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_relevance_keywords() -> list[str]:
    """
    Returns the union of all relevance_keywords arrays across all 8 research
    questions. This is the keyword list used by the Phase 2 relevance filter.
    """
    rq = load_research_questions()
    keywords: set[str] = set()
    for q in rq["questions"]:
        keywords.update(q.get("relevance_keywords", []))
    return sorted(keywords)


def get_semantic_queries() -> dict[str, str]:
    """
    Returns a dict mapping research question ID → user-voice semantic query.
    Used by the Phase 5 RAG engine.
    """
    rq = load_research_questions()
    return {q["id"]: q["semantic_query"] for q in rq["questions"]}


def get_enabled_sources() -> list[dict]:
    """Returns only the source configs that have enabled=true."""
    sources = load_sources()
    return [s for s in sources["sources"] if s.get("enabled", False)]
