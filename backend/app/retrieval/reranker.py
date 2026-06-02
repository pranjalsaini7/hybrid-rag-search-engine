"""
Cross-Encoder Reranker

After hybrid retrieval returns ~20 candidates, the cross-encoder
reranks them by computing a deep relevance score for each
(query, chunk) pair.  Only the top-5 survive.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  • ~22 M params, ~250 MB RAM, runs on CPU
  • ~50 ms for a batch of 20 pairs — negligible latency
  • Captures negation, coreference, and deep semantic overlap
    that bi-encoders miss
"""

from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document

from app.config import settings

logger = logging.getLogger(__name__)


class Reranker:
    """Rerank retrieved documents using a cross-encoder model."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.RERANKER_MODEL
        self._model = None

    @property
    def model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            if settings.DISABLE_RERANKER:
                raise RuntimeError("Reranker is disabled in configuration.")
            logger.info("Loading reranker: %s …", self._model_name)
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)
            logger.info("Reranker loaded.")
        return self._model

    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_k: int | None = None,
    ) -> List[Document]:
        """
        Score and sort documents by relevance to *query*.

        Returns the top-k documents with a ``relevance_score``
        field added to their metadata.
        """
        top_k = top_k or settings.TOP_K_FINAL

        if not documents:
            return []

        if settings.DISABLE_RERANKER:
            logger.info("Reranker is disabled. Bypassing reranking step.")
            # Ensure relevance_score is present in metadata to prevent any frontend or guard crashes
            for doc in documents:
                if "relevance_score" not in doc.metadata:
                    doc.metadata["relevance_score"] = 1.0
            return documents[:top_k]

        # Build (query, chunk) pairs for the cross-encoder
        pairs = [(query, doc.page_content) for doc in documents]
        scores = self.model.predict(pairs)

        # Attach scores and sort descending
        for doc, score in zip(documents, scores):
            doc.metadata["relevance_score"] = float(score)

        ranked = sorted(
            documents,
            key=lambda d: d.metadata["relevance_score"],
            reverse=True,
        )

        logger.info(
            "Reranked %d → top %d  (best score: %.3f)",
            len(documents),
            top_k,
            ranked[0].metadata["relevance_score"] if ranked else 0,
        )

        return ranked[:top_k]
