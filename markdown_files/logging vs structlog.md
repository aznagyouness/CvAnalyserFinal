# I - the benifit that tells why i will choose it over logging 

Here is why you choose `structlog` over Python's standard `logging`:

*   **Structured Data (JSON):** Outputs machine-readable JSON instead of unparseable strings, making it instantly compatible with log aggregators (Datadog, ELK, Splunk).
collecting as json makes your logs querible and i can filter it by user or error type or whatever

the ultimate superpower of structured logging. 

With standard `logging`, finding "all errors for user 42" means writing fragile `grep` commands or complex Regex. 

With **structlog JSON**, you just query it like a database. 

You can instantly pivot from *"Show me all errors"* to *"Show me all errors for user 42 on the `/checkout` endpoint in the last 5 minutes."* 

That is exactly why it's the industry standard for modern applications.
*   **Effortless Context Binding:** Use `log.bind(user_id=123)` to automatically attach context to *all* subsequent logs. No need to build complex `LoggerAdapter` or custom filter setups.
*   **Data as Arguments, Not Strings:** Pass data as keyword arguments (`log.info("event", key="value")`) instead of messy f-strings. Data stays typed and structured.
*   **Dev vs. Prod Flexibility:** Use the exact same log statements, but output pretty/colorful text in local dev and strict JSON in production.
*   **Async-Safe Context:** Built-in `contextvars` automatically propagates context (like `request_id`) across async tasks without manually passing logger objects through function parameters.
*   **Third-Party Interop:** Seamlessly intercepts and reformats standard `logging` calls from third-party libraries (like SQLAlchemy, Celery, or Django) into your structured format.

 

# II - 🎓 Welcome to Structlog 26.1.0 — The Masterclass

> *"Grab a seat, get comfortable, and by the end of this lesson, you'll never want to go back to `print()` debugging again."*

---

## 📖 PART 1: The "Why" — Before We Touch Any Code

Imagine you're running a web service with 50 microservices. Something breaks at 3 AM. You open your logs and see:

```
ERROR: Something went wrong
ERROR: Failed
INFO: Done
```

**Useless.** Which service? Which user? Which request? 😩

Now imagine seeing this instead:

```json
{
  "event": "payment_failed",
  "level": "error",
  "user_id": "u_4829",
  "order_id": "ord_99123",
  "amount": 49.99,
  "currency": "USD",
  "timestamp": "2026-07-20T03:14:22.001Z",
  "trace_id": "abc123def456"
}
```

**Instant clarity.** You know *exactly* what happened, to whom, and when.

> 🧠 **Key Insight:** `structlog` turns your logs from **unstructured strings** into **structured data** (dictionaries/JSON). That's it. That's the superpower.

---

## 📦 PART 2: Installation

```bash
pip install structlog==26.1.0
```

Structlog uses **CalVer** (Calendar Versioning), so `26.1.0` = **January 2026** release. This means you're getting a modern, mature, battle-tested library.

---

## 🚀 PART 3: Your First Log (30 Seconds to "Aha!")

```python
import structlog

# Zero configuration — it just works out of the box!
log = structlog.get_logger()

log.info("user_logged_in", user_id=42, method="oauth")
```

**Output (dev mode, pretty-printed):**
```
[info     ] user_logged_in                 method=oauth user_id=42
```

Notice what happened:
- ✅ The **event name** (`user_logged_in`) is separate from the **data** (`user_id`, `method`)
- ✅ Everything is **key=value** — structured!
- ✅ No f-strings. No string formatting. **Data stays data.**

> 🎯 **Teacher's Rule #1:** Never put data inside the message string. Always pass it as keyword arguments.

---

## ⚙️ PART 4: Configuration — The Processor Pipeline

This is the **heart** of structlog. Think of it like an **assembly line** in a factory:

```
Log Event → [Processor 1] → [Processor 2] → [Processor 3] → Output
```

Each processor **transforms** the log event before it reaches the final output.

### The Modern Production Setup (26.1.0)

```python
import logging
import structlog

structlog.configure(
    processors=[
        # 1️⃣ Add contextvars (request-scoped data) to every log
        structlog.contextvars.merge_contextvars,

        # 2️⃣ Add the log level to the event dict
        structlog.processors.add_log_level,

        # 3️⃣ Add a timestamp
        structlog.processors.TimeStamper(fmt="iso"),

        # 4️⃣ Format the exception stack trace (if any)
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,

        # 5️⃣ FINAL STEP: Render as JSON for production
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.WriteLoggerFactory(),
    cache_logger_on_first_use=True,  # ⚡ Performance boost!
)

log = structlog.get_logger()
log.info("server_started", port=8080, workers=4)
```

**Output:**
```json
{"port": 8080, "workers": 4, "event": "server_started", "level": "info", "timestamp": "2026-07-20T10:30:00.123456Z"}
```

### Let's Break Down Each Piece:

| Component | What It Does | Analogy |
|---|---|---|
| **`processors`** | The assembly line — transforms your log step by step | Factory workers |
| **`wrapper_class`** | Controls which log levels are active (filters `DEBUG` if set to `INFO`) | Bouncer at a club |
| **`logger_factory`** | Decides *where* logs go (stdout, file, etc.) | Mail carrier |
| **`cache_logger_on_first_use`** | Caches the logger for performance | Speed dial |

---

## 🔄 PART 5: Dev vs. Production — The Two-Mode Pattern

This is a **best practice** you'll use in every real project:

```python
import sys
import logging
import structlog

def configure_logging(environment: str = "production"):
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if environment == "development":
        # 🎨 Pretty, colorful output for your terminal
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # 🤖 Machine-readable JSON for log aggregators (ELK, Datadog, etc.)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if environment == "development" else logging.INFO
        ),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage:
configure_logging("development")
log = structlog.get_logger()
log.warning("disk_space_low", percent_remaining=4.2, host="web-03")
```

**Dev output (colorful!):**
```
[warning  ] disk_space_low                 host=web-03 percent_remaining=4.2
```

**Prod output:**
```json
{"event": "disk_space_low", "level": "warning", "percent_remaining": 4.2, "host": "web-03", "timestamp": "..."}
```

---

## 🧩 PART 6: Binding Context — The Real Magic

### What is "binding"?

Binding means **attaching persistent context** to a logger so every subsequent log includes that data automatically.

```python
log = structlog.get_logger()

# Bind user context once...
user_log = log.bind(user_id="u_4829", tenant="acme_corp")

# ...and it appears in EVERY log automatically!
user_log.info("page_viewed", page="/dashboard")
user_log.info("button_clicked", button="export_csv")
user_log.warning("rate_limit_approaching", requests=980, limit=1000)
```

**Output:**
```json
{"user_id": "u_4829", "tenant": "acme_corp", "event": "page_viewed", "page": "/dashboard", ...}
{"user_id": "u_4829", "tenant": "acme_corp", "event": "button_clicked", "button": "export_csv", ...}
{"user_id": "u_4829", "tenant": "acme_corp", "event": "rate_limit_approaching", ...}
```

