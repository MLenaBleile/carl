"""VerifyAgent: Adversarial LLM quality review."""

import json

from agents.base import BaseAgent
from agents.models import VerifyResult


class VerifyAgent(BaseAgent):
    def __init__(self, model: str = "claude-opus-4-6", config: dict = None):
        super().__init__(prompt_name="verify_agent", model=model, config=config)

    async def call(self, *, profile: dict, style_guide: str = "",
                   resume: str = "", cover_letter: str = "",
                   app_questions: list = None,
                   match_result: dict = None,
                   fact_check_results: dict = None,
                   llm_client=None, **kwargs) -> VerifyResult:
        """Run adversarial review on generated documents.

        Args:
            profile: Candidate profile dict
            style_guide: Style guide markdown text
            resume: Resume markdown content
            cover_letter: Cover letter text (may be empty)
            app_questions: List of Q&A dicts (may be None)
            match_result: Match analysis dict
            fact_check_results: Results from Programmatic Verification Suite
            llm_client: LLMClient instance

        Returns:
            VerifyResult
        """
        messages = self._build_messages(
            profile=profile, style_guide=style_guide,
            resume=resume, cover_letter=cover_letter,
            app_questions=app_questions, match_result=match_result,
            fact_check_results=fact_check_results,
        )
        response = await llm_client.complete(
            model=self.model,
            system=self.system_prompt,
            messages=messages,
        )
        parsed = self._parse_json_response(response["content"])
        return VerifyResult(
            verdict=parsed.get("verdict", "FAIL"),
            resume_review=parsed.get("resume_review", {}),
            cover_letter_review=parsed.get("cover_letter_review", {}),
            app_questions_review=parsed.get("app_questions_review", {}),
            revision_instructions=parsed.get("revision_instructions", {}),
            notes=parsed.get("notes", ""),
            token_usage=response["token_usage"],
        )

    def _build_user_content(self, **kwargs) -> str:
        content = {
            "profile": kwargs.get("profile", {}),
            "resume": kwargs.get("resume", ""),
        }

        style_guide = kwargs.get("style_guide", "")
        if style_guide:
            content["style_guide"] = style_guide

        cover_letter = kwargs.get("cover_letter", "")
        if cover_letter:
            content["cover_letter"] = cover_letter

        app_questions = kwargs.get("app_questions")
        if app_questions:
            content["app_questions"] = app_questions

        match_result = kwargs.get("match_result")
        if match_result:
            content["match_result"] = match_result

        fact_check_results = kwargs.get("fact_check_results")
        if fact_check_results:
            content["fact_check_results"] = fact_check_results

        return json.dumps(content, indent=2, default=str)
