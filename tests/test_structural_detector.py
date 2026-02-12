"""Tests for StructuralAIDetector."""

import os
import pytest

from verification.structural_detector import StructuralAIDetector

DEFAULT_CONFIG = {
    "max_consecutive_parallel_bullets": 3,
    "max_tricolon_lists": 1,
    "max_connector_words_per_document": 2,
    "connector_words": ["Moreover", "Furthermore", "Additionally", "Consequently", "Henceforth"],
    "paragraph_balance_cv_threshold": 0.15,
    "sentence_uniformity_cv_threshold": 0.20,
    "min_sentences_for_uniformity": 5,
}


@pytest.fixture
def detector():
    return StructuralAIDetector(DEFAULT_CONFIG)


class TestParallelBullets:
    def test_parallel_bullets_detected(self, detector):
        """5 bullets all starting with same POS pattern -> MEDIUM flag."""
        content = """# Experience

- Developed advanced machine learning models for prediction
- Developed comprehensive data pipelines for processing
- Developed innovative monitoring systems for tracking
- Developed scalable deployment solutions for production
- Developed extensive reporting dashboards for analysis
"""
        issues = detector.check(content, "resume")
        parallel = [i for i in issues if i["type"] == "PARALLEL_BULLETS"]
        assert len(parallel) > 0
        assert parallel[0]["severity"] == "MEDIUM"

    def test_parallel_bullets_within_threshold(self, detector):
        """3 bullets with same pattern (at limit of 3) -> no flag."""
        content = """# Experience

- Developed machine learning models
- Developed data pipelines quickly
- Developed testing frameworks here
"""
        issues = detector.check(content, "resume")
        parallel = [i for i in issues if i["type"] == "PARALLEL_BULLETS"]
        assert len(parallel) == 0

    def test_parallel_bullets_section_boundary_resets(self, detector):
        """3 same-pattern bullets in section A, 3 in section B -> no flag.

        v3.1 fix: run resets at section break.
        """
        content = """# Experience

- Developed machine learning models
- Developed data pipelines quickly
- Developed testing frameworks here

# Education

- Developed thesis on statistics
- Developed research methodology
- Developed analytical framework
"""
        issues = detector.check(content, "resume")
        parallel = [i for i in issues if i["type"] == "PARALLEL_BULLETS"]
        assert len(parallel) == 0


class TestTricolons:
    def test_tricolons_detected(self, detector):
        """3 "X, Y, and Z" patterns -> LOW flag (max is 1)."""
        content = (
            "Skills include modeling, analysis, and reporting. "
            "Tools include R, Python, and SAS. "
            "Methods include Bayesian, frequentist, and machine learning."
        )
        issues = detector.check(content)
        tricolon = [i for i in issues if i["type"] == "TRICOLON_EXCESS"]
        assert len(tricolon) == 1
        assert tricolon[0]["severity"] == "LOW"

    def test_multiword_tricolons_detected(self, detector):
        """Multi-word tricolons counted."""
        content = (
            "Expertise in statistical modeling, causal inference, and reinforcement learning. "
            "Also skilled in clinical trials, real-world evidence, and patient outcomes research."
        )
        issues = detector.check(content)
        tricolon = [i for i in issues if i["type"] == "TRICOLON_EXCESS"]
        assert len(tricolon) == 1


class TestConnectorExcess:
    def test_connector_excess(self, detector):
        """4 'Moreover'/'Furthermore' -> MEDIUM flag (max 2)."""
        content = (
            "The analysis was thorough. Moreover, it covered all subgroups. "
            "Furthermore, it used robust methods. "
            "Additionally, the results were validated externally. "
            "Moreover, the team published the findings."
        )
        issues = detector.check(content)
        connector = [i for i in issues if i["type"] == "CONNECTOR_EXCESS"]
        assert len(connector) == 1
        assert connector[0]["severity"] == "MEDIUM"


class TestParagraphBalance:
    def test_paragraph_balance_flagged(self, detector):
        """3 paragraphs of very similar word count -> LOW flag."""
        # Create 3 paragraphs of exactly 50 words each
        words = "word " * 50
        content = f"{words.strip()}\n\n{words.strip()}\n\n{words.strip()}"
        issues = detector.check(content)
        balance = [i for i in issues if i["type"] == "PARAGRAPH_BALANCE"]
        assert len(balance) == 1
        assert balance[0]["severity"] == "LOW"

    def test_natural_paragraph_variation(self, detector):
        """Paragraphs of 30, 80, 45 words -> no flag."""
        p1 = " ".join(["word"] * 30)
        p2 = " ".join(["word"] * 80)
        p3 = " ".join(["word"] * 45)
        content = f"{p1}\n\n{p2}\n\n{p3}"
        issues = detector.check(content)
        balance = [i for i in issues if i["type"] == "PARAGRAPH_BALANCE"]
        assert len(balance) == 0


class TestSentenceUniformity:
    def test_sentence_uniformity_flagged(self, detector):
        """6 sentences all ~same length -> LOW flag."""
        # Create sentences of very similar token count
        content = (
            "The quick brown fox jumps over the lazy dog today. "
            "The slow gray cat sleeps under the warm sun here. "
            "The tall dark man walks along the busy road now. "
            "The old wise owl sits upon the thick branch there. "
            "The new blue car drives down the long highway fast. "
            "The big red bus stops near the small station soon."
        )
        issues = detector.check(content)
        uniformity = [i for i in issues if i["type"] == "SENTENCE_UNIFORMITY"]
        assert len(uniformity) == 1
        assert uniformity[0]["severity"] == "LOW"

    def test_short_content_skipped(self, detector):
        """2 sentences -> no sentence uniformity check."""
        content = "First sentence here. Second sentence there."
        issues = detector.check(content)
        uniformity = [i for i in issues if i["type"] == "SENTENCE_UNIFORMITY"]
        assert len(uniformity) == 0


class TestResumeFull:
    def test_ai_fingerprint_resume_flagged(self, detector):
        """ai_fingerprint.md should trigger multiple structural flags."""
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "resumes")
        with open(os.path.join(fixtures_dir, "ai_fingerprint.md")) as f:
            content = f.read()
        issues = detector.check(content, "resume")
        issue_types = {i["type"] for i in issues}
        # Should detect at least parallel bullets or connectors
        assert len(issues) > 0
