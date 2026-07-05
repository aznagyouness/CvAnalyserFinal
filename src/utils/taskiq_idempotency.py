# src/utils/taskiq_idempotency.py
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from prometheus_client import Counter, Gauge
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
from taskiq import SimpleRetryMiddleware, TaskiqMiddleware, TaskiqResult
from taskiq.message import TaskiqMessage

logger = logging.getLogger(__name__)

# ─── Metrics ────────────────────────────────────────────────────────────────
IDEMPOTENCY_DECISIONS = Counter(
    "taskiq_idempotency_decisions_total",
    "Decisions made by the idempotency middleware",
    ["task_name", "decision"],
)

IDEMPOTENCY_INFLIGHT = Gauge(
    "taskiq_idempotency_inflight_tasks",
    "Tasks currently holding an in-flight idempotency lock",
)

# ─── Middleware ─────────────────────────────────────────────────────────────
class TaskiqIdempotencyMiddleware(TaskiqMiddleware):
    def __init__(
        self,
        *,
        redis_url: str,
        session_factory: Callable[[], Any],
        run_ttl: int = 900,
        done_ttl: int = 86_400,
        strict_audit: bool = True,
    ):
        if run_ttl < 30:
            raise ValueError("run_ttl must be >= 30 seconds")
        if done_ttl < run_ttl:
            raise ValueError("done_ttl must be >= run_ttl")
        if session_factory is None:
            raise ValueError("session_factory is required")

        self._redis_url = redis_url
        self._session_factory = session_factory
        self._run_ttl = run_ttl
        self._done_ttl = done_ttl
        self._strict_audit = strict_audit
        self._redis: Optional[Redis] = None

    async def startup(self) -> None:
        if self._redis is not None:
            return
        self._redis = Redis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
        await self._redis.ping()
        logger.info("TaskiqIdempotencyMiddleware connected to Redis")

    async def shutdown(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        except Exception:
            logger.exception("error closing idempotency Redis connection")
        self._redis = None
        logger.info("TaskiqIdempotencyMiddleware Redis connection closed")

    @staticmethod
    def _key_run(task_hash: str) -> str:
        return f"idem:{task_hash}:run"

    @staticmethod
    def _key_done(task_hash: str) -> str:
        return f"idem:{task_hash}:done"

    def _hash(self, message: TaskiqMessage) -> str:
        payload = {
            "task_name": message.task_name,
            "args": message.args,
            "kwargs": message.kwargs,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    # ─── PRE_SEND: Check idempotency BEFORE queuing ────────────────────────
    async def pre_send(self, message: TaskiqMessage) -> TaskiqMessage:
        """
        Check idempotency when the task is being QUEUED (in FastAPI process).
        This prevents duplicates from ever reaching RabbitMQ.
        """
        if self._redis is None:
            await self.startup()

        task_name = message.task_name
        task_hash = self._hash(message)
        run_key = self._key_run(task_hash)
        done_key = self._key_done(task_hash)

        # 1. Check if already completed
        if await self._redis.exists(done_key):
            IDEMPOTENCY_DECISIONS.labels(task_name=task_name, decision="skipped_completed").inc()
            logger.info("pre_send: skipping %s hash=%s — already completed", task_name, task_hash[:12])
            message.labels = message.labels or {}
            message.labels["idempotency_skip"] = "completed"
            return message

        # 2. Check if currently running
        if await self._redis.exists(run_key):
            IDEMPOTENCY_DECISIONS.labels(task_name=task_name, decision="skipped_running").inc()
            logger.warning("pre_send: skipping %s hash=%s — currently running", task_name, task_hash[:12])
            message.labels = message.labels or {}
            message.labels["idempotency_skip"] = "running"
            return message

        # 3. Not a duplicate — allow queuing
        IDEMPOTENCY_DECISIONS.labels(task_name=task_name, decision="queued").inc()
        message.labels = message.labels or {}
        message.labels["task_hash"] = task_hash
        return message

    # ─── PRE_EXECUTE: Handle duplicates that made it to the worker ─────────
    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """
        Check if this task was marked as duplicate in pre_send.
        Set a flag for the task to check.
        """
        if self._redis is None:
            raise RuntimeError("TaskiqIdempotencyMiddleware not started")

        task_name = message.task_name
        labels = message.labels or {}

        # If marked as duplicate in pre_send, set flag for task to check
        if labels.get("idempotency_skip"):
            logger.info("pre_execute: task %s marked as duplicate, will skip", task_name)
            message.labels["should_skip"] = "true"
            return message

        # Otherwise, acquire lock and proceed normally
        task_hash = labels.get("task_hash") or self._hash(message)
        run_key = self._key_run(task_hash)
        done_key = self._key_done(task_hash)

        # Acquire in-flight lock
        acquired = await self._redis.set(run_key, "1", nx=True, ex=self._run_ttl)
        if not acquired:
            logger.warning("pre_execute: %s hash=%s — lock acquisition failed, marking as skip", task_name, task_hash[:12])
            message.labels["should_skip"] = "true"
            return message

        IDEMPOTENCY_INFLIGHT.inc()

        # Stash Redis keys for cleanup
        message.labels["idem_run_key"] = run_key
        message.labels["idem_done_key"] = done_key
        message.labels["task_hash"] = task_hash

        # Audit log
        execution_id: Optional[int] = None
        try:
            from src.models.db_schemes.cv_analysis_db.db_tables import TaskiqTaskExecution

            session = self._session_factory()
            try:
                record = TaskiqTaskExecution(
                    task_name=task_name,
                    taskiq_task_id=message.task_id,
                    task_args_hash=task_hash,
                    task_args={
                        "args": list(message.args or []),
                        "kwargs": dict(message.kwargs or {}),
                    },
                    status="RUNNING",
                    enqueued_at=datetime.now(timezone.utc),
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)
                execution_id = record.execution_id
                message.labels["db_execution_id"] = str(execution_id)
            except SQLAlchemyError as e:
                await session.rollback()
                raise
            finally:
                await session.close()
        except Exception as e:
            if self._strict_audit:
                logger.error("audit insert failed (strict) for %s: %s", task_name, e)
                raise RuntimeError(f"Failed to audit task {task_name}: {e}") from e
            logger.error("audit insert failed (non-strict) for %s: %s — continuing", task_name, e)

        return message

    async def post_execute(self, message: TaskiqMessage, result: Any) -> None:
        labels = message.labels or {}
        task_name = message.task_name

        # If task was marked as skip, just log and exit
        if labels.get("should_skip") == "true":
            logger.info("post_execute: task %s was skipped (duplicate)", task_name)
            return

        run_key = labels.get("idem_run_key")
        done_key = labels.get("idem_done_key")
        execution_id_str = labels.get("db_execution_id")

        IDEMPOTENCY_INFLIGHT.dec()

        # Write completed marker
        if done_key:
            try:
                await self._redis.set(done_key, "1", ex=self._done_ttl)
            except Exception:
                logger.exception("failed to write done marker for %s", task_name)

        # Release in-flight lock
        if run_key:
            await self._safe_redis_delete(run_key)

        # Update audit row
        if execution_id_str:
            await self._update_audit(int(execution_id_str), "SUCCESS", result, None)

    async def on_error(
        self, message: TaskiqMessage, result: Any, exception: BaseException,
    ) -> None:
        labels = message.labels or {}
        run_key = labels.get("idem_run_key")
        execution_id_str = labels.get("db_execution_id")
        task_name = message.task_name

        # If task was marked as skip, don't decrement inflight
        if labels.get("should_skip") == "true":
            return

        IDEMPOTENCY_INFLIGHT.dec()

        if run_key:
            await self._safe_redis_delete(run_key)

        if execution_id_str:
            await self._update_audit(int(execution_id_str), "FAILED", None, repr(exception))

    async def _safe_redis_delete(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            logger.exception("redis DELETE failed key=%s — will expire via TTL", key)

    async def _update_audit(
        self,
        execution_id: int,
        status: str,
        result: Any,
        error: Optional[str],
    ) -> None:
        from src.models.db_schemes.cv_analysis_db.db_tables import TaskiqTaskExecution

        session = self._session_factory()
        try:
            record = await session.get(TaskiqTaskExecution, execution_id)
            if record is None:
                logger.warning("audit row %s not found", execution_id)
                return
            
            record.status = status
            record.completed_at = datetime.now(timezone.utc)
            
            if error is not None:
                record.error = error
            
            if result is not None:
                try:
                    record.result = json.loads(json.dumps(result, default=str))
                except (TypeError, ValueError):
                    record.result = repr(result)
                    
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.exception("failed to update audit row %s", execution_id)
        except Exception:
            logger.exception("unexpected error updating audit row %s", execution_id)
        finally:
            await session.close()
"""
# src/utils/taskiq_idempotency.py
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from prometheus_client import Counter, Gauge
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
from taskiq import SimpleRetryMiddleware, TaskiqMiddleware, TaskiqResult
from taskiq.message import TaskiqMessage

logger = logging.getLogger(__name__)

# ─── Metrics ────────────────────────────────────────────────────────────────
IDEMPOTENCY_DECISIONS = Counter(
    "taskiq_idempotency_decisions_total",
    "Decisions made by the idempotency middleware",
    ["task_name", "decision"],  # executed | skipped_completed | skipped_running
)

IDEMPOTENCY_INFLIGHT = Gauge(
    "taskiq_idempotency_inflight_tasks",
    "Tasks currently holding an in-flight idempotency lock",
)

# ─── Exceptions ─────────────────────────────────────────────────────────────
class IdempotencyViolationError(Exception):
    
    DEPRECATED: We no longer raise this exception because it breaks Taskiq's 
    internal Receiver callback and prevents the message from being ACKed.
    Kept here for backward compatibility or external catching if needed.
    
    pass

# ─── Smart retry ─────────────────────────────────────────────────────────────
class IdempotencyAwareRetryMiddleware(SimpleRetryMiddleware):
    DEPRECATED: Since we no longer raise IdempotencyViolationError, 
    the standard SimpleRetryMiddleware is sufficient. 
    Kept here in case you reference it in tk_broker.py.
    
    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
        exception: BaseException,
    ) -> None:
        if isinstance(exception, IdempotencyViolationError):
            return
        await super().on_error(message, result, exception)

# ─── Middleware ─────────────────────────────────────────────────────────────
class TaskiqIdempotencyMiddleware(TaskiqMiddleware):
    def __init__(
        self,
        *,
        redis_url: str,
        session_factory: Callable[[], Any],
        run_ttl: int = 900,
        done_ttl: int = 86_400,
        strict_audit: bool = True,
    ):
        if run_ttl < 30:
            raise ValueError("run_ttl must be >= 30 seconds")
        if done_ttl < run_ttl:
            raise ValueError("done_ttl must be >= run_ttl")
        if session_factory is None:
            raise ValueError("session_factory is required")

        self._redis_url = redis_url
        self._session_factory = session_factory
        self._run_ttl = run_ttl
        self._done_ttl = done_ttl
        self._strict_audit = strict_audit
        self._redis: Optional[Redis] = None

    async def startup(self) -> None:
        if self._redis is not None:
            return
        self._redis = Redis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
        await self._redis.ping()
        logger.info("TaskiqIdempotencyMiddleware connected to Redis")

    async def shutdown(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        except Exception:
            logger.exception("error closing idempotency Redis connection")
        self._redis = None
        logger.info("TaskiqIdempotencyMiddleware Redis connection closed")

    @staticmethod
    def _key_run(task_hash: str) -> str:
        return f"idem:{task_hash}:run"

    @staticmethod
    def _key_done(task_hash: str) -> str:
        return f"idem:{task_hash}:done"

    def _hash(self, message: TaskiqMessage) -> str:
        payload = {
            "task_name": message.task_name,
            "args": message.args,
            "kwargs": message.kwargs,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        if self._redis is None:
            raise RuntimeError("TaskiqIdempotencyMiddleware not started")

        task_name = message.task_name
        task_hash = self._hash(message)
        run_key = self._key_run(task_hash)
        done_key = self._key_done(task_hash)

        # 1. Fast-path: completed marker
        if await self._redis.exists(done_key):
            IDEMPOTENCY_DECISIONS.labels(task_name=task_name, decision="skipped_completed").inc()
            logger.info("idempotency: skipping %s hash=%s — already completed", task_name, task_hash[:12])
            return self._redirect_to_dummy(message, task_name, "completed")

        # 2. Acquire in-flight lock (atomic SET NX)
        acquired = await self._redis.set(run_key, "1", nx=True, ex=self._run_ttl)
        if not acquired:
            IDEMPOTENCY_DECISIONS.labels(task_name=task_name, decision="skipped_running").inc()
            logger.warning("idempotency: skipping %s hash=%s — currently running on another worker", task_name, task_hash[:12])
            return self._redirect_to_dummy(message, task_name, "running")

        # 3. TOCTOU re-check
        if await self._redis.exists(done_key):
            await self._safe_redis_delete(run_key)
            IDEMPOTENCY_DECISIONS.labels(task_name=task_name, decision="skipped_completed").inc()
            logger.info("idempotency: %s hash=%s — race resolved, duplicate completed", task_name, task_hash[:12])
            return self._redirect_to_dummy(message, task_name, "race_resolved")

        IDEMPOTENCY_INFLIGHT.inc()
        IDEMPOTENCY_DECISIONS.labels(task_name=task_name, decision="executed").inc()

        # 4. Stash Redis keys in labels
        message.labels = message.labels or {}
        message.labels["idem_run_key"] = run_key
        message.labels["idem_done_key"] = done_key
        acquired_at = datetime.now(timezone.utc)

        # 5. Audit log
        execution_id: Optional[int] = None
        try:
            from src.models.db_schemes.cv_analysis_db.db_tables import TaskiqTaskExecution

            session = self._session_factory()
            try:
                record = TaskiqTaskExecution(
                    task_name=task_name,
                    taskiq_task_id=message.task_id,
                    task_args_hash=task_hash,
                    task_args={
                        "args": list(message.args or []),
                        "kwargs": dict(message.kwargs or {}),
                    },
                    status="RUNNING",
                    enqueued_at=acquired_at,
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)
                execution_id = record.execution_id
                message.labels["db_execution_id"] = str(execution_id)
            except SQLAlchemyError as e:
                await session.rollback()
                raise
            finally:
                await session.close()
        except Exception as e:
            if self._strict_audit:
                logger.error("audit insert failed (strict) for %s: %s", task_name, e)
                raise RuntimeError(f"Failed to audit task {task_name}: {e}") from e
            logger.error("audit insert failed (non-strict) for %s: %s — continuing", task_name, e)

        return message

    def _redirect_to_dummy(self, message: TaskiqMessage, original_name: str, reason: str) -> TaskiqMessage:
        
        #Senior Dev Pattern: Instead of raising an exception that breaks the Receiver's 
        #ACK flow, we rewrite the message to point to a dummy task. 
        #Taskiq will execute the dummy task (instantly) and ACK the message naturally.
        
        message.labels = message.labels or {}
        message.labels["original_task_name"] = original_name
        message.labels["skip_reason"] = reason
        message.labels["idempotency_status"] = "skipped"
        
        # Rewrite the message to target the dummy task
        message.task_name = "taskiq.internal.idempotency_skip"
        message.args = []
        message.kwargs = {}
        
        return message

    async def post_execute(self, message: TaskiqMessage, result: Any) -> None:
        # 1. Check if this was a redirected duplicate
        if message.labels.get("idempotency_status") == "skipped":
            original_name = message.labels.get("original_task_name")
            logger.info(f"Idempotency: Successfully dropped duplicate of {original_name}")
            # Exit early. We DO NOT decrement IDEMPOTENCY_INFLIGHT because we never incremented it.
            return

        # 2. Normal post_execute logic for actual tasks
        labels = message.labels or {}
        run_key = labels.get("idem_run_key")
        done_key = labels.get("idem_done_key")
        execution_id_str = labels.get("db_execution_id")
        task_name = message.task_name

        IDEMPOTENCY_INFLIGHT.dec()

        # 2a. Write completed marker FIRST
        if done_key:
            try:
                await self._redis.set(done_key, "1", ex=self._done_ttl)
            except Exception:
                logger.exception("failed to write done marker for %s", task_name)

        # 2b. Release in-flight lock
        if run_key:
            await self._safe_redis_delete(run_key)

        # 2c. Update audit row
        if execution_id_str:
            await self._update_audit(int(execution_id_str), "SUCCESS", result, None)

    async def on_error(
        self, message: TaskiqMessage, result: Any, exception: BaseException,
    ) -> None:
        # Note: We no longer need to check for IdempotencyViolationError here 
        # because we are redirecting to a dummy task instead of raising.
        
        labels = message.labels or {}
        run_key = labels.get("idem_run_key")
        execution_id_str = labels.get("db_execution_id")
        task_name = message.task_name

        IDEMPOTENCY_INFLIGHT.dec()

        if run_key:
            await self._safe_redis_delete(run_key)

        if execution_id_str:
            await self._update_audit(int(execution_id_str), "FAILED", None, repr(exception))

    async def _safe_redis_delete(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            logger.exception("redis DELETE failed key=%s — will expire via TTL", key)

    async def _update_audit(
        self,
        execution_id: int,
        status: str,
        result: Any,
        error: Optional[str],
    ) -> None:
        from src.models.db_schemes.cv_analysis_db.db_tables import TaskiqTaskExecution

        session = self._session_factory()
        try:
            record = await session.get(TaskiqTaskExecution, execution_id)
            if record is None:
                logger.warning("audit row %s not found", execution_id)
                return
            
            record.status = status
            record.completed_at = datetime.now(timezone.utc)
            
            if error is not None:
                record.error = error
            
            if result is not None:
                try:
                    record.result = json.loads(json.dumps(result, default=str))
                except (TypeError, ValueError):
                    record.result = repr(result)
                    
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.exception("failed to update audit row %s", execution_id)
        except Exception:
            logger.exception("unexpected error updating audit row %s", execution_id)
        finally:
            await session.close()

"""