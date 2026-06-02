# Tasks with Taskiq:

## The Main Code:
```python
@broker.task(
    task_name="tasks.file_processing.process_project_files",
    max_retry=3,
    retry_backoff=True,
    # labels={"queue": "io_queue"}
)
async def process_project_files(project_id: int):
    ...
```

## Define a Task (Create it):
### 1️⃣ `@broker.task(...)`
**Big Picture Mental Model:**
- This decorator registers your function with the **Taskiq Broker**.
- It makes the function "dispatchable" across the network.
- **Unlike Celery**: It supports `async def` natively. No more `asyncio.run()` hacks.

---

## Parameters:

### 2️⃣ `task_name="tasks.file_processing.process_project_files"`
- **What it does**: Explicitly sets the task's unique ID in the system.
- **Why it matters**: 
    - Decouples the task from the Python module path.
    - If you move the file, the task name stays the same, so pending tasks in the broker won't break.
- **🧠 Mental Model**: "This is the task's permanent address."

### 3️⃣ `max_retry=3`
- **What it does**: If the task raises an exception, Taskiq will automatically reschedule it.
- **Calculation**: 1 original run + 3 retries = 4 total attempts.
- **🧠 Mental Model**: "Don't give up on the first failure; the network might be glitchy."

### 4️⃣ `retry_backoff=True`
- **What it does**: Automatically increases the wait time between retries (Exponential Backoff).
- **Why it matters**: If a service is down, retrying immediately makes the problem worse. Waiting longer between retries gives the service time to recover.
- **🧠 Mental Model**: "Step back and give the system some breathing room."

---

### 5️⃣ Dependency Injection (The "Pro" Feature)
**This is Taskiq's superpower compared to Celery.**

```python
from taskiq import TaskiqDepends
from src.database import get_db

@broker.task
async def save_to_db(data: str, db = TaskiqDepends(get_db)):
    # Works exactly like FastAPI!
    await db.execute(...)
```
- **🧠 Mental Model**: "My background tasks are just as smart as my API endpoints."

---

### 6️⃣ FULL FLOW:
1. `await task.kiq()` sends the message to **RabbitMQ**.
2. **Taskiq Worker** (running in a separate process) picks up the message.
3. If the task is `async def`, the worker **awaits** it.
4. If an error occurs ❌, the worker checks `max_retry`.
5. Task is sent back to the broker with a delay (backoff).
6. Result is eventually saved to **Redis**.

---

## Retries: Best Practices 🛡️

### **When to Retry ✅**
- **External APIs**: Qwen/DeepSeek/OpenAI timeouts.
- **Database Connection**: Temporary "Too many connections" errors.
- **Network Issues**: DNS glitches or transient socket errors.

### **When NOT to Retry ⚠️**
- **Validation Errors**: If the user sent a bad `project_id`, retrying won't fix the ID.
- **Logic Bugs**: `IndexError` or `AttributeError` in your code won't be fixed by retrying.
- **Non-Idempotent Actions**: If your task sends an email, retrying might send the same email twice.

### **Pro Strategy (Selective Retries):**
Instead of `max_retry` on everything, catch specific errors:
```python
from taskiq import TaskiqRetries

@broker.task
async def index_task(project_id: int):
    try:
        await nlp_controller.index(...)
    except (ConnectionError, TimeoutError):
        # Only retry if it's a network/timeout issue
        raise TaskiqRetries() 
```

---
**🧠 Final Mental Model:**
Taskiq is **FastAPI for background tasks**. Use it to keep your RAG indexing and LLM calls non-blocking and resilient.
