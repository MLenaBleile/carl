"""Tests for JobDeduplicator."""

import os
import tempfile
import pytest

from agents.dedup import JobDeduplicator


@pytest.fixture
def dedup(tmp_path):
    db_path = str(tmp_path / "test_seen_jobs.db")
    return JobDeduplicator(db_path)


class TestJobDeduplicator:
    def test_exact_url_duplicate(self, dedup):
        """Same URL -> duplicate."""
        job = {"url": "https://example.com/job/123", "title": "Data Scientist", "company": "Acme", "description": "ML role"}
        dedup.add_seen(job)

        is_dup, reason = dedup.is_duplicate(job)
        assert is_dup is True
        assert "exact_url" in reason

    def test_different_url_same_job(self, dedup):
        """Different URLs but very similar content -> duplicate via text similarity."""
        job1 = {
            "url": "https://linkedin.com/job/123",
            "title": "Senior Biostatistician",
            "company": "Sanofi",
            "description": "Lead statistical design for Phase III oncology trials",
        }
        dedup.add_seen(job1)

        job2 = {
            "url": "https://indeed.com/job/456",
            "title": "Senior Biostatistician",
            "company": "Sanofi",
            "description": "Lead statistical design for Phase III oncology trials",
        }
        is_dup, reason = dedup.is_duplicate(job2)
        assert is_dup is True
        assert "text_similarity" in reason

    def test_different_jobs_not_duplicate(self, dedup):
        """Different companies and roles -> not duplicate."""
        job1 = {
            "url": "https://example.com/job/123",
            "title": "Senior Biostatistician",
            "company": "Sanofi",
            "description": "Lead statistical design for Phase III oncology trials at a major pharma company",
        }
        dedup.add_seen(job1)

        job2 = {
            "url": "https://example.com/job/456",
            "title": "Frontend Engineer",
            "company": "Google",
            "description": "Build user interfaces for Google Cloud Platform products and services",
        }
        is_dup, reason = dedup.is_duplicate(job2)
        assert is_dup is False

    def test_empty_db_no_duplicate(self, dedup):
        """No jobs in DB -> not duplicate."""
        job = {"url": "https://example.com/job/1", "title": "Engineer", "company": "Corp", "description": "Work"}
        is_dup, reason = dedup.is_duplicate(job)
        assert is_dup is False

    def test_add_and_retrieve(self, dedup):
        """Add multiple jobs, all tracked."""
        for i in range(5):
            dedup.add_seen({
                "url": f"https://example.com/job/{i}",
                "title": f"Role {i}",
                "company": f"Company {i}",
                "description": f"Description {i}",
            })
        # All should be found by URL
        for i in range(5):
            is_dup, _ = dedup.is_duplicate({"url": f"https://example.com/job/{i}", "title": "", "company": "", "description": ""})
            assert is_dup is True
