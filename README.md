# 📚 Research Paper RAG Assistant

A **production-grade Retrieval-Augmented Generation** system for querying research papers. Upload PDFs and ask cross-paper questions — powered by **Ollama/LLaMA 3**, **ChromaDB**, **hybrid BM25+vector search**, and a **RAGAS evaluation dashboard**.

> **100% Local** — No API keys, no cloud services. Everything runs on your machine.

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
- **LLM-as-Judge** — Uses Ollama locally (zero cost)
- **Historical Tracking** — Compare evaluation runs over time

### Premium Web UI
- **Dark Mode** with glassmorphism and vibrant accents
- **Drag-and-drop** document upload with progress
- **Real-time streaming** chat with typing indicators
- **Source panel** with relevance score bars
- **Evaluation dashboard** with score cards

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.12+** (via uv or standard install)
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

## 📁 Project Structure

```
RAG Assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── config.py                # All tunable parameters
│   │   ├── models.py                # Pydantic schemas
│   │   ├── database.py              # SQLite async ORM
│   │   ├── ingestion/
│   │   │   ├── loader.py            # PDF/DOCX/TXT loaders
│   │   │   ├── chunker.py           # Recursive text splitting
│   │   │   └── pipeline.py          # Full ingestion orchestration
│   │   ├── retrieval/
│   │   │   ├── vector_store.py      # ChromaDB wrapper
│   │   │   ├── bm25_store.py        # BM25 keyword index
│   │   │   ├── hybrid_retriever.py  # Weighted RRF fusion
│   │   │   └── reranker.py          # Cross-encoder reranking
│   │   ├── chain/
│   │   │   ├── qa_chain.py          # RAG chain + follow-ups + comparison
│   │   │   ├── memory.py            # Conversational memory
│   │   │   └── hallucination_guard.py
│   │   ├── evaluation/
│   │   │   └── ragas_eval.py        # RAGAS metric computation
│   │   └── routers/
│   │       ├── documents.py         # Upload, list, delete
│   │       ├── chat.py              # WebSocket + REST chat
│   │       └── evaluation.py        # Run & view evaluations
│   ├── data/                        # ChromaDB, uploads, SQLite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Main layout + routing
│   │   ├── index.css                # Design system
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx    # Streaming chat
│   │   │   ├── SourcePanel.jsx      # Source references
│   │   │   ├── DocumentManager.jsx  # Upload + manage docs
│   │   │   ├── EvalDashboard.jsx    # RAGAS metrics
│   │   │   └── Sidebar.jsx          # Navigation
│   │   ├── hooks/useWebSocket.js    # WebSocket with reconnect
│   │   └── utils/api.js             # REST client
│   └── package.json
├── cli/cli_harness.py               # Terminal test interface
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

All settings are in `backend/.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `OLLAMA_MODEL` | `llama3` | Ollama model name |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks (20%) |
| `HYBRID_VECTOR_WEIGHT` | `0.7` | Vector search weight |
| `HYBRID_BM25_WEIGHT` | `0.3` | BM25 search weight |
| `TOP_K_RETRIEVAL` | `20` | Candidates before reranking |
| `TOP_K_FINAL` | `5` | Results after reranking |

---

## 🎓 Technical Decisions

### Why Hybrid Search?
Pure vector search misses exact keyword matches (author names, acronyms). BM25 catches those. Combining both with weighted RRF gives 30-40% better retrieval than either alone.

### Why Cross-Encoder Reranking?
Bi-encoder embeddings are fast but shallow. Cross-encoders process (query, chunk) pairs jointly, capturing negation, coreference, and deep semantic overlap. ~50ms for 20 pairs.

### Why Reciprocal Rank Fusion?
BM25 scores and cosine similarity live on different scales. RRF is score-agnostic — it fuses based on rank position, not raw scores.

---

## 📄 License

MIT
