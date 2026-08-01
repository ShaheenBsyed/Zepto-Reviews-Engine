"""
src/embedding/validation.py
==============================
Retrieval quality validation for Phase 3.

Validates the vector index by running test queries drawn from the
8 research questions and inspecting the top-K results for semantic
relevance.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.embedding.indexer import VectorIndexer
from src.utils.config import settings, load_research_questions
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TOP_K = 5
DEFAULT_NUM_QUERIES = 5


class RetrievalValidator:
    """
    Validates retrieval quality using test queries from research questions.

    For each test query, the validator:
      1. Embeds the query using the same model as the index
      2. Retrieves top-K results from the vector index
      3. Checks that results are non-empty and semantically relevant
    """

    def __init__(
        self,
        indexer: VectorIndexer,
        top_k: int = DEFAULT_TOP_K,
        num_queries: int = DEFAULT_NUM_QUERIES,
    ):
        """
        Initialize the retrieval validator.

        Args:
            indexer: VectorIndexer instance with an existing collection.
            top_k: Number of results to retrieve per query.
            num_queries: Number of research questions to use as test queries.
        """
        self.indexer = indexer
        self.top_k = top_k
        self.num_queries = num_queries

    def _get_test_queries(self) -> List[Dict[str, Any]]:
        """
        Load research questions and extract semantic queries for validation.

        Returns:
            List of dicts with 'id', 'question', 'semantic_query'.
        """
        rq = load_research_questions()
        questions = rq.get("questions", [])

        # Use the first num_questions questions for validation
        selected = questions[: self.num_queries]

        test_queries = []
        for q in selected:
            test_queries.append(
                {
                    "id": q.get("id", ""),
                    "label": q.get("label", ""),
                    "question": q.get("question", ""),
                    "semantic_query": q.get("semantic_query", ""),
                }
            )

        return test_queries

    def validate(
        self,
    ) -> Dict[str, Any]:
        """
        Run retrieval validation for all test queries.

        Returns:
            Dict with validation results per query and overall pass/fail.
        """
        test_queries = self._get_test_queries()
        results: List[Dict[str, Any]] = []
        all_passed = True

        logger.info(
            "Running retrieval validation with %d test queries (top-%d)",
            len(test_queries),
            self.top_k,
        )

        for i, tq in enumerate(test_queries):
            query_text = tq["semantic_query"]
            query_id = tq["id"]
            query_label = tq["label"]

            logger.info(
                "[Query %d/%d] %s: %s",
                i + 1,
                len(test_queries),
                query_id,
                query_text[:80],
            )

            hits = self.indexer.search(
                query_text=query_text,
                n_results=self.top_k,
            )

            passed = len(hits) > 0
            sources: set[str] = set()
            if not passed:
                all_passed = False
                logger.warning(
                    "Query '%s' returned 0 results — possible data gap",
                    query_id,
                )
            else:
                # Check for source diversity
                sources = set(
                    h.get("metadata", {}).get("source", "unknown")
                    for h in hits
                )
                if len(sources) == 1 and len(hits) > 1:
                    logger.info(
                        "All %d results for '%s' come from a single source: %s",
                        len(hits),
                        query_id,
                        next(iter(sources)),
                    )

            results.append(
                {
                    "query_id": query_id,
                    "query_label": query_label,
                    "query_text": query_text,
                    "results_count": len(hits),
                    "passed": passed,
                    "sources": list(sources),
                    "top_results": [
                        {
                            "id": h.get("id", ""),
                            "document_preview": h.get("document", "")[:100],
                            "metadata": h.get("metadata", {}),
                            "distance": h.get("distance"),
                        }
                        for h in hits[:3]
                    ],
                }
            )

        report = {
            "validation_timestamp": __import__(
                "datetime"
            ).datetime.now().isoformat(),
            "total_queries": len(test_queries),
            "queries_passed": sum(1 for r in results if r["passed"]),
            "queries_failed": sum(1 for r in results if not r["passed"]),
            "all_passed": all_passed,
            "top_k": self.top_k,
            "results": results,
        }

        logger.info(
            "Validation complete: %d/%d queries passed",
            report["queries_passed"],
            report["total_queries"],
        )

        return report

    def save_report(
        self,
        report: Dict[str, Any],
        output_path: Optional[str] = None,
    ) -> Path:
        """
        Save the validation report to a JSON file.

        Args:
            report: The validation report dict.
            output_path: Path to save the report. Defaults to
                outputs/retrieval_validation.json.

        Returns:
            Path to the saved report file.
        """
        output_path = Path(
            output_path or settings.outputs_dir / "retrieval_validation.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info("Validation report saved to %s", output_path)
        return output_path


def main() -> Dict[str, Any]:
    """Standalone entry point: run retrieval validation."""
    indexer = VectorIndexer()
    validator = RetrievalValidator(indexer)
    report = validator.validate()
    validator.save_report(report)
    return report


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))