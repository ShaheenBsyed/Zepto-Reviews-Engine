"""
src/validation/spot_check.py
==============================
Human spot-check utilities for Phase 6 validation.

Manages the workflow where a human reviewer reads a sample of insights
and rates them as Grounded / Partially Grounded / Hallucinated.
"""

from __future__ import annotations

import json
import random
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

VALID_RATINGS = {"grounded", "partially_grounded", "hallucinated"}


class SpotCheckManager:
    """
    Manages the human spot-check workflow for Phase 6 validation.

    Selects a random sample of insights, records reviewer ratings and notes,
    and produces a summary report.
    """

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = Path(output_dir or settings.outputs_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reviews: list[dict[str, Any]] = []
        self._state_path = self.output_dir / "spot_check_state.json"
        self._load_state()

    def _load_state(self) -> None:
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.reviews = data.get("reviews", [])
            except (json.JSONDecodeError, OSError):
                self.reviews = []

    def _save_state(self) -> None:
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump({"reviews": self.reviews}, f, indent=2, ensure_ascii=False, default=str)

    def select_insights(
        self,
        insights: list[dict[str, Any]],
        n: int = 5,
        seed: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Select n random insights for human review.

        Args:
            insights: Full list of insights from insights.json.
            n: Number of insights to select (default 5).
            seed: Optional random seed for reproducibility.

        Returns:
            List of selected insight dicts with a `spot_check_index` added.
        """
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random

        if not insights:
            return []

        selected = rng.sample(insights, min(n, len(insights)))
        for idx in range(len(selected)):
            selected[idx] = dict(selected[idx])
            selected[idx]["spot_check_index"] = idx + 1
            selected[idx]["spot_check_status"] = "pending"
        return selected

    def record_review(
        self,
        insight_id: str,
        rating: str,
        notes: str = "",
        reviewer: str = "human_reviewer",
    ) -> dict[str, Any]:
        """
        Record a human reviewer's rating for an insight.

        Args:
            insight_id: The research_question_id of the insight.
            rating: One of "Grounded", "Partially Grounded", "Hallucinated".
            notes: Optional reviewer notes.
            reviewer: Reviewer identifier.

        Returns:
            The recorded review dict.
        """
        rating_lower = rating.lower().replace(" ", "_")
        if rating_lower not in VALID_RATINGS:
            raise ValueError(
                f"Invalid rating '{rating}'. Must be one of: {sorted(VALID_RATINGS)}"
            )

        review = {
            "insight_id": insight_id,
            "rating": rating_lower,
            "rating_display": rating,
            "notes": notes,
            "reviewer": reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.reviews = [r for r in self.reviews if r.get("insight_id") != insight_id]
        self.reviews.append(review)
        self._save_state()

        logger.info("Recorded spot-check review for %s: %s", insight_id, rating_lower)
        return review

    def get_report(self) -> dict[str, Any]:
        """
        Generate a spot-check summary report.

        Returns:
            Dict with review counts, hallucination count, and per-insight ratings.
        """
        total = len(self.reviews)
        grounded = sum(1 for r in self.reviews if r.get("rating") == "grounded")
        partially = sum(1 for r in self.reviews if r.get("rating") == "partially_grounded")
        hallucinated = sum(1 for r in self.reviews if r.get("rating") == "hallucinated")
        pending = sum(1 for r in self.reviews if r.get("rating") not in VALID_RATINGS)

        return {
            "total_reviews": total,
            "grounded_count": grounded,
            "partially_grounded_count": partially,
            "hallucinated_count": hallucinated,
            "pending_count": pending,
            "hallucination_rate": hallucinated / total if total > 0 else 0.0,
            "passed": hallucinated == 0 and partially <= 1,
            "reviews": self.reviews,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_unreviewed(self, insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return insights that have not yet been reviewed."""
        reviewed_ids = {r.get("insight_id") for r in self.reviews}
        return [i for i in insights if i.get("research_question_id") not in reviewed_ids]

    def clear(self) -> None:
        """Clear all recorded reviews."""
        self.reviews = []
        self._save_state()
