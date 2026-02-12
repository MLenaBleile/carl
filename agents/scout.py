"""ScoutAgent: Discovers relevant job postings."""

import json

from agents.base import BaseAgent


class ScoutAgent(BaseAgent):
    def __init__(self, model: str = "claude-sonnet-4-5-20250929", config: dict = None):
        super().__init__(prompt_name="scout_agent", model=model, config=config)

    async def call(self, *, profile: dict, mode: str = "search",
                   llm_client=None, **kwargs) -> dict:
        """Discover job postings.

        Args:
            profile: Candidate profile dict
            mode: "search" or "market_research"
            llm_client: LLMClient instance for API calls

        Returns:
            dict with "jobs" list and "token_usage"
        """
        messages = self._build_messages(profile=profile, mode=mode)
        response = await llm_client.complete(
            model=self.model,
            system=self.system_prompt,
            messages=messages,
        )
        parsed = self._parse_json_response(response["content"])
        jobs = parsed if isinstance(parsed, list) else parsed.get("jobs", [parsed])
        return {"jobs": jobs, "token_usage": response["token_usage"]}

    def _build_user_content(self, **kwargs) -> str:
        profile = kwargs.get("profile", {})
        mode = kwargs.get("mode", "search")
        target_roles = profile.get("summary", {}).get("target_roles", [])
        skills = profile.get("skills", {})

        content = {
            "mode": mode,
            "target_roles": target_roles,
            "skills": skills,
            "location": profile.get("identity", {}).get("location", {}),
        }
        return json.dumps(content, indent=2, default=str)
