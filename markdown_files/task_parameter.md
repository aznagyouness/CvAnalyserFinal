# 📋 Complete Taskiq Parameters Reference

Based on the official Taskiq source code and documentation, here are ALL the parameters available:

---

## 🎯 Table 1: `@broker.task` Decorator Parameters

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task_name` | `str \| None` | `None` | Custom task name. If `None`, auto-generated as `module:function` |
| `**labels` | `Any` | - | Arbitrary keyword arguments become message labels |

### Built-in Labels (Special Parameters)

| Label | Type | Description | Example |
|-------|------|-------------|---------|
| `timeout` | `float` | Task execution timeout in seconds | `@broker.task(timeout=60.0)` |
| `retry_on_error` | `bool` | Enable automatic retry on failure | `@broker.task(retry_on_error=True)` |
| `max_retries` | `int` | Maximum retry attempts | `@broker.task(max_retries=3)` |
| `delay` | `float` | Delay task execution (seconds) | `@broker.task(delay=300)` |
| `schedule` | `list[dict]` | Cron/interval scheduling | See scheduling section below |
| `priority` | `int` | Message priority (0-9 for RabbitMQ) | `@broker.task(priority=5)` |
| `queue_name` | `str` | Route to specific queue | `@broker.task(queue_name="high_priority")` |

### Scheduling Labels

```python
@broker.task(
    schedule=[
        {
            "cron": "0 2 * * *",           # str: crontab expression
            "cron_offset": None,            # str | timedelta | None: timezone offset
            "interval": None,               # int | timedelta: seconds between runs
            "time": None,                   # datetime: specific execution time
            "args": [],                     # List[Any]: positional args
            "kwargs": {},                   # Dict[str, Any]: keyword args
            "labels": {},                   # Dict[str, Any]: additional labels
            "schedule_id": "nightly_job",   # str | None: unique schedule ID
        }
    ]
)
async def nightly_cleanup():
    pass
```

### Complete Example

```python
@broker.task(
    task_name="indexing:process_file",
    timeout=300.0,
    retry_on_error=True,
    max_retries=3,
    priority=5,
    queue_name="heavy_io",
    schedule=[{"cron": "0 * * * *"}],
    custom_label="custom_value"  # Any custom label
)
async def process_file(file_id: str):
    pass
```

---

## 🏗️ Table 2: `AioPikaBroker` Constructor Parameters

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str \| None` | `"amqp://guest:guest@localhost:5672"` | RabbitMQ connection URL |
| `result_backend` | `AsyncResultBackend \| None` | `None` | **Deprecated** - use `.with_result_backend()` |
| `task_id_generator` | `Callable \| None` | `None` | **Deprecated** - use `.with_id_generator()` |
| `qos` | `int` | `10` | Prefetch count (messages per worker) |
| `loop` | `asyncio.AbstractEventLoop \| None` | `None` | Event loop to use |
| `**connection_kwargs` | `Any` | - | Additional `aio-pika` connection args |

### Exchange & Queue Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exchange` | `Exchange \| None` | `Exchange()` | Main exchange configuration |
| `task_queues` | `list[Queue] \| None` | `[]` | List of task queues |
| `dead_letter_queue` | `Queue \| None` | `Queue(name="taskiq.dead_letter")` | Dead letter queue config |
| `delay_queue` | `Queue \| None` | `None` | Queue for delayed messages |
| `delayed_message_exchange_plugin` | `bool` | `False` | Enable RabbitMQ delayed-message plugin |
| `delayed_message_exchange` | `Exchange \| None` | `None` | Exchange for delayed messages |

### Routing Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label_for_routing` | `str` | `"queue_name"` | Label name to determine routing key |
| `label_for_priority` | `str` | `"priority"` | Label name to determine message priority |

### Complete Example

```python
from taskiq_aio_pika import AioPikaBroker
from taskiq_aio_pika.exchange import Exchange
from taskiq_aio_pika.queue import Queue

broker = AioPikaBroker(
    url="amqp://user:pass@rabbitmq:5672/vhost",
    qos=20,
    exchange=Exchange(
        name="taskiq_exchange",
        type="direct",
        durable=True,
        declare=True,
    ),
    task_queues=[
        Queue(name="default", durable=True, declare=True),
        Queue(name="high_priority", durable=True, declare=True),
    ],
    dead_letter_queue=Queue(
        name="taskiq.dead_letter",
        durable=True,
        declare=True,
    ),
    delay_queue=Queue(name="taskiq.delay", durable=True, declare=True),
    label_for_routing="queue_name",
    label_for_priority="priority",
)
```

