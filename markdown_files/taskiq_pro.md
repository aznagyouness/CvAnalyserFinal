# 🛡️ Taskiq Pro: The Ultimate Production Guide (v0.12.4)

Welcome to the definitive guide for building resilient, high-performance asynchronous task systems with **Taskiq**. This guide focuses on production-grade patterns, reliability, and observability.

---

## 📦 0. Required Libraries (The Installation Guide)

To implement the professional patterns in this guide, you will need the following ecosystem libraries:

### 🎯 The Rule

| Type | Syntax | Example |
|------|--------|---------|
| **Taskiq extras** (bundled) | `taskiq[extra]` | `taskiq[metrics,orjson]` |
| **Taskiq plugins** (separate) | `package-name` | `taskiq-dashboard` |
| **Taskiq brokers** (separate) | `package-name` | `taskiq-aio-pika` |

**Bottom line**: Only `metrics`, `orjson`, `uv`, `all`, `reload`, and `zmq` go inside the brackets. Everything else is a separate `pip install`.


### **Core & Infrastructure**
```bash
pip install taskiq==0.12.4  # The core library ⏰ Periodic/Cron tasks also supported
pip install taskiq[metrics,orjson,uv]==0.12.4  # built-in Prometheus support  # Ultra-fast JSON serialization
pip install taskiq-aio-pika==0.6.0          # RabbitMQ Broker (Async)
pip install taskiq-redis==1.2.2             # Redis Result Backend
```

### **Integrations**
```bash
pip install taskiq-fastapi==0.5.0           # FastAPI Dependency Injection support
pip install taskiq-dashboard==0.4.4        # Web UI for monitoring
```

### **Observability & Safety**
```bash

pip install taskiq-pipelines==0.1.4         # 🔗 Chaining tasks (A -> B -> C)
pip install sentry-sdk[fastapi]==2.19.2      # Sentry Error Tracking
# ==> you need to Create Sentry account (free tier: 5k events/month) and get the DSN --> then create functions to capture errors
# ==> Not good & it could be replaced with what you already have PostgreSQL, Prometheus, and Grafana, you don't need to pay for Sentry. 
```

| Feature | Benefit of sentry-sdk|
|---------|---------|
| **Error tracking** | Know immediately when tasks fail |
| **Full traceback** | See exactly where code broke |
| **Request context** | Know which user/file caused the error |
| **Performance monitoring** | Identify slow tasks/endpoints |
| **Alerting** | Get notified via Slack/email/SMS |
| **Release tracking** | Know which deployment introduced the bug |
| **User impact** | See how many users are affected |
| **Trending** | Track error frequency over time |

                   


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

### **4. `metrics` & `taskiq-dashboard`**
- **Where**: Metrics (Prometheus support) is a middleware on the broker; Dashboard is a separate process.
- **Why**: `metrics` provides the raw data (RPM, latency, error rates) for your Grafana dashboards. The Dashboard provides a human-friendly "Flower-like" UI for quick debugging.
- **Pro Tip**: Always enable metrics in production to catch "silent" performance degradations.

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
from taskiq import SimpleRetryMiddleware
from taskiq.middlewares.prometheus import PrometheusMiddleware  # Correct import from taskiq core extra!
from pathlib import Path  # ✅ IMPORTANT: Need Path for metrics_path!

# Create a writable metrics directory inside your project!
METRICS_DIR = Path(__file__).parent.parent / "data" / "taskiq_metrics"
METRICS_DIR.mkdir(parents=True, exist_ok=True)  # Auto-creates if missing!

# Define Result Backend
result_backend = RedisAsyncResultBackend(
    redis_url="redis://localhost:6379/1",
    keep_results=True,
    result_ex_time=3600,
)

