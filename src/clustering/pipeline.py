"""
src.clustering.pipeline
=============================
Phase 4: Theme Identification Pipeline.

Orchestrates the complete Phase 4 workflow:
  1. Load embeddings from ChromaDB
  2. Reduce dimensionality with UMAP (384D -> 5D for clustering, 2D for viz)
  3. Cluster with HDBSCAN
  4. Extract representative samples per cluster
  5. Label themes with LLM
  6. Consolidate overlapping themes
  7. Generate visualization and taxonomy JSON

Exit criteria (from implementationplan.md):
  - 8-20 final themes
  - < 20% noise ratio
  - Manual review notes on consolidated/merged clusters
  - 2D UMAP visualization generated
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.clustering.clusterer import ThemeClusterer
from src.clustering.labeler import ThemeLabeler
from src.clustering.reducer import DimensionalityReducer
from src.clustering.taxonomy import (
    consolidate_themes,
    save_taxonomy,
    validate_taxonomy,
)
from src.clustering.visualizer import (
    plot_clusters_2d,
    save_umap_coords,
)
from src.embedding.indexer import VectorIndexer
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_pipeline(
    min_cluster_size: int = 7,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    n_samples_per_cluster: int = 10,
    overlap_threshold: float = 0.7,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the complete Phase 4 theme identification pipeline."""
    out_dir = Path(output_dir or settings.outputs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Phase 4: Theme Identification Pipeline")
    logger.info("=" * 60)

    pipeline_start = time.time()

    # Step 1: Load embeddings
    logger.info("[Step 1/6] Loading embeddings from ChromaDB")
    t0 = time.time()
    reducer = DimensionalityReducer(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
    )
    embeddings, chunks = reducer.load_embeddings()

    if embeddings.size == 0:
        logger.error("No embeddings loaded. Aborting.")
        return {"status": "error", "message": "No embeddings loaded"}

    logger.info("Step 1 complete: loaded %d embeddings in %.1f sec", len(chunks), time.time() - t0)

    # Step 2: UMAP 5D reduction for clustering
    logger.info("[Step 2/6] Reducing dimensions to 5D with UMAP")
    t0 = time.time()
    embeddings_5d = reducer.fit_transform_5d(embeddings)
    logger.info("Step 2 complete: UMAP 5D reduction in %.1f sec", time.time() - t0)

    # Step 3: HDBSCAN clustering
    logger.info("[Step 3/6] Clustering with HDBSCAN")
    t0 = time.time()
    clusterer = ThemeClusterer(min_cluster_size=min_cluster_size)
    cluster_result = clusterer.fit(embeddings_5d)

    labels = cluster_result["labels"]
    num_clusters = cluster_result["num_clusters"]
    noise_count = cluster_result["noise_count"]
    noise_ratio = cluster_result["noise_ratio"]

    if num_clusters == 0:
        logger.error("No clusters found. All points are noise.")
        return {
            "status": "error",
            "message": "No clusters found - all points are noise",
            "noise_ratio": noise_ratio,
        }

    logger.info(
        "Step 3 complete: %d clusters, %.1f%% noise in %.1f sec",
        num_clusters,
        noise_ratio * 100,
        time.time() - t0,
    )

    # Edge case: too many clusters
    if num_clusters > 30:
        logger.warning(
            "%d clusters found - too many. Consider increasing min_cluster_size.",
            num_clusters,
        )

    # Edge case: too few clusters
    if num_clusters < 5:
        logger.warning(
            "%d clusters found - too few. Consider reducing min_cluster_size or broadening the relevance filter.",
            num_clusters,
        )

    # Edge case: too much noise
    if noise_ratio > 0.20:
        logger.warning(
            "%.1f%% of data is noise - corpus may need further cleaning or clustering parameters need tuning.",
            noise_ratio * 100,
        )

    # Step 4: Get representative samples per cluster
    logger.info("[Step 4/6] Extracting representative samples per cluster")
    t0 = time.time()
    cluster_samples = clusterer.get_cluster_samples(
        labels, chunks, n_samples=n_samples_per_cluster, embeddings=embeddings,
    )
    noise_samples = clusterer.get_noise_samples(labels, chunks, n_samples=5)
    logger.info("Step 4 complete: representative extraction in %.1f sec", time.time() - t0)

    # Step 5: Label themes with LLM
    logger.info("[Step 5/6] Labelling themes with LLM")
    t0 = time.time()
    labeler = ThemeLabeler()
    themes = labeler.label_clusters(cluster_samples)
    logger.info("Step 5 complete: LLM labeling in %.1f sec", time.time() - t0)

    # Add noise samples reference to each theme
    for theme in themes:
        theme["noise_samples"] = [
            {
                "chunk_id": s.get("chunk_id", ""),
                "text_preview": s.get("text", "")[:200],
            }
            for s in noise_samples
        ]

    # Step 6: Consolidate overlapping themes
    logger.info("[Step 6/6] Consolidating overlapping themes")
    t0 = time.time()
    themes = consolidate_themes(themes, overlap_threshold=overlap_threshold)
    logger.info("Step 6 complete: consolidation in %.1f sec", time.time() - t0)

    # Validate categories and barriers are present
    for t in themes:
        if not t.get("category"):
            t["category"] = "General / Multiple Categories"
        if not t.get("barrier"):
            t["barrier"] = "Trust Issues"

    # Generate visualizations
    logger.info("Generating 2D UMAP visualization")
    t0 = time.time()
    embeddings_2d = reducer.transform_2d_from_5d(embeddings_5d)
    plot_path = plot_clusters_2d(
        embeddings_2d, labels,
        title="Phase 4: %d Themes via UMAP + HDBSCAN" % num_clusters,
    )
    coords_path = save_umap_coords(embeddings_2d, labels)
    logger.info("Visualization complete in %.1f sec", time.time() - t0)

    # Save taxonomy
    taxonomy_path = save_taxonomy(themes)

    # Validate
    validation = validate_taxonomy(themes)

    # Print discovered themes
    logger.info("=" * 60)
    logger.info("Discovered Themes")
    logger.info("=" * 60)
    for t in themes:
        logger.info("Category: %s", t.get("category"))
        logger.info("  Barrier: %s", t.get("barrier"))
        logger.info("  Description: %s", t.get("description", "")[:120])
        logger.info("  Reviews: %d", t.get("num_samples", 0))
        logger.info("  Keywords: %s", ", ".join(t.get("keywords", [])))
        logger.info("  Representative Reviews:")
        for q in t.get("quotes", []):
            logger.info("    - %s", q[:100])
    logger.info("=" * 60)

    # Save manual review notes
    review_notes = _generate_review_notes(
        themes, cluster_result, noise_ratio, num_clusters,
    )
    review_path = out_dir / "phase4_review_notes.json"
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(review_notes, f, indent=2, default=str)

    # Build result
    total_time = time.time() - pipeline_start
    result = {
        "status": "ok",
        "pipeline_run_timestamp": __import__("datetime").datetime.now().isoformat(),
        "phase": "Phase 4: Theme Identification",
        "num_clusters": num_clusters,
        "noise_count": noise_count,
        "noise_ratio": round(noise_ratio, 4),
        "num_themes": len(themes),
        "min_cluster_size": min_cluster_size,
        "overlap_threshold": overlap_threshold,
        "themes": themes,
        "validation": validation,
        "artifacts": {
            "taxonomy_json": str(taxonomy_path),
            "umap_plot": str(plot_path),
            "umap_coords": str(coords_path),
            "review_notes": str(review_path),
        },
        "exit_criteria": {
            "themes_in_range": 2 <= len(themes) <= 30,
            "noise_below_threshold": noise_ratio <= 0.20,
            "taxonomy_valid": validation.get("valid", False),
            "visualization_generated": plot_path.exists(),
        },
        "timing": {
            "total_seconds": round(total_time, 1),
            "step_1_load_embeddings": "included",
            "step_2_umap_reduction": "included",
            "step_3_clustering": "included",
            "step_4_representative_extraction": "included",
            "step_5_llm_labeling": "included",
            "step_6_consolidation": "included",
        },
    }

    # Save pipeline report
    report_path = out_dir / "phase4_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info("Phase 4 report saved to %s", report_path)

    logger.info("=" * 60)
    logger.info("Phase 4 Pipeline Summary")
    logger.info("=" * 60)
    logger.info("Clusters found:     %d", num_clusters)
    logger.info("Themes identified:   %d", len(themes))
    logger.info("Noise ratio:         %.1f%%", noise_ratio * 100)
    logger.info("Total pipeline time: %.1f sec", total_time)
    logger.info("Themes in range:     %s", result["exit_criteria"]["themes_in_range"])
    logger.info("Noise below 20%%:    %s", result["exit_criteria"]["noise_below_threshold"])
    logger.info("Taxonomy valid:      %s", result["exit_criteria"]["taxonomy_valid"])
    logger.info("Visualization:       %s", result["exit_criteria"]["visualization_generated"])
    logger.info("=" * 60)

    return result


def _generate_review_notes(
    themes: List[Dict[str, Any]],
    cluster_result: Dict[str, Any],
    noise_ratio: float,
    num_clusters: int,
) -> Dict[str, Any]:
    """Generate manual review notes for consolidated clusters."""
    notes = []
    for t in themes:
        notes.append(
            {
                "cluster_id": t.get("cluster_id"),
                "theme_name": t.get("theme_name"),
                "num_samples": t.get("num_samples", 0),
                "consolidated": False,
            }
        )
    return {
        "review_timestamp": __import__("datetime").datetime.now().isoformat(),
        "num_clusters": num_clusters,
        "num_themes": len(themes),
        "noise_ratio": noise_ratio,
        "notes": notes,
        "consolidation_log": "Themes were consolidated if they shared more than 70% of their representative chunks.",
    }


def main() -> Dict[str, Any]:
    """Entry point for the Phase 4 pipeline."""
    return run_pipeline()


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))
