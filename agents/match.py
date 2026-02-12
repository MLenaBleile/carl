"""MatchAgent: Scores and ranks discovered jobs against the candidate profile."""

import json

from agents.base import BaseAgent
from agents.models import MatchResult


class MatchAgent(BaseAgent):
    # Classification boundaries
    STRONG_THRESHOLD = 7.5
    GOOD_THRESHOLD = 6.0
    MARGINAL_THRESHOLD = 4.5

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", config: dict = None):
        super().__init__(prompt_name="match_agent", model=model, config=config)

    async def call(self, *, profile: dict, jobs: list[dict],
                   llm_client=None, **kwargs) -> list[MatchResult]:
        """Score each job against the profile.

        Args:
            profile: Candidate profile dict
            jobs: List of job dicts from ScoutAgent
            llm_client: LLMClient instance

        Returns:
            List of MatchResult objects
        """
        messages = self._build_messages(profile=profile, jobs=jobs)
        response = await llm_client.complete(
            model=self.model,
            system=self.system_prompt,
            messages=messages,
        )
        parsed = self._parse_json_response(response["content"])
        results_raw = parsed if isinstance(parsed, list) else [parsed]

        results = []
        for r in results_raw:
            score = r.get("composite_score", 0)
            classification = r.get("classification", self._classify(score))
            results.append(MatchResult(
                job=r.get("job", {}),
                composite_score=score,
                classification=classification,
                dimension_scores=r.get("dimension_scores", {}),
                key_selling_points=r.get("key_selling_points", []),
                gaps=r.get("gaps", []),
                tailoring_notes=r.get("tailoring_notes", ""),
                token_usage=response["token_usage"],
            ))
        return results

    @classmethod
    def _classify(cls, score: float) -> str:
        """Classify score into STRONG/GOOD/MARGINAL/WEAK."""
        if score >= cls.STRONG_THRESHOLD:
            return "STRONG"
        elif score >= cls.GOOD_THRESHOLD:
            return "GOOD"
        elif score >= cls.MARGINAL_THRESHOLD:
            return "MARGINAL"
        else:
            return "WEAK"

    def _build_user_content(self, **kwargs) -> str:
        return json.dumps({
            "profile": kwargs.get("profile", {}),
            "jobs": kwargs.get("jobs", []),
        }, indent=2, default=str)
