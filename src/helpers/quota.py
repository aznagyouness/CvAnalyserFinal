import asyncio
import time
import random
import logging
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

class GlobalLLMQuota:
    """
    Distributed Quota Manager to protect LLM API keys 
    while allowing real-time SSE streaming.
    """
    def __init__(self, redis_url: str, max_rpm: int, key_prefix: str):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.max_rpm = max_rpm
        self.key_prefix = key_prefix

    async def wait_for_slot(self):
        """
        Pauses execution until a global slot is available.
        Transparent to the user (they just see a slightly longer 'loading' state).
        """
        while True:
            # 1. Use UTC Time for the Key (Synchronized across all servers)
            now_utc = time.time()
            current_minute = int(now_utc // 60)
            key = f"{self.key_prefix}:{current_minute}"
            
            # 2. LUA Script for Atomic Incr + Expire (Fixes the Race Condition)
            # This ensures we never leak keys without TTL if a process crashes.
            lua = """
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return count
            """
            try:
                # Execute atomically in one Redis trip
                count = await self.redis.eval(lua, 1, key, 120)
            except Exception as e:
                # 🛡️ Fail-Open Policy: Don't crash the chatbot if Redis is down
                logger.warning(f"Quota Manager: Redis unavailable, failing open. Error: {e}")
                return 

            if count <= self.max_rpm:
                return # Slot acquired! Proceed to LLM call
            
            # 3. Calculate sleep with Jitter (Prevents the Thundering Herd)
            # We sleep exactly until the next minute starts + a tiny random delay
            next_minute_start = (current_minute + 1) * 60
            sleep_time = (next_minute_start - now_utc) + random.uniform(0.05, 0.2)
            await asyncio.sleep(max(0, sleep_time))

    async def close(self):
        """Gracefully close the Redis connection pool."""
        await self.redis.close()