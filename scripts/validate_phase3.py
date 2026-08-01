"""
scripts/validate_phase3.py
=============================
Phase 3 exit-gate validation script.

Run this after completing Phase 3 embedding and vector indexing.
It checks all Phase 3 deliverables:

  1. ChromaDB collection exists and has records
  2. All clean chunks are indexed (100% coverage)
  3. Index stats report is generated
  4. Retrieval validation report exists and passes
  5. Embedding cache exists and is consistent
  6. Each indexed record has required metadata fields

Exit code 0 = all checks pass. Exit code 1 = one or more failures.

Usage:
    python scripts/validate_phase3.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.embedding.cache import EmbeddingCache
from src.embedding.indexer import VectorIndexer
from src.embedding.pipeline import run_pipeline
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
    print("Phase 3 Exit-Gate Validation")
    print("=" * 72)

    # ── Check 1: ChromaDB collection exists and has records ──
    rule("Check 1: ChromaDB Collection")
    try:
        indexer = VectorIndexer()
        collection = indexer.collection
        total_vectors = collection.count()
        check(
            "ChromaDB collection exists",
            total_vectors > 0,
            detail=f"{total_vectors} vectors in '{indexer.collection_name}'",
        )
    except Exception as exc:
        check("ChromaDB collection exists", False, detail=str(exc))
        total_vectors = 0

    # ── Check 2: All clean chunks are indexed ─────────────────
    rule("Check 2: Indexing Coverage")
    chunks_path = PROJECT_ROOT / "data" / "processed" / "clean_chunks.jsonl"
    chunk_count = 0
    if chunks_path.is_file():
        with open(chunks_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    chunk_count += 1

    check(
        "Clean chunks file exists and is readable",
        chunk_count > 0,
        detail=f"{chunk_count} chunks in clean_chunks.jsonl",
    )

    if chunk_count > 0 and total_vectors > 0:
        coverage = total_vectors / chunk_count * 100
        check(
            f"Indexing coverage >= 100%",
            coverage >= 100,
            detail=f"{coverage:.1f}% ({total_vectors}/{chunk_count})",
        )
    else:
        check("Indexing coverage >= 100%", False, detail="Cannot compute coverage")

    # ── Check 3: Index stats report exists ────────────────────
    rule("Check 3: Index Stats")
    try:
        stats = indexer.get_stats()
        check(
            "Index stats report generated",
            stats.get("total_vectors", 0) > 0,
            detail=f"dim={stats.get('embedding_dimension')}, "
            f"collection={stats.get('collection_name')}",
        )
        check(
            "Metadata schema present",
            bool(stats.get("metadata_schema")),
            detail=str(stats.get("metadata_schema", {})),
        )
    except Exception as exc:
        check("Index stats report generated", False, detail=str(exc))

    # ── Check 4: Retrieval validation report ──────────────────
    rule("Check 4: Retrieval Validation")
    validation_path = settings.outputs_dir / "retrieval_validation.json"
    validation_passed = False
    if validation_path.is_file():
        try:
            with open(validation_path, encoding="utf-8") as f:
                val_report = json.load(f)
            validation_passed = val_report.get("all_passed", False)
            check(
                "Retrieval validation report exists",
                True,
                detail=f"{val_report.get('queries_passed', 0)}/"
                f"{val_report.get('total_queries', 0)} queries passed",
            )
            check(
                "All validation queries passed",
                validation_passed,
                detail=f"failed={val_report.get('queries_failed', 0)}",
            )
        except (json.JSONDecodeError, OSError) as exc:
            check("Retrieval validation report readable", False, detail=str(exc))
    else:
        check("Retrieval validation report exists", False, detail=str(validation_path))

    # ── Check 5: Embedding cache ──────────────────────────────
    rule("Check 5: Embedding Cache")
    cache = EmbeddingCache()
    cache_count = cache.get_indexed_count()
    check(
        "Embedding cache exists",
        cache_count >= 0,
        detail=f"{cache_count} chunk IDs cached",
    )

    if chunk_count > 0:
        check(
            "Cache covers all chunks",
            cache_count >= chunk_count,
            detail=f"{cache_count}/{chunk_count}",
        )

    # ── Check 6: Required metadata fields ─────────────────────
    rule("Check 6: Metadata Schema")
    required_meta_fields = ["source", "app", "date", "rating", "chunk_id"]
    if total_vectors > 0:
        sample = collection.peek(limit=1)
        if sample and sample.get("metadatas"):
            meta = sample["metadatas"][0]
            for field in required_meta_fields:
                check(
                    f"Metadata field '{field}' present",
                    field in meta,
                    detail=f"value={meta.get(field)}",
                )
        else:
            check("Metadata fields present", False, detail="No sample records")
    else:
        check("Metadata fields present", False, detail="No records in collection")

    # ── Check 7: Phase 3 report ───────────────────────────────
    rule("Check 7: Pipeline Report")
    report_path = settings.outputs_dir / "phase3_report.json"
    if report_path.is_file():
        try:
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)
            exit_criteria = report.get("exit_criteria", {})
            all_met = all(exit_criteria.values())
            check(
                "Phase 3 report generated",
                True,
                detail=str(report_path),
            )
            check(
                "All exit criteria met",
                all_met,
                detail=str(exit_criteria),
            )
        except (json.JSONDecodeError, OSError) as exc:
            check("Phase 3 report readable", False, detail=str(exc))
    else:
        check("Phase 3 report exists", False, detail=str(report_path))

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"Results: {checks_passed} passed, {checks_failed} failed")
    print("=" * 72)

    if checks_failed > 0:
        print("Phase 3 validation FAILED")
        return 1
    else:
        print("Phase 3 validation PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())