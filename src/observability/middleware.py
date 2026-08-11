# src/observability/middleware.py
"""Pure ASGI request context middleware + Taskiq context propagation."""
import uuid
from typing import Any

import structlog
from taskiq.abc.middleware import TaskiqMiddleware
from taskiq.message import TaskiqMessage

from src.observability.context import (
    bind_request_context,
    clear_request_context,
    snapshot_context,
)


# ---------------------------------------------------------------------------
# FastAPI ASGI middleware (your existing code, kept intact)
# ---------------------------------------------------------------------------

class RequestContextMiddleware:
    """
    - Reads or generates `X-Trace-Id`
    - Binds trace_id, method, path, user_id to structlog contextvars
    - Echoes `X-Trace-Id` in response headers
    - Clears contextvars at the end (prevents leaks across requests)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        trace_id = headers.get("x-trace-id") or str(uuid.uuid4())
        user_id = headers.get("x-user-id")

        bind_request_context(
            trace_id=trace_id,
            method=scope["method"],
            path=scope["path"],
            user_id=user_id,
        )

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                hdrs.append((b"x-trace-id", trace_id.encode()))
                message["headers"] = hdrs
            await send(message)

        try:
            return await self.app(scope, receive, send_wrapper)
        finally:
            clear_request_context()


# ---------------------------------------------------------------------------
# Taskiq middleware — NEW
# ---------------------------------------------------------------------------

class TaskiqContextPropagationMiddleware(TaskiqMiddleware):
    """
    Propagate structlog contextvars from the sender (FastAPI)
    to the Taskiq worker via message labels.
    """

    async def pre_send(self, message: TaskiqMessage) -> TaskiqMessage:
        """Capture current structlog context and inject into task labels."""
        ctx = snapshot_context()
        for key, value in ctx.items():
            # Don't overwrite labels explicitly set by the task
            if key not in message.labels:
                message.labels[key] = value
        return message

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """Restore observability contextvars from labels in the worker."""
        observability_keys = {"trace_id", "method", "path", "user_id", "queue"}
        ctx = {k: v for k, v in message.labels.items() if k in observability_keys}
        # ← ADD: bind task_id so every log line in the worker includes it
        ctx["task_id"] = message.task_id
        if ctx:
            structlog.contextvars.bind_contextvars(**ctx)
        return message

    async def post_execute(self, message: TaskiqMessage, result: Any) -> None:
        """Clear context after successful task execution."""
        clear_request_context()

    async def on_error(
        self,
        message: TaskiqMessage,
        result: Any,
        exception: BaseException,
    ) -> None:
        """Clear context after failed task execution."""
        clear_request_context()