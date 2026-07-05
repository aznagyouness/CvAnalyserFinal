# I- RPM Management — Production Solution

Drop-in code for a production-grade Generative AI platform. Copy these files, set the env vars, and you're done.

---

## 📁 File Structure

```
src/
├── helpers/
│   ├── config.py              # ← add the new settings (snippet below)
│   └── quota.py               # ← GlobalLLMQuota
├── utils/
│   └── taskiq_rate_limiter.py # ← RedisTokenBucketMiddleware
├── tk_broker.py               # ← wire the new middleware in
└── main.py                    # ← FastAPI lifespan wires the quota managers
```

---

## 1. Settings — `src/helpers/config.py`

Add these fields to your existing `Settings` class:

```python
# ─── LLM Rate Limits ────────────────────────────────────────────────────────
MAX_RPM_EMBEDDING: int = 1500      # cheap embeddings
MAX_RPM_GENERATION: int = 20       # expensive LLM calls

# ─── Redis URLs (one Redis, multiple logical DBs) ───────────────────────────
REDIS_URL_QUOTA: str       = "redis://localhost:6379/0"   # quota counters
REDIS_URL_TASKIQ_LIMITER: str = "redis://localhost:6379/2"  # token bucket
REDIS_URL_TASKIQ_RESULTS: str  = "redis://localhost:6379/1"  # taskiq results
```

---

## 2. Global Quota Manager — `src/helpers/quota.py`

```python
# src/helpers/quota.py
from __future__ import annotations

import asyncio
import logging
import random
import time

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class GlobalLLMQuota:
    """
    Distributed per-lane RPM limiter backed by Redis.
    Used by FastAPI routes to gate interactive LLM calls.
    """

    def __init__(self, redis_url: str, max_rpm: int, key_prefix: str):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.max_rpm = max_rpm
        self.key_prefix = key_prefix

    async def wait_for_slot(self) -> None:
        """Block until a slot is free in the current UTC minute window."""
        while True:
            now_utc = time.time()
            current_minute = int(now_utc // 60)
            key = f"{self.key_prefix}:{current_minute}"

            # Atomic INCR + EXPIRE on first hit. Prevents leaked keys.
            lua = """
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return count
            """
            try:
                count = await self.redis.eval(lua, 1, key, 120)
            except Exception as e:
                # Fail-open: never crash the chatbot because Redis is down.
                logger.warning(
                    "Quota Manager (%s): Redis unavailable, failing open. Error: %s",
                    self.key_prefix, e,
                )
                return

            if count <= self.max_rpm:
                return

            # Sleep until the next minute + jitter to avoid thundering herd.
            next_minute_start = (current_minute + 1) * 60
            sleep_time = (next_minute_start - now_utc) + random.uniform(0.05, 0.2)
            await asyncio.sleep(max(0, sleep_time))

    async def close(self) -> None:
        await self.redis.aclose()
```

---

## 3. Taskiq Rate Limiter — `src/utils/taskiq_rate_limiter.py`

