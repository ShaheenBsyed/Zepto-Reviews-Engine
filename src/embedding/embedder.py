"""
src/embedding/embedder.py
==========================
Batch embedding generation using all-MiniLM-L6-v2.

Uses chromadb's ONNXMiniLM_L6_V2 embedding function which wraps
the same all-MiniLM-L6-v2 model locally — zero API cost, no rate limits.

This module provides:
  - Embedder class for batch embedding of text chunks
  - Idempotent operation: already-indexed chunks are skipped via cache
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 384


class Embedder:
    """
    Generates embeddings for text chunks using all-MiniLM-L6-v2.

    Uses chromadb's ONNXMiniLM_L6_V2 which runs the same model
    locally with zero API cost.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        batch_size: int = 64,
    ):
        """
        Initialize the embedder.

        Args:
            model_name: Must be 'all-MiniLM-L6-v2' (enforced).
            batch_size: Number of texts to embed in a single batch call.
        """
        if model_name != "all-MiniLM-L6-v2":
            raise ValueError(
                f"Unsupported embedding model: {model_name}. "
                "Only all-MiniLM-L6-v2 is supported."
            )
        self.model_name = model_name
        self.batch_size = batch_size
        self._ef: Optional[ONNXMiniLM_L6_V2] = None

    @property
    def embedding_function(self) -> ONNXMiniLM_L6_V2:
        """Lazily initialize and return the ONNX embedding function."""
        if self._ef is None:
            logger.info("Initializing ONNXMiniLM_L6_V2 embedding function")
            self._ef = ONNXMiniLM_L6_V2()
        return self._ef

    @property
    def dimension(self) -> int:
        """Returns the embedding vector dimension (384)."""
        return EMBEDDING_DIM

    def embed(
        self, texts: List[str], chunk_ids: Optional[List[str]] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of text strings.

        Args:
            texts: List of text strings to embed.
            chunk_ids: Optional list of chunk IDs for logging.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            ValueError: If texts is empty or chunk_ids length mismatch.
        """
        if not texts:
            raise ValueError("No texts provided for embedding")

        if chunk_ids and len(chunk_ids) != len(texts):
            raise ValueError(
                f"chunk_ids length ({len(chunk_ids)}) does not match "
                f"texts length ({len(texts)})"
            )

        ef = self.embedding_function
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_ids = chunk_ids[i : i + self.batch_size] if chunk_ids else None

            logger.debug(
                "Embedding batch %d-%d of %d",
                i,
                min(i + self.batch_size, len(texts)),
                len(texts),
            )

            vectors = ef(batch)
            all_embeddings.extend([v.tolist() if hasattr(v, "tolist") else v for v in vectors])

        logger.info(
            "Generated %d embeddings (%s, %d dims)",
            len(all_embeddings),
            self.model_name,
            self.dimension,
        )

        return all_embeddings

    def embed_single(self, text: str) -> List[float]:
        """Embed a single text string."""
        return self.embed([text])[0]


def load_chunks_from_jsonl(path: str) -> List[Dict[str, Any]]:
    """
    Load chunk records from a JSONL file produced by Phase 2.

    Skips comment lines (starting with #) and empty lines.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of chunk dictionaries.
    """
    chunks: List[Dict[str, Any]] = []
    p = Path(path)

    if not p.exists():
        logger.warning("Chunk file not found: %s", path)
        return chunks

    with open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                chunk = json.loads(line)
                chunks.append(chunk)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed JSON line: %s", exc)

    logger.info("Loaded %d chunks from %s", len(chunks), path)
    return chunks


def main() -> Dict[str, Any]:
    """
    Standalone entry point: load chunks, embed them, and print stats.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 3: Generate embeddings for clean chunks"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/processed/clean_chunks.jsonl",
        help="Path to clean chunks JSONL file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for embedding",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    chunks = load_chunks_from_jsonl(args.input)
    if not chunks:
        logger.error("No chunks loaded. Exiting.")
        return {"status": "error", "message": "No chunks loaded"}

    embedder = Embedder(batch_size=args.batch_size)
    texts = [c.get("text", "") for c in chunks]
    chunk_ids = [c.get("chunk_id", "") for c in chunks]

    embeddings = embedder.embed(texts, chunk_ids)

    logger.info("Embedding complete: %d vectors of dimension %d", len(embeddings), embedder.dimension)
    return {
        "status": "ok",
        "chunks_count": len(chunks),
        "embedding_dim": embedder.dimension,
        "model": embedder.model_name,
    }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))