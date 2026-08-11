# 🚀 Production Hardening Guide: Taskiq, Idempotency & Result Handling

## 📋 Overview

This guide documents **production-grade improvements** for your CvAnalyser Taskiq system, using:
- Your existing guides: [`TaskiqMessage & TaskResult.md`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/markdown_files/TaskiqMessage%20%26%20TaskResult.md) and [`Taskiq_qwen.md`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/markdown_files/Taskiq_qwen.md)
- Your current codebase as a reference

---

## 📁 Files Covered

1. [`src/utils/taskiq_idempotency.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/utils/taskiq_idempotency.py) - Idempotency middleware
2. [`src/services/task_result_service.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/services/task_result_service.py) - Hybrid result lookup
3. [`src/tk_broker.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/tk_broker.py) - Broker & middlewares
4. [`src/models/db_schemes/cv_analysis_db/db_tables.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/models/db_schemes/cv_analysis_db/db_tables.py) - Task execution audit table
5. [`src/routes/task_result_router.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/routes/task_result_router.py) - Task result endpoints
6. [`src/tasks/test_taskiq.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/tasks/test_taskiq.py) - Test tasks

---

## 🔴 High-Priority Critical Improvements

---

### 1. Remove **Huge Block of Deprecated Code** from [`taskiq_idempotency.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/utils/taskiq_idempotency.py)

#### Problem
Lines 334‑643 are **all commented-out, deprecated code**, including:
- Old redirect logic
- Legacy retry middleware
- Deprecated idempotency violation error

#### Impact
- Cognitive overload
- Larger PRs
- Risk of accidentally reusing bad code
- Confusion for new developers

#### Solution
**Delete lines 334‑643 entirely**! Keep only the live, working code at the top (lines 1‑333).

---

### 2. Add Circuit Breaker for Redis (Fail Fast)