```python
# src/utils/taskiq_rate_limiter.py
from __future__ import annotations

import logging
import time
from typing import Any

from redis.asyncio import Redis
from taskiq import TaskiqMiddleware, TaskiqMessage

logger = logging.getLogger(__name__)


class RedisTokenBucketMiddleware(TaskiqMiddleware):
    """
    Per-task Redis token-bucket rate limiter.
    Used by Taskiq to throttle background tasks across all workers.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        rate: float,        # tokens per second
        capacity: int,      # max bucket size (burst)
        key_prefix: str = "ratelimit",
    ):
        self._redis_url = redis_url
        self._rate = rate
        self._capacity = capacity
        self._key_prefix = key_prefix
        self._redis: Redis | None = None

    async def startup(self) -> None:
        if self._redis is not None:
            return
        self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        await self._redis.ping()
        logger.info("RedisTokenBucketMiddleware connected to Redis")

    async def shutdown(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        except Exception:
            logger.exception("error closing rate-limiter Redis connection")
        self._redis = None

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        if self._redis is None:
            raise RuntimeError("RedisTokenBucketMiddleware not started")

        key = f"{self._key_prefix}:{message.task_name}"
        now = time.time()

        lua = """
        local key       = KEYS[1]
        local rate      = tonumber(ARGV[1])
        local capacity  = tonumber(ARGV[2])
        local now       = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'ts')
        local tokens = tonumber(bucket[1]) or capacity
        local ts     = tonumber(bucket[2]) or now

        local delta  = math.max(0, now - ts)
        tokens = math.min(capacity, tokens + delta * rate)

        if tokens >= requested then
            tokens = tokens - requested
            redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
            redis.call('EXPIRE', key, 3600)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
            redis.call('EXPIRE', key, 3600)
            return 0
        end
        """
        ok = await self._redis.eval(
            lua, 1, key, self._rate, self._capacity, now, 1,
        )
        if not ok:
            raise Exception(f"rate-limited: {message.task_name}")
        return message
```

---

## 4. Wire Into Broker — `src/tk_broker.py`

Add the import and add it to your `with_middlewares(...)` chain. Place it **before** the retry middleware:

```python
from src.utils.taskiq_rate_limiter import RedisTokenBucketMiddleware

# ... your existing broker + idempotency setup ...

broker = broker.with_middlewares(
    idempotency_middleware,
    RedisTokenBucketMiddleware(
        redis_url=settings.REDIS_URL_TASKIQ_LIMITER,
        rate=10,           # 10 tokens/sec per task_name
        capacity=20,       # burst of 20
    ),
    IdempotencyAwareRetryMiddleware(default_retry_count=3),
    PrometheusMiddleware(server_addr="0.0.0.0", server_port=9000),
)
```

---

## 5. Wire Into FastAPI — `src/main.py`

```python
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from src.helpers.config import get_settings
from src.helpers.quota import GlobalLLMQuota

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lane 1: Embedding (cheap, high RPM)
    app.state.embedding_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_EMBEDDING,
        key_prefix="quota:llm_embedding",
    )

    # Lane 2: Generation (expensive, low RPM)
    app.state.generation_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_GENERATION,
        key_prefix="quota:llm_generation",
    )

    yield

    await app.state.embedding_quota.close()
    await app.state.generation_quota.close()


app = FastAPI(lifespan=lifespan)


# ─── Example routes ─────────────────────────────────────────────────────────

@app.post("/search/{project_id}")
async def search_project(request: Request, payload: dict):
    """Embedding lane — gates cheap embedding calls."""
    await request.app.state.embedding_quota.wait_for_slot()
    # ... embedding + vector search ...
    return {"results": [...]}


@app.post("/answer/stream")
async def answer_stream(request: Request, payload: dict):
    """Generation lane — gates expensive LLM streaming calls."""
    await request.app.state.generation_quota.wait_for_slot()
    # ... stream from LLM ...
    return {"answer": "..."}
```

---

## 6. Strip Provider Classes

In your LLM provider classes (e.g. `QwenModel`, `OpenAIModel`), **remove**:

- ❌ `max_requests_per_minute`
- ❌ `max_concurrent_requests`
- ❌ `self.rpm_limiter = AsyncLimiter(...)`

Provider classes should only know how to talk to the LLM API. Rate control lives at the application layer.

---

## 7. Environment Variables (`.env`)

```bash
# Rate limits (per minute, per lane)
MAX_RPM_EMBEDDING=1500
MAX_RPM_GENERATION=20

# Redis — one instance, three logical DBs
REDIS_URL_QUOTA=redis://localhost:6379/0
REDIS_URL_TASKIQ_LIMITER=redis://localhost:6379/2
REDIS_URL_TASKIQ_RESULTS=redis://localhost:6379/1
```

---

## 8. Quick Smoke Test

After deploying, hit Redis to verify the counters are working:

