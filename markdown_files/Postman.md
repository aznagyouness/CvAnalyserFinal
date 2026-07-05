
# I- 📮 Postman Inputs for Test Taskiq Router

## Base URL
```
http://localhost:8000
```

---

## 1️⃣ POST `/test-taskiq/queue` — Queue a Task

### Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/test-taskiq/queue`
- **Headers:**
  ```
  Content-Type: application/json
  ```
- **Body (raw JSON):**
  ```json
  {
    "text": "Hello Taskiq",
    "delay": 0
  }
  ```

### Expected Response (202 Accepted)
```json
{
  "task_id": "abc123def456...",
  "status": "queued",
  "message": "Task queued. Check status at /test-taskiq/status/abc123def456..."
}
```

### ✅ Verify
- [ ] Response status is `202`
- [ ] `task_id` is returned
- [ ] Copy `task_id` for endpoint #3

---

## 2️⃣ POST `/test-taskiq/queue-and-wait` — Queue + Wait

### Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/test-taskiq/queue-and-wait?timeout=10`
- **Headers:**
  ```
  Content-Type: application/json
  ```
- **Body (raw JSON):**
  ```json
  {
    "text": "Quick task",
    "delay": 2
  }
  ```

### Expected Response (200 OK)
```json
{
  "task_id": "xyz789...",
  "status": "SUCCESS",
  "result": {
    "status": "done",
    "task_id": "xyz789...",
    "text": "Quick task",
    "text_length": 10,
    "delay": 2.0,
    "message": "Processed text: 'Quick task'"
  },
  "error": null,
  "source": null
}
```

### ✅ Verify
- [ ] Response status is `200`
- [ ] `status` is `SUCCESS`
- [ ] Response time ≈ delay + processing time (~2-3 seconds)

---

## 3️⃣ GET `/test-taskiq/status/{task_id}` — Check Status

### Request
- **Method:** `GET`
- **URL:** `http://localhost:8000/test-taskiq/status/{task_id}`
- **Replace `{task_id}`** with the ID from endpoint #1

### Example URLs
```
http://localhost:8000/test-taskiq/status/abc123def456
http://localhost:8000/test-taskiq/status/5b1d81059f0c4f1b9f96c7f2f9d825d7
```

### Expected Response (200 OK) — Success
```json
{
  "task_id": "abc123def456...",
  "status": "SUCCESS",
  "result": {
    "status": "done",
    "task_id": "abc123def456...",
    "text": "Hello Taskiq",
    "text_length": 12,
    "delay": 0.0,
    "message": "Processed text: 'Hello Taskiq'"
  },
  "error": null,
  "source": "redis"
}
```

### Expected Response (200 OK) — Pending
```json
{
  "task_id": "pending-task-id",
  "status": "PENDING",
  "result": null,
  "error": null,
  "source": "postgres"
}
```

### ✅ Verify
- [ ] `source` is `"redis"` for recent tasks
- [ ] `source` is `"postgres"` for older tasks
- [ ] `status` transitions from `PENDING` → `SUCCESS`

---

## 4️⃣ POST `/test-taskiq/test-idempotency` — Test Duplicate Detection

### Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/test-taskiq/test-idempotency`
- **Headers:**
  ```
  Content-Type: application/json
  ```
- **Body (raw JSON):**
  ```json
  {
    "text": "Duplicate test",
    "delay": 0
  }
  ```

### Expected Response (200 OK)
```json
{
  "task1": {
    "task_id": "task1-id...",
    "status": "SUCCESS",
    "result": {
      "status": "done",
      "task_id": "task1-id...",
      "text": "Duplicate test",
      "text_length": 14,
      "delay": 0.0,
      "message": "Processed text: 'Duplicate test'"
    }
  },
  "task2": {
    "task_id": "task2-id...",
    "status": "SUCCESS",
    "result": {
      "status": "done",
      "task_id": "task2-id...",
      "text": "Duplicate test",
      "text_length": 14,
      "delay": 0.0,
      "message": "Processed text: 'Duplicate test'"
    },
    "note": "Should be skipped by idempotency middleware"
  },
  "idempotency_working": true
}
```

