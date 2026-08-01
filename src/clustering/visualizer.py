from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def plot_clusters_2d(
    embeddings_2d: np.ndarray,
    labels: List[int],
    output_path: Optional[str] = None,
    title: str = "UMAP 2D Cluster Visualization",
    figsize: tuple[int, int] = (14, 10),
) -> Path:
    """
    Generate a 2D scatter plot of UMAP-reduced embeddings colored by cluster label.

    Noise points (label -1) are plotted in grey.

    Args:
        embeddings_2d: Nx2 array of UMAP 2D coordinates.
        labels: Cluster label for each point.
        output_path: Path to save the figure. Defaults to outputs/umap_clusters.png.
        title: Plot title.
        figsize: Figure size as (width, height).

    Returns:
        Path to the saved figure.
    """
    output_path = Path(output_path or settings.outputs_dir / "umap_clusters.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    unique_labels = sorted(set(labels))
    num_clusters = len([l for l in unique_labels if l != -1])

    fig, ax = plt.subplots(figsize=figsize)

    for label in unique_labels:
        mask = np.array(labels) == label
        coords = embeddings_2d[mask]
        if label == -1:
            ax.scatter(
                coords[:, 0],
                coords[:, 1],
                c="lightgrey",
                s=10,
                alpha=0.5,
                label=f"Noise ({label})",
                edgecolors="none",
            )
        else:
            ax.scatter(
                coords[:, 0],
                coords[:, 1],
                s=15,
                alpha=0.7,
                label=f"Cluster {label}",
                edgecolors="none",
            )

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("UMAP Dimension 1", fontsize=10)
    ax.set_ylabel("UMAP Dimension 2", fontsize=10)
    ax.legend(
        loc="upper right",
        fontsize=8,
        markerscale=1.5,
        framealpha=0.9,
    )
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(
        str(output_path),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)

    logger.info(
        "2D UMAP visualization saved to %s (%d clusters, %d points)",
        output_path,
        num_clusters,
        len(embeddings_2d),
    )
    return output_path


def save_umap_coords(
    embeddings_2d: np.ndarray,
    labels: List[int],
    output_path: Optional[str] = None,
) -> Path:
    """Save UMAP 2D coordinates and labels as JSON for use in the dashboard."""
    output_path = Path(output_path or settings.outputs_dir / "umap_coords.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    coords = []
    for i, (point, label) in enumerate(zip(embeddings_2d, labels)):
        coords.append(
            {
                "point_index": i,
                "umap_1": float(point[0]),
                "umap_2": float(point[1]),
                "cluster_label": int(label),
            }
        )

    data = {
        "umap_dimensions": 2,
        "num_points": len(coords),
        "num_clusters": len(set(labels)) - (1 if -1 in labels else 0),
        "points": coords,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("UMAP coordinates saved to %s", output_path)
    return output_path


def main() -> Dict[str, Any]:
    """Standalone entry point: generate visualization placeholder."""
    return {"status": "ok", "message": "Visualization requires embeddings from Phase 3"}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))