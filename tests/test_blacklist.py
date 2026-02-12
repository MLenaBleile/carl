"""Tests for BlacklistScanner."""

import os
import yaml
import pytest

from verification.blacklist_scanner import BlacklistScanner

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "ai_blacklist.yaml")


@pytest.fixture
def scanner():
    return BlacklistScanner(CONFIG_PATH)


@pytest.fixture
def blacklist_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


class TestPhraseDetection:
    def test_phrase_detected(self, scanner):
        """'I am writing to express my interest' -> HIGH flag."""
        issues = scanner.check("I am writing to express my interest in the position.")
        phrase_issues = [i for i in issues if i["type"] == "AI_PHRASE"]
        assert len(phrase_issues) >= 1
        assert phrase_issues[0]["severity"] == "HIGH"

    def test_phrase_case_insensitive(self, scanner):
        """'i am writing to Express My Interest' -> still flagged."""
        issues = scanner.check("i am writing to Express My Interest in this role.")
        phrase_issues = [i for i in issues if i["type"] == "AI_PHRASE"]
        assert len(phrase_issues) >= 1


class TestWordDetection:
    def test_word_detected(self, scanner):
        """'leveraged the platform' -> MEDIUM flag for 'leverage'."""
        issues = scanner.check("I leveraged the platform to improve outcomes.")
        word_issues = [i for i in issues if i["type"] == "AI_VOCABULARY" and i["text"] == "leverage"]
        assert len(word_issues) == 1
        assert word_issues[0]["severity"] == "MEDIUM"

    def test_word_base_form(self, scanner):
        """'leverage' (base form) -> flagged."""
        issues = scanner.check("We need to leverage our strengths.")
        word_issues = [i for i in issues if i["type"] == "AI_VOCABULARY" and i["text"] == "leverage"]
        assert len(word_issues) == 1

    def test_word_plural(self, scanner):
        """'leverages' -> flagged."""
        issues = scanner.check("She leverages her expertise effectively.")
        word_issues = [i for i in issues if i["type"] == "AI_VOCABULARY" and i["text"] == "leverage"]
        assert len(word_issues) == 1


class TestContextDependentExceptions:
    def test_robust_with_stats_context_exempt(self, scanner):
        """'robust regression methods' -> no flag."""
        issues = scanner.check("We used robust regression methods to handle outliers.")
        robust_issues = [i for i in issues if i.get("text") == "robust"]
        assert len(robust_issues) == 0

    def test_robust_without_context_flagged(self, scanner):
        """'a robust approach to leadership' -> MEDIUM flag."""
        issues = scanner.check("She demonstrated a robust approach to leadership.")
        robust_issues = [i for i in issues if i.get("text") == "robust"]
        assert len(robust_issues) == 1
        assert robust_issues[0]["severity"] == "MEDIUM"

    def test_robust_multiple_occurrences_mixed(self, scanner):
        """Text with 'robust regression' AND 'robust approach' -> only 1 flag."""
        text = (
            "Applied robust regression methods to the dataset. "
            "The analysis covered multiple treatment arms and endpoints across the entire trial population in a thorough manner. "
            "Also showed a robust approach to team management."
        )
        issues = scanner.check(text)
        robust_issues = [i for i in issues if i.get("text") == "robust"]
        assert len(robust_issues) == 1  # Only the non-statistical usage


class TestCleanText:
    def test_clean_text(self, scanner):
        """Professional text with no blacklisted terms -> empty issues."""
        text = (
            "Developed statistical models for clinical trial data analysis. "
            "Collaborated with cross-functional teams to deliver results. "
            "Applied Bayesian methods to subgroup identification."
        )
        issues = scanner.check(text)
        assert len(issues) == 0


class TestAllPhrases:
    def test_all_phrases_caught(self, scanner, blacklist_config):
        """Iterate through all phrases in YAML, verify each is caught."""
        for phrase in blacklist_config["phrases"]:
            text = f"The candidate said: {phrase} in the cover letter."
            issues = scanner.check(text)
            phrase_issues = [i for i in issues if i["type"] == "AI_PHRASE"]
            assert len(phrase_issues) >= 1, f"Phrase not caught: '{phrase}'"
