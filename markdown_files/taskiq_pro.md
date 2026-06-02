# 🛡️ Taskiq Pro: The Ultimate Production Guide (v0.12.4)

Welcome to the definitive guide for building resilient, high-performance asynchronous task systems with **Taskiq**. This guide focuses on production-grade patterns, reliability, and observability.

---

## 📦 0. Required Libraries (The Installation Guide)

To implement the professional patterns in this guide, you will need the following ecosystem libraries:

### **Core & Infrastructure**
```bash
pip install taskiq==0.12.4           # The core library
pip install taskiq-aio-pika          # RabbitMQ Broker (Async)
pip install taskiq-redis             # Redis Result Backend & Broker
```

### **Integrations**
```bash
pip install taskiq-fastapi           # FastAPI Dependency Injection support
pip install taskiq-prometheus        # Metrics for Grafana
pip install taskiq-dashboard         # Web UI for monitoring
```

### **Observability & Safety**
```bash
pip install taskiq-sentry            # Error tracking in background tasks
pip install taskiq-opentelemetry     # Distributed tracing
pip install taskiq-rate-limiter      # 🛡️ Global rate limiting
pip install taskiq-pipelines         # 🔗 Chaining tasks (A -> B -> C)
pip install taskiq-scheduler         # ⏰ Periodic/Cron tasks
pip install orjson                   # Ultra-fast JSON serialization
```

---

## 🔍 1. Library Deep-Dive: When & Where to use

### **1. `taskiq-aio-pika` (RabbitMQ Broker)**
- **Where**: Used in your broker configuration file (e.g., `src/tk_broker.py`).
- **Why**: RabbitMQ is the industry standard for message reliability. `aio-pika` is the async driver that ensures your FastAPI app never blocks while sending tasks.
- **Pro Tip**: Use it for mission-critical tasks like **Indexing** or **File Processing** where you cannot afford to lose a message.

### **2. `taskiq-redis` (Result Backend)**
- **Where**: Attached to the broker using `.with_result_backend()`.
- **Why**: Redis is ultra-fast for key-value lookups. It’s perfect for storing the "receipt" (result) of a task that the frontend needs to fetch later.
- **Pro Tip**: Use a separate Redis DB index (e.g., `db=1`) to avoid clashing with your app's main cache.

### **3. `taskiq-fastapi` (The Bridge)**
- **Where**: Inside your FastAPI startup logic (`main.py`).
- **Why**: It allows Taskiq workers to "see" your FastAPI app. This enables the use of `TaskiqDepends`, allowing background tasks to share the same Database sessions and Settings as your API routes.
- **Pro Tip**: Essential for RAG projects to ensure workers use the exact same DB and VectorDB configurations as the API.

### **4. `taskiq-prometheus` & `taskiq-dashboard`**
- **Where**: Prometheus is a middleware on the broker; Dashboard is a separate process.
- **Why**: Prometheus provides the raw data (RPM, latency, error rates) for your Grafana dashboards. The Dashboard provides a human-friendly "Flower-like" UI for quick debugging.
- **Pro Tip**: Always enable Prometheus in production to catch "silent" performance degradations.

### **5. `taskiq-sentry` & `taskiq-opentelemetry`**
- **Where**: Middlewares on the broker.
- **Why**: Sentry alerts you the moment a background task crashes. OpenTelemetry allows you to trace a single user request as it travels from the API into the background worker.
- **Pro Tip**: Use OpenTelemetry to debug "Slow RAG" issues—it will show you exactly if the delay is in retrieval, embedding, or generation.

### **6. `orjson` (The Speed Demon)**
- **Where**: Configured as the `serializer` for the broker.
- **Why**: `orjson` is significantly faster than Python's built-in `json` library. For high-volume tasks, this reduces CPU overhead and speeds up task dispatching.
- **Pro Tip**: Crucial when passing large metadata objects in your RAG pipeline.

---

## 🏗️ 2. Production Code Architecture

A clean architecture is the difference between a project that scales and one that becomes "spaghetti code." Here is the recommended layout for a Taskiq + FastAPI project.

### **The Folder Structure**
```text
src/
├── main.py              # FastAPI app initialization & Taskiq linking
├── tk_broker.py         # The "Source of Truth" for your Broker & Backend
├── tasks/               # Directory for all background tasks
│   ├── __init__.py      # Essential: imports the broker and all task files
│   ├── indexing.py      # Specific tasks for RAG indexing
│   └── maintenance.py   # Specific tasks for DB cleanup, etc.
└── routes/
    └── nlp.py           # API endpoints that trigger background tasks
```

