# 🚀 The Ultimate Guide to RPM Management in Generative AI

Welcome to the definitive architectural blueprint for managing **Requests Per Minute (RPM)** in production-grade RAG and Chatbot systems. This guide documents the evolution of rate-limiting strategies, from local workarounds to the **"Final Boss" Hybrid Strategy**.

---

## 🏛️ 1. The Evolution of the Shield

### **Level 1: The Local Workaround (`AsyncLimiter`)**
Often found inside provider classes (e.g., `qwen_model.py`), this is a limiter living inside the function code itself.

*   **The Logic**: `self.rpm_limiter = AsyncLimiter(10, 60)`
*   **The Fatal Flaw**: It is **isolated**. If you scale to 4 worker processes, each worker is "blind" to the others. 

*   **The Math**: 
    - Worker #1 says: "I'm allowed 10 requests. Sending 10..." 
    - Worker #2 says: "I'm allowed 10 requests. Sending 10..." 
    - Worker #3 says: "I'm allowed 10 requests. Sending 10..." 
    - Worker #4 says: "I'm allowed 10 requests. Sending 10..." 
    - **Total sent to LLM Provider**: **40 RPM**. 
    - **Outcome**: **CRASH**. Your LLM Provider sees 40 requests in one minute, identifies you've exceeded the 10 RPM limit, and blocks your API Key. Your application starts returning `429 Too Many Requests` errors for every user.

*   **Verdict**: ❌ **Student Grade.** Avoid in multi-worker production environments.

### **Level 2: The Front-Door Guard (`SlowAPI`)**
A FastAPI middleware that counts requests per minute per IP address.

*   **The Logic**: `@limiter.limit("5/minute")`
*   **The Strength**: Protects your server from DDoS and spamming by a single user.
*   **The Fatal Flaw**: It doesn't protect your **Global Wallet**. If 1,000 "good" users each send 1 request, `SlowAPI` lets them all through. 

*   **The Math**: 
    - User #1 (IP: 1.1.1.1) sends 5 requests. (Allowed ✅)
    - User #2 (IP: 2.2.2.2) sends 5 requests. (Allowed ✅)
    - User #100 sends 5 requests. (Allowed ✅)
    - **Total sent to LLM Provider**: **500 RPM**. 
    - **Outcome**: **CRASH**. SlowAPI protected your server from one bad user, but it failed to protect your API Key from the "Thundering Herd" of many good users. Your provider blocks your key.

*   **Verdict**: 🛡️ **Security Essential.** Use it to protect the server, but not the budget.

### **Level 3: The Infrastructure Commander (Taskiq `rate_limit`)**
A global policy enforced at the task queue level using Redis as the "Single Source of Truth."

*   **The Logic**: `@broker.task(rate_limit="50/m")`
*   **The Strength**: Total visibility across all workers. It turns a "Thundering Herd" of requests into a disciplined, unbreakable stream. 

*   **The Math**: 
    - 100 Users each send 1 indexing task at the same time.
    - **Redis Counter** tracks exactly 50 slots per minute.
    - Worker #1 pulls 25 tasks; Worker #2 pulls 25 tasks.
    - **Total sent to LLM Provider**: **Exactly 50 RPM**. 
    - **Outcome**: **STABILITY**. The first 50 tasks finish in Minute 1. The remaining 50 wait automatically in the RabbitMQ queue and finish in Minute 2. No 429s, no bans, just perfect orchestration.

*   **The Limitation**: It breaks **Streaming (SSE)**. Background tasks are great for indexing but too slow for interactive chatbots.
*   **Verdict**: 💎 **Production Standard.** Perfect for heavy lifting like indexing and batch processing.

---

## 👑 2. The Final Boss: The "Hybrid Strategy"

The ultimate solution for Generative AI satisfy the user with **word-by-word streaming** while maintaining **strict global budget control**.

### **The Blueprint**
We split our application into two lanes:
1.  **The Background Lane (Taskiq)**: For Indexing/OCR/Batching.
2.  **The Interactive Lane (FastAPI + Global Semaphore)**: For Chat/Search.

