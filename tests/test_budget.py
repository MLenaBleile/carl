"""Tests for TokenBudget."""

import os
import pytest

from agents.budget import TokenBudget

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "budget.yaml")


@pytest.fixture
def budget():
    return TokenBudget(CONFIG_PATH)


class TestEstimate:
    def test_estimate_with_cover_letter(self, budget):
        """Should be ~$1.50."""
        job = {"requires_cover_letter": True}
        est = budget.estimate(job)
        assert 1.0 <= est <= 2.0

    def test_estimate_without_cover_letter(self, budget):
        """Should be ~$0.75."""
        job = {"requires_cover_letter": False}
        est = budget.estimate(job)
        assert 0.5 <= est <= 1.0

    def test_estimate_with_app_questions(self, budget):
        """App questions add a small amount."""
        job_base = {"requires_cover_letter": True, "application_questions": None}
        job_aq = {"requires_cover_letter": True, "application_questions": [{"q": "why?"}]}
        base_est = budget.estimate(job_base)
        aq_est = budget.estimate(job_aq)
        assert aq_est > base_est


class TestCanAfford:
    def test_can_afford_within_budget(self, budget):
        """Returns True when within budget."""
        assert budget.can_afford(1.50) is True

    def test_can_afford_over_daily_limit(self, budget):
        """Returns False after spending too much."""
        # Simulate spending up to the limit
        budget._daily_spend = 19.50
        assert budget.can_afford(1.50) is False

    def test_can_afford_over_per_app_limit(self, budget):
        """Returns False if estimate exceeds per-app limit."""
        assert budget.can_afford(10.00) is False  # per_app_limit is 5.00


class TestRecord:
    def test_record_accumulates(self, budget):
        """Multiple records sum correctly."""
        budget.record({
            "input_tokens": 1000,
            "output_tokens": 500,
            "model": "claude-sonnet-4-5-20250929",
        })
        budget.record({
            "input_tokens": 2000,
            "output_tokens": 1000,
            "model": "claude-sonnet-4-5-20250929",
        })
        assert budget.get_daily_spend() > 0
        assert budget.get_run_cost() > 0
        assert len(budget._records) == 2

    def test_record_opus_pricing(self, budget):
        """Opus pricing is higher than Sonnet."""
        budget_opus = TokenBudget(CONFIG_PATH)
        budget_sonnet = TokenBudget(CONFIG_PATH)

        tokens = {"input_tokens": 10000, "output_tokens": 5000}

        budget_opus.record({**tokens, "model": "claude-opus-4-6"})
        budget_sonnet.record({**tokens, "model": "claude-sonnet-4-5-20250929"})

        assert budget_opus.get_run_cost() > budget_sonnet.get_run_cost()

    def test_daily_reset(self, budget):
        """Spend resets to 0."""
        budget.record({
            "input_tokens": 10000,
            "output_tokens": 5000,
            "model": "claude-sonnet-4-5-20250929",
        })
        assert budget.get_daily_spend() > 0

        budget.reset_daily()
        assert budget.get_daily_spend() == 0.0

    def test_run_reset(self, budget):
        """Run cost resets independently of daily spend."""
        budget.record({
            "input_tokens": 10000,
            "output_tokens": 5000,
            "model": "claude-sonnet-4-5-20250929",
        })
        daily_before = budget.get_daily_spend()

        budget.reset_run()
        assert budget.get_run_cost() == 0.0
        # Daily spend unaffected
        assert budget.get_daily_spend() == daily_before
