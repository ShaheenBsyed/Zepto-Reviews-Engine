"""
src/ingestion/quora_connector.py
=====================================
Quora discussions scraper for Zepto AI Review Engine.

Uses BeautifulSoup and requests to scrape publicly accessible
Quora questions and answers related to Zepto, grocery delivery,
and category exploration. Disabled by default — enable only after
verifying HTML selectors are current.

Each record is normalized to the canonical review schema defined in
config/sources.json and returned as a list of dicts.

Connector interface:
    connect(config: dict) -> list[dict]
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

QUORA_SEARCH_URLS = [
    "https://www.quora.com/search?q=Zepto+app+review",
    "https://www.quora.com/search?q=Zepto+grocery+delivery",
    "https://www.quora.com/search?q=Zepto+vs+Blinkit",
    "https://www.quora.com/search?q=Zepto+category+exploration",
]


def _resolve_quora_date(date_str: str) -> str:
    """Convert a Quora date string to ISO 8601 date."""
    if not date_str:
        return ""
    date_str = date_str.strip().lower()
    now = datetime.now()

    try:
        if "just now" in date_str or "a few seconds" in date_str:
            return now.strftime("%Y-%m-%d")
        if "minute" in date_str or "minutes ago" in date_str:
            parts = date_str.split()
            minutes = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(minutes=minutes)
            return dt.strftime("%Y-%m-%d")
        if "hour" in date_str or "hours ago" in date_str:
            parts = date_str.split()
            hours = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(hours=hours)
            return dt.strftime("%Y-%m-%d")
        if "day" in date_str or "days ago" in date_str:
            parts = date_str.split()
            days = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(days=days)
            return dt.strftime("%Y-%m-%d")
        if "month" in date_str or "months ago" in date_str:
            parts = date_str.split()
            months = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(days=months * 30)
            return dt.strftime("%Y-%m-%d")
        if "year" in date_str or "years ago" in date_str:
            parts = date_str.split()
            years = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(days=years * 365)
            return dt.strftime("%Y-%m-%d")
        if len(date_str) == 10 and date_str[:4].isdigit():
            return date_str
    except (ValueError, IndexError, OSError):
        pass

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


def _scrape_quora_search(
    search_url: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_documents: int,
    max_pages: int = 10,
    delay_seconds: float = 3.0,
) -> list[dict]:
    """Scrape Quora search results for Zepto-related discussions."""
    records: list[dict] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        time.sleep(delay_seconds)
        resp = requests.get(search_url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for result in soup.find_all("div", class_="q-box"):
            if max_documents > 0 and len(records) >= max_documents:
                break

            question_el = result.find("span", class_="q-text") or result.find("a", class_="question_link")
            question_text = question_el.get_text(strip=True) if question_el else ""

            if not question_text:
                continue

            answer_el = result.find("div", class_="q-markup") or result.find("div", class_="answer")
            answer_text = answer_el.get_text(strip=True) if answer_el else ""

            if not answer_text:
                continue

            date_el = result.find("span", class_="date") or result.find("time")
            date_str = ""
            if date_el:
                date_str = date_el.get_text(strip=True)
                if not date_str[:4].isdigit():
                    date_str = _resolve_quora_date(date_str)

            if not _is_within_date_range(date_str, start_date, end_date):
                continue

            url = ""
            if question_el and question_el.find("a"):
                href = question_el.find("a").get("href", "")
                url = f"https://www.quora.com{href}" if href.startswith("/") else href

            combined_text = (question_text + " " + answer_text).strip()

            record_id = str(uuid.uuid4())
            record: dict[str, Any] = {
                "id": record_id,
                "source": "quora",
                "app": "zepto",
                "text": combined_text,
                "rating": None,
                "created_at": date_str,
                "url": url,
                "language": "en",
                "platform": "quora",
                "metadata": {
                    "question": question_text,
                    "forum": "quora",
                },
            }
            records.append(record)

    except Exception as exc:
        logger.error("Failed to scrape Quora (%s): %s", search_url, exc)

    return records


def connect(config: dict) -> list[dict]:
    """
    Scrape Quora for Zepto-related discussions.

    Args:
        config: Source configuration dict from sources.json with keys:
            - search_queries: list of Quora search URLs
            - config: dict with start_date, end_date, max_documents, max_pages_per_query

    Returns:
        List of normalized Quora discussion records matching the canonical schema.
    """
    if not config.get("enabled", False):
        logger.info("Quora connector is disabled in config, skipping")
        return []

    source_config = config.get("config", {})
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_quora)
    max_pages = source_config.get("max_pages_per_query", 10)

    all_records: list[dict] = []
    seen_text_hashes: set[str] = set()

    search_urls = config.get("search_queries", QUORA_SEARCH_URLS)

    for search_url in search_urls:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for Quora, stopping", max_documents
            )
            break

        logger.info("Scraping Quora: %s", search_url)

        records = _scrape_quora_search(
            search_url, start_date, end_date,
            max_documents, max_pages,
        )

        for record in records:
            text_hash = hashlib.sha256(
                record["text"].encode("utf-8")
            ).hexdigest()
            if text_hash not in seen_text_hashes:
                seen_text_hashes.add(text_hash)
                all_records.append(record)

    logger.info("Total Quora records collected: %d", len(all_records))
    return all_records