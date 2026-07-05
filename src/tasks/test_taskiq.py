# src/tasks/test_taskiq.py
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from taskiq import Context, TaskiqDepends
from typing import Annotated

from src.tk_broker import broker

logger = logging.getLogger(__name__)


# ─── Task 1: Simple Test Task ────────────────────────────────────────────────
@broker.task(
    task_name="src.tasks.test_taskiq:my_task",
    timeout=60.0,
    labels={"queue": "default", "test": "true"},
)
async def my_task(
    context: Annotated[Context, TaskiqDepends()] = None,
) -> Dict[str, Any]:
    """
    Simple test task with no parameters.
    Used for basic connectivity testing.
    """
    # Check if this task was marked as duplicate
    if context and context.message.labels.get("should_skip") == "true":
        task_id = context.message.task_id
        logger.info(f"Task {task_id} skipped (duplicate)")
        return {"status": "skipped_by_idempotency", "task_id": task_id}
    
    task_id = context.message.task_id if context else "unknown"
    
    logger.info(f"Executing my_task with task_id: {task_id}")
    
    # Simulate some work
    await asyncio.sleep(1)
    
    result = {
        "status": "done",
        "task_id": task_id,
        "message": "Simple task completed successfully",
    }
    
    logger.info(f"my_task completed: {result}")
    return result


# ─── Task 2: Test Task with Text Parameter ───────────────────────────────────
@broker.task(
    task_name="src.tasks.test_taskiq:my_task2",
    timeout=120.0,
    labels={"queue": "default", "test": "true"},
)
async def my_task2(
    text: str,
    delay: float = 0.0,
    context: Annotated[Context, TaskiqDepends()] = None,
) -> Dict[str, Any]:
    """
    Test task with text parameter.
    Used for testing parameter passing and idempotency.
    
    Args:
        text: Text to process
        delay: Optional delay in seconds (for testing long-running tasks)
        context: Taskiq context (injected automatically)
    
    Returns:
        Dictionary with processing results
    """
    # Check if this task was marked as duplicate
    if context and context.message.labels.get("should_skip") == "true":
        task_id = context.message.task_id
        logger.info(f"Task {task_id} skipped (duplicate)")
        return {"status": "skipped_by_idempotency", "task_id": task_id}
    
    task_id = context.message.task_id if context else "unknown"
    
    logger.info(f"Executing my_task2 with text: '{text}', delay: {delay}s, task_id: {task_id}")
    
    # Simulate work with optional delay
    if delay > 0:
        logger.info(f"my_task2: waiting {delay} seconds...")
        await asyncio.sleep(delay)
    else:
        await asyncio.sleep(0.5)  # Small default delay
    
    result = {
        "status": "done",
        "task_id": task_id,
        "text": text,
        "text_length": len(text),
        "delay": delay,
        "message": f"Processed text: '{text}'",
    }
    
    logger.info(f"my_task2 completed: {result}")
    return result


# ─── Task 3: Task That Can Fail (for testing error handling) ─────────────────
@broker.task(
    task_name="src.tasks.test_taskiq:failing_task",
    timeout=60.0,
    labels={"queue": "default", "test": "true"},
)
async def failing_task(
    should_fail: bool = True,
    error_message: str = "Intentional failure for testing",
    context: Annotated[Context, TaskiqDepends()] = None,
) -> Dict[str, Any]:
    """
    Test task that can intentionally fail.
    Used for testing error handling, retries, and audit logging.
    
    Args:
        should_fail: Whether to raise an exception
        error_message: Custom error message
        context: Taskiq context (injected automatically)
    """
    # Check if this task was marked as duplicate
    if context and context.message.labels.get("should_skip") == "true":
        task_id = context.message.task_id
        logger.info(f"Task {task_id} skipped (duplicate)")
        return {"status": "skipped_by_idempotency", "task_id": task_id}
    
    task_id = context.message.task_id if context else "unknown"
    
    logger.info(f"Executing failing_task with should_fail: {should_fail}, task_id: {task_id}")
    
    if should_fail:
        logger.error(f"failing_task: raising exception - {error_message}")
        raise ValueError(f"{error_message} (task_id: {task_id})")
    
    await asyncio.sleep(0.5)
    
    result = {
        "status": "done",
        "task_id": task_id,
        "message": "Task completed without failure",
    }
    
    logger.info(f"failing_task completed successfully: {result}")
    return result


# ─── Task 4: Long-Running Task (for testing timeouts and polling) ────────────
@broker.task(
    task_name="src.tasks.test_taskiq:long_running_task",
    timeout=300.0,  # 5 minutes
    labels={"queue": "heavy_io", "test": "true"},
)
async def long_running_task(
    duration: float = 10.0,
    context: Annotated[Context, TaskiqDepends()] = None,
) -> Dict[str, Any]:
    """
    Long-running test task for testing polling and timeouts.
    
    Args:
        duration: How long the task should run (seconds)
        context: Taskiq context (injected automatically)
    """
    # Check if this task was marked as duplicate
    if context and context.message.labels.get("should_skip") == "true":
        task_id = context.message.task_id
        logger.info(f"Task {task_id} skipped (duplicate)")
        return {"status": "skipped_by_idempotency", "task_id": task_id}
    
    task_id = context.message.task_id if context else "unknown"
    
    logger.info(f"Starting long_running_task for {duration}s, task_id: {task_id}")
    
    # Simulate long work with progress logging
    for i in range(int(duration)):
        await asyncio.sleep(1)
        if i % 5 == 0:  # Log every 5 seconds
            logger.info(f"long_running_task: {i}/{duration}s completed, task_id: {task_id}")
    
    result = {
        "status": "done",
        "task_id": task_id,
        "duration": duration,
        "message": f"Long task completed after {duration} seconds",
    }
    
    logger.info(f"long_running_task completed: {result}")
    return result


# ─── Task 5: Task with Multiple Parameters (for testing complex inputs) ──────
@broker.task(
    task_name="src.tasks.test_taskiq:complex_task",
    timeout=60.0,
    labels={"queue": "default", "test": "true"},
)
async def complex_task(
    user_id: int,
    file_id: str,
    options: Optional[Dict[str, Any]] = None,
    context: Annotated[Context, TaskiqDepends()] = None,
) -> Dict[str, Any]:
    """
    Test task with multiple parameters including nested dict.
    Used for testing complex input handling and hash generation.
    
    Args:
        user_id: User identifier
        file_id: File identifier
        options: Optional configuration dictionary
        context: Taskiq context (injected automatically)
    """
    # Check if this task was marked as duplicate
    if context and context.message.labels.get("should_skip") == "true":
        task_id = context.message.task_id
        logger.info(f"Task {task_id} skipped (duplicate)")
        return {"status": "skipped_by_idempotency", "task_id": task_id}
    
    task_id = context.message.task_id if context else "unknown"
    
    logger.info(
        f"Executing complex_task: user_id={user_id}, file_id={file_id}, "
        f"options={options}, task_id: {task_id}"
    )
    
    await asyncio.sleep(1)
    
    result = {
        "status": "done",
        "task_id": task_id,
        "user_id": user_id,
        "file_id": file_id,
        "options": options or {},
        "message": f"Processed file {file_id} for user {user_id}",
    }
    
    logger.info(f"complex_task completed: {result}")
    return result