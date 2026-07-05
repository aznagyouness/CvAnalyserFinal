# I- 👤 What Happens on the User Side (UX Comparison)

## 🎯 The User's Perspective for Each Approach

### Scenario: User clicks "Process Payment" button

---

## 1️⃣ FastAPI Sync Response

```
User clicks "Pay $50"
    │
    ▼
┌─────────────────────────────────────┐
│  🔄 Loading spinner...              │
│  (HTTP request held open)           │
└─────────────────────────────────────┘
    │
    ├─── ✅ SUCCESS (0.5s) ──────────► "Payment successful!" ✅
    │
    └─── ❌ FAILURE (network timeout) ► "500 Internal Server Error" ❌
                                          │
                                          └─► User confused, clicks again
                                              └─► Might charge TWICE 💸
```

**User experience:**
- ✅ Fast feedback on success
- ❌ Generic error on failure ("500 Error")
- ❌ No idea what went wrong
- ❌ Risk of double-charging if they retry
- ❌ No way to check if payment actually went through

---

## 2️⃣ Taskiq with `wait_result()` (Fast Task)

```
User clicks "Pay $50"
    │
    ▼
┌─────────────────────────────────────┐
│  🔄 Loading spinner...              │
│  (HTTP request held open)           │
│  BUT: Taskiq retries 3x behind      │
│       the scenes automatically      │
└─────────────────────────────────────┘
    │
    ├─── ✅ SUCCESS (after retries) ──► "Payment successful!" ✅
    │
    └─── ❌ FAILURE (all retries fail)► "Payment failed: Card declined" ❌
                                          │
                                          └─► Clear error message
                                              └─► User knows what happened
                                                  └─► Can try different card
```

**User experience:**
- ✅ Fast feedback on success
- ✅ **Automatic retries** — transient errors fixed without user knowing
- ✅ **Clear error messages** (you control them)
- ✅ **No double-charge risk** (idempotency)
- ✅ **Audit trail** — support can investigate later

---

## 3️⃣ Taskiq with `task_id` (Slow Task)

```
User clicks "Generate Report"
    │
    ▼
┌─────────────────────────────────────┐
│  ✅ "Report is being generated"     │
│  Task ID: abc123                    │
│  (HTTP returns immediately)         │
└─────────────────────────────────────┘
    │
    ▼
User navigates away, does other stuff
    │
    ▼
User checks status page:
    │
    ├─── 🔄 "Processing... 50%" ─────► User waits, sees progress
    │
    ├─── ✅ "Completed! Download" ────► User downloads report
    │
    └─── ❌ "Failed: Invalid data" ──► User fixes data, retries
```

**User experience:**
- ✅ **No loading spinner** — instant feedback
- ✅ **Can navigate away** — not stuck waiting
- ✅ **Progress tracking** — knows what's happening
- ✅ **Can retry safely** — idempotency protects
- ✅ **Works on mobile** — no timeout issues

---

## 📊 Side-by-Side User Experience

| Situation | FastAPI Sync | Taskiq + `wait_result()` | Taskiq + `task_id` |
|-----------|--------------|--------------------------|---------------------|
| **Fast success** | ✅ Instant | ✅ Instant | ✅ Instant |
| **Transient failure** | ❌ Error, user retries | ✅ Auto-retry, user sees success | ✅ Auto-retry, user sees success later |
| **Permanent failure** | ❌ Generic 500 error | ❌ Clear error message | ❌ Clear error message |
| **Slow operation** | ❌ Timeout, frustrated | ❌ Timeout, frustrated | ✅ No timeout, happy |
| **Double-click** | 💸 Might charge twice | ✅ Protected (idempotency) | ✅ Protected (idempotency) |
| **Server crash** | ❌ Lost, no idea | ❌ Lost, but audited | ✅ Continues, user checks later |
| **Mobile user** | ❌ Timeout risk | ❌ Timeout risk | ✅ Works perfectly |
| **Support ticket** | ❌ No info | ✅ Full audit trail | ✅ Full audit trail |

---

## 🎯 The User's Emotional Journey

### FastAPI Sync Response:
```
Click → Wait → (Success? 😊 OR Error? 😡 → Retry → Double charge? 💸)
```
**Emotions:** Impatient, confused, frustrated

