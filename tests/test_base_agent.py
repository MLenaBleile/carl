"""Tests for BaseAgent."""

import json
import pytest

from agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Concrete subclass for testing."""

    async def call(self, **kwargs):
        return kwargs


@pytest.fixture
def agent():
    return ConcreteAgent(
        prompt_name="scout_agent",
        model="claude-sonnet-4-5-20250929",
    )


class TestPromptLoading:
    def test_prompt_loaded(self, agent):
        """Verify prompt file loaded correctly."""
        assert len(agent.system_prompt) > 0
        assert "SCOUT AGENT" in agent.system_prompt

    def test_prompt_version_extracted(self, agent):
        """Verify version parsed from prompt file."""
        assert agent.prompt_version == "1.0.0"

    def test_model_set(self, agent):
        """Verify model is stored."""
        assert agent.model == "claude-sonnet-4-5-20250929"

    def test_prompt_name_stored(self, agent):
        """Verify prompt name is stored."""
        assert agent.prompt_name == "scout_agent"


class TestJsonParsing:
    def test_json_parsing_clean(self, agent):
        """Clean JSON parses correctly."""
        result = agent._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_parsing_with_fences(self, agent):
        """JSON in markdown code fences parses correctly."""
        text = '```json\n{"key": "value"}\n```'
        result = agent._parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_parsing_with_preamble(self, agent):
        """JSON preceded by preamble text parses correctly."""
        text = 'Here is the result:\n{"key": "value"}'
        result = agent._parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_parsing_array(self, agent):
        """JSON array parses correctly."""
        text = '[{"a": 1}, {"b": 2}]'
        result = agent._parse_json_response(text)
        assert result == [{"a": 1}, {"b": 2}]

    def test_json_parsing_with_text_after(self, agent):
        """JSON followed by text still parses."""
        text = 'Result:\n{"key": "value"}\nDone!'
        result = agent._parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_parsing_nested(self, agent):
        """Nested JSON object parses correctly."""
        obj = {"outer": {"inner": [1, 2, 3]}, "list": ["a", "b"]}
        text = f"```json\n{json.dumps(obj)}\n```"
        result = agent._parse_json_response(text)
        assert result == obj

    def test_json_parsing_failure(self, agent):
        """Unparseable text raises ValueError."""
        with pytest.raises(ValueError, match="Could not parse JSON"):
            agent._parse_json_response("This is just plain text with no JSON")


class TestMessageBuilding:
    def test_build_messages(self, agent):
        """Verify messages list structure."""
        messages = agent._build_messages(query="test", limit=5)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        content = json.loads(messages[0]["content"])
        assert content["query"] == "test"
        assert content["limit"] == 5
