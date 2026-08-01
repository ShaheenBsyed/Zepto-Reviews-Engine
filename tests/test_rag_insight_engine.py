"""
tests/test_rag_insight_engine.py
==================================
Tests for the RAGInsightEngine class in src/rag/insight_engine.py.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.rag.insight_engine import RAGInsightEngine
from src.rag.prompt_templates import FALLBACK_INSIGHT


class TestRAGInsightEngineInit:
    def test_defaults(self):
        engine = RAGInsightEngine()
        assert engine.top_k == 10
        assert engine.output_dir.name == "outputs"
        assert len(engine.queries) == 8

    def test_custom_params(self):
        engine = RAGInsightEngine(top_k=5, output_dir="outputs")
        assert engine.top_k == 5


class TestRAGInsightEngineRetrieval:
    def test_run_retrieval_returns_results(self):
        engine = RAGInsightEngine()
        with patch("src.rag.retriever.RAGRetriever") as MockRetriever:
            mock_retriever = MockRetriever.return_value
            mock_retriever.retrieve_all.return_value = {
                "queries": [
                    {
                        "question_id": "RQ1",
                        "label": "Habit",
                        "chunks": [
                            {"id": "c1", "document": "I always buy the same things", "metadata": {"source": "play_store"}},
                            {"id": "c2", "document": "I never try new categories", "metadata": {"source": "play_store"}},
                        ],
                    }
                ]
            }
            mock_retriever.save_results.return_value = None

            results = engine.run_retrieval(save=False)
            assert "queries" in results
            assert len(results["queries"]) == 1

    def test_load_retrieved_chunks_from_dict(self):
        engine = RAGInsightEngine()
        retrieval_output = {
            "queries": [
                {
                    "question_id": "RQ1",
                    "chunks": [{"id": "c1", "document": "test", "metadata": {}}],
                }
            ]
        }
        engine.load_retrieved_chunks(retrieval_output)
        assert "RQ1" in engine._retrieved_chunks
        assert len(engine._retrieved_chunks["RQ1"]) == 1


class TestRAGInsightEngineGenerate:
    def test_generate_insight_no_chunks(self):
        engine = RAGInsightEngine()
        query_entry = {"id": "RQ1", "label": "Habit", "question": "test", "metadata_filters": {}}
        insight = engine.generate_insight(query_entry, [])
        assert insight["finding"] == FALLBACK_INSIGHT["finding"]
        assert insight["confidence"] == 0.0
        assert insight["research_question_id"] == "RQ1"

    def test_generate_insight_with_chunks(self):
        engine = RAGInsightEngine()
        query_entry = {
            "id": "RQ1",
            "label": "Habit",
            "question": "Why do users repeatedly buy from the same categories?",
            "metadata_filters": {},
        }
        chunks = [
            {"id": "c1", "document": "I always buy the same things every week and never try anything new from this app. I just stick to what I know.", "metadata": {"source": "play_store", "app": "zepto", "rating": 4}},
            {"id": "c2", "document": "The delivery is fast and I trust the quality so I don't explore other sections.", "metadata": {"source": "play_store", "app": "zepto", "rating": 5}},
        ]

        mock_response = {
            "finding": "Users stick to familiar categories due to trust and convenience.",
            "evidence": [
                {"quote": "I always buy the same things every week and never try anything new from this app. I just stick to what I know.", "source_chunk": "c1"},
                {"quote": "The delivery is fast and I trust the quality so I don't explore other sections.", "source_chunk": "c2"},
            ],
            "implication": "Zepto should introduce gentle nudges to encourage exploration without breaking trust.",
            "segment": "Regular weekly grocery shoppers in urban areas",
            "confidence": 0.85,
        }

        with patch.object(engine, "_call_llm", return_value=mock_response):
            insight = engine.generate_insight(query_entry, chunks)

        assert insight["finding"] == mock_response["finding"]
        assert insight["confidence"] == 0.85
        assert insight["research_question_id"] == "RQ1"
        assert insight["research_question_label"] == "Habit"
        assert len(insight["evidence_linked"]) == 2
        assert all(item["grounded"] for item in insight["evidence_linked"])

    def test_generate_insight_llm_failure(self):
        engine = RAGInsightEngine()
        query_entry = {"id": "RQ1", "label": "Habit", "question": "test", "metadata_filters": {}}
        chunks = [{"id": "c1", "document": "test text", "metadata": {}}]

        with patch.object(engine, "_call_llm", return_value=FALLBACK_INSIGHT):
            insight = engine.generate_insight(query_entry, chunks)

        assert insight["finding"] == FALLBACK_INSIGHT["finding"]
        assert insight["confidence"] == 0.0

    def test_format_chunks_uses_document_field(self):
        engine = RAGInsightEngine()
        chunks = [
            {"id": "c1", "document": "Text in document field", "text": "", "metadata": {"source": "play_store", "app": "zepto", "rating": 4}},
            {"id": "c2", "document": "", "text": "Text in text field", "metadata": {"source": "play_store", "app": "zepto", "rating": 3}},
        ]
        formatted = engine._format_chunks_for_prompt(chunks)
        assert "Text in document field" in formatted
        assert "Text in text field" in formatted


class TestRAGInsightEngineParsing:
    def test_parse_llm_json_valid(self):
        engine = RAGInsightEngine()
        raw = '{"finding": "test", "evidence": [{"quote": "q1", "source_chunk": "c1"}], "implication": "impl", "segment": "seg", "confidence": 0.9}'
        result = engine._parse_llm_json(raw, fallback=FALLBACK_INSIGHT)
        assert result["finding"] == "test"
        assert result["confidence"] == 0.9

    def test_parse_llm_json_with_code_block(self):
        engine = RAGInsightEngine()
        raw = '```json\n{"finding": "test", "evidence": [], "implication": "impl", "segment": "seg", "confidence": 0.5}\n```'
        result = engine._parse_llm_json(raw, fallback=FALLBACK_INSIGHT)
        assert result["finding"] == "test"

    def test_parse_llm_json_invalid(self):
        engine = RAGInsightEngine()
        raw = "This is not JSON at all."
        result = engine._parse_llm_json(raw, fallback=FALLBACK_INSIGHT)
        assert result == FALLBACK_INSIGHT

    def test_parse_insight_minimal(self):
        engine = RAGInsightEngine()
        raw = {"finding": "Only a finding"}
        result = engine._parse_insight(raw)
        assert result["finding"] == "Only a finding"
        assert len(result["evidence"]) == 2
        assert result["confidence"] == 0.0

    def test_parse_insight_confidence_bounds(self):
        engine = RAGInsightEngine()
        raw = {"finding": "test", "confidence": 1.5}
        result = engine._parse_insight(raw)
        assert result["confidence"] == 1.0

        raw = {"finding": "test", "confidence": -0.5}
        result = engine._parse_insight(raw)
        assert result["confidence"] == 0.0


class TestRAGInsightEngineRun:
    def test_run_returns_report(self):
        engine = RAGInsightEngine(output_dir="outputs")
        retrieval_output = {
            "queries": [
                {
                    "question_id": f"RQ{i}",
                    "chunks": [
                        {"id": f"c{i}", "document": f"test text {i}", "metadata": {"source": "play_store", "app": "zepto", "rating": 4}}
                    ],
                }
                for i in range(1, 9)
            ]
        }

        mock_response = {
            "finding": "Users stick to familiar categories.",
            "evidence": [{"quote": "test text", "source_chunk": "c1"}],
            "implication": "Introduce discovery nudges.",
            "segment": "Weekly grocery shoppers",
            "confidence": 0.8,
        }

        with patch.object(engine, "_call_llm", return_value=mock_response):
            report = engine.run(retrieval_output=retrieval_output)

        assert "insights" in report
        assert len(report["insights"]) == 8
        assert report["total_questions"] == 8
        assert report["insufficient_evidence_count"] == 0

    def test_run_saves_insights_json(self):
        engine = RAGInsightEngine(output_dir="outputs")
        retrieval_output = {
            "queries": [
                {
                    "question_id": "RQ1",
                    "chunks": [
                        {"id": "c1", "document": "test text", "metadata": {"source": "play_store", "app": "zepto", "rating": 4}}
                    ],
                }
            ]
        }

        mock_response = {
            "finding": "Users stick to familiar categories.",
            "evidence": [{"quote": "test text", "source_chunk": "c1"}],
            "implication": "Introduce discovery nudges.",
            "segment": "Weekly grocery shoppers",
            "confidence": 0.8,
        }

        with patch.object(engine, "_call_llm", return_value=mock_response):
            report = engine.run(retrieval_output=retrieval_output)

        output_path = engine.output_dir / "insights.json"
        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["total_questions"] == 8
