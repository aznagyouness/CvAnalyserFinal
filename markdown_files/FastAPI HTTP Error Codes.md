# FastAPI HTTP Error Codes

FastAPI uses standard HTTP status codes to indicate the success or failure of an API request. You raise them via `fastapi.HTTPException` (or `starlette.exceptions.HTTPException`).

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.get("/items/{item_id}")
def read_item(item_id: int):
    if item_id <= 0:
        raise HTTPException(status_code=400, detail="item_id must be positive")
    return {"item_id": item_id}
```

## 4xx — Client Errors

The request was malformed, unauthorized, or the client asked for something it can't have.

| Code | Name | Meaning | When to use in FastAPI |
|------|------|---------|------------------------|
| **400** | Bad Request | Generic client-side error; the server cannot process the request due to client mistake. | Invalid query params, malformed JSON, business rule violation. |
| **401** | Unauthorized | No valid authentication credentials provided. | Missing/invalid token, no `Authorization` header. |
| **403** | Forbidden | Authenticated but not allowed to access this resource. | Valid token but insufficient permissions/role. |
| **404** | Not Found | Resource doesn't exist. | Item not in DB, route doesn't match. |
| **405** | Method Not Allowed | HTTP verb not supported for this endpoint. | Sending `POST` to a `GET`-only route (FastAPI auto-handles). |
| **406** | Not Acceptable | Server can't produce a response matching the `Accept` header. | Client asks for `application/xml` but you only return JSON. |
| **409** | Conflict | Request conflicts with current resource state. | Duplicate username, unique-key collision on insert. |
| **415** | Unsupported Media Type | Payload format not supported. | Client sends XML body but endpoint expects JSON. |
| **422** | Unprocessable Entity | Request is well-formed but semantically invalid. | Pydantic validation failure (FastAPI's default for body validation). |
| **429** | Too Many Requests | Rate limit exceeded. | User hammered the endpoint; pair with `Retry-After` header. |

## 5xx — Server Errors

The request was valid but the server failed to handle it.

| Code | Name | Meaning | When to use in FastAPI |
|------|------|---------|------------------------|
| **500** | Internal Server Error | Generic server-side failure. | Unhandled exception, unexpected crash. |
| **501** | Not Implemented | Server doesn't support the feature. | Feature stubbed out, planned for later. |
| **502** | Bad Gateway | Upstream service returned an invalid response. | Your API calls another API that returned garbage. |
| **503** | Service Unavailable | Server temporarily down (overload or maintenance). | Deploying, DB down, health check failing. |
| **504** | Gateway Timeout | Upstream service didn't respond in time. | Downstream API timed out. |

## Quick Usage Examples

```python
from fastapi import HTTPException, status

# 400
raise HTTPException(status_code=400, detail="Invalid input")

# 401 — usually handled by OAuth2 / Depends
raise HTTPException(
    status_code=401,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)

# 403
raise HTTPException(status_code=403, detail="Not enough permissions")

# 404
raise HTTPException(status_code=404, detail="Item not found")

# 409
raise HTTPException(status_code=409, detail="Email already registered")

# 422 — usually auto-raised by Pydantic, but you can raise it manually too
raise HTTPException(status_code=422, detail="Validation failed")

# 429 with Retry-After
raise HTTPException(
    status_code=429,
    detail="Rate limit exceeded",
    headers={"Retry-After": "60"},
)

# 500
raise HTTPException(status_code=500, detail="Something went wrong")
```

## Custom Exception Handler

For consistent error response shapes across the app, register a custom handler:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

class AppError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "path": request.url.path},
    )
```


# ✅ Why `except Exception` is OK here:
```python
try:
    # RULE 2: Microscopic try block around the external call
    vectors = [
                self.embedding_client.embed_text(text=text, document_type=DocumentTypeEnum.DOCUMENT.value)
                for text in texts
            ]
except Exception as e:
    # RULE 3 & 4: Log with exc_info and chain the exception
    logger.error(f"Embedding failed for project {project.project_id}", exc_info=True)
    raise EmbeddingError(str(e)) from e
```

1. **External API calls have unpredictable failure modes**
   - Network timeouts
   - Authentication errors
   - Rate limits
   - Malformed responses
   - Library bugs
   - SSL errors
   
   You can't predict or catch all of these individually.

