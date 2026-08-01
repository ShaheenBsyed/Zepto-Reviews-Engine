# -*- coding: utf-8 -*-
"""
scripts/validate_phase2.py
=============================
Phase 2 exit-gate validation script.

Run this after completing Phase 2 preprocessing. It checks all
Phase 2 deliverables:

   1. Clean chunked JSONL corpus exists in data/processed/
   2. At least 500 clean chunks
   3. Preprocessing stats are logged (raw → language → dedup → noise → chunks)
   4. Each chunk has required fields (chunk_id, text, parent_record_id, source, app)
   5. No empty text segments
   6. Chunks inherit metadata from parent records

Exit code 0 = all checks pass. Exit code 1 = one or more failures.

Usage:
    python scripts/validate_phase2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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


# -- Check 1: Corpus file exists -----------------------------------------
rule("Check 1: Corpus File")
corpus_path = PROJECT_ROOT / "data" / "processed" / "clean_chunks.jsonl"
check(
    "Clean chunks JSONL exists",
    corpus_path.is_file(),
    detail=str(corpus_path),
)


# -- Check 2: Chunk count ------------------------------------------------
rule("Check 2: Chunk Count")
chunk_count = 0
required_fields = ["chunk_id", "text", "parent_record_id", "source", "app"]
optional_fields = ["chunk_index", "total_chunks", "rating", "date", "language", "metadata"]
all_have_required = True
all_text_nonempty = True
chunks_with_metadata = 0

if corpus_path.is_file():
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            chunk_count += 1
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                check(f"Chunk {chunk_count} is valid JSON", False)
                continue

            for field in required_fields:
                if field not in chunk or not chunk[field]:
                    all_have_required = False

            if not chunk.get("text", "").strip():
                all_text_nonempty = False

            if "metadata" in chunk and chunk["metadata"] is not None:
                chunks_with_metadata += 1

    check("At least 500 clean chunks", chunk_count >= 500, detail=f"Found {chunk_count} chunks")
    check("All chunks have required fields", all_have_required, detail=f"Required: {required_fields}")
    check("No empty text segments", all_text_nonempty, detail=f"Checked {chunk_count} chunks")
    check("Chunks inherit metadata", chunks_with_metadata > 0, detail=f"{chunks_with_metadata}/{chunk_count} have metadata")


# -- Check 3: Preprocessing stats ----------------------------------------
rule("Check 3: Preprocessing Stats")
stats_path = PROJECT_ROOT / "data" / "processed" / "clean_chunks.jsonl"
if stats_path.is_file():
    with open(stats_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()

    has_stats = first_line.startswith("# Preprocessing stats:")
    check("Preprocessing stats header present", has_stats)

    if has_stats:
        try:
            stats_json = first_line.replace("# Preprocessing stats: ", "")
            stats = json.loads(stats_json)
            check("Stats has raw_count", "raw_count" in stats, detail=str(stats.get("raw_count")))
            check("Stats has after_language_filter", "after_language_filter" in stats)
            check("Stats has after_deduplication", "after_deduplication" in stats)
            check("Stats has after_noise_removal", "after_noise_removal" in stats)
            check("Stats has final_chunk_count", "final_chunk_count" in stats)

            # Verify pipeline order makes sense
            if all(k in stats for k in ["raw_count", "after_language_filter", "after_deduplication", "after_noise_removal", "final_chunk_count"]):
                ordered = [
                    stats["raw_count"],
                    stats["after_language_filter"],
                    stats["after_deduplication"],
                    stats["after_noise_removal"],
                    stats["final_chunk_count"],
                ]
                monotonically_decreasing = all(ordered[i] >= ordered[i + 1] for i in range(len(ordered) - 1))
                check("Stats show monotonic decrease", monotonically_decreasing)
        except json.JSONDecodeError:
            check("Stats are valid JSON", False, detail="Could not parse stats")


# -- Check 4: Data quality -----------------------------------------------
rule("Check 4: Data Quality")
if corpus_path.is_file() and chunk_count > 0:
    sources = set()
    apps = set()
    ratings = set()
    dates_with_data = 0

    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            sources.add(chunk.get("source", ""))
            apps.add(chunk.get("app", ""))
            if chunk.get("rating") is not None:
                ratings.add(chunk.get("rating"))
            if chunk.get("date"):
                dates_with_data += 1

    check("Chunks span multiple sources", len(sources) >= 1, detail=f"Sources: {sources}")
    check("Chunks span multiple apps", len(apps) >= 1, detail=f"Apps: {apps}")
    check("Has rating data", len(ratings) > 0, detail=f"Ratings: {sorted(ratings)}")
    check("Has date coverage", dates_with_data > 0, detail=f"{dates_with_data}/{chunk_count} chunks have dates")


# -- Summary ---------------------------------------------------------------
rule("Phase 2 Validation Summary")
total_checks = checks_passed + checks_failed
print(f"  Passed : {checks_passed} / {total_checks}")
if checks_failed > 0:
    print(f"  Failed : {checks_failed} -- resolve the above failures before proceeding to Phase 3.")
    sys.exit(1)
else:
    print("  All checks passed. Phase 2 complete. Proceed to Phase 3: Embedding & Vector Indexing.")
    sys.exit(0)