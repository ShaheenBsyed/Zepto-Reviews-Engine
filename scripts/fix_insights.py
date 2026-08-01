#!/usr/bin/env python
"""Generate basic extractive insights from retrieval results without LLM calls."""
import json
import re
from pathlib import Path

RETRIEVAL_PATH = Path("outputs/retrieval_results.json")
INSIGHTS_PATH = Path("outputs/insights.json")
QUESTIONS_PATH = Path("config/research_questions.json")


def extract_sentences(text: str, max_sentences: int = 5) -> list[str]:
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    return sentences[:max_sentences]


def generate_extractive_insight(query_entry: dict, chunks: list[dict]) -> dict:
    question_id = query_entry["id"]
    question_label = query_entry["label"]
    question_text = query_entry["question"]

    if not chunks:
        return {
            "research_question_id": question_id,
            "research_question_label": question_label,
            "finding": "Insufficient evidence to generate a meaningful insight.",
            "evidence": [
                {"quote": "No chunks retrieved for this question.", "source_chunk": "N/A"},
                {"quote": "No chunks retrieved for this question.", "source_chunk": "N/A"},
            ],
            "implication": "The corpus may lack relevant content for this research question. Consider revisiting the retrieval query or source filters.",
            "segment": "Unknown",
            "confidence": 0.0,
            "chunk_ids": [],
            "metadata_filter_applied": query_entry.get("metadata_filters", {}),
            "evidence_linked": [],
        }

    top_chunks = chunks[:5]
    all_text = " ".join(c.get("document", "") or c.get("text", "") for c in top_chunks)
    sentences = extract_sentences(all_text, max_sentences=8)

    finding = sentences[0] if sentences else "Reviewers discuss relevant experiences in this area."
    if len(finding) > 200:
        finding = finding[:197] + "..."

    evidence = []
    for c in top_chunks[:3]:
        text = (c.get("document", "") or c.get("text", "")).strip()
        if len(text) > 200:
            text = text[:197] + "..."
        evidence.append({
            "quote": text,
            "source_chunk": c.get("id", "unknown"),
        })

    segment = "Weekly grocery shoppers"
    if "baby" in all_text.lower() or "parent" in all_text.lower():
        segment = "New parents"
    elif "pet" in all_text.lower() or "dog" in all_text.lower() or "cat" in all_text.lower():
        segment = "Pet owners"
    elif "health" in all_text.lower() or "organic" in all_text.lower():
        segment = "Health-conscious shoppers"

    return {
        "research_question_id": question_id,
        "research_question_label": question_label,
        "finding": finding,
        "evidence": evidence,
        "implication": f"Based on review analysis for {question_label.lower()}, consider addressing the patterns identified in customer feedback.",
        "segment": segment,
        "confidence": 0.6,
        "chunk_ids": [c.get("id", "") for c in top_chunks],
        "metadata_filter_applied": query_entry.get("metadata_filters", {}),
        "evidence_linked": [],
    }


def main():
    with open(RETRIEVAL_PATH, "r", encoding="utf-8") as f:
        retrieval_data = json.load(f)

    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions_data = json.load(f)
    questions = questions_data.get("questions", [])

    chunk_map = {}
    for q in retrieval_data.get("queries", []):
        chunk_map[q["question_id"]] = q.get("chunks", [])

    insights = []
    for q in questions:
        qid = q["id"]
        query_entry = {
            "id": qid,
            "label": q["label"],
            "question": q["question"],
            "metadata_filters": q.get("metadata_filters", {}),
        }
        chunks = chunk_map.get(qid, [])
        insight = generate_extractive_insight(query_entry, chunks)
        insights.append(insight)

    report = {
        "pipeline_run_timestamp": retrieval_data.get("pipeline_run_timestamp", ""),
        "phase": "Phase 5: RAG Insight Generation (extractive fallback)",
        "total_questions": len(questions),
        "insights": insights,
        "low_confidence_count": sum(1 for i in insights if i.get("confidence", 0) < 0.7),
        "insufficient_evidence_count": sum(1 for i in insights if i.get("finding", "").startswith("Insufficient")),
    }

    with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(insights)} extractive insights")
    print(f"Saved to {INSIGHTS_PATH}")


if __name__ == "__main__":
    main()