### Taskiq + `wait_result()`:
```
Click → Wait → (Success? 😊 OR Clear error? 😐 → Fix & retry)
```
**Emotions:** Slightly impatient, but informed and in control

### Taskiq + `task_id`:
```
Click → Instant feedback → Do other stuff → Check later → (Success? 🎉 OR Error? 😐)
```
**Emotions:** Relaxed, in control, satisfied

---

## 🏆 The Senior Dev's Rule for UX

> **"The user should never see a generic 500 error, never be stuck waiting, and never accidentally perform the same action twice."**

| Goal | Best Approach |
|------|---------------|
| **Fast operation, no failures** | FastAPI Sync |
| **Fast operation, can fail** | Taskiq + `wait_result()` |
| **Slow operation** | Taskiq + `task_id` |
| **Critical operation** | Taskiq (either pattern) |

**Bottom line**: From the user's perspective, Taskiq always provides a **better, safer, more reliable experience** — whether you use `wait_result()` for fast tasks or `task_id` for slow tasks. The only "downside" is the infrastructure cost, which the user never sees. 🎯


---
---
---
# II- 🏆 Best Production Pattern for Retrieving Taskiq Results

## 🎯 The Hybrid Approach (Redis Fast Path + PostgreSQL Fallback)

This is the **production-grade** pattern: use Redis for speed on recent tasks, PostgreSQL for permanence and guaranteed linkage.

---

## 📊 Why Hybrid Beats Each Individual Approach

| Approach | Speed | Persistence | Guaranteed Linkage | Production-Ready? |
|----------|-------|-------------|-------------------|-------------------|
| **Redis only** (`broker.result_backend.get_result`) | ⚡ Fast | ❌ 1h TTL | ❌ No task_name/args stored | 🟡 No |
| **PostgreSQL only** (`TaskResultService`) | 🐢 Slower | ✅ Permanent | ✅ Yes | ✅ Yes |
| **Hybrid** (Redis → PG fallback) | ⚡ Fast + ✅ Permanent | ✅ Both | ✅ Yes | ✅ **Best** |

---
# 🏆 Production-Grade Refactored Code (Short-Lived Sessions)

## 🎯 The Performance Problem You Identified

```python
# ❌ BAD: Session held open for entire request duration
@router.get("/by-task-id/{task_id}")
async def get_result(task_id: str, session: AsyncSession = Depends(get_db_session)):
    # 1. Check Redis (10ms) — session is OPEN but unused
    redis_result = await broker.result_backend.get_result(task_id)
    
    # 2. JSON processing (5ms) — session is OPEN but unused
    if redis_result:
        return format_result(redis_result)
    
    # 3. Finally use session (2ms) — only now it's needed
    record = await session.execute(stmt)
    
    # Total: Session was open for 17ms, but only used for 2ms
    # Under load: 1000 concurrent requests = 1000 idle sessions!
```

---

## ✅ task_result_service.py : Senior level code

