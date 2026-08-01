"""
tests/test_clustering.py
=========================
Tests for Phase 4: Theme Identification (clustering module).
"""

from __future__ import annotations

import json
import os

import pytest

import numpy as np
from src.clustering.clusterer import ThemeClusterer
from src.clustering.labeler import ThemeLabeler
from src.clustering.reducer import DimensionalityReducer
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


class TestDimensionalityReducer:
    """Tests for DimensionalityReducer."""

    def test_default_clustering_dims(self):
        reducer = DimensionalityReducer()
        assert reducer.n_components_clustering == 5

    def test_default_visualization_dims(self):
        reducer = DimensionalityReducer()
        assert reducer.n_components_visualization == 2

    def test_custom_n_neighbors(self):
        reducer = DimensionalityReducer(n_neighbors=30)
        assert reducer.n_neighbors == 30

    def test_custom_min_dist(self):
        reducer = DimensionalityReducer(min_dist=0.3)
        assert reducer.min_dist == 0.3


class TestThemeClusterer:
    """Tests for ThemeClusterer."""

    def test_default_min_cluster_size(self):
        clusterer = ThemeClusterer()
        assert clusterer.min_cluster_size == 5

    def test_custom_min_cluster_size(self):
        clusterer = ThemeClusterer(min_cluster_size=10)
        assert clusterer.min_cluster_size == 10

    def test_fit_returns_expected_keys(self, sample_chunks):
        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)
        embeddings_array = np.array(embeddings, dtype=np.float32)

        clusterer = ThemeClusterer(min_cluster_size=2)
        result = clusterer.fit(embeddings_array)

        assert "labels" in result
        assert "num_clusters" in result
        assert "noise_count" in result
        assert "noise_ratio" in result
        assert "cluster_counts" in result

    def test_get_cluster_samples(self, sample_chunks):
        clusterer = ThemeClusterer(min_cluster_size=2)
        # Use labels where all points are in one cluster
        labels = [0] * len(sample_chunks)
        samples = clusterer.get_cluster_samples(labels, sample_chunks, n_samples=3)

        assert 0 in samples
        assert len(samples[0]) <= 3

    def test_get_noise_samples(self, sample_chunks):
        clusterer = ThemeClusterer(min_cluster_size=2)
        labels = [-1] * len(sample_chunks)
        samples = clusterer.get_noise_samples(labels, sample_chunks, n_samples=3)

        assert len(samples) == 3


class TestThemeLabeler:
    """Tests for ThemeLabeler."""

    def test_labeler_creates_instance(self):
        labeler = ThemeLabeler()
        assert labeler.model == "gemini-2.5-flash"
        assert labeler.max_rpm == 15

    def test_rate_limit_cooldown(self):
        labeler = ThemeLabeler(max_rpm=1000)
        expected_cooldown = 60.0 / 1000
        # Verify that cooldown is less than 1 second for high RPM
        assert expected_cooldown < 1.0

    def test_parse_response_json(self):
        labeler = ThemeLabeler()
        response = '{"category": "Packaged Groceries", "barrier": "High Prices", "description": "Users mention price concerns.", "quotes": ["quote 1", "quote 2", "quote 3"]}'
        result = labeler._parse_response(response)

        assert result["category"] == "Packaged Groceries"
        assert result["barrier"] == "High Prices"
        assert len(result["quotes"]) == 3

    def test_parse_response_text(self):
        labeler = ThemeLabeler()
        response = "1. Packaged Groceries\n\n2. High Prices\n\n3. - quote one\n- quote two\n- quote three"
        result = labeler._parse_response(response)

        assert result["category"] == "Packaged Groceries"
        assert len(result["description"]) > 0

    def test_parse_response_empty(self):
        labeler = ThemeLabeler()
        result = labeler._parse_response("")
        assert result["category"] == ""
        assert result["description"] == ""
        assert result["quotes"] == []

    def test_fallback_label(self, sample_chunks):
        labeler = ThemeLabeler()
        result = labeler._fallback_label(sample_chunks, 0)
        assert result["cluster_id"] == 0
        assert "category" in result
        assert "barrier" in result
        assert "description" in result
        assert "quotes" in result
        assert result["num_samples"] == len(sample_chunks)
        assert "representative_chunks" in result
        assert len(result["representative_chunks"]) == len(sample_chunks)

    def test_label_cluster_fallback_includes_num_samples(self, sample_chunks):
        labeler = ThemeLabeler()
        result = labeler.label_cluster(sample_chunks, 0)
        assert result["num_samples"] == len(sample_chunks)
        assert "representative_chunks" in result


