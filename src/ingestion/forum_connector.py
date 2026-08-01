"""
src/ingestion/forum_connector.py
====================================
Community forum scraper for Zepto AI Review Engine.

Uses BeautifulSoup and requests to scrape posts from
MouthShut and LocalCircles. Disabled by default — enable
only after verifying HTML selectors are current.

Each record is normalized to the canonical review schema defined
in config/sources.json and returned as a list of dicts.

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

FORUM_TARGETS = {
    "mouthshut": {
        "base_url": "https://www.mouthshut.com",
        "search_path": "/search?q=zepto+delivery",
    },
    "localcircles": {
        "base_url": "https://www.localcircles.com",
        "search_path": "/search?q=zepto+grocery",
    },
}


def _resolve_relative_date(relative_str: str) -> str:
    """
    Convert a relative date string (e.g., '3 months ago') to an
    ISO 8601 date string. Returns empty string if resolution fails.
    """
    relative_str = relative_str.strip().lower()
    now = datetime.now()

    try:
        if "just now" in relative_str or "a few seconds" in relative_str:
            return now.strftime("%Y-%m-%d")
        if "minute" in relative_str:
            parts = relative_str.split()
            minutes = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(minutes=minutes)
            return dt.strftime("%Y-%m-%d")
        if "hour" in relative_str:
            parts = relative_str.split()
            hours = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(hours=hours)
            return dt.strftime("%Y-%m-%d")
        if "day" in relative_str:
            parts = relative_str.split()
            days = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(days=days)
            return dt.strftime("%Y-%m-%d")
        if "month" in relative_str:
            parts = relative_str.split()
            months = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(days=months * 30)
            return dt.strftime("%Y-%m-%d")
        if "year" in relative_str:
            parts = relative_str.split()
            years = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(days=years * 365)
            return dt.strftime("%Y-%m-%d")
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


def _scrape_mouthshut(
    base_url: str,
    search_path: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_documents: int,
    max_pages: int = 5,
    delay_seconds: float = 2.0,
) -> list[dict]:
    """Scrape MouthShut for Zepto-related reviews."""
    records: list[dict] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        search_url = f"{base_url}{search_path}"
        time.sleep(delay_seconds)
        resp = requests.get(search_url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for article in soup.find_all("article", class_="review"):
            if max_documents > 0 and len(records) >= max_documents:
                break

            title_el = article.find("h2") or article.find("a", class_="title")
            title = title_el.get_text(strip=True) if title_el else ""

            body_el = article.find("div", class_="review-text")
            body = body_el.get_text(strip=True) if body_el else ""

            if not body:
                continue

            date_el = article.find("span", class_="date") or article.find(
                "time"
            )
            date_str = ""
            if date_el:
                date_str = date_el.get_text(strip=True)
                if not date_str[:4].isdigit():
                    date_str = _resolve_relative_date(date_str)

            if not _is_within_date_range(date_str, start_date, end_date):
                continue

            url = ""
            if title_el and title_el.find("a"):
                url = base_url + title_el.find("a").get("href", "")

            record_id = str(uuid.uuid4())
            record: dict[str, Any] = {
                "id": record_id,
                "source": "forum",
                "app": "zepto",
                "text": (title + " " + body).strip(),
                "rating": None,
                "created_at": date_str,
                "url": url,
                "language": "en",
                "platform": "community_forum",
                "metadata": {
                    "forum": "mouthshut",
                    "thread_title": title,
                },
            }
            records.append(record)

    except Exception as exc:
        logger.error("Failed to scrape MouthShut: %s", exc)

    return records


def _scrape_localcircles(
    base_url: str,
    search_path: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_documents: int,
    max_pages: int = 5,
    delay_seconds: float = 2.0,
) -> list[dict]:
    """Scrape LocalCircles for Zepto-related discussions."""
    records: list[dict] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        search_url = f"{base_url}{search_path}"
        time.sleep(delay_seconds)
        resp = requests.get(search_url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for post in soup.find_all("div", class_="post"):
            if max_documents > 0 and len(records) >= max_documents:
                break

            title_el = post.find("h3") or post.find("a", class_="title")
            title = title_el.get_text(strip=True) if title_el else ""

            body_el = post.find("div", class_="body") or post.find(
                "div", class_="content"
            )
            body = body_el.get_text(strip=True) if body_el else ""

            if not body:
                continue

            date_el = post.find("span", class_="date") or post.find("time")
            date_str = ""
            if date_el:
                date_str = date_el.get_text(strip=True)
                if not date_str[:4].isdigit():
                    date_str = _resolve_relative_date(date_str)

            if not _is_within_date_range(date_str, start_date, end_date):
                continue

            url = ""
            if title_el and title_el.find("a"):
                url = base_url + title_el.find("a").get("href", "")

            record_id = str(uuid.uuid4())
            record: dict[str, Any] = {
                "id": record_id,
                "source": "forum",
                "app": "zepto",
                "text": (title + " " + body).strip(),
                "rating": None,
                "created_at": date_str,
                "url": url,
                "language": "en",
                "platform": "community_forum",
                "metadata": {
                    "forum": "localcircles",
                    "thread_title": title,
                },
            }
            records.append(record)

    except Exception as exc:
        logger.error("Failed to scrape LocalCircles: %s", exc)

    return records


def connect(config: dict) -> list[dict]:
    """
    Scrape community forums for Zepto-related discussions.

    Args:
        config: Source configuration dict from sources.json with keys:
            - targets: list of forum target dicts
            - config: dict with start_date, end_date, max_documents, max_pages_per_target, delay_seconds

    Returns:
        List of normalized forum post records matching the canonical schema.
    """
    if not settings.include_hinglish and not config.get("enabled", False):
        logger.info("Forum connector is disabled in config, skipping")
        return []

    source_config = config.get("config", {})
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_forum)
    max_pages = source_config.get("max_pages_per_target", 5)
    delay_seconds = source_config.get("delay_seconds", 2)

    all_records: list[dict] = []
    seen_text_hashes: set[str] = set()

    targets = config.get("targets", [])

    for target in targets:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for forums, stopping", max_documents
            )
            break

        target_name = target.get("name", "unknown")
        base_url = target.get("base_url", "")
        search_path = target.get("search_path", "")

        logger.info("Scraping forum: %s", target_name)

        if target_name == "mouthshut":
            records = _scrape_mouthshut(
                base_url, search_path, start_date, end_date,
                max_documents, max_pages, delay_seconds,
            )
        elif target_name == "localcircles":
            records = _scrape_localcircles(
                base_url, search_path, start_date, end_date,
                max_documents, max_pages, delay_seconds,
            )
        else:
            logger.warning("Unknown forum target: %s", target_name)
            continue

        for record in records:
            text_hash = hashlib.sha256(
                record["text"].encode("utf-8")
            ).hexdigest()
            if text_hash not in seen_text_hashes:
                seen_text_hashes.add(text_hash)
                all_records.append(record)

    logger.info("Total forum records collected: %d", len(all_records))
    return all_records