### ✅ Verify
- [ ] Both tasks return `SUCCESS`
- [ ] `idempotency_working` is `true`
- [ ] Worker logs show: `idempotency: skipping ... — already completed`

---

## 5️⃣ POST `/test-taskiq/queue-with-background` — BackgroundTasks Comparison

### Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/test-taskiq/queue-with-background`
- **Headers:**
  ```
  Content-Type: application/json
  ```
- **Body (raw JSON):**
  ```json
  {
    "text": "Background test",
    "delay": 0
  }
  ```

### Expected Response (202 Accepted)
```json
{
  "task_id": "background-task",
  "status": "queued",
  "message": "Task queued via FastAPI BackgroundTasks (no task_id available)"
}
```

### ✅ Verify
- [ ] Response status is `202`
- [ ] FastAPI logs show: `Background task queued: ...`
- [ ] **Note:** This is for comparison only — not recommended for production

---

## 6️⃣ POST `/test-taskiq/queue-failing` — Test Error Handling

### Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/test-taskiq/queue-failing`
- **Headers:**
  ```
  Content-Type: application/json
  ```
- **Body (raw JSON) — Test Failure:**
  ```json
  {
    "should_fail": true,
    "error_message": "Testing error handling in Taskiq!"
  }
  ```
- **Body (raw JSON) — Test Success:**
  ```json
  {
    "should_fail": false,
    "error_message": "This won't be used!"
  }
  ```

### Expected Response (202 Accepted)
```json
{
  "task_id": "failing-task-id-123...",
  "status": "queued",
  "message": "Failing task queued. Check status at /test-taskiq/status/failing-task-id-123..."
}
```

### ✅ Verify
- [ ] Response status is `202`
- [ ] If `should_fail=true`, then `GET /test-taskiq/status/{task_id}` returns:
  ```json
  {
    "task_id": "...",
    "status": "FAILED",
    "error": "ValueError('Testing error handling in Taskiq! (task_id: ...)')"
  }
  ```
- [ ] If `should_fail=false`, then `GET /test-taskiq/status/{task_id}` returns:
  ```json
  {
    "task_id": "...",
    "status": "SUCCESS",
    "result": {
      "status": "done",
      "task_id": "...",
      "message": "Task completed without failure"
    }
  }
  ```

---

## 📊 Quick Reference Table

| Endpoint | Method | URL | Body | Query Params |
|----------|--------|-----|------|--------------|
| Queue Task | POST | `/test-taskiq/queue` | `{"text": "...", "delay": 0}` | None |
| Queue + Wait | POST | `/test-taskiq/queue-and-wait` | `{"text": "...", "delay": 2}` | `?timeout=10` |
| Check Status | GET | `/test-taskiq/status/{task_id}` | None | None |
| Test Idempotency | POST | `/test-taskiq/test-idempotency` | `{"text": "Duplicate test"}` | None |
| BackgroundTasks | POST | `/test-taskiq/queue-with-background` | `{"text": "..."}` | None |
| Queue Failing Task | POST | `/test-taskiq/queue-failing` | `{"should_fail": true, "error_message": "..."}` | None |

---

## 🧪 Complete Test Flow

### Step 1: Queue a Task
```bash
POST http://localhost:8000/test-taskiq/queue
{
  "text": "Test message",
  "delay": 0
}
```
**Copy the `task_id` from response**

### Step 2: Check Status
```bash
GET http://localhost:8000/test-taskiq/status/{paste_task_id_here}
```
**Verify `status` transitions from `PENDING` → `SUCCESS`**

### Step 3: Test Idempotency
```bash
POST http://localhost:8000/test-taskiq/test-idempotency
{
  "text": "Duplicate test",
  "delay": 0
}
```
**Verify `idempotency_working: true`**

### Step 4: Test Queue-and-Wait
```bash
POST http://localhost:8000/test-taskiq/queue-and-wait?timeout=10
{
  "text": "Quick task",
  "delay": 2
}
```
**Verify response time ≈ 2-3 seconds**

