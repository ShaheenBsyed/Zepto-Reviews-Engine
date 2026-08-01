#!/usr/bin/env python
"""Run the Phase 5 RAG Insight Generation pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.insight_engine import RAGInsightEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5: RAG Insight Generation")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K chunks per question")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Only run retrieval, skip insight generation",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()

    import logging

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    engine = RAGInsightEngine(
        top_k=args.top_k,
        output_dir=args.output_dir or "outputs",
    )

    if args.retrieval_only:
        results = engine.run_retrieval(save=True)
        print(json.dumps(results, indent=2, default=str))
        return 0

    result = engine.run()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("insights") else 1


if __name__ == "__main__":
    sys.exit(main())
