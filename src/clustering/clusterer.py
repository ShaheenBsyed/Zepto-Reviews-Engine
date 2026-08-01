from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import hdbscan
import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ThemeClusterer:
    """
    Clusters reduced embeddings using HDBSCAN.

    HDBSCAN is a density-based clustering algorithm that does not require
    specifying the number of clusters in advance. It identifies clusters of
    varying density and marks low-density points as noise (cluster -1).
    """

    def __init__(
        self,
        min_cluster_size: int = 5,
        min_samples: Optional[int] = None,
        metric: str = "euclidean",
        cluster_selection_method: str = "eom",
    ):
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.metric = metric
        self.cluster_selection_method = cluster_selection_method
        self._model: Optional[hdbscan.HDBSCAN] = None

    @property
    def model(self) -> hdbscan.HDBSCAN:
        if self._model is None:
            self._model = hdbscan.HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                min_samples=self.min_samples,
                metric=self.metric,
                cluster_selection_method=self.cluster_selection_method,
            )
        return self._model

    def fit(self, embeddings_5d: np.ndarray) -> Dict[str, Any]:
        """
        Cluster the reduced embeddings.

        Args:
            embeddings_5d: Nx5 array of UMAP-reduced embeddings.

        Returns:
            Dict with cluster labels, counts, and noise statistics.
        """
        logger.info(
            "Clustering %d embeddings with HDBSCAN (min_cluster_size=%d)",
            embeddings_5d.shape[0],
            self.min_cluster_size,
        )

        labels = self.model.fit_predict(embeddings_5d)

        unique_labels = np.unique(labels)
        cluster_counts = {int(label): int(np.sum(labels == label)) for label in unique_labels}
        noise_count = int(np.sum(labels == -1))
        num_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)

        result: Dict[str, Any] = {
            "labels": labels.tolist(),
            "unique_clusters": [int(l) for l in unique_labels],
            "cluster_counts": cluster_counts,
            "noise_count": noise_count,
            "num_clusters": num_clusters,
            "total_points": len(labels),
            "noise_ratio": noise_count / len(labels) if len(labels) > 0 else 0.0,
            "min_cluster_size": self.min_cluster_size,
        }

        logger.info(
            "Clustering complete: %d clusters, %d noise points (%.1f%%)",
            num_clusters,
            noise_count,
            result["noise_ratio"] * 100,
        )

        return result

    def get_cluster_samples(
        self,
        labels: List[int],
        chunks: List[Dict[str, Any]],
        n_samples: int = 10,
        embeddings: Optional[np.ndarray] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        For each cluster, return the n_samples chunks closest to the centroid.

        Args:
            labels: Cluster label for each chunk.
            chunks: List of chunk metadata dicts (must have chunk_id and text).
            n_samples: Number of representative samples per cluster.
            embeddings: Optional pre-computed embeddings (NxD array).
                If provided, avoids re-embedding all chunks.

        Returns:
            Dict mapping cluster_id -> list of representative chunk dicts.
        """
        cluster_ids = [l for l in set(labels) if l != -1]
        if not cluster_ids:
            logger.warning("No clusters found (all points labeled as noise)")
            return {}

        if embeddings is None:
            logger.info("No pre-computed embeddings provided, embedding %d chunks...", len(chunks))
            embedder = Embedder()
            all_texts = [c.get("text", "") for c in chunks]
            embeddings = np.array(embedder.embed(all_texts))
        else:
            logger.info("Using pre-computed embeddings (%d chunks)", embeddings.shape[0])

        cluster_samples: Dict[int, List[Dict[str, Any]]] = {}

        for cid in cluster_ids:
            indices = [i for i, l in enumerate(labels) if l == cid]
            if len(indices) == 0:
                continue

            cluster_embs = embeddings[indices]
            centroid = cluster_embs.mean(axis=0).reshape(1, -1)

            distances = np.linalg.norm(cluster_embs - centroid, axis=1)
            sorted_indices = np.argsort(distances)[:n_samples]

            representative = []
            for idx in sorted_indices:
                chunk_idx = indices[idx]
                representative.append(
                    {
                        "chunk_id": chunks[chunk_idx].get("chunk_id", ""),
                        "text": chunks[chunk_idx].get("text", ""),
                        "source": chunks[chunk_idx].get("source", ""),
                        "app": chunks[chunk_idx].get("app", ""),
                        "rating": chunks[chunk_idx].get("rating"),
                        "distance_to_centroid": float(distances[idx]),
                    }
                )

            cluster_samples[cid] = representative

        logger.info(
            "Extracted %d representative samples for each of %d clusters",
            n_samples,
            len(cluster_ids),
        )

        return cluster_samples

    def get_noise_samples(
        self,
        labels: List[int],
        chunks: List[Dict[str, Any]],
        n_samples: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return up to n_samples noise points for manual review."""
        noise_indices = [i for i, l in enumerate(labels) if l == -1]
        samples = []
        for idx in noise_indices[:n_samples]:
            samples.append(
                {
                    "chunk_id": chunks[idx].get("chunk_id", ""),
                    "text": chunks[idx].get("text", ""),
                    "source": chunks[idx].get("source", ""),
                    "app": chunks[idx].get("app", ""),
                    "rating": chunks[idx].get("rating"),
                }
            )
        return samples


def main() -> Dict[str, Any]:
    """Standalone entry point: cluster embeddings and print stats."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 4: Cluster embeddings with HDBSCAN"
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=5,
        help="Minimum samples in a cluster",
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

    clusterer = ThemeClusterer(min_cluster_size=args.min_cluster_size)
    print(json.dumps(clusterer.model.get_params(), indent=2, default=str))
    return {"status": "ok", "min_cluster_size": args.min_cluster_size}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))