---

## 🎯 Common Test Scenarios

### Scenario 1: Verify Basic Flow
1. Queue task → Get `task_id`
2. Check status → See `PENDING`
3. Wait 2 seconds → Check status → See `SUCCESS`

### Scenario 2: Verify Idempotency
1. Test idempotency endpoint
2. Check worker logs for skip message
3. Verify only 1 execution in PostgreSQL

### Scenario 3: Verify Timeout Handling
1. Queue-and-wait with `delay=5` and `timeout=3`
2. Should get `408 Request Timeout`

### Scenario 4: Verify BackgroundTasks
1. Queue with background endpoint
2. Check FastAPI logs (not worker logs)
3. Note: No persistence, no retries

**All inputs ready to copy-paste into Postman!** 🚀


----
----





# II - 📮 Postman Inputs for Task Result Endpoints (with service folder)

## Base URL
```
http://localhost:8000
```

---

## 1️⃣ GET `/task-results/by-task-id/{task_id}` — Hybrid Retrieval

### Request
- **Method:** `GET`
- **URL:** `http://localhost:8000/task-results/by-task-id/{task_id}`
- **Replace `{task_id}`** with actual task ID from queue endpoint

### Example URLs
```
http://localhost:8000/task-results/by-task-id/5b1d81059f0c4f1b9f96c7f2f9d825d7
http://localhost:8000/task-results/by-task-id/abc123def456
```

### Expected Response (200 OK) — Redis Hit (Recent Task)
```json
{
  "task_id": "5b1d81059f0c4f1b9f96c7f2f9d825d7",
  "status": "SUCCESS",
  "result": {
    "status": "done",
    "task_id": "5b1d81059f0c4f1b9f96c7f2f9d825d7",
    "text": "Hello Taskiq",
    "text_length": 12,
    "delay": 0.0,
    "message": "Processed text: 'Hello Taskiq'"
  },
  "error": null,
  "source": "redis"
}
```

**Response Headers:**
```
Cache-Control: public, max-age=3600
```

### Expected Response (200 OK) — PostgreSQL Fallback (Old Task)
```json
{
  "task_id": "old-task-id-123",
  "task_name": "src.tasks.test_taskiq:my_task2",
  "status": "SUCCESS",
  "result": {
    "status": "done",
    "text": "Old task"
  },
  "error": null,
  "enqueued_at": "2026-06-29T10:30:00+00:00",
  "completed_at": "2026-06-29T10:30:02+00:00",
  "source": "postgres"
}
```

**Response Headers:**
```
Cache-Control: public, max-age=3600
```

### Expected Response (200 OK) — Pending Task
```json
{
  "task_id": "pending-task-id",
  "status": "PENDING"
}
```

**Response Headers:**
```
Cache-Control: no-store
```

### ✅ Verify
- [ ] `source` is `"redis"` for recent tasks (< 1 hour)
- [ ] `source` is `"postgres"` for older tasks
- [ ] `Cache-Control` header is set correctly
- [ ] Response time: Redis hit < 10ms, PG fallback ~50ms

---

## 2️⃣ POST `/task-results/by-input` — Guaranteed Linkage

### Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/task-results/by-input`
- **Headers:**
  ```
  Content-Type: application/json
  ```

### Body Examples

#### Example 1: Simple Task (my_task)
```json
{
  "task_name": "src.tasks.test_taskiq:my_task",
  "args": [],
  "kwargs": {}
}
```

#### Example 2: Task with Text Parameter (my_task2)
```json
{
  "task_name": "src.tasks.test_taskiq:my_task2",
  "args": [],
  "kwargs": {
    "text": "Hello Taskiq",
    "delay": 0.0
  }
}
```
**NB:** `kwargs`the middleware stored the delay value as a float (30.0), so not use in Postman an integer (30) --> {"detail": "No successful execution found for this input"}  -->  HTTPException we made.

