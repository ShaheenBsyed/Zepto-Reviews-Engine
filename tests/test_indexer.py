"""
tests/test_indexer.py
========================
Tests for the VectorIndexer class in src/embedding/indexer.py.
"""

from __future__ import annotations

import json
import os

import pytest

from src.embedding.indexer import VectorIndexer


class TestIndexerInit:
    """Tests for VectorIndexer initialization."""

    def test_default_collection_name(self, tmp_path):
        indexer = VectorIndexer(persist_directory=str(tmp_path))
        assert indexer.collection_name == "zepto_reviews"

    def test_custom_collection_name(self, tmp_path):
        indexer = VectorIndexer(
            collection_name="test_collection",
            persist_directory=str(tmp_path),
        )
        assert indexer.collection_name == "test_collection"

    def test_persist_directory_created(self, tmp_path):
        indexer = VectorIndexer(persist_directory=str(tmp_path))
        assert tmp_path.exists()


class TestIndexerUpsert:
    """Tests for VectorIndexer.upsert()."""

    def test_upsert_adds_records(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_upsert",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        result = indexer.upsert(sample_chunks, embeddings)

        assert result["upserted"] == len(sample_chunks)
        assert result["total_in_collection"] == len(sample_chunks)

    def test_upsert_idempotent(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_idempotent",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)
        first_count = indexer.collection.count()

        indexer.upsert(sample_chunks, embeddings)
        second_count = indexer.collection.count()

        assert first_count == second_count

    def test_upsert_mismatched_lengths_raises(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_mismatch",
            persist_directory=temp_persist_dir,
        )
        chunks = [sample_chunks[0]]
        embeddings = [[0.0] * 384, [0.0] * 384]

        with pytest.raises(ValueError, match="does not match"):
            indexer.upsert(chunks, embeddings)


class TestIndexerSearch:
    """Tests for VectorIndexer.search()."""

    def test_search_returns_results(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_search",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)

        results = indexer.search("grocery shopping delivery", n_results=3)
        assert len(results) > 0
        assert len(results) <= 3

    def test_search_with_metadata_filter(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_filter",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)

        results = indexer.search(
            "grocery shopping",
            n_results=10,
            where={"app": "zepto"},
        )
        assert len(results) > 0
        for hit in results:
            assert hit["metadata"]["app"] == "zepto"

    def test_search_empty_query(self, temp_persist_dir):
        indexer = VectorIndexer(
            collection_name="test_empty",
            persist_directory=temp_persist_dir,
        )
        results = indexer.search("", n_results=5)
        assert isinstance(results, list)


class TestIndexerStats:
    """Tests for VectorIndexer.get_stats()."""

    def test_stats_contains_required_fields(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_stats",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)

        stats = indexer.get_stats()
        assert "collection_name" in stats
        assert "total_vectors" in stats
        assert "embedding_dimension" in stats
        assert stats["total_vectors"] > 0
        assert stats["embedding_dimension"] == 384

    def test_stats_metadata_schema(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_meta_schema",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)

        stats = indexer.get_stats()
        meta_schema = stats.get("metadata_schema", {})
        assert "source" in meta_schema
        assert "app" in meta_schema


class TestIndexerDeleteCollection:
    """Tests for VectorIndexer.delete_collection()."""

    def test_delete_and_recreate(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_delete",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)
        assert indexer.collection.count() > 0

        indexer.delete_collection()
        assert indexer.collection.count() == 0


class TestIndexerPersist:
    """Test that the index persists across instances."""

    def test_persistence_across_instances(self, temp_persist_dir, sample_chunks):
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer1 = VectorIndexer(
            collection_name="test_persist",
            persist_directory=temp_persist_dir,
        )
        indexer1.upsert(sample_chunks, embeddings)

        indexer2 = VectorIndexer(
            collection_name="test_persist",
            persist_directory=temp_persist_dir,
        )
        assert indexer2.collection.count() == len(sample_chunks)