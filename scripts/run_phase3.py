#!/usr/bin/env python
"""scripts/run_phase3.py
========================
Phase 3: Embedding & Vector Indexing entry point.

Runs the complete Phase 3 workflow:
1. Loads clean chunks from data/processed/clean_chunks.jsonl
2. Generates embeddings using all-MiniLM-L6-v2 (ONNX, local)
3. Upserts embeddings + metadata into ChromaDB
4. Saves embedding cache for idempotent re-runs
5. Runs retrieval quality validation with test queries
6. Generates index stats report
7. Saves phase3_report.json to outputs/

Usage:
    python scripts/run_phase3.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.embedding.pipeline import run_pipeline


def main() -> dict:
    report = run_pipeline()

    output_path = Path("outputs/phase3_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    return report


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))