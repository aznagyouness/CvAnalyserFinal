# src/observability/logging.py
"""
structlog 26.1.0 production configuration.

Call `configure_logging()` ONCE at process startup, before any logging.
Idempotent. Reads everything from `settings` (no `os.getenv` anywhere).
"""
import ast
import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from src.helpers.config import get_settings

settings = get_settings()


# --- Custom processors ----------------------------------------------------

def _rename_level_to_severity(
    _: Any, __: str, event_dict: EventDict
) -> EventDict:
    """`level` → `severity` (uppercase) for OpenTelemetry / Grafana / Loki."""
    if "level" in event_dict:
        event_dict["severity"] = event_dict.pop("level").upper()
    return event_dict


def _add_service_metadata(
    _: Any, __: str, event_dict: EventDict
) -> EventDict:
    """Static fields injected on every log line."""
    event_dict.setdefault("service", settings.APPNAME)
    event_dict.setdefault("env", settings.ENVIRONMENT)
    event_dict.setdefault("version", settings.APPVERSION)
    return event_dict


def _drop_color_message_key(
    _: Any, __: str, event_dict: EventDict
) -> EventDict:
    """Uvicorn's access logger adds `color_message` for console output. Drop it in JSON mode."""
    event_dict.pop("color_message", None)
    return event_dict


def _extract_worker_info(
    _: Any, __: str, event_dict: EventDict
) -> EventDict:
    """
    Extract taskName / processName / process from the LogRecord.

    structlog's default conversion filters these out, but they're useful
    for multi-process / multi-worker setups (taskiq, gunicorn, etc.).
    The record is available via event_dict['_record'] for foreign records.

    Adds: worker_id ("worker-0"), process_name ("MainProcess"), pid (12345)
    """
    record = event_dict.get("_record")
    if record is not None:
        if hasattr(record, "taskName") and record.taskName:
            event_dict["worker_id"] = record.taskName
        if hasattr(record, "processName") and record.processName:
            event_dict["process_name"] = record.processName
        if hasattr(record, "process") and record.process:
            event_dict["pid"] = record.process
    return event_dict


def _expand_labels_string(
    _: Any, __: str, event_dict: EventDict
) -> EventDict:
    """
    Parse 'labels' string field back into individual fields.

    Taskiq stringifies the labels dict when logging via stdlib.
    We parse it back so the values are queryable in Loki/Postgres.

    Before: "labels": "{'queue': 'default', 'test': 'true'}"
    After:  "queue": "default", "test": "true"
    """
    if "labels" not in event_dict:
        return event_dict

    labels = event_dict["labels"]
    if not isinstance(labels, str):
        return event_dict
    if not (labels.startswith("{") and labels.endswith("}")):
        return event_dict

    try:
        parsed = ast.literal_eval(labels)
        if isinstance(parsed, dict):
            del event_dict["labels"]
            for k, v in parsed.items():
                event_dict.setdefault(k, v)
    except (ValueError, SyntaxError):
        pass  # not a valid dict literal, leave as-is

    return event_dict


# --- Environments that get pretty console output --------------------------

_DEV_ENVIRONMENTS: frozenset[str] = frozenset({
    "dev", "development", "local", "test", "testing", "ci",
})

# --- Custom processors ----------------------------------------------------

# we replace: structlog.processors.dict_tracebacks, With this custom processor:
def _safe_dict_tracebacks(logger, method_name, event_dict):
    """Like dict_tracebacks but removes locals to prevent secret leakage."""
    if "exception" in event_dict:
        for exc in event_dict.get("exception", []):
            for frame in exc.get("frames", []):
                frame.pop("locals", None)
    return event_dict
#dict_tracebacks dumps every local variable into your logs—API keys, passwords, tokens, and user data—turning a simple TimeoutError into a permanent secret leak in Loki or Datadog. _safe_dict_tracebacks keeps the full structured stack trace (exception type, file, line number, and call chain) so you still know exactly what broke and where, but strips the locals payload that holds your sensitive data. It gives you all the debugging power with none of the security risk: your logs help you fix bugs instead of causing compliance incidents.


# --- Main configuration ---------------------------------------------------

