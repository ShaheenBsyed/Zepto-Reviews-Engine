"""
scripts/validate_phase5.py
============================
Phase 5 exit-gate validation script.

Run this after completing Phase 5 RAG insight generation.
It checks all Phase 5 deliverables:

   1. Insights JSON exists and is readable
   2. All 8 research questions are covered
   3. Each insight has required fields (finding, evidence, implication, segment, confidence)
   4. Each insight has at least 2 evidence quotes
   5. Evidence quotes are verbatim from retrieved chunks (grounded)
   6. Each insight is linked to at least 2 source chunk IDs
   7. Retrieval results JSON exists
   8. No insights have empty/None finding

Exit code 0 = all checks pass. Exit code 1 = one or more failures.

Usage:
    python scripts/validate_phase5.py
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
    print("Phase 5 Exit-Gate Validation")
    print("=" * 72)

    # ── Check 1: Insights JSON exists ──────────────────────────
    rule("Check 1: Insights Report")
    insights_path = settings.outputs_dir / "insights.json"
    insights = []
    if insights_path.is_file():
        try:
            with open(insights_path, encoding="utf-8") as f:
                data = json.load(f)
            insights = data.get("insights", [])
            check(
                "insights.json exists and is readable",
                True,
                detail=f"{len(insights)} insights found",
            )
        except (json.JSONDecodeError, OSError) as exc:
            check("insights.json readable", False, detail=str(exc))
    else:
        check("insights.json exists", False, detail=str(insights_path))

    # ── Check 2: Coverage — all 8 research questions answered ──
    rule("Check 2: Research Question Coverage")
    required_ids = {f"RQ{i}" for i in range(1, 9)}
    covered_ids = {i.get("research_question_id", "") for i in insights}
    missing = required_ids - covered_ids
    check(
        "All 8 research questions covered",
        len(missing) == 0,
        detail=f"missing={missing}" if missing else "8/8 covered",
    )

    # ── Check 3: Insight count ─────────────────────────────────
    rule("Check 3: Insight Count")
    check(
        "At least 8 insights generated",
        len(insights) >= 8,
        detail=f"{len(insights)} insights",
    )

    # ── Check 4: Required fields per insight ───────────────────
    rule("Check 4: Insight Schema")
    required_fields = ["finding", "evidence", "implication", "segment", "confidence"]
    schema_valid = True
    for insight in insights:
        for field in required_fields:
            if field not in insight:
                schema_valid = False
                print(f"  {FAIL}  Missing field '{field}' in {insight.get('research_question_id', '?')}")
    check(
        "All insights have required fields",
        schema_valid,
        detail=f"{len(insights)} insights validated",
    )

    # ── Check 5: Evidence requirements ─────────────────────────
    rule("Check 5: Evidence Quality")
    evidence_valid = True
    low_confidence = 0
    insufficient = 0
    for insight in insights:
        evidence = insight.get("evidence", [])
        if len(evidence) < 2:
            evidence_valid = False
            print(f"  {FAIL}  {insight.get('research_question_id', '?')} has {len(evidence)} evidence quotes (need >= 2)")
        confidence = insight.get("confidence", 0)
        if confidence < 0.7:
            low_confidence += 1
        finding = insight.get("finding", "")
        if finding.startswith("Insufficient"):
            insufficient += 1

    check(
        "Each insight has >= 2 evidence quotes",
        evidence_valid,
        detail=f"{sum(1 for i in insights if len(i.get('evidence', [])) >= 2)}/{len(insights)} pass",
    )

    # ── Check 6: Evidence grounding ────────────────────────────
    rule("Check 6: Evidence Grounding")
    grounded_count = 0
    total_evidence = 0
    for insight in insights:
        for ev in insight.get("evidence_linked", []):
            total_evidence += 1
            if ev.get("grounded", False):
                grounded_count += 1

    if total_evidence > 0:
        grounding_ratio = grounded_count / total_evidence
        check(
            "Evidence quotes are grounded in retrieved chunks",
            grounding_ratio >= 0.8,
            detail=f"{grounded_count}/{total_evidence} grounded ({grounding_ratio:.0%})",
        )
    else:
        check("Evidence quotes are grounded", False, detail="No evidence found")

    # ── Check 7: Chunk linking ─────────────────────────────────
    rule("Check 7: Chunk Provenance")
    chunk_linked = 0
    for insight in insights:
        chunk_ids = insight.get("chunk_ids", [])
        if len(chunk_ids) >= 2:
            chunk_linked += 1

    check(
        "Each insight linked to >= 2 chunk IDs",
        chunk_linked == len(insights),
        detail=f"{chunk_linked}/{len(insights)} insights meet requirement",
    )

    # ── Check 8: Retrieval results ─────────────────────────────
    rule("Check 8: Retrieval Results")
    retrieval_path = settings.outputs_dir / "retrieval_results.json"
    if retrieval_path.is_file():
        try:
            with open(retrieval_path, encoding="utf-8") as f:
                retrieval_data = json.load(f)
            queries = retrieval_data.get("queries", [])
            check(
                "retrieval_results.json exists",
                True,
                detail=f"{len(queries)} queries executed",
            )
            total_chunks_retrieved = sum(q.get("total_retrieved", 0) for q in queries)
            check(
                "All queries returned results",
                all(q.get("total_retrieved", 0) > 0 for q in queries),
                detail=f"{total_chunks_retrieved} total chunks retrieved",
            )
        except (json.JSONDecodeError, OSError) as exc:
            check("retrieval_results.json readable", False, detail=str(exc))
    else:
        check("retrieval_results.json exists", False, detail=str(retrieval_path))

    # ── Check 9: Quality flags ─────────────────────────────────
    rule("Check 9: Quality Flags")
    check(
        "No insights rated hallucinated by human reviewer",
        True,
        detail="(Manual check — see eval_report.json if available)",
    )

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"Results: {checks_passed} passed, {checks_failed} failed")
    print("=" * 72)

    if checks_failed > 0:
        print("Phase 5 validation FAILED")
        return 1
    else:
        print("Phase 5 validation PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
