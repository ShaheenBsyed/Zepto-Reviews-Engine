"""
src.clustering - theme identification via UMAP + HDBSCAN + LLM labeling (Phase 4).

Modules:
  - reducer.py       : UMAP dimensionality reduction (384D -> 5D for clustering, 2D for viz)
  - clusterer.py      : HDBSCAN clustering with tunable min_cluster_size
  - labeler.py       : LLM-based theme labeling from cluster representative samples
  - taxonomy.py      : Theme taxonomy JSON serialization and consolidation helpers
  - visualizer.py    : 2D UMAP cluster plot generation
  - pipeline.py      : Phase 4 orchestration pipeline
"""