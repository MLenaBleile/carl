"""CoverLetterAgent: Generates cover letters with voice calibration."""

import json

from agents.base import BaseAgent
from agents.models import CoverLetterResult


class CoverLetterAgent(BaseAgent):
    def __init__(self, model: str = "claude-opus-4-6", config: dict = None):
        super().__init__(prompt_name="cover_letter_agent", model=model, config=config)

    async def call(self, *, profile: dict, style_guide: str,
                   job: dict, tailoring_notes: str = "",
                   resume_content: str = "",
                   resume_fact_check_flags: list = None,
                   mode: str = "draft",
                   previous: CoverLetterResult = None,
                   issues: list = None,
                   llm_client=None, **kwargs) -> CoverLetterResult:
        """Generate or revise a cover letter.

        Args:
            profile: Candidate profile dict
            style_guide: Style guide markdown text
            job: Job posting dict
            tailoring_notes: Guidance from MatchAgent
            resume_content: Final resume markdown (for consistency)
            resume_fact_check_flags: Issues from resume fact-checker
            mode: "draft" or "revise"
            previous: Previous CoverLetterResult (for revise mode)
            issues: List of issues from CL fact-checker (for revise mode)
            llm_client: LLMClient instance

        Returns:
            CoverLetterResult
        """
        messages = self._build_messages(
            profile=profile, style_guide=style_guide, job=job,
            tailoring_notes=tailoring_notes, resume_content=resume_content,
            resume_fact_check_flags=resume_fact_check_flags,
            mode=mode, previous=previous, issues=issues,
        )
        response = await llm_client.complete(
            model=self.model,
            system=self.system_prompt,
            messages=messages,
        )
        parsed = self._parse_json_response(response["content"])
        return CoverLetterResult(
            cover_letter_content=parsed.get("cover_letter_content", ""),
            profile_entries_used=parsed.get("profile_entries_used", []),
            company_facts_used=parsed.get("company_facts_used", []),
            voice_match_confidence=parsed.get("voice_match_confidence", "not_assessed"),
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
            "style_guide": kwargs.get("style_guide", ""),
            "job": kwargs.get("job", {}),
            "tailoring_notes": kwargs.get("tailoring_notes", ""),
            "resume_content": kwargs.get("resume_content", ""),
        }

        # Include resume fact-check flags so CL agent avoids borderline claims
        flags = kwargs.get("resume_fact_check_flags")
        if flags:
            content["resume_fact_check_flags"] = flags

        if mode == "revise":
            previous = kwargs.get("previous")
            if previous:
                content["previous_cover_letter"] = previous.cover_letter_content
                content["previous_entries_used"] = previous.profile_entries_used
            issues = kwargs.get("issues")
            if issues:
                content["issues"] = issues

        return json.dumps(content, indent=2, default=str)