#### Example 3: Complex Task (complex_task)
```json
{
  "task_name": "src.tasks.test_taskiq:complex_task",
  "args": [],
  "kwargs": {
    "user_id": 123,
    "file_id": "abc123",
    "options": {
      "mode": "fast",
      "retry": true
    }
  }
}
```

#### Example 4: Task with Positional Args
```json
{
  "task_name": "src.tasks.test_taskiq:my_task2",
  "args": ["Hello World"],
  "kwargs": {
    "delay": 2.0
  }
}
```

### Expected Response (200 OK) — Success
```json
{
  "task_id": "5b1d81059f0c4f1b9f96c7f2f9d825d7",
  "task_name": "src.tasks.test_taskiq:my_task2",
  "task_hash": "968020836037abcdef1234567890abcdef1234567890abcdef1234567890ab",
  "input": {
    "args": [],
    "kwargs": {
      "text": "Hello Taskiq",
      "delay": 0.0
    }
  },
  "status": "SUCCESS",
  "result": {
    "status": "done",
    "task_id": "5b1d81059f0c4f1b9f96c7f2f9d825d7",
    "text": "Hello Taskiq",
    "text_length": 12,
    "delay": 0.0,
    "message": "Processed text: 'Hello Taskiq'"
  },
  "enqueued_at": "2026-06-29T12:34:59+00:00",
  "completed_at": "2026-06-29T12:35:01+00:00",
  "linkage_verified": true
}
```

### Expected Response (404 Not Found) — No Matching Task
```json
{
  "detail": "No successful execution found for this input"
}
```

### ✅ Verify
- [ ] `linkage_verified` is `true`
- [ ] `task_hash` matches the hash of input
- [ ] `input.kwargs` matches what you sent
- [ ] Returns most recent SUCCESS execution

---

## 3️⃣ POST `/task-results/all-executions-by-input` — Debug All Attempts

### Request
- **Method:** `POST`
- **URL:** `http://localhost:8000/task-results/all-executions-by-input`
- **Headers:**
  ```
  Content-Type: application/json
  ```

### Body Examples

#### Example 1: Check All Attempts for a Task
```json
{
  "task_name": "src.tasks.test_taskiq:my_task2",
  "args": [],
  "kwargs": {
    "text": "Duplicate test",
    "delay": 0.0
  }
}
```

#### Example 2: Check Failed Task Retries
```json
{
  "task_name": "src.tasks.test_taskiq:failing_task",
  "args": [],
  "kwargs": {
    "should_fail": true,
    "error_message": "Test error"
  }
}
```

### Expected Response (200 OK) — Single Execution
```json
{
  "count": 1,
  "executions": [
    {
      "task_id": "5b1d81059f0c4f1b9f96c7f2f9d825d7",
      "task_name": "src.tasks.test_taskiq:my_task2",
      "status": "SUCCESS",
      "result": {
        "status": "done",
        "text": "Duplicate test"
      },
      "error": null,
      "enqueued_at": "2026-06-29T12:34:59+00:00",
      "completed_at": "2026-06-29T12:35:01+00:00"
    }
  ]
}
```
Get ALL executions of the same task signature (for debugging).
        [
           {"task_id": "...", "status": "SUCCESS", "result": "...", ...},
           {"task_id": "...", "status": "FAILED", "error": "...", ...},
           {"task_id": "...", "status": "SUCCESS", "result": "...", ...}
        ]
        if no executions found, return [] if 1 success you get 1 success
        if 1 failed you get 1 failed
        it not include duplication .