```bash
# Watch the embedding quota counter tick up
redis-cli -n 0 --scan --pattern 'quota:llm_embedding:*' | while read key; do
  echo "$key → $(redis-cli -n 0 GET "$key") (TTL $(redis-cli -n 0 TTL "$key")s)"
done

# Watch the token-bucket state
redis-cli -n 2 --scan --pattern 'ratelimit:*' | while read key; do
  echo "$key → $(redis-cli -n 2 HGETALL "$key")"
done
```

You should see the counters increment under load and the TTL stay close to 120s / 3600s respectively.

---

## ✅ Deploy Checklist

- [ ] `Settings` has `MAX_RPM_EMBEDDING`, `MAX_RPM_GENERATION`, three `REDIS_URL_*`
- [ ] `src/helpers/quota.py` exists with `GlobalLLMQuota`
- [ ] `src/utils/taskiq_rate_limiter.py` exists with `RedisTokenBucketMiddleware`
- [ ] `RedisTokenBucketMiddleware` is in `tk_broker.with_middlewares(...)`
- [ ] `lifespan` in `main.py` instantiates both `embedding_quota` and `generation_quota`
- [ ] Each route calls `await request.app.state.<lane>_quota.wait_for_slot()` before any LLM call
- [ ] LLM provider classes stripped of all local rate-limit fields
- [ ] `aclose()` called on shutdown in both `lifespan` and broker middleware
- [ ] Redis logical DBs split: 0=quota, 1=results, 2=rate limiter
- [ ] `.env` populated with the four variables above

---
---

# II- 🚀 Details & discussion of RPM Management in Generative AI :

> **A production-grade architectural blueprint for managing Requests Per Minute (RPM) in RAG and Chatbot systems.** This guide documents the evolution of rate-limiting strategies — from local workarounds to a **Hybrid Strategy** that combines background-task queuing with real-time streaming.

---

## 🏛️ 1. The Evolution of the Shield

There are three "shields" you can put in front of an LLM provider. They protect against different failure modes. You need all three, in the right order.

### **Level 1: The Local Workaround (`AsyncLimiter`)**

Often found inside provider classes (e.g., `qwen_model.py`), this is a limiter living inside the function code itself.

* **The Logic**: `self.rpm_limiter = AsyncLimiter(10, 60)`
* **The Fatal Flaw**: It is **isolated**. If you scale to 4 worker processes, each worker is "blind" to the others.

* **The Math**:
  - Worker #1 says: "I'm allowed 10 requests. Sending 10…"
  - Worker #2 says: "I'm allowed 10 requests. Sending 10…"
  - Worker #3 says: "I'm allowed 10 requests. Sending 10…"
  - Worker #4 says: "I'm allowed 10 requests. Sending 10…"
  - **Total sent to LLM Provider**: **40 RPM**
  - **Outcome**: **CRASH.** Your LLM provider sees 40 requests in one minute, identifies you've exceeded the 10 RPM limit, and blocks your API key. Every user starts seeing `429 Too Many Requests`.

* **Verdict**: ❌ **Anti-pattern in multi-worker production.** Avoid.

---

### **Level 2: The Front-Door Guard (`SlowAPI`)**

A FastAPI middleware that counts requests per minute per IP address.

* **The Logic**: `@limiter.limit("5/minute")`
* **The Strength**: Protects your server from DDoS and spam from a single IP.
* **The Fatal Flaw**: It doesn't protect your **global wallet**. If 1,000 different "good" users each send 1 request, SlowAPI lets them all through.

* **The Math**:
  - User #1 (IP: 1.1.1.1) sends 5 requests. (Allowed ✅)
  - User #2 (IP: 2.2.2.2) sends 5 requests. (Allowed ✅)
  - User #100 sends 5 requests. (Allowed ✅)
  - **Total sent to LLM Provider**: **500 RPM**
  - **Outcome**: **CRASH.** SlowAPI protected your server from one bad user, but failed to protect your API key from the **Thundering Herd** of many good users.

* **Verdict**: 🛡️ **Security essential.** Use it — but for DDoS protection, not budget control.

