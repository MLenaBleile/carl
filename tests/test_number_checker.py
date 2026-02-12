"""Tests for NumberChecker."""

import json
import os
import pytest

from verification.profile_index import ProfileIndex
from verification.number_checker import NumberChecker

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def complete_profile():
    with open(os.path.join(FIXTURES_DIR, "profile_complete.json")) as f:
        return json.load(f)


@pytest.fixture
def profile_index(complete_profile):
    return ProfileIndex(complete_profile)


@pytest.fixture
def checker(profile_index):
    return NumberChecker(profile_index)


class TestExemptions:
    def test_year_exempt(self, checker):
        """'2022' in resume -> no flag."""
        issues = checker.check("Worked at Sanofi from 2022 to present.")
        year_issues = [i for i in issues if i["number"] == "2022"]
        assert len(year_issues) == 0

    def test_date_from_profile_exempt(self, checker):
        """A year that appears in profile experience dates -> no flag."""
        # 2021 is in experience dates (exp_001 start_date)
        issues = checker.check("Joined the company in 2021.")
        year_issues = [i for i in issues if i["number"] == "2021"]
        assert len(year_issues) == 0

    def test_derived_count_exempt(self, checker):
        """'4 publications' when profile has 4 pubs -> no flag."""
        issues = checker.check("Author of 4 publications in peer-reviewed journals.")
        count_issues = [i for i in issues if i["number"] == "4"]
        assert len(count_issues) == 0

    def test_experience_years_exempt(self, checker):
        """'5+ years of experience' -> no flag."""
        issues = checker.check("Has 5+ years of experience in biostatistics.")
        year_issues = [i for i in issues if i["number"] == "5"]
        assert len(year_issues) == 0

    def test_experience_years_no_plus(self, checker):
        """'8 years of experience' -> no flag."""
        issues = checker.check("With 8 years of experience in clinical trials.")
        year_issues = [i for i in issues if i["number"] == "8"]
        assert len(year_issues) == 0


class TestFlagging:
    def test_unverified_metric_flagged(self, checker):
        """'reduced costs by 40%' where 40 is NOT in profile -> HIGH flag."""
        issues = checker.check("Reduced costs by 40% through process optimization.")
        flagged = [i for i in issues if i["number"] == "40%"]
        assert len(flagged) == 1
        assert flagged[0]["severity"] == "HIGH"
        assert flagged[0]["type"] == "UNVERIFIED_METRIC"

    def test_number_in_profile_passes(self, checker):
        """A number that IS in the profile -> no flag."""
        # "22%" is in the profile (exp_001 accomplishment)
        issues = checker.check("Reduced sample size by 22% through adaptive design.")
        flagged = [i for i in issues if i["number"] == "22%"]
        assert len(flagged) == 0

    def test_percentage_found(self, checker):
        """'improved accuracy by 15.5%' -> number '15.5%' extracted."""
        issues = checker.check("Improved accuracy by 15.5% using new methodology.")
        # 15.5% is not in the profile, should be flagged
        flagged = [i for i in issues if "15.5%" in i["number"]]
        assert len(flagged) == 1

    def test_profile_number_15_passes(self, checker):
        """15 is in the profile (used by 15 statisticians) -> no flag."""
        issues = checker.check("The package was used by 15 team members.")
        flagged = [i for i in issues if i["number"] == "15"]
        assert len(flagged) == 0


class TestEdgeCases:
    def test_no_numbers(self, checker):
        """Text with no numbers -> empty issues list."""
        issues = checker.check("This text contains no numbers at all.")
        assert issues == []

    def test_multiple_numbers_mixed(self, checker):
        """Mix of exempt and flagged numbers."""
        text = (
            "In 2022, reduced analysis time by 40% and managed 15 statisticians "
            "across 3 departments."
        )
        issues = checker.check(text)
        # 2022: exempt_date, 15: in profile, 3: in profile
        # 40%: NOT in profile -> flagged
        flagged_numbers = {i["number"] for i in issues}
        assert "40%" in flagged_numbers
        assert "2022" not in flagged_numbers
        assert "15" not in flagged_numbers

    def test_presentation_count(self, checker):
        """'3 presentations' when profile has 3 -> no flag."""
        issues = checker.check("Delivered 3 presentations at major conferences.")
        count_issues = [i for i in issues if i["number"] == "3"]
        assert len(count_issues) == 0
