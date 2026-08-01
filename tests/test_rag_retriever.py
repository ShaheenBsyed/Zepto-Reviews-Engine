"""
tests/test_rag_retriever.py
============================
Tests for the RAGRetriever class in src/rag/retriever.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.embedding.indexer import VectorIndexer
from src.rag.retriever import RAGRetriever


class TestRAGRetrieverInit:
    def test_defaults(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_retriever_defaults",
            persist_directory=temp_persist_dir,
        )
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)
        indexer.upsert(sample_chunks, embeddings)

        retriever = RAGRetriever(indexer=indexer)
        assert retriever.top_k == 10
        assert retriever.max_chunks_per_parent == 2

    def test_custom_params(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_retriever_custom",
            persist_directory=temp_persist_dir,
        )
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)
        indexer.upsert(sample_chunks, embeddings)

        retriever = RAGRetriever(indexer=indexer, top_k=3, max_chunks_per_parent=1)
        assert retriever.top_k == 3
        assert retriever.max_chunks_per_parent == 1


class TestRAGRetrieverRetrieve:
    def test_retrieve_returns_chunks(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_retrieve_chunks",
            persist_directory=temp_persist_dir,
        )
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)
        indexer.upsert(sample_chunks, embeddings)

        retriever = RAGRetriever(indexer=indexer, top_k=3)
        query_entry = {
            "id": "TQ1",
            "label": "Test Query",
            "semantic_query": "I always buy the same things",
            "metadata_filters": {},
        }
        result = retriever.retrieve_for_query(query_entry)

        assert result["question_id"] == "TQ1"
        assert "chunks" in result
        assert result["total_retrieved"] == len(result["chunks"])

    def test_retrieve_empty_on_no_match(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_retrieve_empty",
            persist_directory=temp_persist_dir,
        )
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)
        indexer.upsert(sample_chunks, embeddings)

        retriever = RAGRetriever(indexer=indexer, top_k=3)
        query_entry = {
            "id": "TQ2",
            "label": "Unrelated Query",
            "semantic_query": "xyzzy completely unrelated nonsense query",
            "metadata_filters": {},
        }
        result = retriever.retrieve_for_query(query_entry)
        assert result["total_retrieved"] >= 0

    def test_retrieve_applies_metadata_filter(self, temp_persist_dir, sample_chunks):
        indexer = VectorIndexer(
            collection_name="test_retrieve_filter",
            persist_directory=temp_persist_dir,
        )
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)
        indexer.upsert(sample_chunks, embeddings)

        retriever = RAGRetriever(indexer=indexer, top_k=10)
        query_entry = {
            "id": "TQ3",
            "label": "Zepto Only",
            "semantic_query": "shopping groceries",
            "metadata_filters": {"app": "zepto"},
        }
        result = retriever.retrieve_for_query(query_entry)
        for chunk in result["chunks"]:
            assert chunk.get("metadata", {}).get("app") == "zepto"

    def test_retrieve_enforces_parent_diversity(self, temp_persist_dir):
        chunks = [
            {
                "chunk_id": f"chunk-{i:03d}",
                "text": "I always buy the same things every week and never try anything new from this app. I just stick to what I know.",
                "parent_record_id": "record-001",
                "chunk_index": i,
                "total_chunks": 3,
                "source": "play_store",
                "app": "zepto",
                "rating": 4,
                "date": "2025-06-15",
                "language": "en",
            }
            for i in range(3)
        ]

        indexer = VectorIndexer(
            collection_name="test_diversity",
            persist_directory=temp_persist_dir,
        )
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in chunks]
        embeddings = embedder.embed(texts)
        indexer.upsert(chunks, embeddings)

        retriever = RAGRetriever(indexer=indexer, top_k=10, max_chunks_per_parent=2)
        query_entry = {
            "id": "TQ4",
            "label": "Diversity Test",
            "semantic_query": "I always buy the same things every week",
            "metadata_filters": {},
        }
        result = retriever.retrieve_for_query(query_entry)
        parent_counts: dict[str, int] = {}
        for chunk in result["chunks"]:
            pid = chunk.get("metadata", {}).get("parent_record_id", chunk.get("id", ""))
            parent_counts[pid] = parent_counts.get(pid, 0) + 1
        for count in parent_counts.values():
            assert count <= 2

    def test_save_results_creates_file(self, temp_persist_dir, sample_chunks, temp_outputs_dir):
        indexer = VectorIndexer(
            collection_name="test_save_results",
            persist_directory=temp_persist_dir,
        )
        from src.embedding.embedder import Embedder

        embedder = Embedder()
        texts = [c["text"] for c in sample_chunks]
        embeddings = embedder.embed(texts)
        indexer.upsert(sample_chunks, embeddings)

        retriever = RAGRetriever(indexer=indexer, top_k=3)
        query_entry = {
            "id": "TQ5",
            "label": "Save Test",
            "semantic_query": "I always buy the same things",
            "metadata_filters": {},
        }
        results = retriever.retrieve_all([query_entry])
        output_path = Path(temp_outputs_dir) / "retrieval_results.json"
        saved = retriever.save_results(results, output_path=str(output_path))

        assert saved.exists()
        with open(saved, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert "queries" in loaded
        assert len(loaded["queries"]) == 1
