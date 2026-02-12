"""Tests for Queue Agent."""

import pytest

from agents.queue import package_for_review, generate_one_liner, sort_queue


@pytest.fixture
def sample_job():
    return {
        "job_id": "scout_20260210_abc",
        "company": {"name": "Adaptive Bio", "industry": "pharma"},
        "role": {
            "title": "Senior Statistician",
            "url": "https://example.com/job/123",
            "application_deadline": "2026-02-15",
        },
    }


@pytest.fixture
def sample_match():
    return {
        "composite_score": 8.2,
        "classification": "STRONG",
        "key_selling_points": ["causal inference experience", "clinical trials background"],
        "gaps": ["no finance experience"],
        "tailoring_notes": "Emphasize adaptive design work",
    }


class TestPackageForReview:
    def test_package_structure(self, sample_job, sample_match):
        """Verify all required keys present."""
        package = package_for_review(
            job=sample_job,
            match_result=sample_match,
            resume={"content": "resume markdown", "quality_score": 92},
            cover_letter={"content": "cover letter text", "quality_score": 88},
            app_questions=[{"question": "Why?", "answer": "Because."}],
            verification={"status": "PASS", "issues": []},
            cost_summary={"total_cost": 1.82, "calls": 7, "tokens": 34000},
        )

        required_keys = [
            "queue_id", "job_id", "company", "title", "composite_score",
            "classification", "one_liner", "resume", "cover_letter",
            "app_questions", "verification", "cost_summary", "match_result",
            "status", "created_at", "posting_verified_live",
        ]
        for key in required_keys:
            assert key in package, f"Missing key: {key}"

        assert package["status"] == "pending"
        assert package["composite_score"] == 8.2

    def test_package_needs_human_help(self, sample_job, sample_match):
        """Verification FAIL sets needs_human_help."""
        package = package_for_review(
            job=sample_job,
            match_result=sample_match,
            resume={},
            cover_letter=None,
            app_questions=None,
            verification={"status": "FAIL", "issues": [{"type": "HIGH"}]},
            cost_summary={},
        )
        assert package["needs_human_help"] is True


class TestGenerateOneLiner:
    def test_one_liner_generated(self, sample_match):
        """Verify non-empty summary."""
        one_liner = generate_one_liner(sample_match)
        assert len(one_liner) > 0
        assert "STRONG" in one_liner

    def test_one_liner_with_gap(self, sample_match):
        """One-liner includes gap info."""
        one_liner = generate_one_liner(sample_match)
        assert "gap" in one_liner.lower()

    def test_one_liner_no_selling_points(self):
        """Handle empty selling points gracefully."""
        match = {"classification": "WEAK", "key_selling_points": [], "gaps": []}
        one_liner = generate_one_liner(match)
        assert "WEAK" in one_liner


class TestSortQueue:
    def test_sort_deadline_first(self):
        """Entry with deadline sorts before entry without."""
        entries = [
            {"job_id": "no_deadline", "composite_score": 9.0},
            {"job_id": "has_deadline", "composite_score": 5.0, "deadline": "2026-03-01"},
        ]
        sorted_entries = sort_queue(entries)
        assert sorted_entries[0]["job_id"] == "has_deadline"

    def test_sort_score_within_deadline(self):
        """Same deadline presence, higher score first."""
        entries = [
            {"job_id": "low", "composite_score": 5.0, "deadline": "2026-03-01"},
            {"job_id": "high", "composite_score": 9.0, "deadline": "2026-02-15"},
        ]
        sorted_entries = sort_queue(entries)
        # Earlier deadline first
        assert sorted_entries[0]["job_id"] == "high"

    def test_sort_no_deadlines_by_score(self):
        """Without deadlines, sort by score descending."""
        entries = [
            {"job_id": "low", "composite_score": 4.0},
            {"job_id": "high", "composite_score": 8.0},
            {"job_id": "mid", "composite_score": 6.0},
        ]
        sorted_entries = sort_queue(entries)
        scores = [e["composite_score"] for e in sorted_entries]
        assert scores == [8.0, 6.0, 4.0]
