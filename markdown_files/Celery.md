# *** Celery Configuration (Production Mind-Map Friendly) ***

## Celery Application
### Definition :
- Celery is a distributed task queue system used to run background jobs asynchronously.
- It relies on a **broker** for message delivery and an optional **backend** for result storage.

---
## 3-Step Mental Model :
### 1- Design Phase 📐 = ```s()```
####
```python
blueprint = task.s(args)  # Just planning task is fct decorated with task , is for Signatures ( plan ), not for starting --> Use s() to create signatures, then chain them
```
#### s() creates and returns a task blueprint (Signature) that describes HOW to run a task later. It does NOT execute anything.
####
```python
<class 'celery.canvas.Signature'> - it's just a blueprint!
```
design = task.s(args)  # Just planning
### 2- Construction Phase 🏗️ (start building) = ```delay() / apply_async() ```
-   return : AsyncResult ==> with it we can get task id , result if we wait for task to complete.
- just tells us that the task is began not more.
### 3- Waiting Phase ⏳ = ```.get()```
-   AsyncResult.get() : we can the result if we wait for task to complete.

### Example :
#### 1:
```python
# What s() returns:
blueprint = task.s(args)  # Returns a Signature (not a result!)

# Signature is a task RECIPE containing:
# - Which task to run - What arguments to pass  - Not yet executed!

# You can then:
y = blueprint.delay()        # start execution (get it with y.get() --> need to wait until task finished )
result = y.get()

# or with a chain containing ++ blueprint 
x = chain(blueprint1, ...)    # Plan a  workflows
y= x.delay()                    # or apply_async() to  start execution (get it with y.get() --> need to wait until task finished )
result = y.get()
```
#### 2:
```python
# the output of task1 is the input of task2
# From simple to workflow:

# SIMPLE (90% of cases):
task.delay(arg1, arg2)

# WORKFLOW needed? Convert to:
chain(
    task1.s(arg1, arg2),  # Step 1 blueprint
    task2.s(),            # Step 2 blueprint  
    task3.s()             # Step 3 blueprint
).delay()                 # Execute entire workflow
```

---
## start tasks 
### delay() = apply_async() with default settings! They're siblings, not enemies.
```python
# These are IDENTICAL:
task_name.delay(1, 2)
task_name.apply_async(args=(1, 2))  # Same thing!
```
### .delay() apply_async() doesn't care about your function type (if it s sync fct or async fct ). ==> It just sends the task to the queue. The worker determines how to execute it.
### delay() :
####
- -Shortcut method for simple task invocation
-No advanced options - just pass arguments
-Use in FastAPI endpoints for fire-and-forget tasks
#### Example: 
```python
task_name.delay(arg1, arg2)
```
#### USE:
- Email notifications
Database updates
Simple background processing
90% of your endpoints!

### apply_async() :
#### 
- -Full-featured method with complete control
-Accepts advanced options: countdown, eta, queue, priority, retry_policy, etc.
-Required for scheduled tasks, custom routing, callbacks
-Use for production-grade task configuration
#### Example: 
```python
task.apply_async(args=(1, 2), countdown=60, queue='high_priority')
```
#### USE:
- Scheduling (countdown/eta)
Priority handling
Queue routing
Complex workflows
Production robustness
---

## **Celery App Initialization**

### Exp :
```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "minirag",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=[
        "tasks.file_processing",
        "tasks.data_indexing",
        "tasks.process_workflow",
        "tasks.maintenance",
    ],
)
# so we have 4 files containing our tasks (fcts )
```
### App Name
#### Parameter : name  
##### Type : str  
#### Possible Values :
- Any string (`"myapp"`, `"worker"`, `"celery_app"`)
#### Description :
- Logical identifier for the Celery application
- Appears in logs, monitoring tools (Flower), and task namespaces
#### Best Practice :
- Use your project name

---

### Broker
#### Parameter : broker  
##### Type : str (URL)  
#### Possible Values :
- `redis://host:port/db`
- `amqp://user:password@host:port/vhost` (RabbitMQ)
- `sqs://` (AWS SQS)
- `memory://` (development only)
#### Description :
- Message queue transporting tasks from producers to workers
#### Best Practice :
- Redis for simplicity
- RabbitMQ for advanced routing and reliability

---

### Result Backend
#### Parameter : backend  
##### Type : str (URL)  
#### Possible Values :
- `redis://host:port/db`
- `rpc://`
- `database+postgresql://...`
- `disabled://`
#### Description :
- Stores task states and results
#### Best Practice :
- Disable if results are not required

---

