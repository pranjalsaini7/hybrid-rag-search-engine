"""
Vector Store — Dual-Mode (ChromaDB / Pinecone) Wrapper

Provides a persistent vector store backed by ChromaDB (locally) or Pinecone (in the cloud)
with HuggingFace sentence-transformer embeddings.
"""

from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Thin wrapper around Chroma/Pinecone with lifecycle management."""

    def __init__(self) -> None:
        self._embeddings: HuggingFaceEmbeddings | None = None
        self._store = None

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Lazy-load the embedding model (heavy first-time download)."""
        if self._embeddings is None:
            logger.info(
                "Loading embedding model: %s …", settings.EMBEDDING_MODEL
            )
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("Embedding model loaded.")
        return self._embeddings

    @property
    def store(self):
        """Lazy-load the vector store (ChromaDB locally, Pinecone in cloud)."""
        if self._store is None:
            if settings.PINECONE_API_KEY:
                logger.info("Initializing Pinecone Vector Store...")
                from langchain_pinecone import PineconeVectorStore
                self._store = PineconeVectorStore(
                    index_name=settings.PINECONE_INDEX_NAME,
                    embedding=self.embeddings,
                    pinecone_api_key=settings.PINECONE_API_KEY
                )
                logger.info(
                    "Pinecone loaded — index '%s'",
                    settings.PINECONE_INDEX_NAME
                )
            else:
                logger.info("Initializing ChromaDB Vector Store...")
                from langchain_chroma import Chroma
                self._store = Chroma(
                    collection_name=settings.CHROMA_COLLECTION,
                    embedding_function=self.embeddings,
                    persist_directory=settings.CHROMA_PERSIST_DIR,
                )
                logger.info(
                    "ChromaDB loaded — collection '%s', persist_dir '%s'",
                    settings.CHROMA_COLLECTION,
                    settings.CHROMA_PERSIST_DIR,
                )
        return self._store

    # ── Public API ──────────────────────────────────────────────────────

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Embed and store documents. Returns the assigned IDs."""
        ids = self.store.add_documents(documents)
        logger.info("Added %d chunks to Vector Store.", len(ids))
        return ids

    def similarity_search(
        self, query: str, k: int | None = None
    ) -> List[Document]:
        """Return the top-k most similar documents to *query*."""
        k = k or settings.TOP_K_RETRIEVAL
        return self.store.similarity_search(query, k=k)

    def as_retriever(self, k: int | None = None):
        """Return a LangChain Retriever interface for the store."""
        k = k or settings.TOP_K_RETRIEVAL
        return self.store.as_retriever(search_kwargs={"k": k})

    def delete_by_source(self, source_filename: str) -> None:
        """Remove all chunks belonging to a given source document."""
        if settings.PINECONE_API_KEY:
            self.store.delete(filter={"source": source_filename})
            logger.info("Deleted chunks from Pinecone for source '%s'.", source_filename)
        else:
            collection = self.store._collection
            results = collection.get(
                where={"source": source_filename},
            )
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                logger.info(
                    "Deleted %d chunks for source '%s'.",
                    len(results["ids"]),
                    source_filename,
                )

    def get_all_documents(self) -> List[Document]:
        """Retrieve every document from the collection (for BM25 rebuild)."""
        if settings.PINECONE_API_KEY:
            # Pinecone does not support fetching all vectors without querying,
            # so we perform a similarity search with a zero vector and large k.
            zero_vector = [0.0] * 384
            return self.store.similarity_search_by_vector(zero_vector, k=10000)
        else:
            collection = self.store._collection
            data = collection.get(include=["documents", "metadatas"])
            docs = []
            for text, meta in zip(data["documents"], data["metadatas"]):
                docs.append(Document(page_content=text, metadata=meta or {}))
            return docs

    @property
    def count(self) -> int:
        """Number of chunks currently stored."""
        if settings.PINECONE_API_KEY:
            try:
                from pinecone import Pinecone
                pc = Pinecone(api_key=settings.PINECONE_API_KEY)
                idx = pc.Index(settings.PINECONE_INDEX_NAME)
                stats = idx.describe_index_stats()
                return stats.total_vector_count
            except Exception as e:
                logger.error("Failed to fetch Pinecone vector count: %s", e)
                return 0
        else:
            return self.store._collection.count()
