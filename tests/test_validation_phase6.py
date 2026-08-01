"""
tests/test_validation_phase6.py
==================================
Tests for Phase 6 validation modules.

Covers:
  - src/validation/faithfulness.py
  - src/validation/coverage.py
  - src/validation/contradiction.py
  - src/validation/spot_check.py
  - src/validation/eval_report.py
  - src/validation/pipeline.py
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.validation.coverage import CoverageChecker
from src.validation.contradiction import ContradictionDetector
from src.validation.eval_report import EvalReportBuilder
from src.validation.faithfulness import FaithfulnessScorer
from src.validation.pipeline import ValidationPipeline
from src.validation.spot_check import SpotCheckManager


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_insights():
    return [
        {
            "research_question_id": "RQ1",
            "research_question_label": "Habit & Repetition",
            "finding": "Users stick to familiar categories due to trust and convenience.",
            "evidence": [
                {"quote": "I only buy from the same categories every week.", "source_chunk": "c1"},
                {"quote": "I never explore new sections of the app.", "source_chunk": "c3"},
            ],
            "implication": "Introduce discovery nudges.",
            "segment": "Weekly grocery shoppers",
            "confidence": 0.8,
            "chunk_ids": ["c1", "c3"],
        },
        {
            "research_question_id": "RQ2",
            "research_question_label": "Exploration Barriers",
            "finding": "Insufficient evidence to generate a meaningful insight.",
            "evidence": [
                {"quote": "No chunks retrieved for this question.", "source_chunk": "N/A"},
                {"quote": "No chunks retrieved for this question.", "source_chunk": "N/A"},
            ],
            "implication": "The corpus may lack relevant content.",
            "segment": "Unknown",
            "confidence": 0.0,
            "chunk_ids": [],
        },
        {
            "research_question_id": "RQ3",
            "research_question_label": "Discovery Pathways",
            "finding": "Users discover new products through deals and recommendations.",
            "evidence": [
                {"quote": "I discovered a new product because of a recommendation.", "source_chunk": "c4"},
                {"quote": "The offer led me to try something new.", "source_chunk": "c5"},
            ],
            "implication": "Promote deals more prominently.",
            "segment": "Deal-sensitive urban shoppers",
            "confidence": 0.85,
            "chunk_ids": ["c4", "c5"],
        },
    ]


@pytest.fixture
def sample_chunks():
    return [
        {
            "id": "c1",
            "document": "I only buy from the same categories every week. I never explore new sections of the app.",
            "metadata": {"source": "play_store", "app": "blinkit", "rating": 4},
        },
        {
            "id": "c3",
            "document": "The search and browsing experience needs improvement. It is hard to discover new categories.",
            "metadata": {"source": "play_store", "app": "swiggy_instamart", "rating": 3},
        },
        {
            "id": "c4",
            "document": "Discovering new products through deals and promotions is the best part of using Zepto.",
            "metadata": {"source": "play_store", "app": "zepto", "rating": 5},
        },
        {
            "id": "c5",
            "document": "I tried a new category because of a discount offer and now I buy it regularly.",
            "metadata": {"source": "play_store", "app": "zepto", "rating": 4},
        },
    ]


@pytest.fixture
def sample_retrieval_results(sample_chunks):
    return {
        "pipeline_run_timestamp": "2026-07-29T21:00:00",
        "phase": "Phase 5: Retrieval",
        "queries": [
            {
                "question_id": "RQ1",
                "label": "Habit & Repetition",
                "chunks": [sample_chunks[0], sample_chunks[1]],
                "total_retrieved": 2,
            },
            {
                "question_id": "RQ2",
                "label": "Exploration Barriers",
                "chunks": [],
                "total_retrieved": 0,
            },
            {
                "question_id": "RQ3",
                "label": "Discovery Pathways",
                "chunks": [sample_chunks[2], sample_chunks[3]],
                "total_retrieved": 2,
            },
        ],
    }


# ── Faithfulness Tests ─────────────────────────────────────────────────────────

class TestFaithfulnessScorerInit:
    def test_default_threshold(self):
        scorer = FaithfulnessScorer()
        assert scorer.threshold == 0.7

    def test_custom_threshold(self):
        scorer = FaithfulnessScorer(threshold=0.9)
        assert scorer.threshold == 0.9


class TestFaithfulnessScorerScoreInsight:
    def test_insufficient_evidence_returns_zero(self):
        scorer = FaithfulnessScorer()
        insight = {
            "research_question_id": "RQ2",
            "finding": "Insufficient evidence to generate a meaningful insight.",
        }
        result = scorer.score_insight(insight, [])
        assert result["faithfulness_score"] == 0.0
        assert result["faithfulness_passed"] is False
        assert result["judge"] == "skipped"

    def test_empty_finding_returns_zero(self):
        scorer = FaithfulnessScorer()
        insight = {"research_question_id": "RQ1", "finding": ""}
        result = scorer.score_insight(insight, [])
        assert result["faithfulness_score"] == 0.0

    def test_no_chunks_returns_zero(self):
        scorer = FaithfulnessScorer()
        insight = {"research_question_id": "RQ1", "finding": "Users stick to familiar categories."}
        result = scorer.score_insight(insight, [])
        assert result["faithfulness_score"] == 0.0
        assert result["judge"] == "skipped"

    def test_chunks_without_text_returns_zero(self):
        scorer = FaithfulnessScorer()
        insight = {"research_question_id": "RQ1", "finding": "Users stick to familiar categories."}
        chunks = [{"id": "c1", "metadata": {}}]
        result = scorer.score_insight(insight, chunks)
        assert result["faithfulness_score"] == 0.0

    @patch.object(FaithfulnessScorer, "_compute_score")
    def test_score_insight_calls_compute(self, mock_compute):
        mock_compute.return_value = (0.85, "Well supported", "llm-judge-gemini")
        scorer = FaithfulnessScorer()
        insight = {"research_question_id": "RQ1", "finding": "Users stick to familiar categories."}
        chunks = [{"document": "I only buy from the same categories.", "metadata": {}}]
        result = scorer.score_insight(insight, chunks)
        assert result["faithfulness_score"] == 0.85
        assert result["faithfulness_passed"] is True
        mock_compute.assert_called_once()

    def test_score_below_threshold_fails(self):
        scorer = FaithfulnessScorer(threshold=0.9)
        with patch.object(FaithfulnessScorer, "_compute_score", return_value=(0.85, "Mostly supported", "llm-judge-gemini")):
            insight = {"research_question_id": "RQ1", "finding": "Users stick to familiar categories."}
            chunks = [{"document": "test chunk", "metadata": {}}]
            result = scorer.score_insight(insight, chunks)
            assert result["faithfulness_passed"] is False

    def test_score_at_threshold_passes(self):
        scorer = FaithfulnessScorer(threshold=0.7)
        with patch.object(FaithfulnessScorer, "_compute_score", return_value=(0.7, "Supported", "llm-judge-gemini")):
            insight = {"research_question_id": "RQ1", "finding": "Users stick to familiar categories."}
            chunks = [{"document": "test chunk", "metadata": {}}]
            result = scorer.score_insight(insight, chunks)
            assert result["faithfulness_passed"] is True


class TestFaithfulnessScorerScoreAll:
    def test_score_all_returns_list(self, sample_insights, sample_retrieval_results):
        scorer = FaithfulnessScorer()
        with patch.object(FaithfulnessScorer, "score_insight") as mock_score:
            mock_score.return_value = {
                "research_question_id": "RQ1",
                "faithfulness_score": 0.8,
                "faithfulness_passed": True,
                "judge": "test",
                "reasoning": "test",
            }
            results = scorer.score_all(sample_insights, sample_retrieval_results)
            assert len(results) == len(sample_insights)
            assert mock_score.call_count == len(sample_insights)

    def test_score_all_maps_chunks_by_question(self, sample_insights, sample_retrieval_results):
        scorer = FaithfulnessScorer()
        chunks_map = {}
        for q in sample_retrieval_results["queries"]:
            chunks_map[q["question_id"]] = q["chunks"]

        with patch.object(FaithfulnessScorer, "score_insight") as mock_score:
            mock_score.return_value = {
                "research_question_id": "test",
                "faithfulness_score": 0.5,
                "faithfulness_passed": False,
                "judge": "test",
                "reasoning": "test",
            }
            scorer.score_all(sample_insights, sample_retrieval_results)
            assert mock_score.call_count == len(sample_insights)
            expected_chunks = [chunks_map[i["research_question_id"]] for i in sample_insights]
            for idx, insight in enumerate(sample_insights):
                call_args = mock_score.call_args_list[idx]
                assert call_args[0][0] == insight
                assert call_args[0][1] == expected_chunks[idx]


class TestFaithfulnessScorerLLMJudge:
    def test_parse_judge_response_valid(self):
        scorer = FaithfulnessScorer()
        score, reasoning = scorer._parse_judge_response('{"score": 0.85, "reasoning": "Well supported"}')
        assert score == 0.85
        assert reasoning == "Well supported"

    def test_parse_judge_response_clamps_bounds(self):
        scorer = FaithfulnessScorer()
        score, _ = scorer._parse_judge_response('{"score": 1.5, "reasoning": "test"}')
        assert score == 1.0
        score, _ = scorer._parse_judge_response('{"score": -0.2, "reasoning": "test"}')
        assert score == 0.0

    def test_parse_judge_response_invalid_json(self):
        scorer = FaithfulnessScorer()
        score, reasoning = scorer._parse_judge_response("Not JSON at all.")
        assert score == 0.0
        assert "Failed to parse" in reasoning

    def test_parse_judge_response_partial(self):
        scorer = FaithfulnessScorer()
        score, reasoning = scorer._parse_judge_response('some text "score": 0.6 more text')
        assert score == 0.6

    @patch.object(FaithfulnessScorer, "_call_judge_llm")
    def test_llm_judge_score_uses_call(self, mock_call):
        mock_call.return_value = '{"score": 0.9, "reasoning": "Very well supported"}'
        scorer = FaithfulnessScorer()
        score, reasoning, judge = scorer._llm_judge_score(
            "Users stick to familiar categories.",
            ["I only buy from the same categories every week."],
            {"evidence": [{"quote": "test"}]},
        )
        assert score == 0.9
        assert reasoning == "Very well supported"
        assert judge == "llm-judge-gemini"

    @patch.object(FaithfulnessScorer, "_call_judge_llm")
    def test_llm_judge_handles_failure(self, mock_call):
        mock_call.return_value = '{"score": 0.0, "reasoning": "LLM call failed during scoring."}'
        scorer = FaithfulnessScorer()
        score, reasoning, judge = scorer._llm_judge_score(
            "Users stick to familiar categories.",
            ["test chunk"],
            {"evidence": []},
        )
        assert score == 0.0
        assert judge == "llm-judge-gemini"


# ── Coverage Tests ─────────────────────────────────────────────────────────────

class TestCoverageChecker:
    def test_default_initialization(self):
        checker = CoverageChecker()
        assert len(checker.REQUIRED_QUESTION_IDS) == 8
        assert "RQ1" in checker.REQUIRED_QUESTION_IDS
        assert "RQ8" in checker.REQUIRED_QUESTION_IDS

    def test_all_questions_covered(self):
        checker = CoverageChecker()
        insights = [
            {
                "research_question_id": f"RQ{i}",
                "finding": f"Finding {i}",
                "evidence": [{"quote": f"q{i}"}, {"quote": f"q{i}b"}],
                "implication": f"Implication {i}",
                "segment": f"Segment {i}",
                "confidence": 0.8,
            }
            for i in range(1, 9)
        ]
        result = checker.check(insights)
        assert result["all_questions_covered"] is True
        assert result["all_schema_valid"] is True
        assert result["all_have_sufficient_evidence"] is True
        assert result["passed"] is True
        assert len(result["missing_questions"]) == 0

    def test_missing_questions_detected(self):
        checker = CoverageChecker()
        insights = [
            {"research_question_id": "RQ1", "finding": "Finding 1", "evidence": [{"quote": "q1"}, {"quote": "q1b"}], "confidence": 0.8},
            {"research_question_id": "RQ3", "finding": "Finding 3", "evidence": [{"quote": "q3"}, {"quote": "q3b"}], "confidence": 0.8},
        ]
        result = checker.check(insights)
        assert result["all_questions_covered"] is False
        assert "RQ2" in result["missing_questions"]
        assert "RQ4" in result["missing_questions"]
        assert result["passed"] is False

    def test_insufficient_evidence_detected(self):
        checker = CoverageChecker()
        insights = [
            {"research_question_id": "RQ1", "finding": "Insufficient evidence.", "evidence": [], "confidence": 0.0},
        ]
        result = checker.check(insights)
        assert result["all_have_sufficient_evidence"] is False
        assert "RQ1" in result["insufficient_evidence_questions"]
        assert result["passed"] is False

    def test_schema_validation_missing_fields(self):
        checker = CoverageChecker()
        insights = [
            {"research_question_id": "RQ1", "finding": "Test"},
        ]
        result = checker.check(insights)
        assert result["all_schema_valid"] is False
        assert len(result["schema_issues"]) > 0

    def test_schema_validation_insufficient_evidence_count(self):
        checker = CoverageChecker()
        insights = [
            {"research_question_id": "RQ1", "finding": "Test", "evidence": [{"quote": "only one"}], "confidence": 0.8},
        ]
        result = checker.check(insights)
        assert result["all_schema_valid"] is False
        assert any("evidence" in issue for issue in result["schema_issues"])

    def test_get_missing_questions(self):
        checker = CoverageChecker()
        insights = [{"research_question_id": "RQ1", "finding": "Test", "evidence": [{"quote": "q"}, {"quote": "q2"}], "confidence": 0.8}]
        missing = checker.get_missing_questions(insights)
        assert "RQ2" in missing
        assert "RQ8" in missing
        assert "RQ1" not in missing

    def test_insights_by_question_structure(self):
        checker = CoverageChecker()
        insights = [
            {
                "research_question_id": "RQ1",
                "research_question_label": "Habit",
                "finding": "Test finding",
                "evidence": [{"quote": "q1"}, {"quote": "q2"}],
                "implication": "Test implication",
                "segment": "Test segment",
                "confidence": 0.8,
            },
        ]
        result = checker.check(insights)
        rq1_info = result["insights_by_question"]["RQ1"]
        assert rq1_info["label"] == "Habit"
        assert rq1_info["evidence_count"] == 2
        assert rq1_info["schema_valid"] is True
        assert rq1_info["has_sufficient_evidence"] is True
        assert rq1_info["is_insufficient"] is False


# ── Contradiction Tests ────────────────────────────────────────────────────────

class TestContradictionDetector:
    def test_less_than_two_insights_returns_empty(self):
        detector = ContradictionDetector()
        assert detector.detect([]) == []
        assert detector.detect([{"research_question_id": "RQ1", "finding": "Test"}]) == []

    def test_heuristic_skip_insufficient(self):
        detector = ContradictionDetector(use_llm=False)
        insights = [
            {"research_question_id": "RQ1", "finding": "Insufficient evidence."},
            {"research_question_id": "RQ2", "finding": "Users love the app.", "segment": "All users"},
        ]
        results = detector.detect(insights)
        assert len(results) == 0

    def test_heuristic_skip_identical_findings(self):
        detector = ContradictionDetector(use_llm=False)
        insights = [
            {"research_question_id": "RQ1", "finding": "Users love the app."},
            {"research_question_id": "RQ2", "finding": "Users love the app."},
        ]
        results = detector.detect(insights)
        assert len(results) == 0

    def test_rule_based_contradiction(self):
        detector = ContradictionDetector(use_llm=False)
        insights = [
            {"research_question_id": "RQ1", "finding": "The app is great and easy to use.", "segment": "All users"},
            {"research_question_id": "RQ2", "finding": "The app is terrible and very frustrating.", "segment": "All users"},
        ]
        results = detector.detect(insights)
        assert len(results) == 1
        assert results[0]["contradicts"] is True
        assert results[0]["judge"] == "rule-based"
        assert results[0]["severity"] == "potential"

    def test_rule_based_no_contradiction(self):
        detector = ContradictionDetector(use_llm=False)
        insights = [
            {"research_question_id": "RQ1", "finding": "Delivery is fast.", "segment": "Urban users"},
            {"research_question_id": "RQ2", "finding": "Prices are reasonable.", "segment": "All users"},
        ]
        results = detector.detect(insights)
        assert len(results) == 0

    def test_llm_check_called_when_enabled(self):
        detector = ContradictionDetector(use_llm=True)
        insights = [
            {"research_question_id": "RQ1", "finding": "Users find discovery easy via deals.", "segment": "Deal seekers"},
            {"research_question_id": "RQ2", "finding": "Users say there is no discovery mechanism.", "segment": "Frustrated users"},
        ]
        with patch.object(detector, "_llm_check") as mock_llm:
            mock_llm.return_value = {
                "insight_a": "RQ1",
                "insight_b": "RQ2",
                "contradicts": True,
                "severity": "medium",
                "explanation": "Opposing claims.",
                "judge": "llm",
            }
            results = detector.detect(insights)
            mock_llm.assert_called_once()
            assert len(results) == 1
            assert results[0]["contradicts"] is True

    def test_parse_contradiction_response_valid(self):
        detector = ContradictionDetector()
        insight_a = {"research_question_id": "RQ1", "finding": "Finding A"}
        insight_b = {"research_question_id": "RQ2", "finding": "Finding B"}
        result = detector._parse_contraction_response(
            '{"contradicts": true, "severity": "medium", "explanation": "Opposing claims"}',
            insight_a,
            insight_b,
        )
        assert result["contradicts"] is True
        assert result["severity"] == "medium"
        assert result["judge"] == "llm-judge-gemini"

    def test_parse_contradiction_response_invalid(self):
        detector = ContradictionDetector()
        insight_a = {"research_question_id": "RQ1", "finding": "Finding A"}
        insight_b = {"research_question_id": "RQ2", "finding": "Finding B"}
        result = detector._parse_contraction_response("Not JSON", insight_a, insight_b)
        assert result["contradicts"] is False
        assert "fallback" in result["judge"]


# ── Spot-Check Tests ───────────────────────────────────────────────────────────

class TestSpotCheckManager:
    def test_select_insights_returns_list(self, sample_insights, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        selected = manager.select_insights(sample_insights, n=2)
        assert len(selected) == 2
        assert all("spot_check_index" in s for s in selected)

    def test_select_insights_respects_n(self, sample_insights, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        selected = manager.select_insights(sample_insights, n=5)
        assert len(selected) == min(5, len(sample_insights))

    def test_select_insights_with_seed(self, sample_insights, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        selected1 = manager.select_insights(sample_insights, n=2, seed=42)
        selected2 = manager.select_insights(sample_insights, n=2, seed=42)
        assert [s["research_question_id"] for s in selected1] == [s["research_question_id"] for s in selected2]

    def test_record_review_valid(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        review = manager.record_review("RQ1", "Grounded", "Very well supported.")
        assert review["insight_id"] == "RQ1"
        assert review["rating"] == "grounded"
        assert review["rating_display"] == "Grounded"
        assert "timestamp" in review

    def test_record_review_case_insensitive(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        review = manager.record_review("RQ1", "GROUNDED")
        assert review["rating"] == "grounded"

    def test_record_review_invalid_rating_raises(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        with pytest.raises(ValueError):
            manager.record_review("RQ1", "InvalidRating")

    def test_record_review_overwrites_existing(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        manager.record_review("RQ1", "Grounded")
        manager.record_review("RQ1", "Hallucinated", "Updated review.")
        assert len(manager.reviews) == 1
        assert manager.reviews[0]["rating"] == "hallucinated"

    def test_get_report_structure(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        manager.record_review("RQ1", "Grounded")
        manager.record_review("RQ2", "Hallucinated", "Not supported.")
        report = manager.get_report()
        assert report["total_reviews"] == 2
        assert report["grounded_count"] == 1
        assert report["hallucinated_count"] == 1
        assert report["hallucination_rate"] == 0.5
        assert report["passed"] is False
        assert len(report["reviews"]) == 2

    def test_get_report_passes_with_no_hallucinated(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        manager.record_review("RQ1", "Grounded")
        manager.record_review("RQ2", "Partially Grounded")
        report = manager.get_report()
        assert report["passed"] is True

    def test_get_report_empty(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        report = manager.get_report()
        assert report["total_reviews"] == 0
        assert report["passed"] is True

    def test_get_unreviewed(self, sample_insights, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        manager.record_review("RQ1", "Grounded")
        unreviewed = manager.get_unreviewed(sample_insights)
        assert len(unreviewed) == 2
        assert all(i["research_question_id"] != "RQ1" for i in unreviewed)

    def test_clear_reviews(self, tmp_path):
        manager = SpotCheckManager(output_dir=str(tmp_path))
        manager.record_review("RQ1", "Grounded")
        manager.clear()
        assert len(manager.reviews) == 0
        assert manager.get_report()["total_reviews"] == 0


# ── Eval Report Tests ──────────────────────────────────────────────────────────

class TestEvalReportBuilder:
    def test_build_report_structure(self, sample_insights, sample_retrieval_results):
        builder = EvalReportBuilder()
        faithfulness_scores = [
            {"research_question_id": "RQ1", "faithfulness_score": 0.85, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"},
            {"research_question_id": "RQ2", "faithfulness_score": 0.0, "faithfulness_passed": False, "judge": "skipped", "reasoning": "no finding"},
            {"research_question_id": "RQ3", "faithfulness_score": 0.9, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"},
        ]
        coverage = {
            "all_questions_covered": False,
            "coverage_count": 2,
            "total_questions": 8,
            "missing_questions": ["RQ2"],
            "passed": False,
        }
        contradictions = []
        spot_check = {"total_reviews": 5, "hallucinated_count": 0, "partially_grounded_count": 1, "passed": True}

        report = builder.build(
            insights=sample_insights,
            faithfulness_scores=faithfulness_scores,
            coverage_result=coverage,
            contradictions=contradictions,
            spot_check_report=spot_check,
            retrieval_results=sample_retrieval_results,
        )

        assert report["phase"] == "Phase 6: Validation & Quality Assurance"
        assert "faithfulness" in report
        assert "coverage" in report
        assert "contradictions" in report
        assert "spot_check" in report
        assert "insights" in report
        assert report["faithfulness"]["total_insights"] == 3
        assert report["faithfulness"]["passed"] == 2
        assert report["faithfulness"]["failed"] == 1

    def test_build_report_enriches_insights(self):
        builder = EvalReportBuilder()
        insights = [{"research_question_id": "RQ1", "finding": "Test", "evidence": [], "confidence": 0.8}]
        scores = [{"research_question_id": "RQ1", "faithfulness_score": 0.8, "faithfulness_passed": True, "judge": "llm", "reasoning": "ok"}]
        coverage = {"all_questions_covered": False, "coverage_count": 0, "total_questions": 8, "missing_questions": [], "passed": False}
        report = builder.build(insights, scores, coverage, [], {"total_reviews": 0, "hallucinated_count": 0, "passed": True})

        enriched = report["insights"][0]
        assert enriched["faithfulness_score"] == 0.8
        assert enriched["faithfulness_passed"] is True
        assert enriched["faithfulness_judge"] == "llm"

    def test_save_report_creates_file(self, tmp_path):
        builder = EvalReportBuilder(output_dir=str(tmp_path))
        report = {"phase": "Phase 6", "passed": True}
        saved = builder.save(report)
        assert saved.exists()
        with open(saved) as f:
            loaded = json.load(f)
        assert loaded["passed"] is True

    def test_passed_true_when_all_checks_pass(self):
        builder = EvalReportBuilder()
        scores = [{"research_question_id": f"RQ{i}", "faithfulness_score": 0.9, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"} for i in range(1, 9)]
        coverage = {"all_questions_covered": True, "coverage_count": 8, "total_questions": 8, "missing_questions": [], "schema_issues": [], "all_schema_valid": True, "insufficient_evidence_questions": [], "all_have_sufficient_evidence": True, "passed": True}
        report = builder.build(
            insights=[],
            faithfulness_scores=scores,
            coverage_result=coverage,
            contradictions=[],
            spot_check_report={"total_reviews": 5, "hallucinated_count": 0, "partially_grounded_count": 1, "passed": True},
        )
        assert report["passed"] is True

    def test_passed_false_when_coverage_fails(self):
        builder = EvalReportBuilder()
        scores = [{"research_question_id": f"RQ{i}", "faithfulness_score": 0.9, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"} for i in range(1, 9)]
        coverage = {"all_questions_covered": False, "coverage_count": 7, "total_questions": 8, "missing_questions": ["RQ8"], "schema_issues": [], "all_schema_valid": True, "insufficient_evidence_questions": [], "all_have_sufficient_evidence": True, "passed": False}
        report = builder.build(
            insights=[],
            faithfulness_scores=scores,
            coverage_result=coverage,
            contradictions=[],
            spot_check_report={"total_reviews": 5, "hallucinated_count": 0, "partially_grounded_count": 1, "passed": True},
        )
        assert report["passed"] is False

    def test_passed_false_when_faithfulness_fails(self):
        builder = EvalReportBuilder()
        scores = [{"research_question_id": f"RQ{i}", "faithfulness_score": 0.9, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"} for i in range(1, 8)]
        scores.append({"research_question_id": "RQ8", "faithfulness_score": 0.5, "faithfulness_passed": False, "judge": "test", "reasoning": "weak"})
        coverage = {"all_questions_covered": True, "coverage_count": 8, "total_questions": 8, "missing_questions": [], "schema_issues": [], "all_schema_valid": True, "insufficient_evidence_questions": [], "all_have_sufficient_evidence": True, "passed": True}
        report = builder.build(
            insights=[],
            faithfulness_scores=scores,
            coverage_result=coverage,
            contradictions=[],
            spot_check_report={"total_reviews": 5, "hallucinated_count": 0, "partially_grounded_count": 1, "passed": True},
        )
        assert report["passed"] is False

    def test_passed_false_when_hallucinated_in_spot_check(self):
        builder = EvalReportBuilder()
        scores = [{"research_question_id": f"RQ{i}", "faithfulness_score": 0.9, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"} for i in range(1, 9)]
        coverage = {"all_questions_covered": True, "coverage_count": 8, "total_questions": 8, "missing_questions": [], "schema_issues": [], "all_schema_valid": True, "insufficient_evidence_questions": [], "all_have_sufficient_evidence": True, "passed": True}
        report = builder.build(
            insights=[],
            faithfulness_scores=scores,
            coverage_result=coverage,
            contradictions=[],
            spot_check_report={"total_reviews": 5, "hallucinated_count": 1, "partially_grounded_count": 1, "passed": True},
        )
        assert report["passed"] is False


# ── Pipeline Tests ─────────────────────────────────────────────────────────────

class TestValidationPipeline:
    def test_run_empty_insights_builds_empty_report(self, tmp_path):
        pipeline = ValidationPipeline(
            insights_path=str(tmp_path / "nonexistent.json"),
            output_path=str(tmp_path / "eval_report.json"),
        )
        with patch.object(ValidationPipeline, "_init_report_builder") as mock_builder:
            mock_builder.return_value.save.return_value = tmp_path / "eval_report.json"
            report = pipeline.run()
            assert report["passed"] is False
            assert "error" in report

    def test_run_produces_report(self, tmp_path, sample_insights, sample_retrieval_results):
        insights_path = tmp_path / "insights.json"
        with open(insights_path, "w") as f:
            json.dump({"insights": sample_insights}, f)

        retrieval_path = tmp_path / "retrieval_results.json"
        with open(retrieval_path, "w") as f:
            json.dump(sample_retrieval_results, f)

        output_path = tmp_path / "eval_report.json"

        pipeline = ValidationPipeline(
            insights_path=str(insights_path),
            retrieval_results_path=str(retrieval_path),
            output_path=str(output_path),
        )

        with patch.object(ValidationPipeline, "_run_faithfulness") as mock_faith, \
             patch.object(ValidationPipeline, "_run_coverage") as mock_cov, \
             patch.object(ValidationPipeline, "_run_contradictions") as mock_contra, \
             patch.object(ValidationPipeline, "_run_spot_check") as mock_spot:
            mock_faith.return_value = [
                {"research_question_id": "RQ1", "faithfulness_score": 0.85, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"},
                {"research_question_id": "RQ2", "faithfulness_score": 0.0, "faithfulness_passed": False, "judge": "skipped", "reasoning": "no finding"},
                {"research_question_id": "RQ3", "faithfulness_score": 0.9, "faithfulness_passed": True, "judge": "test", "reasoning": "ok"},
            ]
            mock_cov.return_value = {
                "all_questions_covered": False,
                "coverage_count": 2,
                "total_questions": 8,
                "missing_questions": [],
                "schema_issues": [],
                "all_schema_valid": True,
                "insufficient_evidence_questions": ["RQ2"],
                "all_have_sufficient_evidence": False,
                "passed": False,
            }
            mock_contra.return_value = []
            mock_spot.return_value = {"total_reviews": 3, "hallucinated_count": 0, "partially_grounded_count": 0, "passed": True}

            report = pipeline.run()

            assert "phase" in report
            assert report["phase"] == "Phase 6: Validation & Quality Assurance"
            assert output_path.exists()
