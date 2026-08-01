"""
src/ingestion/play_store_connector.py
==========================================
Google Play Store scraper for Zepto AI Review Engine.

Uses the google-play-scraper library to fetch reviews for Zepto,
Blinkit, Swiggy Instamart, and BigBasket from the Indian Play Store.

Each record is normalized to the canonical review schema defined in
config/sources.json and returned as a list of dicts.

Connector interface:
    connect(config: dict) -> list[dict]
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from google_play_scraper import Sort, reviews

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _resolve_date(date_val) -> str:
    """Convert a date value from google-play-scraper to ISO 8601 date string."""
    if isinstance(date_val, datetime):
        return date_val.strftime("%Y-%m-%d")
    try:
        dt = datetime.fromisoformat(str(date_val).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _parse_date(date_str: str) -> str:
    """Parse an ISO 8601 date string, returning it as YYYY-MM-DD or empty string."""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
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


def connect(config: dict) -> list[dict]:
    """
    Scrape Play Store reviews for all enabled apps.

    Args:
        config: Source configuration dict from sources.json with keys:
            - apps: list of app dicts with name, app_id, label
            - config: dict with country, lang, start_date, end_date, max_documents

    Returns:
        List of normalized review records matching the canonical schema.
    """
    source_config = config.get("config", {})
    country = source_config.get("country", "in")
    lang = source_config.get("lang", "en")
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_play_store)

    all_records: list[dict] = []
    apps = config.get("apps", [])

    for app_entry in apps:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for Play Store, stopping", max_documents
            )
            break

        app_label = app_entry["label"]
        app_id = app_entry["app_id"]

        logger.info(
            "Scraping Play Store for %s (%s) — max %d records",
            app_label,
            app_id,
            max_documents,
        )

        try:
            result, _ = reviews(
                app_id,
                lang=lang,
                country=country,
                sort=Sort.MOST_RELEVANT,
                count=max_documents,
            )
        except Exception as exc:
            logger.error(
                "Failed to scrape Play Store for %s (%s): %s",
                app_label,
                app_id,
                exc,
            )
            continue

        for review in result:
            text = review.get("content", "")
            if not text or not text.strip():
                continue

            review_date = _resolve_date(review.get("at", ""))
            if not _is_within_date_range(review_date, start_date, end_date):
                continue

            record_id = str(uuid.uuid4())
            record: dict[str, Any] = {
                "id": record_id,
                "source": "play_store",
                "app": app_label,
                "text": text.strip(),
                "rating": review.get("score"),
                "created_at": review_date,
                "url": review.get("url", ""),
                "language": lang,
                "platform": "google_play",
                "metadata": {
                    "app_id": app_id,
                    "thumbs_up": review.get("thumbsUpCount"),
                    "reply_content": review.get("replyContent"),
                    "at": str(review.get("at", "")),
                },
            }
            all_records.append(record)

            if max_documents > 0 and len(all_records) >= max_documents:
                logger.info(
                    "Reached max_documents (%d) for Play Store, stopping", max_documents
                )
                break

        logger.info(
            "Scraped %d records from Play Store for %s", len(all_records), app_label
        )

    return all_records