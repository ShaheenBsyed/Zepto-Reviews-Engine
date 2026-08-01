"""
src.rag — RAG insight generation engine (Phase 5).
Modules:
  - retriever.py       : Semantic retrieval with metadata filters and parent diversity
  - insight_engine.py  : Orchestrates retrieval + LLM generation for all 8 research questions
  - query_builder.py   : Loads semantic queries and metadata filters from research_questions.json
  - prompt_templates.py: Structured LLM prompts with JSON schema enforcement
  - insight_schema.py  : Pydantic model for the insight output (finding, evidence, implication, segment)
  - tracer.py          : Links evidence quotes back to source chunk_ids in SQLite
"""
