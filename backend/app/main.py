"""
FastAPI Application — Entry Point

Initializes all services on startup:
  1. Database tables (SQLite)
  2. ChromaDB vector store
  3. BM25 keyword index (rebuilt from ChromaDB)
  4. Cross-encoder reranker
  5. Hybrid retriever
  6. QA chain (Ollama / LLaMA 3)
  7. Ingestion pipeline
  8. Conversational memory
  9. Hallucination guard
  10. RAGAS evaluator

All components are held as module-level singletons accessed by
routers via lazy imports.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.retrieval.vector_store import VectorStore
from app.retrieval.bm25_store import BM25Store
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.reranker import Reranker
from app.chain.qa_chain import QAChain
from app.chain.memory import ConversationMemory
from app.chain.hallucination_guard import HallucinationGuard
from app.ingestion.pipeline import IngestionPipeline
from app.evaluation.ragas_eval import RAGASEvaluator

# ── Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Singletons (populated on startup) ──────────────────────────────────

vector_store: VectorStore = None  # type: ignore[assignment]
bm25_store: BM25Store = None      # type: ignore[assignment]
reranker: Reranker = None          # type: ignore[assignment]
hybrid_retriever: HybridRetriever = None  # type: ignore[assignment]
qa_chain: QAChain = None           # type: ignore[assignment]
pipeline: IngestionPipeline = None  # type: ignore[assignment]
memory: ConversationMemory = None   # type: ignore[assignment]
hallucination_guard: HallucinationGuard = None  # type: ignore[assignment]
evaluator: RAGASEvaluator = None   # type: ignore[assignment]


# ── Lifespan ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, clean up on shutdown."""
    global vector_store, bm25_store, reranker, hybrid_retriever
    global qa_chain, pipeline, memory, hallucination_guard, evaluator

    logger.info("=" * 60)
    logger.info("🚀  RAG Assistant — starting up …")
    logger.info("=" * 60)

    # 1. Ensure data directories exist
    settings.ensure_directories()

    # 2. Initialize database
    await init_db()
    logger.info("✅  Database initialized.")

    # 3. Vector store (ChromaDB + embeddings)
    vector_store = VectorStore()
    _ = vector_store.embeddings  # Trigger model download on first run
    logger.info("✅  Vector store ready  (%d chunks).", vector_store.count)

    # 4. BM25 index — rebuild from ChromaDB contents
    bm25_store = BM25Store()
    existing_docs = vector_store.get_all_documents()
    if existing_docs:
        bm25_store.build_index(existing_docs)
    logger.info("✅  BM25 index ready.")

    # 5. Reranker
    reranker = Reranker()
    _ = reranker.model  # Pre-load
    logger.info("✅  Reranker ready.")

    # 6. Hybrid retriever
    hybrid_retriever = HybridRetriever(vector_store, bm25_store)
    logger.info("✅  Hybrid retriever ready.")

    # 7. QA chain
    qa_chain = QAChain(hybrid_retriever, reranker)
    logger.info("✅  QA chain ready  (model: %s).", settings.OLLAMA_MODEL)

    # 8. Ingestion pipeline (with QA chain for auto-summarization)
    pipeline = IngestionPipeline(vector_store, bm25_store, qa_chain)
    logger.info("✅  Ingestion pipeline ready.")

    # 9. Conversational memory
    memory = ConversationMemory()
    logger.info("✅  Conversational memory ready.")

    # 10. Hallucination guard
    hallucination_guard = HallucinationGuard()
    logger.info("✅  Hallucination guard ready.")

    # 11. RAGAS evaluator
    evaluator = RAGASEvaluator(qa_chain)
    logger.info("✅  RAGAS evaluator ready.")

    logger.info("=" * 60)
    logger.info("🟢  All systems go — ready to accept requests!")
    logger.info("=" * 60)

    yield  # ← App runs here

    logger.info("🔴  Shutting down …")


# ── App ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Research Paper RAG Assistant",
    description=(
        "A production-grade RAG system for querying research papers. "
        "Features hybrid search (vector + BM25), cross-encoder reranking, "
        "auto-summarization, conversational memory, document comparison, "
        "hallucination guard, and streaming responses via Ollama / LLaMA 3."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow public access for deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────

from app.routers import documents, chat, evaluation  # noqa: E402

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(evaluation.router)


# ── Health Check ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Quick health check — confirms the server is running."""
    return {
        "status": "healthy",
        "model": settings.OLLAMA_MODEL,
        "documents": vector_store.count if vector_store else 0,
        "features": [
            "hybrid_search",
            "cross_encoder_reranking",
            "auto_summarization",
            "conversational_memory",
            "follow_up_questions",
            "document_comparison",
            "hallucination_guard",
            "ragas_evaluation",
        ],
    }