### Expected Response (200 OK) — Multiple Attempts (Retries + Idempotency)
```json
{
  "count": 4,
  "executions": [
    {
      "task_id": "attempt-4-id",
      "task_name": "src.tasks.test_taskiq:failing_task",
      "status": "FAILED",
      "result": null,
      "error": "ValueError('Test error (task_id: attempt-4-id)')",
      "enqueued_at": "2026-06-29T12:40:00+00:00",
      "completed_at": "2026-06-29T12:40:01+00:00"
    },
    {
      "task_id": "attempt-3-id",
      "task_name": "src.tasks.test_taskiq:failing_task",
      "status": "FAILED",
      "result": null,
      "error": "ValueError('Test error (task_id: attempt-3-id)')",
      "enqueued_at": "2026-06-29T12:39:55+00:00",
      "completed_at": "2026-06-29T12:39:56+00:00"
    },
    {
      "task_id": "attempt-2-id",
      "task_name": "src.tasks.test_taskiq:failing_task",
      "status": "FAILED",
      "result": null,
      "error": "ValueError('Test error (task_id: attempt-2-id)')",
      "enqueued_at": "2026-06-29T12:39:50+00:00",
      "completed_at": "2026-06-29T12:39:51+00:00"
    },
    {
      "task_id": "attempt-1-id",
      "task_name": "src.tasks.test_taskiq:failing_task",
      "status": "FAILED",
      "result": null,
      "error": "ValueError('Test error (task_id: attempt-1-id)')",
      "enqueued_at": "2026-06-29T12:39:45+00:00",
      "completed_at": "2026-06-29T12:39:46+00:00"
    }
  ]
}
```

### ✅ Verify
- [ ] `count` matches number of executions
- [ ] Executions ordered by `enqueued_at` DESC (newest first)
- [ ] Can see retry attempts (multiple FAILED with same input)
- [ ] Can see idempotency skips (if logged)

---

## 📊 Quick Reference Table

| Endpoint | Method | URL | Body | Use Case |
|----------|--------|-----|------|----------|
| **By Task ID** | GET | `/task-results/by-task-id/{task_id}` | None | Check specific task status |
| **By Input** | POST | `/task-results/by-input` | `{"task_name": "...", "args": [], "kwargs": {...}}` | Find result by input (guaranteed linkage) |
| **All Executions** | POST | `/task-results/all-executions-by-input` | `{"task_name": "...", "args": [], "kwargs": {...}}` | Debug retries, see all attempts |

---

## 🧪 Complete Test Flow

### Step 1: Queue a Task
```bash
POST /test-taskiq/queue
{
  "text": "Test message",
  "delay": 0
}
```
**Response:**
```json
{
  "task_id": "abc123...",
  "status": "queued"
}
```

### Step 2: Check Status by Task ID
```bash
GET /task-results/by-task-id/abc123...
```
**Response:**
```json
{
  "task_id": "abc123...",
  "status": "SUCCESS",
  "result": {...},
  "source": "redis"
}
```

### Step 3: Find by Input (Alternative)
```bash
POST /task-results/by-input
{
  "task_name": "src.tasks.test_taskiq:my_task2",
  "args": [],
  "kwargs": {
    "text": "Test message",
    "delay": 0.0
  }
}
```
**Response:**
```json
{
  "task_id": "abc123...",
  "status": "SUCCESS",
  "linkage_verified": true
}
```

### Step 4: Debug All Attempts
```bash
POST /task-results/all-executions-by-input
{
  "task_name": "src.tasks.test_taskiq:my_task2",
  "args": [],
  "kwargs": {
    "text": "Test message",
    "delay": 0.0
  }
}
```
**Response:**
```json
{
  "count": 1,
  "executions": [...]
}
```

---

## 🎯 Common Test Scenarios

### Scenario 1: Verify Idempotency
1. Queue same task twice via `/test-taskiq/test-idempotency`
2. Check `/task-results/all-executions-by-input`
3. Should see only 1 SUCCESS execution (second was skipped)

### Scenario 2: Verify Retry Logic
1. Queue failing task: `POST /test-taskiq/queue` with `should_fail=true`
2. Wait for retries
3. Check `/task-results/all-executions-by-input`
4. Should see 3 FAILED executions (default retry count)

### Scenario 3: Verify Redis vs PostgreSQL
1. Queue task and wait for completion
2. Immediately check `/task-results/by-task-id/{task_id}` → `source: "redis"`
3. Wait 1 hour (or manually delete from Redis)
4. Check again → `source: "postgres"`

**All inputs ready to copy-paste into Postman!** 🚀