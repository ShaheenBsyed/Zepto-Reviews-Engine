"""
src/ingestion/blog_connector.py
===================================
Public blog scraper for Zepto AI Review Engine.

Uses BeautifulSoup and requests to scrape blog posts that
discuss Zepto, grocery delivery, and category exploration.
Disabled by default — enable only after verifying HTML selectors.

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

BLOG_TARGETS = [
    {
        "name": "zepto_blog",
        "base_url": "https://www.zeptonow.com/blog",
        "search_path": "/",
    },
]


def _resolve_blog_date(date_str: str) -> str:
    """Convert a blog date string to ISO 8601 date."""
    if not date_str:
        return ""
    date_str = date_str.strip()

    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass

    try:
        dt = datetime.strptime(date_str, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass

    try:
        dt = datetime.strptime(date_str, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass

    now = datetime.now()
    date_str_lower = date_str.lower()
    try:
        if "just now" in date_str_lower or "today" in date_str_lower:
            return now.strftime("%Y-%m-%d")
        if "yesterday" in date_str_lower:
            dt = now - timedelta(days=1)
            return dt.strftime("%Y-%m-%d")
        if "week" in date_str_lower:
            dt = now - timedelta(days=7)
            return dt.strftime("%Y-%m-%d")
        if "month" in date_str_lower:
            parts = date_str_lower.split()
            months = int(parts[0]) if parts[0].isdigit() else 1
            dt = now - timedelta(days=months * 30)
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


def _scrape_blog(
    base_url: str,
    search_path: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_documents: int,
    max_pages: int = 5,
    delay_seconds: float = 2.0,
) -> list[dict]:
    """Scrape a blog for Zepto-related posts."""
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

        for article in soup.find_all("article") or soup.find_all("div", class_="post") or soup.find_all("div", class_="blog-post"):
            if max_documents > 0 and len(records) >= max_documents:
                break

            title_el = article.find("h1") or article.find("h2") or article.find("a", class_="title")
            title = title_el.get_text(strip=True) if title_el else ""

            body_el = article.find("div", class_="content") or article.find("div", class_="body") or article.find("div", class_="post-content")
            body = body_el.get_text(strip=True) if body_el else ""

            if not body:
                continue

            date_el = article.find("time") or article.find("span", class_="date") or article.find("span", class_="published")
            date_str = ""
            if date_el:
                date_str = date_el.get_text(strip=True)
                if not date_str[:4].isdigit():
                    date_str = _resolve_blog_date(date_str)
                else:
                    date_str = _resolve_blog_date(date_str)

            if not _is_within_date_range(date_str, start_date, end_date):
                continue

            url = ""
            if title_el and title_el.find("a"):
                url = title_el.find("a").get("href", "")
            elif base_url:
                url = base_url

            record_id = str(uuid.uuid4())
            record: dict[str, Any] = {
                "id": record_id,
                "source": "blog",
                "app": "zepto",
                "text": (title + " " + body).strip(),
                "rating": None,
                "created_at": date_str,
                "url": url,
                "language": "en",
                "platform": "blog",
                "metadata": {
                    "blog": "zepto_blog",
                    "article_title": title,
                },
            }
            records.append(record)

    except Exception as exc:
        logger.error("Failed to scrape blog %s: %s", base_url, exc)

    return records


def connect(config: dict) -> list[dict]:
    """
    Scrape public blogs for Zepto-related discussions.

    Args:
        config: Source configuration dict from sources.json with keys:
            - targets: list of blog target dicts
            - config: dict with start_date, end_date, max_documents, max_pages_per_target

    Returns:
        List of normalized blog post records matching the canonical schema.
    """
    if not config.get("enabled", False):
        logger.info("Blog connector is disabled in config, skipping")
        return []

    source_config = config.get("config", {})
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_blog)
    max_pages = source_config.get("max_pages_per_target", 5)
    delay_seconds = source_config.get("delay_seconds", 2)

    all_records: list[dict] = []
    seen_text_hashes: set[str] = set()

    targets = config.get("targets", BLOG_TARGETS)

    for target in targets:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for blogs, stopping", max_documents
            )
            break

        target_name = target.get("name", "unknown")
        base_url = target.get("base_url", "")
        search_path = target.get("search_path", "/")

        logger.info("Scraping blog: %s", target_name)

        records = _scrape_blog(
            base_url, search_path, start_date, end_date,
            max_documents, max_pages, delay_seconds,
        )

        for record in records:
            text_hash = hashlib.sha256(
                record["text"].encode("utf-8")
            ).hexdigest()
            if text_hash not in seen_text_hashes:
                seen_text_hashes.add(text_hash)
                all_records.append(record)

    logger.info("Total blog records collected: %d", len(all_records))
    return all_records