"""
Hallucination Guard — Self-Verification Post-Processing

After the LLM generates an answer, this module verifies each claim
against the retrieved context.  Marks claims as:
  • GROUNDED   — appears in the context
  • UNGROUNDED — does NOT appear in the context
  • HEDGED     — answer appropriately qualifies uncertainty

Returns a confidence level (high / medium / low) for the UI badge.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings

logger = logging.getLogger(__name__)

GUARD_PROMPT = """\
You are a fact-checking assistant.  Given an answer and the source context \
it was derived from, verify the factual grounding of the answer.

Evaluate the overall answer and return a JSON object with:
- "confidence": "high" if all claims are grounded, "medium" if mostly grounded, "low" if significant claims are ungrounded
- "issues": a list of strings describing any ungrounded or questionable claims (empty list if fully grounded)

Answer to verify:
{answer}

Source context:
{context}

Return ONLY valid JSON, no markdown fences, no explanation."""


class HallucinationGuard:
    """Post-processing chain that verifies answer grounding."""

    def __init__(self) -> None:
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            if settings.GROQ_API_KEY:
                logger.info("Connecting to Groq API (model: llama3-8b-8192) for HallucinationGuard...")
                from langchain_groq import ChatGroq
                self._llm = ChatGroq(
                    model="llama3-8b-8192",
                    groq_api_key=settings.GROQ_API_KEY,
                    temperature=0.0,
                    max_tokens=512,
                )
            else:
                from langchain_ollama import ChatOllama
                self._llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL,
                    temperature=0.0,
                    num_predict=512,
                )
        return self._llm

    async def verify(
        self, answer: str, context: str
    ) -> dict:
        """
        Verify an answer against its source context.

        Returns: {"confidence": "high"|"medium"|"low", "issues": [...]}
        """
        prompt = ChatPromptTemplate.from_messages([
            ("human", GUARD_PROMPT),
        ])
        chain = prompt | self.llm | StrOutputParser()

        try:
            raw = await chain.ainvoke({
                "answer": answer,
                "context": context[:4000],  # limit context size
            })

            # Try to parse JSON from the response
            # Strip markdown code fences if present
            cleaned = raw.strip()
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

            result = json.loads(cleaned)
            confidence = result.get("confidence", "medium")
            issues = result.get("issues", [])

            return {
                "confidence": confidence,
                "issues": issues if isinstance(issues, list) else [],
            }

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Hallucination guard failed: %s", e)
            return {
                "confidence": "medium",
                "issues": ["Verification could not be completed"],
            }
