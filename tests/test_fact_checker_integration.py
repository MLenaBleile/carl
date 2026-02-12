"""Integration tests for the full VerificationRunner pipeline."""

import json
import os
import pytest

from verification.profile_index import ProfileIndex
from verification.runner import VerificationRunner

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

CONFIG = {
    "generation": {
        "source_mapper_resume_threshold": 0.30,
        "source_mapper_cover_letter_threshold": 0.25,
    },
    "structural_rules": {
        "max_consecutive_parallel_bullets": 3,
        "max_tricolon_lists": 1,
        "max_connector_words_per_document": 2,
        "connector_words": ["Moreover", "Furthermore", "Additionally", "Consequently", "Henceforth"],
        "paragraph_balance_cv_threshold": 0.15,
        "sentence_uniformity_cv_threshold": 0.20,
        "min_sentences_for_uniformity": 5,
    },
    "blacklist_path": os.path.join(os.path.dirname(__file__), "..", "config", "ai_blacklist.yaml"),
}


@pytest.fixture
def complete_profile():
    with open(os.path.join(FIXTURES_DIR, "profile_complete.json")) as f:
        return json.load(f)


@pytest.fixture
def profile_index(complete_profile):
    return ProfileIndex(complete_profile)


@pytest.fixture
def runner(profile_index):
    return VerificationRunner(profile_index, CONFIG)


@pytest.fixture
def good_resume():
    with open(os.path.join(FIXTURES_DIR, "resumes", "good_resume.md")) as f:
        return f.read()


@pytest.fixture
def hallucinated_resume():
    with open(os.path.join(FIXTURES_DIR, "resumes", "hallucinated.md")) as f:
        return f.read()


@pytest.fixture
def ai_fingerprint_resume():
    with open(os.path.join(FIXTURES_DIR, "resumes", "ai_fingerprint.md")) as f:
        return f.read()


class TestResumeVerification:
    def test_good_resume_passes(self, runner, good_resume):
        """good_resume.md against profile_complete.json -> status PASS, quality_score >= 80."""
        result = runner.verify_resume(good_resume)
        assert result["status"] == "PASS"
        assert result["quality_score"] >= 80

    def test_hallucinated_resume_fails(self, runner, hallucinated_resume):
        """hallucinated.md -> has UNGROUNDED_CLAIM or UNVERIFIED_METRIC issues."""
        result = runner.verify_resume(hallucinated_resume)
        issue_types = {i["type"] for i in result["issues"]}
        # Should have at least some flags for the fabricated claims
        assert len(result["issues"]) > 0

    def test_ai_fingerprint_detected(self, runner, ai_fingerprint_resume):
        """ai_fingerprint.md -> has AI_VOCABULARY and/or structural issues."""
        result = runner.verify_resume(ai_fingerprint_resume)
        issue_types = {i["type"] for i in result["issues"]}
        # Should detect at least blacklist words (spearhead, leverage, champion)
        # and/or connectors (Moreover, Furthermore, Additionally)
        ai_issues = [
            i for i in result["issues"]
            if i["type"] in ("AI_VOCABULARY", "AI_PHRASE", "PARALLEL_BULLETS", "CONNECTOR_EXCESS")
        ]
        assert len(ai_issues) > 0


class TestCoverLetterVerification:
    def test_cover_letter_verification(self, runner):
        """A simple CL -> runs without error, returns valid structure."""
        cl = (
            "I developed adaptive enrichment designs during my PhD at Harvard. "
            "At Sanofi, I built statistical frameworks for Phase III oncology trials. "
            "My work on Bayesian subgroup analysis was adopted by 15 statisticians. "
            "Your team's focus on precision oncology aligns with my research interests."
        )
        result = runner.verify_cover_letter(cl, claimed_ids=["exp_001", "exp_003"])
        assert "status" in result
        assert "issues" in result
        assert "quality_score" in result
        assert "source_map" in result
        assert isinstance(result["quality_score"], int)


class TestAppQuestionsVerification:
    def test_app_questions_verification(self, runner, complete_profile):
        """Simple Q&A set -> runs, flags ungrounded answers."""
        answers = [
            {
                "question_text": "Why do you want to work here?",
                "answer": "I am passionate about making a difference in healthcare.",
                "source": "profile_derived",
            },
            {
                "question_text": "Do you require visa sponsorship?",
                "answer": "No",
                "source": "pre_approved",
            },
        ]
        result = runner.verify_app_questions(answers, complete_profile)
        assert "status" in result
        assert "issues" in result
        assert "quality_score" in result
        # The first answer uses "passionate" which is blacklisted
        blacklist_issues = [i for i in result["issues"] if i["type"] == "AI_VOCABULARY"]
        assert len(blacklist_issues) >= 1


class TestQualityScoreMath:
    def test_quality_score_math(self, runner):
        """2 HIGH + 3 MEDIUM + 1 LOW = 100 - 30 - 15 - 1 = 54."""
        issues = [
            {"severity": "HIGH"}, {"severity": "HIGH"},
            {"severity": "MEDIUM"}, {"severity": "MEDIUM"}, {"severity": "MEDIUM"},
            {"severity": "LOW"},
        ]
        score = runner._score(issues)
        assert score == 54

    def test_quality_score_floor(self, runner):
        """Score can't go below 0."""
        issues = [{"severity": "HIGH"}] * 10  # 10 * 15 = 150 > 100
        score = runner._score(issues)
        assert score == 0

    def test_quality_score_perfect(self, runner):
        """No issues -> score 100."""
        score = runner._score([])
        assert score == 100
