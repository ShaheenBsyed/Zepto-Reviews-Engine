#!/usr/bin/env python
"""scripts/run_phase4.py
=======================
Phase 4: Theme Identification entry point.

Runs the complete Phase 4 workflow:
1. Loads embeddings from ChromaDB
2. Reduces dimensionality with UMAP
3. Clusters with HDBSCAN
4. Extracts representative samples per cluster
5. Labels themes with LLM (or fallback)
6. Consolidates overlapping themes
7. Generates taxonomy JSON, cluster assignments, and statistics
8. Produces Theme Identification Report

Usage:
    python scripts/run_phase4.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.clustering.pipeline import run_pipeline


def main() -> int:
    result = run_pipeline()

    output_path = Path("outputs/phase4_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    if result.get("status") != "ok":
        print("Phase 4 pipeline failed:", result.get("message", "unknown error"))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())