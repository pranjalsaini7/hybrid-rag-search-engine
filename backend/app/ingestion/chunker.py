"""
Text Chunker — Recursive Character Splitting

KEY DESIGN DECISION:
  Fixed-size splitting destroys sentence context.  We use recursive
  character splitting that tries separators in order:
    paragraph → newline → sentence → word → character
  with a 20 % overlap so boundary context is never lost.

  Default: 1000 chars / 200 overlap.  Use ChunkingExperiment to
  benchmark 256 / 512 / 1000 / 1500 on your actual documents —
  this alone can swing answer quality by 30–40 %.
"""

from __future__ import annotations

from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


def create_chunker(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> RecursiveCharacterTextSplitter:
    """
    Build a recursive splitter with the given (or default) parameters.

    Separator hierarchy:
      1. "\\n\\n"  — paragraph breaks (best split point)
      2. "\\n"    — line breaks
      3. ". "     — sentence endings
      4. " "      — word boundaries
      5. ""       — character-level fallback
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.CHUNK_SIZE,
        chunk_overlap=chunk_overlap or settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
        is_separator_regex=False,
        add_start_index=True,  # tracks char offset in original text
    )


def chunk_documents(
    documents: List[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> List[Document]:
    """
    Split a list of Documents into smaller chunks, preserving metadata.

    Each resulting chunk carries the original metadata plus:
      • chunk_index — position within the parent document
      • chunk_size_config — the chunk_size used (for experiment tracking)
    """
    splitter = create_chunker(chunk_size, chunk_overlap)
    chunks = splitter.split_documents(documents)

    # Enrich metadata with chunk position
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["chunk_size_config"] = chunk_size or settings.CHUNK_SIZE

    return chunks
