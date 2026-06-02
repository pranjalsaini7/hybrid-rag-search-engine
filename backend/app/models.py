"""
Pydantic Schemas — Request / Response Models

These schemas define the API contract between backend and frontend
(and the CLI harness).  They are intentionally kept separate from
the SQLAlchemy ORM models in database.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Document Schemas ────────────────────────────────────────────────────


class DocumentUploadResponse(BaseModel):
    """Returned after a successful document upload + ingestion."""

    id: str = Field(..., description="Unique document ID (UUID4)")
    filename: str
    file_type: str
    chunk_count: int
    summary: str = Field(
        default="",
        description="Auto-generated 3-line semantic summary",
    )
    status: str = Field(default="indexed", description="Processing status")


class DocumentInfo(BaseModel):
    """Full metadata for a stored document."""

    id: str
    filename: str
    file_type: str
    chunk_count: int
    summary: str = ""
    upload_date: datetime
    status: str = "indexed"


class DocumentListResponse(BaseModel):
    """Wrapper for listing all documents."""

    documents: list[DocumentInfo]
    total: int


# ── Chat Schemas ────────────────────────────────────────────────────────


class SourceReference(BaseModel):
    """A single cited source chunk returned alongside an answer."""

    document_name: str
    page_number: int | None = None
    chunk_text: str
    relevance_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Cross-encoder relevance score (0–1)",
    )


class ChatRequest(BaseModel):
    """Incoming chat message (used by REST fallback; WS uses raw JSON)."""

    query: str
    session_id: str = "default"
    use_decomposition: bool = False


class ChatResponse(BaseModel):
    """Full answer returned after generation completes."""

    answer: str
    sources: list[SourceReference] = []
    follow_up_questions: list[str] = Field(
        default_factory=list,
        description="2–3 smart follow-up questions",
    )
    guard_result: dict | None = Field(
        default=None,
        description="Hallucination guard result: {confidence, issues}",
    )


class ChatMessage(BaseModel):
    """A single message in the chat history."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    sources: list[SourceReference] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Document Comparison ────────────────────────────────────────────────


class CompareRequest(BaseModel):
    """Compare two documents regarding a specific question."""

    query: str
    doc_a_id: str = Field(..., description="First document ID")
    doc_b_id: str = Field(..., description="Second document ID")


# ── Streaming Token (WebSocket) ────────────────────────────────────────


class StreamToken(BaseModel):
    """A single streamed token sent over the WebSocket."""

    type: str = Field(
        ...,
        description="'token' | 'sources' | 'follow_up' | 'guard' | 'done' | 'error'",
    )
    content: str | None = None
    data: dict | list | None = None


# ── Evaluation Schemas ─────────────────────────────────────────────────


class EvalQuestion(BaseModel):
    """A single question in a gold test set."""

    question: str
    ground_truth: str = ""
    context_ids: list[str] = Field(default_factory=list)


class EvalTestSet(BaseModel):
    """Gold test set for RAGAS evaluation."""

    name: str = "default"
    questions: list[EvalQuestion] = []


class EvalMetrics(BaseModel):
    """RAGAS evaluation metrics."""

    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0


class EvalRunResult(BaseModel):
    """Result of an evaluation run."""

    id: str
    timestamp: datetime
    metrics: EvalMetrics
    per_question: list[dict] = Field(default_factory=list)
    test_set_name: str = "default"


class EvalRunListResponse(BaseModel):
    """List of evaluation runs."""

    runs: list[EvalRunResult] = []
    total: int = 0
