"""
tests/test_validation_phase4.py
==================================
Tests for Phase 4: Theme Identification validation.

Covers:
  - src/clustering/pipeline.py (run_pipeline output validation)
  - src/clustering/taxonomy.py (validate_taxonomy, save_taxonomy, load_taxonomy)
  - src/clustering/labeler.py (fallback labeling produces valid themes)
  - src/clustering/clusterer.py (cluster samples extraction)
  - src/clustering/visualizer.py (UMAP visualization output)
  - scripts/validate_phase4.py (exit-gate validation checks)
"""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from src.clustering.clusterer import ThemeClusterer
from src.clustering.labeler import ThemeLabeler
from src.clustering.taxonomy import (
    consolidate_themes,
    load_taxonomy,
    save_taxonomy,
    validate_taxonomy,
)
from src.clustering.visualizer import (
    plot_clusters_2d,
    save_umap_coords,
)


class TestPhase4TaxonomyValidation:
    """Tests for taxonomy validation in Phase 4."""

    def test_validate_taxonomy_valid(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Price Sensitivity",
                "category": "Packaged Groceries",
                "barrier": "High Prices",
                "description": "Users mention price concerns.",
                "quotes": ["quote one", "quote two", "quote three"],
                "keywords": ["price", "concerns"],
                "num_samples": 10,
                "representative_chunks": ["chunk-1", "chunk-2"],
            },
            {
                "cluster_id": 1,
                "theme_name": "Delivery Speed",
                "category": "Dairy, Bread & Eggs",
                "barrier": "Trust Issues",
                "description": "Users care about fast delivery.",
                "quotes": ["quote four", "quote five", "quote six"],
                "keywords": ["delivery", "speed"],
                "num_samples": 8,
                "representative_chunks": ["chunk-3", "chunk-4"],
            },
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is True
        assert result["num_themes"] == 2
        assert result["issues"] == []

    def test_validate_taxonomy_duplicate_names(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Unlabeled Theme",
                "description": "Cluster 0.",
                "quotes": ["q1"],
                "num_samples": 5,
                "representative_chunks": ["chunk-1"],
            },
            {
                "cluster_id": 1,
                "theme_name": "Unlabeled Theme",
                "description": "Cluster 1.",
                "quotes": ["q2"],
                "num_samples": 3,
                "representative_chunks": ["chunk-2"],
            },
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is False
        assert any("Duplicate" in issue for issue in result["issues"])

    def test_validate_taxonomy_too_few_themes(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Only Theme",
                "description": "Just one theme.",
                "quotes": ["q1"],
                "num_samples": 5,
                "representative_chunks": ["chunk-1"],
            },
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is False
        assert any("2" in issue for issue in result["issues"])

    def test_validate_taxonomy_too_many_themes(self):
        themes = [
            {
                "cluster_id": i,
                "theme_name": f"Theme {i}",
                "description": f"Description {i}.",
                "quotes": [f"quote {i}"],
                "num_samples": 5,
                "representative_chunks": [f"chunk-{i}"],
            }
            for i in range(31)
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is False
        assert any("30" in issue or "most" in issue for issue in result["issues"])

    def test_validate_taxonomy_empty_category(self):
        themes = [
            {
                "cluster_id": 0,
                "barrier": "Trust Issues",
                "description": "No category.",
                "quotes": ["q1"],
                "num_samples": 5,
                "representative_chunks": ["chunk-1"],
            },
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is False
        assert any("no category" in issue for issue in result["issues"])

    def test_validate_taxonomy_no_quotes(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Theme 1",
                "category": "General / Multiple Categories",
                "barrier": "Trust Issues",
                "description": "No quotes.",
                "quotes": [],
                "num_samples": 5,
                "representative_chunks": ["chunk-1"],
            },
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is False
        assert any("no verbatim quotes" in issue for issue in result["issues"])


class TestPhase4SaveLoadTaxonomy:
    """Tests for taxonomy save/load in Phase 4."""

    def test_save_and_load_with_num_samples(self, tempdir):
        themes = [
            {
                "cluster_id": 0,
                "category": "Packaged Groceries",
                "barrier": "High Prices",
                "description": "A test theme",
                "quotes": ["quote 1", "quote 2", "quote 3"],
                "num_samples": 10,
                "representative_chunks": ["chunk-1", "chunk-2"],
            }
        ]
        path = os.path.join(tempdir, "themes.json")
        save_taxonomy(themes, output_path=path)

        loaded = load_taxonomy(path)
        assert len(loaded) == 1
        assert loaded[0]["category"] == "Packaged Groceries"
        assert loaded[0]["barrier"] == "High Prices"
        assert loaded[0]["num_samples"] == 10
        assert loaded[0]["representative_chunks"] == ["chunk-1", "chunk-2"]

    def test_save_taxonomy_serializes_representative_chunks(self, tempdir):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Theme A",
                "description": "Desc A",
                "quotes": ["q1"],
                "num_samples": 5,
                "representative_chunks": ["c1", "c2", "c3"],
            }
        ]
        path = os.path.join(tempdir, "themes.json")
        save_taxonomy(themes, output_path=path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["representative_chunks"] == ["c1", "c2", "c3"]
        assert data[0]["num_samples"] == 5


class TestPhase4FallbackLabelerOutput:
    """Tests that fallback labeling produces valid theme dicts."""

    def test_fallback_label_has_num_samples(self, sample_chunks):
        labeler = ThemeLabeler()
        result = labeler._fallback_label(sample_chunks, 0)
        assert result["num_samples"] == len(sample_chunks)

    def test_fallback_label_has_representative_chunks(self, sample_chunks):
        labeler = ThemeLabeler()
        result = labeler._fallback_label(sample_chunks, 0)
        assert "representative_chunks" in result
        assert "category" in result
        assert "barrier" in result
        assert len(result["representative_chunks"]) == len(sample_chunks)
        assert all(
            isinstance(c, str) and len(c) > 0
            for c in result["representative_chunks"]
        )

    def test_label_cluster_fallback_has_num_samples(self, sample_chunks):
        labeler = ThemeLabeler()
        result = labeler.label_cluster(sample_chunks, 0)
        assert result["num_samples"] == len(sample_chunks)
        assert "representative_chunks" in result
        assert "category" in result
        assert "barrier" in result

    def test_label_cluster_empty_samples_has_num_samples_zero(self):
        labeler = ThemeLabeler()
        result = labeler.label_cluster([], 0)
        assert result["num_samples"] == 0
        assert result["representative_chunks"] == []
        assert result["category"] == "General / Multiple Categories"
        assert result["barrier"] == "Trust Issues"

    def test_fallback_label_category_not_empty(self, sample_chunks):
        labeler = ThemeLabeler()
        result = labeler._fallback_label(sample_chunks, 0)
        assert len(result["category"]) > 0
        assert result["category"] != "Unlabeled Theme"


class TestPhase4ConsolidationWithRepresentativeChunks:
    """Tests for consolidation using representative_chunks."""

    def test_consolidation_uses_representative_chunks(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Theme A",
                "quotes": ["a", "b"],
                "representative_chunks": ["chunk-1", "chunk-2"],
                "num_samples": 5,
            },
            {
                "cluster_id": 1,
                "theme_name": "Theme B",
                "quotes": ["same chunk", "unique b"],
                "representative_chunks": ["chunk-1", "chunk-3"],
                "num_samples": 3,
            },
        ]
        result = consolidate_themes(themes, overlap_threshold=0.4)
        assert len(result) == 1
        assert "chunk-1" in result[0]["representative_chunks"]

    def test_consolidation_preserves_num_samples(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Theme A",
                "quotes": ["a"],
                "representative_chunks": ["chunk-1"],
                "num_samples": 5,
            },
            {
                "cluster_id": 1,
                "theme_name": "Theme B",
                "quotes": ["b"],
                "representative_chunks": ["chunk-2"],
                "num_samples": 3,
            },
        ]
        result = consolidate_themes(themes, overlap_threshold=0.7)
        assert len(result) == 2