### **The "Source of Truth" (`src/tk_broker.py`)**
Define your broker and result backend here. This file is imported by both the API and the Worker.
```python
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

# Define Result Backend
result_backend = RedisAsyncResultBackend(redis_url="redis://localhost:6379/1")

# Define Broker
broker = AioPikaBroker(
    "amqp://guest:guest@localhost:5672/"
).with_result_backend(result_backend)
```

### **The Integration Point (`src/main.py`)**
Link your FastAPI application to Taskiq. The `taskiq_fastapi.init` function automatically handles the broker's startup and shutdown.

```python
import taskiq_fastapi
from fastapi import FastAPI
from src.tk_broker import broker

# 1. Define the FastAPI app
app = FastAPI()

# 2. Initialize Taskiq
# Passing the 'app' instance directly is the safest approach
taskiq_fastapi.init(broker, app)
```

### **The Task Discovery (`src/tasks/__init__.py`)**
For the worker to "see" your tasks, they must be imported here.
```python
from src.tk_broker import broker
from src.tasks.indexing import index_project_task, process_file_task
from src.tasks.maintenance import cleanup_old_assets_task, optimize_qdrant_task

__all__ = ["broker", "index_project_task", "process_file_task", "cleanup_old_assets_task", "optimize_qdrant_task"]
```

### **Implementation Examples**

#### **1. The Indexing Task (`src/tasks/indexing.py`)**
This file handles the heavy lifting of the RAG pipeline. It orchestrates file processing, chunking, embedding, and vector storage.

```python
from src.tk_broker import broker
from src.controllers.NLPController import NLPController
from src.controllers.ProcessController import ProcessController
from src.database import get_utils
from taskiq import TaskiqDepends, TaskiqRetries
import logging

logger = logging.getLogger(__name__)

@broker.task(task_name="indexing.process_file", max_retry=3)
async def process_file_task(
    asset_id: int,
    project_id: int,
    db_utils = TaskiqDepends(get_utils)
):
    """
    Step 1: Process a raw file (PDF/Docx) into cleaned chunks.
    Uses ProcessController to handle the logic.
    """
    _, sessionmaker = db_utils
    processor = ProcessController(db_client=sessionmaker)
    
    try:
        # Perform heavy CPU-bound parsing
        chunks = await processor.process_asset_to_chunks(asset_id, project_id)
        
        # Trigger the next step in the pipeline: Indexing
        await index_project_task.kiq(project_id, chunks)
        
        return f"File {asset_id} processed into {len(chunks)} chunks"
    except Exception as e:
        logger.error(f"Failed to process file {asset_id}: {e}")
        raise TaskiqRetries()

@broker.task(task_name="indexing.index_project")
async def index_project_task(
    project_id: int,
    chunks: list,
    db_utils = TaskiqDepends(get_utils),
    # You can also inject specific LLM/VectorDB clients
    # vectordb = TaskiqDepends(get_vectordb),
    # llm = TaskiqDepends(get_llm)
):
    """
    Step 2: Take chunks, embed them, and store in Qdrant.
    """
    _, sessionmaker = db_utils
    nlp = NLPController(db_client=sessionmaker)
    
    # NLPController handles embedding and Qdrant insertion
    success = await nlp.index_into_vector_db(
        project_id=project_id,
        chunks=chunks,
        do_reset=False
    )
    
    if not success:
        raise Exception("Indexing failed")
        
    return f"Project {project_id} updated with new vectors"
```

#### **2. The Maintenance Task (`src/tasks/maintenance.py`)**
This file handles background house-keeping to keep the system lean and fast.

```python
from src.tk_broker import broker
from src.models.crud.AssetCrud import AssetCrud
from src.database import get_utils
from taskiq import TaskiqDepends
import logging

logger = logging.getLogger(__name__)

@broker.task(task_name="maintenance.cleanup_old_assets")
async def cleanup_old_assets_task(
    days_old: int = 30,
    db_utils = TaskiqDepends(get_utils)
):
    """
    Periodic cleanup of old assets and their temporary files.
    """
    _, sessionmaker = db_utils
    asset_crud = AssetCrud(db_client=sessionmaker)
    
    deleted_count = await asset_crud.delete_old_assets(days=days_old)
    logger.info(f"Cleanup complete: {deleted_count} assets removed.")
    
    return {"status": "success", "deleted": deleted_count}

@broker.task(task_name="maintenance.optimize_qdrant")
async def optimize_qdrant_task(
    project_id: int,
    # vectordb = TaskiqDepends(get_vectordb)
):
    """
    Trigger Qdrant collection optimization (compaction/indexing).
    Useful after large batch imports.
    """
    # Logic to call Qdrant's optimize endpoint
    # await vectordb.optimize_collection(f"collection_{project_id}")
    return "Optimization triggered"
```

