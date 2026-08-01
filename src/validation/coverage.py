"""
src/validation/coverage.py
============================
Coverage checking for Phase 6 validation.

Ensures all 8 canonical research questions have a corresponding insight
and that each insight meets minimum quality thresholds.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CoverageChecker:
    """
    Checks that all research questions are covered by insights and that
    each insight meets minimum schema requirements.
    """

    REQUIRED_QUESTION_IDS = {f"RQ{i}" for i in range(1, 9)}
    REQUIRED_INSIGHT_FIELDS = ["finding", "evidence", "implication", "segment", "confidence"]

    def __init__(self, research_questions: Optional[list[dict[str, Any]]] = None) -> None:
        if research_questions is None:
            from src.utils.config import load_research_questions
            rq_data = load_research_questions()
            self.research_questions = rq_data.get("questions", [])
        else:
            self.research_questions = research_questions

        self.rq_by_id: dict[str, dict[str, Any]] = {
            q["id"]: q for q in self.research_questions
        }

    def check(self, insights: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Run all coverage checks against the insight set.

        Args:
            insights: List of insight dicts from insights.json.

        Returns:
            Dict with coverage status, missing questions, and per-question details.
        """
        covered_ids = {i.get("research_question_id", "") for i in insights}
        missing = sorted(self.REQUIRED_QUESTION_IDS - covered_ids)
        extra = sorted(covered_ids - self.REQUIRED_QUESTION_IDS)

        insights_by_question: dict[str, dict[str, Any]] = {}
        schema_issues: list[str] = []
        insufficient_evidence: list[str] = []

        for insight in insights:
            qid = insight.get("research_question_id", "unknown")
            issues = self._validate_insight_schema(insight)
            if issues:
                schema_issues.append(f"{qid}: {'; '.join(issues)}")

            if insight.get("finding", "").startswith("Insufficient"):
                insufficient_evidence.append(qid)

            evidence_count = len(insight.get("evidence", []))
            insights_by_question[qid] = {
                "label": insight.get("research_question_label", ""),
                "finding_preview": insight.get("finding", "")[:80],
                "evidence_count": evidence_count,
                "confidence": insight.get("confidence", 0.0),
                "schema_valid": len(issues) == 0,
                "has_sufficient_evidence": evidence_count >= 2,
                "is_insufficient": insight.get("finding", "").startswith("Insufficient"),
            }

        all_covered = len(missing) == 0
        all_schema_valid = len(schema_issues) == 0
        all_sufficient = len(insufficient_evidence) == 0

        return {
            "all_questions_covered": all_covered,
            "coverage_count": len(covered_ids & self.REQUIRED_QUESTION_IDS),
            "total_questions": len(self.REQUIRED_QUESTION_IDS),
            "missing_questions": missing,
            "extra_question_ids": extra,
            "insights_by_question": insights_by_question,
            "schema_issues": schema_issues,
            "all_schema_valid": all_schema_valid,
            "insufficient_evidence_questions": insufficient_evidence,
            "all_have_sufficient_evidence": all_sufficient,
            "passed": all_covered and all_schema_valid and all_sufficient,
        }

    def _validate_insight_schema(self, insight: dict[str, Any]) -> list[str]:
        issues = []
        for field in self.REQUIRED_INSIGHT_FIELDS:
            if field not in insight:
                issues.append(f"missing field '{field}'")

        evidence = insight.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) < 2:
            issues.append(f"evidence has {len(evidence) if isinstance(evidence, list) else 0} items (need >= 2)")

        confidence = insight.get("confidence")
        if confidence is None or not isinstance(confidence, (int, float)):
            issues.append("missing or invalid confidence")

        return issues

    def get_missing_questions(self, insights: list[dict[str, Any]]) -> list[str]:
        """Convenience method: return only the missing question IDs."""
        covered = {i.get("research_question_id", "") for i in insights}
        return sorted(self.REQUIRED_QUESTION_IDS - covered)
