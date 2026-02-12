"""LLMClient: Wraps the Anthropic API with rate limiting, retry, and budget tracking.

All LLM calls in the system go through this client.
"""

import asyncio
import random


class LLMClient:
    def __init__(self, api_key: str, rate_limiter=None, budget=None):
        """Initialize the LLM client.

        Args:
            api_key: Anthropic API key
            rate_limiter: Optional APIRateLimiter instance
            budget: Optional TokenBudget instance
        """
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.budget = budget
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(self, model: str, system: str, messages: list[dict],
                       max_tokens: int = 4096) -> dict:
        """Call the Anthropic API with retry and rate limiting.

        Uses try/finally to ensure rate limiter is always released.

        Args:
            model: Model identifier
            system: System prompt
            messages: List of message dicts
            max_tokens: Maximum tokens in response

        Returns:
            dict with "content" (str) and "token_usage" (dict)
        """
        last_error = None

        for attempt in range(3):
            if self.rate_limiter:
                await self.rate_limiter.acquire()
            try:
                client = self._get_client()
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                )

                token_usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "model": model,
                }

                if self.budget:
                    self.budget.record(token_usage)

                return {
                    "content": response.content[0].text,
                    "token_usage": token_usage,
                }

            except Exception as e:
                last_error = e
                error_name = type(e).__name__
                # Retry on rate limit, timeout, or API errors
                if error_name in ("RateLimitError", "APIStatusError",
                                  "APITimeoutError", "APIConnectionError",
                                  "TimeoutError"):
                    if attempt < 2:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        await asyncio.sleep(wait)
                        continue
                raise
            finally:
                if self.rate_limiter:
                    self.rate_limiter.release()

        raise last_error