---

## 🔧 Table 3: `Exchange` Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"taskiq"` | Exchange name |
| `type` | `str` | `"direct"` | Exchange type: `direct`, `topic`, `fanout`, `headers` |
| `durable` | `bool` | `True` | Survive broker restarts |
| `auto_delete` | `bool` | `False` | Delete when no queues bound |
| `internal` | `bool` | `False` | Internal exchange (no direct publishing) |
| `passive` | `bool` | `False` | Only check if exists, don't create |
| `declare` | `bool` | `True` | Declare exchange on startup |
| `arguments` | `dict \| None` | `None` | Additional exchange arguments |
| `timeout` | `float \| None` | `None` | Declaration timeout |

---

## 📦 Table 4: `Queue` Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"taskiq_queue"` | Queue name |
| `durable` | `bool` | `True` | Survive broker restarts |
| `exclusive` | `bool` | `False` | Only one consumer allowed |
| `auto_delete` | `bool` | `False` | Delete when no consumers |
| `passive` | `bool` | `False` | Only check if exists |
| `declare` | `bool` | `True` | Declare queue on startup |
| `routing_key` | `str \| None` | `None` | Binding routing key |
| `max_priority` | `int \| None` | `None` | Max priority (0-255) |
| `type` | `QueueType` | `QueueType.CLASSIC` | Queue type: `CLASSIC` or `QUORUM` |
| `arguments` | `dict \| None` | `None` | Additional queue arguments |
| `timeout` | `float \| None` | `None` | Declaration timeout |
| `bind_arguments` | `dict \| None` | `None` | Arguments for binding |
| `bind_timeout` | `float \| None` | `None` | Binding timeout |
| `consumer_arguments` | `dict \| None` | `None` | Consumer arguments |

---

## 🔄 Table 5: Middleware Parameters

### SimpleRetryMiddleware

```python
from taskiq import SimpleRetryMiddleware

broker = broker.with_middlewares(
    SimpleRetryMiddleware(
        default_retry_count=3,  # Default max retries
    )
)
```

### SmartRetryMiddleware

```python
from taskiq import SmartRetryMiddleware

broker = broker.with_middlewares(
    SmartRetryMiddleware(
        default_retry_count=3,      # Default max retries
        default_delay=5,            # Default delay (seconds)
        use_jitter=True,            # Add random jitter
        use_exponential_backoff=True,  # Exponential backoff
    )
)
```

### Task-Specific Retry Labels

| Label | Type | Description |
|-------|------|-------------|
| `retry_on_error` | `bool` | Enable retry for this task |
| `max_retries` | `int` | Override default retry count |
| `delay` | `float` | Override default delay |

---

## 📊 Table 6: Kicker (`.kiq()`) Parameters

```python
# Method 1: Direct call
await my_task.kiq(arg1, arg2, kwarg1=value1)

# Method 2: With labels
await my_task.kicker().with_labels(
    timeout=60.0,
    priority=5,
    queue_name="high_priority",
    delay=300,
).kiq(arg1, arg2)

# Method 3: With specific task_id
await my_task.kicker().with_task_id("custom-id-123").kiq(arg1)
```

### Kicker Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `.with_labels(**labels)` | `**labels: Any` | Add message labels |
| `.with_task_id(task_id)` | `task_id: str` | Set custom task ID |
| `.kiq(*args, **kwargs)` | Task arguments | Send the task |

---

## 🎯 Quick Reference: Most Common Parameters

### For `@broker.task`:
```python
@broker.task(
    task_name="module:task",      # Custom name
    timeout=60.0,                  # Execution timeout
    retry_on_error=True,           # Enable retries
    max_retries=3,                 # Max retry attempts
    priority=5,                    # Message priority
    queue_name="my_queue",         # Route to queue
    delay=300,                     # Delay execution
    schedule=[{"cron": "0 * * * *"}]  # Schedule
)
```

### For `AioPikaBroker`:
```python
broker = AioPikaBroker(
    url="amqp://localhost",        # Connection URL
    qos=10,                        # Prefetch count
    exchange=Exchange(...),        # Exchange config
    task_queues=[Queue(...)],      # Queue config
)
```

---

## 📚 Sources

All information extracted from:
- [Taskiq GitHub Repository](https://github.com/taskiq-python/taskiq)
- [Taskiq Documentation](https://taskiq-python.github.io/)
- [taskiq-aio-pika Source Code](https://github.com/taskiq-python/taskiq-aio-pika)
- [Official Taskiq Guide](https://github.com/taskiq-python/taskiq/tree/master/docs/guide)
