"""
src/rag/insight_engine.py
==========================
Phase 5: RAG Insight Generation Engine.

Orchestrates the complete Phase 5 workflow:
  1. Load research questions and semantic queries
  2. Retrieve top-K relevant chunks from the vector index
  3. Format chunks as grounding context for the LLM
  4. Generate structured insights with evidence, implication, and segment
  5. Verify evidence grounding and link back to source chunk IDs
  6. Save insights report and retrieval results

Exit criteria (from implementationplan.md):
  - >= 8 insights, one per research question
  - Each insight linked to at least 2 source chunk IDs
  - Evidence quotes verified as verbatim from retrieved chunks
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_QUESTIONS_PATH = "config/research_questions.json"
DEFAULT_OUTPUT_DIR = "outputs"
DEFAULT_TOP_K = 10
DEFAULT_EMBEDDINGS_PATH = "data/embeddings/chroma"

MAX_RPM = 15
COOLDOWN_SECONDS = 60.0 / MAX_RPM


class RAGInsightEngine:
    def __init__(
        self,
        questions_path: str = DEFAULT_QUESTIONS_PATH,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        top_k: int = DEFAULT_TOP_K,
        embeddings_path: str = DEFAULT_EMBEDDINGS_PATH,
    ) -> None:
        self.questions_path = questions_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.top_k = top_k
        self.embeddings_path = embeddings_path
        self.queries = self._load_queries()
        self._insights: list[dict[str, Any]] = []
        self._retrieved_chunks: dict[str, list[dict[str, Any]]] = {}
        self._last_call_time: float = 0.0

    def _load_queries(self) -> list[dict[str, Any]]:
        from src.rag.query_builder import build_queries

        return build_queries(path=self.questions_path)

    def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < COOLDOWN_SECONDS:
            sleep_time = COOLDOWN_SECONDS - elapsed
            logger.debug("Rate limiting: sleeping %.1f seconds", sleep_time)
            time.sleep(sleep_time)
        self._last_call_time = time.time()

    def run_retrieval(self, save: bool = True) -> dict[str, Any]:
        """
        Run semantic retrieval for all research questions.

        Returns:
            Dict with retrieval results including chunks per question.
        """
        from src.rag.retriever import RAGRetriever

        retriever = RAGRetriever(top_k=self.top_k)
        results = retriever.retrieve_all(self.queries)

        if save:
            retriever.save_results(results)

        return results

    def load_retrieved_chunks(self, retrieval_output: Optional[dict[str, Any]] = None) -> None:
        if retrieval_output is not None:
            for q in retrieval_output.get("queries", []):
                self._retrieved_chunks[q["question_id"]] = q.get("chunks", [])
            return
        retrieval_path = Path(self.output_dir) / "retrieval_results.json"
        if retrieval_path.exists():
            with open(retrieval_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for q in data.get("queries", []):
                self._retrieved_chunks[q["question_id"]] = q.get("chunks", [])
            logger.info("Loaded retrieved chunks for %d questions", len(self._retrieved_chunks))
        else:
            logger.warning("No retrieval results found at %s", retrieval_path)

    def generate_insight(self, query_entry: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
        from src.rag.prompt_templates import INSIGHT_PROMPT_TEMPLATE, FALLBACK_INSIGHT
        from src.rag.tracer import verify_evidence_grounding

        question_id = query_entry["id"]
        question_label = query_entry["label"]
        question_text = query_entry["question"]
        metadata_filter = query_entry.get("metadata_filters", {})

        if not chunks:
            logger.warning("No chunks retrieved for %s: %s", question_id, question_label)
            result = {
                **FALLBACK_INSIGHT,
                "research_question_id": question_id,
                "research_question_label": question_label,
                "chunk_ids": [],
                "metadata_filter_applied": metadata_filter,
                "evidence_linked": [],
            }
            self._insights.append(result)
            return result

        chunks_text = self._format_chunks_for_prompt(chunks)
        prompt = INSIGHT_PROMPT_TEMPLATE.format(
            question=question_text,
            top_k=len(chunks),
            chunks_text=chunks_text,
        )

        raw_insight = self._call_llm(prompt)
        insight = self._parse_insight(raw_insight)
        insight["research_question_id"] = question_id
        insight["research_question_label"] = question_label
        insight["chunk_ids"] = [c.get("id", "") for c in chunks]
        insight["metadata_filter_applied"] = metadata_filter

        evidence_quotes = [e.get("quote", "") for e in insight.get("evidence", [])]
        linked_evidence = verify_evidence_grounding(evidence_quotes, chunks)
        insight["evidence_linked"] = linked_evidence

        self._insights.append(insight)
        return insight

    def _format_chunks_for_prompt(self, chunks: list[dict[str, Any]]) -> str:
        lines = []
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("document", "") or chunk.get("text", "") or ""
            source = chunk.get("metadata", {}).get("source", "unknown")
            app = chunk.get("metadata", {}).get("app", "unknown")
            rating = chunk.get("metadata", {}).get("rating", "N/A")
            lines.append(
                f"--- Chunk {i} (source={source}, app={app}, rating={rating}) ---\n"
                f"{text[:500]}"
            )
        return "\n\n".join(lines)

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        from src.rag.prompt_templates import FALLBACK_INSIGHT

        self._rate_limit()

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            logger.warning("google-genai not available")
            return FALLBACK_INSIGHT

        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw_text = response.text.strip()
        except Exception as exc:
            logger.warning("LLM call failed for insight generation: %s", exc)
            return FALLBACK_INSIGHT

        return self._parse_llm_json(raw_text, fallback=FALLBACK_INSIGHT)

    def _parse_llm_json(self, raw_text: str, fallback: dict[str, Any]) -> dict[str, Any]:
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
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass

        logger.warning("Failed to parse LLM response as JSON: %s", raw_text[:200])
        return fallback

    def _parse_insight(self, raw: dict[str, Any]) -> dict[str, Any]:
        finding = str(raw.get("finding", "")).strip()
        evidence = raw.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [evidence] if evidence else []

        parsed_evidence = []
        for e in evidence:
            if isinstance(e, dict):
                parsed_evidence.append({
                    "quote": str(e.get("quote", "")).strip(),
                    "source_chunk": str(e.get("source_chunk", "")).strip(),
                })
            elif isinstance(e, str):
                parsed_evidence.append({"quote": e.strip(), "source_chunk": ""})

        if len(parsed_evidence) < 2:
            parsed_evidence.extend(
                [{"quote": "", "source_chunk": ""}] * (2 - len(parsed_evidence))
            )

        try:
            confidence = float(raw.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        return {
            "finding": finding or "Insufficient evidence to generate a meaningful insight.",
            "evidence": parsed_evidence[:5],
            "implication": str(raw.get("implication", "")).strip(),
            "segment": str(raw.get("segment", "Unknown")).strip(),
            "confidence": confidence,
        }

    def run(self, retrieval_output: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        logger.info("Starting Phase 5: RAG Insight Generation")
        self._retrieved_chunks = {}
        self.load_retrieved_chunks(retrieval_output)

        if not self._retrieved_chunks:
            logger.info("No retrieval results loaded. Running retrieval first.")
            retrieval_output = self.run_retrieval(save=True)
            self.load_retrieved_chunks(retrieval_output)

        for query_entry in self.queries:
            qid = query_entry["id"]
            logger.info("Processing %s: %s", qid, query_entry["label"])
            chunks = self._retrieved_chunks.get(qid, [])
            self.generate_insight(query_entry, chunks)

        report = self._build_report()
        report_path = self.output_dir / "insights.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Insights report saved to %s", report_path)
        return report

    def _build_report(self) -> dict[str, Any]:
        total = len(self.queries)
        low_confidence = sum(1 for i in self._insights if i.get("confidence", 0) < 0.7)
        insufficient = sum(
            1
            for i in self._insights
            if i.get("finding", "").startswith("Insufficient")
        )

        return {
            "pipeline_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "Phase 5: RAG Insight Generation",
            "total_questions": total,
            "insights": self._insights,
            "low_confidence_count": low_confidence,
            "insufficient_evidence_count": insufficient,
        }


def main() -> dict[str, Any]:
    engine = RAGInsightEngine()
    return engine.run()


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
