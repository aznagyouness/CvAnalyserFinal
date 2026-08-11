# src/observability/context.py
"""Helpers for working with structlog contextvars."""
import structlog
from structlog.contextvars import get_contextvars


def bind_request_context(
    *,
    trace_id: str,
    method: str,
    path: str,
    user_id: str | None = None,
    extra: dict | None = None,
) -> None:
    """Bind request-scoped contextvars. Call once at request start."""
    payload = {
        "trace_id": trace_id,
        "method": method,
        "path": path,
    }
    if user_id is not None:
        payload["user_id"] = user_id
    if extra:
        payload.update(extra)
    structlog.contextvars.bind_contextvars(**payload)


def clear_request_context() -> None:
    """Clear all bound contextvars. Call at request end."""
    structlog.contextvars.clear_contextvars()


def snapshot_context() -> dict:
    """Snapshot current context as a plain dict (for cross-process handoff)."""
    return dict(get_contextvars())
