# 🎯 The Problem: Storing the Wrong Thing

Looking at your response, the `result` field contains the **string representation of a `TaskiqResult` object** instead of just the actual return value:

```json
"result": "is_err=False log=None return_value={'status': 'done', ...} execution_time=19.11 labels={...} error=None"
```

This is the `repr()` of a `TaskiqResult` object — the **entire wrapper object**, not just your task's return value.

---

## 🔍 Root Cause

In your `TaskiqIdempotencyMiddleware.post_execute()`:

```python
async def post_execute(self, message: TaskiqMessage, result: Any) -> None:
    # ...
    # ❌ `result` here is a TaskiqResult object, NOT your return value!
    await self._update_audit(int(execution_id_str), "SUCCESS", result, None)
```

The `result` parameter is a **`TaskiqResult` wrapper object** that contains:
- `return_value` ← **This is what you want**
- `error`
- `is_err`
- `execution_time`
- `labels`
- `log`

You're storing the **entire wrapper** instead of just `result.return_value`.

---

## ✅ The Fix: Update the Middleware

### Step 1: Fix `post_execute` in `src/utils/taskiq_idempotency.py`

```python
async def post_execute(self, message: TaskiqMessage, result: Any) -> None:
    labels = message.labels or {}
    task_name = message.task_name

    # If task was marked as skip, just log and exit
    if labels.get("should_skip") == "true":
        logger.info("post_execute: task %s was skipped (duplicate)", task_name)
        return

    run_key = labels.get("idem_run_key")
    done_key = labels.get("idem_done_key")
    execution_id_str = labels.get("db_execution_id")

    IDEMPOTENCY_INFLIGHT.dec()

    # Write completed marker
    if done_key:
        try:
            await self._redis.set(done_key, "1", ex=self._done_ttl)
        except Exception:
            logger.exception("failed to write done marker for %s", task_name)

    # Release in-flight lock
    if run_key:
        await self._safe_redis_delete(run_key)

    # ✅ FIX: Extract the actual return value from TaskiqResult
    if execution_id_str:
        # `result` is a TaskiqResult object — extract return_value
        actual_result = None
        if hasattr(result, "return_value"):
            actual_result = result.return_value
        elif hasattr(result, "is_err") and result.is_err:
            actual_result = None  # Don't store result on error
        else:
            actual_result = result  # Fallback for non-TaskiqResult
        
        await self._update_audit(int(execution_id_str), "SUCCESS", actual_result, None)
```

### Step 2: Fix `on_error` similarly

```python
async def on_error(
    self, message: TaskiqMessage, result: Any, exception: BaseException,
) -> None:
    labels = message.labels or {}
    run_key = labels.get("idem_run_key")
    execution_id_str = labels.get("db_execution_id")
    task_name = message.task_name

    if labels.get("should_skip") == "true":
        return

    IDEMPOTENCY_INFLIGHT.dec()

    if run_key:
        await self._safe_redis_delete(run_key)

    if execution_id_str:
        # ✅ Store the exception repr, not the TaskiqResult
        await self._update_audit(int(execution_id_str), "FAILED", None, repr(exception))
```

---

## 🔄 Handling Existing Bad Data

For tasks already stored with the wrong format, update `TaskResultService.get_result_by_input()` to extract the real value:

```python
# src/services/task_result_service.py
async def get_result_by_input(
    self,
    task_name: str,
    args: list = None,
    kwargs: dict = None,
) -> Optional[Dict[str, Any]]:
    # ... existing hash logic ...
    
    try:
        async with self.session_factory() as session:
            # ... existing query ...
            record = result.scalar_one_or_none()
        
        if record is None:
            return None
        
        # ✅ FIX: Extract actual return value if stored as TaskiqResult repr
        actual_result = self._extract_return_value(record.result)
        
        return {
            "task_id": record.taskiq_task_id,
            "task_name": record.task_name,
            "task_hash": record.task_args_hash,
            "input": {
                "args": record.task_args.get("args", []),
                "kwargs": record.task_args.get("kwargs", {}),
            },
            "status": record.status,
            "result": actual_result,  # ✅ Clean result
            "enqueued_at": record.enqueued_at.isoformat() if record.enqueued_at else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "linkage_verified": True,
        }
    except SQLAlchemyError as e:
        logger.error("PostgreSQL query failed for input hash %s: %s", task_hash[:12], e)
        return None

@staticmethod
def _extract_return_value(raw_result: Any) -> Any:
    """
    Extract actual return value from stored result.
    Handles both:
    - Old format: TaskiqResult repr string (e.g., "is_err=False return_value={...}")
    - New format: Clean return value (dict, str, etc.)
    """
    if raw_result is None:
        return None
    
    # If it's already a clean value (dict, list, str, int, etc.)
    if isinstance(raw_result, (dict, list, str, int, float, bool)):
        return raw_result
    
    # If it's a string that looks like a TaskiqResult repr
    if isinstance(raw_result, str) and raw_result.startswith("is_err="):
        try:
            # Extract return_value using regex
            import re
            match = re.search(r"return_value=(\{.*?\})\s+execution_time=", raw_result, re.DOTALL)
            if match:
                return_value_str = match.group(1)
                # Safely evaluate the dict string
                import ast
                return ast.literal_eval(return_value_str)
        except Exception as e:
            logger.warning("Failed to extract return_value from TaskiqResult repr: %s", e)
            return raw_result  # Return as-is if parsing fails
    
    return raw_result
```