2. **You're translating, not swallowing**
   ```python
   logger.error(..., exc_info=True)  # Full stack trace preserved
   raise EmbeddingError(...) from e  # Domain error, original chained
   ```
   You log everything, then raise a clean domain error. Nothing is lost.

3. **This is the "Exception Translation" pattern**
   It's a recognized best practice for wrapping external systems. You convert low-level, library-specific errors into business-level errors your app understands.

### ❌ When `except Exception` is BAD:

```python
# BAD: Swallowing the error
try:
    process_payment()
except Exception as e:
    print("Failed")  # Lost context, no re-raise

# BAD: Catching in business logic where you know what should fail
try:
    user = get_user(user_id)  # You know this raises ValueError
    data = parse_json(user.data)  # You know this raises JSONDecodeError
except Exception:  # Which one failed?!
    pass
```

### The Rule:

**Use `except Exception` when:**
- Wrapping external API/library calls
- You want to translate ANY failure into a domain error
- You log with `exc_info=True` AND re-raise

**Avoid `except Exception` when:**
- You know exactly what errors can occur (catch them specifically)
- You're swallowing the error without re-raising
- You're in business logic with predictable failure modes

Your code is correct because it's wrapping an external embedding API, logging everything, and re-raising as a domain error.


# III - error handeling and logging strategy in this link : https://github.com/bakrianoo/mini-rag
give me your point of view of error handeling and logging strategy in this link : https://github.com/bakrianoo/mini-rag

