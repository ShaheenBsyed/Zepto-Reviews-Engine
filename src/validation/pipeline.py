"""
src/validation/pipeline.py
============================
Phase 6: Validation & Quality Assurance orchestrator.

Runs the complete Phase 6 workflow:
  1. Load insights and retrieval results
  2. Score faithfulness for each insight
  3. Check coverage of all 8 research questions
  4. Detect contradictions between insights
  5. Run spot-check selection (human review prep)
  6. Build and save the evaluation report

Exit criteria (from implementationplan.md):
  - All 8 insights have faithfulness score >= 0.7
  - 0 insights rated hallucinated in spot-check
  - All 8 research questions covered
  - Zero unresolved contradictions
  - outputs/eval_report.json is populated
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_INSIGHTS_PATH = "outputs/insights.json"
DEFAULT_RETRIEVAL_PATH = "outputs/retrieval_results.json"
DEFAULT_OUTPUT_PATH = "outputs/eval_report.json"


class ValidationPipeline:
    """
    Orchestrates Phase 6 validation checks.

    Loads Phase 5 outputs, runs faithfulness scoring, coverage checking,
    contradiction detection, and spot-check preparation, then saves
    the aggregated evaluation report.
    """

    def __init__(
        self,
        insights_path: Optional[str] = None,
        retrieval_results_path: Optional[str] = None,
        output_path: Optional[str] = None,
        faithfulness_threshold: float = 0.7,
    ) -> None:
        self.insights_path = Path(insights_path or settings.outputs_dir / "insights.json")
        self.retrieval_results_path = Path(
            retrieval_results_path or settings.outputs_dir / "retrieval_results.json"
        )
        self.output_path = Path(output_path or settings.outputs_dir / "eval_report.json")
        self.faithfulness_threshold = faithfulness_threshold

        self.insights: list[dict[str, Any]] = []
        self.retrieval_results: dict[str, Any] = {}
        self.themes: list[dict[str, Any]] = []
        self._contra_pairs_checked: int = 0

    def run(self) -> dict[str, Any]:
        """
        Execute the full Phase 6 validation pipeline.

        Returns:
            Complete evaluation report dict.
        """
        logger.info("Starting Phase 6: Validation & Quality Assurance")
        self._load_inputs()

        if not self.insights:
            logger.warning("No insights found. Phase 6 cannot proceed without Phase 5 outputs.")
            return self._build_empty_report()

        logger.info("Loaded %d insights", len(self.insights))

        faithfulness_scores = self._run_faithfulness()
        coverage_result = self._run_coverage()
        contradictions = self._run_contradictions()
        spot_check = self._run_spot_check()

        report_builder = self._init_report_builder()
        report = report_builder.build(
            insights=self.insights,
            faithfulness_scores=faithfulness_scores,
            coverage_result=coverage_result,
            contradictions=contradictions,
            spot_check_report=spot_check,
            retrieval_results=self.retrieval_results,
            pipeline_metadata=self._collect_metadata(
                contra_pairs_checked=self._contra_pairs_checked
            ),
        )

        saved_path = report_builder.save(report)
        report["output_path"] = str(saved_path)

        self._log_summary(report)
        return report

    def _load_inputs(self) -> None:
        """Load insights, retrieval results, and themes from disk."""
        if self.insights_path.exists():
            with open(self.insights_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.insights = data.get("insights", [])
            logger.info("Loaded %d insights from %s", len(self.insights), self.insights_path)
        else:
            logger.warning("Insights file not found: %s", self.insights_path)

        if self.retrieval_results_path.exists():
            with open(self.retrieval_results_path, "r", encoding="utf-8") as f:
                self.retrieval_results = json.load(f)
            logger.info("Loaded retrieval results from %s", self.retrieval_results_path)
        else:
            logger.warning("Retrieval results file not found: %s", self.retrieval_results_path)

        themes_path = settings.outputs_dir / "themes.json"
        if themes_path.exists():
            with open(themes_path, "r", encoding="utf-8") as f:
                self.themes = json.load(f)
            logger.info("Loaded %d themes", len(self.themes))

    def _run_faithfulness(self) -> list[dict[str, Any]]:
        from src.validation.faithfulness import FaithfulnessScorer

        logger.info("Running faithfulness scoring (threshold=%.2f)", self.faithfulness_threshold)
        scorer = FaithfulnessScorer(threshold=self.faithfulness_threshold)
        scores = scorer.score_all(self.insights, self.retrieval_results)

        passed = sum(1 for s in scores if s.get("faithfulness_passed", False))
        logger.info("Faithfulness: %d/%d passed", passed, len(scores))
        return scores

    def _run_coverage(self) -> dict[str, Any]:
        from src.validation.coverage import CoverageChecker

        logger.info("Running coverage check")
        checker = CoverageChecker()
        result = checker.check(self.insights)
        logger.info(
            "Coverage: %d/%d questions covered, passed=%s",
            result.get("coverage_count", 0),
            result.get("total_questions", 0),
            result.get("passed", False),
        )
        return result

    def _run_contradictions(self) -> list[dict[str, Any]]:
        from src.validation.contradiction import ContradictionDetector

        logger.info("Running contradiction detection")
        detector = ContradictionDetector()
        results = detector.detect(self.insights)
        self._contra_pairs_checked = detector.total_pairs_checked
        logger.info("Contradictions found: %d (out of %d pairs checked)", len(results), self._contra_pairs_checked)
        return results

    def _run_spot_check(self) -> dict[str, Any]:
        from src.validation.spot_check import SpotCheckManager

        logger.info("Running spot-check preparation")
        manager = SpotCheckManager(output_dir=str(settings.outputs_dir))
        selected = manager.select_insights(self.insights, n=5)
        check_report = manager.get_report()

        report: dict[str, Any] = {
            **check_report,
            "selected_insights": [
                {
                    "research_question_id": s.get("research_question_id"),
                    "research_question_label": s.get("research_question_label"),
                    "finding": s.get("finding", "")[:120],
                    "spot_check_index": s.get("spot_check_index"),
                    "status": s.get("spot_check_status", "pending"),
                }
                for s in selected
            ],
            "total_selected": len(selected),
            "unreviewed_count": len(manager.get_unreviewed(self.insights)),
            "review_instructions": (
                "Review each selected insight. Rate as: Grounded, Partially Grounded, or Hallucinated. "
                "Add notes explaining your rating. Use SpotCheckManager.record_review() to submit."
            ),
        }
        return report

    def _init_report_builder(self) -> Any:
        from src.validation.eval_report import EvalReportBuilder

        return EvalReportBuilder(output_dir=str(self.output_path.parent))

    def _collect_metadata(self, contra_pairs_checked: int = 0) -> dict[str, Any]:
        return {
            "pipeline_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "Phase 6: Validation & Quality Assurance",
            "faithfulness_threshold": self.faithfulness_threshold,
            "total_insights": len(self.insights),
            "total_themes": len(self.themes),
            "retrieval_queries": len(self.retrieval_results.get("queries", [])),
            "contradiction_pairs_checked": contra_pairs_checked,
        }

    def _build_empty_report(self) -> dict[str, Any]:
        builder = self._init_report_builder()
        report = {
            "pipeline_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "Phase 6: Validation & Quality Assurance",
            "passed": False,
            "error": "No insights available for validation.",
            "coverage": {"passed": False, "all_questions_covered": False},
            "faithfulness": {"total_insights": 0, "passed": 0, "failed": 0, "average_score": 0.0},
            "contradictions": {"total_pairs_checked": 0, "contradictions_found": 0, "unresolved": []},
            "spot_check": {"total_reviews": 0, "hallucinated_count": 0, "passed": False},
            "insights": [],
        }
        builder.save(report)
        return report

    def _log_summary(self, report: dict[str, Any]) -> None:
        logger.info("=" * 60)
        logger.info("Phase 6 Validation Summary")
        logger.info("=" * 60)
        logger.info("  Coverage:       %s", report.get("coverage", {}).get("passed", False))
        logger.info(
            "  Faithfulness:   %s (%s passed)",
            report.get("faithfulness", {}).get("average_score", 0.0),
            report.get("faithfulness", {}).get("passed", 0),
        )
        logger.info(
            "  Contradictions: %d unresolved",
            len(report.get("contradictions", {}).get("unresolved", [])),
        )
        logger.info(
            "  Spot-check:     %d hallucinated",
            report.get("spot_check", {}).get("hallucinated_count", 0),
        )
        logger.info("  OVERALL PASS:  %s", report.get("passed", False))
        logger.info("=" * 60)


def main() -> dict[str, Any]:
    """Entry point: run Phase 6 validation pipeline."""
    pipeline = ValidationPipeline()
    report = pipeline.run()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return report


if __name__ == "__main__":
    result = main()
