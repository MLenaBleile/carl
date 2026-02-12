"""TokenBudget: Tracks token usage and costs against budget limits.

Loads config from budget.yaml. Provides estimation, affordability checks,
and daily spend tracking.
"""

import yaml
from datetime import date


class TokenBudget:
    def __init__(self, config_path: str = "config/budget.yaml"):
        with open(config_path) as f:
            config = yaml.safe_load(f)

        budget = config.get("budget", {})
        self.daily_limit = budget.get("daily_limit_usd", 20.00)
        self.per_app_limit = budget.get("per_application_limit_usd", 5.00)
        self.warning_threshold = budget.get("warning_threshold", 0.80)
        self.hard_stop = budget.get("hard_stop", True)

        pricing = config.get("pricing", {})
        self.pricing = {
            "opus": {
                "input": pricing.get("opus", {}).get("input_per_mtok", 15.00),
                "output": pricing.get("opus", {}).get("output_per_mtok", 75.00),
            },
            "sonnet": {
                "input": pricing.get("sonnet", {}).get("input_per_mtok", 3.00),
                "output": pricing.get("sonnet", {}).get("output_per_mtok", 15.00),
            },
        }

        estimates = config.get("estimates", {})
        self._est_with_cl = estimates.get("with_cover_letter", 1.50)
        self._est_without_cl = estimates.get("without_cover_letter", 0.75)
        self._est_app_questions = estimates.get("app_questions", 0.02)

        # Tracking state
        self._daily_spend = 0.0
        self._run_cost = 0.0
        self._current_date = date.today()
        self._records: list[dict] = []

    def estimate(self, job: dict) -> float:
        """Estimate cost for a job application.

        Args:
            job: dict with optional "requires_cover_letter" and "application_questions" keys
        """
        cost = self._est_without_cl
        if job.get("requires_cover_letter"):
            cost = self._est_with_cl
        if job.get("application_questions"):
            cost += self._est_app_questions
        return cost

    def can_afford(self, estimated_cost: float) -> bool:
        """Check if we can afford an application within budget limits."""
        self._check_day_rollover()

        if self.hard_stop and self._daily_spend + estimated_cost > self.daily_limit:
            return False
        if estimated_cost > self.per_app_limit:
            return False
        return True

    def record(self, token_usage: dict):
        """Record token usage from an API call.

        Args:
            token_usage: dict with "input_tokens", "output_tokens", "model" keys
        """
        self._check_day_rollover()

        input_tokens = token_usage.get("input_tokens", 0)
        output_tokens = token_usage.get("output_tokens", 0)
        model = token_usage.get("model", "sonnet")

        # Determine pricing tier
        tier = "opus" if "opus" in model.lower() else "sonnet"
        pricing = self.pricing[tier]

        cost = (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
        )

        self._daily_spend += cost
        self._run_cost += cost
        self._records.append({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model,
            "cost": cost,
        })

    def get_run_cost(self) -> float:
        """Returns cost of current application run."""
        return self._run_cost

    def get_daily_spend(self) -> float:
        """Returns total spend today."""
        self._check_day_rollover()
        return self._daily_spend

    def reset_daily(self):
        """Reset daily spend counter."""
        self._daily_spend = 0.0
        self._current_date = date.today()

    def reset_run(self):
        """Reset per-application run cost."""
        self._run_cost = 0.0
        self._records = []

    def _check_day_rollover(self):
        """Auto-reset daily spend when date changes."""
        today = date.today()
        if today != self._current_date:
            self._daily_spend = 0.0
            self._current_date = today
