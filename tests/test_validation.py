"""
tests/test_validation.py
===============================
Tests for the RetrievalValidator class in src/embedding/validation.py.
"""

from __future__ import annotations

import json
import os

import pytest

from src.embedding.indexer import VectorIndexer
from src.embedding.validation import RetrievalValidator


class TestRetrievalValidatorInit:
    """Tests for RetrievalValidator initialization."""

    def test_default_top_k(self, temp_persist_dir):
        indexer = VectorIndexer(
            collection_name="test_val_init",
            persist_directory=temp_persist_dir,
        )
        validator = RetrievalValidator(indexer)
        assert validator.top_k == 5

    def test_custom_top_k(self, temp_persist_dir):
        indexer = VectorIndexer(
            collection_name="test_val_custom",
            persist_directory=temp_persist_dir,
        )
        validator = RetrievalValidator(indexer, top_k=10)
        assert validator.top_k == 10


class TestRetrievalValidatorValidate:
    """Tests for RetrievalValidator.validate()."""

    def test_validate_returns_report(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_validate",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)

        validator = RetrievalValidator(indexer, top_k=3, num_queries=2)
        report = validator.validate()

        assert "total_queries" in report
        assert "queries_passed" in report
        assert "queries_failed" in report
        assert "all_passed" in report
        assert "results" in report

    def test_validate_results_have_required_fields(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_val_fields",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)

        validator = RetrievalValidator(indexer, top_k=3, num_queries=1)
        report = validator.validate()

        result = report["results"][0]
        assert "query_id" in result
        assert "query_text" in result
        assert "results_count" in result
        assert "passed" in result
        assert "top_results" in result

    def test_validate_no_results_returns_failed(self, temp_persist_dir):
        indexer = VectorIndexer(
            collection_name="test_val_empty",
            persist_directory=temp_persist_dir,
        )

        validator = RetrievalValidator(indexer, top_k=3, num_queries=1)
        report = validator.validate()

        assert report["queries_passed"] == 0
        assert report["queries_failed"] > 0
        assert report["all_passed"] is False


class TestRetrievalValidatorSaveReport:
    """Tests for RetrievalValidator.save_report()."""

    def test_save_report_creates_file(self, temp_outputs_dir, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_save",
            persist_directory=temp_persist_dir,
        )

        from src.embedding.embedder import Embedder
        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)

        indexer.upsert(sample_chunks, embeddings)

        validator = RetrievalValidator(indexer, top_k=3, num_queries=1)
        report = validator.validate()

        output_path = os.path.join(temp_outputs_dir, "test_validation.json")
        saved_path = validator.save_report(report, output_path=output_path)

        assert saved_path.exists()
        with open(saved_path) as f:
            loaded = json.load(f)
        assert loaded["total_queries"] == report["total_queries"]