"""
QA Chain — RAG Generation with Source Attribution

Ties together retrieval (hybrid + reranker) and generation (Ollama/LLaMA 3)
into a single chain that:
  1. Retrieves relevant chunks via hybrid search
  2. Reranks them with a cross-encoder
  3. Generates an answer grounded in those chunks
  4. Returns structured source citations
  5. Generates smart follow-up questions
  6. Supports conversational memory
  7. Supports document comparison mode

Uses LangChain LCEL for composability and streaming support.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

from app.config import settings
from app.models import ChatResponse, SourceReference
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.reranker import Reranker

logger = logging.getLogger(__name__)

# ── System prompt ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a Research Paper Assistant — an expert at reading and synthesising \
academic literature.  Answer the user's question based ONLY on the provided \
context from research papers.

Rules:
• Cite papers by name using [1], [2], etc. matching the source numbers below.
• If the context does not contain enough information, say so clearly — \
  do NOT hallucinate or invent facts.
• Synthesise information across multiple papers when the question requires it.
• Use clear, academic language appropriate to the user's question.
• Keep answers thorough but concise — aim for 3–6 paragraphs maximum.

────────────────────────────────
CONVERSATION HISTORY:
{history}

────────────────────────────────
SOURCES:
{context}
────────────────────────────────"""

HUMAN_TEMPLATE = "{question}"

# ── Summarization prompt (used during ingestion) ────────────────────────

SUMMARY_PROMPT = """\
You are a research paper summariser.  Given the following excerpts from \
an academic document, produce a concise 3-line summary that captures:
  1. The main topic or research question
  2. The key methodology or approach
  3. The primary finding or contribution

Output ONLY the 3-line summary — no preamble, no bullet markers.

────────────────────────────────
DOCUMENT EXCERPTS:
{text}
────────────────────────────────"""

# ── Follow-up question generation prompt ────────────────────────────────

FOLLOW_UP_PROMPT = """\
Based on the following question and answer from a research paper Q&A session, \
generate exactly 3 follow-up questions that the user might want to ask next.

The follow-up questions should:
- Be specific and relevant to the topic discussed
- Explore different aspects (methodology, results, implications)
- Be concise (under 15 words each)

Question: {question}
Answer: {answer}

Output ONLY the 3 questions, one per line, no numbering, no bullets."""

# ── Document comparison prompt ──────────────────────────────────────────

COMPARISON_PROMPT = """\
You are a Research Paper Assistant comparing two documents.  Based ONLY on \
the provided excerpts from Document A and Document B, compare and contrast \
them regarding the user's question.

Structure your answer as:
1. What Document A says about the topic
2. What Document B says about the topic
3. Key similarities and differences

Cite using [A1], [A2] for Document A sources and [B1], [B2] for Document B sources.

────────────────────────────────
DOCUMENT A EXCERPTS:
{context_a}

────────────────────────────────
DOCUMENT B EXCERPTS:
{context_b}
────────────────────────────────"""

# ── Query condensation prompt ───────────────────────────────────────────

CONDENSE_PROMPT = """\
Given the following conversation history and a follow-up question, rephrase the \
follow-up question to be a standalone question (in its original language) that \
can be understood without the conversation history. Do NOT answer the question, \
just return the rephrased standalone question.

Conversation History:
{history}

Follow-up Question: {question}
Standalone Question:"""