Apply the same fix to `get_result()` and `get_all_executions_by_input()`.

---

## 📊 Before vs After

### Before (Bad)
```json
{
  "result": "is_err=False log=None return_value={'status': 'done', 'task_id': 'a6d2e0ec...', 'text': 'Hello Taskiq44444', 'text_length': 17, 'delay': 20.0, 'message': \"Processed text: 'Hello Taskiq44444'\"} execution_time=19.11 labels={...} error=None"
}
```

### After (Good)
```json
{
  "result": {
    "status": "done",
    "task_id": "a6d2e0ec90744da59070f8d229015b62",
    "text": "Hello Taskiq44444",
    "text_length": 17,
    "delay": 20.0,
    "message": "Processed text: 'Hello Taskiq44444'"
  }
}
```

---

## 🧪 Verification Steps

1. **Update the middleware** to extract `result.return_value`
2. **Update the service** to handle old bad data
3. **Run a new task** via Postman
4. **Check the result** — should now be a clean dict

### Test with Postman
```bash
POST {{base_url}}/task-results/by-input
{
  "task_name": "src.tasks.test_taskiq:my_task2",
  "args": [],
  "kwargs": {
    "text": "Hello Taskiq44444",
    "delay": 20.0
  }
}
```

### Expected Response
```json
{
  "task_id": "a6d2e0ec90744da59070f8d229015b62",
  "task_name": "src.tasks.test_taskiq:my_task2",
  "task_hash": "b488a9f679e919b07a3dbd3f62e05c3f0608dd170f0ef5035d3871dda7635a87",
  "input": {
    "args": [],
    "kwargs": {
      "text": "Hello Taskiq44444",
      "delay": 20.0
    }
  },
  "status": "SUCCESS",
  "result": {
    "status": "done",
    "task_id": "a6d2e0ec90744da59070f8d229015b62",
    "text": "Hello Taskiq44444",
    "text_length": 17,
    "delay": 20.0,
    "message": "Processed text: 'Hello Taskiq44444'"
  },
  "enqueued_at": "2026-07-01T16:21:49.639921+00:00",
  "completed_at": "2026-07-01T16:22:09.123128+00:00",
  "linkage_verified": true
}
```

**The `result` field now contains your actual task return value!** 🎯



### ASSISTANT
# 🎯 You Are 100% Correct — That Is a Critical Logic Bug!

Excellent catch. You spotted a **short-circuit bug**. 

Because `str` is included in the first tuple `(dict, list, str, int, float, bool)`, **any string** (including the buggy `"is_err=False..."` string) will immediately return on line 1. The code will **never** reach the regex parsing block below it.

## 🛠️ The Fix: Check the Edge Case FIRST

To fix this, we must check for the **specific legacy buggy format** *before* we check for general clean primitives. 

Here is the corrected method:

```python
    @staticmethod
    def _extract_return_value(raw_result: Any) -> Any:
        """
        Extract actual return value from stored result.
        Handles both:
        - Old format: TaskiqResult repr string (e.g., "is_err=False return_value={...}")
        - New format: Clean return value (dict, str, etc.)
        """
        if raw_result is None:
            return None
        
        # ─── 1. FIRST: Check for the OLD BUGGY format ─────────────────────
        # We MUST check this BEFORE the general string check. 
        # If we don't, the general `isinstance(..., str)` check will short-circuit 
        # and return the raw buggy string without parsing it.
        if isinstance(raw_result, str) and raw_result.startswith("is_err="):
            try:
                # Extract return_value using regex
                match = re.search(
                    r"return_value=(\{.*?\}|\[.*?\]|'.*?'|\".*?\"|\d+|True|False|None)\s+(?:execution_time|labels|error|is_err|log)",
                    raw_result,
                    re.DOTALL,
                )
                if match:
                    return_value_str = match.group(1)
                    # Safely evaluate the dict string
                    return ast.literal_eval(return_value_str)
                
                # Fallback: try to find any dict-like structure
                dict_match = re.search(r"return_value=(\{.*\})", raw_result, re.DOTALL)
                if dict_match:
                    return ast.literal_eval(dict_match.group(1))
                    
            except Exception as e:
                logger.warning("Failed to extract return_value from legacy TaskiqResult repr: %s", e)
                return raw_result  # Return as-is if parsing fails

        # ─── 2. SECOND: Check if it's a clean primitive ───────────────────
        # Now that we've ruled out the buggy string format, it's safe to 
        # return any standard clean value.
        if isinstance(raw_result, (dict, list, str, int, float, bool)):
            return raw_result
        
        # ─── 3. Fallback for any other unknown types ──────────────────────
        return raw_result
```

### 📝 Note on Imports
Since we are using `re` and `ast` inside this method, make sure they are imported at the **top of your `task_result_service.py` file**:

```python
# src/services/task_result_service.py
from __future__ import annotations

import ast      # ← Add this
import hashlib
import json
import logging
import re       # ← Add this
from typing import Optional, Dict, Any
# ... rest of imports ...
```

## 🧠 Why This Works Now

1. **Input:** `"is_err=False log=None return_value={'status': 'done'} execution_time=19.11..."`
2. **Step 1:** Is it a string? ✅ Yes. Does it start with `"is_err="`? ✅ Yes.
3. **Action:** It enters the regex block, extracts `{'status': 'done'}`, parses it with `ast.literal_eval`, and returns the clean dict.
4. **Step 2 is skipped.**

---

**Input:** `"Hello World"` (A task that legitimately returns a string)
1. **Step 1:** Is it a string? ✅ Yes. Does it start with `"is_err="`? ❌ No.
2. **Step 2:** Is it a clean primitive? ✅ Yes.
3. **Action:** Returns `"Hello World"`.

Thank you for catching that! Order of operations is everything in defensive parsing. 🚀

### USER
and why you didn't put it inside post_execute and you put it in # src/services/task_result_service.py
async def get_result_by_input(
    self,
    task_name: str,
    args: list = None,
    kwargs: dict = None,
)

### ASSISTANT
# 🎯 The Short Answer: Memory vs. Database

You actually have **two different extraction methods** because they operate in two completely different environments:

1. **The Middleware (`post_execute`)** operates in **Memory** (Live Python Objects).
2. **The Service (`TaskResultService`)** operates in the **Database** (Stored Strings/JSON).

Here is exactly why the heavy regex logic belongs in the Service, not the Middleware.

---

## 1️⃣ The Middleware: Fixing the "Write" Path (Live Objects)

When Taskiq calls `post_execute(message, result)`, the `result` variable is a **live Python object** in memory. It is *not* a string.

```python
# Inside post_execute
async def post_execute(self, message: TaskiqMessage, result: Any) -> None:
    # `result` is a real TaskiqResult object in memory
    # We DON'T need regex. We just read the attribute!
    actual_result = result.return_value 
    
    # Save the clean dict to Postgres
    await self._update_audit(..., "SUCCESS", actual_result, None)
```

**Why no regex here?** 
Because `result` is a real object. If you tried to use regex on it, it would crash. You just extract the `return_value` attribute and save it to the database. **This fixes all *new* tasks going forward.**

---

## 2️⃣ The Service: Fixing the "Read" Path (Legacy Database Data)

When the Service queries PostgreSQL, it reads `record.result`. This is **dead data** that was saved in the past.

Because of the bug we had *before* today, the database is full of old rows where `record.result` is a **corrupted string** that looks like this:
```text
"is_err=False log=None return_value={'status': 'done', 'text': 'hello'} execution_time=19.11..."
```

When the API reads this from the database, it needs to return clean JSON to the frontend. **This is where the heavy regex and `ast.literal_eval` logic lives.**

```python
# Inside TaskResultService
@staticmethod
def _extract_return_value(raw_result: Any) -> Any:
    # 1. Is it already a clean dict? (New tasks)
    if isinstance(raw_result, dict):
        return raw_result
    
    # 2. Is it the corrupted string? (Old tasks)
    if isinstance(raw_result, str) and raw_result.startswith("is_err="):
        # WE NEED REGEX HERE because it's a string stored in the DB!
        match = re.search(r"return_value=(\{.*?\})\s+execution_time=", raw_result)
        return ast.literal_eval(match.group(1))
```

