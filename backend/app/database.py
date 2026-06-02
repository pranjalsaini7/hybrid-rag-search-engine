"""
Database — SQLite via SQLAlchemy (async)

Stores document metadata, chat history, and evaluation runs.
The actual vector data lives in ChromaDB; this is for structured metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, Float
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── ORM Base ────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ── Tables ──────────────────────────────────────────────────────────────


class DocumentRecord(Base):
    """Metadata for an ingested document."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    chunk_count = Column(Integer, default=0)
    summary = Column(Text, default="")
    upload_date = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    status = Column(String, default="indexed")


class ChatHistoryRecord(Base):
    """Persisted chat messages for conversational memory."""

    __tablename__ = "chat_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    sources_json = Column(Text, default="[]")
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )


class EvalRunRecord(Base):
    """Persisted evaluation run results."""

    __tablename__ = "eval_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    test_set_name = Column(String, default="default")
    faithfulness = Column(Float, default=0.0)
    answer_relevancy = Column(Float, default=0.0)
    context_precision = Column(Float, default=0.0)
    context_recall = Column(Float, default=0.0)
    per_question_json = Column(Text, default="[]")
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )


# ── Engine & Session Factory ────────────────────────────────────────────

engine = create_async_engine(settings.database_url_async, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables (safe to call repeatedly)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency-injectable session factory for FastAPI."""
    async with async_session() as session:
        yield session
