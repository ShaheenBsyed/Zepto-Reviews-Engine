"""
src/embedding/cache.py
=======================
Embedding cache for idempotent indexing.

Tracks which chunk IDs have already been embedded and indexed,
so the embedding step can be re-run safely without re-computing
or re-inserting already-indexed chunks.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

CACHE_FILENAME = "embedding_cache.json"


class EmbeddingCache:
    """
    Tracks which chunk IDs have been successfully embedded and indexed.

    The cache is stored as a JSON file alongside the ChromaDB persist
    directory. It enables idempotent re-runs of the embedding pipeline —
    chunks that are already indexed are skipped.
    """

    def __init__(self, cache_path: Optional[Path] = None):
        """
        Initialize the embedding cache.

        Args:
            cache_path: Path to the cache JSON file. Defaults to
                data/embeddings/embedding_cache.json.
        """
        self.cache_path = Path(cache_path or (
            settings.chroma_persist_dir.parent / CACHE_FILENAME
        ))
        self._loaded: bool = False
        self._indexed_ids: Set[str] = set()

    def _ensure_loaded(self) -> None:
        """Load the cache from disk if not already loaded."""
        if self._loaded:
            return

        self._indexed_ids = set()

        if self.cache_path.exists():
            try:
                with open(self.cache_path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._indexed_ids = set(data.get("indexed_chunk_ids", []))
                elif isinstance(data, list):
                    self._indexed_ids = set(data)
                logger.info(
                    "Loaded embedding cache with %d indexed chunk IDs",
                    len(self._indexed_ids),
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load embedding cache: %s", exc)
                self._indexed_ids = set()
        else:
            logger.info("No embedding cache found at %s, starting fresh", self.cache_path)

        self._loaded = True

    def is_indexed(self, chunk_id: str) -> bool:
        """Check if a chunk has already been indexed."""
        self._ensure_loaded()
        return chunk_id in self._indexed_ids

    def is_indexed_batch(self, chunk_ids: List[str]) -> Dict[str, bool]:
        """Check which chunks in a batch have already been indexed."""
        self._ensure_loaded()
        return {cid: cid in self._indexed_ids for cid in chunk_ids}

    def add(self, chunk_id: str) -> None:
        """Mark a chunk as indexed."""
        self._ensure_loaded()
        self._indexed_ids.add(chunk_id)

    def add_batch(self, chunk_ids: List[str]) -> None:
        """Mark multiple chunks as indexed."""
        self._ensure_loaded()
        self._indexed_ids.update(chunk_ids)

    def remove(self, chunk_id: str) -> None:
        """Remove a chunk from the indexed set."""
        self._ensure_loaded()
        self._indexed_ids.discard(chunk_id)

    def clear(self) -> None:
        """Clear all indexed chunk IDs."""
        self._indexed_ids = set()
        self._loaded = False

    def save(self) -> None:
        """Persist the cache to disk."""
        self._ensure_loaded()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "indexed_chunk_ids": sorted(self._indexed_ids),
            "total_indexed": len(self._indexed_ids),
        }
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(
            "Saved embedding cache with %d chunk IDs to %s",
            len(self._indexed_ids),
            self.cache_path,
        )

    def get_indexed_count(self) -> int:
        """Return the number of indexed chunk IDs."""
        self._ensure_loaded()
        return len(self._indexed_ids)

    def get_unindexed(
        self, chunk_ids: List[str]
    ) -> List[str]:
        """Return only the chunk IDs that have not yet been indexed."""
        self._ensure_loaded()
        return [cid for cid in chunk_ids if cid not in self._indexed_ids]


def main() -> Dict[str, Any]:
    """Standalone entry point: test the embedding cache."""
    cache = EmbeddingCache()
    print(f"Indexed count: {cache.get_indexed_count()}")
    return {"indexed_count": cache.get_indexed_count()}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))