```python
# src/services/task_result_service.py
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.models.db_schemes.cv_analysis_db.db_tables import TaskiqTaskExecution
from src.tk_broker import broker

logger = logging.getLogger(__name__)


class TaskResultService:
    """
    Production-grade result retrieval with Redis fast path + PG fallback.
    
    Uses SHORT-LIVED sessions: sessions are opened only during actual
    DB operations (milliseconds), not for the entire request.
    """
    
    def __init__(self, db_client: async_sessionmaker[AsyncSession]):
        self.session_factory = db_client
    
    async def get_result(self, task_id: str) -> Dict[str, Any]:
        """
        Get result by task_id using HYBRID strategy:
        1. Try Redis first (fast, for tasks completed < 1 hour ago)
        2. Fall back to PostgreSQL (permanent, for older tasks)
        
        Session is only opened for the PostgreSQL fallback (~2ms).
        """
        # ─── FAST PATH: Redis (no session needed!) ─────────────────────────
        try:
            redis_result = await broker.result_backend.get_result(task_id)
        except Exception as e:
            logger.warning("Redis result backend error, falling back to PG: %s", e)
            redis_result = None
        
        if redis_result is not None:
            return {
                "task_id": task_id,
                "status": "SUCCESS" if not redis_result.is_err else "FAILED",
                "result": redis_result.return_value if not redis_result.is_err else None,
                "error": str(redis_result.error) if redis_result.is_err else None,
                "source": "redis",
            }
        
        # ─── FALLBACK: PostgreSQL (session opened HERE, for ~2ms only) ────
        try:
            async with self.session_factory() as session:
                stmt = select(TaskiqTaskExecution).where(
                    TaskiqTaskExecution.taskiq_task_id == task_id
                )
                result = await session.execute(stmt)
                record = result.scalar_one_or_none()
            
            # Session is CLOSED here — outside the `async with` block
            
            if record is None:
                return {"task_id": task_id, "status": "PENDING"}
            
            return {
                "task_id": record.taskiq_task_id,
                "task_name": record.task_name,
                "status": record.status,
                "result": record.result if record.status == "SUCCESS" else None,
                "error": record.error if record.status == "FAILED" else None,
                "enqueued_at": record.enqueued_at.isoformat() if record.enqueued_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                "source": "postgres",
            }
        except SQLAlchemyError as e:
            logger.error("PostgreSQL query failed for task_id %s: %s", task_id, e)
            return {
                "task_id": task_id,
                "status": "ERROR",
                "error": "Database query failed",
                "source": "postgres",
            }
    
    async def get_result_by_input(
        self,
        task_name: str,
        args: list = None,
        kwargs: dict = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get result by EXACT input (guaranteed linkage).
        ALWAYS uses PostgreSQL — Redis doesn't store task_name/args.
        
        Session opened for ~2ms only.
        """
        # Generate the same hash the middleware uses
        payload = {
            "task_name": task_name,
            "args": args or [],
            "kwargs": kwargs or {},
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        task_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(TaskiqTaskExecution)
                    .where(
                        and_(
                            TaskiqTaskExecution.task_args_hash == task_hash,
                            TaskiqTaskExecution.status == "SUCCESS",
                        )
                    )
                    .order_by(TaskiqTaskExecution.completed_at.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                record = result.scalar_one_or_none()
            
            # Session is CLOSED here
            
            if record is None:
                return None
            
            return {
                "task_id": record.taskiq_task_id,
                "task_name": record.task_name,
                "task_hash": record.task_args_hash,
                "input": {
                    "args": record.task_args.get("args", []),
                    "kwargs": record.task_args.get("kwargs", {}),
                },
                "status": record.status,
                "result": record.result,
                "enqueued_at": record.enqueued_at.isoformat() if record.enqueued_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                "linkage_verified": True,
            }
        except SQLAlchemyError as e:
            logger.error("PostgreSQL query failed for input hash %s: %s", task_hash[:12], e)
            return None
    
    async def get_all_executions_by_input(
        self,
        task_name: str,
        args: list = None,
        kwargs: dict = None,
    ) -> list[Dict[str, Any]]:
        """Get ALL executions of the same task signature (for debugging)."""
        payload = {
            "task_name": task_name,
            "args": args or [],
            "kwargs": kwargs or {},
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        task_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(TaskiqTaskExecution)
                    .where(TaskiqTaskExecution.task_args_hash == task_hash)
                    .order_by(TaskiqTaskExecution.enqueued_at.desc())
                )
                result = await session.execute(stmt)
                records = result.scalars().all()
            
            # Session closed here
            
            return [
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
        except SQLAlchemyError as e:
            logger.error("PostgreSQL query failed: %s", e)
            return []
```

---

## ✅ task_result_router.py: Senior level code.

Get Session Factory from App State