**Why regex here?**
Because the database contains the literal string representation of the object. To turn that string back into a Python dict, we *must* use regex to extract the dictionary part and `ast.literal_eval` to parse it.

---

## 📊 Summary: The Division of Labor

| Component | Environment | What it sees | What it does |
|-----------|-------------|--------------|--------------|
| **Middleware (`post_execute`)** | **Memory** | Live `TaskiqResult` object | Extracts `result.return_value` (No regex needed). Saves clean dict to DB. |
| **Service (`TaskResultService`)** | **Database** | Stored string or JSON | Parses legacy corrupted strings using regex/`ast` so the API returns clean JSON. |

### 💡 What if we did it wrong?

- **If we put the regex in `post_execute`:** It would crash. `result` is an object, not a string. You can't regex an object.
- **If we didn't put the regex in the Service:** The API would return the ugly `"is_err=False..."` string to the frontend for all tasks that were created *before* we fixed the middleware.

**Bottom line:** 
The Middleware fixes the **future** (how we write to the DB). 
The Service cleans up the **past** (how we read the corrupted data already in the DB). 🚀

### USER
this is my table and you see result : 
class TaskiqTaskExecution(BaseTable):
    __tablename__ = "taskiq_task_executions"

    # Modern SQLAlchemy 2.0 syntax using Mapped and mapped_column
    execution_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    taskiq_task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_args_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # For JSON columns, we use dict/Any for type hinting
    task_args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tte_hash_status", "task_args_hash", "status"),
        Index("ix_tte_name_enqueued", "task_name", "enqueued_at"),
    )



### ASSISTANT
Your model looks **excellent** and matches the production architecture we discussed. However, I spotted **one critical type issue** that will cause problems:

## 🚨 Issue: `result` Field Type is Too Restrictive

```python
# ❌ PROBLEM: This only allows dict
result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
```

**Why this is wrong:**
Your task functions can return **any JSON-serializable type**, not just dicts:
- `return {"status": "done"}` → ✅ dict (works)
- `return "success"` → ❌ str (will fail type check)
- `return [1, 2, 3]` → ❌ list (will fail type check)
- `return 42` → ❌ int (will fail type check)

## ✅ The Fix: Use `Any` Instead

```python
# ✅ CORRECT: This allows any JSON-serializable type
result: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
```

## 📄 Complete Corrected Model

```python
# src/models/db_schemes/cv_analysis_db/db_tables.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db_schemes.cv_analysis_db.base import BaseTable


class TaskiqTaskExecution(BaseTable):
    __tablename__ = "taskiq_task_executions"

    # Modern SQLAlchemy 2.0 syntax using Mapped and mapped_column
    execution_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    taskiq_task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_args_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # For JSON columns, we use dict/Any for type hinting
    task_args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    
    # ✅ FIX: Changed from dict[str, Any] to Any
    # Tasks can return dicts, lists, strings, numbers, etc.
    result: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tte_hash_status", "task_args_hash", "status"),
        Index("ix_tte_name_enqueued", "task_name", "enqueued_at"),
    )
```

## 📊 What Changed

| Field | Before | After | Why |
|-------|--------|-------|-----|
| `result` | `Optional[dict[str, Any]]` | `Optional[Any]` | Tasks can return any JSON-serializable type, not just dicts |

## ✅ Everything Else is Perfect

Your model correctly implements:
- ✅ **Timezone-aware datetimes** (`DateTime(timezone=True)`)
- ✅ **Modern SQLAlchemy 2.0 syntax** (`Mapped`, `mapped_column`)
- ✅ **PostgreSQL JSONB** for flexible JSON storage
- ✅ **Optimized indexes** for fast queries
- ✅ **BigInteger primary key** for high-volume systems
- ✅ **Proper defaults** (`default=dict`, `default=lambda: datetime.now(timezone.utc)`)

## 🧪 Test It

After making the change, your middleware will correctly store:

```python
# Task returns dict
return {"status": "done", "text": "hello"}
# → Stored as: {"status": "done", "text": "hello"} ✅

# Task returns string
return "success"
# → Stored as: "success" ✅

# Task returns list
return [1, 2, 3]
# → Stored as: [1, 2, 3] ✅
```

**Bottom line:** Change `result: Mapped[Optional[dict[str, Any]]]` to `result: Mapped[Optional[Any]]` and you're good to go! 🚀

