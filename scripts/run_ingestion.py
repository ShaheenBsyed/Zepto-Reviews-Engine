#!/usr/bin/env python
"""scripts/run_ingestion.py
===========================
Phase 1: Data Ingestion entry point.

Runs the full ingestion pipeline:
1. Initialises the SQLite database
2. Loads source configuration
3. Runs each enabled connector
4. Inserts records with idempotency via text_hash
5. Saves the ingestion report to outputs/ingestion_report.json
6. Prints a summary of collections stats

Usage:
    python scripts/run_ingestion.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.ingest_pipeline import run_pipeline
from src.utils.config import settings


def main() -> dict:
    report = run_pipeline()

    outputs_dir = settings.outputs_dir
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report_path = outputs_dir / "ingestion_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nIngestion report saved to {report_path}")
    return report


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))