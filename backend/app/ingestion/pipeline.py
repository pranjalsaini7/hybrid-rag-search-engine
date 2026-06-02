"""
Ingestion Pipeline — Orchestrates the Full Upload Flow

  upload file → detect type → load → chunk → embed → store
               → generate summary → record in DB → return response

This is the entry point that ties together loaders, chunker,
vector store, BM25 index, and the LLM summarizer.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import DocumentRecord, async_session
from app.ingestion.chunker import chunk_documents
from app.ingestion.loader import load_document, SUPPORTED_EXTENSIONS
from app.models import DocumentInfo, DocumentUploadResponse
from app.retrieval.vector_store import VectorStore
from app.retrieval.bm25_store import BM25Store

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    End-to-end document ingestion: file → chunks → vectors → summary.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        qa_chain=None,  # Optional — set after QAChain is initialized
    ) -> None:
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._qa_chain = qa_chain

    def set_qa_chain(self, qa_chain) -> None:
        """Late-bind the QA chain (avoids circular dependency)."""
        self._qa_chain = qa_chain

    async def ingest(
        self,
        file_path: str | Path,
        original_filename: str | None = None,
    ) -> DocumentUploadResponse:
        """
        Full ingestion pipeline for a single document.

        Steps:
          1. Copy to uploads directory
          2. Load and extract text
          3. Chunk with recursive splitting (20 % overlap)
          4. Embed and store in ChromaDB
          5. Add to BM25 in-memory index
          6. Auto-generate 3-line semantic summary (via LLM)
          7. Record metadata in SQLite
          8. Return structured response with summary
        """
        file_path = Path(file_path)
        original_filename = original_filename or file_path.name
        doc_id = str(uuid.uuid4())
        ext = file_path.suffix.lower()

        # Validate file type
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        # ── Step 1: Copy to uploads directory ───────────────────────────
        settings.ensure_directories()
        dest = Path(settings.UPLOAD_DIR) / f"{doc_id}{ext}"
        shutil.copy2(str(file_path), str(dest))
        logger.info("Saved upload: %s → %s", original_filename, dest)

        # ── Step 2: Load document ───────────────────────────────────────
        raw_docs = load_document(dest)
        if not raw_docs:
            raise ValueError(f"No text could be extracted from '{original_filename}'.")

        # Override source metadata: use original filename, not UUID on disk
        for doc in raw_docs:
            doc.metadata["source"] = original_filename

        logger.info(
            "Loaded %d page(s) from '%s'.", len(raw_docs), original_filename
        )

        # ── Step 3: Chunk ───────────────────────────────────────────────
        chunks = chunk_documents(raw_docs)
        logger.info(
            "Split into %d chunks  (size=%d, overlap=%d).",
            len(chunks),
            settings.CHUNK_SIZE,
            settings.CHUNK_OVERLAP,
        )

        # Ensure every chunk has the document ID and correct source
        for chunk in chunks:
            chunk.metadata["doc_id"] = doc_id
            chunk.metadata["source"] = original_filename

        # ── Step 4: Embed + store in ChromaDB ───────────────────────────
        self._vector_store.add_documents(chunks)

        # ── Step 5: Add to BM25 index ───────────────────────────────────
        self._bm25_store.add_documents(chunks)

        # ── Step 6: Generate summary ────────────────────────────────────
        summary = ""
        if self._qa_chain is not None:
            try:
                # Concatenate the first few chunks for summarization
                sample_text = "\n\n".join(
                    c.page_content for c in chunks[:5]
                )
                summary = await self._qa_chain.summarize_document(sample_text)
                logger.info("Generated summary for '%s'.", original_filename)
            except Exception as e:
                logger.warning("Summary generation failed: %s", e)
                summary = "Summary pending — document indexed successfully."
        else:
            summary = "Summary pending — LLM not available."

        # ── Step 7: Record in SQLite ────────────────────────────────────
        async with async_session() as session:
            record = DocumentRecord(
                id=doc_id,
                filename=original_filename,
                file_path=str(dest),
                file_type=ext.lstrip("."),
                chunk_count=len(chunks),
                summary=summary,
                upload_date=datetime.now(timezone.utc),
                status="indexed",
            )
            session.add(record)
            await session.commit()

        logger.info(
            "✅ Ingestion complete: '%s' → %d chunks, id=%s",
            original_filename,
            len(chunks),
            doc_id,
        )

        return DocumentUploadResponse(
            id=doc_id,
            filename=original_filename,
            file_type=ext.lstrip("."),
            chunk_count=len(chunks),
            summary=summary,
            status="indexed",
        )

    # ── Document listing & deletion ─────────────────────────────────────

    async def list_documents(self) -> list[DocumentInfo]:
        """Retrieve all document metadata from SQLite."""
        async with async_session() as session:
            result = await session.execute(
                select(DocumentRecord).order_by(DocumentRecord.upload_date.desc())
            )
            records = result.scalars().all()
            return [
                DocumentInfo(
                    id=r.id,
                    filename=r.filename,
                    file_type=r.file_type,
                    chunk_count=r.chunk_count,
                    summary=r.summary or "",
                    upload_date=r.upload_date,
                    status=r.status,
                )
                for r in records
            ]

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from all stores (ChromaDB, BM25, SQLite, disk)."""
        async with async_session() as session:
            result = await session.execute(
                select(DocumentRecord).where(DocumentRecord.id == doc_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                return False

            filename = record.filename
            file_path = record.file_path

            # Remove from ChromaDB
            self._vector_store.delete_by_source(filename)

            # Remove from BM25
            self._bm25_store.remove_by_source(filename)

            # Remove from disk
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Could not delete file %s: %s", file_path, e)

            # Remove from SQLite
            await session.delete(record)
            await session.commit()

            logger.info("🗑️ Deleted document: '%s' (id=%s)", filename, doc_id)
            return True

    async def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """Get a single document's metadata."""
        async with async_session() as session:
            result = await session.execute(
                select(DocumentRecord).where(DocumentRecord.id == doc_id)
            )
            r = result.scalar_one_or_none()
            if r is None:
                return None
            return DocumentInfo(
                id=r.id,
                filename=r.filename,
                file_type=r.file_type,
                chunk_count=r.chunk_count,
                summary=r.summary or "",
                upload_date=r.upload_date,
                status=r.status,
            )
