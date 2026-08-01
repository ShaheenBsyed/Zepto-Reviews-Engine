from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import umap
from sklearn.decomposition import PCA

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

CLUSTERING_DIMS = 5
VISUALIZATION_DIMS = 2


class DimensionalityReducer:
    """
    Reduces embedding dimensionality using UMAP.

    Two reductions are produced:
      - 5D for clustering (preserves local structure, suitable for HDBSCAN)
      - 2D for visualization (human-readable scatter plot)
    """

    def __init__(
        self,
        n_components_clustering: int = CLUSTERING_DIMS,
        n_components_visualization: int = VISUALIZATION_DIMS,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        random_state: int = 42,
    ):
        self.n_components_clustering = n_components_clustering
        self.n_components_visualization = n_components_visualization
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
        self.random_state = random_state

        self._reducer_5d: Optional[umap.UMAP] = None
        self._reducer_2d: Optional[umap.UMAP] = None

    @property
    def reducer_5d(self) -> umap.UMAP:
        if self._reducer_5d is None:
            self._reducer_5d = umap.UMAP(
                n_components=self.n_components_clustering,
                n_neighbors=self.n_neighbors,
                min_dist=self.min_dist,
                random_state=self.random_state,
                metric="cosine",
            )
        return self._reducer_5d

    @property
    def reducer_2d(self) -> umap.UMAP:
        if self._reducer_2d is None:
            self._reducer_2d = umap.UMAP(
                n_components=self.n_components_visualization,
                n_neighbors=self.n_neighbors,
                min_dist=self.min_dist,
                random_state=self.random_state,
                metric="cosine",
            )
        return self._reducer_2d

    def fit_transform_5d(self, embeddings: np.ndarray) -> np.ndarray:
        """Reduce embeddings to 5 dimensions for clustering."""
        logger.info(
            "Reducing %d embeddings from %dD to %dD for clustering",
            embeddings.shape[0],
            embeddings.shape[1],
            self.n_components_clustering,
        )
        reduced = self.reducer_5d.fit_transform(embeddings)
        logger.info(
            "5D reduction complete: shape %s",
            reduced.shape,
        )
        return reduced

    def fit_transform_2d(self, embeddings: np.ndarray) -> np.ndarray:
        """Reduce embeddings to 2 dimensions for visualization."""
        logger.info(
            "Reducing %d embeddings from %dD to %dD for visualization",
            embeddings.shape[0],
            embeddings.shape[1],
            self.n_components_visualization,
        )
        reduced = self.reducer_2d.fit_transform(embeddings)
        logger.info(
            "2D reduction complete: shape %s",
            reduced.shape,
        )
        return reduced

    def transform_2d_from_5d(self, embeddings_5d: np.ndarray) -> np.ndarray:
        """Project 5D embeddings to 2D using PCA (avoids refitting UMAP)."""
        logger.info(
            "Projecting %d embeddings from 5D to 2D using PCA for visualization",
            embeddings_5d.shape[0],
        )
        pca = PCA(n_components=self.n_components_visualization, random_state=self.random_state)
        reduced = pca.fit_transform(embeddings_5d)
        logger.info(
            "PCA 2D projection complete: shape %s",
            reduced.shape,
        )
        return reduced

    def save(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Save reducer state and metadata."""
        path = Path(path or settings.outputs_dir / "reducer_state.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "n_components_clustering": self.n_components_clustering,
            "n_components_visualization": self.n_components_visualization,
            "n_neighbors": self.n_neighbors,
            "min_dist": self.min_dist,
            "random_state": self.random_state,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logger.info("Reducer state saved to %s", path)
        return state

    def load_embeddings(
        self,
        embeddings_path: Optional[str] = None,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Load embeddings and chunk metadata from the ChromaDB index.

        Returns:
            Tuple of (embeddings array, chunk metadata list).
        """
        from src.embedding.indexer import VectorIndexer

        indexer = VectorIndexer()
        collection = indexer.collection
        total = collection.count()
        if total == 0:
            raise ValueError(
                "Vector index is empty. Run Phase 3 (embedding) first."
            )

        logger.info("Loading %d embeddings from ChromaDB", total)

        all_embeddings: List[np.ndarray] = []
        all_metadata: List[Dict[str, Any]] = []

        # ChromaDB peek does not support offset; fetch all at once
        batch = collection.peek(limit=total)
        embeddings_list = batch.get("embeddings") if batch else None
        if embeddings_list is not None and len(embeddings_list) > 0:
            for emb in embeddings_list:
                all_embeddings.append(np.array(emb, dtype=np.float32))
            documents_list = batch.get("documents", []) or []
            metadatas_list = batch.get("metadatas", []) or []
            for meta, doc in zip(metadatas_list, documents_list):
                meta = dict(meta)
                meta["text"] = doc
                all_metadata.append(meta)

        embeddings_array = np.vstack(all_embeddings) if all_embeddings else np.array([])
        logger.info(
            "Loaded %d embeddings (%dD) and %d metadata records",
            embeddings_array.shape[0],
            embeddings_array.shape[1] if embeddings_array.ndim > 1 else 0,
            len(all_metadata),
        )
        return embeddings_array, all_metadata


def main() -> Dict[str, Any]:
    """Standalone entry point: reduce embeddings and report stats."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 4: Reduce embedding dimensionality with UMAP"
    )
    parser.add_argument(
        "--n-components",
        type=int,
        default=CLUSTERING_DIMS,
        help="Number of dimensions for clustering reduction",
    )
    parser.add_argument(
        "--n-neighbors",
        type=int,
        default=15,
        help="UMAP n_neighbors parameter",
    )
    parser.add_argument(
        "--min-dist",
        type=float,
        default=0.1,
        help="UMAP min_dist parameter",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    reducer = DimensionalityReducer(n_components_clustering=args.n_components)
    embeddings, metadata = reducer.load_embeddings()

    if embeddings.size == 0:
        logger.error("No embeddings loaded. Exiting.")
        return {"status": "error", "message": "No embeddings loaded"}

    reduced = reducer.fit_transform_5d(embeddings)

    stats = {
        "input_dimensions": int(embeddings.shape[1]),
        "output_dimensions": args.n_components,
        "num_embeddings": int(embeddings.shape[0]),
        "n_neighbors": args.n_neighbors,
        "min_dist": args.min_dist,
    }
    logger.info("Reduction stats: %s", json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))