"""
Hybrid Retriever — Vector + BM25 Weighted Merge

KEY DESIGN DECISION:
  Pure vector search misses exact keyword matches (names, acronyms,
  technical terms).  BM25 catches those.  Combining both with a
  weighted merge (0.7 × vector + 0.3 × BM25) gives noticeably
  better retrieval than either alone.

  We use Reciprocal Rank Fusion (RRF) for merging because it is
  score-agnostic — BM25 scores and cosine similarity live on
  different scales, so raw score averaging would be misleading.

  Weights are configurable via settings.HYBRID_VECTOR_WEIGHT and
  settings.HYBRID_BM25_WEIGHT.

NOTE: LangChain 1.x removed EnsembleRetriever, so we implement
      the weighted RRF merge directly.  This is actually better
      because we have full control over the fusion logic.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import List

from langchain_core.documents import Document

from app.config import settings
from app.retrieval.vector_store import VectorStore
from app.retrieval.bm25_store import BM25Store

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Ensemble retriever combining semantic (vector) and keyword (BM25)
    search with weighted Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
    ) -> None:
        self._vector_store = vector_store
        self._bm25_store = bm25_store

    @staticmethod
    def _reciprocal_rank_fusion(
        result_lists: list[list[Document]],
        weights: list[float],
        k: int = 60,
    ) -> list[Document]:
        """
        Merge multiple ranked result lists using weighted RRF.

        RRF score for document d from retriever i:
            score_i(d) = weight_i / (k + rank_i(d))

        Final score: sum of RRF scores across all retrievers.
        k=60 is the standard constant from the original RRF paper.
        """
        doc_scores: dict[str, float] = defaultdict(float)
        doc_map: dict[str, Document] = {}

        for results, weight in zip(result_lists, weights):
            for rank, doc in enumerate(results, start=1):
                # Use page_content hash as dedup key
                doc_key = hash(doc.page_content)
                rrf_score = weight / (k + rank)
                doc_scores[doc_key] += rrf_score
                # Keep the version with the highest individual score
                if doc_key not in doc_map:
                    doc_map[doc_key] = doc

        # Sort by fused score descending
        sorted_keys = sorted(doc_scores, key=doc_scores.get, reverse=True)
        return [doc_map[key] for key in sorted_keys]

    def retrieve(
        self,
        query: str,
        k: int | None = None,
    ) -> list[Document]:
        """
        Run hybrid retrieval: vector + BM25 with weighted RRF merging.

        Falls back to vector-only if BM25 index is empty.
        """
        k = k or settings.TOP_K_RETRIEVAL

        # Vector search
        vector_results = self._vector_store.similarity_search(query, k=k)

        # BM25 search (may be empty if no docs indexed yet)
        bm25_results = self._bm25_store.search(query, k=k)

        # If BM25 isn't ready, fall back to pure vector search
        if not bm25_results:
            logger.info(
                "BM25 index empty — using vector-only search (%d results).",
                len(vector_results),
            )
            return vector_results[:k]

        # Weighted RRF merge
        merged = self._reciprocal_rank_fusion(
            result_lists=[vector_results, bm25_results],
            weights=[
                settings.HYBRID_VECTOR_WEIGHT,
                settings.HYBRID_BM25_WEIGHT,
            ],
        )

        logger.info(
            "Hybrid search: %d results  (%.0f%% vec + %.0f%% BM25, "
            "vec=%d, bm25=%d)",
            len(merged[:k]),
            settings.HYBRID_VECTOR_WEIGHT * 100,
            settings.HYBRID_BM25_WEIGHT * 100,
            len(vector_results),
            len(bm25_results),
        )
        return merged[:k]
