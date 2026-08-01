"""
src/validation/faithfulness.py
================================
Faithfulness scoring for Phase 6 validation.

Uses RAGAS when available; falls back to an LLM-as-judge using Gemini
(the same free-tier model used by the rest of the pipeline).

Scoring question: "Is the finding fully supported by the provided evidence?"
Scale: 0.0–1.0 (threshold: 0.7 to pass).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RPM = 15
COOLDOWN_SECONDS = 60.0 / MAX_RPM
DEFAULT_THRESHOLD = 0.7


class FaithfulnessScorer:
    """
    Scores each insight's faithfulness against its retrieved evidence chunks.

    Tries RAGAS first; if RAGAS is unavailable or fails, falls back to
    a direct Gemini LLM-as-judge call using the same client pattern as
    the Phase 5 insight engine.
    """

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        use_ragas: bool = True,
    ) -> None:
        self.threshold = threshold
        self.use_ragas = use_ragas
        self._ragas_available = False
        self._last_call_time: float = 0.0

        if use_ragas:
            self._check_ragas()

    def _check_ragas(self) -> None:
        try:
            import ragas  # noqa: F401
            from ragas.metrics import faithfulness as ragas_faithfulness
            self._ragas_available = True
            self._ragas_faithfulness = ragas_faithfulness
            logger.info("RAGAS faithfulness metric loaded")
        except Exception as exc:
            logger.warning("RAGAS not available, will use LLM-as-judge fallback: %s", exc)
            self._ragas_available = False

    def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < COOLDOWN_SECONDS:
            time.sleep(COOLDOWN_SECONDS - elapsed)
        self._last_call_time = time.time()

    def score_insight(
        self,
        insight: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Score a single insight against its retrieved chunks.

        Args:
            insight: Insight dict with at least `finding`, `evidence`, `research_question_id`.
            chunks: Retrieved chunk dicts for this question.

        Returns:
            Dict with `faithfulness_score`, `faithfulness_passed`, `judge`, `reasoning`.
        """
        finding = insight.get("finding", "")
        question_id = insight.get("research_question_id", "unknown")

        if not finding or finding.startswith("Insufficient"):
            return {
                "research_question_id": question_id,
                "faithfulness_score": 0.0,
                "faithfulness_passed": False,
                "judge": "skipped",
                "reasoning": "Insight has no meaningful finding to score.",
            }

        if not chunks:
            return {
                "research_question_id": question_id,
                "faithfulness_score": 0.0,
                "faithfulness_passed": False,
                "judge": "skipped",
                "reasoning": "No retrieved chunks available for scoring.",
            }

        chunk_texts = [
            c.get("document", "") or c.get("text", "") for c in chunks if c.get("document") or c.get("text")
        ]

        if not chunk_texts:
            return {
                "research_question_id": question_id,
                "faithfulness_score": 0.0,
                "faithfulness_passed": False,
                "judge": "skipped",
                "reasoning": "Retrieved chunks have no text content.",
            }

        score, reasoning, judge = self._compute_score(finding, chunk_texts, insight)

        return {
            "research_question_id": question_id,
            "faithfulness_score": round(score, 4),
            "faithfulness_passed": score >= self.threshold,
            "judge": judge,
            "reasoning": reasoning,
        }

    def score_all(
        self,
        insights: list[dict[str, Any]],
        retrieval_results: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Score all insights against their retrieval results.

        Args:
            insights: List of insight dicts from insights.json.
            retrieval_results: Retrieval results dict from retrieval_results.json.

        Returns:
            List of per-insight faithfulness score dicts.
        """
        chunks_by_question: dict[str, list[dict[str, Any]]] = {}
        for query in retrieval_results.get("queries", []):
            qid = query.get("question_id", "")
            chunks_by_question[qid] = query.get("chunks", [])

        scores = []
        for insight in insights:
            qid = insight.get("research_question_id", "")
            chunks = chunks_by_question.get(qid, [])
            scores.append(self.score_insight(insight, chunks))

        return scores

    def _compute_score(
        self,
        finding: str,
        chunk_texts: list[str],
        insight: dict[str, Any],
    ) -> tuple[float, str, str]:
        """Compute faithfulness score, trying RAGAS first then LLM fallback."""
        if self._ragas_available:
            try:
                return self._ragas_score(finding, chunk_texts)
            except Exception as exc:
                logger.warning("RAGAS scoring failed, falling back to LLM judge: %s", exc)

        return self._llm_judge_score(finding, chunk_texts, insight)

    def _ragas_score(
        self,
        finding: str,
        chunk_texts: list[str],
    ) -> tuple[float, str, str]:
        """Score using RAGAS faithfulness metric."""
        from ragas import SingleTurnSample
        from ragas.metrics import faithfulness

        sample = SingleTurnSample(
            user_input=finding,
            response=finding,
            retrieved_contexts=chunk_texts,
        )

        result = faithfulness._single_turn_score(sample, self._ragas_faithfulness)
        score = float(result) if result is not None else 0.0
        score = max(0.0, min(1.0, score))

        return score, "Scored by RAGAS faithfulness metric", "ragas"

    def _llm_judge_score(
        self,
        finding: str,
        chunk_texts: list[str],
        insight: dict[str, Any],
    ) -> tuple[float, str, str]:
        """Score using Gemini as an LLM judge."""
        evidence_quotes = [e.get("quote", "") for e in insight.get("evidence", []) if e.get("quote")]

        prompt = self._build_judge_prompt(finding, chunk_texts, evidence_quotes)
        raw_response = self._call_judge_llm(prompt)
        score, reasoning = self._parse_judge_response(raw_response)

        return max(0.0, min(1.0, score)), reasoning, "llm-judge-gemini"

    def _build_judge_prompt(
        self,
        finding: str,
        chunk_texts: list[str],
        evidence_quotes: list[str],
    ) -> str:
        chunks_section = "\n\n".join(
            f"[Chunk {i+1}]\n{text}" for i, text in enumerate(chunk_texts)
        )

        evidence_section = ""
        if evidence_quotes:
            evidence_section = "\n\nClaimed Evidence Quotes:\n" + "\n".join(
                f"- {q}" for q in evidence_quotes
            )

        return (
            "You are a research quality analyst evaluating insight faithfulness.\n"
            "Your task: determine whether the research finding is fully supported by the evidence chunks.\n\n"
            f"Research Finding:\n{finding}\n\n"
            f"Evidence Chunks:{chunks_section}{evidence_section}\n\n"
            "Instructions:\n"
            "1. Read the finding carefully.\n"
            "2. Read every evidence chunk carefully.\n"
            "3. Score on a 0.0–1.0 scale:\n"
            "   - 1.0 = Every claim is directly supported by verbatim evidence\n"
            "   - 0.7 = Mostly supported with minor gaps\n"
            "   - 0.5 = Some claims supported, others unsupported\n"
            "   - 0.3 = Only a few claims supported\n"
            "   - 0.0 = No claims supported\n"
            "4. Provide concise reasoning (1–2 sentences).\n\n"
            'Output JSON: {"score": 0.0, "reasoning": "..."}'
        )

    def _call_judge_llm(self, prompt: str) -> str:
        self._rate_limit()

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            logger.warning("google-genai not available for faithfulness scoring")
            return '{"score": 0.0, "reasoning": "LLM unavailable for scoring."}'

        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            return response.text.strip()
        except Exception as exc:
            logger.warning("LLM judge call failed: %s", exc)
            return '{"score": 0.0, "reasoning": "LLM call failed during scoring."}'

    def _parse_judge_response(self, raw_text: str) -> tuple[float, str]:
        import re

        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.split("```json", 1)[1]
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                score = float(data.get("score", 0.0))
                reasoning = str(data.get("reasoning", "No reasoning provided."))
                return max(0.0, min(1.0, score)), reasoning
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        match = re.search(r'"score"\s*:\s*([0-9.]+)', cleaned)
        if match:
            try:
                score = float(match.group(1))
                return max(0.0, min(1.0, score)), "Parsed from partial response."
            except (TypeError, ValueError):
                pass

        return 0.0, "Failed to parse judge response."
