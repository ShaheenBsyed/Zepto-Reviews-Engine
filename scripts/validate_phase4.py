#!/usr/bin/env python
"""Phase 4 exit-gate validation script."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.clustering.pipeline import run_pipeline
from src.clustering.taxonomy import validate_taxonomy, load_taxonomy
from src.clustering.visualizer import save_umap_coords
from src.embedding.indexer import VectorIndexer
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
    suffix = "  (%s)" % detail if detail else ""
    print("  %s  %s%s" % (status, label, suffix))
    return condition


def rule(title: str) -> None:
    width = 72
    pad = "-" * ((width - len(title) - 2) // 2)
    print("\n%s %s %s" % (pad, title, pad))


def main() -> int:
    global checks_passed, checks_failed

    print("=" * 72)
    print("Phase 4 Exit-Gate Validation")
    print("=" * 72)

    # Check 1: Taxonomy JSON exists and is valid
    rule("Check 1: Theme Taxonomy")
    taxonomy = load_taxonomy()
    check(
        "Taxonomy JSON exists and is readable",
        len(taxonomy) > 0,
        detail="%d themes found" % len(taxonomy),
    )

    if len(taxonomy) > 0:
        validation = validate_taxonomy(taxonomy)
        check(
            "Taxonomy validation passed",
            validation.get("valid", False),
            detail=str(validation.get("issues", [])),
        )
        check(
            "Themes in range (2-30)",
            2 <= len(taxonomy) <= 30,
            detail="%d themes" % len(taxonomy),
        )

    # Check 2: UMAP visualization exists
    rule("Check 2: Visualization")
    viz_path = settings.outputs_dir / "umap_clusters.png"
    check(
        "UMAP visualization exists",
        viz_path.is_file(),
        detail=str(viz_path),
    )

    # Check 3: UMAP coordinates JSON exists
    rule("Check 3: UMAP Coordinates")
    coords_path = settings.outputs_dir / "umap_coords.json"
    check(
        "UMAP coordinates JSON exists",
        coords_path.is_file(),
        detail=str(coords_path),
    )

    # Check 4: Phase 4 report exists
    rule("Check 4: Pipeline Report")
    report_path = settings.outputs_dir / "phase4_report.json"
    if report_path.is_file():
        try:
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)
            ec = report.get("exit_criteria", {})
            all_met = all(ec.values()) if ec else False
            check(
                "Phase 4 report generated",
                True,
                detail=str(report_path),
            )
            check(
                "All exit criteria met",
                all_met,
                detail=str(ec),
            )
        except (json.JSONDecodeError, OSError) as exc:
            check("Phase 4 report readable", False, detail=str(exc))
    else:
        check("Phase 4 report exists", False, detail=str(report_path))

    # Check 5: Vector index has data
    rule("Check 5: Vector Index")
    try:
        indexer = VectorIndexer()
        collection = indexer.collection
        total = collection.count()
        check(
            "Vector index has records",
            total > 0,
            detail="%d vectors" % total,
        )
    except Exception as exc:
        check("Vector index accessible", False, detail=str(exc))

    # Summary
    print("\n" + "=" * 72)
    print("Results: %d passed, %d failed" % (checks_passed, checks_failed))
    print("=" * 72)

    if checks_failed > 0:
        print("Phase 4 validation FAILED")
        return 1
    else:
        print("Phase 4 validation PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