### **The Execution Command**
When running the worker, always point it to the `__init__.py` or the specific broker file:
```bash
taskiq worker src.tasks:broker
```

---

## 🎯 3. Deep-Dive: The `@broker.task` Decorator

In production, never use `@broker.task` without parameters. Explicit configuration is the key to a stable system.

### **The "Pro" Parameter Breakdown**

```python
@broker.task(
    task_name="indexing.process_file", # 1. Explicit naming
    max_retry=5,                      # 2. Resilience
    retry_delay=10.0,                 # 3. Backoff (seconds)
    task_timeout=300,                 # 4. Safety (seconds)
    ack_on_error=False,               # 5. Reliability
    labels={"queue": "heavy_io"}      # 6. Routing
)
async def my_task():
    ...
```

#### **1. `task_name` (The ID Card)**
- **Why**: By default, Taskiq uses the function's path. If you move the file or rename the function, tasks already in RabbitMQ will crash because the worker can't find the "old" path.
- **Pro Tip**: Always use a fixed string like `domain.action`. This allows you to refactor your code without breaking the queue.

#### **2. `max_retry` & `retry_delay` (Resilience)**
- **Why**: Networks fail, and APIs time out. Retries give your task a second chance.
- **Pro Tip**: Use `retry_delay` for simple tasks. For complex backoff, use the `SimpleRetryMiddleware` on the broker level.

#### **3. `task_timeout` (The Deadman Switch)**
- **Why**: Prevents a task from hanging forever (e.g., an infinite loop or a stuck socket) and blocking a worker slot.
- **Pro Tip**: Set this slightly higher than your expected maximum execution time. For RAG indexing, 300-600 seconds is common.

#### **4. `ack_on_error` (Message Safety)**
- **Why**: If `True`, the message is removed from RabbitMQ even if the task crashes. If `False`, the message stays in the queue (or goes to a Dead Letter Exchange) so you can investigate.
- **Pro Tip**: Set to `False` for mission-critical data like financial transactions or primary indexing.

#### **5. `labels` (Traffic Control)**
- **Why**: Allows you to route tasks to specific workers. You might have a "fast" worker for notifications and a "heavy" worker with more RAM for PDF processing.
- **Pro Tip**: Use labels like `{"queue": "high_priority"}` and start your workers with specific filters.

---

## 🏛️ 4. Professional Infrastructure (The "A-Team" Stack)

In production, never use a single service for everything. Separate your concerns.

### **The Multi-Service Broker Setup**
```python
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend
from taskiq_prometheus import PrometheusMiddleware
from taskiq.middlewares.retry import SimpleRetryMiddleware

# 1. Result Backend (Redis) - Keep results on a dedicated DB (e.g., /1)
result_backend = RedisAsyncResultBackend(
    redis_url="redis://localhost:6379/1",
    keep_results=True,
    result_ex_time=3600, # 1 hour TTL
)

# 2. Broker (RabbitMQ) - The gold standard for delivery guarantees
broker = AioPikaBroker(
    "amqp://guest:guest@localhost:5672/"
).with_result_backend(result_backend).with_middlewares(
    # Order matters! Prometheus should be outside retries
    PrometheusMiddleware(metrics_path="/metrics"),
    SimpleRetryMiddleware(default_retry_count=3)
)
```

---

## 🔌 5. Seamless FastAPI Integration

Don't treat Taskiq as an external tool; treat it as an extension of your FastAPI app.

### **Sharing Dependencies & State**
Use `taskiq-fastapi` to share your database pools and settings.

```python
import taskiq_fastapi
from src.main import app
from src.tk_broker import broker

# This links your FastAPI app to the broker
taskiq_fastapi.init(broker, app)

@broker.task
async def process_cv(
    cv_id: int, 
    db = TaskiqDepends(get_db), # ✅ Reuses your FastAPI DI
    settings = TaskiqDepends(get_settings)
):
    # Logic...
```