### Included Task Modules
#### Parameter : include  
##### Type : List[str]  
#### Possible Values :
##### Python module (.py file) paths containing tasks 
##### deponds to your entry point : celery -A src.celery_app flower --port=5555
##### ==> entry point is src 
######
```python
celery_app = Celery(
    "assai celery",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND_URL,
    include=[
        "src.tasks.file_processing",
    ],
)   
```
#### Description :
- Ensures Celery loads tasks at startup
#### Why :
- -Celery does not automatically scan all files in your project.
-You must tell Celery which modules contain tasks, otherwise you’ll get errors like:
#### Exp : 
```python
# in task we have --> email.py & ml.py where tasks (fcts) are defined.
from celery import Celery

app = Celery(
    "app",
    broker="redis://localhost:6379/0",
    include=[
        "app.tasks.email",
        "app.tasks.ml"
    ]
)
```

---
## ✅ Best-Practice Code Example (Production Ready)

```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "minirag",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=[
        "tasks.file_processing",
        "tasks.data_indexing",
        "tasks.process_workflow",
        "tasks.maintenance",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Reliability
    task_acks_late=True,
    task_time_limit=600,

    # Results
    task_ignore_result=False,
    result_expires=3600,

    # Workers
    worker_concurrency=4,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    # Broker resilience
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # Routing
    task_routes={
        "tasks.file_processing.*": {"queue": "file_processing"},
        "tasks.data_indexing.*": {"queue": "data_indexing"},
        "tasks.maintenance.*": {"queue": "default"},
    },

    # Periodic tasks
    beat_schedule={
        "cleanup-old-records": {
            "task": "tasks.maintenance.clean_celery_executions_table",
            "schedule": crontab(minute="*/10"),
        }
    },

    timezone="UTC",
)

celery_app.conf.task_default_queue = "default"
```



## **Serialization & Content Safety**

### Task Serializer
#### Parameter : task_serializer  
##### Type : str  
#### Possible Values :
- `json` ✅
- `pickle` ⚠️ (unsafe)
- `yaml`
- `msgpack`
#### Description :
##### How tasks are sent :  Serialization format for task payloads ==> A task payload is what the task contains — the arguments, parameters, and data needed to execute the task.
#####
```python
add.delay(2, 3)
The payload is essentially:
{
  "args": [2, 3],
  "kwargs": {}
}
```
#### Best Practice :
- Use `json` only

---

### Result Serializer
#### Parameter : result_serializer  
##### Type : str  
#### Possible Values :
- Same as task_serializer
#### Description :
- Serialization format for task results : How results are stored

---

### Accepted Content
#### Parameter : accept_content  
##### Type : List[str]  
#### Possible Values :
- `["json"]`
- `["json", "msgpack"]`
#### Description :
- Restricts allowed serializers : What workers accept
#### Security :
- Prevents arbitrary code execution

---

## Task Reliability & Safety

### Late Acknowledgment
#### Parameter : task_acks_late  
##### Type : bool  
#### Possible Values :
- True → acknowledge after execution
- False → acknowledge before execution
#### Description :
- Prevents task loss on worker crash
#### Best Practice :
- True for long-running or critical tasks

---

### Task Time Limit
#### Parameter : task_time_limit  
##### Type : int | None  
#### Possible Values :
- None
- Seconds (300, 600, 3600)
#### Description :
- Hard-kills tasks exceeding the limit
#### Best Practice :
- Always set in production

---

## Result Handling

### Ignore Task Result
#### Parameter : task_ignore_result  
##### Type : bool  
#### Possible Values :
- True → no result stored
- False → result stored
#### Description :
- Reduces backend load for fire-and-forget tasks
A fire-and-forget task is a background job you send to a worker and then immediately move on without waiting for a result or caring about the return value—once the task is dispatched,
 your app continues as if it’s done; this is ideal for things like sending emails, logs, notifications, or metrics where success doesn’t affect the current request, 
 and because no result is stored or fetched, it reduces load on the result backend and keeps the system fast and scalable.
==> If the system doesn’t break when the task result is lost → fire-and-forget is the right choice.

---

### Result Expiration
#### Parameter : result_expires  
##### Type : int | None  
#### Possible Values :
- Seconds (3600, 86400)
- None
#### Description :
- Auto-cleans old task results : 
Keep results only as long as someone might realistically read them.

---

## Worker Configuration

### Worker Concurrency
#### Parameter : worker_concurrency  
##### Type : int  
#### Possible Values :
- CPU core count
- Fixed integer (2, 4, 8)
#### Description :
- = how many tasks a single Celery worker can execute at the same time, and the right value depends mainly on whether your tasks are CPU-bound or I/O-bound.
Concurrency equals how many tasks your hardware can run at once without fighting for CPU or memory.
#### Guidelines :
##### CPU-bound → cores
- worker_concurrency ≈ number of CPU cores
-- Example (8-core machine): --concurrency=8
##### IO-bound → higher
- worker_concurrency = cores × (2–5)
##### Memory matters (critical!) ⚠️
###### check always : worker_concurrency × task_memory < available RAM
######
```python
How to verify in real life 🔍

Monitor:

- CPU usage (should be high but not 100% all the time)

- Memory usage (no swapping)

- Queue length (should drain steadily)

- Task latency

If:

-   CPU idle → increase concurrency

-   CPU maxed → decrease concurrency

-   Memory spikes → decrease concurrency
```
#### Celery defaults : 
- worker_concurrency = number of CPU cores
---