### **The "Global Waiting Room" Pattern**
Instead of rejecting the 11th request with a 429 error, we make the user wait in a "Global Waiting Room" managed by Redis. They stay connected, and the stream starts as soon as a slot opens.

*   **The Math**: 
    - User #1 starts a Chat Stream. (Redis slot 1/50 taken ✅)
    - User #2 starts a Search. (Redis slot 2/50 taken ✅)
    - 48 more users join the "Global Waiting Room". (Redis slots 3-50 taken ✅)
    - **User #51** tries to start a chat. Redis says "WAIT."
    - **Total sent to LLM Provider**: **Exactly 50 RPM**. 
    - **Outcome**: **PERFECTION**. User #51's stream simply "pauses" for a few seconds. As soon as User #1 finishes, User #51's words start appearing word-by-word. No errors, no frustration, just a "Premium" feel.

### **The "Global Waiting Room" Implementation**

#### **Step 1: The Global Quota Manager (`src/helpers/quota.py`)**
This is a custom utility that uses Redis to create a "Global Waiting Room." It ensures that your FastAPI routes "wait" for a slot instead of returning a 429 error.

```python
import asyncio
from redis.asyncio import Redis
import time

class GlobalLLMQuota:
    """
    Distributed Quota Manager to protect LLM API keys 
    while allowing real-time SSE streaming.
    """
    def __init__(self, redis_url: str, max_rpm: int):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.max_rpm = max_rpm
        self.key_prefix = "quota:llm_global"

    async def wait_for_slot(self):
        """
        Pauses execution until a global slot is available.
        Optimized to sleep exactly until the next window opens.
        """
        while True:
            now = time.time()
            current_minute = int(now // 60)
            key = f"{self.key_prefix}:{current_minute}"
            
            # Increment the counter in Redis
            count = await self.redis.incr(key)
            
            if count == 1:
                # First request in this minute? Set TTL (120s for safety)
                await self.redis.expire(key, 120)
            
            if count <= self.max_rpm:
                return # Slot acquired! Proceed to LLM call
            
            # Quota reached? Calculate sleep until the next minute starts
            next_minute_start = (current_minute + 1) * 60
            sleep_time = next_minute_start - now + 0.1 # +100ms buffer
            await asyncio.sleep(sleep_time)
```

#### **Why this works: The Power of Redis `INCR`**
This implementation uses the **Fixed Window** algorithm, which is the most efficient for distributed systems.

- **Atomic Operation**: The `await self.redis.incr(key)` command is **atomic**. Even if 1,000 workers call it at the exact same microsecond, Redis processes them one-by-one. There are **never** any race conditions or double-counts.
- **Dynamic Key Generation**: The key is generated using `int(time.time() // 60)`.
    - **New Minute?** Redis sees a brand new key, initializes it to `0`, increments it to `1`, and returns `1`.
    - **Same Minute?** Redis finds the existing key and adds `+1` to the counter.
- **Automatic Reset & Efficient Sleeping**: We don't need a "reset" function. As soon as the clock ticks to the next minute, the code naturally generates a new key. Most importantly, if a slot isn't available, we don't poll; we **calculate exactly how many seconds are left** until the next minute and sleep until then.
- **Self-Cleaning**: By checking `if count == 1`, we set a 120-second expiration (TTL) only once per minute. This ensures the key persists long enough for safety while still being automatically cleaned up by Redis.

#### **Real-World Execution Example**
To understand the precision, let's look at the clock:

1.  **12:00:59**: The generated key is `quota:llm_global:29662226`. Workers are incrementing this key.
2.  **12:01:00** (One second later): The code generates a **new key**: `quota:llm_global:29662227`.
3.  **The Handshake**: When `await self.redis.incr(key)` hits Redis with this new key:
    - Redis realizes the key doesn't exist yet.
    - It **creates** the key with a value of `0`.
    - It **increments** it to `1`.
    - It **returns** `1`.
