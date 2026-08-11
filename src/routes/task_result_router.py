# src/routers/task_result_router.py

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from src.observability.logging import get_logger
from src.services.task_result_service import TaskResultService
from src.tasks.test_taskiq import analyze_document

logger = get_logger(__name__)
task_result_router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ─── Models ───────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class AnalyzeResponse(BaseModel):
    task_id: Optional[str] = None
    status: str
    result: Optional[dict] = None
    source: Optional[str] = None   # "redis" or "postgres"
    cached: bool = False
    message: str


class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    source: Optional[str] = None   # "redis" or "postgres"
    enqueued_at: Optional[str] = None
    completed_at: Optional[str] = None


class GetResultByInputRequest(BaseModel):
    task_name: str = Field(..., description="e.g. 'src.tasks.test_taskiq:my_task2'")
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)


class ExecutionHistoryResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    executions: list[dict]


# ─── Dependency ───────────────────────────────────────────────────────────

def get_task_service(request: Request) -> TaskResultService:
    factory = getattr(request.app.state, "db_session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized",
        )
    return TaskResultService(db_client=factory)


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@task_result_router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze(
    payload: AnalyzeRequest,
    service: TaskResultService = Depends(get_task_service),
):
    """
    Smart entrypoint.

    1. Checks PostgreSQL for existing SUCCESS result with same input.
       → 200 with cached result instantly.
    2. If no cache → queues Taskiq task.
       → 202 with task_id for polling.
    """
    # ← FIXED: use the actual task name, not a hardcoded wrong one
    task_name = analyze_document.task_name

    cached = await service.get_result_by_input(
        task_name=task_name,
        args=[],
        kwargs={"document_id": payload.document_id, "content": payload.content},
    )

    if cached is not None:
        logger.info("cache_hit", task_id=cached["task_id"], document_id=payload.document_id)
        return AnalyzeResponse(
            task_id=cached["task_id"],
            status="completed",
            result=cached["result"],
            source="postgres",
            cached=True,
            message="Returned from previous execution.",
        )

    try:
        task = await analyze_document.kiq(
            document_id=payload.document_id,
            content=payload.content,
        )
    except Exception:
        logger.exception("queue_failed", document_id=payload.document_id)
        raise HTTPException(status_code=500, detail="Failed to queue task")

    logger.info("task_queued", task_id=task.task_id, document_id=payload.document_id)

    return AnalyzeResponse(
        task_id=task.task_id,
        status="queued",
        message=f"Poll result at GET /tasks/{task.task_id}",
    )


@task_result_router.post(
    "/queue",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def queue(payload: AnalyzeRequest):
    """Skip cache check and queue unconditionally."""
    try:
        task = await analyze_document.kiq(
            document_id=payload.document_id,
            content=payload.content,
        )
    except Exception:
        logger.exception("queue_failed", document_id=payload.document_id)
        raise HTTPException(status_code=500, detail="Failed to queue task")

    return AnalyzeResponse(
        task_id=task.task_id,
        status="queued",
        message=f"Poll result at GET /tasks/{task.task_id}",
    )


@task_result_router.get("/{task_id}", response_model=TaskResultResponse)
async def get_result(
    task_id: str,
    response: Response,  # ← moved before Depends()  # ← injected to set headers without losing response_model
    service: TaskResultService = Depends(get_task_service),
):
    """Poll for task result. 200 = done, 202 = pending, 404 = unknown."""
    result = await service.get_result_by_task_id(task_id)

    if result.get("status") == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-store"},  # ← never cache pending
            detail={"task_id": task_id, "status": "PENDING", "message": "Task still running"},
        )

    if result.get("status") == "ERROR":
        raise HTTPException(status_code=500, detail=result)

    # ← Cache completed results privately (browser only, not shared CDNs/proxies)
    if result["status"] in ("SUCCESS", "FAILED"):
        response.headers["Cache-Control"] = "private, max-age=3600"

    return TaskResultResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════
# DEBUG / ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@task_result_router.post("/debug/by-input", response_model=TaskResultResponse)
async def debug_get_by_input(
    body: GetResultByInputRequest,
    service: TaskResultService = Depends(get_task_service),
):
    """Admin/debug: lookup any task by exact input signature."""
    result = await service.get_result_by_input(
        task_name=body.task_name,
        args=body.args,
        kwargs=body.kwargs,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No successful execution found")
    return TaskResultResponse(
        task_id=result["task_id"],
        status=result["status"],
        result=result.get("result"),
        source="postgres",
        enqueued_at=result.get("enqueued_at"),
        completed_at=result.get("completed_at"),
    )


@task_result_router.post("/debug/history", response_model=ExecutionHistoryResponse)
async def debug_history(
    body: GetResultByInputRequest,
    service: TaskResultService = Depends(get_task_service),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Admin/debug: paginated execution history."""
    return await service.get_all_executions_by_input(
        task_name=body.task_name,
        args=body.args,
        kwargs=body.kwargs,
        limit=limit,
        offset=offset,
    )