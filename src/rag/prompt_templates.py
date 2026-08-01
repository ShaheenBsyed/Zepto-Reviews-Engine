SYSTEM_PROMPT = (
    "You are a product research analyst for Zepto, an Indian quick-commerce platform. "
    "Your task is to analyze user feedback and generate structured insights. "
    "CRITICAL RULES:\n"
    "- Every claim in your output MUST be supported by the provided context chunks.\n"
    "- Do NOT draw on your own training data or general knowledge.\n"
    "- Every claim must be traceable to at least one retrieved chunk.\n"
    "- Evidence quotes must be verbatim — do not paraphrase them.\n"
    "- If the retrieved chunks do not contain sufficient evidence, say so explicitly.\n"
    "- The segment must be a concrete user description (life stage, use case, behavior pattern, geography).\n"
    "- Do not produce vague segments like 'all users' or 'most users'."
)

INSIGHT_PROMPT_TEMPLATE = (
    "Research Question: {question}\n\n"
    "Retrieved User Feedback (top {top_k} chunks):\n"
    "{chunks_text}\n\n"
    "Instructions:\n"
    "1. Read all retrieved chunks carefully.\n"
    "2. Generate a one-sentence declarative finding that is directly supported by the evidence.\n"
    "3. Provide at least 2 verbatim quotes from the chunks as evidence. "
    "Each quote must appear exactly as written in the source chunk.\n"
    "4. Explain what this finding means for the product team (implication).\n"
    "5. Identify the specific user segment this applies to (concrete description, not vague).\n"
    "6. Rate confidence from 0.0 (no evidence) to 1.0 (strong evidence).\n\n"
    "Output JSON format:\n"
    "{{\n"
    "  \"finding\": \"...\",\n"
    "  \"evidence\": [\n"
    "    {{\"quote\": \"...\", \"source_chunk\": \"...\"}},\n"
    "    {{\"quote\": \"...\", \"source_chunk\": \"...\"}}\n"
    "  ],\n"
    "  \"implication\": \"...\",\n"
    "  \"segment\": \"...\",\n"
    "  \"confidence\": 0.0\n"
    "}}"
)

FALLBACK_INSIGHT = {
    "finding": "Insufficient evidence to generate a meaningful insight.",
    "evidence": [
        {"quote": "No chunks retrieved for this question.", "source_chunk": "N/A"},
        {"quote": "No chunks retrieved for this question.", "source_chunk": "N/A"},
    ],
    "implication": "The corpus may lack relevant content for this research question. "
                   "Consider revisiting the retrieval query or source filters.",
    "segment": "Unknown",
    "confidence": 0.0,
}