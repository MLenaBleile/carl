"""Tests for SkillLevelChecker."""

import json
import os
import pytest

from verification.profile_index import ProfileIndex
from verification.skill_checker import SkillLevelChecker

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
    return SkillLevelChecker(profile_index)


class TestSkillLevelChecks:
    def test_expert_claim_on_familiar_skill(self, checker):
        """'Expert in Julia' when profile has Julia as familiar -> HIGH."""
        content = "Expert in Julia for high-performance computing."
        issues = checker.check(content)
        julia_issues = [i for i in issues if i.get("skill") == "julia"]
        assert len(julia_issues) == 1
        assert julia_issues[0]["severity"] == "HIGH"
        assert julia_issues[0]["claimed_level"] == "expert"
        assert julia_issues[0]["profile_level"] == "familiar"

    def test_proficient_claim_matches(self, checker):
        """'proficient in Python' when profile has Python as proficient -> no flag."""
        content = "Proficient in Python for data analysis."
        issues = checker.check(content)
        python_issues = [i for i in issues if i.get("skill") == "python"]
        assert len(python_issues) == 0

    def test_skill_listed_without_level(self, checker):
        """'R, Python, Julia' with no level words -> no flag."""
        content = "Skills: R, Python, Julia"
        issues = checker.check(content)
        assert len(issues) == 0

    def test_skill_not_in_profile(self, checker):
        """'experienced in Rust' when Rust not in profile -> no flag.

        This is a SourceMapper concern, not a skill level concern.
        """
        content = "Experienced in Rust for systems programming."
        issues = checker.check(content)
        rust_issues = [i for i in issues if i.get("skill") == "rust"]
        assert len(rust_issues) == 0

    def test_proficient_claim_on_familiar_skill(self, checker):
        """'proficient in SQL' when profile has SQL as familiar -> MEDIUM."""
        content = "Proficient in SQL for database queries."
        issues = checker.check(content)
        sql_issues = [i for i in issues if i.get("skill") == "sql"]
        assert len(sql_issues) == 1
        assert sql_issues[0]["severity"] == "MEDIUM"

    def test_expert_claim_on_expert_skill(self, checker):
        """'Expert in SAS' when profile has SAS as expert -> no flag."""
        content = "Expert in SAS for clinical trial analysis."
        issues = checker.check(content)
        sas_issues = [i for i in issues if i.get("skill") == "sas"]
        assert len(sas_issues) == 0
