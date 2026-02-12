"""Tests for LLMClient."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.llm_client import LLMClient


class FakeUsage:
    def __init__(self, input_tokens=100, output_tokens=50):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeContentBlock:
    def __init__(self, text="response text"):
        self.text = text


class FakeResponse:
    def __init__(self, text="response text", input_tokens=100, output_tokens=50):
        self.content = [FakeContentBlock(text)]
        self.usage = FakeUsage(input_tokens, output_tokens)


class FakeRateLimiter:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    async def acquire(self):
        self.acquired += 1

    def release(self):
        self.released += 1


class TestRetryOnRateLimit:
    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Mock API to raise rate limit once, then succeed."""
        client = LLMClient(api_key="test-key")

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise type("RateLimitError", (Exception,), {})()
            return FakeResponse()

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create = mock_create
        client._client = mock_anthropic_client

        result = await client.complete(
            model="claude-sonnet-4-5-20250929",
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result["content"] == "response text"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Mock API to always fail — should raise after 3 attempts."""
        client = LLMClient(api_key="test-key")

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            raise type("APIStatusError", (Exception,), {})()

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create = mock_create
        client._client = mock_anthropic_client

        with pytest.raises(Exception):
            await client.complete(
                model="claude-sonnet-4-5-20250929",
                system="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
            )

        assert call_count == 3


class TestBudgetRecording:
    @pytest.mark.asyncio
    async def test_budget_recorded(self):
        """Mock successful call — verify budget.record called."""
        budget = MagicMock()
        client = LLMClient(api_key="test-key", budget=budget)

        async def mock_create(**kwargs):
            return FakeResponse(input_tokens=200, output_tokens=100)

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create = mock_create
        client._client = mock_anthropic_client

        result = await client.complete(
            model="claude-opus-4-6",
            system="System",
            messages=[{"role": "user", "content": "Hi"}],
        )

        budget.record.assert_called_once()
        call_args = budget.record.call_args[0][0]
        assert call_args["input_tokens"] == 200
        assert call_args["output_tokens"] == 100
        assert call_args["model"] == "claude-opus-4-6"


class TestSemaphoreReleasedOnError:
    @pytest.mark.asyncio
    async def test_semaphore_released_on_error(self):
        """Mock API error — verify release() called (the try/finally fix)."""
        rate_limiter = FakeRateLimiter()
        client = LLMClient(api_key="test-key", rate_limiter=rate_limiter)

        async def mock_create(**kwargs):
            raise ValueError("Unexpected error")

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create = mock_create
        client._client = mock_anthropic_client

        with pytest.raises(ValueError):
            await client.complete(
                model="claude-sonnet-4-5-20250929",
                system="System",
                messages=[{"role": "user", "content": "Hi"}],
            )

        # Semaphore should be acquired and released even on error
        assert rate_limiter.acquired >= 1
        assert rate_limiter.released >= 1
        assert rate_limiter.acquired == rate_limiter.released

    @pytest.mark.asyncio
    async def test_semaphore_released_on_success(self):
        """Verify release() called on successful call."""
        rate_limiter = FakeRateLimiter()
        client = LLMClient(api_key="test-key", rate_limiter=rate_limiter)

        async def mock_create(**kwargs):
            return FakeResponse()

        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create = mock_create
        client._client = mock_anthropic_client

        await client.complete(
            model="claude-sonnet-4-5-20250929",
            system="System",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert rate_limiter.acquired == 1
        assert rate_limiter.released == 1