> 🎯 **Teacher's Rule #2:** Bind early, bind often. Request ID, user ID, tenant — bind them at the start of the request.

---

## 🌐 PART 7: Context Variables (Async-Safe Magic)

In modern async Python (FastAPI, aiohttp, etc.), you can't just pass loggers around everywhere. `structlog.contextvars` solves this:

```python
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

async def handle_request(request):
    clear_contextvars()  # 🧹 Clean slate for each request

    # Bind once — available to ALL code in this request, even deep in the call stack!
    bind_contextvars(
        request_id=request.headers.get("X-Request-ID"),
        user_id=request.user.id,
        path=request.url.path,
    )

    log = structlog.get_logger()
    log.info("request_started")  # Automatically includes request_id, user_id, path!

    # ... 10 layers deep in your code ...
    await process_payment()  # This function's logs ALSO get the context!
```
example in fastapi route:

```python
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from fastapi import FastAPI, Request
import uuid

log = structlog.get_logger()

@data_router.get("/ping_structlog")
async def ping(request: Request):
    # 1. Clear any leftover context (safety net)
    clear_contextvars()

    try:
        # 2. Bind request-scoped fields
        bind_contextvars(
            request_id=request.headers.get("X-Request-ID", str(uuid.uuid4())),
            user_id=request.headers.get("X-User-ID", "anonymous"),
            path=request.url.path,
        )

        # 3. Any log call inside this try block will include the bindings
        log.info("request_started")

        # Simulate deep call chain
        result = await do_work()

        log.info("request_completed", status=200)
        return {"status": "ok"}

    finally:
        # 4. CRITICAL: clear to avoid leaking to the next request
        clear_contextvars()

async def do_work():
    # This function also gets the context automatically
    log = structlog.get_logger()
    log.info("working...")   # includes request_id, user_id, path
    return "done"
```
> 🧠 **Why this matters:** No more passing `logger` objects through 15 function parameters. Context flows automatically through async tasks and threads.

---

## 🔗 PART 8: Integration with Standard Library Logging

Many libraries (Django, SQLAlchemy, Celery) use Python's built-in `logging`. Structlog can **capture and format** those logs too:

```python
import logging
import structlog

# Configure stdlib logging to use structlog's formatter
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
)

# Make stdlib logs go through structlog's processors
structlog.stdlib.recreate_defaults(log_level=logging.INFO)

# Now third-party library logs are ALSO structured! 🎉
```

---

## 🧪 PART 9: Testing Your Logs

Structlog ships with a **testing module** — because yes, you should test your logs!

```python
from structlog.testing import CapturingLogger

def test_payment_logging():
    cap_logger = CapturingLogger()
    log = structlog.get_logger().bind(logger=cap_logger)

    process_payment(amount=100)

    # Assert that the right log was emitted!
    assert len(cap_logger.calls) == 1
    assert cap_logger.calls[0].method_name == "info"
    assert cap_logger.calls[0].kwargs["event"] == "payment_processed"
    assert cap_logger.calls[0].kwargs["amount"] == 100
```

---

## ⚡ PART 10: Performance Tips (26.1.0)

| Tip | Impact |
|---|---|
| `cache_logger_on_first_use=True` | Avoids re-creating the logger pipeline on every call |
| Use `structlog.make_filtering_bound_logger()` | Drops filtered logs *before* running processors (huge savings!) |
| Avoid `structlog.stdlib.BoundLogger` in hot paths | `make_filtering_bound_logger` is significantly faster |
| Use `WriteLoggerFactory` over `PrintLoggerFactory` | `print()` is surprisingly slow; `sys.stdout.write` is faster |

---

## 📋 PART 11: The Complete Cheat Sheet

```python
import structlog

log = structlog.get_logger()

# Basic logging
log.debug("checking_cache", key="user:42")
log.info("cache_miss", key="user:42")
log.warning("retry_attempt", attempt=3, max=5)
log.error("payment_failed", error="insufficient_funds")
log.critical("database_down", host="db-primary")

# Binding context
log = log.bind(request_id="abc123")

# Temporary context (with statement)
with structlog.contextvars.bound_contextvars(job_id="j_999"):
    log.info("job_started")  # includes job_id

# Exceptions
try:
    1 / 0
except ZeroDivisionError:
    log.exception("math_broke")  # Automatically captures the traceback!
```

---

## 🎓 Final Exam — Key Takeaways

1. **Structure over strings.** Data as kwargs, not f-strings.
2. **Processors are the pipeline.** Each one transforms the log event.
3. **Dev = pretty, Prod = JSON.** Switch the renderer, keep the processors.
4. **Bind context early.** Request ID, user ID — bind at the entry point.
5. **Use `contextvars` for async.** It flows through your entire call stack.
6. **Filter early.** `make_filtering_bound_logger` drops logs before processing.
7. **Test your logs.** `structlog.testing` makes it easy.

---

> 🏆 *"You now know more about structured logging than 90% of Python developers. Go forth and log responsibly!"*

Any questions? Want me to dive deeper into any specific area — like FastAPI integration, custom processors, or log aggregation pipelines? Just ask! 🙋‍♂️

# III - 🎓  structlog 26.1.0 — Production Guide

**Pinned versions:** `structlog==26.1.0` · `fastapi==0.136.3` · `uvicorn[standard]==0.40.0` · `taskiq==0.12.4`

Two setups covered:
- **Part A** — FastAPI alone
- **Part B** — FastAPI + Taskiq (with cross-process trace propagation)

---

## Table of Contents

