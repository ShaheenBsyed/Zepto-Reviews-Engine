#!/usr/bin/env python
"""Run the Phase 4 clustering pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.clustering.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4: Theme Identification")
    parser.add_argument("--min-cluster-size", type=int, default=7, help="HDBSCAN min_cluster_size")
    parser.add_argument("--n-neighbors", type=int, default=15, help="UMAP n_neighbors")
    parser.add_argument("--min-dist", type=float, default=0.1, help="UMAP min_dist")
    parser.add_argument("--n-samples", type=int, default=10, help="Representative samples per cluster")
    parser.add_argument("--overlap-threshold", type=float, default=0.7, help="Consolidation overlap threshold")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    import logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    result = run_pipeline(
        min_cluster_size=args.min_cluster_size,
        n_neighbors=args.n_neighbors,
        min_dist=args.min_dist,
        n_samples_per_cluster=args.n_samples,
        overlap_threshold=args.overlap_threshold,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
