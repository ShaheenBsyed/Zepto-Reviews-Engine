"""
src/ingestion/product_review_connector.py
=============================================
Product review website scraper for Zepto AI Review Engine.

Uses BeautifulSoup and requests to scrape product review sites
such as MouthShut and Trustpilot for Zepto-related reviews.
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

DEFAULT_TARGETS = [
    {
        "name": "mouthshut_reviews",
        "base_url": "https://www.mouthshut.com",
        "search_path": "/zepto-reviews",
    },
    {
        "name": "trustpilot",
        "base_url": "https://www.trustpilot.com",
        "search_path": "/search?q=zepto",
    },
]


def _resolve_review_date(date_str: str) -> str:
    """Convert a product review date string to ISO 8601 date."""
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


def _scrape_product_review_site(
    target_name: str,
    base_url: str,
    search_path: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_documents: int,
    max_pages: int = 5,
    delay_seconds: float = 2.0,
) -> list[dict]:
    """Scrape a product review site for Zepto-related reviews."""
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

        review_selectors = [
            ("div", "review"),
            ("div", "review-content"),
            ("div", "review-card"),
            ("div", "user-review"),
            ("div", "review-item"),
            ("article", "review"),
            ("div", "review-wrapper"),
        ]

        review_elements = []
        for tag, cls in review_selectors:
            review_elements.extend(soup.find_all(tag, class_=cls))

        if not review_elements:
            review_elements = soup.find_all("div", class_=lambda c: c and "review" in c.lower() if c else False)

        for review_el in review_elements:
            if max_documents > 0 and len(records) >= max_documents:
                break

            title_el = review_el.find("h3") or review_el.find("h4") or review_el.find("a", class_="title")
            title = title_el.get_text(strip=True) if title_el else ""

            body_el = (
                review_el.find("div", class_="review-text")
                or review_el.find("p", class_="review-body")
                or review_el.find("div", class_="content")
                or review_el.find("div", class_="review-content")
            )
            body = body_el.get_text(strip=True) if body_el else ""

            if not body:
                continue

            date_el = (
                review_el.find("span", class_="date")
                or review_el.find("time")
                or review_el.find("span", class_="review-date")
            )
            date_str = ""
            if date_el:
                date_str = date_el.get_text(strip=True)
                if not date_str[:4].isdigit():
                    date_str = _resolve_review_date(date_str)

            if not _is_within_date_range(date_str, start_date, end_date):
                continue

            rating = None
            rating_el = (
                review_el.find("span", class_="rating")
                or review_el.find("div", class_="rating")
                or review_el.find("meta", itemprop="ratingValue")
            )
            if rating_el:
                rating_val = rating_el.get("content") or rating_el.get_text(strip=True)
                try:
                    rating = int(float(rating_val))
                    if rating < 1 or rating > 5:
                        rating = None
                except (ValueError, TypeError):
                    rating = None

            url = ""
            if title_el and title_el.find("a"):
                url = title_el.find("a").get("href", "")
            elif base_url:
                url = base_url

            record_id = str(uuid.uuid4())
            record: dict[str, Any] = {
                "id": record_id,
                "source": "product_review",
                "app": "zepto",
                "text": (title + " " + body).strip(),
                "rating": rating,
                "created_at": date_str,
                "url": url,
                "language": "en",
                "platform": "product_review_site",
                "metadata": {
                    "review_site": target_name,
                    "review_title": title,
                },
            }
            records.append(record)

    except Exception as exc:
        logger.error("Failed to scrape product review site %s: %s", target_name, exc)

    return records


def connect(config: dict) -> list[dict]:
    """
    Scrape product review websites for Zepto-related reviews.

    Args:
        config: Source configuration dict from sources.json with keys:
            - targets: list of review site target dicts
            - config: dict with start_date, end_date, max_documents, max_pages_per_target

    Returns:
        List of normalized product review records matching the canonical schema.
    """
    if not config.get("enabled", False):
        logger.info("Product review connector is disabled in config, skipping")
        return []

    source_config = config.get("config", {})
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_product_review)
    max_pages = source_config.get("max_pages_per_target", 5)
    delay_seconds = source_config.get("delay_seconds", 2)

    all_records: list[dict] = []
    seen_text_hashes: set[str] = set()

    targets = config.get("targets", DEFAULT_TARGETS)

    for target in targets:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for product reviews, stopping", max_documents
            )
            break

        target_name = target.get("name", "unknown")
        base_url = target.get("base_url", "")
        search_path = target.get("search_path", "")

        logger.info("Scraping product review site: %s", target_name)

        records = _scrape_product_review_site(
            target_name, base_url, search_path,
            start_date, end_date, max_documents,
            max_pages, delay_seconds,
        )

        for record in records:
            text_hash = hashlib.sha256(
                record["text"].encode("utf-8")
            ).hexdigest()
            if text_hash not in seen_text_hashes:
                seen_text_hashes.add(text_hash)
                all_records.append(record)

    logger.info("Total product review records collected: %d", len(all_records))
    return all_records