4.  **The Cleanup**: The `if count == 1` block triggers, setting a **120-second TTL**. The old key from `12:00:59` will be automatically deleted by Redis, while the current key stays alive long enough to prevent any race conditions or premature expiration.

#### **Step 2: The Interactive Stream (`src/routes/nlp.py`)**
This is how you use the manager inside your FastAPI route to provide a perfect SSE stream while staying under your RPM limit.

```python
from fastapi.responses import StreamingResponse
from src.helpers.quota import GlobalLLMQuota

# Initialize globally (e.g., 50 RPM limit)
quota_manager = GlobalLLMQuota(redis_url="redis://localhost:6379/0", max_rpm=50)

@nlp_router.post("/answer/stream")
async def answer_question_stream(rag_request: RAGRequest):
    # --- LAYER 1: THE SHIELD ---
    # This will pause here if the global 50 RPM limit is reached.
    # No 429 error is sent; the connection just stays open.
    await quota_manager.wait_for_slot()

    # --- LAYER 2: THE SATISFACTION ---
    # Now that we have a slot, start the word-by-word stream instantly.
    async def stream_generator():
        async for chunk in nlp_controller.stream_rag_answer(rag_request):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream"
    )
```

#### **Step 3: The Background Heavy-Lifter (`src/tasks/indexing.py`)**
For non-interactive tasks, you continue to use the Taskiq `rate_limit` method.

```python
@broker.task(task_name="indexing.process_file", rate_limit="50/m")
async def process_file_task(asset_id: int, project_id: int):
    """
    Taskiq handles the queuing and RPM limits automatically.
    No need for manual wait_for_slot() here.
    """
    # Logic for heavy PDF parsing and indexing...
    pass
```

---

## 🛠️ 3. The Decoupling Principle: Application-Level Control

In a production-grade system, your LLM Provider classes (e.g., `QwenModel`) should be "dumb workers." They should only care about **how** to format prompts and call APIs. They should **not** manage the "politics" of how fast they are allowed to run.

### **What to Remove (The Local Bloat)**
If you adopt the **Hybrid Strategy**, you should eliminate the following from your low-level provider constructors:
- ❌ `max_requests_per_minute`
- ❌ `max_concurrent_requests`
- ❌ `self.rpm_limiter = AsyncLimiter(...)`

### **Why Decoupling is the "Pro" Move**
1.  **Single Responsibility**: Your LLM folder stays clean. It only contains logic for API communication and response parsing.
2.  **Centralized Orchestration**: The "Source of Truth" moves to your `.env` and `Settings`.
    - **Used in the Hybrid Strategy (Application Level)**: 
        - Passed to the `GlobalLLMQuota(max_rpm=settings.MAX_RPM_EMBEDDING)` in your FastAPI routes. is passed to the **Global Quota Manager** for streams. 
        - Passed to the `@broker.task(rate_limit=f"{settings.MAX_RPM_EMBEDDING}/m")` in your Taskiq tasks. is passed to **Taskiq** for background jobs.
3.  **Infrastructure over Implementation**: You are using **Redis** (Infrastructure) to manage the state of your traffic, rather than **Python Variables** (Implementation). This allows you to scale to hundreds of containers without a single "blind" worker crashing your API Key.

---

## 🎯 4. Summary Verdict

As the best AI developers in the world, we don't just "limit" traffic; we **orchestrate** it.

| Strategy | User Experience | Global Safety | Use Case |
| :--- | :--- | :--- | :--- |
| **Taskiq** | Queued (Slow) | ✅ 100% | Indexing, PDF Parsing, Batching |
| **Hybrid** | Streaming (Fast) | ✅ 100% | **Chatbots, Interactive Q&A, RAG** |

**Final Wisdom**: Treat your LLM Provider as a finite resource. Use **Redis as the Brain**, **Taskiq as the Muscle**, and **FastAPI as the Voice**. This is how you build an unbreakable, high-performance Generative AI platform.
