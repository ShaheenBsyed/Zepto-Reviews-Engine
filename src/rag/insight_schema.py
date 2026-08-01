from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional


class InsightEvidence(BaseModel):
    quote: str = Field(..., min_length=1, description="Verbatim quote from a retrieved chunk")
    chunk_id: str = Field(..., description="Source chunk ID linking back to SQLite store")
    source: Optional[str] = Field(None, description="Source tag of the parent record")


class Insight(BaseModel):
    research_question_id: str = Field(..., description="ID of the research question this insight answers")
    research_question_label: str = Field(..., description="Label of the research question")
    finding: str = Field(..., min_length=10, description="One-sentence declarative claim supported by evidence")
    evidence: List[InsightEvidence] = Field(..., min_length=2, description="At least 2 verbatim quotes from retrieved chunks")
    implication: str = Field(..., min_length=10, description="What this finding means for the product team")
    segment: str = Field(..., min_length=3, description="Concrete user segment this applies to")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for this insight")
    chunk_ids: List[str] = Field(default_factory=list, description="All chunk IDs retrieved for this question")
    metadata_filter_applied: Optional[dict] = Field(None, description="Metadata filter used during retrieval")


class InsightReport(BaseModel):
    pipeline_run_timestamp: str = Field(..., description="ISO 8601 timestamp of pipeline run")
    phase: str = Field(default="Phase 5: RAG Insight Generation")
    total_questions: int = Field(..., description="Total number of research questions processed")
    insights: List[Insight] = Field(..., description="Generated insights, one per research question")
    low_confidence_count: int = Field(default=0, description="Number of insights marked low-confidence")
    insufficient_evidence_count: int = Field(default=0, description="Number of questions with insufficient evidence")