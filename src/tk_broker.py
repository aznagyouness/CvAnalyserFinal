# src/tk_broker.py
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from taskiq import PrometheusMiddleware, SimpleRetryMiddleware  # ← Import from taskiq
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

import src.database as db
from src.helpers.config import get_settings
from src.utils.taskiq_idempotency import TaskiqIdempotencyMiddleware  # ← Only import this

logger = logging.getLogger(__name__)
settings = get_settings()

# 1. Result backend
result_backend = RedisAsyncResultBackend(
    redis_url=settings.REDIS_URL_TASKIQ_RESULTS,
    keep_results=True,
    result_ex_time=3600,
)

# 2. Broker subclass — handles DB engine lifecycle
class AppAioPikaBroker(AioPikaBroker):
    async def startup(self) -> None:
        if db.db_engine is None:
            db.db_engine = create_async_engine(
                settings.POSTGRES_DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            db.db_session_factory = async_sessionmaker(
                bind=db.db_engine,
                expire_on_commit=False,
                autoflush=False,
            )
            logger.info("AppAioPikaBroker: DB engine initialized")
        await super().startup()

    async def shutdown(self) -> None:
        await super().shutdown()
        if db.db_engine is not None:
            try:
                await db.db_engine.dispose()
            except Exception:
                logger.exception("DB engine dispose failed")
            db.db_engine = None
            db.db_session_factory = None

# Build the broker
broker = AppAioPikaBroker(settings.TASKIQ_BROKER_URL).with_result_backend(result_backend)

# 3. Middlewares
idempotency_middleware = TaskiqIdempotencyMiddleware(
    redis_url=settings.REDIS_URL_TASKIQ_LIMITER,
    session_factory=lambda: db.db_session_factory(),
    run_ttl=settings.IDEMPOTENCY_RUN_TTL,
    done_ttl=settings.IDEMPOTENCY_DONE_TTL,
    strict_audit=settings.IDEMPOTENCY_STRICT_AUDIT,
)


broker = broker.with_middlewares(
    PrometheusMiddleware(server_addr="0.0.0.0", server_port=9000),  # outermost: sees EVERYTHING  # Sees the message first. Measures total lifecycle including idempotency + retries + task execution.
    SimpleRetryMiddleware(default_retry_count=3),                    # middle: handles failures   # Wraps the idempotency check + task. Hides retries from the inner layers.
    idempotency_middleware,                                          # innermost: gate just before execution  # Sits right above the task. Decides on duplicates just-in-time, right before the actual function runs.
)

# 4. Import tasks AFTER broker is built
from src.tasks import indexing      # noqa: E402, F401
from src.tasks import maintenance   # noqa: E402, F401
from src.tasks import test_taskiq   # noqa: E402, F401

"""
# src/tk_broker.py
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from taskiq import PrometheusMiddleware
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

import src.database as db
from src.helpers.config import get_settings
from src.utils.taskiq_idempotency import (
        IdempotencyAwareRetryMiddleware,
        TaskiqIdempotencyMiddleware,
    )

logger = logging.getLogger(__name__)
settings = get_settings()

# 1. Result backend
result_backend = RedisAsyncResultBackend(
        redis_url=settings.REDIS_URL_TASKIQ_RESULTS,
        keep_results=True,
        result_ex_time=3600,
    )

# 2. Broker subclass — handles DB engine lifecycle
class AppAioPikaBroker(AioPikaBroker):
    async def startup(self) -> None:
        # 1. Init DB if not already done (FastAPI lifespan may have done this)
        if db.db_engine is None:
            db.db_engine = create_async_engine(
                settings.POSTGRES_DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                )
            db.db_session_factory = async_sessionmaker(
                    bind=db.db_engine,
                    expire_on_commit=False,
                    autoflush=False,
                )
            logger.info("AppAioPikaBroker: DB engine initialized")

        # 2. Taskiq natively iterates over middlewares and calls their startup() hooks
        await super().startup()

    async def shutdown(self) -> None:
        # 1. Taskiq natively iterates over middlewares and calls their shutdown() hooks
        await super().shutdown()

        # 2. Dispose DB engine
        if db.db_engine is not None:
            try:
                await db.db_engine.dispose()
            except Exception:
                logger.exception("DB engine dispose failed")
            db.db_engine = None
            db.db_session_factory = None

broker = AppAioPikaBroker(settings.TASKIQ_BROKER_URL).with_result_backend(result_backend)

# 3. Middlewares
# We use a lambda for session_factory because db.db_session_factory is None at module load time.
# The lambda ensures it's only evaluated when the middleware actually needs a session.
idempotency_middleware = TaskiqIdempotencyMiddleware(
    redis_url=settings.REDIS_URL_TASKIQ_LIMITER,
    session_factory=lambda: db.db_session_factory(), 
    run_ttl=settings.IDEMPOTENCY_RUN_TTL,
    done_ttl=settings.IDEMPOTENCY_DONE_TTL,
    strict_audit=settings.IDEMPOTENCY_STRICT_AUDIT,
    )

broker = broker.with_middlewares(
    idempotency_middleware,
    IdempotencyAwareRetryMiddleware(default_retry_count=3),
    PrometheusMiddleware(server_addr="0.0.0.0", server_port=9000),
    )

# 🚀 ADD THIS AT THE BOTTOM:
import src.tasks.test_taskiq  # This registers the tasks to the broker


# src/tk_broker.py

@broker.task(task_name="taskiq.internal.idempotency_skip")
async def _idempotency_skip_task():
    #A dummy task used to safely absorb and ACK duplicate messages.
    return {"status": "skipped_by_idempotency"}

"""