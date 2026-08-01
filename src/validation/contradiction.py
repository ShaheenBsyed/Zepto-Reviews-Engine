"""
src/validation/contradiction.py
==================================
Contradiction detection for Phase 6 validation.

Compares pairs of insights to identify logically incompatible claims.
Uses an LLM judge (Gemini) for pairwise comparison, with a fast
heuristic pre-filter to avoid unnecessary LLM calls.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RPM = 15
COOLDOWN_SECONDS = 60.0 / MAX_RPM


class ContradictionDetector:
    """
    Detects contradictory insights by comparing all pairs.

    Two insights are contradictory if they make logically incompatible
    claims about the same user behavior or phenomenon. Genuine segment
    differences (e.g., "Users find discovery easy" vs "Users say there
    is no discovery") are NOT contradictions — the LLM judge is prompted
    to distinguish these.
    """

    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self._last_call_time: float = 0.0
        self.total_pairs_checked: int = 0
        self.contradictions_found: list[dict[str, Any]] = []

    def detect(self, insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Check all insight pairs for contradictions.

        Args:
            insights: List of insight dicts.

        Returns:
            List of contradiction dicts with `insight_a`, `insight_b`,
            `contradicts`, `severity`, and `explanation`.
        """
        if len(insights) < 2:
            self.total_pairs_checked = 0
            self.contradictions_found = []
            return []

        contradictions = []
        pairs_checked = 0

        for idx_a, idx_b in itertools.combinations(range(len(insights)), 2):
            insight_a = insights[idx_a]
            insight_b = insights[idx_b]

            if self._heuristic_skip(insight_a, insight_b):
                continue

            pairs_checked += 1
            result = self._check_pair(insight_a, insight_b)
            if result.get("contradicts", False):
                contradictions.append(result)

        self.total_pairs_checked = pairs_checked
        self.contradictions_found = contradictions
        logger.info("Checked %d insight pairs, found %d contradictions", pairs_checked, len(contradictions))
        return contradictions

    def _heuristic_skip(
        self,
        insight_a: dict[str, Any],
        insight_b: dict[str, Any],
    ) -> bool:
        """Fast skip for pairs that are unlikely to be contradictory."""
        finding_a = insight_a.get("finding", "")
        finding_b = insight_b.get("finding", "")

        if not finding_a or not finding_b:
            return True

        if finding_a.startswith("Insufficient") or finding_b.startswith("Insufficient"):
            return True

        if finding_a == finding_b:
            return True

        return False

    def _check_pair(
        self,
        insight_a: dict[str, Any],
        insight_b: dict[str, Any],
    ) -> dict[str, Any]:
        """Check a single insight pair for contradiction."""
        if self.use_llm:
            return self._llm_check(insight_a, insight_b)
        return self._rule_based_check(insight_a, insight_b)

    def _llm_check(
        self,
        insight_a: dict[str, Any],
        insight_b: dict[str, Any],
    ) -> dict[str, Any]:
        """Use Gemini to judge whether two insights contradict."""
        prompt = self._build_contradiction_prompt(insight_a, insight_b)
        raw_response = self._call_llm(prompt)
        return self._parse_contradiction_response(raw_response, insight_a, insight_b)

    def _rule_based_check(
        self,
        insight_a: dict[str, Any],
        insight_b: dict[str, Any],
    ) -> dict[str, Any]:
        """Lightweight rule-based contradiction check without LLM."""
        finding_a = insight_a.get("finding", "").lower()
        finding_b = insight_b.get("finding", "").lower()

        negation_words = ["not", "no", "never", "difficult", "hard", "bad", "poor", "worst", "frustrating", "annoying"]
        positive_words = ["easy", "good", "great", "fast", "simple", "convenient", "love", "best", "excellent"]

        a_has_neg = any(w in finding_a for w in negation_words)
        b_has_pos = any(w in finding_b for w in positive_words)
        a_has_pos = any(w in finding_a for w in positive_words)
        b_has_neg = any(w in finding_b for w in negation_words)

        contradicts = (a_has_neg and b_has_pos) or (a_has_pos and b_has_neg)

        return {
            "insight_a": insight_a.get("research_question_id", "unknown"),
            "insight_b": insight_b.get("research_question_id", "unknown"),
            "finding_a": insight_a.get("finding", ""),
            "finding_b": insight_b.get("finding", ""),
            "contradicts": contradicts,
            "severity": "potential" if contradicts else "none",
            "explanation": "Rule-based heuristic detected opposing sentiment." if contradicts else "No contradiction detected by heuristic.",
            "judge": "rule-based",
        }

    def _build_contradiction_prompt(
        self,
        insight_a: dict[str, Any],
        insight_b: dict[str, Any],
    ) -> str:
        segment_a = insight_a.get("segment", "Unknown")
        segment_b = insight_b.get("segment", "Unknown")

        return (
            "You are a research quality analyst. Compare two research insights and "
            "determine if they contradict each other.\n\n"
            "IMPORTANT: Different user segments can have genuinely different experiences. "
            "For example, 'Users find discovery easy via deals' and 'Users say there is "
            "no discovery mechanism' are NOT contradictions if they apply to different segments. "
            "Only flag as a contradiction if the two insights make logically incompatible "
            "claims about the same user behavior or phenomenon.\n\n"
            f"Insight A (RQ: {insight_a.get('research_question_id', '?')}):\n"
            f"  Label: {insight_a.get('research_question_label', '')}\n"
            f"  Finding: {insight_a.get('finding', '')}\n"
            f"  Segment: {segment_a}\n\n"
            f"Insight B (RQ: {insight_b.get('research_question_id', '?')}):\n"
            f"  Label: {insight_b.get('research_question_label', '')}\n"
            f"  Finding: {insight_b.get('finding', '')}\n"
            f"  Segment: {segment_b}\n\n"
            "Output JSON:\n"
            '{"contradicts": false, "severity": "none", "explanation": "..."}\n'
            "severity options: none, low, medium, high"
        )

    def _call_llm(self, prompt: str) -> str:
        self._rate_limit()

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            logger.warning("google-genai not available for contradiction detection")
            return '{"contradicts": false, "severity": "none", "explanation": "LLM unavailable."}'

        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            return response.text.strip()
        except Exception as exc:
            logger.warning("LLM contradiction check failed: %s", exc)
            return '{"contradicts": false, "severity": "none", "explanation": "LLM call failed."}'

    def _parse_contraction_response(
        self,
        raw_text: str,
        insight_a: dict[str, Any],
        insight_b: dict[str, Any],
    ) -> dict[str, Any]:
        import re

        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.split("```json", 1)[1]
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return {
                    "insight_a": insight_a.get("research_question_id", "unknown"),
                    "insight_b": insight_b.get("research_question_id", "unknown"),
                    "finding_a": insight_a.get("finding", ""),
                    "finding_b": insight_b.get("finding", ""),
                    "contradicts": bool(data.get("contradicts", False)),
                    "severity": str(data.get("severity", "none")),
                    "explanation": str(data.get("explanation", "")),
                    "judge": "llm-judge-gemini",
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        match = re.search(r'"contradicts"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
        contradicts = match and match.group(1).lower() == "true" if match else False

        return {
            "insight_a": insight_a.get("research_question_id", "unknown"),
            "insight_b": insight_b.get("research_question_id", "unknown"),
            "finding_a": insight_a.get("finding", ""),
            "finding_b": insight_b.get("finding", ""),
            "contradicts": contradicts,
            "severity": "potential" if contradicts else "none",
            "explanation": "Parsed from partial response." if contradicts else "No contradiction detected.",
            "judge": "llm-judge-gemini-fallback",
        }

    def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < COOLDOWN_SECONDS:
            time.sleep(COOLDOWN_SECONDS - elapsed)
        self._last_call_time = time.time()