---

### **Level 3: The Infrastructure Commander (Distributed Redis Token Bucket)**

A global policy enforced at the task-queue level using Redis as the **single source of truth**.

> ⚠️ **Correction from earlier draft**: Taskiq core does **not** ship a built-in `rate_limit` parameter on `@broker.task`, nor does `taskiq-rate-limiter` exist on PyPI. You have to write the middleware yourself. ~30 lines.

* **The Logic**: A `RedisTokenBucketMiddleware` sits between the broker and your tasks. Every worker hits Redis atomically before executing a task.
* **The Strength**: Total visibility across all workers. It turns a Thundering Herd into a disciplined, unbreakable stream.

* **The Math**:
  - 100 users each send 1 indexing task at the same time.
  - **Redis token bucket** holds exactly `capacity` tokens, refilling at `rate` per second.
  - Worker #1 grabs 25 tokens; Worker #2 grabs 25 tokens; Workers #3-4 grab the rest.
  - **Total sent to LLM Provider**: **Exactly the configured rate.**
  - **Outcome**: **Stability.** Tasks finish at the rate you configured. Excess tasks wait in the RabbitMQ queue (or are rate-limited) and finish in subsequent windows. No `429`s, no bans, just perfect orchestration.

* **The Limitation**: Adds latency. Background tasks tolerate it; interactive streaming does not.
* **Verdict**: 💎 **Production standard for heavy lifting** (indexing, OCR, batching).

#### **Reference implementation**

```python
# src/utils/taskiq_rate_limiter.py
from __future__ import annotations
import logging
import time
from typing import Any
from redis.asyncio import Redis
from taskiq import TaskiqMiddleware, TaskiqMessage

logger = logging.getLogger(__name__)


class RedisTokenBucketMiddleware(TaskiqMiddleware):
    """Per-task Redis token-bucket rate limiter."""

    def __init__(
        self,
        *,
        redis_url: str,
        rate: float,        # tokens per second
        capacity: int,      # max bucket size (burst)
        key_prefix: str = "ratelimit",
    ):
        self._redis_url = redis_url
        self._rate = rate
        self._capacity = capacity
        self._key_prefix = key_prefix
        self._redis: Redis | None = None

    async def startup(self) -> None:
        if self._redis is not None:
            return
        self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        await self._redis.ping()
        logger.info("RedisTokenBucketMiddleware connected")

    async def shutdown(self) -> None:
        if self._redis is None:
            return
        await self._redis.aclose()
        self._redis = None

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        if self._redis is None:
            raise RuntimeError("not started")

        key = f"{self._key_prefix}:{message.task_name}"
        now = time.time()

        # Atomic Lua token bucket
        lua = """
        local key       = KEYS[1]
        local rate      = tonumber(ARGV[1])
        local capacity  = tonumber(ARGV[2])
        local now       = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'ts')
        local tokens = tonumber(bucket[1]) or capacity
        local ts     = tonumber(bucket[2]) or now

        local delta  = math.max(0, now - ts)
        tokens = math.min(capacity, tokens + delta * rate)

        if tokens >= requested then
            tokens = tokens - requested
            redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
            redis.call('EXPIRE', key, 3600)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
            redis.call('EXPIRE', key, 3600)
            return 0
        end
        """

        ok = await self._redis.eval(
            lua, 1, key, self._rate, self._capacity, now, 1,
        )
        if not ok:
            # Re-raise so the broker nacks and the message is requeued.
            # For "drop instead of requeue" semantics, swap this for an ack.
            raise Exception(f"rate-limited: {message.task_name}")

        return message
```

Wire it in `tk_broker.py`:

```python
broker = broker.with_middlewares(
    idempotency_middleware,
    RedisTokenBucketMiddleware(
        redis_url=settings.REDIS_URL_TASKIQ_LIMITER,
        rate=10,           # 10 tokens/sec per task_name
        capacity=20,       # burst of 20
    ),
    IdempotencyAwareRetryMiddleware(default_retry_count=3),
    PrometheusMiddleware(server_addr="0.0.0.0", server_port=9000),
)
```

