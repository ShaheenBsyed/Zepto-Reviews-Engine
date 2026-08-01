"""
src/validation/eval_report.py
===============================
Evaluation report builder for Phase 6 validation.

Aggregates faithfulness scores, coverage results, contradiction flags,
and spot-check results into a single JSON report saved to outputs/eval_report.json.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EvalReportBuilder:
    """
    Builds and saves the Phase 6 evaluation report.

    The report contains:
      - Per-insight faithfulness scores
      - Coverage status
      - Contradiction flags
      - Spot-check results
      - Overall pass/fail determination
    """

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = Path(output_dir or settings.outputs_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.output_dir / "eval_report.json"

    def build(
        self,
        insights: list[dict[str, Any]],
        faithfulness_scores: list[dict[str, Any]],
        coverage_result: dict[str, Any],
        contradictions: list[dict[str, Any]],
        spot_check_report: dict[str, Any],
        retrieval_results: Optional[dict[str, Any]] = None,
        pipeline_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Assemble the complete evaluation report.

        Args:
            insights: Original insights list.
            faithfulness_scores: Per-insight faithfulness dicts from FaithfulnessScorer.
            coverage_result: Coverage check dict from CoverageChecker.
            contradictions: Contradiction list from ContradictionDetector.
            spot_check_report: Spot-check report dict from SpotCheckManager.
            retrieval_results: Optional retrieval results dict.
            pipeline_metadata: Optional metadata from upstream phases.

        Returns:
            Complete evaluation report dict.
        """
        scores_by_qid = {s["research_question_id"]: s for s in faithfulness_scores}

        enriched_insights = []
        for insight in insights:
            qid = insight.get("research_question_id", "unknown")
            score_info = scores_by_qid.get(qid, {})
            enriched = dict(insight)
            enriched["faithfulness_score"] = score_info.get("faithfulness_score", 0.0)
            enriched["faithfulness_passed"] = score_info.get("faithfulness_passed", False)
            enriched["faithfulness_judge"] = score_info.get("judge", "unknown")
            enriched["faithfulness_reasoning"] = score_info.get("reasoning", "")
            enriched_insights.append(enriched)

        unresolved_contradictions = [
            c for c in contradictions if c.get("contradicts", False)
        ]

        contra_pairs_checked = 0
        if pipeline_metadata:
            contra_pairs_checked = pipeline_metadata.get("contradiction_pairs_checked", 0)
        if not contra_pairs_checked:
            contra_pairs_checked = len(contradictions)

        report = {
            "pipeline_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "Phase 6: Validation & Quality Assurance",
            "thresholds": {
                "faithfulness_min": 0.7,
                "max_hallucinated": 0,
                "max_partially_grounded": 1,
                "max_contradictions_unresolved": 0,
                "required_coverage": 8,
            },
            "coverage": coverage_result,
            "faithfulness": {
                "total_insights": len(faithfulness_scores),
                "passed": sum(1 for s in faithfulness_scores if s.get("faithfulness_passed", False)),
                "failed": sum(1 for s in faithfulness_scores if not s.get("faithfulness_passed", False)),
                "average_score": self._average([s.get("faithfulness_score", 0.0) for s in faithfulness_scores]),
                "per_insight": scores_by_qid,
            },
            "contradictions": {
                "total_pairs_checked": contra_pairs_checked,
                "contradictions_found": len(unresolved_contradictions),
                "unresolved": unresolved_contradictions,
            },
            "spot_check": spot_check_report,
            "insights": enriched_insights,
            "passed": self._determine_pass(
                coverage_result,
                faithfulness_scores,
                spot_check_report,
                unresolved_contradictions,
            ),
        }

        if retrieval_results:
            report["retrieval_summary"] = {
                "total_queries": len(retrieval_results.get("queries", [])),
                "total_chunks_retrieved": sum(
                    q.get("total_retrieved", 0) for q in retrieval_results.get("queries", [])
                ),
            }

        if pipeline_metadata:
            report["pipeline_metadata"] = pipeline_metadata

        return report

    def save(self, report: dict[str, Any]) -> Path:
        """Save the evaluation report to JSON."""
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Evaluation report saved to %s", self.output_path)
        return self.output_path

    def _average(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)

    def _determine_pass(
        self,
        coverage: dict[str, Any],
        faithfulness_scores: list[dict[str, Any]],
        spot_check: dict[str, Any],
        contradictions: list[dict[str, Any]],
    ) -> bool:
        if not coverage.get("passed", False):
            return False

        for score in faithfulness_scores:
            if not score.get("faithfulness_passed", False):
                return False

        if spot_check.get("hallucinated_count", 0) > 0:
            return False

        if len(contradictions) > 0:
            return False

        return True
