"""
scripts/validate_phase6.py
============================
Phase 6 exit-gate validation script.

Run this after completing Phase 6 validation & quality assurance.
It checks all Phase 6 deliverables:

   1. eval_report.json exists and is readable
   2. All 8 research questions are covered
   3. All insights have faithfulness score >= 0.7
   4. Zero insights rated as hallucinated in spot-check
   5. Zero unresolved contradictions
   6. Eval report contains per-insight faithfulness details
   7. Spot-check selected 5 insights for human review
   8. Overall pass flag is set correctly

Exit code 0 = all checks pass. Exit code 1 = one or more failures.

Usage:
    python scripts/validate_phase6.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import settings

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

checks_passed = 0
checks_failed = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global checks_passed, checks_failed
    status = PASS if condition else FAIL
    if condition:
        checks_passed += 1
    else:
        checks_failed += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  {status}  {label}{suffix}")
    return condition


def rule(title: str) -> None:
    width = 72
    pad = "-" * ((width - len(title) - 2) // 2)
    print(f"\n{pad} {title} {pad}")


def main() -> int:
    global checks_passed, checks_failed

    print("=" * 72)
    print("Phase 6 Exit-Gate Validation")
    print("=" * 72)

    # ── Check 1: Eval report exists ────────────────────────────
    rule("Check 1: Evaluation Report")
    eval_path = settings.outputs_dir / "eval_report.json"
    report = {}
    if eval_path.is_file():
        try:
            with open(eval_path, encoding="utf-8") as f:
                report = json.load(f)
            check("eval_report.json exists and is readable", True)
        except (json.JSONDecodeError, OSError) as exc:
            check("eval_report.json readable", False, detail=str(exc))
    else:
        check("eval_report.json exists", False, detail=str(eval_path))

    # ── Check 2: Coverage ──────────────────────────────────────
    rule("Check 2: Research Question Coverage")
    coverage = report.get("coverage", {})
    all_covered = coverage.get("all_questions_covered", False)
    coverage_count = coverage.get("coverage_count", 0)
    total_questions = coverage.get("total_questions", 8)
    check(
        "All 8 research questions covered",
        all_covered,
        detail=f"{coverage_count}/{total_questions} covered",
    )
    missing = coverage.get("missing_questions", [])
    check(
        "No missing research questions",
        len(missing) == 0,
        detail=f"missing={missing}" if missing else "0 missing",
    )

    # ── Check 3: Faithfulness scores ───────────────────────────
    rule("Check 3: Faithfulness Scores")
    faithfulness = report.get("faithfulness", {})
    total_insights = faithfulness.get("total_insights", 0)
    passed_faith = faithfulness.get("passed", 0)
    failed_faith = faithfulness.get("failed", 0)
    avg_score = faithfulness.get("average_score", 0.0)

    check(
        "At least 8 faithfulness scores recorded",
        total_insights >= 8,
        detail=f"{total_insights} insights scored",
    )
    check(
        "All insights score >= 0.7",
        failed_faith == 0 and total_insights > 0,
        detail=f"{passed_faith}/{total_insights} passed, avg={avg_score:.2f}",
    )

    per_insight = faithfulness.get("per_insight", {})
    low_scores = [qid for qid, info in per_insight.items() if info.get("faithfulness_score", 0) < 0.7]
    check(
        "No low faithfulness scores",
        len(low_scores) == 0,
        detail=f"low_scores={low_scores}" if low_scores else "all >= 0.7",
    )

    # ── Check 4: Spot-check results ────────────────────────────
    rule("Check 4: Human Spot-Check")
    spot_check = report.get("spot_check", {})
    hallucinated = spot_check.get("hallucinated_count", 0)
    partially = spot_check.get("partially_grounded_count", 0)
    total_reviews = spot_check.get("total_reviews", 0)

    check(
        "At least 5 insights selected for spot-check",
        total_reviews >= 5,
        detail=f"{total_reviews} selected",
    )
    check(
        "Zero insights rated hallucinated",
        hallucinated == 0,
        detail=f"{hallucinated} hallucinated" if hallucinated else "0 hallucinated",
    )
    check(
        "At most 1 insight rated partially grounded",
        partially <= 1,
        detail=f"{partially} partially grounded",
    )

    # ── Check 5: Contradictions ────────────────────────────────
    rule("Check 5: Contradiction Detection")
    contradictions = report.get("contradictions", {})
    unresolved = contradictions.get("unresolved", [])
    check(
        "Zero unresolved contradictions",
        len(unresolved) == 0,
        detail=f"{len(unresolved)} unresolved" if unresolved else "0 unresolved",
    )

    # ── Check 6: Report structure ──────────────────────────────
    rule("Check 6: Report Structure")
    check(
        "Report contains per-insight faithfulness details",
        "faithfulness" in report and "per_insight" in faithfulness,
        detail="per_insight present" if "per_insight" in faithfulness else "missing per_insight",
    )
    check(
        "Report contains contradiction details",
        "contradictions" in report,
        detail="present" if "contradictions" in report else "missing",
    )
    check(
        "Report contains spot-check details",
        "spot_check" in report,
        detail="present" if "spot_check" in report else "missing",
    )

    # ── Check 7: Overall pass flag ─────────────────────────────
    rule("Check 7: Overall Pass Flag")
    overall_passed = report.get("passed", False)
    check(
        "Overall pass flag is True",
        overall_passed,
        detail="PASS" if overall_passed else "FAIL",
    )

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"Results: {checks_passed} passed, {checks_failed} failed")
    print("=" * 72)

    if checks_failed > 0:
        print("Phase 6 validation FAILED")
        return 1
    else:
        print("Phase 6 validation PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
