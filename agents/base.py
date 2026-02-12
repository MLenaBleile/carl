"""BaseAgent: Abstract base class for all LLM agents.

Provides prompt loading, message construction, and JSON response parsing.
All LLM agents inherit from this class.
"""

import json
import os
import re
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    def __init__(self, prompt_name: str, model: str, config: dict = None):
        """Initialize agent with system prompt from prompts/{prompt_name}.md.

        Args:
            prompt_name: Name of the prompt file (without .md extension)
            model: Model identifier string (e.g., "claude-opus-4-6")
            config: Optional configuration dict
        """
        self.model = model
        self.config = config or {}
        self.prompt_name = prompt_name

        prompt_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
        self.prompt_path = os.path.join(prompt_dir, f"{prompt_name}.md")
        self.system_prompt = self._load_prompt()
        self.prompt_version = self._extract_version()

    def _load_prompt(self) -> str:
        """Load system prompt from file."""
        with open(self.prompt_path) as f:
            return f.read()

    def _extract_version(self) -> str:
        """Extract VERSION comment from prompt file."""
        match = re.search(r'#\s*VERSION:\s*(\S+)', self.system_prompt)
        return match.group(1) if match else "unknown"

    @abstractmethod
    async def call(self, **kwargs):
        """Execute the agent's primary task. Subclasses must implement."""
        ...

    def _build_messages(self, **kwargs) -> list[dict]:
        """Construct the messages list with system prompt + user content.

        Subclasses should override _build_user_content to customize.
        """
        user_content = self._build_user_content(**kwargs)
        return [
            {"role": "user", "content": user_content},
        ]

    def _build_user_content(self, **kwargs) -> str:
        """Build the user message content. Subclasses override this."""
        return json.dumps(kwargs, indent=2, default=str)

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from LLM response text.

        Handles:
        - Clean JSON
        - JSON wrapped in markdown code fences
        - JSON preceded by preamble text
        - Partial/broken JSON (best effort)
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fences
        fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object or array in text
        for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    # Try progressively shorter substrings for partial JSON
                    candidate = match.group(0)
                    for end_char in ['}', ']']:
                        last = candidate.rfind(end_char)
                        if last >= 0:
                            try:
                                return json.loads(candidate[:last + 1])
                            except json.JSONDecodeError:
                                continue

        raise ValueError(f"Could not parse JSON from response: {text[:200]}...")