```python
# src/routers/task_result_router.py
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.services.task_result_service import TaskResultService

logger = logging.getLogger(__name__)

task_result_router = APIRouter(prefix="/task-results", tags=["Task Results"])


# ─── Request/Response Models ─────────────────────────────────────────────────
class GetResultByInputRequest(BaseModel):
    task_name: str = Field(..., description="e.g., 'src.tasks.test_taskiq:my_task'")
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)


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


# ─── Endpoint 1: Get result by task_id (hybrid) ──────────────────────────────
@task_result_router.get("/by-task-id/{task_id}")
async def get_result_by_task_id(task_id: str, request: Request):
    """
    Hybrid retrieval: Redis (fast) → PostgreSQL (fallback).
    
    Performance: Session opened ONLY if Redis misses (~2ms).
    For Redis hits, no session is opened at all.
    """
    session_factory = _get_session_factory(request)
    service = TaskResultService(session_factory)
    
    result = await service.get_result(task_id)
    
    response = JSONResponse(content=result)
    
    # Cache completed results (they never change)
    if result["status"] in ["SUCCESS", "FAILED"]:
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
    
    return response


# ─── Endpoint 2: Get result by input (guaranteed linkage) ────────────────────
@task_result_router.post("/by-input")
async def get_result_by_input(body: GetResultByInputRequest, request: Request):
    """
    Guaranteed linkage: task_name + args + kwargs → result.
    ALWAYS uses PostgreSQL (Redis doesn't store input).
    
    Performance: Session opened for ~2ms only.
    """
    session_factory = _get_session_factory(request)
    service = TaskResultService(session_factory)
    
    result = await service.get_result_by_input(
        task_name=body.task_name,
        args=body.args,
        kwargs=body.kwargs,
    )
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No successful execution found for this input",
        )
    
    return result


# ─── Endpoint 3: Get ALL executions by input (debugging) ─────────────────────
@task_result_router.post("/all-executions-by-input")
async def get_all_executions_by_input(body: GetResultByInputRequest, request: Request):
    """
    Get ALL executions of the same task signature.
    Useful for debugging idempotency and seeing retry attempts.
    """
    session_factory = _get_session_factory(request)
    service = TaskResultService(session_factory)
    
    results = await service.get_all_executions_by_input(
        task_name=body.task_name,
        args=body.args,
        kwargs=body.kwargs,
    )
    
    return {"count": len(results), "executions": results}
```

---

## 📊 Performance Comparison

### Before (Long-Lived Sessions)
```
Request starts
  ├── Open session (0ms)
  ├── Check Redis (10ms)          ← session IDLE
  ├── Format JSON (5ms)           ← session IDLE
  ├── DB query (2ms)              ← session USED
  ├── Return response (1ms)       ← session IDLE
  └── Close session (0ms)
Total session open time: 18ms
Total session USED time: 2ms
Efficiency: 11% ❌
```

### After (Short-Lived Sessions)
```
Request starts
  ├── Check Redis (10ms)          ← no session
  ├── Format JSON (5ms)           ← no session
  ├── Open session (0ms)
  ├── DB query (2ms)              ← session USED
  ├── Close session (0ms)
  └── Return response (1ms)       ← no session
Total session open time: 2ms
Total session USED time: 2ms
Efficiency: 100% ✅
```

---

## 🎯 Key Benefits

| Aspect | Before (Depends) | After (Session Factory) |
|--------|------------------|------------------------|
| **Session lifetime** | Entire request (ms to seconds) | Only DB operation (~2ms) |
| **Redis hits** | Session still opened (wasted) | No session opened ✅ |
| **Concurrency** | 1000 requests = 1000 open sessions | 1000 requests = ~50 open sessions ✅ |
| **Pool exhaustion risk** | 🔴 High under load | 🟢 Minimal ✅ |
| **Follows your CRUD pattern** | ❌ No | ✅ Yes |
| **Error handling** | Depends on FastAPI | Explicit in service ✅ |

---

## ✅ Ensure FastAPI Lifespan Sets Up Session Factory

Make sure your `main.py` sets up `app.state.db_session_factory`:

```python
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.helpers.config import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    engine = create_async_engine(
        settings.POSTGRES_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    app.state.db_engine = engine
    app.state.db_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    
    yield
    
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

---

## 🎯 Bottom Line

**You're absolutely right** — sessions should never be held open at the endpoint level. This refactored pattern:

1. ✅ Opens sessions **only when needed** (during DB queries)
2. ✅ Closes sessions **immediately after** (via `async with`)
3. ✅ **Skips sessions entirely** on Redis cache hits
4. ✅ Follows your existing `AssetCrud` pattern
5. ✅ Scales better under high concurrency
6. ✅ Reduces database connection pool pressure

This is the **production-grade** pattern for FastAPI + SQLAlchemy async. 🚀
---


---

## 📊 Decision Matrix: Which Method to Use When

| Scenario | Method | Why |
|----------|--------|-----|
| **User just submitted task, has task_id** | `GET /by-task-id/{task_id}` | Hybrid: fast Redis + PG fallback |
| **User lost task_id, knows input** | `POST /by-input` | Guaranteed linkage via hash |
| **User needs result immediately (fast task)** | `await task.wait_result(timeout=5)` | Blocks HTTP but OK for < 1s tasks |
| **User needs result immediately (slow task)** | ❌ Don't do this | Use polling instead |
| **Admin debugging** | `POST /all-executions-by-input` | See all attempts |
| **Internal service-to-service** | Redis directly | Fastest, no DB overhead |

---

## 🏆 The Golden Rules for Production

1. **Return `task_id` immediately** from POST endpoints (don't block HTTP)
2. **Use hybrid retrieval** — Redis for speed, PostgreSQL for permanence
3. **Cache completed results** — they never change
4. **Use exponential backoff** for polling (not fixed intervals)
5. **For guaranteed linkage**, always use PostgreSQL hash-based queries
6. **Save `task_id` in localStorage** so users can recover after page refresh
7. **Authorize access** — users only see their own tasks

---

## 🎯 Bottom Line

**The best production pattern is:**

```
POST /submit-task  →  return task_id immediately (0.1s)
        ↓
Client polls  →  GET /by-task-id/{task_id}
        ↓
Service checks  →  Redis (fast) → PostgreSQL (fallback)
        ↓
Return  →  {status: "SUCCESS", result: {...}}
```

This gives you:
- ✅ **Speed** (Redis sub-ms for recent tasks)
- ✅ **Reliability** (PostgreSQL never loses data)
- ✅ **Guaranteed linkage** (hash-based queries)
- ✅ **Great UX** (no timeouts, instant feedback)
- ✅ **Zero cost** (uses existing infrastructure)

**This is the pattern senior engineers use in production.** 🚀

---
---
---

# III- 🎯 Production Guide: Result Retrieval with User Experience in Mind

## 📋 The Complete User Journey

```
User Action → Queue Task → Get task_id → Poll/Check → Get Result
    │              │            │              │            │
    ▼              ▼            ▼              ▼            ▼
  Click        FastAPI      Return in     User polls   Show result
  button       → Taskiq     0.1s          endpoint     or error
```

---

## 🎯 Which Endpoint to Use When

### Scenario 1: User Has `task_id` (Most Common)
**Use:** `GET /task-results/by-task-id/{task_id}`

**When:** User just submitted a task and wants to check its status.

```python
# Frontend flow
async def check_task_status(task_id: str):
    response = await client.get(f"/task-results/by-task-id/{task_id}")
    if response.status_code == 404:
        return {"status": "pending"}  # Task not in audit yet
    return response.json()
```

### Scenario 2: User Lost `task_id` or Wants to Verify
**Use:** `POST /task-results/by-input`

**When:** User refreshes the page, comes back later, or wants to verify "did my file get processed?"

```python
# User knows they uploaded file_abc123 but lost the task_id
async def verify_file_processed(file_id: str):
    response = await client.post("/task-results/by-input", json={
        "task_name": "indexing:process_file",
        "args": [],
        "kwargs": {"file_id": file_id, "user_id": current_user.id}
    })
    if response.status_code == 404:
        return {"processed": False}
    return {"processed": True, "result": response.json()["result"]}
```

### Scenario 3: Admin/Debug View
**Use:** `POST /task-results/all-executions-by-input`

**When:** Support team investigating "why did this fail?" or debugging idempotency.

```python
# Admin dashboard
async def debug_task(task_name: str, kwargs: dict):
    response = await client.post("/task-results/all-executions-by-input", json={
        "task_name": task_name,
        "args": [],
        "kwargs": kwargs
    })
    return response.json()  # Shows ALL attempts (successes + failures)
```

---

## 🔄 The Smart Polling Strategy (Production-Ready)

Don't hammer your server with requests. Use **exponential backoff**:

```python
# Frontend polling service
import asyncio
from typing import Callable, Optional