---

## 🛠️ 6. Task Design Patterns (The "Senior" Way)

### **A. Idempotency (Critical!)**
A task might run twice due to network retries. Ensure it doesn't break your data.
- **Pattern**: `Check -> Act -> Update`
- **Example**: Check if `cv_id` is already indexed in Qdrant before running the heavy LLM logic.

### **B. Precise Retries**
Don't retry on user errors (400s). Only retry on infrastructure failures (500s/Timeouts).
```python
from taskiq import TaskiqRetries

@broker.task
async def call_llm_api(prompt: str):
    try:
        return await llm_client.generate(prompt)
    except (httpx.ConnectTimeout, httpx.ReadTimeout):
        # Only infrastructure issues trigger a retry
        raise TaskiqRetries()
```

---

## ⚡ 7. Advanced Taskiq Components (The "Lead Developer" Toolbox)

For complex RAG systems, simple background tasks aren't enough. You need orchestration, rate limiting, and scheduling.

### **A. `taskiq-pipelines`: Complex Orchestration**
Pipelines allow you to chain tasks together. This is perfect for the RAG flow: `Parse -> Chunk -> Embed -> Notify`.

```python
from taskiq import TaskiqPipeline
from src.tasks.indexing import process_file_task, index_project_task

async def trigger_full_indexing(asset_id: int, project_id: int):
    # Create a pipeline where the result of task A is passed to task B
    # A -> B -> C
    pipeline = (
        process_file_task.kiq(asset_id, project_id)
        .pipe(index_project_task, project_id=project_id)
    )
    await pipeline.kiq()
```

**Why this is professional:**
- **`process_file_task.kiq(...)`**: Initiates the first task. It takes its own arguments (`asset_id`, `project_id`) and returns a list of chunks.
- **`.pipe(index_project_task, ...)`**: This is the magic. It tells Taskiq: *"Wait for the first task to finish, then take its return value (the chunks) and pass it as the first argument to `index_project_task`."*
- **Decoupling**: Your tasks remain small and focused. `process_file_task` only knows how to parse; `index_project_task` only knows how to embed. The pipeline handles the handshake.
- **Reliability**: If the first task fails, the second one never starts, preventing "garbage in, garbage out" scenarios in your VectorDB.

### **B. `taskiq-rate-limiter`: API Protection**
LLM providers (DeepSeek, OpenAI) have strict RPM limits. Use the rate limiter to ensure your workers don't get banned.

```python
from taskiq_redis import RedisRateLimiter

# 1. Attach to broker
broker.with_middlewares(
    RedisRateLimiter(redis_url="redis://localhost:6379/2")
)

# 2. Apply to sensitive tasks
@broker.task(rate_limit="10/m") # Only 10 calls per minute
async def call_expensive_llm(prompt: str):
    return await llm.generate(prompt)
```

**Why this is professional:**
- **Global Enforcement**: Unlike local rate limiters that only track requests per-worker, `RedisRateLimiter` uses Redis as a "Single Source of Truth." This means if you have 10 workers across 5 servers, they all share the same counter.
- **Provider Protection**: Most LLM providers (DeepSeek, OpenAI) limit your account based on your **API Key**, not your user ID. This global limit ensures your entire system stays within your provider's RPM/TPM limits.
- **Client Agnostic**: This protects your infrastructure from a "thundering herd" of requests, regardless of whether they come from one malicious client or 100 legitimate ones.
- **Separation of Concerns**: Use FastAPI-level limiting to protect your API endpoints, and use Taskiq-level limiting to protect your external service dependencies and infrastructure.

### **C. `taskiq-scheduler`: The Cron Engine**
Use the scheduler for periodic system maintenance without needing a separate `crontab`.

```python
from taskiq.schedule_sources import LabelScheduleSource

# In your broker file
broker.with_schedule_source(LabelScheduleSource())

# In maintenance.py
@broker.task(schedule=[{"cron": "0 0 * * *"}]) # Run every midnight
async def midnight_cleanup():
    # Cleanup logic...
    pass
```
**Execution Command**:
```bash
taskiq scheduler src.tasks:broker
```

### **D. `taskiq-fastapi`: Deep Integration**
While `taskiq_fastapi.init` handles the broker's lifecycle, you might have other resources (like Database pools) that require a `lifespan` handler. Taskiq integrates seamlessly with custom lifespans.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
import taskiq_fastapi

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Your custom startup logic (e.g., DB pool)
    print("Database pool starting...")
    yield
    # Your custom shutdown logic
    print("Database pool shutting down...")