1. [Why structlog over stdlib `logging`](#1-why-structlog-over-stdlib-logging)
2. [Core concepts you must know](#2-core-concepts-you-must-know)
3. [The production config](#3-the-production-config)
4. [Part A — FastAPI alone](#4-part-a--fastapi-alone)
5. [Part B — FastAPI + Taskiq](#5-part-b--fastapi--taskiq)
6. [Exception logging](#6-exception-logging)
7. [Error Tracking & Observability (No-Sentry Stack)](#7-error-tracking--observability-no-sentry-stack)
8. [Performance notes](#8-performance-notes)
9. [Anti-patterns](#9-anti-patterns)
10. [Production checklist](#10-production-checklist)

---

## 1. Why structlog over stdlib `logging`

- **Structured JSON output by default** — queryable in Grafana Loki, Datadog, or OpenObserve
- **Processor pipeline** — composable, testable
- **Native `contextvars` support** — request-scoped fields with zero plumbing
- **Type-friendly** — `bound_logger` is annotated, IDE autocomplete works
- **Drop-in compatible with stdlib** — works alongside `logging.getLogger("uvicorn")`

The stdlib's `extra={"foo": "bar"}` only works with the right formatter. structlog makes structured logging the default, not the exception.

---

## 2. Core concepts you must know

### 2.1 The processor chain

structlog processes each log event through a list of **processors** in order:

```text
log.info("payment_processed", amount=100)
        │
        ▼
┌─────────────────────────────────────────────┐
│ 1. contextvars.merge_contextvars            │  ← adds trace_id, user_id
│ 2. add_logger_name                          │
│ 3. add_log_level                            │
│ 4. CallsiteParameterAdder                   │  ← module, lineno, func
│ 5. StackInfoRenderer                        │
│ 6. dict_tracebacks                          │  ← structured exceptions
│ 7. TimeStamper (utc=True)                   │
│ 8. EventRenamer("message")                  │
│ 9. JSONRenderer                             │  ← final output
└─────────────────────────────────────────────┘
        │
        ▼
{"message": "payment_processed", "amount": 100, "trace_id": "...", ...}
```

Order matters. `merge_contextvars` must be early so subsequent processors see the bound vars. `JSONRenderer` must be last (it's the renderer).

### 2.2 `bind` vs `contextvars` — the #1 gotcha

| | `logger.bind(x=1)` | `structlog.contextvars.bind_contextvars(x=1)` |
|---|---|---|
| Scope | This Python object forever | Current `asyncio.Task` |
| Affects other loggers? | Only the bound copy | All loggers in the same task |
| Use in server code? | **NO** | Yes |
| Use in one-off scripts? | Yes | Doesn't matter |

In a server, **always** use `contextvars`. `bind` at module level leaks the previous request's data into the next request.

### 2.3 Log levels

structlog uses string levels (`"info"`, `"error"`, etc.) by default. We rename to `severity` (uppercase) for OpenTelemetry/Loki/Grafana convention.

Filtering happens via `wrapper_class=structlog.make_filtering_bound_logger(LEVEL)`. Without this, **everything logs** (including DEBUG in production).

---

## 3. The production config

This file is shared by both Part A and Part B. Put it in `src/observability/logging.py`.

```python
# src/observability/logging.py
"""
structlog 26.1.0 production configuration.

Call `configure_logging()` ONCE at process startup, before any logging.
Idempotent. Read LOG_LEVEL and LOG_JSON from env.
"""
import logging
import os
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


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
    event_dict.setdefault("service", os.getenv("SERVICE_NAME", "unknown"))
    event_dict.setdefault("env", os.getenv("ENV", "dev"))
    event_dict.setdefault("version", os.getenv("APP_VERSION", "0.0.0"))
    return event_dict


def _drop_color_message_key(
    _: Any, __: str, event_dict: EventDict
) -> EventDict:
    """Uvicorn's access logger adds `color_message` for console output. Drop it in JSON mode."""
    event_dict.pop("color_message", None)
    return event_dict


# --- Main configuration ---------------------------------------------------

def configure_logging(
    log_level: str | None = None,
    json_output: bool | None = None,
) -> None:
    """
    Configure structlog. Call once at process startup.

    Env vars:
        LOG_LEVEL   (default INFO)
        LOG_JSON    (default true; set to "false" for dev console output)
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if json_output is None:
        json_output = os.getenv("LOG_JSON", "true").lower() == "true"

    level_int = getattr(logging, log_level, logging.INFO)

    # Processors shared by both JSON and console output
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
        # 7. Exceptions as structured dict, not strings
        structlog.processors.dict_tracebacks,
        # 8. ISO UTC timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if json_output:
        # Production: structured JSON
        # IMPORTANT: last structlog processor is `wrap_for_formatter`, which
        # hands the partially-processed event_dict to stdlib as a LogRecord.
        # `ProcessorFormatter` then finishes the rendering. This is the
        # ONLY way to get uvicorn/sqlalchemy/etc. through the same chain.
        final_structlog_processor = structlog.stdlib.ProcessorFormatter.wrap_for_formatter
        # The ProcessorFormatter is built below (needs `shared_processors`)
        logger_factory: structlog.types.LoggerFactory = structlog.stdlib.LoggerFactory()
    else:
        # Dev: human-readable console, no stdlib bridge needed
        final_structlog_processor = structlog.dev.ConsoleRenderer(colors=True)
        logger_factory = structlog.PrintLoggerFactory(file=sys.stdout)

    # Wire structlog
    structlog.configure(
        processors=shared_processors + [final_structlog_processor],
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        context_class=dict,
        logger_factory=logger_factory,
        cache_logger_on_first_use=True,  # perf — important under load
    )

    if not json_output:
        return  # no stdlib bridge needed for dev

    # The official structlog↔stdlib bridge.
    # Both structlog records AND stdlib records (uvicorn, sqlalchemy, etc.)
    # go through the SAME processor chain and emit the SAME JSON shape.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,         # applied to stdlib records
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _drop_color_message_key,                  # remove uvicorn console key
            _rename_level_to_severity,                # level → severity
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Clear any default handlers (uvicorn installs its own; basicConfig too)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level_int)

    # Quiet down chatty stdlib loggers; they'll still propagate as JSON
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        stdlib_logger = logging.getLogger(noisy)
        stdlib_logger.handlers = []
        stdlib_logger.propagate = True
        stdlib_logger.setLevel(level_int)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Use this everywhere instead of `structlog.get_logger()` directly."""
    return structlog.get_logger(name)
```

### What you get

Every log line in JSON mode looks like:
```json
{
  "message": "payment_processed",
  "severity": "INFO",
  "timestamp": "2026-07-19T18:30:53.123Z",
  "service": "mini-rag-api",
  "env": "prod",
  "version": "1.2.3",
  "logger": "src.services.payment",
  "module": "src.services.payment",
  "lineno": 42,
  "func_name": "charge",
  "trace_id": "abc-123",
  "user_id": "u-42",
  "amount_cents": 5000
}
```

That's the level of structure that makes monitoring tools actually useful.

#### Why event_dict.setdefault("service", settings.APPNAME) and event_dict.setdefault("env", settings.ENV) are highly recommended for production

##### 1. service Field
- **Purpose**: Identifies which application the log is coming from.
- **Use Case**: If you have multiple services (e.g., CvanalyserFinal, another API, a worker) logging to the same place (like Grafana Loki, Datadog, or ELK), this field lets you filter logs to just CvanalyserFinal.
- **Example**: In Grafana, you could run a query like {service="essai-for-celery"} to see only this app's logs.

##### 2. env Field
- **Purpose**: Tells you which environment the log is from (dev, staging, prod).
- **Use Case**: This is critical for triaging errors—you don't want to spend hours debugging a log only to realize it's from a development environment.
- **Example**: In Grafana Loki: {service="essai-for-celery", env="prod"} to see only production logs.

##### When They Might Not Be Strictly Necessary
- If this is a small, single-environment, single-service project with no centralized logging, you could skip them.
- But given that your project already has Docker, Prometheus, Grafana, Taskiq, etc., it's set up like a production app, so these fields are valuable.

##### Summary
- **Is it required for the code to run?** No.
- **Is it a production best practice?** Yes! It makes debugging and monitoring way easier.


---

## 4. Part A — FastAPI alone

### 4.1 File layout

```text
src/
├── observability/
│   ├── __init__.py
│   ├── logging.py        # from §3
│   ├── context.py        # contextvars helpers
│   └── middleware.py     # ASGI middleware
├── main.py
└── ...
```

### 4.2 `src/observability/context.py`

```python
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
```

### 4.3 `src/observability/middleware.py`

Pure ASGI middleware (NOT `BaseHTTPMiddleware` — see notes in §8).

```python
"""Pure ASGI request context middleware."""
import uuid

from src.observability.context import (
    bind_request_context,
    clear_request_context,
)


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

        # 1. Extract or generate trace_id
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        trace_id = headers.get("x-trace-id") or str(uuid.uuid4())

        # 2. Optional: extract user_id from auth header (or do it in a dep)
        user_id = headers.get("x-user-id")  # simplified; use proper auth in real code

        # 3. Bind context
        bind_request_context(
            trace_id=trace_id,
            method=scope["method"],
            path=scope["path"],
            user_id=user_id,
        )

        # 4. Wrap send to inject header into response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                hdrs.append((b"x-trace-id", trace_id.encode()))
                message["headers"] = hdrs
            await send(message)

        try:
            return await self.app(scope, receive, send_wrapper)
        finally:
            # 5. CRITICAL: clear so next request doesn't inherit
            clear_request_context()
```

### 4.4 `src/main.py`

```python
from fastapi import FastAPI
from src.observability.logging import configure_logging
from src.observability.middleware import RequestContextMiddleware
from src.routes.nlp import nlp_router

# 1. Configure logging FIRST — before anything else logs
configure_logging()

# 2. Build app
app = FastAPI(title="mini-rag", version="0.2.0")

# 3. Add middleware (executed in REVERSE order of registration,
#    but `RequestContextMiddleware` should be the OUTERMOST, so add it LAST
#    OR use `add_middleware` correctly)
app.add_middleware(RequestContextMiddleware)

# 4. Mount routers
app.include_router(nlp_router, prefix="/api/v1")
```

### 4.5 Usage in route handlers and services

```python
# src/routes/payment.py
from fastapi import APIRouter
from src.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/charge")
async def charge(amount_cents: int):
    # No bind needed — trace_id, method, path are already in context
    log.info("charge_started", amount_cents=amount_cents)

    try:
        result = await _do_charge(amount_cents)
        log.info("charge_succeeded", amount_cents=amount_cents, txn_id=result.txn_id)
        return {"status": "ok", "txn_id": result.txn_id}
    except Exception as e:
        # log.exception auto-attaches structured exception info
        log.exception("charge_failed", amount_cents=amount_cents)
        raise
```

Output (JSON):
```json
{
  "message": "charge_succeeded",
  "severity": "INFO",
  "timestamp": "2026-07-19T18:30:53.123Z",
  "service": "mini-rag-api",
  "logger": "src.routes.payment",
  "module": "src.routes.payment",
  "lineno": 14,
  "func_name": "charge",
  "trace_id": "abc-123",
  "method": "POST",
  "path": "/payments/charge",
  "amount_cents": 5000,
  "txn_id": "pi_abc"
}
```

### 4.6 Access log middleware (HTTP request/response logging)

Beyond the trace-context middleware, you want a **dedicated access log** that records the response status, latency, and size for every request. This is the most-queried log stream in production.

```python
# src/observability/access_log.py
"""Structured access log middleware."""
import time
from src.observability.logging import get_logger

log = get_logger("access")


class AccessLogMiddleware:
    """Pure ASGI. Logs after the response is fully sent."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.perf_counter()
        status_holder = {"status": 500}
        bytes_holder = {"sent": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            elif message["type"] == "http.response.body":
                bytes_holder["sent"] += len(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            # info for 2xx/3xx, warning for 4xx, error for 5xx
            severity = (
                "error" if status_holder["status"] >= 500
                else "warning" if status_holder["status"] >= 400
                else "info"
            )
            log.log(
                severity,
                "http_request",
                method=scope["method"],
                path=scope["path"],
                status=status_holder["status"],
                duration_ms=round(duration_ms, 2),
                response_bytes=bytes_holder["sent"],
            )
```

Wire it up in `main.py`. **Register `AccessLogMiddleware` first**, so `RequestContextMiddleware` becomes the **outer** wrapper in the request flow:
```python
# Starlette runs middleware in REVERSE order of registration.
# Registering AccessLogMiddleware first makes RequestContextMiddleware the
# outermost wrapper, which is what we want: it binds trace_id BEFORE the
# access logger emits its log line, so the access log carries trace_id.
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestContextMiddleware)
```

Output:
```json
{
  "message": "http_request",
  "severity": "INFO",
  "timestamp": "2026-07-19T18:30:53.123Z",
  "trace_id": "abc-123",
  "method": "POST",
  "path": "/payments/charge",
  "status": 200,
  "duration_ms": 87.42,
  "response_bytes": 142
}
```

> **Tip:** Disable uvicorn's built-in access log when you use this — it's redundant and produces duplicate lines. Pass `--no-access-log` to uvicorn, or set `log_config=None` (see §4.7).

### 4.7 Uvicorn integration: pass `log_config=None`

By default, uvicorn installs its own logging config that conflicts with yours. Disable it:

```python
# src/main.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=None,        # ← let our structlog config own everything
        access_log=False,       # ← AccessLogMiddleware handles this
    )
```

In production under a process manager (gunicorn/supervisor), the equivalent is to configure the entry point the same way. This avoids the classic double-logging problem where uvicorn's basicConfig fights your structlog bridge.

---

## 5. Part B — FastAPI + Taskiq

The complication: Taskiq runs in a **separate process** (or at least a separate `asyncio.Task`). The `contextvars` from the FastAPI request do **not** propagate automatically. You must pass them explicitly.

### 5.1 Updated file layout

```text
src/
├── observability/
│   ├── __init__.py
│   ├── logging.py        # from §3 (unchanged)
│   ├── context.py        # from §4.2 (unchanged)
│   └── middleware.py     # FastAPI ASGI middleware (unchanged)
├── tasks/
│   ├── __init__.py
│   ├── broker.py         # Taskiq broker setup
│   ├── middleware.py     # Taskiq middleware (binds contextvars per task)
│   └── ingestion.py      # actual tasks
├── main.py
└── ...
```
Yes! If you want complete, linked logs in Grafana for both FastAPI requests AND their related Taskiq tasks, you definitely need this middleware!

### Why?
1. Links FastAPI → Taskiq Logs : It passes the trace_id (and other context) from your FastAPI request to your Taskiq tasks, so you can see all logs from a single request in Grafana.
2. Task Metadata : Adds task_id and task_name to Taskiq logs, so you know exactly which task is logging what.
3. Prevents Leaks : Clears context after each task to avoid mixing up data between different tasks.
### If You Didn't Add It:
- Your Taskiq logs wouldn't have trace_id , so you couldn't link them to the original FastAPI request in Grafana.
- Task logs wouldn't have task_id / task_name to identify which task they're from.
So yes—add it! 😊

### 5.2 `src/tasks/middleware.py`

```python
"""Taskiq middleware: bind contextvars per task execution."""
import structlog
from taskiq import TaskiqMessage, TaskiqResult


class TaskContextMiddleware:
    """
    - Bind contextvars from `message.labels` (passed from FastAPI) and task metadata
    - Clear on exit (prevent leaks)
    """

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        structlog.contextvars.bind_contextvars(
            task_id=message.task_id,
            task_name=message.task_name,
            **(message.labels or {}),
        )
        return message

    async def post_execute(
        self,
        message: TaskiqMessage,
        result: TaskiqResult,
        exc: Exception | None = None,
    ) -> None:
        structlog.contextvars.clear_contextvars()
```

### 5.3 `src/tasks/broker.py`

```python
from src.tasks.middleware import TaskContextMiddleware

broker = broker.with_middlewares(
    TaskContextMiddleware(),  # ← ADD THIS FIRST
    PrometheusMiddleware(server_addr="0.0.0.0", server_port=9000),
    SimpleRetryMiddleware(default_retry_count=3),
    idempotency_middleware,
)
```
we put TaskContextMiddleware() first in the middleware list:

#### Why First?
1. Order Matters for Taskiq Middlewares : Taskiq middlewares run in the order you add them for pre_execute() (and reverse order for post_execute() ).
2. Bind Context EARLY : We want to bind the trace_id , task_id , and message.labels to structlog's contextvars before any other middleware runs (like PrometheusMiddleware or SimpleRetryMiddleware).
3. All Logs Get Context : If we put it first, every log from every middleware and the task itself will automatically include the context fields! If we put it later, some logs from earlier middlewares would miss the context!

Middleware order:
1. TaskContextMiddleware → Binds context
2. PrometheusMiddleware → Logs now have context!
3. SimpleRetryMiddleware → Logs now have context!
4. Task itself → Logs now have context!

### 5.4 task definition : `src/tasks/ingestion.py`
every task should have this : you put this specially the `from src.observability.logging import get_logger` and  `log = get_logger(__name__)`
```python
from src.tasks.broker import broker
from src.observability.logging import get_logger
from src.exceptions import (
    ProjectNotFoundError, EmbeddingError, VectorDBInsertError,
)

log = get_logger(__name__)
#............
log.info("indexing_completed", indexed=len(document_ids))
# the indexed is a context variable you choose & you ll see in the logs
```
detailed example : 
```python
from src.tasks.broker import broker
from src.observability.logging import get_logger
from src.exceptions import (
    ProjectNotFoundError, EmbeddingError, VectorDBInsertError,
)

log = get_logger(__name__)


@broker.task(retry_on=(EmbeddingError,))
async def index_project_task(project_id: str, document_ids: list[str]):
    """
    Index documents for a project. Receives `project_id` and `document_ids`.

    Note: trace_id and user_id are NOT in the signature — they come from
    `message.labels` (set by the FastAPI route) and are bound to contextvars
    by `TaskContextMiddleware`.
    """
    # Bind task-specific context
    structlog.contextvars.bind_contextvars(
        project_id=project_id,
        doc_count=len(document_ids),
    )

    log.info("indexing_started")

    project = await _fetch_project(project_id)
    if not project:
        # Terminal — Taskiq will NOT retry (not in retry_on)
        log.error("project_not_found")
        raise ProjectNotFoundError(project_id)

    try:
        for doc_id in document_ids:
            await _process_document(project_id, doc_id)
    except EmbeddingError as e:
        # Transient — Taskiq WILL retry (in retry_on)
        log.warning("embedding_error_will_retry", exc_info=True)
        raise
    except VectorDBInsertError as e:
        # Terminal — won't retry
        log.error("vectordb_insert_failed_terminal", exc_info=True)
        await _mark_project_status(project_id, "FAILED", reason=str(e))
        raise

    log.info("indexing_completed", indexed=len(document_ids))
    return {"indexed": len(document_ids)}
```
### 5.5 in FastAPI routes`src/routes/nlp.py` — kicking tasks with context

After this, trace_id from the FastAPI request propagates to the worker logs. One line. The 3am-debugging-payback is enormous.
without it : you will  ask which request has related to the task failure. ==> you ll not know task has not trace_id ( the key for each request)--> you ask the client to give you the endpoint, the time ... not professional !!! 
solution : give he worker log the trace_id of each request with `from src.observability.context import snapshot_context` `ctx = snapshot_context()` `.kiq(labels=ctx,)`

```python
from fastapi import APIRouter
from src.observability.context import snapshot_context
from src.tasks.ingestion import index_project_task

router = APIRouter(prefix="/api/v1/nlp", tags=["nlp"])


@router.post("/index/push/{project_id}", status_code=202)
async def trigger_indexing(project_id: str):
    project = await _fetch_project(project_id)
    if not project:
        raise ProjectNotFoundError(project_id)

    # Snapshot the current contextvars (trace_id, user_id, project_id, etc.)
    # and pass them as Taskiq `labels` so the worker can rebind them.
    ctx = snapshot_context()

    # Pass ALL bound contextvars. Don't filter to just trace_id/user_id —
    # the worker's logs need the full context (project_id is critical for
    # RAG task logs). Contextvars are small strings/IDs; total payload is
    # typically < 1KB. See §5.5.1 for the anti-pattern to avoid.
    await index_project_task.kiq(
        project_id=project_id,
        document_ids=project.document_ids,
        labels=ctx,  # ⬅️ This is the handoff
    )

    return {
        "message": "Indexing started",
        "project_id": project_id,
        "status_url": f"/api/v1/nlp/status/{project_id}",
    }
```

in the task definition : 
```python
@broker.task
async def my_task2(
    text: str,
    delay: float,
    ctx: Context = TaskiqDepends(), # the context propagation has done here 
):
    task_id = ctx.message.task_id
    task_name = ctx.message.task_name
    labels = ctx.message.labels  # your snapshot_context dict
    log.info("task started", task_id=task_id, task_name=task_name, labels=labels)
```

### 5.5.1 Don't filter the snapshot to "essentials"

A common-but-wrong suggestion is to filter `snapshot_context()` to only trace_id/user_id before passing as labels:

```python
# ❌ WRONG — this breaks the handoff
ctx = {k: v for k, v in snapshot_context().items() if k in {"trace_id", "user_id"}}
await task.kiq(..., labels=ctx)
```

**Why it's wrong:**
- The whole point of `snapshot_context()` is to propagate **all** bound contextvars to the worker
- For a RAG system, **`project_id` is the most important field** — every Taskiq indexing task is scoped to a project
- Filtering strips `project_id`, `request_id`, `method`, `path`, and any custom field
- Worker logs become un-correlatable to the originating request
- "Broker payload bloat" is theoretical — contextvars are small strings/IDs, typically < 1KB total

**When filtering IS appropriate:** if you've accidentally bound a **secret** to contextvars (e.g., `api_key`). The right fix is to never bind secrets to contextvars in the first place — that's a data discipline issue, not a labels issue.

```python
# ✅ RIGHT — don't bind secrets to contextvars
structlog.contextvars.bind_contextvars(trace_id=..., user_id=..., project_id=...)
# Pass ctx as-is to Taskiq
```

### 5.6 The data flow

```text
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI process                                                  │
│                                                                  │
│  RequestContextMiddleware                                        │
│   ├─ bind_contextvars(trace_id, user_id, method, path)          │
│   └─ clear_contextvars()  [on exit]                              │
│                                                                  │
│  route handler                                                   │
│   ├─ ctx = snapshot_context()   # dict copy                     │
│   └─ task.kiq(args..., labels=ctx)                              │
│                                                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │  serializes to Redis / RabbitMQ
                           │  {args: [...], labels: {trace_id:...}}
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Taskiq worker process (DIFFERENT process or task)                │
│                                                                  │
│  TaskContextMiddleware.pre_execute                               │
│   └─ bind_contextvars(task_id, task_name, **message.labels)     │
│                                                                  │
│  task body                                                       │
│   └─ log.info(...)   # has all contextvars bound                │
│                                                                  │
│  TaskContextMiddleware.post_execute                              │
│   └─ clear_contextvars()  [prevent leaks]                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.7 Verifying the handoff

Run a request, then grep logs for the trace_id:

```bash
# All FastAPI logs with that trace_id
grep '"trace_id":"abc-123"' logs.json

# All Taskiq logs with that trace_id (same trace_id, different process)
grep '"trace_id":"abc-123"' worker.log
```

If both match → handoff works. If Taskiq logs have `"trace_id": null` → fix your `labels=` handoff.

---

## 6. Exception logging

### 6.1 The right way

```python
try:
    await do_thing()
except DomainError as e:
    # `log.exception` automatically:
    # - sets level=ERROR
    # - captures the traceback
    # - runs it through dict_tracebacks → structured exception
    log.exception(
        "operation_failed",
        operation="do_thing",
        retry_after_ms=e.retry_after_ms,
    )
    raise
except Exception as e:
    # Truly unexpected — log + let the global handler deal with it
    log.exception("unexpected_error", operation="do_thing")
    raise
```

The output for an exception:
```json
{
  "message": "operation_failed",
  "severity": "ERROR",
  "timestamp": "2026-07-19T18:30:53.123Z",
  "trace_id": "abc-123",
  "operation": "do_thing",
  "retry_after_ms": 2000,
  "exception": {
    "type": "DomainError",
    "value": "rate limit exceeded",
    "module": "src.exceptions",
    "frames": [
      {"file": "src/services/payment.py", "line": 42, "function": "charge", ...},
      ...
    ]
  }
}
```

### 6.2 Chained exceptions (Python `raise X from e`)

```python
try:
    await call_external()
except ExternalError as e:
    log.exception("external_call_failed", endpoint="/api/x")
    # Chain — keeps original traceback
    raise DomainError("user-facing message") from e
```

Both exceptions appear in the traceback. dict_tracebacks handles this correctly.

### 6.3 What NOT to do

```python
# ❌ Don't put the log message in the log call as a comment
log.exception("the following logging is for Exception : ")

# ❌ Don't stringify the exception yourself
log.error("operation failed: " + str(e))

# ❌ Don't lose the traceback
log.error("operation failed", error=str(e))  # no exc_info, no traceback
raise  # bare re-raise preserves traceback but log is useless

# ❌ Don't use `print` for errors
print("ERROR:", e)
```

---

## 7. Error Tracking & Observability (No-Sentry Stack)

Sentry's free tier is a trap (e.g., an infinite loop bug can instantly trigger $300+/month in overages). Since you already have **PostgreSQL, Prometheus, and Grafana**, you can build a superior, cost-free observability stack.

### 7.1 Taskiq Errors: PostgreSQL (You already have this)
Your task execution audit logic catches failures and writes them to the `taskiq_task_executions` table:
```python
if error is not None:
    record.error = repr(error)
    record.status = "FAILED"
```
**Action:** Connect Grafana to PostgreSQL and create a panel:
```sql
SELECT task_name, error, completed_at 
FROM taskiq_task_executions 
WHERE status = 'FAILED' 
ORDER BY completed_at DESC 
LIMIT 50;
```
Set up a Grafana alert: `Alert when count(status='FAILED') > 0 in the last 5 minutes`.

### 7.2 FastAPI HTTP Errors: Grafana Loki
For HTTP request context, use **Grafana Loki**. It plugs directly into your existing Grafana dashboards.

Ensure your global exception handler logs structured data with `exc_info=True` (via `log.exception`) so `dict_tracebacks` captures the stack for Loki ingestion:
```python
from fastapi import Request
from fastapi.responses import JSONResponse
from src.observability.logging import get_logger

log = get_logger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # contextvars will auto-inject trace_id, user_id, method, path here
    log.exception(
        "unhandled_http_exception",
        url=str(request.url),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
```
Ship these JSON logs to Loki (via Promtail or Grafana Alloy). You can now search logs by `url`, `method`, or `trace_id` right next to your Prometheus metrics.

### 7.3 Optional: GlitchTip (Self-hosted "Sentry")
If you absolutely need the Sentry UI/workflow without the SaaS cost, use **GlitchTip**. It is an open-source reimplementation of Sentry that uses the **exact same `sentry-sdk`**.
```python
import sentry_sdk

# Point the DSN to your self-hosted GlitchTip instance instead of sentry.io
sentry_sdk.init(
    dsn="http://your-glitchtip-instance/1", 
    traces_sample_rate=1.0,
)
```
*Result: You get the Sentry UI and SDK, but you host it yourself with unlimited events.*

---

## 8. Performance notes

### 8.1 `cache_logger_on_first_use=True` — important, with a tested caveat

Without this, structlog re-builds the processor chain on **every log call**. With it, the first call to a logger caches the result, and subsequent calls skip the chain construction. For high-throughput services this is a 30–50% speedup.

**Caveat (tested against structlog 26.1.0):** the cached logger pins the `wrapper_class` used at cache time. If you support a **dynamic log-level endpoint** (e.g., `POST /admin/log-level {level: "DEBUG"}`), reconfigure structlog + the stdlib root logger, but **already-cached logger instances will keep their old filter**. I tested this explicitly:

```python
# Test result (structlog 26.1.0, cache_logger_on_first_use=True)
setup(INFO)              # wrapper_class = make_filtering_bound_logger(INFO)
log = get_logger("x")    # cache will be built on first .info() call
log.debug("a")           # → filtered ✅
setup(DEBUG)             # wrapper_class = make_filtering_bound_logger(DEBUG)
log.debug("b")           # → STILL filtered ❌  (cache key is the logger, not the wrapper)
get_logger("y").debug("c")  # → emitted ✅  (new logger, new cache)
```

**The cache key is the logger instance, not the wrapper class.** The claim that "structlog rebuilds the cached wrapper when the configuration changes" is **not true** in 26.1.0.

Three options:

```python
# Option A: reconfigure AND drop references (for hot-swap patterns)
import gc

def set_log_level(level: str):
    level_int = getattr(logging, level.upper())
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        # other config preserved
    )
    logging.getLogger().setLevel(level_int)
    # Drop references to cached loggers so they're re-resolved on next use
    gc.collect()  # not perfect; better: re-import modules that hold loggers
```

```python
# Option B: don't cache (slower but always honors current config)
cache_logger_on_first_use=False
```

```python
# Option C: just don't support runtime level changes (recommended)
# Most teams don't need this. If you do, use a different mechanism
# (e.g., per-module level override via a custom wrapper_class).
```

For most production services, **C is the right answer** — configure at startup, accept the level is fixed. Document the limitation and move on. The cache is too valuable for perf to give up by default.

### 8.2 Avoid `BaseHTTPMiddleware`

Starlette's `BaseHTTPMiddleware` has a [long-standing bug](https://github.com/encode/starlette/issues/472) where it buffers the entire response body in memory before sending. Worse under 3.14t free-threaded.

**Use pure ASGI middleware** (see §4.3) for anything that touches the response.

### 8.3 Sampling in high-volume paths

For very chatty paths (e.g., per-request access logs), use a sampling processor. Renamed for clarity from `_sample_drop` to `_drop_with_probability`:

```python
import random
import structlog
from structlog.types import EventDict, Processor


def _drop_with_probability(probability: float) -> Processor:
    """
    Drop a log event with the given probability.
      probability=0.0  → keep 100%
      probability=0.5  → keep 50%
      probability=0.9  → keep 10% (drop 90%)
    """
    def processor(_, __, event_dict: EventDict) -> EventDict:
        if random.random() < probability:
            raise structlog.DropEvent
        return event_dict
    return processor


# In your processor chain (after merge_contextvars, before any expensive work):
shared_processors = [
    structlog.contextvars.merge_contextvars,
    _drop_with_probability(0.0),  # adjust per environment
    ...
]
```

### 8.3.1 Trace-aware sampling (advanced)

If you're using OpenTelemetry, you typically want to **drop logs for traces that aren't sampled** — keeps log volume in line with trace volume:

```python
# Imports hoisted to module level — OTel lookup is module-cached and cheap
try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import SpanKind
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


def _drop_unsampled_traces(_, __, event_dict: EventDict) -> EventDict:
    """
    Drop the event if the current OTel trace was not sampled.

    The proper way to check sampling is via the span's trace_flags —
    the OTel SDK does NOT export an OTEL_TRACE_SAMPLED env var.
    """
    if not _OTEL_AVAILABLE:
        return event_dict
    span = _otel_trace.get_current_span()
    if span is None or not span.is_recording():
        return event_dict
    ctx = span.get_span_context()
    if ctx is None or ctx.trace_id == 0:
        return event_dict
    # trace_flags is a TraceFlags int; sampled bit is 0x01
    if not (ctx.trace_flags and ctx.trace_flags.sampled):
        raise structlog.DropEvent
    return event_dict
```

### 8.3.2 OpenTelemetry `span_id` integration

If you use OpenTelemetry, you want both `trace_id` AND `span_id` in your logs so you can pivot between logs and traces. Module-level OTel import (see §8.3.1) is reused here.

```python
def _add_otel_ids(_, __, event_dict: EventDict) -> EventDict:
    """Inject OpenTelemetry trace_id and span_id if a span is active."""
    if not _OTEL_AVAILABLE:
        return event_dict
    span = _otel_trace.get_current_span()
    if span is None or not span.is_recording():
        return event_dict
    ctx = span.get_span_context()
    if ctx is None or ctx.trace_id == 0:
        return event_dict
    event_dict["trace_id"] = format(ctx.trace_id, "032x")
    event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


# Add to shared_processors AFTER merge_contextvars
shared_processors = [
    structlog.contextvars.merge_contextvars,
    _add_otel_ids,  # ← OTel takes precedence over contextvar trace_id
    _drop_unsampled_traces,  # ← drop logs for non-sampled traces
    ...
]
```

When OTel is active, every log line carries the same `trace_id` and `span_id` as the current span — your log aggregator and Jaeger/Tempo can be cross-linked.

### 8.4 Don't log sensitive data (recursive redaction)

structlog makes it easy to leak PII by accident. The naive redaction (check top-level keys only) **misses PII in nested objects** — e.g., `user={"email": "x@y.com"}` would not be redacted. Use a recursive implementation:

```python
import copy
from typing import Any

# Common PII / secret fields. Add your own.
_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "bearer",
    "api_key", "apikey", "secret", "secret_key",
    "authorization", "auth", "cookie", "set-cookie",
    "credit_card", "card_number", "cvv", "cvc",
    "ssn", "social_security",
    "email", "phone", "phone_number",
    "private_key", "session_id",
})


def _is_sensitive(key: str) -> bool:
    return key.lower() in _SENSITIVE_KEYS


def _redact_value(value: Any) -> Any:
    """Recursively walk dicts and lists, redacting values whose key is sensitive."""
    if isinstance(value, dict):
        return {
            k: ("***REDACTED***" if _is_sensitive(k) else _redact_value(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(v) for v in value)
    return value


def _redact_sensitive(_, __, event_dict: EventDict) -> EventDict:
    """Processor that recursively redacts sensitive fields at any nesting level."""
    return _redact_value(event_dict)


# Add to the shared processors (early in the chain, so redaction runs first):
shared_processors = [
    structlog.contextvars.merge_contextvars,
    _redact_sensitive,  # ← before add_log_level / TimeStamper so the redacted dict gets timestamped
    ...
]
```

**Why the redacted value is `"***REDACTED***"` (a string) and not the original type:** the original could be anything — a token (string), a credit card (int), a private key (bytes). Replacing with a uniform sentinel string makes the redacted field easy to spot in logs and impossible to accidentally use. PII-secure by construction.

**Perf note:** recursion on every log call adds CPU. For high-throughput services (>10k logs/sec), this is measurable. If profiling shows it's a bottleneck:
- Skip recursion for known-safe event_dict shapes (e.g., if you know you never log nested user objects)
- Or use a selective redaction that only recurses when keys like `user`, `payload`, `request` are present
- Or pre-filter at the call site: don't log PII in the first place

For typical services, the cost is negligible (~1–2% overhead on log calls).

---

## 9. Anti-patterns

### ❌ Anti-pattern 1: `logger = logger.bind(...)` at module level

```python
# ❌ WRONG — leaks across requests
logger = structlog.get_logger()
logger = logger.bind(request_id="abc-123")  # bound forever on this object
```

**Fix:** Use `structlog.contextvars.bind_contextvars(...)` in middleware.

### ❌ Anti-pattern 2: string concatenation in messages

```python
# ❌ WRONG
log.info("user " + user_id + " charged " + str(amount) + " cents")

# ✅ RIGHT — structured fields
log.info("user_charged", user_id=user_id, amount_cents=amount)
```

The structured form is searchable; the concatenated form is not.

### ❌ Anti-pattern 3: missing `merge_contextvars`

If you `bind_contextvars` but `merge_contextvars` is not in the processor chain, **your bindings are silently dropped**. Always include it as the first processor.

### ❌ Anti-pattern 4: missing `cache_logger_on_first_use`

Perf hit. Always set it.

### ❌ Anti-pattern 5: log level not filtered

`structlog.configure(...)` without `wrapper_class=make_filtering_bound_logger(LEVEL)` logs everything. In production you will spam DEBUG to your aggregator.

### ❌ Anti-pattern 6: using `format_exc_info` instead of `dict_tracebacks`

`format_exc_info` produces a string. Your monitoring tool can't index the exception type, file, or line. **Always `dict_tracebacks` in JSON mode.**

### ❌ Anti-pattern 7: passing contextvars across `kiq()` boundary and expecting them to "just work"

`contextvars` are task-local. `kiq()` serializes to a broker. The worker has no idea what was bound in the FastAPI request. You MUST pass via `labels=` or args. (See §5.)

### ❌ Anti-pattern 8: bare `print` in production

```python
# ❌ WRONG
print("ERROR:", e)

# ✅ RIGHT
log.exception("operation_failed")
```

`print` is unstructured, unleveled, unfilterable, and bypasses your centralized observability stack (Loki/PostgreSQL).

### ❌ Anti-pattern 9: swallowing the traceback

```python
except Exception as e:
    log.error("failed: " + str(e))  # no exc_info → no traceback
    return None
```

Always use `log.exception(...)` (which sets `exc_info=True` by default) or pass `exc_info=True` explicitly.

### ❌ Anti-pattern 10: logging in tight loops

```python
# ❌ WRONG
for chunk in chunks:
    log.info("processing_chunk", idx=chunk.idx)  # 1000s of logs

# ✅ RIGHT — log summary
log.info("chunk_processing_started", total=len(chunks))
for chunk in chunks:
    _process(chunk)
log.info("chunk_processing_completed", total=len(chunks))
```

### ❌ Anti-pattern 11: broken stdlib bridge

```python
# ❌ WRONG — structlog emits JSON, but uvicorn/sqlalchemy emit plain text
logging.basicConfig(format="%(message)s", stream=sys.stdout, level=20)
for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(noisy).handlers = []
    logging.getLogger(noisy).propagate = True
```

Result: a mixed stream of JSON and unformatted strings. Your log aggregator parses one and chokes on the other. **This is the highest-impact bug to fix.**

```python
# ✅ RIGHT — unified bridge via ProcessorFormatter
structlog.configure(
    processors=shared_processors + [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    ...
)

formatter = structlog.stdlib.ProcessorFormatter(
    foreign_pre_chain=shared_processors,
    processors=[
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        structlog.processors.JSONRenderer(),
    ],
)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
root = logging.getLogger()
for h in list(root.handlers):
    root.removeHandler(h)
root.addHandler(handler)
root.setLevel(20)
```

See §3 for the complete config.

---

## 10. Production checklist

### Configuration
- [x] `configure_logging()` called ONCE at process startup
- [x] `cache_logger_on_first_use=True`
- [x] `wrapper_class=make_filtering_bound_logger(LOG_LEVEL)`
- [x] `TimeStamper(fmt="iso", utc=True)`
- [x] `dict_tracebacks` (not `format_exc_info`) for JSON
- [x] `CallsiteParameterAdder` for module/lineno/func
- [x] `EventRenamer("message")` for OTel/Grafana convention
- [x] `JSONRenderer(sort_keys=True)` for deterministic output
- [x] **Stdlib bridge uses `ProcessorFormatter` + `wrap_for_formatter` (NOT `basicConfig`)** — see §3

### Processors
- [x] `structlog.contextvars.merge_contextvars` as first processor
- [x] `_redact_sensitive` for PII/secrets
- [x] `_add_service_metadata` for service/env/version tags
- [x] `_rename_level_to_severity` for OTel compat
- [x] (Optional) `_add_otel_ids` for `span_id` when using OpenTelemetry — see §8.3.2

### FastAPI middleware
- [x] Pure ASGI middleware, NOT `BaseHTTPMiddleware`
- [x] `RequestContextMiddleware` for trace_id/user_id binding
- [x] `AccessLogMiddleware` for method/path/status/duration logging
- [x] `clear_request_context` in `finally` (prevents leaks)
- [x] `X-Trace-Id` header echoed in response
- [x] uvicorn launched with `log_config=None` and `access_log=False` to avoid double logging — see §4.7

### Taskiq (Part B)
- [x] `TaskContextMiddleware` registers and clears contextvars
- [x] FastAPI route uses `snapshot_context()` + `labels=ctx`
- [x] Task signature doesn't duplicate context fields — use labels
- [x] Verify handoff: same `trace_id` in FastAPI and Taskiq logs

### Exception handling
- [x] Use `log.exception(...)` not `log.error(..., exc_info=True)` (it's the same, but `exception` is more idiomatic)
- [x] Never `log.exception(...)` then `pass` — log AND handle (or re-raise)
- [x] Chained exceptions: `raise NewError(...) from e`
- [x] FastAPI global exception handler uses `log.exception` for Loki ingestion
- [x] Taskiq errors are persisted to PostgreSQL for Grafana alerting

### Monitoring
- [x] Logs ship to aggregator (Grafana Loki/Datadog/OpenObserve) as JSON
- [x] **Logs from uvicorn, sqlalchemy, and your code all emit the same JSON shape** (via ProcessorFormatter bridge)
- [x] No `print` anywhere
- [x] No `format_exc_info` — only `dict_tracebacks`

---

## Quick reference

```python
# Import
from src.observability.logging import get_logger
from src.observability.context import (
    bind_request_context, clear_request_context, snapshot_context,
)
import structlog

# Get a logger
log = get_logger(__name__)

# Log an event with structured fields
log.info("user_signed_up", user_id="u-123", plan="pro")

# Log an exception
try:
    ...
except Exception as e:
    log.exception("operation_failed", operation="signup")
    raise

# Bind context (server code only — via contextvars)
structlog.contextvars.bind_contextvars(trace_id="...", user_id="...")

# Snapshot for cross-process handoff
ctx = snapshot_context()
await some_task.kiq(args, labels=ctx)
```

That's the whole playbook. Apply it once, never think about it again, and your future self will thank you at 3am during the next incident.

