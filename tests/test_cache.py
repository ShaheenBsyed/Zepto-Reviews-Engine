"""
tests/test_cache.py
=======================
Tests for the EmbeddingCache class in src/embedding/cache.py.
"""

from __future__ import annotations

import os

import pytest

from src.embedding.cache import EmbeddingCache


class TestCacheInit:
    """Tests for EmbeddingCache initialization."""

    def test_default_cache_path(self):
        cache = EmbeddingCache()
        assert cache.cache_path is not None

    def test_custom_cache_path(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        assert str(cache.cache_path) == temp_cache_path


class TestCacheAddAndCheck:
    """Tests for adding and checking indexed chunks."""

    def test_add_single_chunk(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add("chunk-001")
        assert cache.is_indexed("chunk-001")

    def test_add_batch(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add_batch(["chunk-001", "chunk-002", "chunk-003"])
        assert cache.is_indexed("chunk-001")
        assert cache.is_indexed("chunk-002")
        assert cache.is_indexed("chunk-003")

    def test_is_indexed_false_for_new_chunk(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add("chunk-001")
        assert not cache.is_indexed("chunk-002")

    def test_is_indexed_batch(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add_batch(["chunk-001", "chunk-002"])
        result = cache.is_indexed_batch(
            ["chunk-001", "chunk-002", "chunk-003"]
        )
        assert result["chunk-001"] is True
        assert result["chunk-002"] is True
        assert result["chunk-003"] is False


class TestCacheRemove:
    """Tests for removing chunks from the cache."""

    def test_remove_chunk(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add("chunk-001")
        assert cache.is_indexed("chunk-001")

        cache.remove("chunk-001")
        assert not cache.is_indexed("chunk-001")

    def test_remove_nonexistent_chunk_does_not_raise(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.remove("nonexistent")
        assert not cache.is_indexed("nonexistent")


class TestCacheClear:
    """Tests for clearing the cache."""

    def test_clear(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add_batch(["chunk-001", "chunk-002"])
        assert cache.get_indexed_count() == 2

        cache.clear()
        assert cache.get_indexed_count() == 0


class TestCachePersistence:
    """Tests for saving and loading the cache from disk."""

    def test_save_and_load(self, temp_cache_path):
        cache1 = EmbeddingCache(cache_path=temp_cache_path)
        cache1.add_batch(["chunk-001", "chunk-002", "chunk-003"])
        cache1.save()

        cache2 = EmbeddingCache(cache_path=temp_cache_path)
        assert cache2.is_indexed("chunk-001")
        assert cache2.is_indexed("chunk-002")
        assert cache2.is_indexed("chunk-003")
        assert cache2.get_indexed_count() == 3

    def test_save_creates_directory_if_needed(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add("chunk-001")
        cache.save()
        assert os.path.exists(temp_cache_path)


class TestCacheGetUnindexed:
    """Tests for getting unindexed chunk IDs."""

    def test_get_unindexed(self, temp_cache_path):
        cache = EmbeddingCache(cache_path=temp_cache_path)
        cache.add_batch(["chunk-001", "chunk-002"])

        unindexed = cache.get_unindexed(
            ["chunk-001", "chunk-002", "chunk-003", "chunk-004"]
        )
        assert "chunk-001" not in unindexed
        assert "chunk-002" not in unindexed
        assert "chunk-003" in unindexed
        assert "chunk-004" in unindexed
        assert len(unindexed) == 2