"""
tests/conftest.py
===================
Shared fixtures for Phase 3 embedding tests.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_chunks() -> list[dict]:
    """Return a list of sample chunk records for testing."""
    return [
        {
            "chunk_id": "chunk-001",
            "text": "I love shopping for groceries on this app. The delivery is always fast and the items are fresh.",
            "parent_record_id": "record-001",
            "chunk_index": 0,
            "total_chunks": 1,
            "source": "play_store",
            "app": "zepto",
            "rating": 5,
            "created_at": "2025-06-15",
            "language": "en",
            "metadata": {"app_id": "com.zeptoconsumerapp"},
        },
        {
            "chunk_id": "chunk-002",
            "text": "The app keeps crashing when I try to browse different categories. Very frustrating experience.",
            "parent_record_id": "record-002",
            "chunk_index": 0,
            "total_chunks": 1,
            "source": "play_store",
            "app": "zepto",
            "rating": 2,
            "created_at": "2025-07-20",
            "language": "en",
            "metadata": {"app_id": "com.zeptoconsumerapp"},
        },
        {
            "chunk_id": "chunk-003",
            "text": "I only buy from the same categories every week. I never explore new sections of the app.",
            "parent_record_id": "record-003",
            "chunk_index": 0,
            "total_chunks": 1,
            "source": "play_store",
            "app": "blinkit",
            "rating": 4,
            "created_at": "2025-08-01",
            "language": "en",
            "metadata": {"app_id": "com.blinkit"},
        },
        {
            "chunk_id": "chunk-004",
            "text": "Discovering new products through deals and promotions is the best part of using Zepto.",
            "parent_record_id": "record-004",
            "chunk_index": 0,
            "total_chunks": 1,
            "source": "forum",
            "app": "zepto",
            "rating": None,
            "created_at": "2025-05-10",
            "language": "en",
            "metadata": {"thread_title": "Best deals on Zepto"},
        },
        {
            "chunk_id": "chunk-005",
            "text": "The search and browsing experience needs improvement. It is hard to discover new categories.",
            "parent_record_id": "record-005",
            "chunk_index": 0,
            "total_chunks": 1,
            "source": "play_store",
            "app": "swiggy_instamart",
            "rating": 3,
            "created_at": "2025-09-05",
            "language": "en",
            "metadata": {"app_id": "com.swiggy.instamart"},
        },
    ]


@pytest.fixture
def temp_chunks_jsonl(sample_chunks: list[dict]) -> str:
    """Create a temporary JSONL file with sample chunks."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for chunk in sample_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        temp_path = f.name

    yield temp_path

    os.unlink(temp_path)


@pytest.fixture
def temp_persist_dir() -> str:
    """Create a temporary directory for ChromaDB persistence."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def temp_cache_path() -> str:
    """Create a temporary path for the embedding cache."""
    tmpdir = tempfile.mkdtemp()
    yield os.path.join(tmpdir, "embedding_cache.json")
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def temp_outputs_dir() -> str:
    """Create a temporary directory for output files."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass

@pytest.fixture
def tempdir() -> str:
    """Create a temporary directory for test outputs."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass

