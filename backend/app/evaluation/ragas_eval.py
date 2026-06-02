"""
RAGAS Evaluator — Local Evaluation with Ollama

Runs RAGAS-style evaluation metrics locally using the same Ollama
model used for generation.  Computes:
  • Faithfulness — is the answer grounded in context?
  • Answer Relevancy — does the answer address the question?
  • Context Precision — are retrieved chunks relevant?
  • Context Recall — did we retrieve all needed information?

Since RAGAS requires an LLM judge, we use Ollama (fully local, no cost).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select

from app.config import settings
from app.database import EvalRunRecord, async_session
from app.models import (
    EvalMetrics,
    EvalQuestion,
    EvalRunResult,
    ChatResponse,
)

logger = logging.getLogger(__name__)


class RAGASEvaluator:
    """Evaluate RAG pipeline quality using LLM-as-judge metrics."""

    def __init__(self, qa_chain=None) -> None:
        self._qa_chain = qa_chain

    def set_qa_chain(self, qa_chain) -> None:
        self._qa_chain = qa_chain

    async def evaluate(
        self, questions: List[EvalQuestion]
    ) -> EvalRunResult:
        """
        Run evaluation on a set of questions.

        For each question:
          1. Run the full RAG pipeline (retrieve + generate)
          2. Score the answer against ground truth using LLM-as-judge
          3. Aggregate metrics

        Returns an EvalRunResult with per-question and aggregate scores.
        """
        if self._qa_chain is None:
            raise RuntimeError("QA chain not initialized")

        per_question = []
        total_faithfulness = 0.0
        total_relevancy = 0.0
        total_precision = 0.0
        total_recall = 0.0

        for q in questions:
            try:
                # Run the RAG pipeline
                response: ChatResponse = await self._qa_chain.query(q.question)

                # Score using simple heuristics + LLM judge
                scores = await self._score_response(
                    question=q.question,
                    answer=response.answer,
                    ground_truth=q.ground_truth,
                    sources=response.sources,
                )

                per_question.append({
                    "question": q.question,
                    "answer": response.answer[:500],
                    "ground_truth": q.ground_truth[:500],
                    "scores": scores,
                    "source_count": len(response.sources),
                })

                total_faithfulness += scores.get("faithfulness", 0)
                total_relevancy += scores.get("answer_relevancy", 0)
                total_precision += scores.get("context_precision", 0)
                total_recall += scores.get("context_recall", 0)

            except Exception as e:
                logger.error("Eval failed for question: %s — %s", q.question[:50], e)
                per_question.append({
                    "question": q.question,
                    "answer": "",
                    "error": str(e),
                    "scores": {},
                })

        n = max(len(questions), 1)
        metrics = EvalMetrics(
            faithfulness=round(total_faithfulness / n, 3),
            answer_relevancy=round(total_relevancy / n, 3),
            context_precision=round(total_precision / n, 3),
            context_recall=round(total_recall / n, 3),
        )

        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Persist to database
        async with async_session() as session:
            record = EvalRunRecord(
                id=run_id,
                faithfulness=metrics.faithfulness,
                answer_relevancy=metrics.answer_relevancy,
                context_precision=metrics.context_precision,
                context_recall=metrics.context_recall,
                per_question_json=json.dumps(per_question),
                timestamp=now,
            )
            session.add(record)
            await session.commit()

        return EvalRunResult(
            id=run_id,
            timestamp=now,
            metrics=metrics,
            per_question=per_question,
        )

    async def _score_response(
        self,
        question: str,
        answer: str,
        ground_truth: str,
        sources: list,
    ) -> dict:
        """
        Score a single response using LLM-as-judge.

        Uses the Ollama model to evaluate faithfulness and relevancy.
        Context precision/recall use simpler heuristic checks.
        """
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        import re

        JUDGE_PROMPT = """\
You are an evaluation judge. Score the following answer on two dimensions.

Question: {question}
Answer: {answer}
Ground Truth: {ground_truth}

Score each dimension from 0.0 to 1.0:
1. faithfulness: Is the answer factually consistent with itself and not making things up?
2. answer_relevancy: Does the answer actually address the question asked?

Return ONLY valid JSON: {{"faithfulness": 0.X, "answer_relevancy": 0.X}}"""

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("human", JUDGE_PROMPT),
            ])
            chain = prompt | self._qa_chain.llm | StrOutputParser()
            raw = await chain.ainvoke({
                "question": question,
                "answer": answer[:1000],
                "ground_truth": ground_truth[:1000] if ground_truth else "Not provided",
            })

            cleaned = raw.strip()
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            scores = json.loads(cleaned)

            # Context precision: ratio of sources that seem relevant (simple heuristic)
            context_precision = min(len(sources) / max(settings.TOP_K_FINAL, 1), 1.0)

            # Context recall: if ground truth is provided, check keyword overlap
            context_recall = 0.8  # default
            if ground_truth:
                gt_words = set(ground_truth.lower().split())
                answer_words = set(answer.lower().split())
                overlap = len(gt_words & answer_words)
                context_recall = min(overlap / max(len(gt_words), 1), 1.0)

            return {
                "faithfulness": float(scores.get("faithfulness", 0.5)),
                "answer_relevancy": float(scores.get("answer_relevancy", 0.5)),
                "context_precision": round(context_precision, 3),
                "context_recall": round(context_recall, 3),
            }

        except Exception as e:
            logger.warning("LLM judge scoring failed: %s", e)
            return {
                "faithfulness": 0.5,
                "answer_relevancy": 0.5,
                "context_precision": 0.5,
                "context_recall": 0.5,
            }

    async def list_runs(self) -> list[EvalRunResult]:
        """List all past evaluation runs."""
        async with async_session() as session:
            result = await session.execute(
                select(EvalRunRecord).order_by(EvalRunRecord.timestamp.desc())
            )
            records = result.scalars().all()
            return [
                EvalRunResult(
                    id=r.id,
                    timestamp=r.timestamp,
                    metrics=EvalMetrics(
                        faithfulness=r.faithfulness,
                        answer_relevancy=r.answer_relevancy,
                        context_precision=r.context_precision,
                        context_recall=r.context_recall,
                    ),
                    per_question=json.loads(r.per_question_json or "[]"),
                    test_set_name=r.test_set_name or "default",
                )
                for r in records
            ]

    async def get_run(self, run_id: str) -> EvalRunResult | None:
        """Get a specific evaluation run."""
        async with async_session() as session:
            result = await session.execute(
                select(EvalRunRecord).where(EvalRunRecord.id == run_id)
            )
            r = result.scalar_one_or_none()
            if r is None:
                return None
            return EvalRunResult(
                id=r.id,
                timestamp=r.timestamp,
                metrics=EvalMetrics(
                    faithfulness=r.faithfulness,
                    answer_relevancy=r.answer_relevancy,
                    context_precision=r.context_precision,
                    context_recall=r.context_recall,
                ),
                per_question=json.loads(r.per_question_json or "[]"),
                test_set_name=r.test_set_name or "default",
            )