# Define Broker
broker = AioPikaBroker(
    "amqp://guest:guest@localhost:5672/",
    #dead_letter_queue_name="my_app.dlq",          # 👈 No need to put it Taskiq automatically creates a dead-letter queue (DLQ) for you. It will generate one using the default naming pattern: {queue_name}.dead_letter
).with_result_backend(result_backend).with_middlewares(
    # 🏆 THE MASTER ORDER:
    # Prometheus MUST be the first (outermost) layer.
    PrometheusMiddleware(
        server_addr="0.0.0.0",    # Host to listen on
        server_port=9000,         # Port for metrics server (HTTP endpoint: http://localhost:9000)
        metrics_path=METRICS_DIR  # ✅ This is a DIRECTORY PATH (on disk), NOT an HTTP path!
    ), 
    SimpleRetryMiddleware(default_retry_count=3)
)
# the task definition : 
# in src/tasks/indexing.py
@broker.task(
    task_name="indexing.process_file", # 1. Explicit naming (survives code refactoring)
    max_retries=5,                     # 2. Resilience (must be plural in 0.12.4)
    delay=10.0,                        # 3. Backoff in seconds (official param is 'delay')
    task_timeout=300,                  # 4. Safety limit (must use 'task_timeout')
    ack_on_error=False,                # 5. Reliability (keeps message in queue on failure)
    retry_on_error=True,               # 6. REQUIRED: Activates the retry middleware engine
    labels={"queue": "heavy_io"}       # 7. Routing (use 'labels')
)
async def my_task():
    ...

```

---

### 💡 Simplifying PrometheusMiddleware (Using Defaults)

Okay! That's a fantastic idea! Let's check what the **default parameters are for PrometheusMiddleware**!

Yes! That's exactly right! If you just use `PrometheusMiddleware()` (no parameters), it will use the **defaults**, which should fix all our problems!

Let's confirm the defaults by looking at Taskiq's source code:
```python
# Default parameters for PrometheusMiddleware
def __init__(
    self,
    server_addr: str = "0.0.0.0",
    server_port: int = 9000,
    metrics_path: Path = Path("metrics"),  # Default is "metrics" directory in current working dir
):
    # ... code ...
```

#### What Happens If We Just Use `PrometheusMiddleware()`?
1. **Defaults**:
   - `server_addr="0.0.0.0"` (same as before)
   - `server_port=9000` (same as before)
   - `metrics_path=Path("metrics")` (default: creates a `metrics` directory in your current working directory)
2. **HTTP Endpoint**:
   - The HTTP endpoint still starts on `http://localhost:9000` when you run the worker!
3. **Directory**:
   - It creates a `metrics` folder in your **current working directory** (the folder you run the command from)

#### But Wait: What If We Don't Want Prometheus At All?
Alternatively, if you don't need Prometheus metrics right now, you can **just remove the middleware entirely** and only keep `SimpleRetryMiddleware(default_retry_count=3)`! That would also fix all errors!

#### So Yes, You're 100% Correct!
If you just use `PrometheusMiddleware()` (with no arguments):
- You don't need to define `METRICS_DIR`
- You don't need to call `mkdir()`
- The HTTP endpoint still works when you start the worker!
- It just uses the default `metrics` directory in your CWD!

And like I said, if you don't need metrics right now, you can even **remove the `PrometheusMiddleware` entirely** and just keep the `SimpleRetryMiddleware`! 😊

---

#### **3.1. Result Backend**
- **What it does: Stores task results (return values, exceptions, state) so you can inspect them later.**
- **/1 database:**: Isolates result storage from other Redis data (e.g., cache, sessions). Prevents accidental key collisions..
- **keep_results=True**: Task results are saved even after completion.
- **result_ex_time=3600**: Results expire after 1 hour. Automatically cleans up old data.
- **Pro Tip**: Always set a TTL. Without it, Redis becomes a memory bomb.

#### **3.2. Broker**
- **Why RabbitMQ over Redis or In‑memory?** : RabbitMQ gives you durable queues, acknowledgements, and dead‑letter exchanges – crucial for “at‑least‑once” delivery guarantees.
- **Why Prometheus FIRST**: It must measure everything, including the retry attempts and any delays.
- **dead_letter_queue_name="my_app.dlq"**: tells Taskiq (and RabbitMQ) to create a special queue called my_app.dlq where messages are sent after all retry attempts have failed (e.g., after max_retries=5 is exhausted).
- **why ? dead_letter_queue_name="my_app.dlq"**: Prevents infinite loops – Without a DLQ, a failing task with ack_on_error=False keeps getting re‑queued forever, clogging the system.- Saves failed messages for inspection – Instead of deleting or losing the task, it's parked safely so you can debug later.- Protects the main queue – Poison messages are moved out, allowing healthy tasks to process without blocking. - Enables manual recovery – You can examine, fix, and replay failed messages from the DLQ.

