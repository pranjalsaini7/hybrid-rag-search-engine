"""
Documents Router — Upload, List, Delete, Get

REST endpoints for document management.  The actual ingestion work
is delegated to the IngestionPipeline singleton.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ingestion.loader import SUPPORTED_EXTENSIONS
from app.models import DocumentInfo, DocumentListResponse, DocumentUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_pipeline():
    """Import lazily to avoid circular imports at module load time."""
    from app.main import pipeline
    return pipeline


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a single document (PDF, DOCX, or TXT).

    The file is ingested immediately: loaded → chunked → embedded →
    summarized → stored.  Returns the document ID, chunk count, and
    auto-generated summary.
    """
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    # Save to a temp file, then let the pipeline copy it to uploads/
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        pipeline = _get_pipeline()
        result = await pipeline.ingest(
            file_path=tmp_path,
            original_filename=file.filename,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ingestion failed for '%s'", file.filename)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


@router.get("/", response_model=DocumentListResponse)
async def list_documents():
    """List all ingested documents with metadata and summaries."""
    pipeline = _get_pipeline()
    docs = await pipeline.list_documents()
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get("/{doc_id}", response_model=DocumentInfo)
async def get_document(doc_id: str):
    """Get metadata for a single document."""
    pipeline = _get_pipeline()
    doc = await pipeline.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """
    Delete a document from all stores (ChromaDB, BM25, SQLite, disk).
    """
    pipeline = _get_pipeline()
    deleted = await pipeline.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "deleted", "id": doc_id}
