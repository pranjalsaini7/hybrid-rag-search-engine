"""
Evaluation Router — Run & View RAGAS Evaluations

Endpoints:
  POST /api/eval/run        — Run evaluation on a test set
  GET  /api/eval/results    — List all evaluation runs
  GET  /api/eval/results/{id} — Get specific run details
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models import (
    EvalQuestion,
    EvalRunResult,
    EvalRunListResponse,
    EvalTestSet,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


def _get_evaluator():
    """Import lazily to avoid circular imports."""
    from app.main import evaluator
    return evaluator


@router.post("/run", response_model=EvalRunResult)
async def run_evaluation(test_set: EvalTestSet):
    """
    Run a RAGAS evaluation on the provided test questions.

    Each question should have a `question` and optionally a `ground_truth`.
    The system will run the full RAG pipeline on each question and score
    the results using LLM-as-judge metrics.
    """
    if not test_set.questions:
        raise HTTPException(status_code=400, detail="Test set is empty.")

    evaluator = _get_evaluator()
    result = await evaluator.evaluate(test_set.questions)
    return result


@router.get("/results", response_model=EvalRunListResponse)
async def list_eval_runs():
    """List all past evaluation runs with their metrics."""
    evaluator = _get_evaluator()
    runs = await evaluator.list_runs()
    return EvalRunListResponse(runs=runs, total=len(runs))


@router.get("/results/{run_id}", response_model=EvalRunResult)
async def get_eval_run(run_id: str):
    """Get details of a specific evaluation run."""
    evaluator = _get_evaluator()
    run = await evaluator.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found.")
    return run