---

## 👑 2. The Final Boss: The Hybrid Strategy

The ultimate solution for Generative AI: satisfy the user with **word-by-word streaming** while maintaining **strict global budget control**.

### **The Blueprint**

We split the application into two lanes:

1. **The Background Lane (Taskiq + RedisTokenBucket)** — for indexing, OCR, batching.
2. **The Interactive Lane (FastAPI + Global Quota)** — for chat and search.

### **The "Global Waiting Room" Pattern**

Instead of rejecting the 11th request with a `429`, we make the user wait in a "Global Waiting Room" managed by Redis. They stay connected, and the stream starts as soon as a slot opens.

* **The Math**:
  - User #1 starts a chat stream. (Redis slot 1/50 taken ✅)
  - User #2 starts a search. (Redis slot 2/50 taken ✅)
  - 48 more users join the Global Waiting Room. (Redis slots 3–50 taken ✅)
  - **User #51** tries to start a chat. Redis says "WAIT."
  - **Total sent to LLM Provider**: **Exactly 50 RPM.**
  - **Outcome**: User #51's stream simply "pauses" for a few seconds. As soon as User #1 finishes, User #51's words start appearing word-by-word. No errors, no frustration, just a premium feel.

### **The "Global Waiting Room" Implementation**

#### **Step 1: The Global Quota Manager (`src/helpers/quota.py`)**

```python
# src/helpers/quota.py
import asyncio
import time
import random
import logging
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class GlobalLLMQuota:
    """
    Distributed Quota Manager to protect LLM API keys
    while allowing real-time SSE streaming.
    """

    def __init__(self, redis_url: str, max_rpm: int, key_prefix: str):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.max_rpm = max_rpm
        self.key_prefix = key_prefix  # Lane ID (e.g. "quota:llm_embedding")

    async def wait_for_slot(self):
        """
        Pauses execution until a global slot is available.
        Transparent to the user (they just see a slightly longer 'loading' state).
        """
        while True:
            # 1. UTC minute window — synchronized across all servers.
            now_utc = time.time()
            current_minute = int(now_utc // 60)
            key = f"{self.key_prefix}:{current_minute}"

            # 2. Lua script: atomic INCR + EXPIRE on first hit.
            #    Prevents leaked keys if a process crashes between INCR and EXPIRE.
            lua = """
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return count
            """
            try:
                count = await self.redis.eval(lua, 1, key, 120)
            except Exception as e:
                # 🛡️ Fail-Open: don't crash the chatbot if Redis is down.
                logger.warning(
                    "Quota Manager (%s): Redis unavailable, failing open. Error: %s",
                    self.key_prefix, e,
                )
                return

            if count <= self.max_rpm:
                return  # Slot acquired — proceed to LLM call.

            # 3. Sleep until next minute + jitter (Thundering-Herd defense).
            next_minute_start = (current_minute + 1) * 60
            sleep_time = (next_minute_start - now_utc) + random.uniform(0.05, 0.2)
            await asyncio.sleep(max(0, sleep_time))

    async def close(self):
        """Gracefully close the Redis connection pool."""
        await self.redis.aclose()  # aclose(), not close() — redis-py 4.2+
```

#### **Why this is the production-grade implementation**

1. **Lua Script for Atomicity** — In a distributed system, a process can crash between `INCR` and `EXPIRE`, leaving a key with no TTL. A Lua script combines both ops into one unbreakable atomic action.

2. **Traffic Smoothing (Jitter)** — If 100 requests are waiting for the next minute, they shouldn't all wake up at the exact same millisecond. 50–200 ms of random jitter spreads the load.

3. **Fail-Open Reliability** — If Redis goes down, the chatbot still works. We log a warning and let the request through rather than 5xx-ing the user.

4. **UTC Synchronization** — Using `time.time()` (UTC) for key generation ensures all servers worldwide reference the same minute window. Server-local time would break across regions.

