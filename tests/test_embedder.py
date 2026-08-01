"""
tests/test_embedder.py
========================
Tests for the Embedder class in src/embedding/embedder.py.
"""

from __future__ import annotations

import pytest

from src.embedding.embedder import Embedder


class TestEmbedderInit:
    """Tests for Embedder initialization."""

    def test_default_model(self):
        embedder = Embedder()
        assert embedder.model_name == "all-MiniLM-L6-v2"

    def test_custom_batch_size(self):
        embedder = Embedder(batch_size=32)
        assert embedder.batch_size == 32

    def test_unsupported_model_raises(self):
        with pytest.raises(ValueError, match="Unsupported embedding model"):
            Embedder(model_name="text-embedding-3-small")

    def test_dimension_is_384(self):
        embedder = Embedder()
        assert embedder.dimension == 384


class TestEmbedderEmbed:
    """Tests for the Embedder.embed() method."""

    def test_embed_single_text(self):
        embedder = Embedder()
        result = embedder.embed(["Hello world"])
        assert len(result) == 1
        assert len(result[0]) == 384

    def test_embed_multiple_texts(self):
        embedder = Embedder()
        texts = ["Hello world", "Good morning", "Test embedding"]
        result = embedder.embed(texts)
        assert len(result) == 3
        for vec in result:
            assert len(vec) == 384

    def test_embed_returns_float_vectors(self):
        embedder = Embedder()
        result = embedder.embed(["Test"])
        assert all(isinstance(v, list) for v in result)
        assert all(isinstance(x, float) for v in result for x in v)

    def test_embed_empty_texts_raises(self):
        embedder = Embedder()
        with pytest.raises(ValueError, match="No texts provided"):
            embedder.embed([])

    def test_embed_chunk_ids_length_mismatch(self):
        embedder = Embedder()
        with pytest.raises(ValueError, match="does not match"):
            embedder.embed(["Hello"], chunk_ids=["id1", "id2"])

    def test_embed_single_method(self):
        embedder = Embedder()
        result = embedder.embed_single("Single text")
        assert len(result) == 384


class TestEmbedderConsistency:
    """Tests that the same text produces the same embedding."""

    def test_deterministic_embeddings(self):
        embedder = Embedder()
        text = "Consistency test text"
        result1 = embedder.embed([text])
        result2 = embedder.embed([text])
        assert result1[0] == result2[0]

    def test_different_texts_different_embeddings(self):
        embedder = Embedder()
        text1 = "This is the first text"
        text2 = "This is the second text"
        result1 = embedder.embed([text1])
        result2 = embedder.embed([text2])
        assert result1[0] != result2[0]