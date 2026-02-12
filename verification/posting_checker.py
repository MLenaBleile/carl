"""PostingChecker: Verifies job postings are still live.

Async HTTP check with body scanning for expired signals.
"""

import aiohttp
import asyncio


# Signals in page body that indicate the posting is expired
EXPIRED_SIGNALS = [
    "this job is no longer available",
    "this position has been filled",
    "this listing has expired",
    "no longer accepting applications",
    "this job has been closed",
    "position closed",
]


class PostingChecker:
    async def is_live(self, url: str) -> tuple[bool, int, str]:
        """Check if a job posting URL is still live.

        Returns:
            (is_live, status_code, notes)

        v3.1 fix: timeout returns (False, 0, "Connection timed out...")
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    status = response.status

                    if status in (404, 410):
                        return (False, status, f"HTTP {status} — posting removed")

                    if status != 200:
                        return (False, status, f"HTTP {status} — non-200 response")

                    body = await response.text()
                    body_lower = body.lower()

                    for signal in EXPIRED_SIGNALS:
                        if signal in body_lower:
                            return (False, 200, f"Expired signal found: '{signal}'")

                    return (True, 200, "Live")

        except asyncio.TimeoutError:
            return (False, 0, "Connection timed out — treat as potentially expired")
        except aiohttp.ClientError as e:
            return (False, 0, f"Connection error: {type(e).__name__}")
        except Exception as e:
            return (False, 0, f"Unexpected error: {type(e).__name__}: {e}")
