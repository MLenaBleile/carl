"""APIRateLimiter: Async rate limiting for LLM API calls.

Combines a semaphore for max concurrent calls with a sliding window
for per-minute rate limiting. Separate from the task semaphore.
"""

import asyncio
import time


class APIRateLimiter:
    def __init__(self, config: dict):
        self._semaphore = asyncio.Semaphore(config.get("concurrent_max", 5))
        self._rpm = config.get("requests_per_minute", 30)
        self._times: list[float] = []

    async def acquire(self):
        """Acquire a rate limit slot. Blocks until available."""
        await self._semaphore.acquire()
        now = time.monotonic()
        # Clean old timestamps outside the 60-second window
        self._times = [t for t in self._times if now - t < 60]
        if len(self._times) >= self._rpm:
            wait_time = 60 - (now - self._times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        self._times.append(time.monotonic())

    def release(self):
        """Release the rate limit slot."""
        self._semaphore.release()
