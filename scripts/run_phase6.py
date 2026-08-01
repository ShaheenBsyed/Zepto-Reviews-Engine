#!/usr/bin/env python
"""Run the Phase 6 Validation & Quality Assurance pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.validation.pipeline import ValidationPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6: Validation & Quality Assurance")
    parser.add_argument(
        "--insights-path",
        type=str,
        default=None,
        help="Path to insights.json (default: outputs/insights.json)",
    )
    parser.add_argument(
        "--retrieval-path",
        type=str,
        default=None,
        help="Path to retrieval_results.json (default: outputs/retrieval_results.json)",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=None,
        help="Path to save eval_report.json (default: outputs/eval_report.json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Minimum faithfulness score to pass (default: 0.7)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    pipeline = ValidationPipeline(
        insights_path=args.insights_path,
        retrieval_results_path=args.retrieval_path,
        output_path=args.output_path,
        faithfulness_threshold=args.threshold,
    )

    report = pipeline.run()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
