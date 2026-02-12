"""ResumeAgent: Generates tailored resumes grounded in the profile."""

import json

from agents.base import BaseAgent
from agents.models import ResumeResult


class ResumeAgent(BaseAgent):
    def __init__(self, model: str = "claude-opus-4-6", config: dict = None):
        super().__init__(prompt_name="resume_agent", model=model, config=config)

    async def call(self, *, profile: dict, job: dict,
                   tailoring_notes: str = "", mode: str = "draft",
                   previous: ResumeResult = None, issues: list = None,
                   llm_client=None, **kwargs) -> ResumeResult:
        """Generate or revise a resume.

        Args:
            profile: Candidate profile dict
            job: Job posting dict
            tailoring_notes: Guidance from MatchAgent
            mode: "draft" or "revise"
            previous: Previous ResumeResult (for revise mode)
            issues: List of issues from fact-checker (for revise mode)
            llm_client: LLMClient instance

        Returns:
            ResumeResult
        """
        messages = self._build_messages(
            profile=profile, job=job, tailoring_notes=tailoring_notes,
            mode=mode, previous=previous, issues=issues,
        )
        response = await llm_client.complete(
            model=self.model,
            system=self.system_prompt,
            messages=messages,
        )
        parsed = self._parse_json_response(response["content"])
        return ResumeResult(
            resume_content=parsed.get("resume_content", ""),
            profile_entries_used=parsed.get("profile_entries_used", []),
            iterations_completed=parsed.get("iterations_completed", 1),
            iteration_log=parsed.get("iteration_log", []),
            remaining_concerns=parsed.get("remaining_concerns", []),
            profile_version=parsed.get("profile_version", "1.0.0"),
            token_usage=response["token_usage"],
        )

    def _build_user_content(self, **kwargs) -> str:
        mode = kwargs.get("mode", "draft")
        content = {
            "mode": mode,
            "profile": kwargs.get("profile", {}),
            "job": kwargs.get("job", {}),
            "tailoring_notes": kwargs.get("tailoring_notes", ""),
        }

        if mode == "revise":
            previous = kwargs.get("previous")
            if previous:
                content["previous_resume"] = previous.resume_content
                content["previous_entries_used"] = previous.profile_entries_used
            issues = kwargs.get("issues")
            if issues:
                content["issues"] = issues

        return json.dumps(content, indent=2, default=str)
