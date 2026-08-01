#!/usr/bin/env python
"""scripts/run_preprocessing.py
=================================
Phase 2: Preprocessing & Corpus Refinement entry point.

Runs the full preprocessing pipeline:
1. Loads raw records from SQLite
2. Language filter
3. Deduplication (MinHash LSH)
4. Noise removal
5. Chunking (overlapping token windows)
6. Generates detailed preprocessing report
7. Saves clean chunks to data/processed/clean_chunks.jsonl

Usage:
    python scripts/run_preprocessing.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.pipeline import PreprocessingPipeline, load_records_from_sqlite


def main() -> dict:
    raw_db = PROJECT_ROOT / "data" / "raw" / "reviews.db"
    output_path = PROJECT_ROOT / "data" / "processed" / "clean_chunks.jsonl"

    records = load_records_from_sqlite(str(raw_db))
    if not records:
        print("No records loaded. Preprocessing aborted.")
        return {}

    pipeline = PreprocessingPipeline(
        allow_hinglish=False,
        min_word_count=6,
        dedup_threshold=0.97,
        min_chunk_tokens=300,
        max_chunk_tokens=500,
        overlap_tokens=50,
    )

    chunks = pipeline.run(records)
    pipeline.save_chunks(chunks, str(output_path))

    stats = pipeline.get_stats()
    print(f"\nPreprocessing complete: {stats['final_chunk_count']} chunks from {stats['raw_count']} raw records")
    return stats


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))