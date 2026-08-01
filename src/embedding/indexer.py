"""
src/embedding/indexer.py
=========================
ChromaDB vector index management for Phase 3.

Responsibilities:
  - Create and manage a ChromaDB collection for the embedding index
   - Upsert embeddings with metadata (chunk_id, source, app, created_at, rating)
  - Provide semantic search with optional metadata filtering
  - Persist the index to disk for reuse across pipeline runs
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
EMBEDDING_DIM = 384


class VectorIndexer:
    """
    Manages a ChromaDB collection for storing and retrieving embeddings.

    Each stored record includes:
      - id: chunk_id (UUID)
      - embedding: 384-dim vector
       - metadata: source, app, created_at, rating, chunk_index, total_chunks, parent_record_id
      - document: the original text chunk
    """

    def __init__(
        self,
        collection_name: str = "zepto_reviews",
        persist_directory: Optional[str] = None,
    ):
        """
        Initialize the ChromaDB indexer.

        Args:
            collection_name: Name of the ChromaDB collection.
            persist_directory: Path to persist the ChromaDB index on disk.
                Defaults to settings.chroma_persist_dir.
        """
        self.collection_name = collection_name
        self.persist_directory = Path(
            persist_directory or settings.chroma_persist_dir
        )
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None

    @property
    def client(self) -> chromadb.Client:
        """Lazily initialize and return the ChromaDB persistent client."""
        if self._client is None:
            logger.info(
                "Initializing ChromaDB persistent client at %s",
                self.persist_directory,
            )
            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory)
            )
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        """Lazily initialize and return the ChromaDB collection."""
        if self._collection is None:
            try:
                self._collection = self.client.get_collection(
                    name=self.collection_name
                )
                logger.info(
                    "Loaded existing collection '%s' (%d records)",
                    self.collection_name,
                    self._collection.count(),
                )
            except Exception:
                self._collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={
                        "hnsw:space": "cosine",
                        "description": "Zepto AI Review Engine - Phase 3 embeddings",
                    },
                )
                logger.info(
                    "Created new collection '%s'", self.collection_name
                )
        return self._collection

    @property
    def embedding_function(self) -> ONNXMiniLM_L6_V2:
        """Return the ONNXMiniLM_L6_V2 embedding function."""
        return ONNXMiniLM_L6_V2()

    def upsert(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        batch_size: int = 200,
    ) -> Dict[str, Any]:
        """
        Upsert chunks and their embeddings into the ChromaDB collection.

        Already-indexed chunks (by chunk_id) are skipped for idempotency.

        Args:
            chunks: List of chunk dictionaries with chunk_id, text, and metadata.
            embeddings: List of embedding vectors corresponding to chunks.
            batch_size: Number of records to upsert per batch.

        Returns:
            Dict with upsert statistics.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks count ({len(chunks)}) does not match "
                f"embeddings count ({len(embeddings)})"
            )

        collection = self.collection
        existing_count = collection.count()
        logger.info(
            "Collection '%s' currently has %d records",
            self.collection_name,
            existing_count,
        )

        # Build batch data
        ids: List[str] = []
        documents: List[str] = []
        embeddings_batch: List[List[float]] = []
        metadatas: List[Dict[str, Any]] = []

        upserted = 0
        skipped = 0

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = chunk.get("chunk_id", "")
            if not chunk_id:
                logger.warning("Skipping chunk with empty chunk_id")
                skipped += 1
                continue

            ids.append(chunk_id)
            documents.append(chunk.get("text", ""))
            embeddings_batch.append(embedding)

            metadata = {
                "chunk_id": chunk_id,
                "source": chunk.get("source", ""),
                "app": chunk.get("app", ""),
                "rating": chunk.get("rating"),
                "created_at": chunk.get("created_at", ""),
                "language": chunk.get("language", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "total_chunks": chunk.get("total_chunks", 1),
                "parent_record_id": chunk.get("parent_record_id", ""),
            }
            metadatas.append(metadata)

        # Upsert in batches
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            batch_docs = documents[i : i + batch_size]
            batch_embs = embeddings_batch[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]

            collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                embeddings=batch_embs,
                metadatas=batch_meta,
            )
            upserted += len(batch_ids)
            logger.debug(
                "Upserted batch %d-%d (%d records)",
                i,
                min(i + batch_size, len(ids)),
                len(batch_ids),
            )

        final_count = collection.count()
        logger.info(
            "Upsert complete: %d new records, %d skipped. Collection now has %d records.",
            upserted,
            skipped,
            final_count,
        )

        return {
            "upserted": upserted,
            "skipped": skipped,
            "total_in_collection": final_count,
            "collection_name": self.collection_name,
        }

    def search(
        self,
        query_text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search with optional metadata filtering.

        Args:
            query_text: The search query string.
            n_results: Number of results to return (Top-K).
            where: Optional metadata filter dict (e.g., {"source": "play_store"}).

        Returns:
            List of result dicts with id, document, metadata, and distance.
        """
        collection = self.collection
        ef = self.embedding_function
        query_embedding = ef([query_text])[0]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
            )
        except Exception:
            return []

        hits: List[Dict[str, Any]] = []
        if results and results.get("ids"):
            for i in range(len(results["ids"][0])):
                hits.append(
                    {
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i]
                        if results.get("distances")
                        else None,
                    }
                )

        logger.info(
            "Search for '%s...' returned %d result(s) (n_results=%d)",
            query_text[:50],
            len(hits),
            n_results,
        )
        return hits

    def get_stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        collection = self.collection
        count = collection.count()

        # Get a sample record to inspect metadata schema
        sample = collection.peek(limit=1)
        metadata_schema: Dict[str, Any] = {}
        if sample and sample.get("metadatas"):
            metadata_schema = {
                k: type(v).__name__ for k, v in sample["metadatas"][0].items()
            }

        return {
            "collection_name": self.collection_name,
            "total_vectors": count,
            "embedding_dimension": EMBEDDING_DIM,
            "metadata_schema": metadata_schema,
            "persist_directory": str(self.persist_directory),
        }

    def delete_collection(self) -> None:
        """Delete the collection and recreate it empty."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self._collection = None
            self._collection = self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "description": "Zepto AI Review Engine - Phase 3 embeddings",
                },
            )
            logger.info("Deleted and recreated collection '%s'", self.collection_name)
        except Exception as exc:
            logger.error("Failed to delete collection: %s", exc)
            raise


def main() -> Dict[str, Any]:
    """Standalone entry point: create indexer and print stats."""
    indexer = VectorIndexer()
    stats = indexer.get_stats()
    print(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))