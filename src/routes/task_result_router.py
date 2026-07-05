# src/routers/task_result_router.py
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.services.task_result_service import TaskResultService

logger = logging.getLogger(__name__)

task_result_router = APIRouter(prefix="/task-results", tags=["Task Results"])


# ─── Request/Response Models ─────────────────────────────────────────────────
class GetResultByInputRequest(BaseModel):
    task_name: str = Field(..., description="e.g., 'src.tasks.test_taskiq:my_task'")
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)


# ─── Helper: Get session factory from app state ──────────────────────────────
def _get_session_factory(request: Request):
    """Get session factory from app state (set in FastAPI lifespan)."""
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise HTTPException(
            status_code=500,
            detail="Database not initialized. Check FastAPI lifespan.",
        )
    return session_factory


# ─── Endpoint 1: Get result by task_id (hybrid) ──────────────────────────────
@task_result_router.get("/by-task-id/{task_id}")
async def get_result_by_task_id(task_id: str, request: Request):
    """
    Hybrid retrieval: Redis (fast) → PostgreSQL (fallback).
    
    Performance: Session opened ONLY if Redis misses (~2ms).
    For Redis hits, no session is opened at all.
    """
    session_factory = _get_session_factory(request)
    service = TaskResultService(session_factory)
    
    result = await service.get_result_by_task_id(task_id)
    
    response = JSONResponse(content=result)
    
    # Cache completed results (they never change)
    if result["status"] in ["SUCCESS", "FAILED"]:
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
    
    return response


# ─── Endpoint 2: Get result by input (guaranteed linkage) ────────────────────
@task_result_router.post("/by-input")
async def get_result_by_input(body: GetResultByInputRequest, request: Request):
    """
    Guaranteed linkage: task_name + args + kwargs → result.
    ALWAYS uses PostgreSQL (Redis doesn't store input).
    
    Performance: Session opened for ~2ms only.
    """
    session_factory = _get_session_factory(request)
    service = TaskResultService(session_factory)
    
    result = await service.get_result_by_input(
        task_name=body.task_name,
        args=body.args,
        kwargs=body.kwargs,
    )
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No successful execution found for this input",
        )
    
    return result


# ─── Endpoint 3: Get ALL executions by input (debugging) ─────────────────────
@task_result_router.post("/all-executions-by-input")
async def get_all_executions_by_input(body: GetResultByInputRequest, request: Request):
    """
    Get ALL executions of the same task signature.
    Useful for debugging idempotency and seeing retry attempts.
    """
    session_factory = _get_session_factory(request)
    service = TaskResultService(session_factory)
    
    results = await service.get_all_executions_by_input(
        task_name=body.task_name,
        args=body.args,
        kwargs=body.kwargs,
    )
    
    return {"count": len(results), "executions": results}