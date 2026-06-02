"""
BM25 Store — Keyword-Based Retrieval Index

BM25 excels at exact keyword matches: author names, acronyms, technical
terms that embedding models sometimes miss.  Combined with vector search
in the hybrid retriever, it gives noticeably better recall.

The index is held in memory and rebuilt from ChromaDB on server startup.
"""

from __future__ import annotations

import logging
from typing import List

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from app.config import settings

logger = logging.getLogger(__name__)


class BM25Store:
    """In-memory BM25 index over the document corpus."""

    def __init__(self) -> None:
        self._retriever: BM25Retriever | None = None
        self._documents: List[Document] = []

    @property
    def is_ready(self) -> bool:
        return self._retriever is not None and len(self._documents) > 0

    def build_index(self, documents: List[Document]) -> None:
        """Build (or rebuild) the BM25 index from a full document list."""
        if not documents:
            logger.warning("BM25: No documents to index.")
            self._retriever = None
            self._documents = []
            return

        self._documents = list(documents)
        self._retriever = BM25Retriever.from_documents(
            self._documents,
            k=settings.TOP_K_RETRIEVAL,
        )
        logger.info("BM25 index built with %d documents.", len(self._documents))

    def add_documents(self, documents: List[Document]) -> None:
        """Add new documents and rebuild the index."""
        self._documents.extend(documents)
        self._retriever = BM25Retriever.from_documents(
            self._documents,
            k=settings.TOP_K_RETRIEVAL,
        )
        logger.info(
            "BM25 index updated — now %d documents total.",
            len(self._documents),
        )

    def remove_by_source(self, source_filename: str) -> None:
        """Remove documents by source and rebuild."""
        before = len(self._documents)
        self._documents = [
            doc
            for doc in self._documents
            if doc.metadata.get("source") != source_filename
        ]
        removed = before - len(self._documents)
        if removed > 0:
            self.build_index(self._documents)
            logger.info(
                "BM25: Removed %d chunks for '%s'.", removed, source_filename
            )

    def search(self, query: str, k: int | None = None) -> List[Document]:
        """Keyword search.  Returns empty list if index is not built."""
        if not self.is_ready:
            return []
        self._retriever.k = k or settings.TOP_K_RETRIEVAL
        return self._retriever.invoke(query)

    def as_retriever(self, k: int | None = None) -> BM25Retriever | None:
        """Return the underlying LangChain retriever (or None)."""
        if self._retriever is not None:
            self._retriever.k = k or settings.TOP_K_RETRIEVAL
        return self._retriever
