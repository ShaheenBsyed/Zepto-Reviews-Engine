import json
from pathlib import Path
from typing import Any, Optional


DEFAULT_QUESTIONS_PATH = Path("config/research_questions.json")


def load_research_questions(path: str = str(DEFAULT_QUESTIONS_PATH)) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Research questions file not found: {path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


def build_queries(
    questions: Optional[list[dict[str, Any]]] = None,
    path: str = str(DEFAULT_QUESTIONS_PATH),
) -> list[dict[str, Any]]:
    if questions is None:
        questions = load_research_questions(path)
    return [
        {
            "id": q["id"],
            "label": q["label"],
            "question": q["question"],
            "semantic_query": q["semantic_query"],
            "metadata_filters": q.get("metadata_filters", {}),
            "relevance_keywords": q.get("relevance_keywords", []),
        }
        for q in questions
    ]


def get_metadata_filter(query_entry: dict[str, Any]) -> Optional[dict[str, Any]]:
    filters = query_entry.get("metadata_filters", {})
    if not filters:
        return None
    result = {}
    if "rating_lte" in filters:
        result["rating"] = {"$lte": filters["rating_lte"]}
    if "source" in filters:
        result["source"] = filters["source"]
    if "app" in filters:
        result["app"] = filters["app"]
    return result if result else None