async def poll_task_result(
    task_id: str,
    on_progress: Optional[Callable] = None,
    max_wait: int = 300,  # 5 minutes max
) -> dict:
    """
    Poll for task result with exponential backoff.
    
    Returns the final result or raises TimeoutError.
    """
    # Polling intervals: 0.5s, 1s, 2s, 4s, 8s, 16s, 30s, 30s, 30s...
    intervals = [0.5, 1, 2, 4, 8, 16] + [30] * 20
    
    elapsed = 0
    for interval in intervals:
        if elapsed >= max_wait:
            raise TimeoutError(f"Task {task_id} did not complete in {max_wait}s")
        
        response = await client.get(f"/task-results/by-task-id/{task_id}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Task completed
            if data["status"] in ["SUCCESS", "FAILED"]:
                return data
            
            # Task still running
            if on_progress:
                on_progress(data)
        
        await asyncio.sleep(interval)
        elapsed += interval
    
    raise TimeoutError(f"Task {task_id} timed out")
```

### Frontend Integration (React Example)

```jsx
function TaskStatus({ taskId }) {
  const [status, setStatus] = useState('pending');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    
    async function poll() {
      const intervals = [500, 1000, 2000, 4000, 8000, 16000, 30000];
      let i = 0;
      
      while (!cancelled && i < intervals.length) {
        try {
          const res = await fetch(`/task-results/by-task-id/${taskId}`);
          const data = await res.json();
          
          if (data.status === 'SUCCESS') {
            setStatus('success');
            setResult(data.result);
            return;
          }
          if (data.status === 'FAILED') {
            setStatus('failed');
            setError(data.error);
            return;
          }
          
          setStatus('processing');
        } catch (e) {
          console.error('Poll error:', e);
        }
        
        await new Promise(r => setTimeout(r, intervals[i]));
        i++;
      }
      
      if (!cancelled) setStatus('timeout');
    }
    
    poll();
    return () => { cancelled = true; };
  }, [taskId]);

  return (
    <div>
      {status === 'pending' && <Spinner />}
      {status === 'processing' && <ProgressBar />}
      {status === 'success' && <ResultDisplay data={result} />}
      {status === 'failed' && <ErrorMessage error={error} />}
      {status === 'timeout' && <TimeoutMessage />}
    </div>
  );
}
```

---

## 🚀 Alternative: Server-Sent Events (SSE) for Real-Time Updates

Instead of polling, push updates to the user:

```python
# src/routers/task_result_router.py
from fastapi.responses import StreamingResponse
import asyncio

