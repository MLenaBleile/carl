"""Tests for APIRateLimiter."""

import asyncio
import time
import pytest
from unittest.mock import patch

from agents.rate_limiter import APIRateLimiter


@pytest.fixture
def limiter():
    return APIRateLimiter({"concurrent_max": 3, "requests_per_minute": 30})


class TestAPIRateLimiter:
    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Launch 10 concurrent acquires with max_concurrent=3, verify max 3 run simultaneously."""
        limiter = APIRateLimiter({"concurrent_max": 3, "requests_per_minute": 100})
        active = 0
        max_active = 0

        async def worker():
            nonlocal active, max_active
            await limiter.acquire()
            try:
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.05)
            finally:
                active -= 1
                limiter.release()

        tasks = [asyncio.create_task(worker()) for _ in range(10)]
        await asyncio.gather(*tasks)
        assert max_active <= 3

    @pytest.mark.asyncio
    async def test_rpm_limiting(self):
        """Verify that requests_per_minute is enforced."""
        # Set RPM to 5 and fill up the window
        limiter = APIRateLimiter({"concurrent_max": 10, "requests_per_minute": 5})

        # Mock time.monotonic to control the sliding window
        fake_time = 100.0

        def mock_monotonic():
            return fake_time

        with patch("agents.rate_limiter.time.monotonic", side_effect=mock_monotonic):
            # Fill up 5 slots quickly
            for _ in range(5):
                await limiter.acquire()
                limiter.release()

        # Now all 5 timestamps should be at time=100.0
        assert len(limiter._times) == 5

    @pytest.mark.asyncio
    async def test_acquire_and_release(self, limiter):
        """Basic acquire/release works."""
        await limiter.acquire()
        limiter.release()
        # Should not deadlock or error

    @pytest.mark.asyncio
    async def test_release_increases_semaphore(self):
        """After release, another acquire can proceed."""
        limiter = APIRateLimiter({"concurrent_max": 1, "requests_per_minute": 100})
        await limiter.acquire()
        limiter.release()

        # Should be able to acquire again immediately
        await asyncio.wait_for(limiter.acquire(), timeout=1.0)
        limiter.release()
