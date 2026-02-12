"""Tests for ApplicationDeduplicator."""

import pytest

from verification.application_dedup import ApplicationDeduplicator


@pytest.fixture
def dedup():
    return ApplicationDeduplicator()


class TestApplicationDeduplicator:
    def test_same_company_similar_title(self, dedup):
        """'Sr. Statistician' vs 'Senior Statistician' at same company -> duplicate."""
        job = {"company": "Sanofi", "title": "Sr. Statistician"}
        history = [
            {"company": "Sanofi", "title": "Senior Statistician", "status": "approved"},
        ]
        is_dup, past, sim = dedup.check(job, history)
        assert is_dup is True
        assert past is not None
        assert sim > 0.75

    def test_same_company_different_role(self, dedup):
        """'Statistician' vs 'ML Engineer' -> not duplicate."""
        job = {"company": "Sanofi", "title": "Statistician"}
        history = [
            {"company": "Sanofi", "title": "ML Engineer", "status": "approved"},
        ]
        is_dup, past, sim = dedup.check(job, history)
        assert is_dup is False

    def test_different_company(self, dedup):
        """Same title at different companies -> not duplicate."""
        job = {"company": "Moderna", "title": "Senior Statistician"}
        history = [
            {"company": "Sanofi", "title": "Senior Statistician", "status": "approved"},
        ]
        is_dup, past, sim = dedup.check(job, history)
        assert is_dup is False

    def test_skipped_apps_ignored(self, dedup):
        """Past app with status 'skipped' shouldn't trigger dup."""
        job = {"company": "Sanofi", "title": "Senior Statistician"}
        history = [
            {"company": "Sanofi", "title": "Senior Statistician", "status": "skipped"},
        ]
        is_dup, past, sim = dedup.check(job, history)
        assert is_dup is False

    def test_error_apps_ignored(self, dedup):
        """Past app with status 'error' shouldn't trigger dup."""
        job = {"company": "Sanofi", "title": "Senior Statistician"}
        history = [
            {"company": "Sanofi", "title": "Senior Statistician", "status": "error"},
        ]
        is_dup, past, sim = dedup.check(job, history)
        assert is_dup is False

    def test_empty_history(self, dedup):
        """No history -> not duplicate."""
        job = {"company": "Sanofi", "title": "Senior Statistician"}
        is_dup, past, sim = dedup.check(job, [])
        assert is_dup is False
        assert past is None
        assert sim == 0.0

    def test_multiple_past_apps(self, dedup):
        """Multiple history entries, only one matches."""
        job = {"company": "Sanofi", "title": "Senior Biostatistician"}
        history = [
            {"company": "Google", "title": "Software Engineer", "status": "approved"},
            {"company": "Moderna", "title": "Statistician", "status": "approved"},
            {"company": "Sanofi", "title": "Senior Biostatistician", "status": "approved"},
        ]
        is_dup, past, sim = dedup.check(job, history)
        assert is_dup is True
        assert past["company"] == "Sanofi"