#### Problem
Right now, if Redis is down, your [`TaskiqIdempotencyMiddleware`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/utils/taskiq_idempotency.py#L32-L332) will crash trying to acquire locks or write markers!

#### Critical Note
**We NEVER use PostgreSQL for locking**! Row-level locks (`SELECT ... FOR UPDATE`) will cause massive contention and crash your database under load.

#### Impact
- Redis downtime takes down your entire worker fleet
- No safe failover (idempotency requires Redis locking)
- Cascading failures

#### Solution
Add a circuit breaker using `aiobreaker` or `tenacity` to **fail fast and reject tasks** if Redis is down:

##### Example Implementation (Add to `taskiq_idempotency.py`)
```python
# Install: pip install aiobreaker
from aiobreaker import CircuitBreaker, CircuitBreakerError

# Initialize breaker in __init__
self.redis_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    timeout=5.0
)

# Wrap Redis calls
@self.redis_breaker
async def _safe_redis_get(self, key: str):
    if self._redis:
        return await self._redis.get(key)

@self.redis_breaker
async def _safe_redis_set_nx_ex(self, key: str, value: Any, ex: int) -> bool:
    if self._redis:
        return await self._redis.set(key, value, nx=True, ex=ex)

@self.redis_breaker
async def _safe_redis_delete(self, key: str):
    if self._redis:
        await self._redis.delete(key)

@self.redis_breaker
async def _safe_redis_set(self, key: str, value: Any, ex: int):
    if self._redis:
        await self._redis.set(key, value, ex=ex)
```

##### Behavior When Redis Circuit Is Open
When the circuit opens (Redis is down):
1. **Raise an exception immediately** (don't execute the task!)
2. Let `SimpleRetryMiddleware` handle retries
3. **Log it loudly** for observability
4. **NEVER use Postgres for locking**!

---

### 3. Archive Old `TaskiqTaskExecution` Records

#### Problem
Your [`TaskiqTaskExecution`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/models/db_schemes/cv_analysis_db/db_tables.py#L35-L66) audit table will **grow forever**!

#### Impact
- Slower queries over time
- Higher storage costs
- Slower backups

#### Solution
Add a **Taskiq background task** to delete/archive old records:

##### Example Task (Add to `tasks/maintenance.py`)
```python
@broker.task(
    task_name="src.tasks.maintenance:archive_old_task_executions",
    timeout=300.0,
    labels={"queue": "maintenance", "priority": 1}
)
async def archive_old_task_executions(
    older_than_days: int = 90,
    context: Annotated[Context, TaskiqDepends()] = None
):
    """Delete task execution records older than N days (configurable)."""
    from sqlalchemy import delete
    from datetime import timedelta

    logger.info(f"Archiving task executions older than {older_than_days} days")
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    async with db.db_session_factory() as session:
        stmt = delete(TaskiqTaskExecution).where(TaskiqTaskExecution.completed_at < cutoff)
        result = await session.execute(stmt)
        await session.commit()

    logger.info(f"Archived {result.rowcount} old task execution records")
```

##### Schedule It (Add to `tk_broker.py`)
Use `taskiq-scheduler` or a cron job to run it **once daily**.

---

### 6. Add Pagination to `get_all_executions_by_input`

#### Problem
In [`task_result_service.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/services/task_result_service.py#L182), you return **every single execution attempt** for a given input:
```python
return [ ... for r in records ]
```

#### Impact
- If a task retries 1000 times, this returns 1000 huge objects
- Risk of timeouts
- Unnecessary data transfer

#### Solution
Add `limit` and `offset` parameters!

##### Updated `get_all_executions_by_input`
```python
async def get_all_executions_by_input(
    self,
    task_name: str,
    args: list = None,
    kwargs: dict = None,
    limit: int = 100,  # ✅ NEW
    offset: int = 0,  # ✅ NEW
) -> Dict[str, Any]:  # ✅ Return dict with metadata instead of list
    payload = {
        "task_name": task_name,
        "args": args or [],
        "kwargs": kwargs or {},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    task_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    
    try:
        async with self.session_factory() as session:
            # Get COUNT first
            count_stmt = select(func.count(TaskiqTaskExecution.execution_id)).where(TaskiqTaskExecution.task_args_hash == task_hash)
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar_one()
            
            # Get paginated records
            stmt = (
                select(TaskiqTaskExecution)
                .where(TaskiqTaskExecution.task_args_hash == task_hash)
                .order_by(TaskiqTaskExecution.enqueued_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()
        
        return {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "executions": [
                {
                    "task_id": r.taskiq_task_id,
                    "task_name": r.task_name,
                    "status": r.status,
                    "result": r.result if r.status == "SUCCESS" else None,
                    "error": r.error if r.status == "FAILED" else None,
                    "enqueued_at": r.enqueued_at.isoformat() if r.enqueued_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in records
            ]
        }
    except SQLAlchemyError as e:
        logger.error("PostgreSQL query failed: %s", e)
        return {"total_count": 0, "limit": limit, "offset": offset, "executions": []}
```

##### Update the Endpoint
Also update [`/all-executions-by-input`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/routes/task_result_router.py#L90-L105) to accept `limit` and `offset` query parameters!

---

## 🟡 Medium-Priority Production Improvements

---

### 5. Add Structured Logging Everywhere

#### Problem
Right now, your logging uses **plain strings**:
```python
logger.info("pre_send: skipping %s hash=%s — already completed", task_name, task_hash[:12])
```

#### Impact
- Hard to query/filter logs in tools like Datadog, ELK or Loki
- No standardized fields for task metadata

#### Solution
Use **structured logging with `extra`**:

```python
# ✅ Better structured logging
logger.info(
    "idempotency_skip",
    extra={
        "task_name": task_name,
        "task_hash": task_hash[:12],
        "reason": "already_completed",
        "taskiq_task_id": getattr(context.message, "task_id", "unknown") if context else "unknown"
    }
)
```

---

### 6. Improve Result Serialization for Complex Objects

#### Problem
Right now, you use:
```python
record.result = json.loads(json.dumps(result, default=str))  # Line 320, taskiq_idempotency.py
```

#### Impact
- For `datetime`, `UUID` or Pydantic models, you just get their string representation
- Hard to deserialize back to original types later

#### Solution
Use a **custom JSON encoder** that preserves type info!

##### Custom Encoder (Add to `taskiq_idempotency.py` or `helpers/json.py`)
```python
import uuid
from datetime import datetime

def json_default(obj):
    if isinstance(obj, datetime):
        return {"__type__": "datetime", "isoformat": obj.isoformat()}
    if isinstance(obj, uuid.UUID):
        return {"__type__": "uuid", "hex": obj.hex}
    # Add support for Pydantic models if needed
    if hasattr(obj, "model_dump"):
        return {"__type__": "pydantic_model", "model": obj.__class__.__name__, "data": obj.model_dump()}
    return str(obj)
```

##### Custom Decoder (Add to `task_result_service.py`)
```python
def json_object_hook(obj):
    try:
        if obj.get("__type__") == "datetime":
            return datetime.fromisoformat(obj["isoformat"])
        if obj.get("__type__") == "uuid":
            return uuid.UUID(hex=obj["hex"])
    except Exception:
        pass  # Fall back to raw object if decoding fails
    return obj
```

##### Use It
```python
# When writing:
record.result = json.loads(json.dumps(result, default=json_default))

# When reading:
actual_result = json.loads(json.dumps(record.result), object_hook=json_object_hook)
```

---

### 7. Use Production-Grade Taskiq Worker Flags

From your [`Taskiq_qwen.md`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/markdown_files/Taskiq_qwen.md) (lines 2033‑2040):

```bash
taskiq worker src.tasks:broker \
    --workers 4 \
    --max-async-tasks 50 \
    --ack-type when_saved \  # ✅ Critical for data safety!
    --wait-tasks-timeout 30 \
    --max-prefetch 10
```

#### Key Flags Explained
- `--ack-type when_saved`: Only ACK the task **after it's saved to audit log & result backend** (prevents data loss!)
- `--wait-tasks-timeout 30`: Wait 30s for running tasks to finish on shutdown
- `--max-prefetch 10`: Limit how many messages a worker can prefetch (prevents overloading)

---

### 8. Add Dead Letter Queue (DLQ) for Failed Tasks

From your [`Taskiq_qwen.md`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/markdown_files/Taskiq_qwen.md), add a DLQ to RabbitMQ!

#### Why?
- Don't lose failed tasks forever
- Can reprocess them later manually
- Better observability

---

## 🟢 Low-Priority Nice-to-Haves

---

### 6. Add More Prometheus Metrics

#### For `task_result_service.py`:
- `taskiq_result_lookup_seconds`: Histogram of lookup times
- `taskiq_result_lookup_total`: Counter with labels (`source: redis|postgres`, `status: success|failed`)
- `taskiq_result_lookup_cache_hits_total`: Counter for Redis hits

#### For `taskiq_idempotency.py`:
- `taskiq_idempotency_lock_acquisition_seconds`: Histogram of lock acquisition times
- `taskiq_idempotency_audit_write_seconds`: Histogram of audit DB write times
- `taskiq_idempotency_decisions_total`: Counter with labels (`decision: queued|skipped_completed|skipped_running`)

---

### 7. Add Pydantic Validation for Task Results

If your task results have predictable schemas, create Pydantic models for them:

```python
# src/models/task_results.py
from pydantic import BaseModel

class MyTask2Result(BaseModel):
    status: str
    task_id: str
    text: str
    text_length: int
    delay: float
    message: str
```

Then validate on write/read to catch corruption early!

---

## 📊 Summary of Current Status

### ✅ What's Already Great
1. Hybrid Redis/PostgreSQL result lookup
2. TaskiqResult extraction (no more storing wrapper objects!)
3. Legacy data handling in `task_result_service.py`
4. Short-lived DB sessions
5. Proper indexes on `TaskiqTaskExecution`
6. `pre_send` idempotency check (prevents duplicates from even being queued!)
7. Prometheus middleware
8. SimpleRetryMiddleware
9. Idempotency middleware with PG audit
10. **TTL config already done!** (You already pass `run_ttl` and `done_ttl` from settings in [`tk_broker.py`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/tk_broker.py#L57-L64)! The defaults in `__init__` are just type hints.)

---

## 💡 Minor Tweaks & Clarifications

### 1. `labels["labels"]` Redundancy
This isn't a bug in your middleware—it's a quirk of how Taskiq's `@broker.task` decorator handles kwargs! If you define a task like `@broker.task(labels={"queue": "default"})`, Taskiq sometimes nests it.

#### Solution
Change your task definitions to use:
- Explicit kwargs: `@broker.task(queue_name="default")`
- Or use `kicker().with_labels()` when queuing tasks

---

### 2. Custom JSON Encoder/Decoder
This is a great idea, but be careful with the decoder! If you change the schema of your task results later, old records in Postgres might fail to deserialize. Keep the decoder very forgiving—use `try/except` and fallback to raw strings if decoding fails!

---

### 3. Dead Letter Queue (DLQ)
RabbitMQ handles DLQs via `x-dead-letter-exchange`. Taskiq's `AioPikaBroker` supports this out of the box! Just ensure your RabbitMQ queue is configured with a DLQ routing key so failed tasks don't just vanish after max retries!

---

## 🎯 Top 5 Must-Dos First (Priority Order)

1. **Delete deprecated code** from `taskiq_idempotency.py`
2. **Add circuit breaker for Redis** (fail fast, no Postgres fallback!)
3. **Add pagination** to `/all-executions-by-input`
4. **Write the maintenance task** to archive old Postgres audit records
5. **Ensure you use `--ack-type when_saved`** in worker startup script

---

## 🔗 References

- Your Taskiq message guide: [`TaskiqMessage & TaskResult.md`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/markdown_files/TaskiqMessage%20%26%20TaskResult.md)
- Your Qwen Taskiq guide: [`Taskiq_qwen.md`](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/markdown_files/Taskiq_qwen.md)
- Taskiq Official Docs: https://taskiq-python.github.io/
- Prometheus Client Docs: https://prometheus.github.io/client_python/
