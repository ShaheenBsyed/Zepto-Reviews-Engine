from typing import Any, Optional


def tracer_link_evidence(
    finding: str,
    evidence_quotes: list[str],
    retrieved_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    linked_evidence = []
    for quote in evidence_quotes:
        matched_chunk = _find_chunk_for_quote(quote, retrieved_chunks)
        linked_evidence.append(
            {
                "quote": quote,
                "chunk_id": matched_chunk.get("id", "unknown") if matched_chunk else "unknown",
                "source": matched_chunk.get("metadata", {}).get("source", "unknown")
                if matched_chunk
                else "unknown",
                "app": matched_chunk.get("metadata", {}).get("app", "unknown")
                if matched_chunk
                else "unknown",
                "rating": matched_chunk.get("metadata", {}).get("rating")
                if matched_chunk
                else None,
            }
        )
    return linked_evidence


def _find_chunk_for_quote(quote: str, chunks: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    for chunk in chunks:
        chunk_text = chunk.get("text", "") or chunk.get("document", "") or ""
        if quote in chunk_text:
            return chunk
        if quote.strip('"') in chunk_text:
            return chunk
    for chunk in chunks:
        chunk_text = chunk.get("text", "") or chunk.get("document", "") or ""
        if len(quote) >= 10 and quote[:10] in chunk_text:
            return chunk
    return None


def verify_evidence_grounding(
    evidence_quotes: list[str], retrieved_chunks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    results = []
    for quote in evidence_quotes:
        found = False
        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "") or chunk.get("document", "") or ""
            if quote in chunk_text:
                found = True
                break
            if quote.strip('"') in chunk_text:
                found = True
                break
        results.append({
            "quote": quote,
            "grounded": found,
            "source_chunk_id": matched_chunk.get("id", "unknown") if matched_chunk else "unknown",
        })
    return results