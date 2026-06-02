# 🚀 Celery Masterclass: From Zero to Pro

Welcome, Scholar! You are about to master **Celery**, the powerhouse of distributed task queues in the Python ecosystem. Think of Celery not just as a library, but as the **Postal Service** for your application.

---

## 🏛️ 1. The "Postal Service" Architecture

To use Celery like a pro, you must visualize how data flows:

1.  **The Producer (Your FastAPI App)**: Someone writes a letter (a task) and puts it in the mailbox.
2.  **The Broker (Redis/RabbitMQ)**: The post office sorting facility. It holds the letters until a mailman is ready.
3.  **The Worker (Celery Process)**: The mailman who picks up the letter and actually delivers the package (executes the code). (in reality the worker is a process having code & memory space & the OS is choose what worker that will execute the task with CPU)
4.  **The Result Backend (PostgreSQL/Redis)**: A delivery receipt that says "Task Completed" or "Task Failed."

---

## ⚡ 2. Choosing Your "Mailmen" (Worker Types)

This is where most developers fail. You must choose your worker type based on the **job description**:

### **A. The Muscle (Prefork)**
-   **What it is**: Uses Python's `multiprocessing`.
-   **Best for**: **CPU-Bound** tasks (Image processing, local ML models, heavy math).
-   **Pro Tip**: Use this when your code is doing the "heavy lifting" itself.
-   **Command**: `celery -A main.celery_app worker --pool=prefork -c 4`

### **B. The Multitasker (Eventlet / Gevent)**
-   **What it is**: Uses "Greenlets" (lightweight threads).
-   **Best for**: **I/O-Bound** tasks (API calls to Qwen/DeepSeek, database queries, web scraping).
-   **Pro Tip**: You can run **thousands** of these on a single CPU core because they spend most of their time waiting for the internet.
-   **Command**: `celery -A main.celery_app worker --pool=eventlet -c 1000`

---

## 🛠️ 3. Designing Tasks Like a Senior Architect

### **Rule #1: Tasks must be Idempotent**
A task should be safe to run 10 times or 1 time. If it fails halfway and restarts, it shouldn't create duplicate data.
-   **Bad**: `add_balance(user_id, 100)`
-   **Pro**: `set_balance(user_id, new_total)` or check if a transaction ID exists first.

### **Rule #2: Keep the "Payload" Slim**
Don't send large objects (like a whole PDF file) through Celery.
-   **Bad**: `process_pdf(pdf_bytes)` (This clogs your Broker/Redis).
-   **Pro**: `process_pdf(file_path)` or `process_pdf(asset_id)`. Let the worker fetch the data it needs.

### **Rule #3: The "Retry" Mindset**
The internet is flaky. Your tasks should expect failure.
```python
@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def index_document(self, doc_id):
    # If the Vector DB is down, Celery will wait and try again automatically!
    ...
```

---

## 🔗 4. Integrating with FastAPI (The Pro Pattern)

In production, you never make a user wait for a "Loading" screen for more than 2 seconds.

1.  **User Hits Endpoint**: "Index my Project!"
2.  **FastAPI**: `task = index_task.delay(project_id)`
3.  **FastAPI Returns**: `{"task_id": task.id, "status": "Pending"}`
4.  **Frontend**: Polls a status endpoint or uses WebSockets to show a progress bar.

---

## 🌟 5. Pro Tips for the CvanalyserFinal Project

1.  **Separate Queues**: Create a `high_priority` queue for "Search" and a `low_priority` queue for "Batch Indexing." Don't let a big indexing job block a user's search query!
2.  **Monitoring**: Use **Flower**. It's a web-based dashboard for Celery. Run it with:
    `celery -A main.celery_app flower`
3.  **Timeouts**: Always set a `time_limit`. Never let a worker hang forever on a stuck API call.

---

### 🎓 Final Exam Question:
If you are calling the **Qwen API** to embed 1,000 resumes, which worker pool should you use?
*(Answer: Eventlet/Gevent, because you are waiting on the network!)*

---

## 🏗️ 6. Complete Pro Example: The "Async Indexing" Pattern

Here is how a senior engineer would implement the `index_project` flow in your project.

### **A. The Task Definition (`tasks.py`)**
```python
from celery import Celery
from src.controllers.NLPController import NLPController
from src.database import get_utils

# 1. Initialize Celery
celery_app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/1')

@celery_app.task(
    bind=True, 
    name="tasks.index_project_task",
    autoretry_for=(Exception,), 
    retry_backoff=True, 
    max_retries=3
)
def index_project_task(self, project_id: int, provider: str):
    """
    Pro Example: Heavy indexing job moved to background.
    """
    import asyncio
    
    # Since our controllers are async, we use a helper to run them in Celery
    loop = asyncio.get_event_loop()
    
    async def run_indexing():
        # Get DB and VectorDB clients
        (db_engine, db_client_sessionmaker) = await get_utils()
        
        # ... logic to initialize NLPController ...
        # nlp_controller.index_into_vector_db(...)
        return f"Project {project_id} indexed successfully!"

    return loop.run_until_complete(run_indexing())
```

### **B. The FastAPI Route (`routes/nlp.py`)**
```python
@nlp_router.post("/index/push/{project_id}")
async def index_project_async(project_id: int, push_request: PushRequest):
    # 1. Trigger the task (returns immediately)
    task = index_project_task.delay(project_id, push_request.provider)
    
    # 2. Return the Task ID to the frontend
    return {
        "message": "Indexing started in background",
        "task_id": task.id,
        "check_status_url": f"/api/v1/tasks/status/{task.id}"
    }
```

### **C. The Status Checker (`routes/tasks.py`)**
```python
@task_router.get("/status/{task_id}")
def get_status(task_id: str):
    task_result = index_project_task.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task_result.status, # PENDING, PROGRESS, SUCCESS, FAILURE
        "result": task_result.result if task_result.ready() else None
    }
```

---

## 🛡️ 7. Idempotency: The "Check-Then-Act" Pattern

**Idempotency** means that if you run the same task 100 times, the result is the same as running it once. In a distributed system, tasks **will** occasionally retry due to network glitches. If your task isn't idempotent, you'll end up with duplicate data (e.g., duplicate embeddings in your Vector DB).

### **The "Pro" Way to Handle Idempotency**

Instead of just "inserting," always verify the state first.

```python
@celery_app.task(bind=True, max_retries=3)
def process_cv_task(self, asset_id: int):
    # 1. Check if this asset was already processed successfully
    # We use a unique 'status' or 'processed_at' flag in the database
    asset = db.get_asset(asset_id)
    if asset.status == "COMPLETED":
        print(f"✅ Asset {asset_id} already processed. Skipping.")
        return "Already Done"

    try:
        # 2. Perform the work
        text = extract_text(asset.path)
        index_into_qdrant(asset_id, text)

        # 3. Mark as completed in the SAME transaction if possible
        asset.status = "COMPLETED"
        db.commit()
        
    except Exception as exc:
        # If it fails here, the status remains 'PENDING' 
        # and the next retry will attempt the work again.
        raise self.retry(exc=exc)
```

### **Why this matters for your Project:**
In your [NLPController.py](file:///c:/Users/user/Documents/trae_projects/CvanalyserFinal/src/controllers/NLPController.py#L50), if the `insert_many` call to Qdrant succeeds but the network cuts out before Celery can record the task as "Success," Celery will **retry** the task. 

Without an idempotency check, you would insert the **same vectors again**, giving you duplicate search results! Always check if the `record_ids` already exist in Qdrant before inserting.

---
*Generated with ❤️ by your AI Pair Programmer.*