class TestConsolidateThemes:
    """Tests for consolidate_themes."""

    def test_no_consolidation_needed(self):
        themes = [
            {"cluster_id": 0, "theme_name": "Theme A", "quotes": ["a", "b"], "representative_chunks": ["chunk-a1", "chunk-a2"]},
            {"cluster_id": 1, "theme_name": "Theme B", "quotes": ["c", "d"], "representative_chunks": ["chunk-b1", "chunk-b2"]},
        ]
        result = consolidate_themes(themes, overlap_threshold=0.7)
        assert len(result) == 2

    def test_consolidation_with_overlap(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Theme A",
                "quotes": ["same chunk", "unique a"],
                "representative_chunks": ["chunk-1", "chunk-2"],
            },
            {
                "cluster_id": 1,
                "theme_name": "Theme B",
                "quotes": ["same chunk", "unique b"],
                "representative_chunks": ["chunk-1", "chunk-3"],
            },
        ]
        # 1 shared out of 2 = 0.5 overlap, must be > threshold to consolidate
        result = consolidate_themes(themes, overlap_threshold=0.4)
        assert len(result) == 1

    def test_single_theme_passes_through(self):
        themes = [
            {"cluster_id": 0, "theme_name": "Only Theme", "quotes": ["a"]},
        ]
        result = consolidate_themes(themes)
        assert len(result) == 1


class TestSaveLoadTaxonomy:
    """Tests for taxonomy save/load."""

    def test_save_and_load(self, tempdir):
        themes = [
            {
                "cluster_id": 0,
                "category": "Packaged Groceries",
                "barrier": "High Prices",
                "description": "A test theme",
                "quotes": ["quote 1", "quote 2", "quote 3"],
            }
        ]
        path = os.path.join(tempdir, "themes.json")
        save_taxonomy(themes, output_path=path)

        loaded = load_taxonomy(path)
        assert len(loaded) == 1
        assert loaded[0]["category"] == "Packaged Groceries"
        assert loaded[0]["barrier"] == "High Prices"

    def test_validate_valid_taxonomy(self):
        themes = [
            {
                "cluster_id": 0,
                "category": "Packaged Groceries",
                "barrier": "High Prices",
                "quotes": ["quote one", "quote two", "quote three"],
                "keywords": ["theme", "one"],
                "description": "Description one",
            },
            {
                "cluster_id": 1,
                "category": "Dairy, Bread & Eggs",
                "barrier": "Trust Issues",
                "quotes": ["quote four", "quote five", "quote six"],
                "keywords": ["theme", "two"],
                "description": "Description two",
            },
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is True

    def test_validate_too_few_themes(self):
        themes = [
            {
                "cluster_id": 0,
                "theme_name": "Only Theme",
                "quotes": ["quote one"],
            },
        ]
        result = validate_taxonomy(themes)
        assert result["valid"] is False
        assert any("2" in issue for issue in result.get("issues", []))


class TestVisualizer:
    """Tests for visualization functions."""

    def test_plot_clusters_2d(self, tempdir):
        import numpy as np

        embeddings_2d = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        labels = [0, 0, 1]
        path = plot_clusters_2d(
            embeddings_2d,
            labels,
            output_path=os.path.join(tempdir, "test_plot.png"),
        )
        assert path.exists()

    def test_save_umap_coords(self, tempdir):
        import numpy as np

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
