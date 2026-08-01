"""
src/ingestion/twitter_connector.py
======================================
Twitter/X API connector for Zepto AI Review Engine.

Uses the Twitter/X API v2 to fetch tweets mentioning Zepto
and related keywords. Requires a bearer token (TIER 3 source).

This connector is DISABLED by default. Enable only if Tier 1+2
corpus is below 800 records and a TWITTER_BEARER_TOKEN is set.

Each record is normalized to the canonical review schema defined in
config/sources.json and returned as a list of dicts.

Connector interface:
    connect(config: dict) -> list[dict]
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import requests

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _resolve_tweet_date(created_at: str) -> str:
    """Convert a Twitter created_at string to ISO 8601 date."""
    try:
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
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
    Fetch tweets mentioning Zepto and related keywords.

    Args:
        config: Source configuration dict from sources.json with keys:
            - search_queries: list of Twitter search queries
            - config: dict with start_date, end_date, max_documents, max_results_per_query

    Returns:
        List of normalized tweet records matching the canonical schema.
    """
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not bearer_token:
        logger.warning(
            "Twitter connector skipped: TWITTER_BEARER_TOKEN not set"
        )
        return []

    source_config = config.get("config", {})
    start_date = source_config.get("start_date", "2024-01-01")
    end_date = source_config.get("end_date", "current")
    max_documents = source_config.get("max_documents", settings.max_documents_twitter)
    max_results = source_config.get("max_results_per_query", 100)

    search_queries = config.get("search_queries", [])
    if not search_queries:
        logger.warning("No Twitter search queries configured")
        return []

    all_records: list[dict] = []
    seen_text_hashes: set[str] = set()

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "ZeptoReviewEngine/1.0",
    }

    for query in search_queries:
        if max_documents > 0 and len(all_records) >= max_documents:
            logger.info(
                "Reached max_documents (%d) for Twitter, stopping", max_documents
            )
            break

        logger.info("Fetching tweets for query: %s", query)

        search_url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": query,
            "max_results": min(max_results, max_documents - len(all_records)) if max_documents > 0 else max_results,
            "tweet.fields": "created_at,public_metrics",
        }

        try:
            resp = requests.get(
                search_url,
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Failed to fetch tweets for '%s': %s", query, exc)
            continue

        tweets = data.get("data", [])

        for tweet in tweets:
            text = tweet.get("text", "")
            if not text or not text.strip():
                continue

            created_at = tweet.get("created_at", "")
            date_str = _resolve_tweet_date(created_at)

            if not _is_within_date_range(date_str, start_date, end_date):
                continue

            tweet_id = tweet.get("id", "")
            url = f"https://twitter.com/i/web/status/{tweet_id}" if tweet_id else ""

            record: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "source": "twitter",
                "app": "zepto",
                "text": text.strip(),
                "rating": None,
                "created_at": date_str,
                "url": url,
                "language": "en",
                "platform": "twitter",
                "metadata": {
                    "tweet_id": tweet_id,
                    "public_metrics": tweet.get("public_metrics", {}),
                    "query": query,
                },
            }

            text_hash = __import__("hashlib").sha256(
                record["text"].encode("utf-8")
            ).hexdigest()
            if text_hash not in seen_text_hashes:
                seen_text_hashes.add(text_hash)
                all_records.append(record)

    logger.info("Total Twitter records collected: %d", len(all_records))
    return all_records