#### **3.3. Middlewares**
- **default_retry_count**: The default number of retries for a task before it is marked as failed.

#### **3.4. Task Definition**
- **What it does**: Defines the behavior of a background task.
- **Where**: In your task files (`src/tasks/`).
- **Why**: Each task is a separate function, and you can define its behavior (like retries, timeouts, etc.).
- **task_name="indexing.process_file"**: Explicit naming is critical for monitoring. Without it, Taskiq generates a name from the function – refactoring breaks dashboards & logs. Here, you decouple the logical name from the function name.
- **max_retries=5, delay=10.0**: Set the task to retry up to 5 times with a delay of 10 seconds between each attempt Overrides the middleware’s default (3 retries). This specific task is more fragile (file indexing), so you give it more attempts. retry_delay=10.0 – waits 10 seconds between retries, not instant.
- **timeout=300**: Hard timeout (5 minutes). If the task runs longer, Taskiq cancels it. Protects against “zombie” tasks that hang forever (e.g., stuck I/O, deadlocks)..
- **ack_on_error=False – The Unsung Hero**: Default behaviour (ack_on_error=True): If a task raises an exception, the broker acknowledges (removes) the message from the queue. The task is lost forever. ack_on_error=False (recommended for critical tasks): On failure, the message stays in the queue and can be retried or moved to a dead‑letter exchange. This guarantees at‑least‑once processing. You must pair it with a retry middleware, otherwise you’ll get infinite loops.
- **queue_name="heavy_io"**:  it tells the worker pool to route this task to a specific queue (e.g., “heavy_io” queue). You can start different worker groups listening to different queues – resource isolation.- One group of workers runs CPU‑bound tasks.- Another group runs I/O‑bound tasks.
- **retry_on_error=True**: 	Mandatory. Without this, the retry middleware ignores the task entirely.

this blueprint, adjust the numbers to your SLA, and you will out‑engineer 90% of distributed task setups.

---

## 📊 3. Prometheus Metrics Deep Dive

The metrics are exposed by a built-in web server that the middleware starts automatically. Here's exactly where to find them and what they track.

### 🔎 Where to Find the Metrics
The PrometheusMiddleware starts a lightweight HTTP server that exposes your metrics at the **root of the server address/port** (e.g., `http://localhost:9000`). By default, it uses the following configuration:
- **Host address**: `0.0.0.0`
- **Port**: `9000`
- **HTTP Endpoint**: `http://<server_addr>:<server_port>` (e.g., `http://localhost:9000`)

To access the raw metrics, you can navigate to `http://localhost:9000` in your browser or use curl:
```bash
curl http://localhost:9000
```
If you need to customize the server's address or port, you can specify them when initializing the PrometheusMiddleware:
```python
PrometheusMiddleware(
    server_addr="0.0.0.0",   # Host to listen on
    server_port=9000,        # Port for metrics server
    metrics_path=METRICS_DIR # 🚨 THIS IS A DIRECTORY PATH ON DISK, NOT AN HTTP PATH! 🚨
)
```
**Important**:
- The `metrics_path` parameter is a **directory path where metrics are temporarily saved on disk**, NOT the HTTP path!
- The metrics server is only started in worker processes. When you run a worker with `taskiq worker`, it will start the server automatically. However, if you start a broker in a non‑worker context (for example, a FastAPI app sending tasks), the server will not be started, and the endpoint will not be available.

### 📊 What the Metrics Mean
The middleware tracks five key metrics. Each metric includes a `task_name` label to distinguish between different task functions.

