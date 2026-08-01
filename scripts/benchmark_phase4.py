import sys
import os
import time
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.clustering.pipeline import run_pipeline

start = time.time()
result = run_pipeline(min_cluster_size=15, n_neighbors=15, min_dist=0.1, n_samples_per_cluster=5)
elapsed = time.time() - start

print(f"\n{'='*60}")
print(f"OPTIMIZED PIPELINE BENCHMARK")
print(f"{'='*60}")
print(f"Total pipeline time: {elapsed:.1f} seconds")
print(f"Status: {result['status']}")
print(f"Num clusters: {result.get('num_clusters', 0)}")
print(f"Num themes: {result.get('num_themes', 0)}")
print(f"{'='*60}")