@task_result_router.get("/stream/{task_id}")
async def stream_task_result(
    task_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Stream task status updates via SSE."""
    
    async def event_generator():
        service = TaskResultService(session)
        intervals = [0.5, 1, 2, 4, 8, 16, 30]
        
        for interval in intervals:
            result = await service.get_result_by_task_id(task_id)
            
            if result is None:
                data = {"status": "pending"}
            else:
                data = result
            
            yield f"data: {json.dumps(data)}\n\n"
            
            # Stop if completed
            if result and result["status"] in ["SUCCESS", "FAILED"]:
                break
            
            await asyncio.sleep(interval)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

**Frontend:**
```javascript
const eventSource = new EventSource(`/task-results/stream/${taskId}`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateUI(data);
  if (data.status === 'SUCCESS' || data.status === 'FAILED') {
    eventSource.close();
  }
};
```

---

## 🏭 Production Considerations

### 1. **Caching for Hot Results**

```python
from functools import lru_cache
from datetime import datetime, timedelta

@task_result_router.get("/by-task-id/{task_id}")
async def get_result_by_task_id(
    task_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    service = TaskResultService(session)
    result = await service.get_result_by_task_id(task_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Add cache headers for completed tasks
    response = JSONResponse(content=result)
    if result["status"] in ["SUCCESS", "FAILED"]:
        # Cache completed results for 1 hour
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        # Don't cache pending results
        response.headers["Cache-Control"] = "no-store"
    
    return response
```

### 2. **Rate Limiting (Prevent Abuse)**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@task_result_router.get("/by-task-id/{task_id}")
@limiter.limit("30/minute")  # Max 30 polls per minute per user
async def get_result_by_task_id(request: Request, task_id: str, ...):
    ...
```

### 3. **Authorization (User Can Only See Their Tasks)**

```python
@task_result_router.get("/by-task-id/{task_id}")
async def get_result_by_task_id(
    task_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    service = TaskResultService(session)
    result = await service.get_result_by_task_id(task_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 🔒 SECURITY: Verify the task belongs to this user
    # (You need to store user_id in task_args when queueing)
    task_user_id = result["input"]["kwargs"].get("user_id")
    if task_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return result
```

### 4. **Performance: Add Database Indexes**

```sql
-- Critical indexes for fast queries
CREATE INDEX idx_taskiq_task_id ON taskiq_task_executions(taskiq_task_id);
CREATE INDEX idx_taskiq_hash ON taskiq_task_executions(task_args_hash);
CREATE INDEX idx_taskiq_name_status ON taskiq_task_executions(task_name, status);
CREATE INDEX idx_taskiq_enqueued ON taskiq_task_executions(enqueued_at DESC);
```

---

## 🎯 Complete Production Flow Example

### Backend: Queue + Result Endpoints

```python
# src/routers/tasks.py
from fastapi import APIRouter, Depends
from src.tasks.indexing import process_file_task
from src.tk_broker import broker

tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])

@tasks_router.post("/process-file", status_code=202)
async def queue_process_file(
    request: ProcessFileRequest,
    current_user: User = Depends(get_current_user)
):
    """Queue a file processing task."""
    task = await process_file_task.kiq(
        file_id=request.file_id,
        user_id=current_user.id,  # ← Store user_id for authorization
    )
    return {
        "task_id": task.task_id,
        "status": "queued",
        "poll_url": f"/task-results/by-task-id/{task.task_id}",
        "stream_url": f"/task-results/stream/{task.task_id}",
    }
```

### Frontend: Complete User Flow

```javascript
// 1. Submit task
const submitTask = async (fileId) => {
  const response = await fetch('/tasks/process-file', {
    method: 'POST',
    body: JSON.stringify({ file_id: fileId }),
  });
  const { task_id, poll_url } = await response.json();
  
  // 2. Save task_id in localStorage (user can come back later)
  localStorage.setItem(`task_${fileId}`, task_id);
  
  // 3. Start polling
  startPolling(task_id);
};

// 4. Poll with exponential backoff
const startPolling = async (taskId) => {
  const intervals = [500, 1000, 2000, 4000, 8000, 16000, 30000];
  
  for (const interval of intervals) {
    const response = await fetch(`/task-results/by-task-id/${taskId}`);
    
    if (response.status === 404) {
      showStatus('pending');
    } else {
      const data = await response.json();
      
      if (data.status === 'SUCCESS') {
        showResult(data.result);
        return;
      }
      if (data.status === 'FAILED') {
        showError(data.error);
        return;
      }
      
      showStatus('processing');
    }
    
    await sleep(interval);
  }
  
  showError('Task timed out. Please check back later.');
};

// 5. User refreshes page → recover from localStorage
const recoverTask = (fileId) => {
  const taskId = localStorage.getItem(`task_${fileId}`);
  if (taskId) {
    startPolling(taskId);
  }
};
```

---

## 🏆 Production Checklist

- [ ] **Polling strategy**: Exponential backoff (not fixed interval)
- [ ] **Caching**: Cache completed results, don't cache pending
- [ ] **Rate limiting**: Prevent poll abuse (30/min per user)
- [ ] **Authorization**: Users can only see their own tasks
- [ ] **Database indexes**: On `task_id`, `task_hash`, `task_name`
- [ ] **Timeout handling**: Frontend shows timeout after max wait
- [ ] **Recovery**: Save `task_id` in localStorage for page refresh
- [ ] **Error messages**: Clear, actionable errors (not generic 500s)
- [ ] **SSE option**: For real-time updates without polling
- [ ] **Monitoring**: Track poll endpoint latency and error rates

---

## 🎯 Key Takeaways

1. **`by-task-id`** = Primary endpoint (user just submitted task)
2. **`by-input`** = Recovery endpoint (user lost task_id or verifying)
3. **`all-executions-by-input`** = Admin/debug endpoint
4. **Poll with exponential backoff** — don't hammer the server
5. **Cache completed results** — they never change
6. **Authorize access** — users only see their tasks
7. **Save task_id in localStorage** — survive page refreshes
8. **Consider SSE** — better UX than polling for long tasks

**Bottom line**: The endpoints you built are production-ready. The key is wrapping them with smart polling, caching, rate limiting, and authorization to create a great user experience. 🚀