### Cancel Tasks on Connection Loss
#### Parameter : worker_cancel_long_running_tasks_on_connection_loss  
##### Type : bool  
#### Possible Values :
- True
- False
#### Description :
- Cancels tasks if broker connection is lost
#### Best Practice :
- True

---

## Broker Reliability

### Retry on Startup
#### Parameter : broker_connection_retry_on_startup  
##### Type : bool  
#### Possible Values :
- True
- False
#### Description :
- Retries broker connection at worker startup
#### Required For :
- Docker / Kubernetes

---

### Retry on Runtime Failure
#### Parameter : broker_connection_retry  
##### Type : bool  
#### Possible Values :
- True
- False
#### Description :
- Enables reconnect on broker failure

---

### Max Broker Retries
#### Parameter : broker_connection_max_retries  
##### Type : int | None  
#### Possible Values :
- Integer (e.g. 10)
- None (infinite)
#### Description :
- Limits reconnection attempts when brocker doesn't recieve ACK on the task limit time.

---

## Task Routing & Queues

### Task Routes
#### Parameter : task_routes  
##### Type : Dict[str, Dict]  
#### Possible Values :
- Task name → queue mapping
#### Description :
- Routes tasks to specific queues
#### Purpose :
- Workload isolation
- Independent scaling
#### why exist :
```python
Why task_routes exists 🧭

Without routing:

- All tasks land in the default queue

- Heavy tasks block light ones

- No isolation, no prioritization

With task_routes:

- CPU-heavy tasks → CPU workers

- I/O tasks → I/O workers

- Critical tasks → high-priority queues
```

---

### Default Queue
#### Parameter : task_default_queue  
##### Type : str  
#### Possible Values :
- Any queue name
#### Description :
- Used when no route matches a task
#### Requirement :
- Must always exist

---

## Periodic Tasks (Celery Beat)

### Beat Schedule
#### Parameter : beat_schedule  
##### Type : Dict  
#### Possible Values :
- Integer seconds
- `crontab(...)`
- `timedelta(...)`
#### Description :
- Defines scheduled tasks
#### Use Case :
- Cleanup
- Maintenance
- Monitoring
#### Why ?
- Without Beat: You manually call tasks.
With Beat: Tasks run automatically on schedule!

---

## Time Configuration

### Timezone
#### Parameter : timezone  
####### Type : str  
#### Possible Values :
- "UTC"  : like GMT
- "Africa/Casablanca"
- "Europe/Paris"
#### Best Practice :
- Always use UTC

---



## Celery 5.x Return Cheat Sheet

### Constructors / Primitives

| Constructors / Methods | Returns |
|------------------------|---------|
| `Celery()` | Celery application instance |
| `Task()` | Base task class (custom task logic) |
| `signature()` / `s()` | Task signature object |
| `chain()` | Chain object (sequential execution) |
| `group()` | Group object (parallel execution) |
| `chord()` | Chord object (group + callback) |

### Task Execution & Result Handling

| Methods / Attributes | Returns |
|----------------------|---------|
| `delay(*args, **kwargs)` | `AsyncResult` (task result handle) |
| `apply_async(...)` | `AsyncResult` |
| `AsyncResult.task_id` | `str` (task UUID) |
| `AsyncResult.get(timeout=None)` | Task result or raises exception |
| `AsyncResult.state` | `str` (`PENDING`, `STARTED`, `SUCCESS`, `FAILURE`, etc.) |
| `AsyncResult.status` | Alias of `state` |
| `AsyncResult.ready()` | `bool` (True if finished) |
| `AsyncResult.successful()` | `bool` (True if succeeded) |
| `AsyncResult.failed()` | `bool` (True if failed) |
| `AsyncResult.result` | Task return value or exception |
| `AsyncResult.traceback` | Exception traceback (if failed) |

### Task Control & State Management

| Methods / Attributes | Returns |
|----------------------|---------|
| `Task.update_state(state=..., meta=...)` | `None` (updates task state in result backend; A task method (bind=True required) that updates the task's current state and metadata ) |
| `revoke(task_id, terminate=False)` | `None` (revokes task) |
| `control.revoke(task_id, terminate=False)` | `None` (revokes remote task) |

### Worker Inspection & Monitoring

| Methods | Returns |
|--------|---------|
| `inspect().active()` | `dict` of active tasks per worker |
| `inspect().reserved()` | `dict` of reserved tasks per worker |
| `inspect().scheduled()` | `dict` of scheduled tasks per worker |
| `inspect().stats()` | Worker statistics |
| `control.ping()` | List of worker responses |