| Metric Name | Type | What It Tracks | PromQL Example |
|-------------|------|----------------|----------------|
| `found_errors` | Counter | Total number of tasks that failed with an exception. | `rate(found_errors[5m])` |
| `received_tasks` | Counter | Total number of tasks received by the broker. | `rate(received_tasks[5m])` |
| `success_tasks` | Counter | Total number of tasks that executed without errors. | `rate(success_tasks[5m])` |
| `saved_results` | Counter | Total number of results successfully saved to the result backend (e.g., Redis). | `rate(saved_results[5m])` |
| `execution_time` | Histogram | Duration of task execution (in seconds). This can be used to track percentiles (p50, p95, p99). | `histogram_quantile(0.95, sum(rate(execution_time_bucket[5m])) by (le, task_name))` |

**Note**: `saved_results` may be lower than `success_tasks` if writing to the result backend fails (for example, when Redis is unavailable).

---

![alt text](image-1.png)

#### **3.5. ack_on_error=True (Default – Not for critical tasks) or ack_on_error=False (Recommended for critical tasks)**
##### **a- ack_on_error=True**
- **What it does**: If a task raises an exception, the broker acknowledges (removes) the message from the queue. The task is lost forever.
- **Why**: This is the default behavior. It's suitable for non-critical tasks where losing a task is acceptable.
![alt text](image-2.png)

##### **b- ack_on_error=False + Retry Middleware + Dead‑Letter Queue (Correct for critical tasks)**
- **What it does**: If a task raises an exception, the broker does not acknowledge the message. The task is put back in the queue for retry.
- **Why**: This is suitable for critical tasks where losing a task is not acceptable. Dead‑Letter Queue ensures that failed tasks are not lost forever. You can inspect them later and take corrective actions. the inspection will be found in the dead‑letter queue. you can start the queue again with a function that you define.


![alt text](deepseek_mermaid_20260609_d00371.png)

##### **c- Side‑by‑side comparison (visual table)**
![alt text](deepseek_mermaid_20260609_2ff9b3.png)




##### **d- Key takeaway as a simple decision flow**
![alt text](deepseek_mermaid_20260609_da854d.png)

**Rule of thumb**: Ask yourself – If this task fails and the message disappears forever, will a human being complain or money be lost? If yes → critical. If no → non-critical.
![alt text](image-3.png)
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
from taskiq import TaskiqDepends
import logging

logger = logging.getLogger(__name__)

@broker.task(
    task_name="indexing.process_file", 
    max_retries=3,     # ✅ Plural as per docs
    delay=10.0,       # ✅ Delay label
    retry_on_error=True,
    task_timeout=300, # ✅ Core timeout param
    labels={"queue": "heavy_io"} # ✅ Routing label
)
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
        # Just raise the error - SimpleRetryMiddleware will handle the retry
        raise e

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
    task_name="indexing.process_file", # 1. Explicit naming (survives code refactoring)
    max_retries=5,                     # 2. Resilience (must be plural in 0.12.4)
    delay=10.0,                        # 3. Backoff in seconds (official param is 'delay')
    timeout=300,                       # 4. Safety limit (official param is 'timeout')
    ack_on_error=False,                # 5. Reliability (keeps message in queue on failure)
    retry_on_error=True,               # 6. REQUIRED: Activates the retry middleware engine
    queue_name="heavy_io"              # 7. Routing (use queue_name, not labels dict)
)
async def my_task():
    ...
