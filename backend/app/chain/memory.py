"""
Conversational Memory — Session-Based Window Memory

Keeps the last N turns (user + assistant) per session, persisted
to SQLite so memory survives server restarts.

Each browser tab / CLI session gets its own memory via session_id.
"""

from __future__ import annotations

import json
import logging
from typing import List, Tuple

from sqlalchemy import select

from app.database import ChatHistoryRecord, async_session

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10  # Keep last 10 user/assistant pairs


class ConversationMemory:
    """Session-scoped conversation memory with SQLite persistence."""

    async def get_history(self, session_id: str) -> List[Tuple[str, str]]:
        """
        Retrieve the last N turns for a session.

        Returns list of (user_message, assistant_message) tuples.
        """
        async with async_session() as session:
            result = await session.execute(
                select(ChatHistoryRecord)
                .where(ChatHistoryRecord.session_id == session_id)
                .order_by(ChatHistoryRecord.timestamp.asc())
            )
            records = result.scalars().all()

        # Group into pairs
        pairs: List[Tuple[str, str]] = []
        user_msg = None
        for r in records:
            if r.role == "user":
                user_msg = r.content
            elif r.role == "assistant" and user_msg is not None:
                pairs.append((user_msg, r.content))
                user_msg = None

        # Keep only the last N turns
        return pairs[-MAX_HISTORY_TURNS:]

    async def get_formatted_history(self, session_id: str) -> str:
        """Return history as a formatted string for the prompt."""
        pairs = await self.get_history(session_id)
        if not pairs:
            return "(No prior conversation)"

        lines = []
        for user_msg, assistant_msg in pairs:
            lines.append(f"User: {user_msg}")
            lines.append(f"Assistant: {assistant_msg[:500]}")  # Truncate long answers
        return "\n".join(lines)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources_json: str = "[]",
    ) -> None:
        """Persist a single message to the database."""
        async with async_session() as session:
            record = ChatHistoryRecord(
                session_id=session_id,
                role=role,
                content=content,
                sources_json=sources_json,
            )
            session.add(record)
            await session.commit()

    async def clear_session(self, session_id: str) -> int:
        """Delete all messages for a session. Returns count deleted."""
        async with async_session() as session:
            result = await session.execute(
                select(ChatHistoryRecord)
                .where(ChatHistoryRecord.session_id == session_id)
            )
            records = result.scalars().all()
            count = len(records)
            for r in records:
                await session.delete(r)
            await session.commit()
            return count
