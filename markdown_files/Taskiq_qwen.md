### USER
use the following guide link https://github.com/taskiq-python/taskiq/tree/9f8db96bf52947939651b4a8f0b2fdc663c6ca33/docs/guide and act like a senior devlopper and give my ultimate guide 

### ASSISTANT
# 🚀 The Ultimate Senior Developer's Guide to Taskiq

> *A battle-tested, production-ready guide to Python's most modern async distributed task queue*

---

## 📋 Table of Contents

1. [Why Taskiq? The Senior Dev Perspective](#1-why-taskiq-the-senior-dev-perspective)
2. [Architecture Deep Dive](#2-architecture-deep-dive)
3. [Getting Started — From Zero to Hero](#3-getting-started--from-zero-to-hero)
4. [Brokers & Result Backends — Production Choices](#4-brokers--result-backends--production-choices)
5. [Task Definition Patterns & Best Practices](#5-task-definition-patterns--best-practices)
6. [Dependency Injection — The FastAPI Way](#6-dependency-injection--the-fastapi-way)
7. [State Management & Lifecycle Events](#7-state-management--lifecycle-events)
8. [Scheduling Tasks — Cron, Intervals & Dynamic](#8-scheduling-tasks--cron-intervals--dynamic)
9. [Middlewares — The Power Layer](#9-middlewares--the-power-layer)
10. [CLI Mastery & Worker Management](#10-cli-mastery--worker-management)
11. [Testing Strategies That Actually Work](#11-testing-strategies-that-actually-work)
12. [Production Deployment & Scaling](#12-production-deployment--scaling)
13. [Advanced Patterns & Gotchas](#13-advanced-patterns--gotchas)
14. [The Senior Dev's Checklist](#14-the-senior-devs-checklist)

---

## 1. Why Taskiq? The Senior Dev Perspective

Let me be direct: **If you're building an async Python application in 2026, Taskiq should be your default choice for distributed task processing.** Here's why I've moved away from Celery and Dramatiq for async-first projects:

### The Problem with Legacy Solutions

Most Python task queues were built for synchronous code. When you try to use them with `asyncio`, you end up with:
- Thread-pool hacks that defeat the purpose of async
- Poor type safety and IDE support
- Complex configuration that's hard to debug
- No native dependency injection

### Taskiq's Core Advantages

| Feature | Why It Matters |
|---------|----------------|
| **Native Async** | Built from the ground up for `asyncio` — no thread-pool wrappers |
| **Type Safety** | Full PEP 612 support means your IDE actually helps you |
| **Modular Architecture** | Swap brokers, result backends, and serializers independently |
| **Dependency Injection** | FastAPI-style DI for tasks — testable and composable |
| **Active Development** | Unlike Arq or AioTasks, Taskiq is actively maintained (as of 2026) |
| **Multiple Brokers** | RabbitMQ, NATS, Redis, ZeroMQ, Kafka — pick your poison |

### When NOT to Use Taskiq

- **Pure synchronous projects**: Stick with Celery or Dramatiq
- **Simple cron jobs**: A basic `asyncio` loop might be enough
- **Single-server setups**: If you don't need distribution, you're over-engineering

---

## 2. Architecture Deep Dive

Before writing a single line of code, you need to understand Taskiq's architecture. This isn't just academic — it directly affects how you debug, scale, and maintain your system.

### The Component Model

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT SIDE                              │
│                                                                  │
│   Your Code ──► Kicker ──► Broker ──► External Queue            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         WORKER SIDE                              │
│                                                                  │
│   External Queue ──► Broker ──► Task Execution                  │
│                              │                                   │
│                              ▼                                   │
│                       Result Backend                             │
│                              │                                   │
│                              ▼                                   │
│                       Your Code (reads result)                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components Explained

#### **Broker** — The Message Router
The broker is the heart of Taskiq. It must implement `AsyncBroker` with two critical methods:
- `kick()`: Sends a message to the external queue (e.g., Redis `PUB`, RabbitMQ `basic_publish`)
- `listen()`: Infinite loop that receives messages and spawns task execution

**Senior Tip**: The broker is stateless by design. You can run multiple workers against the same broker, and they'll load-balance automatically.

#### **Kicker** — The Message Builder
When you call `task.kiq()`, Taskiq creates a Kicker instance. This is what allows you to:
- Override the broker at call-time
- Add dynamic labels
- Change the task_id
- Chain operations fluently

```python
# These are equivalent:
await my_task.kiq(1, 2, 3)
await my_task.kicker().kiq(1, 2, 3)

# But the kicker gives you power:
await my_task.kicker() \
    .with_broker(other_broker) \
    .with_labels(priority="high", retry=3) \
    .with_task_id("custom-id-123") \
    .kiq(1, 2, 3)
```

#### **Result Backend** — The State Store
Stores `TaskiqResult` objects. By default, brokers use `DummyResultBackend` (which does nothing). **In production, you MUST configure a real result backend** or you'll lose task results.

#### **Workers** — The Executors
Workers are separate processes started via CLI. They:
1. Connect to the broker
2. Listen for messages
3. Execute tasks
4. Store results in the result backend

**Critical Insight**: Workers run in separate processes from your main application. This means:
- They have their own event loop
- They don't share memory with your web app
- They need their own database connections, caches, etc.

---

## 3. Getting Started — From Zero to Hero

### Installation

```bash
# Core library
pip install taskiq

# Production-ready stack (recommended)
pip install taskiq taskiq-aio-pika taskiq-redis

# Or with NATS instead of RabbitMQ
pip install taskiq taskiq-nats taskiq-redis
```

### Step 1: Define Your Broker

Create a `broker.py` file. This is your single source of truth for task routing.

```python
# broker.py
from taskiq import InMemoryBroker

# For local development — no external dependencies
broker = InMemoryBroker()
```

**⚠️ Critical Warning**: `InMemoryBroker` is for development only. It doesn't send data over the network, and tasks only execute in the same process.

### Step 2: Define Your First Task

```python
# tasks.py
import asyncio
from broker import broker

@broker.task
async def process_order(order_id: int) -> dict:
    """Process an order asynchronously."""
    await asyncio.sleep(2)  # Simulate heavy work
    return {"order_id": order_id, "status": "processed"}
```

### Step 3: Execute the Task

```python
# main.py
import asyncio
from broker import broker
from tasks import process_order

async def main():
    # REQUIRED: Startup the broker before use
    await broker.startup()
    
    try:
        # Send task to the queue
        task = await process_order.kiq(42)
        
        # Wait for result (with timeout)
        result = await task.wait_result(timeout=10.0)
        
        print(f"Status: {result.status}")
        print(f"Result: {result.return_value}")
        print(f"Error: {result.error}")
        print(f"Execution time: {result.execution_time}s")
    finally:
        await broker.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 4: Distributed Execution (Production Setup)

Now let's make it real with RabbitMQ and Redis:

```python
# broker.py
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

broker = AioPikaBroker(
    "amqp://guest:guest@localhost:5672",
).with_result_backend(
    RedisAsyncResultBackend("redis://localhost:6379")
)
```

**Start the infrastructure:**

```bash
# RabbitMQ
docker run --rm -d \
  --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  rabbitmq:3.13-management-alpine

# Redis
docker run --rm -d \
  --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

**Start the worker:**

```bash
taskiq worker broker:broker
```

**Run your application:**

```bash
python main.py
```

You'll see the worker pick up the task and execute it. The result is stored in Redis and retrieved by your main application.

---

## 4. Brokers & Result Backends — Production Choices

This is where most teams make mistakes. Let me break down the options with real-world trade-offs.

### Broker Comparison

| Broker | Use Case | Pros | Cons |
|--------|----------|------|------|
| **AioPika (RabbitMQ)** | General purpose, complex routing | Mature, reliable, rich routing | Heavier resource usage |
| **NATS** | High throughput, low latency | Blazing fast, simple | Less feature-rich than RabbitMQ |
| **Redis** | Simple queues, caching | Fast, ubiquitous | Not designed as a message broker |
| **ZeroMQ** | In-process or simple IPC | No broker needed | No persistence, limited features |

**My Recommendation**: 
- **Default choice**: `taskiq-aio-pika` — it's the most battle-tested
- **High throughput**: `taskiq-nats` — if you need millions of messages/second
- **Simple setups**: `taskiq-redis` — if you already have Redis and don't need advanced routing

### Result Backend Comparison

| Backend | Use Case | Pros | Cons |
|---------|----------|------|------|
| **Redis** | General purpose | Fast, supports TTL | Memory-bound |
| **PostgreSQL** | Durable storage | ACID, queryable | Slower than Redis |
| **S3/MinIO** | Large results | Cheap, scalable | Slow for small results |

**Production Pattern**: Use Redis for results with a TTL (e.g., 24 hours). If you need long-term storage, implement a middleware that archives results to S3 or PostgreSQL.

### Configuration Example

```python
# broker.py
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

broker = AioPikaBroker(
    url="amqp://user:pass@rabbitmq:5672/vhost",
    # RabbitMQ-specific options
    max_priority=10,  # Enable priority queues
).with_result_backend(
    RedisAsyncResultBackend(
        redis_url="redis://:password@redis:6379/0",
        # Keep results for 24 hours
        expiry=86400,
    )
)
```

---

## 5. Task Definition Patterns & Best Practices

### the complete reference table for the `@broker.task(...)` decorator parameters, based on the Taskiq guide:

| Parameter | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| **`task_name`** | `str \| None` | Overrides the default task name (which is the fully qualified function path). Useful for stable naming across code refactors. | `task_name="process_payment"` |
| **`timeout`** | `float \| int \| None` | Maximum execution time in seconds. Raises `TimeoutError` and cancels the task if exceeded. | `timeout=30.0` |
| **`cron`** | `str \| None` | Standard cron expression for static scheduling (requires `LabelScheduleSource` and a running scheduler). | `cron="0 2 * * *"` *(Daily at 2 AM)* |
| **`cron_offset`** | `str \| timedelta \| None` | Timezone string or UTC offset for the `cron` schedule. Defaults to UTC. | `cron_offset="America/New_York"` |
| **`time`** | `datetime.time \| None` | Runs the task at a specific time of day, every day. | `time=datetime.time(14, 30)` |
| **`interval`** | `timedelta \| None` | Runs the task repeatedly at a fixed time interval. | `interval=timedelta(minutes=15)` |
| **`labels`** | `dict \| None` | Arbitrary metadata attached to every execution. Read by middlewares for routing, metrics, or custom logic. | `labels={"priority": "high"}` |

### 💡 Quick Reminder: What DOES NOT go here?
To avoid confusion, remember that **execution policies** like retries, dynamic queue routing, and custom task IDs are **not** defined in this decorator. They are handled dynamically:
*   **Retries:** Handled globally via `SimpleRetryMiddleware` or custom middlewares.
*   **Dynamic Routing/IDs:** Handled at call-time using the Kicker: 
    ```python
    await my_task.kicker().with_labels(queue="fast").with_task_id("abc").kiq()
    ```
### Basic Task Definition

```python
@broker.task
async def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email asynchronously."""
    # Your email logic here
    return True
```

### Task Labels — The Hidden Power

Labels are metadata attached to tasks. They're not just for decoration — they control behavior.

```python
# Set labels via decorator
@broker.task(
    timeout=30,           # Task timeout in seconds
    retry_on_error=True,  # Auto-retry on failure
    max_retries=3,        # Maximum retry attempts
    priority=5,           # Queue priority (if broker supports it)
    custom_label="value"  # Your own metadata
)
async def my_task():
    pass

# Or set labels dynamically at call time
await my_task.kicker().with_labels(
    timeout=60,
    user_id=12345,
    trace_id="abc-123"
).kiq()
```

**Senior Tip**: Use labels for distributed tracing. Add a `trace_id` label to every task, and you can correlate logs across your entire system.

### Custom Task Names

By default, Taskiq uses the fully qualified function name. But you can override this:

```python
@broker.task(task_name="orders.process_payment")
async def process_payment(order_id: int):
    pass
```

**Why do this?**
- Stable names across refactors
- Better routing in some brokers
- Clearer task identification in monitoring

### Automatic Type Casting

Taskiq automatically casts incoming parameters to match your type hints:

```python
@broker.task
async def process_user(user_id: int, is_active: bool) -> None:
    # Even if called with strings, they'll be cast correctly
    pass

# This works:
await process_user.kiq("123", "true")  # Casts to int and bool
```

**Disable if needed**: Pass `--no-parse` to the worker CLI.

### Timeouts — Critical for Production

```python
# Via decorator
@broker.task(timeout=30)
async def slow_task():
    await asyncio.sleep(60)  # Will raise TimeoutError

# Via kicker
await slow_task.kicker().with_labels(timeout=5).kiq()
```

**⚠️ Important**: Timeouts use `asyncio.wait_for()`. For sync functions, the timeout raises `TimeoutError`, but the underlying thread may continue executing. This is a Python limitation — design your sync tasks to be interruptible.

---

## 6. Dependency Injection — The FastAPI Way

This is one of Taskiq's killer features. If you've used FastAPI, you'll feel right at home.

### Basic Dependencies

```python
from taskiq import TaskiqDepends, Context
from typing import Annotated  # Python 3.10+

# Simple function dependency
def get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@broker.task
async def create_user(
    name: str,
    db: Annotated[Session, TaskiqDepends(get_db_session)]
):
    db.add(User(name=name))
    db.commit()
```

### Context Access

The `Context` object gives you access to the current execution environment:

```python
@broker.task
async def my_task(context: Annotated[Context, TaskiqDepends()]):
    # Access the broker
    broker = context.broker
    
    # Access the current message
    message = context.message
    task_id = message.task_id
    
    # Access state
    redis_pool = context.state.redis
    
    # Control flow
    if some_condition:
        await context.requeue()  # Put back in queue
    if another_condition:
        await context.reject()   # Drop the message
```

### Class-Based Dependencies

```python
class UserService:
    def __init__(self, db: Session = TaskiqDepends(get_db_session)):
        self.db = db
    
    async def create_user(self, name: str):
        # Implementation
        pass

@broker.task
async def create_user_task(
    name: str,
    service: Annotated[UserService, TaskiqDepends()]
):
    await service.create_user(name)
```

### Generator Dependencies (Setup/Teardown)

Perfect for transactions, connections, and resources:

```python
async def get_transaction():
    async with db.begin():
        yield db
        # If task succeeds, transaction commits
        # If task fails, transaction rolls back

@broker.task
async def transfer_money(
    from_id: int,
    to_id: int,
    amount: float,
    db: Annotated[Session, TaskiqDepends(get_transaction)]
):
    # All operations happen in a single transaction
    await db.execute(debit(from_id, amount))
    await db.execute(credit(to_id, amount))
```

**⚠️ Exception Handling**: By default, exceptions propagate to generator dependencies (allowing rollback). Disable with `--no-propagate-errors` if you want different behavior.

### Generic Dependencies

```python
from typing import TypeVar, Generic

T = TypeVar('T')

class Repository(Generic[T]):
    def __init__(self, model: type[T]):
        self.model = model
    
    async def get(self, id: int) -> T:
        # Implementation
        pass

class UserRepository(Repository[User]):
    def __init__(self):
        super().__init__(User)

@broker.task
async def get_user_task(
    user_id: int,
    repo: Annotated[UserRepository, TaskiqDepends()]
):
    return await repo.get(user_id)
```

---

## 7. State Management & Lifecycle Events

### TaskiqState — Global Shared State

`TaskiqState` is a global object that persists across task executions within a worker process. Perfect for connection pools, caches, and expensive-to-create resources.

```python
from taskiq import TaskiqState, TaskiqEvents

@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def setup_state(state: TaskiqState):
    """Initialize resources when worker starts."""
    state.redis = await aioredis.from_url("redis://localhost")
    state.http_client = httpx.AsyncClient()
    state.db_pool = await create_db_pool()

@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def cleanup_state(state: TaskiqState):
    """Clean up resources when worker shuts down."""
    await state.redis.close()
    await state.http_client.aclose()
    await state.db_pool.dispose()
```

### Event Types

| Event | When It Fires | Use Case |
|-------|---------------|----------|
| `WORKER_STARTUP` | Worker process starts | Initialize pools, connections |
| `WORKER_SHUTDOWN` | Worker process stops | Clean up resources |
| `CLIENT_STARTUP` | `broker.startup()` called | Client-side initialization |
| `CLIENT_SHUTDOWN` | `broker.shutdown()` called | Client-side cleanup |

**Critical Distinction**: 
- **Worker events** fire in the worker process (when running `taskiq worker`)
- **Client events** fire in your application process (when calling `broker.startup()`)

### Accessing State in Tasks

```python
@broker.task
async def my_task(context: Annotated[Context, TaskiqDepends()]):
    redis = context.state.redis
    await redis.set("key", "value")
```

**Senior Tip**: Use state for resources that are expensive to create but safe to share across tasks. Don't use it for request-specific data — that's what task arguments are for.

---

## 8. Scheduling Tasks — Cron, Intervals & Dynamic

### Basic Scheduling

```python
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

# Define your scheduler
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)

# Schedule a task with cron
@broker.task(cron="*/5 * * * *")  # Every 5 minutes
async def cleanup_old_records():
    # Cleanup logic
    pass

# Schedule with interval
@broker.task(interval=timedelta(hours=1))
async def sync_external_data():
    # Sync logic
    pass

# Schedule with specific time
@broker.task(time=datetime.time(14, 0))  # Every day at 2 PM
async def generate_daily_report():
    # Report generation
    pass
```

### Running the Scheduler

```bash
taskiq scheduler broker:scheduler
```

**⚠️ Critical**: Run **only one** scheduler instance. Multiple schedulers will cause duplicate task execution.

### Timezone Handling

```python
from datetime import datetime
import pytz

# Cron with timezone offset
@broker.task(cron="0 9 * * *", cron_offset="America/New_York")
async def morning_task():
    # Runs at 9 AM Eastern Time
    pass

# Time with timezone
@broker.task(time=datetime.time(14, 0, tzinfo=pytz.UTC))
async def utc_task():
    pass
```

### Dynamic Scheduling (Runtime)

For tasks that need to be scheduled at runtime (e.g., "send reminder in 30 minutes"):

```python
from taskiq_redis import ListRedisScheduleSource

# Create a dynamic schedule source
redis_source = ListRedisScheduleSource(
    redis_url="redis://localhost:6379",
    queue_name="dynamic_schedules"
)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker), redis_source],
)

# Schedule a task dynamically
schedule = await my_task.schedule_by_time(
    redis_source,
    datetime.now(UTC) + timedelta(minutes=30),
    arg1="value1",
    arg2="value2"
)

# Cancel the schedule
await schedule.unschedule()

# Or manually
await redis_source.delete_schedule(schedule.schedule_id)
```

### Multiple Schedule Sources

```python
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        LabelScheduleSource(broker),      # Static schedules
        redis_source,                      # Dynamic schedules
        DatabaseScheduleSource(db),        # DB-driven schedules
    ],
    # Custom merge function to handle conflicts
    merge_function=only_unique,  # or preserve_all
)
```

### Skipping First Run

By default, the scheduler executes overdue tasks immediately on startup. To prevent this:

```bash
taskiq scheduler broker:scheduler --skip-first-run
```

---

## 9. Middlewares — The Power Layer

Middlewares let you intercept and modify tasks at every stage of their lifecycle. This is where you implement cross-cutting concerns: logging, metrics, retries, rate limiting, etc.

### Middleware Lifecycle

```
Client Side:
  1. pre_send(message)     → Before sending to broker
  2. post_send(message)    → After sending to broker

Worker Side:
  3. pre_execute(message)  → Before task execution
  4. [Task executes]
  5. on_error(message, error) → If task raises exception
  6. post_execute(message) → After task execution
  7. post_save(message, result) → After result is saved
```

### Writing a Custom Middleware

```python
from taskiq.abc.middleware import TaskiqMiddleware
from taskiq.message import TaskiqMessage
from taskiq.result import TaskiqResult
import time
import logging

logger = logging.getLogger(__name__)

class MetricsMiddleware(TaskiqMiddleware):
    """Track task execution metrics."""
    
    async def pre_send(self, message: TaskiqMessage) -> TaskiqMessage:
        message.labels["sent_at"] = time.time()
        logger.info(f"Task {message.task_name} queued")
        return message
    
    def post_send(self, message: TaskiqMessage) -> None:
        logger.info(f"Task {message.task_id} sent to broker")
    
    async def pre_execute(self, message: TaskiqMessage) -> None:
        message.labels["started_at"] = time.time()
        logger.info(f"Task {message.task_name} started")
    
    def on_error(self, message: TaskiqMessage, error: Exception) -> None:
        logger.error(f"Task {message.task_name} failed: {error}")
        # Increment error counter in your metrics system
    
    def post_execute(self, message: TaskiqMessage, result: TaskiqResult) -> None:
        started_at = message.labels.get("started_at", 0)
        duration = time.time() - started_at
        logger.info(f"Task {message.task_name} completed in {duration:.2f}s")
        # Record duration in your metrics system
```

### Registering Middlewares

```python
broker = AioPikaBroker("amqp://localhost")
broker.add_middleware(MetricsMiddleware())
broker.add_middleware(RetryMiddleware())
broker.add_middleware(RateLimitMiddleware())
```

### Built-in Middlewares

Taskiq comes with some useful middlewares:

```python
from taskiq.middlewares import (
    SimpleRetryMiddleware,      # Basic retry logic
    EventRetryMiddleware,       # Retry based on events
)

broker.add_middleware(SimpleRetryMiddleware(
    default_retry_count=3,
    default_delay=1.0,
))
```

### Advanced Middleware Patterns

**Circuit Breaker**:

```python
class CircuitBreakerMiddleware(TaskiqMiddleware):
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failures = {}
        self.threshold = failure_threshold
        self.timeout = recovery_timeout
    
    async def pre_execute(self, message: TaskiqMessage) -> None:
        task_name = message.task_name
        if task_name in self.failures:
            failures, last_failure_time = self.failures[task_name]
            if failures >= self.threshold:
                if time.time() - last_failure_time < self.timeout:
                    raise CircuitBreakerOpen(f"Circuit breaker open for {task_name}")
                else:
                    # Reset after timeout
                    del self.failures[task_name]
    
    def on_error(self, message: TaskiqMessage, error: Exception) -> None:
        task_name = message.task_name
        failures = self.failures.get(task_name, (0, 0))[0]
        self.failures[task_name] = (failures + 1, time.time())
```

**Rate Limiting**:

```python
from aiolimiter import AsyncLimiter

class RateLimitMiddleware(TaskiqMiddleware):
    def __init__(self, rate: float, per: float):
        self.limiter = AsyncLimiter(rate, per)
    
    async def pre_execute(self, message: TaskiqMessage) -> None:
        await self.limiter.acquire()
```

---

## 10. CLI Mastery & Worker Management

The Taskiq CLI is your primary tool for managing workers and schedulers. Let's master it.

### Starting Workers

```bash
# Basic usage
taskiq worker broker:broker

# With task auto-discovery
taskiq worker broker:broker -fsd  # Finds all **/tasks.py files

# Custom task pattern
taskiq worker broker:broker -tp "**/async_tasks.py"

# Specify app directory
taskiq worker broker:broker --app-dir /path/to/app
```

### Performance Tuning

```bash
# Number of worker processes (default: 2)
taskiq worker broker:broker --workers 4

# For CPU-bound sync tasks, use process pool
taskiq worker broker:broker --use-process-pool --max-process-pool-processes 8

# For IO-bound sync tasks, increase thread pool
taskiq worker broker:broker --max-threadpool-threads 32

# Limit concurrent async tasks
taskiq worker broker:broker --max-async-tasks 100

# Add jitter to prevent thundering herd
taskiq worker broker:broker --max-async-tasks 100 --max-async-tasks-jitter 20
```

### Acknowledgement Strategies

This is critical for reliability:

```bash
# Acknowledge when received (fastest, least safe)
taskiq worker broker:broker --ack-type when_received

# Acknowledge when executed (balanced)
taskiq worker broker:broker --ack-type when_executed

# Acknowledge when result saved (default, safest)
taskiq worker broker:broker --ack-type when_saved
```

**My Recommendation**: Use `when_saved` for critical tasks, `when_executed` for high-throughput non-critical tasks. Never use `when_received` unless you can afford to lose tasks.

### Hot Reload (Development)

```bash
# Install reload support
pip install "taskiq[reload]"

# Start with hot reload
taskiq worker broker:broker --reload

# Watch specific directories
taskiq worker broker:broker --reload --reload-dir ./tasks --reload-dir ./utils

# Respect .gitignore
taskiq worker broker:broker --reload  # Uses .gitignore by default
taskiq worker broker:broker --reload --do-not-use-gitignore  # Ignore .gitignore
```

### Graceful Shutdown & Reload

```bash
# Graceful shutdown (wait for tasks to complete)
kill -SIGINT <worker_pid>
# or
kill -SIGTERM <worker_pid>

# Graceful reload (Unix only) — zero downtime
kill -HUP <worker_pid>

# Force shutdown (send signal multiple times)
kill -SIGINT <worker_pid>  # First signal: graceful
kill -SIGINT <worker_pid>  # Second signal: graceful
kill -SIGINT <worker_pid>  # Third signal: force kill

# Or configure the threshold
taskiq worker broker:broker --hardkill-count 2
```

### Timeouts & Limits

```bash
# Wait timeout for tasks during shutdown
taskiq worker broker:broker --wait-tasks-timeout 30

# Restart worker after N tasks (prevent memory leaks)
taskiq worker broker:broker --max-tasks-per-child 1000

# Restart after N failures
taskiq worker broker:broker --max-fails 10

# Shutdown timeout for broker cleanup
taskiq worker broker:broker --shutdown-timeout 10
```

### Prefetching

```bash
# Prefetch tasks for better throughput
taskiq worker broker:broker --max-prefetch 10
```

**⚠️ Warning**: Prefetching only works with brokers that support acknowledgements. If a worker crashes with prefetched tasks, those tasks may be lost or duplicated.

### Logging

```bash
# Set log level
taskiq worker broker:broker --log-level DEBUG

# Custom log format
taskiq worker broker:broker --log-format "%(levelname)s: %(message)s"

# Disable default logging (use your own)
taskiq worker broker:broker --no-configure-logging
```

### Scheduler CLI

```bash
# Basic scheduler
taskiq scheduler broker:scheduler

# Skip first run
taskiq scheduler broker:scheduler --skip-first-run

# Custom update interval (default: 1 second)
taskiq scheduler broker:scheduler --update-interval 5

# Auto-discover tasks
taskiq scheduler broker:scheduler -fsd
```

---

## 11. Testing Strategies That Actually Work

Testing distributed tasks is tricky. Here's how to do it right.

### Environment-Based Broker Swapping

```python
# broker.py
import os
from taskiq import AsyncBroker, InMemoryBroker

if os.getenv("ENVIRONMENT") == "pytest":
    # Use in-memory broker for tests
    broker = InMemoryBroker()
else:
    # Use production broker
    from taskiq_aio_pika import AioPikaBroker
    from taskiq_redis import RedisAsyncResultBackend
    
    broker = AioPikaBroker("amqp://localhost").with_result_backend(
        RedisAsyncResultBackend("redis://localhost")
    )
```

### Testing Tasks as Regular Functions

```python
# test_tasks.py
import pytest
from tasks import parse_int

@pytest.mark.anyio
async def test_parse_int():
    # Call task directly — no broker involved
    result = await parse_int("42")
    assert result == 42
```

### Testing Task Execution (With Broker)

```python
@pytest.mark.anyio
async def test_parse_int_with_broker():
    from tasks import parse_int
    
    # Send task through broker
    task = await parse_int.kiq("42")
    result = await task.wait_result()
    
    assert result.return_value == 42
    assert result.status == "success"
```

### Handling Unawaited Tasks

When tasks are fire-and-forget, use `InMemoryBroker` features:

**Option 1: Auto-await**

```python
# In test setup
broker = InMemoryBroker(await_inplace=True)

# Now all .kiq() calls are automatically awaited
async def my_function():
    await parse_int.kiq("42")  # Actually executes immediately
    return "done"
```

**Option 2: Manual wait**

```python
@pytest.mark.anyio
async def test_fire_and_forget():
    from tasks import parse_int
    from broker import broker
    
    await my_function()  # Fires task but doesn't wait
    await broker.wait_all()  # Wait for all tasks to complete
    
    # Now assert side effects
```

### Testing with Dependencies

```python
from pathlib import Path
from taskiq import TaskiqDepends

@broker.task
async def modify_path(some_path: Path = TaskiqDepends()):
    return some_path.parent / "taskiq.py"

# Test the function directly
@pytest.mark.anyio
async def test_modify_path_direct():
    result = await modify_path(Path("/home/user"))
    assert str(result).endswith("taskiq.py")

# Test with dependency injection
@pytest.fixture(autouse=True)
async def setup_dependencies():
    # Inject test dependencies
    broker.add_dependency_context({Path: Path("/test/path")})
    yield
    # Clean up
    broker.custom_dependency_context = {}

@pytest.mark.anyio
async def test_modify_path_with_di():
    task = await modify_path.kiq()
    result = await task.wait_result()
    assert str(result.return_value).endswith("taskiq.py")
```

### Testing Middlewares

```python
class TestMiddleware(TaskiqMiddleware):
    def __init__(self):
        self.pre_send_called = False
        self.post_execute_called = False
    
    async def pre_send(self, message):
        self.pre_send_called = True
        return message
    
    def post_execute(self, message, result):
        self.post_execute_called = True

@pytest.mark.anyio
async def test_middleware():
    middleware = TestMiddleware()
    test_broker = InMemoryBroker()
    test_broker.add_middleware(middleware)
    
    @test_broker.task
    async def test_task():
        return 42
    
    task = await test_task.kiq()
    await task.wait_result()
    
    assert middleware.pre_send_called
    assert middleware.post_execute_called
```

---

## 12. Production Deployment & Scaling

### Docker Deployment

**Dockerfile**:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Default command (override in docker-compose)
CMD ["taskiq", "worker", "broker:broker", "--workers", "4"]
```

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  worker:
    build: .
    command: >
      taskiq worker broker:broker
      --workers 4
      --max-async-tasks 100
      --ack-type when_saved
      --log-level INFO
    depends_on:
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - REDIS_URL=redis://redis:6379
    deploy:
      replicas: 3  # Scale horizontally
    restart: unless-stopped

  scheduler:
    build: .
    command: >
      taskiq scheduler broker:scheduler
      --skip-first-run
      --log-level INFO
    depends_on:
      rabbitmq:
        condition: service_healthy
    environment:
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    deploy:
      replicas: 1  # NEVER scale scheduler > 1
    restart: unless-stopped
```

### Kubernetes Deployment

**worker-deployment.yaml**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: taskiq-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: taskiq-worker
  template:
    metadata:
      labels:
        app: taskiq-worker
    spec:
      containers:
      - name: worker
        image: your-registry/taskiq-worker:latest
        command:
        - taskiq
        - worker
        - broker:broker
        - --workers
        - "4"
        - --max-async-tasks
        - "100"
        - --ack-type
        - when_saved
        env:
        - name: RABBITMQ_URL
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"
          initialDelaySeconds: 5
          periodSeconds: 10
```

**scheduler-deployment.yaml**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: taskiq-scheduler
spec:
  replicas: 1  # CRITICAL: Only 1 replica!
  selector:
    matchLabels:
      app: taskiq-scheduler
  template:
    metadata:
      labels:
        app: taskiq-scheduler
    spec:
      containers:
      - name: scheduler
        image: your-registry/taskiq-scheduler:latest
        command:
        - taskiq
        - scheduler
        - broker:scheduler
        - --skip-first-run
        env:
        - name: RABBITMQ_URL
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: taskiq-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: taskiq-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: rabbitmq_queue_messages  # Custom metric
      target:
        type: AverageValue
        averageValue: "100"  # Scale when queue depth > 100
```

### Monitoring & Observability

**Prometheus Metrics Middleware**:

```python
from prometheus_client import Counter, Histogram, Gauge
import time

class PrometheusMiddleware(TaskiqMiddleware):
    def __init__(self):
        self.task_total = Counter(
            'taskiq_tasks_total',
            'Total number of tasks',
            ['task_name', 'status']
        )
        self.task_duration = Histogram(
            'taskiq_task_duration_seconds',
            'Task execution duration',
            ['task_name']
        )
        self.active_tasks = Gauge(
            'taskiq_active_tasks',
            'Number of currently executing tasks',
            ['task_name']
        )
    
    async def pre_execute(self, message: TaskiqMessage) -> None:
        self.active_tasks.labels(task_name=message.task_name).inc()
        message.labels['_start_time'] = time.time()
    
    def post_execute(self, message: TaskiqMessage, result: TaskiqResult) -> None:
        task_name = message.task_name
        self.active_tasks.labels(task_name=task_name).dec()
        
        start_time = message.labels.get('_start_time', 0)
        duration = time.time() - start_time
        self.task_duration.labels(task_name=task_name).observe(duration)
        
        status = 'success' if result.status == 'success' else 'failure'
        self.task_total.labels(task_name=task_name, status=status).inc()
    
    def on_error(self, message: TaskiqMessage, error: Exception) -> None:
        self.task_total.labels(
            task_name=message.task_name,
            status='error'
        ).inc()
```

### Production Checklist

Before going to production, verify:

- [ ] **Broker**: Using production broker (AioPika/NATS), not InMemoryBroker
- [ ] **Result Backend**: Configured with appropriate TTL
- [ ] **Acknowledgements**: Using `when_saved` for critical tasks
- [ ] **Timeouts**: All tasks have appropriate timeouts
- [ ] **Retries**: Retry middleware configured with exponential backoff
- [ ] **Logging**: Structured logging with correlation IDs
- [ ] **Metrics**: Prometheus/StatsD middleware enabled
- [ ] **Health Checks**: Liveness and readiness probes configured
- [ ] **Resource Limits**: CPU/memory limits set in Kubernetes
- [ ] **Scheduler**: Only 1 instance running
- [ ] **Graceful Shutdown**: `--wait-tasks-timeout` configured
- [ ] **Secrets**: Credentials in environment variables or secret manager
- [ ] **Monitoring**: Alerts for queue depth, error rates, latency

---

## 13. Advanced Patterns & Gotchas

### Dynamic Brokers & Tasks

For advanced use cases where you need to create brokers or tasks at runtime:

```python
from taskiq import AsyncBroker

async def dynamic_task_execution():
    # Create broker dynamically
    broker = AioPikaBroker("amqp://localhost")
    await broker.startup()
    
    # Define task dynamically
    async def my_dynamic_task(x: int):
        return x * 2
    
    # Register task
    registered_task = broker.register_task(my_dynamic_task)
    
    # Execute
    result = await registered_task.kiq(5)
    
    await broker.shutdown()
```

**⚠️ Warning**: Dynamically registered tasks won't be discovered by `taskiq worker`. You need to implement a custom receiver or run the worker in the same process.

### Custom Serializers

```python
from taskiq.serializers import TaskiqSerializer
import orjson

class CustomSerializer(TaskiqSerializer):
    def dumpb(self, message: dict) -> bytes:
        return orjson.dumps(message)
    
    def loadb(self, data: bytes) -> dict:
        return orjson.loads(data)

# Use custom serializer
broker = AioPikaBroker("amqp://localhost").with_serializer(
    CustomSerializer()
)
```

**Built-in Options**:
- `ORJSONSerializer` — Fast JSON with datetime/UUID support
- `MSGPackSerializer` — Compact binary format
- `CBORSerializer` — Another compact binary format

```bash
pip install "taskiq[orjson]"  # or msgpack, cbor
```

### Custom Formatters

For interoperability with other systems (e.g., sending tasks to Celery workers):

```python
from taskiq.abc.formatter import TaskiqFormatter
from taskiq.message import TaskiqMessage

class CeleryCompatibleFormatter(TaskiqFormatter):
    def dumps(self, message: TaskiqMessage) -> bytes:
        # Convert to Celery's message format
        celery_msg = {
            "task": message.task_name,
            "args": message.args,
            "kwargs": message.kwargs,
            "id": message.task_id,
        }
        return json.dumps(celery_msg).encode()
    
    def loads(self, data: bytes) -> TaskiqMessage:
        # Parse Celery format
        celery_msg = json.loads(data.decode())
        return TaskiqMessage(
            task_id=celery_msg["id"],
            task_name=celery_msg["task"],
            args=celery_msg.get("args", []),
            kwargs=celery_msg.get("kwargs", {}),
            labels={},
        )
```

### Task Pipelines

Chain tasks together:

```bash
pip install taskiq-pipelines
```

```python
from taskiq_pipelines import Pipeline

@broker.task
async def step1(x: int) -> int:
    return x + 1

@broker.task
async def step2(x: int) -> int:
    return x * 2

@broker.task
async def step3(x: int) -> int:
    return x - 3

# Execute pipeline: ((5 + 1) * 2) - 3 = 9
pipeline = Pipeline(broker)
task = await pipeline.chain([step1, step2, step3]).kiq(5)
result = await task.wait_result()
print(result.return_value)  # 9
```

### Error Handling Strategies

**Retry with Exponential Backoff**:

```python
from taskiq.middlewares import EventRetryMiddleware

class SmartRetryMiddleware(TaskiqMiddleware):
    def on_error(self, message: TaskiqMessage, error: Exception) -> None:
        retries = int(message.labels.get("retry_count", 0))
        max_retries = int(message.labels.get("max_retries", 3))
        
        if retries < max_retries:
            # Exponential backoff: 1s, 2s, 4s, 8s...
            delay = 2 ** retries
            message.labels["retry_count"] = retries + 1
            message.labels["retry_delay"] = delay
            
            # Re-queue with delay
            # Implementation depends on broker capabilities
```

**Dead Letter Queue**:

```python
class DeadLetterMiddleware(TaskiqMiddleware):
    def __init__(self, dead_letter_queue: str):
        self.dead_letter_queue = dead_letter_queue
    
    def on_error(self, message: TaskiqMessage, error: Exception) -> None:
        retries = int(message.labels.get("retry_count", 0))
        max_retries = int(message.labels.get("max_retries", 3))
        
        if retries >= max_retries:
            # Send to dead letter queue
            # Implementation depends on broker
            logging.error(
                f"Task {message.task_name} failed after {max_retries} retries. "
                f"Moving to dead letter queue."
            )
```

### Idempotency Patterns

For tasks that must be safe to execute multiple times:

```python
@broker.task
async def process_payment(
    order_id: int,
    amount: float,
    idempotency_key: str
):
    # Check if already processed
    cache_key = f"payment:{idempotency_key}"
    if await redis.get(cache_key):
        logging.info(f"Payment {idempotency_key} already processed")
        return {"status": "already_processed"}
    
    # Process payment
    result = await payment_gateway.charge(order_id, amount)
    
    # Mark as processed (with TTL)
    await redis.set(cache_key, "processed", ex=86400)
    
    return result

# Usage
await process_payment.kiq(
    order_id=123,
    amount=99.99,
    idempotency_key="unique-key-abc-123"
)
```

### Common Gotchas

**1. Forgetting `broker.startup()`**

```python
# ❌ WRONG
await my_task.kiq(1, 2, 3)  # May fail or behave unexpectedly

# ✅ CORRECT
await broker.startup()
await my_task.kiq(1, 2, 3)
```

**2. Not awaiting task results**

```python
# ❌ WRONG - Fire and forget without waiting
await my_task.kiq(1, 2, 3)

# ✅ CORRECT - Wait for result
task = await my_task.kiq(1, 2, 3)
result = await task.wait_result()
```

**3. Sharing state between client and worker**

```python
# ❌ WRONG - This won't work
shared_data = {}

@broker.task
async def my_task():
    shared_data["key"] = "value"  # Worker's memory, not client's

# ✅ CORRECT - Use result backend or external storage
@broker.task
async def my_task():
    await redis.set("key", "value")
```

**4. Running multiple schedulers**

```bash
# ❌ WRONG - Multiple schedulers = duplicate tasks
taskiq scheduler broker:scheduler  # Instance 1
taskiq scheduler broker:scheduler  # Instance 2

# ✅ CORRECT - Only one scheduler
taskiq scheduler broker:scheduler  # Single instance
```

**5. Not handling worker shutdown**

```python
# ❌ WRONG - Tasks may be interrupted
@broker.task
async def long_running_task():
    for i in range(1000000):
        process(i)  # No checkpoint, can't be interrupted safely

# ✅ CORRECT - Check for shutdown signals
@broker.task
async def long_running_task(context: Context = TaskiqDepends()):
    for i in range(1000000):
        if await should_shutdown():  # Check shutdown signal
            await context.requeue()  # Re-queue for later
            return
        process(i)
```

---

## 14. The Senior Dev's Checklist

### Architecture Decisions

- [ ] **Broker Selection**: Chosen based on throughput, reliability, and feature needs
- [ ] **Result Backend**: Configured with appropriate TTL and storage backend
- [ ] **Serialization**: Selected based on performance vs. compatibility needs
- [ ] **Task Granularity**: Tasks are atomic, idempotent, and < 5 minutes execution time
- [ ] **Error Handling**: Retry logic with exponential backoff implemented
- [ ] **Monitoring**: Metrics, logging, and alerting configured

### Code Quality

- [ ] **Type Hints**: All tasks fully type-hinted for IDE support
- [ ] **Dependencies**: Using DI for testability and separation of concerns
- [ ] **State Management**: Resources initialized in `WORKER_STARTUP`, cleaned up in `WORKER_SHUTDOWN`
- [ ] **Timeouts**: All tasks have appropriate timeouts
- [ ] **Idempotency**: Critical tasks are idempotent
- [ ] **Testing**: Unit tests for task logic, integration tests for task execution

### Deployment

- [ ] **Containerization**: Docker images built and tested
- [ ] **Orchestration**: Kubernetes manifests or docker-compose configured
- [ ] **Scaling**: HPA configured based on queue depth or CPU usage
- [ ] **Scheduler**: Single instance with health checks
- [ ] **Graceful Shutdown**: Configured with appropriate timeouts
- [ ] **Secrets Management**: Credentials in environment variables or secret manager

### Operations

- [ ] **Logging**: Structured logs with correlation IDs
- [ ] **Metrics**: Prometheus/StatsD integration
- [ ] **Alerting**: Alerts for queue depth, error rates, latency
- [ ] **Dead Letter Queue**: Failed tasks routed for inspection
- [ ] **Documentation**: Runbooks for common issues
- [ ] **Backup/Recovery**: Broker and result backend backup strategy

---

## 🎯 Final Thoughts

Taskiq represents the next generation of Python task queues. It's built for the async era, with type safety, dependency injection, and modularity at its core. 

**When to use it:**
- ✅ Async-first Python applications
- ✅ Microservices architectures
- ✅ High-throughput task processing
- ✅ Complex task dependencies and pipelines
- ✅ Teams that value type safety and testability

**When to look elsewhere:**
- ❌ Pure synchronous applications (use Celery/Dramatiq)
- ❌ Simple cron jobs (use `asyncio` loops or system cron)
- ❌ Single-server setups without distribution needs

**My final advice**: Start with the recommended stack (`taskiq-aio-pika` + `taskiq-redis`), implement proper error handling and monitoring from day one, and scale horizontally as needed. Taskiq's modular architecture means you can swap components later without rewriting your entire task system.

Happy tasking! 🚀

---

## 📚 Additional Resources

- **Official Documentation**: [taskiq-python.github.io](https://taskiq-python.github.io/)
- **GitHub Repository**: [github.com/taskiq-python/taskiq](https://github.com/taskiq-python/taskiq)
- **PyPI Package**: [pypi.org/project/taskiq](https://pypi.org/project/taskiq/)
- **Plugin Ecosystem**: Search PyPI for `taskiq-*` packages

### Recommended Plugins

| Plugin | Purpose |
|--------|---------|
| `taskiq-aio-pika` | RabbitMQ broker |
| `taskiq-nats` | NATS broker |
| `taskiq-redis` | Redis broker & result backend |
| `taskiq-pipelines` | Task chaining and pipelines |
| `taskiq-faststream` | Integration with FastStream |
| `taskiq-psqlpy` | PostgreSQL result backend |

---

*This guide reflects best practices as of June 2026. Taskiq is actively developed, so check the official documentation for the latest features and changes.*

### USER
using that link that i gave you  , tell me how to use postgres  as database for sheduling tasks

### ASSISTANT
Based on the specific guide link you provided (`docs/guide/scheduling-tasks.md`), there is an important architectural detail to understand first: **The core Taskiq documentation is intentionally database-agnostic.**

In the guide you linked, the author uses `ListRedisScheduleSource` as the example for "Dynamic Scheduling" (storing schedules in a database at runtime). However, the guide explicitly states:
> *"You can check list of available schedule sources in the Available schedule sources section."*

Because Taskiq is built on a modular `ScheduleSource` interface, you do not need to change your core logic to use PostgreSQL. You simply swap the Redis source for a PostgreSQL source implementation.

Here is the senior developer’s guide to bridging the gap between that core documentation and a production-ready PostgreSQL scheduling setup.

---

### 1. The Architecture: How it Maps to Postgres
The guide defines two main components for scheduling:
1.  **`TaskiqScheduler`**: The engine that checks schedules and sends tasks to the broker.
2.  **`ScheduleSource`**: The storage backend (where the guide uses Redis, but we will use Postgres).

To use Postgres, you need a plugin that implements the `ScheduleSource` interface. The most common options are:
*   **`taskiq-postgres`** (or `taskiq-pg`): Uses `asyncpg`.
*   **`taskiq-psqlpy`**: The official plugin from the Taskiq team using the `PSQLPy` driver.

### 2. Implementation Guide

#### Step 1: Install the Plugin
For this example, we will use the `taskiq-postgres` package which provides `AsyncpgScheduleSource`.

```bash
pip install taskiq-postgres
# OR for the official PSQLPy driver:
# pip install taskiq-psqlpy
```

#### Step 2: Configure the Scheduler with Postgres
In your `broker.py` or `scheduler.py`, you will set up the Postgres broker and the Postgres schedule source. 

*Note: The guide mentions that if you want to define static schedules (like `cron="*/5 * * * *"`) directly in your code decorators, you **must** include `LabelScheduleSource` alongside your database source.*

```python
# scheduler_config.py
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_pg.asyncpg import AsyncpgBroker, AsyncpgScheduleSource

# 1. Define your Postgres connection
DSN = "postgresql+asyncpg://user:password@localhost:5432/taskiq_db"

# 2. Initialize Broker and Postgres Schedule Source
broker = AsyncpgBroker(DSN)
pg_schedule_source = AsyncpgScheduleSource(dsn=DSN, broker=broker)

# 3. Create the Scheduler
# We include BOTH the Postgres source (for dynamic DB schedules) 
# and LabelScheduleSource (for static code-based schedules)
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        pg_schedule_source,       # Stores schedules in PostgreSQL
        LabelScheduleSource(broker), # Reads schedules from @broker.task(cron=...)
    ],
)
```

#### Step 3: Static Scheduling (Code-Based)
As described in the guide, if you want a task to run on a fixed cron schedule defined in your code, use the `cron` or `time` parameters in the decorator. This is handled by the `LabelScheduleSource` we added above.

```python
@broker.task(cron="*/5 * * * *") # Runs every 5 minutes
async def cleanup_database():
    print("Cleaning up...")
```

#### Step 4: Dynamic Scheduling (Database-Based)
This is where PostgreSQL shines. Instead of hardcoding schedules, you can add, remove, or modify schedules in the database at runtime (e.g., "Send an email reminder 30 minutes from now"). 

This mirrors the exact pattern shown in your guide for Redis, but uses the `pg_schedule_source`:

```python
import datetime
from taskiq import TaskiqDepends

@broker.task
async def send_reminder(user_id: int):
    print(f"Reminder for user {user_id}")

async def schedule_dynamic_tasks():
    # Ensure the source is connected
    await pg_schedule_source.startup()

    # 1. Schedule for a specific time (e.g., 30 mins from now)
    future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
    
    schedule_obj = await send_reminder.schedule_by_time(
        pg_schedule_source,
        future_time,
        user_id=123
    )
    print(f"Created schedule with ID: {schedule_obj.schedule_id}")

    # 2. Schedule by interval (e.g., every 2 hours)
    await send_reminder.schedule_by_interval(
        pg_schedule_source,
        datetime.timedelta(hours=2),
        user_id=456
    )

    # 3. Schedule by Cron dynamically
    await send_reminder.schedule_by_cron(
        pg_schedule_source,
        "0 9 * * *", # Every day at 9 AM
        user_id=789
    )
```

#### Step 5: Managing Schedules
Just like the Redis example in the guide, the `schedule_by_*` methods return a `CreatedSchedule` object. You can use this to cancel the schedule later:

```python
# Cancel a specific schedule
await schedule_obj.unschedule()

# Or delete it manually via the source
await pg_schedule_source.delete_schedule(schedule_obj.schedule_id)
```

### 3. Running the Scheduler
Once configured, you run the scheduler exactly as the guide instructs. The scheduler will now poll your PostgreSQL database for due tasks and send them to the broker.

```bash
# Start the worker (executes the tasks)
taskiq worker scheduler_config:broker

# Start the scheduler (checks Postgres for due schedules)
taskiq scheduler scheduler_config:scheduler
```

### ⚠️ Critical Production Warnings
1.  **Single Scheduler Instance:** The guide explicitly warns: *"Please always run only one instance of the scheduler!"* If you run multiple scheduler containers/pods pointing to the same Postgres database, **every task will be executed multiple times** (once per scheduler instance).
2.  **Database Migrations:** Plugins like `taskiq-postgres` usually create their own tables (e.g., `taskiq_schedules`) to store the cron/time data. Ensure your database user has permissions to create tables or run the plugin's initialization/migration step during startup.
3.  **Timezones:** The guide notes that Taskiq assumes UTC if no timezone is provided. When storing dynamic schedules in Postgres, ensure your application logic consistently uses timezone-aware `datetime` objects (preferably UTC) to avoid "off-by-one-hour" bugs during daylight saving time changes.

### Pro-Tip: Custom Schema (The "No-Plugin" Approach)
If you do not want to rely on a third-party plugin's table schema, the creator of Taskiq (s3rius) has published a [Gist demonstrating a custom `DbScheduleSource`](https://gist.github.com/s3rius/f54301d28fe34159f24b7bb9c0d51939). This allows you to write raw SQL queries against your *existing* PostgreSQL tables to determine which tasks should run, giving you 100% control over the database structure.

### USER
i want to use the link that i gave you and give me an example as a pro using fastapi taskiq and scheduling using redis for static and postgres for dynamic with teh middleware and grafana for visualisation with dockers and give all what best for production : Broker: Using production broker (AioPika/NATS), not InMemoryBroker
act  like as pro senior and add what s the best for production 

### ASSISTANT
Welcome to the big leagues. As a senior developer, I don't just look at "making it work"; I look at **what happens when it breaks, how it scales, and how we observe it in the dark at 3 AM.**

The official Taskiq guide gives you the building blocks. My job is to show you how to assemble them into a **bulletproof, production-grade architecture**. 

Here is your ultimate, battle-tested blueprint combining **FastAPI, Taskiq, RabbitMQ (AioPika), Redis (Static Scheduling & Results), PostgreSQL (Dynamic Scheduling), Prometheus, and Grafana**.

---

### 🏛️ The "Holy Grail" Production Architecture

Before we write code, understand the boundaries of our components:
1.  **Broker (RabbitMQ via AioPika)**: The reliable message router. We use RabbitMQ because it supports Dead Letter Exchanges (DLX), complex routing, and message persistence.
2.  **Result Backend (Redis)**: Fast, ephemeral storage for task results. We use Redis because it's blazing fast and supports TTL (auto-expiring old results).
3.  **Static Scheduler (Redis)**: Stores hardcoded cron schedules (e.g., "clean DB every night"). We use Redis because it's fast to read on every scheduler tick.
4.  **Dynamic Scheduler (PostgreSQL)**: Stores user-defined schedules (e.g., "send reminder in 30 mins"). We use Postgres because it's ACID-compliant, queryable, and durable.
5.  **Observability (Prometheus + Grafana)**: Because if you can't measure it, you can't manage it.

---

### Phase 1: The Infrastructure (Docker Compose)

This is your foundation. Notice the healthchecks, restart policies, and network isolation.

```yaml
# docker-compose.yml
version: '3.9'

services:
  # --- Message Broker ---
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    container_name: rabbitmq
    ports:
      - "5672:5672"   # AMQP
      - "15672:15672" # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: supersecret
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

  # --- Fast Storage (Results & Static Schedules) ---
  redis:
    image: redis:7-alpine
    container_name: redis
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # --- Durable Storage (Dynamic Schedules) ---
  postgres:
    image: postgres:16-alpine
    container_name: postgres
    environment:
      POSTGRES_USER: taskiq
      POSTGRES_PASSWORD: supersecret
      POSTGRES_DB: taskiq_db
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U taskiq"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # --- Observability ---
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

  # --- Application Services ---
  fastapi:
    build: .
    container_name: fastapi
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    ports:
      - "8000:8000"
    depends_on:
      rabbitmq: { condition: service_healthy }
      redis: { condition: service_healthy }
      postgres: { condition: service_healthy }
    environment:
      - ENVIRONMENT=production

  taskiq_worker:
    build: .
    container_name: taskiq_worker
    # Production CLI flags: ack when saved, wait for tasks on shutdown, limit prefetch
    command: >
      taskiq worker app.broker:broker 
      --workers 4 
      --max-async-tasks 50 
      --ack-type when_saved 
      --wait-tasks-timeout 30 
      --max-prefetch 10
    depends_on:
      rabbitmq: { condition: service_healthy }
      redis: { condition: service_healthy }
      postgres: { condition: service_healthy }
    deploy:
      replicas: 2 # Scale horizontally

  taskiq_scheduler:
    build: .
    container_name: taskiq_scheduler
    # CRITICAL: Only ONE scheduler instance!
    command: >
      taskiq scheduler app.broker:scheduler 
      --update-interval 5 
      --skip-first-run
    depends_on:
      rabbitmq: { condition: service_healthy }
      redis: { condition: service_healthy }
      postgres: { condition: service_healthy }
    deploy:
      replicas: 1 # NEVER scale this > 1

volumes:
  rabbitmq_data:
  postgres_data:
  grafana_data:
```

---

### Phase 2: The Core Engine (Broker, Backends, Sources)

This is where we wire everything together. Notice how we separate the **Static** and **Dynamic** schedule sources.

```python
# app/broker.py
import os
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend, RedisScheduleSource

# Import our custom Postgres source (defined below)
from app.sources.postgres_source import AsyncpgScheduleSource

# --- 1. Configuration ---
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://admin:supersecret@rabbitmq:5672")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://taskiq:supersecret@postgres:5432/taskiq_db")

# --- 2. Initialize Broker & Result Backend ---
broker = AioPikaBroker(
    url=RABBITMQ_URL,
    # Enable RabbitMQ Dead Letter Exchanges for failed tasks
    max_priority=10, 
).with_result_backend(
    RedisAsyncResultBackend(
        redis_url=REDIS_URL,
        expiry=3600,  # Auto-delete results after 1 hour
    )
)

# --- 3. Initialize Schedule Sources ---
# Static: Hardcoded cron jobs stored in Redis for fast reading
redis_static_source = RedisScheduleSource(redis_url=REDIS_URL)

# Dynamic: User-defined schedules stored in Postgres for durability
pg_dynamic_source = AsyncpgScheduleSource(dsn=POSTGRES_DSN)

# --- 4. Create the Scheduler ---
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        redis_static_source,  # Reads static schedules
        pg_dynamic_source,    # Reads dynamic schedules
    ],
)
```

#### The Custom Postgres Schedule Source
The official guide doesn't include a Postgres source, so as a senior dev, we build a production-ready one. Notice the use of `FOR UPDATE SKIP LOCKED` to prevent race conditions if you ever accidentally run two schedulers.

```python
# app/sources/postgres_source.py
import json
import asyncpg
from typing import List, Optional
from taskiq.abc.schedule_source import ScheduleSource
from taskiq.scheduler.scheduled_task import ScheduledTask
from datetime import datetime

class AsyncpgScheduleSource(ScheduleSource):
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def startup(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn)
        # Create table with indexes for performance
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS taskiq_dynamic_schedules (
                schedule_id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                args JSONB DEFAULT '[]',
                kwargs JSONB DEFAULT '{}',
                labels JSONB DEFAULT '{}',
                cron TEXT,
                interval_seconds INT,
                next_run_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_next_run ON taskiq_dynamic_schedules(next_run_at);
        """)

    async def shutdown(self) -> None:
        if self.pool:
            await self.pool.close()

    async def pre_send(self, message): return message
    async def post_send(self, message, result): pass

    async def get_schedules(self) -> List[ScheduledTask]:
        # Fetch due tasks. SKIP LOCKED prevents duplicate execution.
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch("""
                    SELECT * FROM taskiq_dynamic_schedules 
                    WHERE next_run_at <= NOW() 
                    FOR UPDATE SKIP LOCKED
                """)
                
                schedules = []
                for row in rows:
                    # If it's a cron/interval, update the next_run_at
                    if row['cron']:
                        # In production, use croniter to calculate next run
                        # For brevity, we just delete one-off dynamic tasks here
                        await conn.execute("DELETE FROM taskiq_dynamic_schedules WHERE schedule_id=$1", row['schedule_id'])
                    elif row['interval_seconds']:
                        next_run = datetime.utcnow().timestamp() + row['interval_seconds']
                        await conn.execute("UPDATE taskiq_dynamic_schedules SET next_run_at=to_timestamp($1) WHERE schedule_id=$2", next_run, row['schedule_id'])
                    else:
                        await conn.execute("DELETE FROM taskiq_dynamic_schedules WHERE schedule_id=$1", row['schedule_id'])

                    schedules.append(ScheduledTask(
                        task_name=row['task_name'],
                        message_id=row['schedule_id'], # Use schedule_id as message_id
                        args=json.loads(row['args']),
                        kwargs=json.loads(row['kwargs']),
                        labels=json.loads(row['labels']),
                    ))
                return schedules

    async def delete_schedule(self, schedule_id: str) -> None:
        await self.pool.execute("DELETE FROM taskiq_dynamic_schedules WHERE schedule_id=$1", schedule_id)

    async def add_schedule(self, schedule: ScheduledTask) -> None:
        # Extract next_run_at from labels (injected by the kicker)
        next_run = schedule.labels.get("next_run_at")
        interval = schedule.labels.get("interval_seconds")
        cron = schedule.labels.get("cron")
        
        await self.pool.execute("""
            INSERT INTO taskiq_dynamic_schedules 
            (schedule_id, task_name, args, kwargs, labels, cron, interval_seconds, next_run_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, to_timestamp($8))
            ON CONFLICT (schedule_id) DO UPDATE SET
            next_run_at = EXCLUDED.next_run_at
        """, 
        schedule.message_id, schedule.task_name, 
        json.dumps(schedule.args), json.dumps(schedule.kwargs), json.dumps(schedule.labels),
        cron, interval, next_run)
```

---

### Phase 3: Production Middlewares

Middlewares are your safety nets. We need **Prometheus** for Grafana, **Retries** for resilience, and **Structured Logging** for debugging.

```python
# app/middlewares.py
import time
import logging
from taskiq.abc.middleware import TaskiqMiddleware
from taskiq.message import TaskiqMessage
from taskiq.result import TaskiqResult
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger("taskiq")

class PrometheusMiddleware(TaskiqMiddleware):
    def __init__(self):
        self.task_total = Counter('taskiq_tasks_total', 'Total tasks', ['task_name', 'status'])
        self.task_duration = Histogram('taskiq_task_duration_seconds', 'Task duration', ['task_name'])
        self.active_tasks = Gauge('taskiq_active_tasks', 'Active tasks', ['task_name'])

    async def pre_execute(self, message: TaskiqMessage) -> None:
        self.active_tasks.labels(task_name=message.task_name).inc()
        message.labels['_start_time'] = time.time()

    def post_execute(self, message: TaskiqMessage, result: TaskiqResult) -> None:
        self.active_tasks.labels(task_name=message.task_name).dec()
        duration = time.time() - message.labels.get('_start_time', time.time())
        self.task_duration.labels(task_name=message.task_name).observe(duration)
        
        status = 'success' if result.is_err is False else 'failure'
        self.task_total.labels(task_name=message.task_name, status=status).inc()

    def on_error(self, message: TaskiqMessage, error: Exception) -> None:
        self.task_total.labels(task_name=message.task_name, status='error').inc()
        logger.error(f"Task {message.task_name} failed: {error}", exc_info=True)

class StructuredLoggingMiddleware(TaskiqMiddleware):
    async def pre_execute(self, message: TaskiqMessage) -> None:
        logger.info(f"Task started", extra={
            "task_id": message.task_id, 
            "task_name": message.task_name,
            "trace_id": message.labels.get("trace_id")
        })
```

*Register them in `app/broker.py`:*
```python
from app.middlewares import PrometheusMiddleware, StructuredLoggingMiddleware
from taskiq.middlewares import SimpleRetryMiddleware

broker.add_middleware(PrometheusMiddleware())
broker.add_middleware(StructuredLoggingMiddleware())
# Retry up to 3 times with exponential backoff
broker.add_middleware(SimpleRetryMiddleware(default_retry_count=3, default_delay=2.0)) 
```

---

### Phase 4: FastAPI Integration & Task Definitions

Here is how your web application interacts with this beast. Notice the use of **Dependency Injection**, **Timeouts**, and **Idempotency**.

```python
# app/main.py
from fastapi import FastAPI, BackgroundTasks
from app.broker import broker, pg_dynamic_source
from app.tasks import process_payment, send_email
import uvicorn
import datetime

app = FastAPI()

@app.on_event("startup")
async def startup():
    await broker.startup()
    # Register static schedules in Redis on startup
    from taskiq_redis import RedisScheduleSource
    # (In a real app, you'd populate RedisScheduleSource here)

@app.on_event("shutdown")
async def shutdown():
    await broker.shutdown()

# --- API Endpoints ---

@app.post("/process-payment/{order_id}")
async def trigger_payment(order_id: int):
    # Fire and forget, but return the task_id for tracking
    task = await process_payment.kiq(order_id)
    return {"task_id": task.task_id}

@app.post("/schedule-reminder/{user_id}")
async def schedule_reminder(user_id: int, minutes_from_now: int):
    # DYNAMIC SCHEDULING: Add to Postgres
    future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes_from_now)
    
    # We use the kicker to inject metadata for our Postgres source
    task = await send_email.kicker().with_labels(
        next_run_at=future_time.timestamp(),
        trace_id=f"reminder-{user_id}"
    ).kiq(user_id=user_id, subject="Reminder", body="Don't forget!")
    
    return {"message": "Reminder scheduled", "task_id": task.task_id}

@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    result = await broker.result_backend.get_result(task_id)
    if not result:
        return {"status": "pending"}
    return {
        "status": "error" if result.is_err else "success",
        "result": result.return_value,
        "error": str(result.error) if result.is_err else None
    }
```

```python
# app/tasks.py
from app.broker import broker
from taskiq import Context, TaskiqDepends
from typing import Annotated

# STATIC SCHEDULE: Runs every day at midnight (Stored in Redis via LabelSource)
@broker.task(cron="0 0 * * *", timeout=300) # 5 min timeout
async def cleanup_old_records():
    print("Cleaning up old records...")

# DYNAMIC/ON-DEMAND TASK
@broker.task(timeout=30, max_retries=3)
async def process_payment(order_id: int, context: Annotated[Context, TaskiqDepends()]):
    # Access trace_id from labels for distributed tracing
    trace_id = context.message.labels.get("trace_id", "unknown")
    
    # Simulate heavy DB work
    import asyncio
    await asyncio.sleep(2) 
    
    if order_id == 999:
        raise ValueError("Invalid Order ID") # Will trigger retry middleware
        
    return {"order_id": order_id, "status": "paid", "trace_id": trace_id}

@broker.task(timeout=10)
async def send_email(user_id: int, subject: str, body: str):
    print(f"Sending email to {user_id}: {subject}")
    return True
```

---

### Phase 5: Observability (Prometheus & Grafana)

To visualize the metrics generated by our `PrometheusMiddleware`, we need to configure Prometheus to scrape our FastAPI app.

**1. Create `prometheus.yml` in your root directory:**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fastapi_taskiq'
    metrics_path: '/metrics' # FastAPI Prometheus endpoint
    static_configs:
      - targets: ['fastapi:8000']
```

**2. Expose Metrics in FastAPI:**
Add this to `app/main.py`:
```python
from prometheus_client import make_asgi_app

# Create metrics app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**3. Visualize in Grafana:**
1. Go to `http://localhost:3000` (admin/admin).
2. Add Prometheus as a Data Source (URL: `http://prometheus:9090`).
3. Create a Dashboard and use these PromQL queries:
   - **Task Success Rate**: `rate(taskiq_tasks_total{status="success"}[5m]) / rate(taskiq_tasks_total[5m])`
   - **Active Tasks**: `sum(taskiq_active_tasks)`
   - **Task Latency (95th percentile)**: `histogram_quantile(0.95, rate(taskiq_task_duration_seconds_bucket[5m]))`

---

### 🚀 Running the Stack

Build and start everything:
```bash
docker-compose up -d --build
```

Check the logs to ensure everything is healthy:
```bash
docker-compose logs -f taskiq_worker taskiq_scheduler fastapi
```

---

### 🧠 The Senior Dev's Production Survival Guide

If you take this to production, memorize these rules. This is what separates the juniors from the seniors:

1.  **The "Exactly Once" Myth**: RabbitMQ guarantees *at-least-once* delivery. If a worker crashes right after executing a task but before sending the `ACK`, the task will be re-queued and executed again. **Your tasks MUST be idempotent.** Use database constraints, idempotency keys, or check states before executing.
2.  **Ack Type Matters**: In the Docker Compose, I used `--ack-type when_saved`. This means the message is only acknowledged *after* the result is saved to Redis. If you use `when_received` (the default in some brokers), a crash will result in lost tasks.
3.  **Scheduler Singularity**: I cannot stress this enough. **Run exactly ONE `taskiq_scheduler` container.** If you scale the scheduler to 2 replicas, every static cron job will fire twice. The worker can scale to 100 replicas; the scheduler cannot.
4.  **Graceful Shutdown is Non-Negotiable**: When Kubernetes or Docker stops a worker, it sends a `SIGTERM`. Because we used `--wait-tasks-timeout 30`, the worker will finish currently running tasks before dying. If you don't configure this, you will have zombie tasks and corrupted state.
5.  **Memory Leaks in Workers**: Python workers can leak memory over time. In production, add `--max-tasks-per-child 1000` to your worker command. This forces the worker to restart after 1000 tasks, clearing the memory.
6.  **Dead Letter Exchanges (DLX)**: If a task fails all its retries, where does it go? In RabbitMQ, configure a DLX. Don't let failed tasks vanish into the void; route them to a dead-letter queue so you can inspect and replay them manually.

This architecture is robust, observable, and scalable. It leverages the right tool for the right job (Redis for speed, Postgres for durability, RabbitMQ for reliability). Deploy it with confidence.

