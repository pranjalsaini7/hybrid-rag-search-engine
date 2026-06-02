"""
Chat Router — WebSocket Streaming + REST Fallback

The primary interface is the WebSocket at /ws/chat/{session_id}.
Tokens are streamed as they arrive from the LLM, followed by
source references, follow-up questions, and a "done" signal.

A REST POST endpoint is also provided for simpler clients
(e.g. the CLI harness or curl testing).

Features:
  • Conversational memory (per session, last 10 turns)
  • Smart follow-up question generation
  • Optional hallucination guard
  • Document comparison mode
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models import ChatRequest, ChatResponse, CompareRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _get_qa_chain():
    """Import lazily to avoid circular imports at module load time."""
    from app.main import qa_chain
    return qa_chain


def _get_memory():
    """Import lazily to avoid circular imports at module load time."""
    from app.main import memory
    return memory


def _get_guard():
    """Import lazily to avoid circular imports at module load time."""
    from app.main import hallucination_guard
    return hallucination_guard


# ── REST endpoint ───────────────────────────────────────────────────────

@router.post("/api/chat", response_model=ChatResponse)
async def chat_rest(request: ChatRequest):
    """
    Non-streaming chat endpoint.

    Returns the full answer at once — useful for the CLI harness
    and automated testing.  Supports conversational memory.
    """
    qa = _get_qa_chain()
    mem = _get_memory()

    # Get conversation history
    history = await mem.get_formatted_history(request.session_id)

    # Run RAG pipeline
    response = await qa.query(request.query, history=history)

    # Persist to memory
    await mem.add_message(request.session_id, "user", request.query)
    await mem.add_message(
        request.session_id,
        "assistant",
        response.answer,
        sources_json=json.dumps([s.model_dump() for s in response.sources]),
    )

    return response


# ── Document comparison endpoint ────────────────────────────────────────

@router.post("/api/chat/compare", response_model=ChatResponse)
async def compare_documents(request: CompareRequest):
    """
    Compare two documents regarding a specific question.

    Returns a structured comparison: what doc A says vs doc B says,
    with similarities and differences highlighted.
    """
    qa = _get_qa_chain()

    # Resolve document names from IDs
    from app.main import pipeline
    doc_a = await pipeline.get_document(request.doc_a_id)
    doc_b = await pipeline.get_document(request.doc_b_id)

    if doc_a is None or doc_b is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="One or both documents not found.",
        )

    response = await qa.compare_documents(
        question=request.query,
        doc_a_name=doc_a.filename,
        doc_b_name=doc_b.filename,
    )
    return response


# ── WebSocket endpoint ──────────────────────────────────────────────────

@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    Streaming chat over WebSocket.

    Client sends:
      {"query": "...", "use_guard": false}

    Server streams:
      {"type": "token",      "content": "..."}     — per token
      {"type": "sources",    "data": [...]}         — source references
      {"type": "follow_up",  "data": [...]}         — follow-up questions
      {"type": "guard",      "data": {...}}         — hallucination guard result
      {"type": "done"}                              — generation complete
      {"type": "error",      "content": "..."}      — on failure
    """
    await websocket.accept()
    logger.info("WebSocket connected: session=%s", session_id)

    try:
        while True:
            # Wait for a message from the client
            raw = await websocket.receive_text()
            data = json.loads(raw)
            query = data.get("query", "").strip()
            use_guard = data.get("use_guard", False)

            if not query:
                await websocket.send_json(
                    {"type": "error", "content": "Empty query."}
                )
                continue

            logger.info("Query [%s]: %s", session_id, query[:100])

            try:
                qa = _get_qa_chain()
                mem = _get_memory()
                guard = _get_guard()

                # Get conversation history
                history = await mem.get_formatted_history(session_id)

                # Stream tokens
                token_stream, sources, top_docs = await qa.stream_query(
                    query, history=history
                )

                full_answer = ""
                async for token in token_stream:
                    full_answer += token
                    await websocket.send_json(
                        {"type": "token", "content": token}
                    )

                # Send source references
                source_dicts = [s.model_dump() for s in sources]
                await websocket.send_json({
                    "type": "sources",
                    "data": source_dicts,
                })

                # Generate and send follow-up questions
                follow_ups = await qa._generate_follow_ups(query, full_answer)
                if follow_ups:
                    await websocket.send_json({
                        "type": "follow_up",
                        "data": follow_ups,
                    })

                # Optional: run hallucination guard
                if use_guard and top_docs:
                    context_text = "\n".join(d.page_content for d in top_docs)
                    guard_result = await guard.verify(full_answer, context_text)
                    await websocket.send_json({
                        "type": "guard",
                        "data": guard_result,
                    })

                # Persist to memory
                await mem.add_message(session_id, "user", query)
                await mem.add_message(
                    session_id,
                    "assistant",
                    full_answer,
                    sources_json=json.dumps(source_dicts),
                )

                # Signal completion
                await websocket.send_json({"type": "done"})

            except Exception as e:
                logger.exception("Error processing query: %s", e)
                await websocket.send_json(
                    {"type": "error", "content": str(e)}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