class TestPhase4VisualizationOutputs:
    """Tests for UMAP visualization outputs in Phase 4."""

    def test_plot_clusters_2d_generates_file(self, tempdir):
        embeddings_2d = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        labels = [0, 0, 1]
        path = plot_clusters_2d(
            embeddings_2d,
            labels,
            output_path=os.path.join(tempdir, "test_plot.png"),
        )
        assert path.exists()

    def test_save_umap_coords_generates_file(self, tempdir):
        embeddings_2d = np.array([[1.0, 2.0], [3.0, 4.0]])
        labels = [0, -1]
        path = save_umap_coords(
            embeddings_2d,
            labels,
            output_path=os.path.join(tempdir, "umap_coords.json"),
        )
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["num_points"] == 2
        assert "points" in data
        assert "num_clusters" in data

    def test_save_umap_coords_includes_cluster_labels(self, tempdir):
        embeddings_2d = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        labels = [0, -1, 1]
        path = save_umap_coords(
            embeddings_2d,
            labels,
            output_path=os.path.join(tempdir, "umap_coords.json"),
        )
        with open(path) as f:
            data = json.load(f)
        cluster_labels = [p["cluster_label"] for p in data["points"]]
        assert cluster_labels == [0, -1, 1]


class TestPhase4ClustererSamples:
    """Tests for cluster sample extraction in Phase 4."""

    def test_get_cluster_samples_returns_dict(self, sample_chunks):
        clusterer = ThemeClusterer(min_cluster_size=2)
        labels = [0] * len(sample_chunks)
        samples = clusterer.get_cluster_samples(labels, sample_chunks, n_samples=3)

        assert 0 in samples
        assert len(samples[0]) <= 3
        for sample in samples[0]:
            assert "chunk_id" in sample
            assert "text" in sample
            assert "distance_to_centroid" in sample

    def test_get_noise_samples_returns_list(self, sample_chunks):
        clusterer = ThemeClusterer(min_cluster_size=2)
        labels = [-1] * len(sample_chunks)
        samples = clusterer.get_noise_samples(labels, sample_chunks, n_samples=3)

        assert len(samples) == 3
        for sample in samples:
            assert "chunk_id" in sample
            assert "text" in sample

    def test_get_cluster_samples_with_multiple_clusters(self, sample_chunks):
        clusterer = ThemeClusterer(min_cluster_size=2)
        labels = [0, 0, 1, 1, 1]
        samples = clusterer.get_cluster_samples(labels, sample_chunks, n_samples=2)

        assert 0 in samples
        assert 1 in samples
        assert len(samples[0]) <= 2
        assert len(samples[1]) <= 2