```

#### **1. `task_name` (The ID Card)**
- **Why**: By default, Taskiq uses the function's path. If you move the file or rename the function, tasks already in RabbitMQ will crash because the worker can't find the "old" path.
- **Pro Tip**: Always use a fixed string like `domain.action`. This allows you to refactor your code without breaking the queue.

#### **2. `max_retries` & `delay` (Resilience)**
- **Why**: Networks fail, and APIs time out. Retries give your task a second chance.
- **Pro Tip**: Use `delay` for simple tasks. For complex backoff, use the `SimpleRetryMiddleware` on the broker level.

#### **3. `timeout` (The Deadman Switch)**
- **Why**: Prevents a task from hanging forever (e.g., an infinite loop or a stuck socket) and blocking a worker slot.
- **Pro Tip**: Set this slightly higher than your expected maximum execution time. For RAG indexing, 300-600 seconds is common.

#### **4. `ack_on_error` (Message Safety)**
- **Why**: If `True`, the message is removed from RabbitMQ even if the task crashes. If `False`, the message stays in the queue (or goes to a Dead Letter Exchange) so you can investigate.
- **Pro Tip**: Set to `False` for mission-critical data like financial transactions or primary indexing.

#### **5. `queue_name` (Traffic Control)**
- **Why**: Allows you to route tasks to specific workers. You might have a "fast" worker for notifications and a "heavy" worker with more RAM for PDF processing.
- **Pro Tip**: Use queue names like `"high_priority"` and start your workers with specific filters.

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
    # 🏆 THE MASTER ORDER:
    # Prometheus MUST be the first (outermost) layer.
    PrometheusMiddleware(metrics_path="/metrics"), 
    SimpleRetryMiddleware(default_retry_count=3)
)
```

---

## 🎓 The Middleware Onion: Why Order Matters (A Masterclass)

As a world-class developer, I don't just write code; I design **Systems of Truth**. When configuring Taskiq middlewares, the order isn't a "suggestion"—it's the difference between **Observability** and **Delusion**.

### **Why Order is Non-Negotiable: The Execution Stack**

Middlewares in Taskiq work like an **Onion**. When a task runs, it travels from the **outside in** to reach your function, and then from the **inside out** to return the result.

#### **1. Prometheus at the Outer Layer (The Source of Truth)**
If Prometheus is first in the list, it wraps *everything* else. 
- **The Call**: Prometheus starts its timer ⏱️ → Then it hands the task to the Retry middleware.
- **The Crash**: If the task fails, the Retry middleware catches it and re-runs it 3 times.
- **The Return**: Finally, when the task succeeds (or permanently fails), the flow returns to Prometheus.
- **The Result**: Prometheus records the **Total Latency** and the **True Success/Failure**. Your Grafana dashboard shows you exactly how long the user waited and if the system ultimately delivered.

#### **2. Prometheus at the Inner Layer (The "Metrics Liar" Trap)**
If you put `SimpleRetryMiddleware` first, Prometheus is trapped *inside* the retry loop.
- **The Disaster**: For every single retry attempt, Prometheus starts and stops a *new* timer.
- **The Lie**: If a task fails 2 times and succeeds on the 3rd, your dashboard will show **3 separate successful-looking tasks** with very short durations. 
- **The Consequence**: You will look at your metrics and say, "Everything is fast and healthy!" while in reality, your system is struggling, retrying constantly, and your true latency is 3x higher than what you see.

### **The World-Class Verdict**
- **Prometheus Outside**: Captures the **User Experience** (Total time, Final result).
- **Retry Inside**: Captures the **Infrastructure Resilience** (Fixing transient errors).

**Always put your monitoring at the gates.** If you don't measure the struggle, you aren't managing the system; you're just hoping it works. 🥂

---

### **Pro Infrastructure: The Redis Mansion Pattern**

Imagine you live in a beautiful 16-room mansion (this is your **Redis instance**). Each room has a number from **0 to 15**. These are called **Logical Databases**.

If you try to put your bed, your kitchen, and your office all in **Room 0**, you have a mess. If you drop a plate, you might break your computer. In tech, we call this a **Key Collision**.

By assigning different indices (`/0`, `/1`, `/2`), we give each of your "workers" their own private room. 

```python
# In your Global Quota Manager 
quota_redis_url = "redis://localhost:6379/0" 

# In your Taskiq Result Backend 
result_backend = RedisAsyncResultBackend(redis_url="redis://localhost:6379/1") 

# In your Taskiq Rate Limiter Middleware 
rate_limiter = RedisRateLimiter(redis_url="redis://localhost:6379/2")
```

Here is why this is the "Best Teacher" choice for your production system:

#### **1. Room 0: The Global Quota Manager (The "Brain")**
*   **Purpose**: This room holds your **Hybrid Strategy** counters (`quota:llm_global:...`).
*   **Why here?**: This is the most sensitive data. By putting it in DB 0, we ensure that no other library (like Taskiq) accidentally deletes or overwrites your RPM counters. It is your "VIP Suite."

#### **2. Room 1: Taskiq Result Backend (The "Archive")**
*   **Purpose**: This room stores the results of your background tasks (e.g., "Task #123 finished successfully").
*   **Why here?**: Taskiq generates *thousands* of keys for results. If we put these in the same room as your Quota Manager, your Redis would look like a cluttered warehouse. By separating them, we keep your Quota Manager fast and responsive.

#### **3. Room 2: Taskiq Rate Limiter (The "Traffic Control")**
*   **Purpose**: This room is used by Taskiq's internal middleware to manage its own background task limits.
*   **Why here?**: Taskiq's rate limiter works differently than our "Final Boss" Hybrid strategy. By putting it in DB 2, we prevent Taskiq's internal logic from "tripping over" our custom global logic.

---

#### **The "Master Class" Benefits:**

*   **The "Flush" Safety**: Imagine you want to clear all your old Taskiq results to save memory. You can run the command `FLUSHDB` while inside **DB 1**. 
    - **Result**: All your old results are gone (Clean!), but your **Global Quota Manager in DB 0 is untouched**. If they were in the same room, you would accidentally reset your RPM limits and potentially get your API Key banned!
*   **Debugging Clarity**: When you use a tool like *Redis Insight*, you can switch between "Room 0", "Room 1", and "Room 2". You will see exactly what is happening in each part of your system without being overwhelmed by "noise."
*   **Zero Infrastructure Cost**: You are still only running **one** Redis server. You aren't paying for more RAM or more CPU. You are simply using the "Logical Rooms" that Redis already built for you.

---

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

## 🔌 5. The "Handshake": FastAPI Endpoint to Taskiq Task

### **1. The "Handshake" Mechanism**
The journey of a request follows this path:
- **The Producer (FastAPI)**: Receives the HTTP request and uses the `.kiq()` method to "kick" the task into the broker.
- **The Broker (RabbitMQ)**: Acts as the secure bridge, holding the task message in a queue.
- **The Consumer (Taskiq Worker)**: A separate process that picks up the message, deserializes the arguments, and executes the heavy logic.

### **2. Why This Matters for Production**
- **Non-Blocking Performance**: Your API can return a `202 Accepted` response in milliseconds, regardless of whether the worker is processing a 1-page resume or a 500-page document. Your API response time is independent of how long the task takes. Whether the PDF is 1 page or 1,000 pages, the API response is always ~10ms.
- **Infrastructure Decoupling**: The API doesn't need to know *how* to process the data; it only needs to know *how* to delegate the work. The API doesn't need to know *how* to parse a PDF. It only needs to know *how* to ask the worker to do it.

### **The Producer Side (FastAPI Route)**
In your [data.py](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/routes/data.py), we don't call the function directly. We use the `.kiq()` method.

```python
from src.tasks.indexing import process_file_task

@data_router.post("/process/{project_id}")
async def process_data(project_id: int):
    # 1. FastAPI receives the HTTP request.
    # 2. We "kick" (kiq) the task into the broker.
    await process_file_task.kiq(project_id=project_id, file_name="resume.pdf")
    
    # 3. FastAPI immediately returns a 202 Accepted.
    return JSONResponse(content={"message": "Task queued!"})
```

### **The "Behind the Scenes" Handshake**
1.  **Serialization**: FastAPI takes your arguments (`project_id=400`) and converts them into a JSON message.
2.  **Enveloping**: Taskiq wraps this JSON in a "Task Envelope" that contains the task name (`indexing.process_file`) and metadata.
3.  **Dispatch**: The message is sent to **RabbitMQ**.
4.  **Pick-up**: A **Taskiq Worker** sitting on a different server (or container) sees the message in RabbitMQ.
5.  **Execution**: The worker deserializes the message, finds the function marked with `@broker.task(task_name="indexing.process_file")`, and runs it.

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
