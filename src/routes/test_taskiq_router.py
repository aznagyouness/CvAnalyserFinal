# src/routes/test_taskiq_router.py
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any, Dict

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Query
from pydantic import BaseModel, Field

from src.tasks.test_taskiq import my_task, my_task2, failing_task
from src.services.task_result_service import TaskResultService

logger = logging.getLogger(__name__)

test_taskiq_router = APIRouter(prefix="/test-taskiq", tags=["Test Taskiq"])


# ─── Request/Response Models ─────────────────────────────────────────────────
class TestTaskRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to process")
    delay: float = Field(default=0, ge=0, le=60, description="Optional delay in seconds")


class TestTaskResponse(BaseModel):
    task_id: str
    status: str = "queued"
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # PENDING | SUCCESS | FAILED
    result: Optional[Any] = None
    error: Optional[str] = None
    source: Optional[str] = None  # redis | postgres


class FailingTaskRequest(BaseModel):
    should_fail: bool = Field(default=True, description="Whether the task should intentionally fail")
    error_message: str = Field(default="Intentional failure for testing", description="Custom error message to use")


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


# ─── Endpoint 1: Queue a Task (Fire-and-Forget) ─────────────────────────────
@test_taskiq_router.post("/queue", response_model=TestTaskResponse, status_code=202)
async def queue_test_task(request: TestTaskRequest):
    """
    Queue a test task and return task_id immediately.
    Use GET /test-taskiq/status/{task_id} to check result.
    """
    try:
        task = await my_task2.kiq(text=request.text, delay=request.delay)
        
        return TestTaskResponse(
            task_id=task.task_id,
            status="queued",
            message=f"Task queued. Check status at /test-taskiq/status/{task.task_id}",
        )
    except Exception as e:
        logger.exception("Failed to queue task")
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


# ─── Endpoint 2: Queue and Wait for Result (Synchronous) ────────────────────
@test_taskiq_router.post("/queue-and-wait", response_model=TaskStatusResponse)
async def queue_and_wait(
    request: TestTaskRequest,
    timeout: float = Query(default=10.0, ge=1, le=60, description="Max wait time in seconds"),
):
    """
    Queue a task and wait for the result (blocks HTTP response).
    Only use for FAST tasks (< 5 seconds).
    
    Usage: POST /test-taskiq/queue-and-wait?timeout=10
    """
    try:
        task = await my_task2.kiq(text=request.text, delay=request.delay)
        
        # Wait for result
        result = await task.wait_result(timeout=timeout)
        
        if result.is_err:
            return TaskStatusResponse(
                task_id=task.task_id,
                status="FAILED",
                error=str(result.error),
            )
        
        return TaskStatusResponse(
            task_id=task.task_id,
            status="SUCCESS",
            result=result.return_value,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail=f"Task did not complete within {timeout} seconds",
        )
    except Exception as e:
        logger.exception("Error in queue-and-wait")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ─── Endpoint 3: Check Task Status (Hybrid Redis + PostgreSQL) ──────────────
@test_taskiq_router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, request: Request):
    """
    Get task status using hybrid approach:
    - Redis (fast) for recent tasks
    - PostgreSQL (fallback) for older tasks
    
    Performance: Session opened ONLY if Redis misses (~2ms).
    """
    session_factory = _get_session_factory(request)
    service = TaskResultService(session_factory)
    
    result = await service.get_result_by_task_id(task_id)
    
    return TaskStatusResponse(
        task_id=result["task_id"],
        status=result["status"],
        result=result.get("result"),
        error=result.get("error"),
        source=result.get("source"),
    )


# ─── Endpoint 4: Test Idempotency (Send Same Task Twice) ────────────────────
@test_taskiq_router.post("/test-idempotency", response_model=Dict[str, Any])
async def test_idempotency(request: TestTaskRequest, http_request: Request):
    """
    Send the same task twice to test idempotency.
    Second call should be skipped.
    """
    try:
        # First call
        task1 = await my_task2.kiq(text=request.text, delay=request.delay)
        await asyncio.sleep(0.5)  # Small delay
        
        # Second call (should be detected as duplicate)
        task2 = await my_task2.kiq(text=request.text, delay=request.delay)
        
        # Wait a bit for processing
        await asyncio.sleep(2)
        
        # Check results using short-lived sessions
        session_factory = _get_session_factory(http_request)
        service = TaskResultService(session_factory)
        
        result1 = await service.get_result_by_task_id(task1.task_id)
        result2 = await service.get_result_by_task_id(task2.task_id)
        
        return {
            "task1": {
                "task_id": task1.task_id,
                "status": result1["status"] if result1 else "PENDING",
                "result": result1.get("result") if result1 else None,
            },
            "task2": {
                "task_id": task2.task_id,
                "status": result2["status"] if result2 else "PENDING",
                "result": result2.get("result") if result2 else None,
                "note": "Should be skipped by idempotency middleware",
            },
            "idempotency_working": (
                result1["status"] == "SUCCESS" and 
                result2["status"] == "SUCCESS"
            ),
        }
    except Exception as e:
        logger.exception("Error in idempotency test")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ─── Endpoint 5: Test with BackgroundTasks (FastAPI native) ─────────────────
@test_taskiq_router.post("/queue-with-background", response_model=TestTaskResponse, status_code=202)
async def queue_with_background(
    request: TestTaskRequest,
    background_tasks: BackgroundTasks,
):
    """
    Alternative: Use FastAPI's BackgroundTasks for comparison.
    This runs in the SAME process (no persistence, no retries).
    
    Note: This is for demonstration only — NOT recommended for production.
    """
    async def run_task():
        try:
            task = await my_task2.kiq(text=request.text, delay=request.delay)
            logger.info(f"Background task queued: {task.task_id}")
        except Exception as e:
            logger.error(f"Background task failed to queue: {e}")
    
    background_tasks.add_task(run_task)
    
    return TestTaskResponse(
        task_id="background-task",
        status="queued",
        message="Task queued via FastAPI BackgroundTasks (no task_id available)",
    )


# ─── Endpoint 6: Queue Failing Task (for testing error handling) ─────────────
@test_taskiq_router.post("/queue-failing", response_model=TestTaskResponse, status_code=202)
async def queue_failing_task(request: FailingTaskRequest):
    """
    Queue a test task that can intentionally fail.
    Used for testing error handling, retries, and audit logging.
    Use GET /test-taskiq/status/{task_id} to check result.
    """
    try:
        task = await failing_task.kiq(
            should_fail=request.should_fail,
            error_message=request.error_message
        )
        
        return TestTaskResponse(
            task_id=task.task_id,
            status="queued",
            message=f"Failing task queued. Check status at /test-taskiq/status/{task.task_id}",
        )
    except Exception as e:
        logger.exception("Failed to queue failing task")
        raise HTTPException(status_code=500, detail=f"Failed to queue failing task: {str(e)}")