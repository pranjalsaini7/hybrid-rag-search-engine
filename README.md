# 📚 Research Paper RAG Assistant

A **production-grade Retrieval-Augmented Generation** system for querying research papers. Upload PDFs and ask cross-paper questions — powered by **hybrid BM25+vector search**, **cross-encoder reranking**, **streaming WebSocket chat**, and a **RAGAS evaluation dashboard**.

> **Dual-Mode** — Runs 100% locally with Ollama, or deploys to the cloud with Groq + Pinecone.

[![Live Demo](https://img.shields.io/badge/🔗_Live_Demo-Render-blue)](https://hybrid-rag-search-engine.onrender.com)

---

## ✨ Features

### Core RAG Pipeline
- **Hybrid Search** — 70% vector (semantic) + 30% BM25 (keyword) with Reciprocal Rank Fusion
- **Cross-Encoder Reranking** — ms-marco-MiniLM reranks top-20 candidates to top-5
- **Streaming Responses** — Token-by-token generation via WebSocket
- **Source Citations** — Every answer cites specific papers with page numbers

### Smart Features
- **Auto-Summarization** — 3-line semantic summary generated on upload
- **Follow-up Suggestions** — 2-3 smart follow-up questions after each answer
- **Document Comparison** — Compare what two papers say about the same topic
- **Conversational Memory** — Remembers last 10 turns per session
- **Hallucination Guard** — Self-verification with confidence badges (🟢/🟡/🔴)

### Evaluation
- **RAGAS Metrics** — Faithfulness, Answer Relevancy, Context Precision, Context Recall
- **LLM-as-Judge** — Uses Ollama locally (zero cost) or Groq in the cloud
- **Historical Tracking** — Compare evaluation runs over time

### Premium Web UI
- **Warm academic theme** with terracotta/peach accents and glassmorphism
- **Light & Dark mode** toggle with smooth transitions
- **Drag-and-drop** document upload with real-time progress bars
- **Real-time streaming** chat with typing indicators
- **Source panel** with relevance score bars and clickable citation badges
- **Evaluation dashboard** with score cards and historical charts
- **Notification system** and **profile dropdown** with session management

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────────────────────────────────────┐
│   Frontend   │     │              FastAPI Backend                 │
│  (React/Vite)│────▶│                                              │
│              │ WS  │  ┌─────────┐  ┌──────────┐  ┌────────────┐ │
│  localhost:  │────▶│  │Ingestion│  │ Hybrid   │  │ QA Chain   │ │
│    5173      │     │  │Pipeline │  │Retriever │  │(Ollama/Groq│ │
└──────────────┘     │  └────┬────┘  └────┬─────┘  └─────┬──────┘ │
                     │       │            │               │        │
                     │  ┌────▼────┐  ┌────▼─────┐  ┌─────▼──────┐ │
                     │  │ChromaDB │  │  BM25    │  │  Reranker  │ │
                     │  │/Pinecone│  │  Index   │  │(CrossEnc.) │ │
                     │  └─────────┘  └──────────┘  └────────────┘ │
                     └──────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Local)

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** and npm
- **Ollama** with `llama3` model pulled

### 1. Start Ollama
```bash
ollama serve
ollama pull llama3
```

### 2. Start the Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Open in Browser
Navigate to **http://localhost:5173**

---

## 🐳 Docker Deployment

If you have Docker Desktop installed, you can start everything with one command:

```bash
docker compose up -d --build
```

> **Note:** Ollama must be running on your host machine. The backend connects to it via `http://host.docker.internal:11434`.

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |

---

## ☁️ Cloud Deployment (Render + Vercel)

The project supports a fully cloud-hosted mode that swaps local components for managed services:

| Component | Local | Cloud |
|-----------|-------|-------|
| **LLM** | Ollama (llama3) | Groq API (llama3-70b) |
| **Vector Store** | ChromaDB (on-disk) | Pinecone (managed) |
| **Embeddings** | sentence-transformers (PyTorch, ~500MB) | fastembed (ONNX, ~150MB) |
| **Database** | SQLite | SQLite (ephemeral) |
| **Est. RAM** | ~1GB | ~250MB ✅ |

### Backend → Render
1. Connect your GitHub repo and deploy the `backend/` folder as a **Web Service**.
2. Set the **Root Directory** to `backend` and **Dockerfile Path** to `./Dockerfile`.
3. Add environment variables:
   - `GROQ_API_KEY` — Your Groq API key
   - `PINECONE_API_KEY` — Your Pinecone API key
   - `PINECONE_INDEX_NAME` — Your Pinecone index name (default: `rag-assistant`)
   - `DISABLE_RERANKER=true` — Saves ~100MB RAM on Render free tier

### Frontend → Vercel / Netlify
1. Import the `frontend/` folder.
2. Set `VITE_API_URL` to your Render backend URL.
3. Build command: `npm run build`, Output: `dist`.

---

## 📁 Project Structure

```
RAG Assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point + lifespan
│   │   ├── config.py                # All tunable parameters
│   │   ├── models.py                # Pydantic schemas
│   │   ├── database.py              # SQLite/PostgreSQL async ORM
│   │   ├── ingestion/
│   │   │   ├── loader.py            # PDF/DOCX/TXT loaders
│   │   │   ├── chunker.py           # Recursive text splitting
│   │   │   └── pipeline.py          # Full ingestion orchestration
│   │   ├── retrieval/
│   │   │   ├── vector_store.py      # ChromaDB / Pinecone dual-mode
│   │   │   ├── bm25_store.py        # BM25 keyword index
│   │   │   ├── hybrid_retriever.py  # Weighted RRF fusion
│   │   │   └── reranker.py          # Cross-encoder reranking
│   │   ├── chain/
│   │   │   ├── qa_chain.py          # RAG chain (Ollama / Groq)
│   │   │   ├── memory.py            # Conversational memory
│   │   │   └── hallucination_guard.py
│   │   ├── evaluation/
│   │   │   └── ragas_eval.py        # RAGAS metric computation
│   │   └── routers/
│   │       ├── documents.py         # Upload, list, delete
│   │       ├── chat.py              # WebSocket + REST chat
│   │       └── evaluation.py        # Run & view evaluations
│   ├── data/                        # ChromaDB, uploads, SQLite
│   ├── requirements.txt             # Full local dependencies
│   ├── requirements-cloud.txt       # Cloud-optimized (no PyTorch)
│   └── Dockerfile                   # Cloud container config
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Main 3-column layout
│   │   ├── index.css                # Warm design system
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx    # Streaming chat + citations
│   │   │   ├── SourcePanel.jsx      # Source references panel
│   │   │   ├── Sidebar.jsx          # Knowledge base sidebar
│   │   │   ├── EvalDashboard.jsx    # RAGAS metrics dashboard
│   │   │   └── DocumentManager.jsx  # Upload + manage docs
│   │   ├── hooks/useWebSocket.js    # WebSocket with auto-reconnect
│   │   └── utils/api.js             # REST client
│   ├── Dockerfile                   # Nginx container for prod
│   └── package.json
├── cli/cli_harness.py               # Terminal test interface
├── docker-compose.yml               # Local Docker orchestration
└── README.md
```

---

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + feature list |
| `POST` | `/api/documents/upload` | Upload document (PDF/DOCX/TXT) |
| `GET` | `/api/documents/` | List all documents |
| `DELETE` | `/api/documents/{id}` | Delete document |
| `POST` | `/api/chat` | Q&A (non-streaming) |
| `POST` | `/api/chat/compare` | Document comparison |
| `WS` | `/ws/chat/{session_id}` | Streaming Q&A |
| `POST` | `/api/eval/run` | Run RAGAS evaluation |
| `GET` | `/api/eval/results` | List evaluation runs |

---

## ⚙️ Configuration

All settings are in `backend/.env` or set as environment variables:

| Setting | Default | Description |
|---------|---------|-------------|
| `OLLAMA_MODEL` | `llama3` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks (20%) |
| `HYBRID_VECTOR_WEIGHT` | `0.7` | Vector search weight |
| `HYBRID_BM25_WEIGHT` | `0.3` | BM25 search weight |
| `TOP_K_RETRIEVAL` | `20` | Candidates before reranking |
| `TOP_K_FINAL` | `5` | Results after reranking |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/rag_assistant.db` | Database connection |
| `GROQ_API_KEY` | `None` | Groq API key (cloud mode) |
| `PINECONE_API_KEY` | `None` | Pinecone API key (cloud mode) |
| `PINECONE_INDEX_NAME` | `rag-assistant` | Pinecone index name |
| `DISABLE_RERANKER` | `false` | Skip cross-encoder to save RAM |

---

## 🎓 Technical Decisions

### Why Hybrid Search?
Pure vector search misses exact keyword matches (author names, acronyms). BM25 catches those. Combining both with weighted RRF gives 30-40% better retrieval than either alone.

### Why Cross-Encoder Reranking?
Bi-encoder embeddings are fast but shallow. Cross-encoders process (query, chunk) pairs jointly, capturing negation, coreference, and deep semantic overlap. ~50ms for 20 pairs.

### Why Reciprocal Rank Fusion?
BM25 scores and cosine similarity live on different scales. RRF is score-agnostic — it fuses based on rank position, not raw scores.

### Why fastembed for Cloud?
`sentence-transformers` requires PyTorch (~400MB RAM just for the runtime). `fastembed` uses ONNX Runtime to load the exact same `all-MiniLM-L6-v2` model in ~150MB, making it viable on Render's 512MB free tier.

---

## 📄 License

MIT
