"""
src.embedding — embedding generation and vector DB indexing (Phase 3).

Modules:
  - embedder.py        : Batch embedding via all-MiniLM-L6-v2 (sentence-transformers / ONNX)
  - indexer.py         : ChromaDB upsert and collection management
  - cache.py           : Embedding cache (avoid re-embedding indexed chunks)
  - validation.py      : Retrieval quality validation with test queries
  - pipeline.py        : Phase 3 orchestration pipeline
"""