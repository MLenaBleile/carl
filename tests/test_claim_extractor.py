"""Tests for ClaimExtractor."""

import os
import pytest

from verification.claim_extractor import ClaimExtractor

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def extractor():
    return ClaimExtractor()


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


class TestResumeExtraction:
    def test_bullets_extracted(self, extractor, good_resume):
        """good_resume.md should have >= 10 bullet-type claims."""
        claims = extractor.extract_from_resume(good_resume)
        bullet_claims = [c for c in claims if c["type"] == "bullet"]
        assert len(bullet_claims) >= 10

    def test_headers_skipped(self, extractor, good_resume):
        """No claims with type == 'section_header'."""
        claims = extractor.extract_from_resume(good_resume)
        # Headers are not included in claims at all
        for claim in claims:
            assert claim["type"] != "section_header"
        # Also verify section headers are not in the claims text
        header_texts = {"Elena Vasquez, PhD", "Experience", "Education", "Publications", "Skills"}
        claim_texts = {c["text"] for c in claims}
        assert not header_texts.intersection(claim_texts)

    def test_structural_detected(self, extractor, good_resume):
        """Company|title|date lines tagged structural."""
        claims = extractor.extract_from_resume(good_resume)
        structural = [c for c in claims if c["type"] == "structural"]
        assert len(structural) > 0
        # The bold structural lines like "**Sanofi** | Senior Biostatistician | 2021–Present"
        structural_texts = [c["text"] for c in structural]
        assert any("Sanofi" in t for t in structural_texts)

    def test_content_detected(self, extractor, good_resume):
        """Actual accomplishment lines tagged bullet or content."""
        claims = extractor.extract_from_resume(good_resume)
        content_claims = [c for c in claims if c["type"] in ("bullet", "content")]
        assert len(content_claims) >= 10

    def test_short_content_not_misclassified(self, extractor):
        """v3.1 fix: 4-word content should not be misclassified as structural.

        'Published in Nature Communications' (4 words) should be content, not structural.
        """
        resume = """# Publications

Published in Nature Communications
"""
        claims = extractor.extract_from_resume(resume)
        pub_claims = [c for c in claims if "Published in Nature Communications" in c["text"]]
        assert len(pub_claims) == 1
        assert pub_claims[0]["type"] == "content"

    def test_sections_assigned(self, extractor, good_resume):
        """Claims have correct section assignments."""
        claims = extractor.extract_from_resume(good_resume)
        sections = {c["section"] for c in claims if c["section"]}
        assert "experience" in sections
        assert "education" in sections or "publications" in sections


class TestCoverLetterExtraction:
    def test_cover_letter_sentences(self, extractor):
        """A 5-sentence paragraph should produce 5 claim units."""
        text = (
            "I have extensive experience in biostatistics. "
            "My work at Sanofi focused on adaptive trial design. "
            "I developed novel methods for subgroup analysis. "
            "The team adopted my R package across departments. "
            "I am excited about this opportunity."
        )
        claims = extractor.extract_from_cover_letter(text)
        assert len(claims) == 5
        assert all(c["type"] == "sentence" for c in claims)

    def test_cover_letter_preserves_order(self, extractor):
        """Sentences maintain correct ordering."""
        text = "First sentence. Second sentence. Third sentence."
        claims = extractor.extract_from_cover_letter(text)
        assert claims[0]["sentence_index"] == 0
        assert claims[1]["sentence_index"] == 1
        assert claims[2]["sentence_index"] == 2


class TestEdgeCases:
    def test_empty_input(self, extractor):
        """Empty string returns empty list."""
        assert extractor.extract_from_resume("") == []
        assert extractor.extract_from_cover_letter("") == []

    def test_no_section_context(self, extractor):
        """Bullets before any header have section=None."""
        resume = "- This bullet has no section header above it\n- Neither does this one"
        claims = extractor.extract_from_resume(resume)
        assert len(claims) == 2
        assert all(c["section"] is None for c in claims)

    def test_line_numbers_correct(self, extractor, good_resume):
        """Line numbers are 1-indexed and accurate."""
        claims = extractor.extract_from_resume(good_resume)
        for claim in claims:
            assert claim["line_number"] >= 1


class TestStructuralHeuristic:
    def test_pipe_separator_is_structural(self, extractor):
        """Lines with pipe separators are structural."""
        assert extractor._is_structural("**Sanofi** | Senior Biostatistician | 2021–Present")

    def test_em_dash_is_structural(self, extractor):
        """Lines with em-dash are structural."""
        assert extractor._is_structural("Sanofi — Senior Biostatistician")

    def test_date_range_is_structural(self, extractor):
        """Date range patterns are structural."""
        assert extractor._is_structural("2021–Present")
        assert extractor._is_structural("2018-2021")

    def test_short_no_punct_is_structural(self, extractor):
        """Very short lines (<=3 words) without punctuation are structural."""
        assert extractor._is_structural("Sanofi")
        assert extractor._is_structural("Research Assistant")

    def test_four_word_content_not_structural(self, extractor):
        """v3.1 fix: 4-word lines are NOT structural (threshold is 3)."""
        assert not extractor._is_structural("Published in Nature Communications")
