"""Tests for individual agent implementations with mocked LLM client."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from agents.match import MatchAgent
from agents.resume import ResumeAgent
from agents.cover_letter import CoverLetterAgent
from agents.app_questions import AppQuestionsAgent
from agents.verify import VerifyAgent
from agents.models import ResumeResult, CoverLetterResult, MatchResult


class FakeLLMClient:
    """Fake LLM client that returns predetermined responses."""

    def __init__(self, response_content: str):
        self._response_content = response_content
        self.last_messages = None
        self.last_system = None

    async def complete(self, model, system, messages, max_tokens=4096):
        self.last_messages = messages
        self.last_system = system
        return {
            "content": self._response_content,
            "token_usage": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "model": model,
            },
        }


@pytest.fixture
def sample_profile():
    return {
        "identity": {"name": "Test User"},
        "summary": {"target_roles": [{"title_patterns": ["Data Scientist"]}]},
        "experience": [
            {
                "id": "exp_001",
                "title": "Senior Analyst",
                "organization": "TestCorp",
                "accomplishments": ["Reduced costs by 20%"],
                "responsibilities": ["Data analysis"],
            }
        ],
        "skills": {"programming": {"expert": ["Python"], "proficient": ["R"]}},
        "publications": [],
        "presentations": [],
        "application_question_answers": {
            "sponsorship_required": False,
            "salary_expectation": "$150,000 - $180,000",
        },
    }


@pytest.fixture
def sample_job():
    return {
        "job_id": "test_job_001",
        "company": {"name": "DataCo"},
        "role": {"title": "Data Scientist", "description_raw": "We need a DS."},
    }


class TestResumeAgentDraftMode:
    @pytest.mark.asyncio
    async def test_resume_agent_draft_mode(self, sample_profile, sample_job):
        """Mock LLM response with valid JSON → verify ResumeResult parsed."""
        response = json.dumps({
            "resume_content": "# Test User\n\n## Experience\n- Reduced costs by 20%",
            "profile_entries_used": ["exp_001"],
            "iterations_completed": 1,
            "iteration_log": [],
            "remaining_concerns": [],
            "profile_version": "1.0.0",
        })

        client = FakeLLMClient(response)
        agent = ResumeAgent()

        result = await agent.call(
            profile=sample_profile,
            job=sample_job,
            tailoring_notes="Emphasize cost reduction",
            mode="draft",
            llm_client=client,
        )

        assert isinstance(result, ResumeResult)
        assert "Test User" in result.resume_content
        assert "exp_001" in result.profile_entries_used
        assert result.iterations_completed == 1
        assert result.token_usage["input_tokens"] == 1000


class TestResumeAgentReviseMode:
    @pytest.mark.asyncio
    async def test_resume_agent_revise_mode(self, sample_profile, sample_job):
        """Verify issues are included in the prompt when in revise mode."""
        response = json.dumps({
            "resume_content": "# Revised Resume",
            "profile_entries_used": ["exp_001"],
            "iterations_completed": 2,
        })

        client = FakeLLMClient(response)
        agent = ResumeAgent()

        previous = ResumeResult(
            resume_content="# Old Resume",
            profile_entries_used=["exp_001"],
        )
        issues = [
            {"type": "UNGROUNDED_CLAIM", "severity": "HIGH",
             "message": "Line 5: 'Led team of 10' not found in profile"},
            {"type": "AI_VOCABULARY", "severity": "MEDIUM",
             "message": "Blacklisted: 'leveraged'"},
        ]

        result = await agent.call(
            profile=sample_profile,
            job=sample_job,
            mode="revise",
            previous=previous,
            issues=issues,
            llm_client=client,
        )

        assert isinstance(result, ResumeResult)
        assert result.iterations_completed == 2

        # Verify issues were passed in the message
        user_content = json.loads(client.last_messages[0]["content"])
        assert user_content["mode"] == "revise"
        assert "issues" in user_content
        assert len(user_content["issues"]) == 2
        assert "UNGROUNDED_CLAIM" in user_content["issues"][0]["type"]


class TestCoverLetterReceivesFactCheckFlags:
    @pytest.mark.asyncio
    async def test_cover_letter_receives_fact_check_flags(self, sample_profile, sample_job):
        """Verify the resume fact-check flags appear in the constructed messages."""
        response = json.dumps({
            "cover_letter_content": "Dear Hiring Manager...",
            "profile_entries_used": ["exp_001"],
            "company_facts_used": [],
            "voice_match_confidence": "medium",
        })

        client = FakeLLMClient(response)
        agent = CoverLetterAgent()

        flags = [
            {"type": "UNVERIFIED_METRIC", "severity": "MEDIUM",
             "message": "Number '35%' was borderline match"},
        ]

        result = await agent.call(
            profile=sample_profile,
            style_guide="# Style Guide\nDirect voice.",
            job=sample_job,
            resume_content="# Resume content here",
            resume_fact_check_flags=flags,
            mode="draft",
            llm_client=client,
        )

        assert isinstance(result, CoverLetterResult)
        assert "Dear Hiring Manager" in result.cover_letter_content

        # Verify flags passed to LLM
        user_content = json.loads(client.last_messages[0]["content"])
        assert "resume_fact_check_flags" in user_content
        assert user_content["resume_fact_check_flags"][0]["type"] == "UNVERIFIED_METRIC"


class TestAppQuestionsUsesPreApproved:
    @pytest.mark.asyncio
    async def test_app_questions_uses_pre_approved(self, sample_profile, sample_job):
        """Verify pre-approved answers are referenced in the prompt."""
        response = json.dumps([
            {
                "question_text": "Do you require sponsorship?",
                "answer": "No",
                "source": "pre_approved",
                "profile_entries_used": [],
                "confidence": "high",
                "needs_human_review": False,
            },
            {
                "question_text": "What is your salary expectation?",
                "answer": "$150,000 - $180,000",
                "source": "pre_approved",
                "profile_entries_used": [],
                "confidence": "high",
                "needs_human_review": False,
            },
        ])

        client = FakeLLMClient(response)
        agent = AppQuestionsAgent()

        questions = [
            {"question_text": "Do you require sponsorship?", "question_type": "yes_no"},
            {"question_text": "What is your salary expectation?", "question_type": "free_text"},
        ]

        result = await agent.call(
            profile=sample_profile,
            job=sample_job,
            questions=questions,
            llm_client=client,
        )

        assert len(result.answers) == 2
        assert result.answers[0].source == "pre_approved"
        assert result.answers[0].confidence == "high"

        # Verify pre-approved answers were included in the prompt
        user_content = json.loads(client.last_messages[0]["content"])
        assert "pre_approved_answers" in user_content
        assert user_content["pre_approved_answers"]["sponsorship_required"] is False


class TestVerifyAgentExcludesCodeChecks:
    def test_verify_agent_excludes_code_checks(self):
        """Verify 'No skills above proficiency level' is NOT in the prompt.

        v3.1 fix: SkillLevelChecker handles this in code, so the Verify Agent
        prompt should NOT list it as 'already checked' — it IS already checked
        by code and appears in the verified list without the old wording.
        """
        agent = VerifyAgent()
        # The phrase "No skills above proficiency level" should not appear
        # because SkillLevelChecker handles it in code now
        assert "No skills above proficiency level" not in agent.system_prompt
        # But the programmatic verification list should still be referenced
        assert "Programmatic Verification Suite" in agent.system_prompt
        assert "source map" in agent.system_prompt.lower()


class TestMatchAgentClassificationBoundaries:
    @pytest.mark.asyncio
    async def test_strong_boundary(self, sample_profile, sample_job):
        """Score >= 7.5 → STRONG classification."""
        response = json.dumps([{
            "composite_score": 7.5,
            "dimension_scores": {},
            "key_selling_points": ["perfect fit"],
            "gaps": [],
            "tailoring_notes": "Direct match",
        }])

        client = FakeLLMClient(response)
        agent = MatchAgent()

        results = await agent.call(
            profile=sample_profile,
            jobs=[sample_job],
            llm_client=client,
        )

        assert len(results) == 1
        assert results[0].classification == "STRONG"
        assert results[0].composite_score == 7.5

    @pytest.mark.asyncio
    async def test_good_boundary(self, sample_profile, sample_job):
        """Score 6.0-7.4 → GOOD classification."""
        response = json.dumps([{"composite_score": 6.0}])
        client = FakeLLMClient(response)
        agent = MatchAgent()

        results = await agent.call(
            profile=sample_profile, jobs=[sample_job], llm_client=client,
        )
        assert results[0].classification == "GOOD"

    @pytest.mark.asyncio
    async def test_marginal_boundary(self, sample_profile, sample_job):
        """Score 4.5-5.9 → MARGINAL classification."""
        response = json.dumps([{"composite_score": 4.5}])
        client = FakeLLMClient(response)
        agent = MatchAgent()

        results = await agent.call(
            profile=sample_profile, jobs=[sample_job], llm_client=client,
        )
        assert results[0].classification == "MARGINAL"

    @pytest.mark.asyncio
    async def test_weak_boundary(self, sample_profile, sample_job):
        """Score < 4.5 → WEAK classification."""
        response = json.dumps([{"composite_score": 3.0}])
        client = FakeLLMClient(response)
        agent = MatchAgent()

        results = await agent.call(
            profile=sample_profile, jobs=[sample_job], llm_client=client,
        )
        assert results[0].classification == "WEAK"

    def test_classify_static(self):
        """Test the static classification method directly."""
        assert MatchAgent._classify(8.0) == "STRONG"
        assert MatchAgent._classify(7.5) == "STRONG"
        assert MatchAgent._classify(7.4) == "GOOD"
        assert MatchAgent._classify(6.0) == "GOOD"
        assert MatchAgent._classify(5.9) == "MARGINAL"
        assert MatchAgent._classify(4.5) == "MARGINAL"
        assert MatchAgent._classify(4.4) == "WEAK"
        assert MatchAgent._classify(0.0) == "WEAK"