app = FastAPI(lifespan=lifespan)

# Simply call init; Taskiq will hook into your existing lifespan
# and add its own startup/shutdown logic automatically.
taskiq_fastapi.init(broker, app)
```

**Why this is professional:**
- **No Redundancy**: You don't need to call `broker.startup()` manually. `taskiq_fastapi.init` detects your lifespan and adds the broker's startup/shutdown logic to it.
- **Instance Passing**: Passing the `app` instance directly is the gold standard for avoiding circular imports and ensuring the worker and API are perfectly synced.

---

## 🚀 8. Worker Scaling & Concurrency

### **The Async Advantage**
Taskiq is async-native. A single worker process can handle **hundreds** of concurrent tasks.

- **I/O Bound (API/DB)**: Increase concurrency within the async loop.
- **CPU Bound (Processing)**: Use more OS processes.

**Command Line Deep-Dive:**
```bash
taskiq worker src.tasks:broker --workers 4 --max-async-tasks 100
```

This single command allows you to scale both horizontally (CPU) and vertically (I/O). Here is the breakdown:

1.  **`src.tasks:broker`**:
    - Tells Taskiq where to find the `broker` instance.
    - It follows the pattern `module_path:variable_name`.
2.  **`--workers 4` (Multiprocessing - CPU Scaling)**:
    - This spawns **4 separate OS processes**.
    - **Use Case**: Best for CPU-intensive tasks like PDF parsing, data cleaning, or heavy mathematical computations.
    - **Rule of Thumb**: Set this to the number of CPU cores available in your production environment.
3.  **`--max-async-tasks 100` (Async Concurrency - I/O Scaling)**:
    - Each of the 4 processes will handle up to **100 tasks concurrently** within its own event loop.
    - **Total Capacity**: This worker instance can handle **400 tasks** at the same time (4 workers * 100 async tasks).
    - **Use Case**: Perfect for I/O-bound tasks like calling LLM APIs (OpenAI/DeepSeek), querying Qdrant, or saving to PostgreSQL.
    - **Why it's better than Celery**: Celery would require 400 separate OS processes to do the same, consuming massive amounts of RAM. Taskiq does it with just 4 processes.

---

## 📈 9. Monitoring & Observability

### **The Three Pillars of Taskiq Monitoring**
1.  **Dashboard**: Use `taskiq-dashboard` for a real-time view of your queues.
2.  **Metrics**: Use `taskiq-prometheus` to feed data into Grafana.
3.  **Tracing**: Use `taskiq-opentelemetry` to trace a request from the FastAPI endpoint through the background worker.

### **Prometheus Metrics: What's Under the Hood?**
When you enable `PrometheusMiddleware(metrics_path="/metrics")`, Taskiq begins exposing raw telemetry data. This data is essential for building Grafana dashboards that show the health of your asynchronous pipeline.

Here is what the raw metrics look like and what they mean for your production environment:

#### **1. Task Throughput (`taskiq_tasks_processed_total`)**
This counter tracks how many tasks have completed.
- **Format**: `taskiq_tasks_processed_total{task_name="indexing.process_file", status="success"} 42`
- **Why it matters**: Use this to calculate **RPM (Requests Per Minute)**. If this drops to zero, your workers are idle or crashed.

#### **2. Execution Latency (`taskiq_tasks_execution_time_seconds`)**
A histogram that tracks the actual time your Python function took to run.
- **Format**: `taskiq_tasks_execution_time_seconds_bucket{task_name="indexing.index_project", le="10.0"} 5`
- **Why it matters**: Use this to detect **Slow RAG** issues. If the `95th percentile` (p95) latency increases, your LLM or VectorDB might be struggling.

#### **3. Queue Wait Time (`taskiq_tasks_waiting_time_seconds`)**
Tracks the time a task spent "sitting" in RabbitMQ before a worker picked it up.
- **Format**: `taskiq_tasks_waiting_time_seconds_bucket{le="1.0"} 150`
- **Why it matters**: This is the most critical metric for **Scaling**. If wait times are high, you need to add more workers (e.g., `taskiq worker ... --workers 8`).

#### **4. Failure Rates**
By filtering `taskiq_tasks_processed_total` with `status="failure"`, you can create "Error Rate" alerts.
- **Pro Tip**: Set up an alert if `(failures / total) > 0.05`.

---

## 💻 10. Local Development: Terminal Commands

If you are running Taskiq locally without Docker (similar to how you use Celery), use these direct terminal commands.

### **1. Running the Worker**
Instead of the long Celery command, Taskiq is much more concise and handles async natively.

| Feature | Celery Command | Taskiq Command |
| :--- | :--- | :--- |
| **Basic** | `python -m celery -A app worker` | `taskiq worker src.tasks:broker` |
| **Concurrency** | `--concurrency=2` | `--workers 2` |
| **Log Level** | `--loglevel=info` | (Default is info) |

**The "Power User" Local Command:**
```bash
taskiq worker src.tasks:broker --workers 2 --max-async-tasks 50
```

### **2. Running the Dashboard (Flower Equivalent)**
`taskiq-dashboard` is the lightweight, async-native equivalent to Celery Flower. It provides a real-time Web UI to monitor your tasks.

| Feature | Celery Flower Command | Taskiq Dashboard Command |
| :--- | :--- | :--- |
| **Command** | `python -m celery -A app flower` | `taskiq-dashboard src.tasks:broker` |
| **Port** | `--port=5555` | `--port 8000` |

**The "Power User" Dashboard Command:**
```bash
taskiq-dashboard src.tasks:broker --host 127.0.0.1 --port 8001
```

---

## 🐳 11. Containerizing Taskiq (The DevOps Way)

In a production environment, your Taskiq worker should run in a dedicated container. Here is how to configure it professionally.

### **The Worker Dockerfile**
Your worker uses the same code as your API but starts with a different command.
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for RAG (e.g., for PDF parsing)
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variables
ENV PYTHONPATH=/app

# Start the worker
# --workers 2: Number of processes
# --max-async-tasks 50: Concurrency per process
CMD ["taskiq", "worker", "src.tasks:broker", "--workers", "2"]
```