class QAChain:
    """RAG question-answering chain with Ollama + LangChain LCEL."""

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        reranker: Reranker,
    ) -> None:
        self._retriever = hybrid_retriever
        self._reranker = reranker
        self._llm = None

    @property
    def llm(self):
        """Lazy-load the chat model (Ollama locally, Groq in cloud)."""
        if self._llm is None:
            if settings.GROQ_API_KEY:
                logger.info("Connecting to Groq API (model: llama3-8b-8192)...")
                from langchain_groq import ChatGroq
                self._llm = ChatGroq(
                    model="llama3-8b-8192",
                    groq_api_key=settings.GROQ_API_KEY,
                    temperature=0.3,
                    max_tokens=2048,
                )
            else:
                logger.info("Connecting to Ollama model: %s", settings.OLLAMA_MODEL)
                self._llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL,
                    temperature=0.3,       # low temp for factual answers
                    num_predict=2048,      # max tokens in response
                )
        return self._llm

    # ── Context formatting ──────────────────────────────────────────────

    @staticmethod
    def _format_context(documents: List[Document]) -> str:
        """Format retrieved documents into a numbered source list."""
        parts = []
        for i, doc in enumerate(documents, start=1):
            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", "?")
            score = doc.metadata.get("relevance_score", 0)
            parts.append(
                f"[{i}] {source}  (page {page}, score {score:.2f})\n"
                f"{doc.page_content}\n"
            )
        return "\n".join(parts)

    @staticmethod
    def _format_context_prefixed(
        documents: List[Document], prefix: str = ""
    ) -> str:
        """Format docs with a prefix like [A1], [B1] for comparison mode."""
        parts = []
        for i, doc in enumerate(documents, start=1):
            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", "?")
            parts.append(
                f"[{prefix}{i}] {source}  (page {page})\n"
                f"{doc.page_content}\n"
            )
        return "\n".join(parts)

    @staticmethod
    def _build_source_refs(documents: List[Document]) -> List[SourceReference]:
        """Convert retrieved Documents into SourceReference models."""
        refs = []
        for doc in documents:
            refs.append(
                SourceReference(
                    document_name=doc.metadata.get("source", "unknown"),
                    page_number=doc.metadata.get("page"),
                    chunk_text=doc.page_content[:500],  # truncate for display
                    relevance_score=min(
                        max(doc.metadata.get("relevance_score", 0), 0), 1
                    ),
                )
            )
        return refs

    # ── Follow-up question generation ───────────────────────────────────

    async def _generate_follow_ups(
        self, question: str, answer: str
    ) -> List[str]:
        """Generate 2-3 smart follow-up questions."""
        prompt = ChatPromptTemplate.from_messages([
            ("human", FOLLOW_UP_PROMPT),
        ])
        chain = prompt | self.llm | StrOutputParser()

        try:
            raw = await chain.ainvoke({
                "question": question,
                "answer": answer[:1000],
            })
            questions = [
                q.strip() for q in raw.strip().split("\n")
                if q.strip() and len(q.strip()) > 5
            ]
            return questions[:3]
        except Exception as e:
            logger.warning("Follow-up generation failed: %s", e)
            return []

    # ── Main query interface ────────────────────────────────────────────

    async def _condense_question(self, question: str, history: str) -> str:
        """Condense conversational follow-up into a standalone search query."""
        if not history or history == "(No prior conversation)" or not history.strip():
            return question

        prompt = ChatPromptTemplate.from_messages([
            ("human", CONDENSE_PROMPT),
        ])
        chain = prompt | self.llm | StrOutputParser()

        try:
            condensed = await chain.ainvoke({
                "history": history,
                "question": question,
            })
            condensed_str = condensed.strip()
            if condensed_str and len(condensed_str) > 3:
                logger.info("Condensed query: '%s' -> '%s'", question, condensed_str)
                return condensed_str
        except Exception as e:
            logger.warning("Query condensation failed: %s", e)

        return question

    async def query(
        self,
        question: str,
        history: str = "(No prior conversation)",
    ) -> ChatResponse:
        """
        Full RAG pipeline: retrieve → rerank → generate.

        Returns a ChatResponse with the answer, source references,
        and follow-up questions.
        """
        # 0. Condense question
        search_query = await self._condense_question(question, history)

        # 1. Hybrid retrieval
        candidates = self._retriever.retrieve(search_query)

        # 2. Rerank
        top_docs = self._reranker.rerank(search_query, candidates)

        # 3. Build context
        context = self._format_context(top_docs)

        # 4. Generate answer
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ])
        chain = prompt | self.llm | StrOutputParser()
        answer = await chain.ainvoke({
            "context": context,
            "question": question,
            "history": history,
        })

        # 5. Build response
        sources = self._build_source_refs(top_docs)

        # 6. Generate follow-up questions
        follow_ups = await self._generate_follow_ups(question, answer)

        return ChatResponse(
            answer=answer,
            sources=sources,
            follow_up_questions=follow_ups,
        )


    async def stream_query(
        self,
        question: str,
        history: str = "(No prior conversation)",
    ) -> tuple[AsyncIterator[str], List[SourceReference], List[Document]]:
        """
        Streaming variant: yields tokens as they arrive from the LLM.

        Returns (token_iterator, source_references, top_docs).
        Sources are computed eagerly before streaming starts.
        """
        # 0. Condense question
        search_query = await self._condense_question(question, history)

        # 1. Hybrid retrieval
        candidates = self._retriever.retrieve(search_query)

        # 2. Rerank
        top_docs = self._reranker.rerank(search_query, candidates)

        # 3. Build context + sources
        context = self._format_context(top_docs)
        sources = self._build_source_refs(top_docs)

        # 4. Stream answer
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ])
        chain = prompt | self.llm | StrOutputParser()

        async def token_stream():
            async for token in chain.astream({
                "context": context,
                "question": question,
                "history": history,
            }):
                yield token

        return token_stream(), sources, top_docs


    # ── Document comparison ─────────────────────────────────────────────

    async def compare_documents(
        self,
        question: str,
        doc_a_name: str,
        doc_b_name: str,
    ) -> ChatResponse:
        """
        Compare two documents regarding a specific question.

        Retrieves chunks scoped to each document separately,
        then generates a structured comparison.
        """
        # Retrieve from both docs
        all_candidates = self._retriever.retrieve(question, k=40)

        # Split by document
        doc_a_chunks = [
            d for d in all_candidates
            if d.metadata.get("source") == doc_a_name
        ][:5]
        doc_b_chunks = [
            d for d in all_candidates
            if d.metadata.get("source") == doc_b_name
        ][:5]

        context_a = self._format_context_prefixed(doc_a_chunks, "A")
        context_b = self._format_context_prefixed(doc_b_chunks, "B")

        prompt = ChatPromptTemplate.from_messages([
            ("human", COMPARISON_PROMPT + "\n\nQuestion: {question}"),
        ])
        chain = prompt | self.llm | StrOutputParser()
        answer = await chain.ainvoke({
            "context_a": context_a,
            "context_b": context_b,
            "question": question,
        })

        sources_a = self._build_source_refs(doc_a_chunks)
        sources_b = self._build_source_refs(doc_b_chunks)

        return ChatResponse(
            answer=answer,
            sources=sources_a + sources_b,
        )

    # ── Summarization (used during document ingestion) ──────────────────

    async def summarize_document(self, text: str) -> str:
        """
        Generate a 3-line semantic summary of a document.

        Called automatically after ingestion to populate the document
        manager with intelligent summaries.
        """
        # Take first ~3000 chars to stay within context limits
        excerpt = text[:3000]

        prompt = ChatPromptTemplate.from_messages([
            ("human", SUMMARY_PROMPT),
        ])
        chain = prompt | self.llm | StrOutputParser()

        try:
            summary = await chain.ainvoke({"text": excerpt})
            return summary.strip()
        except Exception as e:
            logger.error("Summarization failed: %s", e)
            return "Summary generation failed — document indexed successfully."
