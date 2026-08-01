"""
src/embedding/pipeline.py
=============================
Phase 3: Embedding & Vector Indexing Pipeline.

Orchestrates the complete Phase 3 workflow:
  1. Load clean chunks from data/processed/clean_chunks.jsonl
  2. Generate embeddings using all-MiniLM-L6-v2 (ONNX)
  3. Upsert embeddings + metadata into ChromaDB
  4. Save the embedding cache for idempotent re-runs
  5. Run retrieval quality validation
  6. Produce index stats report

Exit criteria (from implementationplan.md):
  - 100% of clean chunks indexed
  - Retrieval validation passes (queries return relevant results)
  - Index stats report generated
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.embedding.cache import EmbeddingCache
from src.embedding.embedder import Embedder, load_chunks_from_jsonl
from src.embedding.indexer import VectorIndexer
from src.embedding.validation import RetrievalValidator
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_pipeline(
    chunks_path: str = "data/processed/clean_chunks.jsonl",
    batch_size: int = 64,
    embedding_batch_size: int = 64,
    top_k: int = 10,
    num_test_queries: int = 5,
    skip_if_indexed: bool = True,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the complete Phase 3 embedding and indexing pipeline.

    Args:
        chunks_path: Path to clean chunks JSONL file.
        batch_size: Number of chunks to process per batch.
        embedding_batch_size: Number of texts to embed per batch call.
        top_k: Top-K results for retrieval validation.
        num_test_queries: Number of research questions to use for validation.
        skip_if_indexed: If True, skip chunks already in the cache.

    Returns:
        Dict with pipeline summary statistics.
    """
    logger.info("=" * 60)
    logger.info("Phase 3: Embedding & Vector Indexing Pipeline")
    logger.info("=" * 60)

    # ── Step 1: Load chunks ──────────────────────────────────────────
    logger.info("\n[Step 1/5] Loading clean chunks")
    chunks = load_chunks_from_jsonl(chunks_path)

    if not chunks:
        logger.error("No chunks loaded. Aborting pipeline.")
        return {
            "status": "error",
            "message": "No chunks loaded from " + chunks_path,
        }

    logger.info("Loaded %d chunks", len(chunks))

    # ── Step 2: Initialize components ────────────────────────────────
    logger.info("\n[Step 2/5] Initializing embedder and indexer")
    embedder = Embedder(batch_size=embedding_batch_size)
    indexer = VectorIndexer()
    cache = EmbeddingCache()

    logger.info(
        "Embedding model: %s (%d dims)",
        embedder.model_name,
        embedder.dimension,
    )

    # ── Step 3: Filter already-indexed chunks ────────────────────────
    if skip_if_indexed:
        chunk_ids = [c.get("chunk_id", "") for c in chunks]
        indexed_status = cache.is_indexed_batch(chunk_ids)
        new_chunks = [
            c
            for c in chunks
            if not indexed_status.get(c.get("chunk_id", ""), False)
        ]
        already_indexed = len(chunks) - len(new_chunks)

        if already_indexed > 0:
            logger.info(
                "Skipping %d already-indexed chunks (%d new)",
                already_indexed,
                len(new_chunks),
            )
        else:
            logger.info("No previously indexed chunks found")

        if not new_chunks:
            logger.info("All chunks already indexed. Skipping embedding.")
    else:
        new_chunks = chunks
        already_indexed = 0

    # ── Step 4: Generate embeddings ──────────────────────────────────
    if new_chunks:
        logger.info("\n[Step 3/5] Generating embeddings for %d chunks", len(new_chunks))
        texts = [c.get("text", "") for c in new_chunks]
        chunk_ids = [c.get("chunk_id", "") for c in new_chunks]

        embeddings = embedder.embed(texts, chunk_ids)

        # ── Step 5: Upsert into ChromaDB ──────────────────────────────
        logger.info("\n[Step 4/5] Upserting %d embeddings into ChromaDB", len(new_chunks))
        upsert_result = indexer.upsert(new_chunks, embeddings)

        # ── Step 6: Update cache ──────────────────────────────────────
        logger.info("\n[Step 5/5] Updating embedding cache")
        for cid in chunk_ids:
            cache.add(cid)
        cache.save()
    else:
        upsert_result = {
            "upserted": 0,
            "skipped": 0,
            "total_in_collection": indexer.collection.count(),
            "collection_name": indexer.collection_name,
        }

    # ── Step 7: Run retrieval validation ─────────────────────────────
    logger.info("\n[Validation] Running retrieval quality checks")
    validator = RetrievalValidator(indexer, top_k=top_k, num_queries=num_test_queries)
    validation_report = validator.validate()
    validator.save_report(validation_report)

    # ── Step 8: Generate index stats ─────────────────────────────────
    logger.info("\n[Stats] Generating index statistics")
    index_stats = indexer.get_stats()

    # ── Step 9: Save pipeline report ─────────────────────────────────
    report = {
        "pipeline_run_timestamp": __import__("datetime").datetime.now().isoformat(),
        "phase": "Phase 3: Embedding & Vector Indexing",
        "model": embedder.model_name,
        "embedding_dimension": embedder.dimension,
        "total_chunks_loaded": len(chunks),
        "already_indexed": already_indexed,
        "newly_indexed": upsert_result.get("upserted", 0),
        "skipped_empty": upsert_result.get("skipped", 0),
        "total_in_collection": upsert_result.get("total_in_collection", 0),
        "collection_name": indexer.collection_name,
        "persist_directory": str(indexer.persist_directory),
        "index_stats": index_stats,
        "retrieval_validation": {
            "total_queries": validation_report.get("total_queries", 0),
            "queries_passed": validation_report.get("queries_passed", 0),
            "queries_failed": validation_report.get("queries_failed", 0),
            "all_passed": validation_report.get("all_passed", False),
        },
        "exit_criteria": {
            "all_chunks_indexed": (
                upsert_result.get("total_in_collection", 0)
                >= len(chunks)
            ),
            "retrieval_validation_passed": validation_report.get(
                "all_passed", False
            ),
            "index_stats_valid": index_stats.get("total_vectors", 0) > 0,
        },
    }

    # Save pipeline report
    output_path = Path(output_dir) if output_dir else settings.outputs_dir
    report_path = output_path / "phase3_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Phase 3 report saved to %s", report_path)

    logger.info("=" * 60)
    logger.info("Phase 3 Pipeline Summary")
    logger.info("=" * 60)
    logger.info("Total chunks loaded:    %d", len(chunks))
    logger.info("Already indexed:        %d", already_indexed)
    logger.info("Newly indexed:          %d", upsert_result.get("upserted", 0))
    logger.info("Total in collection:    %d", upsert_result.get("total_in_collection", 0))
    logger.info("Embedding model:        %s (%d dims)", embedder.model_name, embedder.dimension)
    logger.info("Validation queries:     %d/%d passed", validation_report.get("queries_passed", 0), validation_report.get("total_queries", 0))
    logger.info("Exit criteria met:      %s", json.dumps(report["exit_criteria"], indent=2))
    logger.info("=" * 60)

    return report


def main() -> Dict[str, Any]:
    """Entry point for the Phase 3 pipeline."""
    return run_pipeline()


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))