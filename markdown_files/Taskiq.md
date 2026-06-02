# 🚀 Taskiq Configuration (Production Mind-Map Friendly)

## Taskiq Application
### Definition:
- Taskiq is an **asynchronous distributed task queue** built specifically for modern Python (FastAPI, asyncio).
- It relies on a **broker** (transport) and an optional **result backend** (storage).
- **Major Advantage**: Native `async/await` support and FastAPI-style Dependency Injection.

---
## 3-Step Mental Model:
### 1- Design Phase 📐 = `@broker.task`
- You define your function with the `@broker.task` decorator.
- Unlike Celery's `s()`, Taskiq tasks are just functions until they are "kiqed".
- **Signature equivalent**: Taskiq uses `TaskReceipt` after sending, but the planning is done via the decorator options or the `Kicker`.

### 2- Construction Phase 🏗️ (Dispatching) = `.kiq()` / `.kicker()`
- **Method**: `task.kiq(*args, **kwargs)`
- **Return**: `TaskReceipt` object ==> with it we can get task id, and wait for result.
- **Mental Model**: "I am sending this task to the broker now." It returns immediately with a `task_id`.
- **Advanced**: Use `.kicker()` to add labels, timeouts, or custom routing before calling `.kiq()`.

### 3- Waiting Phase ⏳ = `.wait_result()`
- **Method**: `TaskReceipt.wait_result()`
- **Return**: `TaskiqResult` containing `return_value`, `execution_time`, and `is_err`.
- **Mental Model**: "I am waiting for the worker to finish and give me the output."

### Example:
```python
# 1. Define
@broker.task
async def add(a: int, b: int):
    return a + b

# 2. Start (The .delay() equivalent)
receipt = await add.kiq(10, 20)
print(receipt.task_id)

# 3. Get Result (The .get() equivalent)
result = await receipt.wait_result(timeout=10)
print(result.return_value) # 30
```

---
## Starting Tasks: `kiq()` vs `kicker()`

### `.kiq()`
- The standard way to send a task with default settings.
- Equivalent to Celery's `.delay()`.
- **Note**: Always use `await` because sending to the broker is an async I/O operation.
```python
await my_task.kiq(arg1, arg2)
```

### `.kicker()`
- Used for advanced configuration (labels, timeouts, retries).
- Equivalent to Celery's `.apply_async()`.
- **Labels**: Used for routing to specific queues.
```python
# Sending to a specific queue with custom labels
await my_task.kicker().with_labels(queue="high_priority").kiq(arg1)
```

---
## **Taskiq Broker Initialization**

### Example (The "Classic Pro" Setup):
```python
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend
from taskiq_prometheus import PrometheusMiddleware

# 1. The Result Storage (Receipts)
result_backend = RedisAsyncResultBackend(
    redis_url="redis://redis:6379/1"
)

# 2. The Broker (Postman) with Middlewares
broker = AioPikaBroker(
    "amqp://guest:guest@rabbitmq:5672/"
).with_result_backend(result_backend).with_middlewares(
    PrometheusMiddleware(metrics_path="/metrics")
)

# Tasks are discovered automatically by pointing the CLI to this broker
```

### Broker Types:
- **AioPikaBroker**: RabbitMQ (Recommended for reliability/advanced routing).
- **RedisAsyncBroker**: Redis (Simpler, very fast).
- **InMemoryBroker**: For local testing/unit tests (no infrastructure needed).

---

## ✅ Best-Practice Code Example (Production Ready)

```python
import taskiq_fastapi
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend
from src.helpers.config import get_settings

settings = get_settings()

# Backend for results
result_backend = RedisAsyncResultBackend(redis_url=settings.CELERY_RESULT_BACKEND_URL)

# Broker for tasks
broker = AioPikaBroker(
    settings.CELERY_BROKER_URL
).with_result_backend(result_backend)

# FastAPI Integration (Pro Tip!)
taskiq_fastapi.init(broker, "src.main:app")

@broker.task(
    task_name="process_pdf",
    max_retry=3,
    retry_backoff=True,
)
async def process_pdf_task(file_path: str):
    # Heavy async logic here
    ...
```

---

## **Task Configuration & Safety**

### Task Name
- **Parameter**: `task_name`
- **Description**: Explicitly sets the task's unique ID.
- **Best Practice**: Use `module.function_name` to avoid collisions.

### Retries (Native & Simple)
- **`max_retry`**: Total number of retries if task fails.
- **`retry_backoff`**: Boolean or float for exponential backoff between retries.
- **Mental Model**: "If it fails, try again later but wait longer each time."

### Serialization
- Taskiq uses `pickle` by default for speed, but supports custom serializers (JSON/MsgPack).
- **Pro Tip**: Use JSON if you need to communicate with non-Python workers.

---

## **Worker Configuration & Scaling**

### Concurrency
- **Taskiq is Async**: Unlike Celery which needs 1 process per task, a **single Taskiq worker** can handle thousands of tasks concurrently using `asyncio`.
- **Command**: `taskiq worker path.to.broker:broker --workers 4` (This starts 4 OS processes, each handling many async tasks).

### Dependency Injection (The Superpower)
- **Feature**: `TaskiqDepends`
- **Usage**: Allows tasks to use the same database sessions or settings as your FastAPI routes.
```python
from taskiq import TaskiqDepends
from src.database import get_db

@broker.task
async def db_task(db = TaskiqDepends(get_db)):
    await db.execute(...)
```

---

## **Taskiq CLI Cheat Sheet**

| Command | Description |
| :--- | :--- |
| `taskiq worker module:broker` | Starts the worker |
| `--workers N` | Number of worker processes (forks) |
| `--reload` | Hot-reload for development |
| `taskiq-dashboard` | Starts the web UI (Flower equivalent) |

## **Result Handling**

| Methods / Attributes | Returns |
| :--- | :--- |
| `task.kiq()` | `TaskReceipt` |
| `receipt.task_id` | `str` (UUID) |
| `receipt.wait_result()` | `TaskiqResult` |
| `result.return_value` | The function's output |
| `result.is_err` | `bool` (True if failed) |
| `result.execution_time` | `float` (Seconds) |

---
*Generated with ❤️ by your AI Pair Programmer.*