5. **Infrastructure Hygiene** — `aclose()` is called during FastAPI shutdown to release the connection pool.

#### **Caveat: behavior under sustained burst**

The "exactly 50 RPM" claim is only true under **steady-state** load. Under sustained burst where demand >> capacity, the waiting-requests queue grows unboundedly and per-user latency can spike to many minutes. This is fundamental to any rate limiter — if you need to absorb bursts, increase `max_rpm` or pre-queue requests upstream.

---

## 🛣️ 3. The "Multi-Lane Highway" Implementation

In a professional RAG system, you don't have one RPM limit. You have different limits for **Embedding** (cheap, high RPM) and **Generation** (expensive, low RPM).

If you use a single global quota, your cheap search requests might block your expensive generation requests. The fix is a **Multi-Lane Highway**.

### **Step 1: Orchestration in `main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.helpers.quota import GlobalLLMQuota


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lane 1: Embedding Quota (e.g. 1500 RPM)
    app.state.embedding_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_EMBEDDING,
        key_prefix="quota:llm_embedding",
    )

    # Lane 2: Generation Quota (e.g. 20 RPM)
    app.state.generation_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_GENERATION,
        key_prefix="quota:llm_generation",
    )
    yield

    # Shutdown: close both lanes.
    await app.state.embedding_quota.close()
    await app.state.generation_quota.close()


app = FastAPI(lifespan=lifespan)
```

### **Step 2: Route Integration**

#### **Lane A — Search Shield (`src/routes/nlp.py`)**

```python
from fastapi import APIRouter, Request

nlp_router = APIRouter()


@nlp_router.post("/search/{project_id}")
async def search_project(request: Request, payload: dict):
    # Acquire an embedding slot before hitting the embedding model.
    quota_manager = request.app.state.embedding_quota
    await quota_manager.wait_for_slot()

    # ... proceed to embedding + search ...
```

#### **Lane B — Answer Shield (`src/routes/stream.py`)**

```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

stream_router = APIRouter()


@stream_router.post("/answer/stream")
async def answer_stream(request: Request, payload: dict):
    # Acquire a generation slot before streaming.
    quota_manager = request.app.state.generation_quota
    await quota_manager.wait_for_slot()

    # ... proceed to stream word-by-word ...
```

---

## 🏛️ 4. Pro Infrastructure: The Redis Logical-Database Pattern

Imagine a 16-room mansion — this is your Redis instance. Each room has a number from **0 to 15**. These are **Logical Databases**.

If you dump your quota counters, your task results, and your rate-limiter buckets all into Room 0, you have a mess. One careless `FLUSHDB` wipes everything. In tech, we call this a **Key Collision** and a **Blast-Radius Problem**.

By assigning different indices (`/0`, `/1`, `/2`), you give each subsystem its own private room.

```python
# Global Quota Manager — DB 0
quota_redis_url = "redis://localhost:6379/0"

# Taskiq Result Backend — DB 1
result_backend = RedisAsyncResultBackend(redis_url="redis://localhost:6379/1")

# Taskiq Rate Limiter (your custom middleware) — DB 2
rate_limiter = RedisTokenBucketMiddleware(redis_url="redis://localhost:6379/2")
```

> ⚠️ **Correction from earlier draft**: `RedisRateLimiter` from `taskiq-redis` doesn't exist. Use the custom `RedisTokenBucketMiddleware` from Section 1 Level 3.

### **Why this layout?**

#### **1. DB 0 — The Global Quota Manager (The Brain)**

* Holds the Hybrid Strategy counters (`quota:llm_embedding:…`, `quota:llm_generation:…`).
* Most sensitive data. By isolating it, no other library can accidentally delete or overwrite your RPM counters.

#### **2. DB 1 — Taskiq Result Backend (The Archive)**

* Stores background task results (`Task #123 finished successfully`).
* Taskiq generates thousands of keys for results. Isolating them keeps DB 0 fast.

