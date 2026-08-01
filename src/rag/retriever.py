"""
src/rag/retriever.py
======================
Phase 5: RAG retrieval module.

Responsibilities:
  - Execute semantic search queries against the ChromaDB vector index
  - Apply metadata filters (source, app, rating, date range)
  - Enforce per-parent-record diversity (max 2 chunks per parent_record_id)
  - Persist retrieval results to JSON for downstream use
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.embedding.indexer import VectorIndexer
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_CHUNKS_PER_PARENT = 2
DEFAULT_OUTPUT_FILENAME = "retrieval_results.json"


class RAGRetriever:
    """
    Retrieves relevant chunks from the vector index for each research question.

    Uses the semantic_query field from research_questions.json and applies
    optional metadata_filters. Enforces a maximum of MAX_CHUNKS_PER_PARENT
    chunks per parent_record_id to avoid insight domination by a single source.
    """

    def __init__(
        self,
        indexer: Optional[VectorIndexer] = None,
        top_k: int = 10,
        max_chunks_per_parent: int = MAX_CHUNKS_PER_PARENT,
    ) -> None:
        self.indexer = indexer or VectorIndexer()
        self.top_k = top_k
        self.max_chunks_per_parent = max_chunks_per_parent

    def retrieve_for_query(
        self,
        query_entry: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Retrieve chunks for a single research question.

        Args:
            query_entry: Dict with keys: id, label, question, semantic_query,
                metadata_filters.

        Returns:
            Dict with question metadata and list of retrieved chunks.
        """
        question_id = query_entry["id"]
        label = query_entry["label"]
        semantic_query = query_entry.get("semantic_query", "")
        metadata_filters = query_entry.get("metadata_filters", {})

        if not semantic_query:
            logger.warning("No semantic_query for %s: %s", question_id, label)
            return {
                "question_id": question_id,
                "label": label,
                "semantic_query": semantic_query,
                "metadata_filters": metadata_filters,
                "chunks": [],
                "total_retrieved": 0,
            }

        where = self._build_where_clause(metadata_filters)

        logger.info(
            "Retrieving for %s: %s (filters=%s)",
            question_id,
            semantic_query[:60],
            where,
        )

        try:
            hits = self.indexer.search(
                query_text=semantic_query,
                n_results=self.top_k,
                where=where if where else None,
            )
        except Exception as exc:
            logger.warning("Retrieval failed for %s: %s", question_id, exc)
            hits = []

        diversified = self._enforce_parent_diversity(hits)

        logger.info(
            "Retrieved %d chunks for %s (%d after diversity filter)",
            len(hits),
            question_id,
            len(diversified),
        )

        return {
            "question_id": question_id,
            "label": label,
            "semantic_query": semantic_query,
            "metadata_filters": metadata_filters,
            "chunks": diversified,
            "total_retrieved": len(diversified),
        }

    def retrieve_all(
        self,
        queries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Retrieve chunks for all research questions.

        Args:
            queries: List of query entry dicts (from query_builder.build_queries).

        Returns:
            Dict with timestamp and list of per-question retrieval results.
        """
        results = []
        for q in queries:
            result = self.retrieve_for_query(q)
            results.append(result)

        return {
            "pipeline_run_timestamp": __import__("datetime").datetime.now().isoformat(),
            "phase": "Phase 5: Retrieval",
            "top_k": self.top_k,
            "max_chunks_per_parent": self.max_chunks_per_parent,
            "queries": results,
        }

    def save_results(
        self,
        results: dict[str, Any],
        output_path: Optional[str] = None,
    ) -> Path:
        """
        Save retrieval results to JSON.

        Args:
            results: Retrieval results dict from retrieve_all().
            output_path: Optional custom output path.

        Returns:
            Path to the saved file.
        """
        output_path = Path(
            output_path or settings.outputs_dir / DEFAULT_OUTPUT_FILENAME
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        logger.info("Retrieval results saved to %s", output_path)
        return output_path

    def _build_where_clause(
        self, metadata_filters: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Convert metadata_filters from research_questions.json into a ChromaDB
        where clause. Only processes concrete filters (rating, source, app).
        The 'note' field is informational and ignored.

        Args:
            metadata_filters: Raw metadata_filters dict from config.

        Returns:
            ChromaDB-compatible where dict, or None if no concrete filters.
        """
        where: Dict[str, Any] = {}

        if "rating_lte" in metadata_filters:
            where["rating"] = {"$lte": metadata_filters["rating_lte"]}
        elif "rating" in metadata_filters:
            where["rating"] = metadata_filters["rating"]

        if "source" in metadata_filters:
            where["source"] = metadata_filters["source"]

        if "app" in metadata_filters:
            where["app"] = metadata_filters["app"]

        return where if where else None

    def _enforce_parent_diversity(
        self, hits: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Enforce a maximum number of chunks per parent_record_id to prevent
        a single source post from dominating the evidence base.

        Args:
            hits: Raw retrieval results from ChromaDB.

        Returns:
            Diversified list of hits, preserving original order.
        """
        if self.max_chunks_per_parent <= 0:
            return hits

        counts: Dict[str, int] = {}
        diversified = []

        for hit in hits:
            parent_id = hit.get("metadata", {}).get("parent_record_id", "")
            if not parent_id:
                parent_id = hit.get("id", "unknown")

            current_count = counts.get(parent_id, 0)
            if current_count < self.max_chunks_per_parent:
                diversified.append(hit)
                counts[parent_id] = current_count + 1
            else:
                logger.debug(
                    "Dropping chunk %s: parent %s already at limit %d",
                    hit.get("id", ""),
                    parent_id,
                    self.max_chunks_per_parent,
                )

        return diversified


def main() -> dict[str, Any]:
    """Entry point: run retrieval for all research questions."""
    from src.rag.query_builder import build_queries

    queries = build_queries()
    retriever = RAGRetriever(top_k=settings.rag_top_k)
    results = retriever.retrieve_all(queries)
    output_path = retriever.save_results(results)
    print(json.dumps(results, indent=2, default=str))
    return results


if __name__ == "__main__":
    main()
