"""
Application Settings — Central Configuration

All tuneable parameters are defined here and can be overridden via
environment variables or a .env file.  The three most impactful knobs
for answer quality are:

  • CHUNK_SIZE / CHUNK_OVERLAP  — chunking strategy
  • HYBRID_VECTOR_WEIGHT / HYBRID_BM25_WEIGHT — retrieval blend
  • TOP_K_RETRIEVAL / TOP_K_FINAL — reranking budget
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads settings from environment / .env with sensible defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Ollama LLM ──────────────────────────────────────────────────────
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── Embedding model (HuggingFace) ───────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── Cross-encoder reranker ──────────────────────────────────────────
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ── ChromaDB ────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION: str = "research_papers"

    # ── File uploads ────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # ── Chunking strategy ───────────────────────────────────────────────
    #    Recursive character splitting with 20 % overlap.
    #    Test 256 / 512 / 1000 / 1500 on your own corpus.
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # ── Hybrid search weights (must sum to 1.0) ────────────────────────
    HYBRID_VECTOR_WEIGHT: float = 0.7
    HYBRID_BM25_WEIGHT: float = 0.3

    # ── Retrieval budget ────────────────────────────────────────────────
    TOP_K_RETRIEVAL: int = 20   # candidates from hybrid search
    TOP_K_FINAL: int = 5        # after cross-encoder reranking

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/rag_assistant.db"

    @property
    def database_url_async(self) -> str:
        """Helper to ensure PostgreSQL URLs use asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url

    # ── Cloud Deployments (Groq & Pinecone) ─────────────────────────────
    GROQ_API_KEY: str | None = None
    PINECONE_API_KEY: str | None = None
    PINECONE_INDEX_NAME: str = "rag-assistant"

    # ── Derived helpers (not env-configurable) ──────────────────────────
    def ensure_directories(self) -> None:
        """Create data directories if they don't exist."""
        Path(self.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


# Singleton used throughout the app
settings = Settings()
