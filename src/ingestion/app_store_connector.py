"""
src/ingestion/app_store_connector.py
==========================================
Apple App Store scraper for Zepto AI Review Engine.

Uses the app-store-scraper library to fetch reviews for Zepto,
Blinkit, and Swiggy Instamart from the Indian App Store.

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

from app_store_scraper import AppStore

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_APPS = {
    "zepto": "1453856030",
    "blinkit": "1443909946",
    "swiggy_instamart": "989540920",
}


def _resolve_date(date_str: str) -> str:
    """Convert a date string from app-store-scraper to ISO 8601 date."""
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
    Scrape App Store reviews for all enabled apps.

    Args:
        config: Source configuration dict from sources.json with keys:
            - apps: list of app dicts with name, app_id, label
            - config: dict with country, start_date, end_date, max_documents

    Returns:
        List of normalized review records matching the canonical schema.
    """
    source_config = config.get("config", {})
    country = source_config.get("country", "in")
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_app_store)

    all_records: list[dict] = []
    apps = config.get("apps", [])

    for app_entry in apps:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for App Store, stopping", max_documents
            )
            break

        app_label = app_entry["label"]
        app_id = app_entry["app_id"]

        logger.info(
            "Scraping App Store for %s (%s) — max %d records",
            app_label,
            app_id,
            max_documents,
        )

        try:
            app = AppStore(
                country=country,
                app_name=app_label,
                app_id=app_id,
            )
            app.review(how_many=max_documents)
        except Exception as exc:
            logger.error(
                "Failed to scrape App Store for %s (%s): %s",
                app_label,
                app_id,
                exc,
            )
            continue

        for review in app.reviews:
            text = review.get("review", "")
            if not text or not text.strip():
                continue

            review_date = _resolve_date(review.get("date", ""))
            if not _is_within_date_range(review_date, start_date, end_date):
                continue

            record_id = str(uuid.uuid4())
            record: dict[str, Any] = {
                "id": record_id,
                "source": "app_store",
                "app": app_label,
                "text": text.strip(),
                "rating": review.get("score"),
                "created_at": review_date,
                "url": review.get("url", ""),
                "language": "en",
                "platform": "apple_app_store",
                "metadata": {
                    "app_id": app_id,
                    "version": review.get("version"),
                    "title": review.get("title"),
                },
            }
            all_records.append(record)

            if max_documents > 0 and len(all_records) >= max_documents:
                logger.info(
                    "Reached max_documents (%d) for App Store, stopping", max_documents
                )
                break

        logger.info(
            "Scraped %d records from App Store for %s", len(all_records), app_label
        )

    return all_records