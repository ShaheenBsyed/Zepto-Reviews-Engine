"""
tests/test_pipeline.py
=========================
Tests for the Phase 3 pipeline in src/embedding/pipeline.py.
"""

from __future__ import annotations

import json
import os

import pytest

from src.embedding.pipeline import run_pipeline
from src.embedding.indexer import VectorIndexer


class TestRunPipeline:
    """Tests for the run_pipeline() function."""

    def test_pipeline_returns_dict(self, temp_chunks_jsonl, temp_persist_dir, temp_outputs_dir):
        result = run_pipeline(
            chunks_path=temp_chunks_jsonl,
            batch_size=32,
            embedding_batch_size=32,
            top_k=3,
            num_test_queries=2,
            skip_if_indexed=False,
        )

        assert isinstance(result, dict)
        assert "status" not in result or result.get("status") != "error"
        assert "total_chunks_loaded" in result
        assert "newly_indexed" in result
        assert "total_in_collection" in result

    def test_pipeline_indexes_all_chunks(self, temp_chunks_jsonl, temp_persist_dir, temp_outputs_dir):
        result = run_pipeline(
            chunks_path=temp_chunks_jsonl,
            batch_size=32,
            embedding_batch_size=32,
            top_k=3,
            num_test_queries=2,
            skip_if_indexed=False,
        )

        assert result["newly_indexed"] == result["total_chunks_loaded"]

    def test_pipeline_exit_criteria(self, temp_chunks_jsonl, temp_persist_dir, temp_outputs_dir):
        result = run_pipeline(
            chunks_path=temp_chunks_jsonl,
            batch_size=32,
            embedding_batch_size=32,
            top_k=3,
            num_test_queries=2,
            skip_if_indexed=False,
        )

        exit_criteria = result.get("exit_criteria", {})
        assert exit_criteria.get("all_chunks_indexed") is True

    def test_pipeline_creates_report(self, temp_chunks_jsonl, temp_persist_dir, temp_outputs_dir):
        run_pipeline(
            chunks_path=temp_chunks_jsonl,
            batch_size=32,
            embedding_batch_size=32,
            top_k=3,
            num_test_queries=2,
            skip_if_indexed=False,
            output_dir=temp_outputs_dir,
        )

        report_path = os.path.join(temp_outputs_dir, "phase3_report.json")
        assert os.path.exists(report_path)
        with open(report_path) as f:
            report = json.load(f)
        assert "exit_criteria" in report

    def test_pipeline_idempotent(self, temp_chunks_jsonl, temp_persist_dir, temp_outputs_dir):
        run_pipeline(
            chunks_path=temp_chunks_jsonl,
            batch_size=32,
            embedding_batch_size=32,
            top_k=3,
            num_test_queries=2,
            skip_if_indexed=False,
        )

        first_count = VectorIndexer(
            persist_directory=temp_persist_dir,
        ).collection.count()

        run_pipeline(
            chunks_path=temp_chunks_jsonl,
            batch_size=32,
            embedding_batch_size=32,
            top_k=3,
            num_test_queries=2,
            skip_if_indexed=True,
        )

        second_count = VectorIndexer(
            persist_directory=temp_persist_dir,
        ).collection.count()

        assert first_count == second_count

    def test_pipeline_empty_chunks_file(self, temp_persist_dir, temp_outputs_dir):
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Empty chunks file\n")
            empty_path = f.name

        try:
            result = run_pipeline(
                chunks_path=empty_path,
                batch_size=32,
                embedding_batch_size=32,
                top_k=3,
                num_test_queries=2,
                skip_if_indexed=False,
            )
            assert result.get("status") == "error"
        finally:
            os.unlink(empty_path)