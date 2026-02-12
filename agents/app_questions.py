"""AppQuestionsAgent: Generates answers to application form questions."""

import json

from agents.base import BaseAgent
from agents.models import AppQuestionAnswer, AppQuestionsResult


class AppQuestionsAgent(BaseAgent):
    def __init__(self, model: str = "claude-sonnet-4-5-20250929", config: dict = None):
        super().__init__(prompt_name="app_questions_agent", model=model, config=config)

    async def call(self, *, profile: dict, job: dict,
                   questions: list[dict],
                   llm_client=None, **kwargs) -> AppQuestionsResult:
        """Generate answers to application questions.

        Args:
            profile: Candidate profile dict
            job: Job posting dict
            questions: List of question dicts with "question_text", "question_type", etc.
            llm_client: LLMClient instance

        Returns:
            AppQuestionsResult with list of AppQuestionAnswer
        """
        messages = self._build_messages(
            profile=profile, job=job, questions=questions,
        )
        response = await llm_client.complete(
            model=self.model,
            system=self.system_prompt,
            messages=messages,
        )
        parsed = self._parse_json_response(response["content"])
        answers_raw = parsed if isinstance(parsed, list) else parsed.get("answers", [parsed])

        answers = []
        for a in answers_raw:
            answers.append(AppQuestionAnswer(
                question_text=a.get("question_text", ""),
                answer=a.get("answer", ""),
                source=a.get("source", "profile_derived"),
                profile_entries_used=a.get("profile_entries_used", []),
                confidence=a.get("confidence", "medium"),
                needs_human_review=a.get("needs_human_review", False),
            ))

        return AppQuestionsResult(
            answers=answers,
            token_usage=response["token_usage"],
        )

    def _build_user_content(self, **kwargs) -> str:
        profile = kwargs.get("profile", {})
        pre_approved = profile.get("application_question_answers", {})

        content = {
            "profile": profile,
            "job": kwargs.get("job", {}),
            "questions": kwargs.get("questions", []),
            "pre_approved_answers": pre_approved,
        }
        return json.dumps(content, indent=2, default=str)