#### **3. DB 2 — Taskiq Rate Limiter (The Traffic Control)**

* Holds token-bucket state (`ratelimit:my_task`).
* Keeps the rate limiter's HMGET/HMSET traffic out of the quota counters' path.

### **Master-class benefits**

* **Flush Safety** — `FLUSHDB` on DB 1 wipes old results without touching your quota counters. Same for DB 0, 1, 2 independently.
* **Debugging Clarity** — Tools like *Redis Insight* let you switch between rooms visually. You'll see exactly what's happening in each subsystem.
* **Zero Infra Cost** — Still one Redis server. Logical databases cost nothing.

---

## 🛠️ 5. The Decoupling Principle: Application-Level Control

In a production-grade system, your LLM provider classes (e.g. `QwenModel`) should be **dumb workers**. They should only know how to format prompts and call APIs. They should **not** manage the politics of how fast they are allowed to run.

### **What to Remove from Low-Level Providers**

* ❌ `max_requests_per_minute`
* ❌ `max_concurrent_requests`
* ❌ `self.rpm_limiter = AsyncLimiter(...)`

### **Why Decoupling Is the Pro Move**

1. **Single Responsibility** — Your LLM folder stays clean. It only contains API communication and response parsing.
2. **Centralized Orchestration** — The source of truth moves to your `.env` and `Settings`:
   * Interactive lane: `settings.MAX_RPM_EMBEDDING` → `GlobalLLMQuota(max_rpm=…)` in your FastAPI routes.
   * Background lane: `settings.MAX_RPM_EMBEDDING` → `RedisTokenBucketMiddleware(rate=…)` in your Taskiq tasks.
3. **Infrastructure Over Implementation** — Redis (infrastructure) holds the state, not Python variables. You can scale to hundreds of containers without a single blind worker crashing your API key.

---

## 🎯 6. Summary Verdict

| Strategy                | User Experience | Global Safety | Best For                          |
| :---------------------- | :-------------- | :------------ | :-------------------------------- |
| `AsyncLimiter` (local)  | Fast            | ❌ None        | Single-process scripts            |
| `SlowAPI` (per-IP)      | Fast            | 🛡️ Per-user    | DDoS protection                   |
| `RedisTokenBucket` (Taskiq) | Queued     | ✅ 100%        | Indexing, OCR, batching           |
| `GlobalLLMQuota` (Hybrid) | Streaming   | ✅ 100%        | Chatbots, interactive Q&A, RAG    |

### **Final Wisdom**

Treat your LLM provider as a finite resource. Use **Redis as the Brain**, **Taskiq as the Muscle**, and **FastAPI as the Voice**.

* **Redis as the Brain** — holds the global state of who is allowed to do what right now.
* **Taskiq as the Muscle** — does the heavy lifting asynchronously, throttled by your token-bucket middleware.
* **FastAPI as the Voice** — talks to the user in real-time, gated by your global quota manager.

That is how you build an unbreakable, high-performance Generative AI platform. 🟢

---

## 📎 Appendix: Quick-Reference Checklist

Before going to production, verify:

- [ ] No `AsyncLimiter` inside any provider class — moved to Redis
- [ ] `SlowAPI` mounted in FastAPI for per-IP DDoS protection
- [ ] `RedisTokenBucketMiddleware` configured in `tk_broker.py` for background tasks
- [ ] `GlobalLLMQuota` instantiated in `lifespan` for both embedding and generation lanes
- [ ] `aclose()` called on every Redis client during shutdown
- [ ] Redis split across logical DBs (0 = quota, 1 = results, 2 = rate limiter)
- [ ] Settings (`MAX_RPM_EMBEDDING`, `MAX_RPM_GENERATION`) read from `.env`, not hard-coded
- [ ] LLM provider classes stripped of all rate-limit fields
- [ ] `IDEMPOTENCY_STRICT_AUDIT` validated at startup, not per-request
- [ ] Jitter range (50–200 ms) tuned for your traffic shape