def configure_logging(
    log_level: str | None = None,
    json_output: bool | None = None,
) -> None:
    """
    Configure structlog. Call once at process startup.

    Single source of truth via settings:
        settings.ENVIRONMENT  → "development" uses console, anything else uses JSON
        settings.LOG_JSON     → explicit override; if set, wins over ENVIRONMENT
        settings.LOG_LEVEL    → "DEBUG" / "INFO" / "WARNING" / "ERROR"

    Python args override settings when explicitly passed.
    """
    # Level: arg > settings > default
    if log_level is None:
        log_level = settings.LOG_LEVEL.upper()
    level_int = getattr(logging, log_level, logging.INFO)

    # JSON output: arg > settings.LOG_JSON > infer from settings.ENVIRONMENT
    if json_output is None:
        if settings.LOG_JSON is not None:
            json_output = settings.LOG_JSON
        else:
            env_value = (settings.ENVIRONMENT or "").lower()
            json_output = env_value not in _DEV_ENVIRONMENTS

    # Processors shared by both JSON and console output AND foreign (stdlib) records
    shared_processors: list[Processor] = [
        # 1. Merge contextvars — MUST be first
        structlog.contextvars.merge_contextvars,
        # 2. Static service metadata
        _add_service_metadata,
        # 3. Logger name
        structlog.stdlib.add_logger_name,
        # 4. Level (renamed to severity later if JSON)
        structlog.processors.add_log_level,
        # 5. Callsite info — file:line:func, invaluable in prod
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            ],
        ),
        # 6. Stack info if present
        structlog.processors.StackInfoRenderer(),
        # 7. as dict not string 
        structlog.processors.dict_tracebacks,
        # 8. ISO UTC timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    # Processors that only apply to stdlib (foreign) records — they need
    # access to the LogRecord, which only exists for non-structlog logs.
    foreign_only_processors: list[Processor] = [
        _extract_worker_info,   # worker_id, process_name, pid
        _expand_labels_string,   # parse Taskiq's stringified labels
    ]

    # IMPORTANT: always use the stdlib logger factory. The renderer (JSON vs
    # Console) is the ONLY thing that differs between dev and prod. This is
    # the official structlog pattern and avoids the "PrintLogger has no .name"
    # bug you hit when mixing stdlib processors with PrintLoggerFactory.
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Renderer branch: pick the final processor based on output mode
    if json_output:
        final_processors: list[Processor] = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _drop_color_message_key,                  # remove uvicorn console key
            _rename_level_to_severity,                # level → severity
            structlog.processors.EventRenamer("message"),
            _safe_dict_tracebacks,                  #  as structured dict, not strings
            structlog.processors.JSONRenderer(sort_keys=True),
        ]
    else:
        final_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # The official structlog↔stdlib bridge.
    # structlog records  → shared_processors + wrap_for_formatter → final_processors
    # stdlib records     → shared_processors + foreign_only_processors → final_processors
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors + foreign_only_processors,
        processors=final_processors,
    )

    # Force line buffering for stdout (prevents delayed/missing logs in Docker/K8s).
    # Also set PYTHONUNBUFFERED=1 in your container env to cover non-logging writes.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Clear any default handlers (uvicorn installs its own; basicConfig too)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level_int)

    # Quiet down chatty stdlib loggers; they'll still propagate through the bridge
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        stdlib_logger = logging.getLogger(noisy)
        stdlib_logger.handlers = []
        stdlib_logger.propagate = True
        stdlib_logger.setLevel(level_int)

    # Add these to your "noisy" list alongside sqlalchemy.engine
    # --- Infrastructure Log Level (DB, Queue, Workers) ---
    infra_level_str = settings.INFRA_LOG_LEVEL.upper()
    infra_level_int = getattr(logging, infra_level_str, logging.WARNING)

    noisy_internals = [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "taskiq.receiver",
        "taskiq.process-manager",
        "taskiq.worker",
        # Add new libraries here as they appear (e.g., "httpx", "redis")
    ]
    for name in noisy_internals:
        logger = logging.getLogger(name)
        logger.handlers = []        # ← ADD: remove taskiq's plain-text handlers
        logger.propagate = True     # ← ADD: route through root JSON formatter
        logger.setLevel(infra_level_int)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Use this everywhere instead of `structlog.get_logger()` directly."""
    return structlog.get_logger(name)