### ASSISTANT
As a Senior/Staff Engineer reviewing the **[bakrianoo/mini-rag](https://github.com/bakrianoo/mini-rag)** repository, I can see it is explicitly designed as an "Educational Project (step by step) to teach how to build a production-ready app for RAG application" . 

Architecturally, it has good separation of concerns (Routes, Controllers, Models, Stores). However, from a **strict production-grade error handling and logging perspective**, it has several critical gaps that would cause major debugging headaches in a real-world environment.

Here is my detailed, rule-by-rule code review of its strategy.

---

### ✅ What They Do Right (Strengths)

1. **Avoids Exceptions for Control Flow (Rule 7)**: 
   The code correctly uses `if not project:` instead of wrapping `get_project` in a `try/except KeyError`. This is a great habit.
2. **Clean Separation of Concerns**: 
   Routes handle HTTP, `NLPController` handles business logic, and `Stores` handle external APIs. This makes it *easy* to inject proper error handling later.
3. **No "Bare Except" Anti-Pattern**: 
   Because there are almost no `try/except` blocks, it avoids the cardinal sin of swallowing errors with `except Exception:`.

---

### 🚨 Critical Production Gaps (Weaknesses)

#### 1. The "Boolean Return" Anti-Pattern (Violates Rule 3 & 5)
In `NLPController.py`, methods like `index_into_vector_db` and `search_vector_db_collection` return `False` or `None` on failure.
```python
# NLPController.py
if not results:
    return False  # 🚨 WHY did it fail? Network timeout? Bad vector? Empty DB?
```
**Why this is bad:** It destroys the traceback. The caller (`nlp.py`) only knows it failed, but has no idea *why*. You cannot log the root cause, and you cannot make intelligent retry decisions.

#### 2. Generic 400 Bad Request for Everything (Violates HTTP Semantics)
In `routes/nlp.py`, almost every failure returns a `400 Bad Request`:
```python
# routes/nlp.py
if not project:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, ...) # Should be 404!

if not is_inserted:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, ...) # Should be 500/502!
```
**Why this is bad:** A missing project is a `404 Not Found`. A Vector DB timeout is a `502 Bad Gateway` or `500 Internal Server Error`. Lumping them all into `400` tells the client "you sent bad data," which is a lie if the server's database is down.

#### 3. Zero Contextual Logging (Violates Rule 3)
The file declares `logger = logging.getLogger('uvicorn.error')`, but **it is never used** to log failures. 
When `is_inserted` is `False`, the code just returns a JSON response. If this happens in production, you will have zero logs to investigate why the Vector DB insertion failed.

#### 4. Unhandled External API Exceptions
There are no `try/except` blocks around external calls like `self.embedding_client.embed_text()` or `self.generation_client.generate_text()`. If the OpenAI/Cohere API times out or returns a 500, it will bubble up as an unhandled `500 Internal Server Error`, potentially leaking raw stack traces to the client.

---

### 🛠️ Before & After: Refactoring to Production Standards

Here is how I would refactor this exact code to apply the **7 Golden Rules**.

#### Step 1: Define Custom Domain Exceptions (Rule 5)
Instead of returning `False` or using `ResponseSignal` enums, we raise specific exceptions.

```python
# src/exceptions.py
class RAGServiceError(Exception):
    """Base exception for RAG operations."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class ProjectNotFoundError(RAGServiceError):
    def __init__(self, project_id: str):
        super().__init__(f"Project '{project_id}' not found", status_code=404)

class VectorDBInsertError(RAGServiceError):
    def __init__(self, project_id: str, reason: str):
        super().__init__(f"Failed to index project '{project_id}': {reason}", status_code=502)

class EmbeddingError(RAGServiceError):
    def __init__(self, reason: str):
        super().__init__(f"Embedding generation failed: {reason}", status_code=502)
```

#### Step 2: Refactor the Controller to Raise, Not Return `False` (Rules 2, 3, 4)
```python
# src/controllers/NLPController.py
import logging

logger = logging.getLogger(__name__)

class NLPController(BaseController):
    # ... init ...

    def index_into_vector_db(self, project: Project, chunks: List[DataChunk], chunks_ids: List[int], do_reset: bool = False):
        collection_name = self.create_collection_name(project_id=project.project_id)
        texts = [c.chunk_text for c in chunks]
        
        try:
            # RULE 2: Microscopic try block around the external call
            vectors = [
                self.embedding_client.embed_text(text=text, document_type=DocumentTypeEnum.DOCUMENT.value)
                for text in texts
            ]
        except Exception as e:
            # RULE 3 & 4: Log with exc_info and chain the exception
            logger.error(f"Embedding failed for project {project.project_id}", exc_info=True)
            raise EmbeddingError(str(e)) from e

        try:
            self.vectordb_client.create_collection(collection_name=collection_name, embedding_size=self.embedding_client.embedding_size, do_reset=do_reset)
            self.vectordb_client.insert_many(collection_name=collection_name, texts=texts, metadata=[c.chunk_metadata for c in chunks], vectors=vectors, record_ids=chunks_ids)
        except Exception as e:
            logger.error(f"Vector DB insert failed for project {project.project_id}", exc_info=True)
            raise VectorDBInsertError(project.project_id, str(e)) from e
        
        # RULE 7: Success path is implicit (no need to return True)
```

#### Step 3: Clean Up the Route & Add Global Handlers (Rule 1)
```python
# src/routes/nlp.py
import logging
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
from src.exceptions import RAGServiceError, ProjectNotFoundError

logger = logging.getLogger(__name__)
nlp_router = APIRouter(prefix="/api/v1/nlp", tags=["api_v1", "nlp"])

# RULE 1: Global Exception Handler (keeps routes clean)
@nlp_router.exception_handler(RAGServiceError)
async def rag_service_error_handler(request: Request, exc: RAGServiceError):
    # Log the error with full context
    logger.error(f"RAG Error: {exc.message}", exc_info=True)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: str, push_request: PushRequest):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)
    
    # RULE 7: Standard validation, not exception-based control flow
    if not project:
        raise ProjectNotFoundError(project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    # Let the controller do its work. If it fails, it raises an exception, 
    # and the global handler above catches it cleanly.
    nlp_controller.index_into_vector_db(
        project=project,
        chunks=await chunk_model.get_poject_chunks(project_id=project.id, page_no=1),
        do_reset=push_request.do_reset,
        chunks_ids=list(range(len(chunks)))
    )

    # RULE 2: Success path is clean and obvious
    return {"message": "Successfully indexed project", "project_id": project_id}
```

---

### 🏆 Final Verdict

**Current State:** The repository is an excellent **architectural blueprint** for a RAG application. It correctly separates concerns and avoids basic anti-patterns like using exceptions for normal control flow.

**Production Readiness:** **Low**. The error handling strategy relies on "silent failures" (returning `False`), generic HTTP 400 responses, and a lack of contextual logging. If this were deployed to production, debugging a failed Vector DB insertion or an LLM timeout would require guessing, as the root cause and stack trace are discarded.

**Recommendation:** Adopt the **Raise, Don't Return** pattern. Replace boolean returns with custom domain exceptions, log failures with `exc_info=True`, and use FastAPI's `@exception_handler` to map those exceptions to accurate HTTP status codes (404, 500, 502). This transforms the codebase from an "educational prototype" to a truly "production-ready" system.

### USER
how about if i use taskiq instead of celery in the link that i gave you what could be your point of view of error handeling and logging strategy

### ASSISTANT
Switching to **Taskiq** for background processing in a RAG (Retrieval-Augmented Generation) application is a **massive architectural upgrade**. Indexing documents, generating embeddings, and calling LLMs are inherently slow, resource-intensive, and prone to network hiccups. Doing this synchronously in a FastAPI route is a recipe for HTTP timeouts.

However, introducing Taskiq fundamentally changes the rules of error handling and logging. If you get it wrong, you create "zombie tasks" where the user thinks their document is indexed, but it silently failed in the background.

Here is my Staff Engineer’s point of view on how to design the **Error Handling and Logging Strategy** for `mini-rag` using **Taskiq**.

---

### 🚨 The 4 Critical Taskiq + RAG Challenges

1. **The "Silent Success" Trap:** If your `index_into_vector_db` function returns `False` or `None` on failure inside a Taskiq worker, **Taskiq marks the task as SUCCESS**. The user’s UI will show "Indexing Complete," but the Vector DB will be empty.
2. **Blind Retries:** If you just use `@broker.task(retries=3)`, Taskiq will retry *everything*. If the failure is due to an invalid API key or a corrupted PDF, retrying 3 times just wastes money and time.
3. **Lost Context:** When a background task crashes, a log that says `"Embedding failed"` is useless. You need to know *which* project, *which* user, and *which* chunk failed.
4. **Partial Batch Failures:** RAG processes documents in chunks. If chunk 45 out of 100 fails, do you fail the whole task, or skip the bad chunk and continue?

---

### ✅ The Production-Grade Taskiq Strategy for RAG

Here is exactly how I would architect the error handling and logging for this repository using Taskiq.

#### Step 1: Define RAG-Specific Domain Exceptions (Rule 5)
We need to distinguish between errors that should **retry** (transient) and errors that should **fail immediately** (terminal).

```python
# src/exceptions.py
class RAGTaskError(Exception):
    """Base exception for background RAG tasks."""
    def __init__(self, message: str, project_id: str, should_retry: bool = False):
        self.message = message
        self.project_id = project_id
        self.should_retry = should_retry
        super().__init__(self.message)

class EmbeddingRateLimitError(RAGTaskError):
    """Transient: LLM/Embedding API said 'slow down'. Retry with backoff."""
    def __init__(self, project_id: str, retry_after: int):
        super().__init__(f"Embedding rate limited. Retry after {retry_after}s", project_id, should_retry=True)
        self.retry_after = retry_after

class VectorDBConnectionError(RAGTaskError):
    """Transient: Qdrant/Chroma is temporarily unreachable. Retry."""
    def __init__(self, project_id: str, reason: str):
        super().__init__(f"Vector DB connection failed: {reason}", project_id, should_retry=True)

class InvalidDocumentError(RAGTaskError):
    """Terminal: Corrupted file or unsupported format. Do NOT retry."""
    def __init__(self, project_id: str, filename: str):
        super().__init__(f"Cannot process document: {filename}", project_id, should_retry=False)
```

#### Step 2: The Taskiq Worker (The Heart of the Strategy)
This is where Rules 2, 3, and 4 come alive. Notice how we handle partial failures and structured logging.

```python
# src/tasks.py
import logging
from taskiq import TaskiqMessage, TaskiqResult
from src.exceptions import RAGTaskError, EmbeddingRateLimitError, VectorDBConnectionError, InvalidDocumentError

logger = logging.getLogger(__name__)

# Custom middleware to inject structured logging context
class RAGLoggingMiddleware:
    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        # Attach task_id to the logger context for this specific execution
        logger.context = {"task_id": message.task_id, "project_id": message.args[0] if message.args else "unknown"}
        return message

broker.add_middleware(RAGLoggingMiddleware())

@broker.task
async def index_project_task(project_id: str, user_id: str, document_ids: list[str]):
    """
    Background task to chunk, embed, and index documents into the Vector DB.
    """
    logger.info(f"Starting indexing task for project {project_id}")
    
    try:
        # 1. Fetch project metadata
        project = await get_project(project_id)
        if not project:
            raise InvalidDocumentError(project_id, "Project not found")

        # 2. Process chunks (Handling Partial Failures)
        failed_chunks = []
        for doc_id in document_ids:
            try:
                await _process_single_document(project_id, doc_id)
            except InvalidDocumentError as e:
                # Terminal error for this specific doc: Log, skip, continue to next doc
                logger.error(f"Skipping document {doc_id}: {e.message}", exc_info=True)
                failed_chunks.append({"doc_id": doc_id, "error": e.message})
            except RAGTaskError as e:
                # If it's a transient error at the doc level, bubble it up to retry the whole task
                raise e

        # 3. Update Project Status in DB
        await update_project_status(project_id, status="COMPLETED", failed_chunks=failed_chunks)
        logger.info(f"Successfully completed indexing for project {project_id}")

    except RAGTaskError as e:
        # RULE 3 & 4: Log with full context and exc_info, then decide to retry or die
        logger.error(
            f"Task failed for project {project_id}: {e.message}",
            extra={"error_type": e.__class__.__name__, "should_retry": e.should_retry},
            exc_info=True
        )
        
        if e.should_retry:
            # Let the exception bubble up! Taskiq will catch it and retry based on decorator.
            raise e
        else:
            # Terminal error: Update DB to FAILED so the user knows. Do NOT re-raise.
            await update_project_status(project_id, status="FAILED", error_message=e.message)
            return # Task ends, marked as success by Taskiq (because we handled it), but DB says failed.
            
    except Exception as e:
        # RULE 1 & 3: Catch-all for truly unexpected errors (e.g., OutOfMemory, syntax error)
        logger.critical(f"UNEXPECTED CRASH in task for project {project_id}", exc_info=True)
        await update_project_status(project_id, status="FAILED", error_message="Internal system error")
        raise e # Let Taskiq know it crashed
```

#### Step 3: The FastAPI Route (Rule 1: Keep it Clean)
The HTTP layer no longer cares about the complex logic. It just kicks the task and returns a `202 Accepted`.

```python
# src/routes/nlp.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from src.tasks import index_project_task

nlp_router = APIRouter(prefix="/api/v1/nlp", tags=["nlp"])

@nlp_router.post("/index/push/{project_id}", status_code=202)
async def trigger_indexing(project_id: str, user_id: str = Depends(get_current_user)):
    """
    Triggers the background indexing task.
    Returns 202 Accepted immediately.
    """
    # 1. Validate project exists (Synchronous/Fast check)
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.status == "INDEXING":
        raise HTTPException(status_code=409, detail="Project is already being indexed")

    # 2. Update status to "INDEXING" immediately
    await update_project_status(project_id, status="INDEXING")

    # 3. Kick the Taskiq task
    # We pass the IDs, not the whole object, to keep the message queue payload small
    task_kicker = index_project_task.kicker()
    task_info = await task_kicker.kick(project_id, user_id, project.document_ids)

    # 4. Return the task ID so the frontend can poll for status
    return {
        "message": "Indexing started in background",
        "task_id": task_info.task_id,
        "project_id": project_id,
        "status_url": f"/api/v1/nlp/status/{project_id}"
    }
```

---

### 🏆 Why This Strategy is Production-Ready

| Feature | How This Strategy Solves It |
| :--- | :--- |
| **No Silent Failures** | The task either succeeds, updates the DB to `FAILED`, or raises an exception for Taskiq to retry. It never just returns `False`. |
| **Smart Retries** | By checking `e.should_retry`, we only retry transient issues (Rate Limits, DB timeouts). We immediately fail on bad data (`InvalidDocumentError`), saving API costs. |
| **Structured Logging** | The `RAGLoggingMiddleware` ensures every log line in the worker is tagged with `task_id` and `project_id`. You can search your logs (Datadog/ELK) for `project_id="xyz"` and see the entire lifecycle. |
| **Partial Failure Resilience** | The `for doc_id in document_ids` loop catches `InvalidDocumentError` per document. One bad PDF won't ruin the indexing of the other 99 good PDFs in the same batch. |
| **Frontend Feedback Loop** | The route returns a `task_id` and `status_url`. The frontend can poll this endpoint or use WebSockets to show a real progress bar or a specific error message to the user. |

### 💡 Senior Dev Advice for this Specific Repo

If you are modifying `bakrianoo/mini-rag` to use Taskiq, **do not pass large objects** (like the whole `Project` model or list of text chunks) into the `@broker.task` function. 

Taskiq serializes arguments (usually via JSON or MsgPack) to send them to Redis/RabbitMQ. Passing massive lists of text will bloat your message broker and cause serialization errors. 

**Always pass IDs:**
❌ `index_task.kick(project_object, list_of_1000_chunks)`  
✅ `index_task.kick(project_id="123", document_ids=["doc1", "doc2"])`

Let the Taskiq worker fetch the data it needs from the database or storage. This keeps your message queue lightning fast and your error handling robust.


# IV - How FastAPI Catches Child Exceptions

FastAPI uses **Python's exception inheritance**. When you register a handler for `RAGServiceError`, it automatically catches **all subclasses** of `RAGServiceError`.

### The Mechanism

```python
# Your exception hierarchy:
RAGServiceError (Base)
    ├── ProjectNotFoundError (Child)
    ├── VectorDBInsertError (Child)
    └── EmbeddingError (Child)

# When you register:
@nlp_router.exception_handler(RAGServiceError)
async def rag_service_error_handler(request, exc: RAGServiceError):
    ...
```

**FastAPI's logic:**
1. Code raises `VectorDBInsertError`
2. FastAPI checks: "Is `VectorDBInsertError` a subclass of `RAGServiceError`?"
3. **Yes** → Uses `rag_service_error_handler`
4. The handler receives the exception as `exc` (still a `VectorDBInsertError` instance)
5. `exc.message` and `exc.status_code` are accessed polymorphically

---

## Concrete Example

```python
# In your controller:
def index_into_vector_db(self, project_id: str, chunks: list):
    try:
        await self.qdrant_client.insert(...)
    except Exception as e:
        # Raises a CHILD exception
        raise VectorDBInsertError(project_id, str(e))

# In your route:
@nlp_router.post("/index/{project_id}")
async def index_project(project_id: str):
    # No try/except needed!
    controller.index_into_vector_db(project_id, chunks)
    return {"status": "success"}

# FastAPI automatically catches VectorDBInsertError and calls:
@nlp_router.exception_handler(RAGServiceError)
async def rag_service_error_handler(request, exc: RAGServiceError):
    # exc is actually a VectorDBInsertError instance
    # exc.status_code = 502
    # exc.message = "Failed to index project 'proj_123': Connection refused"
    
    return JSONResponse(
        status_code=exc.status_code,  # 502
        content={"error": exc.message}
    )
```

---

## Why This Works

| Python Feature | What It Does |
|----------------|--------------|
| **Inheritance** | `VectorDBInsertError` IS-A `RAGServiceError` |
| **Polymorphism** | Handler can access `.message` and `.status_code` on any child |
| **FastAPI's Resolution** | Checks `isinstance(exc, RAGServiceError)` → matches all children |

---

## The Power: One Handler, All Errors

```python
# All these raise different errors, but ONE handler catches them all:

raise ProjectNotFoundError("proj_123")      # → 404
raise VectorDBInsertError("proj_123", "...") # → 502
raise EmbeddingError("API timeout")          # → 502

# Handler receives the correct status_code and message for each:
@nlp_router.exception_handler(RAGServiceError)
async def rag_service_error_handler(request, exc: RAGServiceError):
    # exc.status_code is 404, 502, or 502 depending on which was raised
    # exc.message contains the specific error details
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
```

This is **DRY (Don't Repeat Yourself)**: You write the error handling logic **once**, and it works for all your domain exceptions.