### **The `docker-compose.yml` Configuration**
Add these services to your existing `docker-compose.yml` to orchestrate the worker and monitoring dashboard.

```yaml
services:
  # The Background Worker
  taskiq-worker:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile
    container_name: taskiq_worker
    environment:
      - BROKER_URL=amqp://guest:guest@rabbitmq:5672/
      - REDIS_URL=redis://redis:6379/1
    depends_on:
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend
    restart: always

  # The Monitoring Dashboard (Flower-like UI)
  taskiq-dashboard:
    image: python:3.11-slim
    container_name: taskiq_dashboard
    command: ["taskiq-dashboard", "src.tasks:broker", "--host", "0.0.0.0", "--port", "8000"]
    ports:
      - "8001:8000"
    depends_on:
      - taskiq-worker
    networks:
      - backend
```

### **Connecting Prometheus (`prometheus.yml`)**
Since Prometheus uses a "Pull" model, you must tell it where to scrape the Taskiq metrics. Update your `docker/prometheus/prometheus.yml` with the following:

```yaml
scrape_configs:
  - job_name: 'taskiq-worker'
    scrape_interval: 5s
    static_configs:
      - targets: ['taskiq-worker:9000'] # Metrics port (exposed by PrometheusMiddleware)
    metrics_path: '/metrics'
```

> **Pro Tip**: Ensure your `taskiq-worker` service has port `9000` open in the internal network if you are using `PrometheusMiddleware`.

---

## 🛡️ 12. Production Checklist

- [ ] **Dedicated Queues**: Use labels to separate "Search" (Fast) from "Indexing" (Slow).
- [ ] **Timeouts**: Always set `task_time_limit` to prevent "zombie" tasks.
- [ ] **Serialization**: Use `ORJSON` or `MsgPack` for faster payload handling.
- [ ] **Logging**: Use a structured logger (like `structlog`) to include `task_id` in every log line.
- [ ] **Graceful Shutdown**: Ensure workers finish active tasks before stopping (Taskiq handles this by default with SIGTERM).

---

## 🧪 13. Testing Strategy

Never test your business logic by sending real tasks to RabbitMQ.

```python
from taskiq import InMemoryBroker

# Use this for your Unit Tests
test_broker = InMemoryBroker()

@test_broker.task
async def test_task():
    return "OK"

# In tests:
# await test_task.kiq() 
```

---
*Guide generated for Taskiq 0.12.4. Stay Async.*
