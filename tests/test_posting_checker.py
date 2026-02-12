"""Tests for PostingChecker (uses mocked aiohttp)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from verification.posting_checker import PostingChecker


@pytest.fixture
def checker():
    return PostingChecker()


class _FakeResponse:
    """Simple fake aiohttp response for testing."""

    def __init__(self, status, body=""):
        self.status = status
        self._body = body

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _FakeSession:
    """Simple fake aiohttp session for testing."""

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def get(self, url):
        if self._error:
            raise self._error
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestPostingChecker:
    @pytest.mark.asyncio
    async def test_live_posting(self, checker):
        """Mock 200 response with normal content -> (True, 200, 'Live')."""
        response = _FakeResponse(200, "<html>Apply now!</html>")
        session = _FakeSession(response=response)

        with patch("verification.posting_checker.aiohttp.ClientSession", return_value=session):
            is_live, status, notes = await checker.is_live("https://example.com/job/123")
            assert is_live is True
            assert status == 200
            assert notes == "Live"

    @pytest.mark.asyncio
    async def test_404(self, checker):
        """Mock 404 -> (False, 404, ...)."""
        response = _FakeResponse(404, "Not Found")
        session = _FakeSession(response=response)

        with patch("verification.posting_checker.aiohttp.ClientSession", return_value=session):
            is_live, status, notes = await checker.is_live("https://example.com/job/gone")
            assert is_live is False
            assert status == 404

    @pytest.mark.asyncio
    async def test_expired_signal(self, checker):
        """Mock 200 with 'this job is no longer available' in body -> (False, 200, ...)."""
        body = "<html><body><h1>this job is no longer available</h1></body></html>"
        response = _FakeResponse(200, body)
        session = _FakeSession(response=response)

        with patch("verification.posting_checker.aiohttp.ClientSession", return_value=session):
            is_live, status, notes = await checker.is_live("https://example.com/job/expired")
            assert is_live is False
            assert status == 200
            assert "Expired signal" in notes

    @pytest.mark.asyncio
    async def test_timeout(self, checker):
        """Mock timeout -> (False, 0, 'Connection timed out...')."""
        session = _FakeSession(error=asyncio.TimeoutError())

        with patch("verification.posting_checker.aiohttp.ClientSession", return_value=session):
            is_live, status, notes = await checker.is_live("https://example.com/slow")
            assert is_live is False
            assert status == 0
            assert "timed out" in notes.lower()

    @pytest.mark.asyncio
    async def test_position_filled(self, checker):
        """Mock 200 with 'this position has been filled' -> expired."""
        body = "<html><body>Sorry, this position has been filled.</body></html>"
        response = _FakeResponse(200, body)
        session = _FakeSession(response=response)

        with patch("verification.posting_checker.aiohttp.ClientSession", return_value=session):
            is_live, status, notes = await checker.is_live("https://example.com/job/filled")
            assert is_live is False
            assert status == 200

    @pytest.mark.asyncio
    async def test_410_gone(self, checker):
        """Mock 410 Gone -> (False, 410, ...)."""
        response = _FakeResponse(410, "Gone")
        session = _FakeSession(response=response)

        with patch("verification.posting_checker.aiohttp.ClientSession", return_value=session):
            is_live, status, notes = await checker.is_live("https://example.com/job/gone")
            assert is_live is False
            assert status == 410
