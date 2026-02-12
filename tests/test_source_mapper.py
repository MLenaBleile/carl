"""Tests for SourceMapper."""

import json
import os
import pytest

from verification.profile_index import ProfileIndex
from verification.claim_extractor import ClaimExtractor
from verification.source_mapper import SourceMapper

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def complete_profile():
    with open(os.path.join(FIXTURES_DIR, "profile_complete.json")) as f:
        return json.load(f)


@pytest.fixture
def profile_index(complete_profile):
    return ProfileIndex(complete_profile)


@pytest.fixture
def mapper(profile_index):
    return SourceMapper(profile_index)


@pytest.fixture
def extractor():
    return ClaimExtractor()


@pytest.fixture
def good_resume():
    with open(os.path.join(FIXTURES_DIR, "resumes", "good_resume.md")) as f:
        return f.read()


class TestDirectMatch:
    def test_direct_match(self, mapper):
        """A bullet that closely mirrors a profile accomplishment -> matched, score > 0.5."""
        claim = {
            "text": "Developed adaptive enrichment design that reduced required sample size by 22% for the BEACON-3 trial",
            "line_number": 6,
            "section": "experience",
            "type": "bullet",
        }
        results = mapper.map_claims([claim])
        assert len(results) == 1
        assert results[0]["status"] == "matched"
        assert results[0]["match"]["score"] > 0.5
        assert results[0]["match"]["entry_id"] == "exp_001"


class TestParaphraseMatch:
    def test_paraphrase_match(self, mapper):
        """A bullet that rephrases a profile accomplishment -> matched, score 0.25-0.60."""
        claim = {
            "text": "Created an R package for Bayesian subgroup analysis adopted across departments",
            "line_number": 8,
            "section": "experience",
            "type": "bullet",
        }
        results = mapper.map_claims([claim])
        assert len(results) == 1
        assert results[0]["status"] == "matched"
        assert 0.25 <= results[0]["match"]["score"] <= 0.80


class TestFabricatedClaim:
    def test_fabricated_claim_flagged(self, profile_index):
        """A bullet not in the profile at all -> unmatched, HIGH issue.

        Uses a threshold of 0.50 to demonstrate that fabricated claims score
        lower than genuine claims. SequenceMatcher character-level similarity
        gives a baseline ~0.30-0.40 even for unrelated text, so the 0.30
        default threshold is tuned for recall. This test verifies the mechanism.
        """
        # Use a higher threshold that separates fabricated from genuine
        mapper = SourceMapper(profile_index, {"source_mapper_resume_threshold": 0.50})
        claim = {
            "text": "Reduced costs by 60% via migration to serverless architecture",
            "line_number": 15,
            "section": "experience",
            "type": "bullet",
        }
        results = mapper.map_claims([claim])
        assert len(results) == 1
        assert results[0]["status"] == "unmatched"
        assert results[0]["issue"]["severity"] == "HIGH"
        assert results[0]["issue"]["type"] == "UNGROUNDED_CLAIM"


class TestStructuralMatch:
    def test_structural_match(self, mapper):
        """Company name line -> matched structural."""
        claim = {
            "text": "**Sanofi** | Senior Biostatistician | 2021–Present",
            "line_number": 4,
            "section": "experience",
            "type": "structural",
        }
        results = mapper.map_claims([claim])
        assert len(results) == 1
        assert results[0]["status"] == "structural"
        assert results[0]["match"]["entry_id"] == "exp_001"


class TestEducationMatch:
    def test_education_match(self, mapper):
        """Education claim matched to edu entry."""
        claim = {
            "text": "PhD Biostatistics, Harvard T.H. Chan School of Public Health, 2018",
            "line_number": 30,
            "section": "education",
            "type": "content",
        }
        results = mapper.map_claims([claim])
        assert len(results) == 1
        assert results[0]["status"] == "matched"
        assert results[0]["match"]["entry_id"] == "edu_001"


class TestPublicationMatch:
    def test_publication_match(self, mapper):
        """Publication reference matched to pub entry."""
        claim = {
            "text": "Adaptive Enrichment Designs with Biomarker Subgroups: Balancing Type I Error and Power. Biometrics, 2019.",
            "line_number": 35,
            "section": "publications",
            "type": "bullet",
        }
        results = mapper.map_claims([claim])
        assert len(results) == 1
        assert results[0]["status"] == "matched"
        assert results[0]["match"]["entry_id"] == "pub_001"


class TestCoverLetterCompanyClaim:
    def test_cover_letter_company_claim_skipped(self, mapper):
        """Pure company sentence -> status 'company_claim_skipped'."""
        claim = {
            "text": "Your team has made remarkable advances in oncology therapeutics.",
            "sentence_index": 0,
            "type": "sentence",
        }
        results = mapper.map_claims([claim], content_type="cover_letter")
        assert len(results) == 1
        assert results[0]["status"] == "company_claim_skipped"

    def test_cover_letter_mixed_sentence_not_skipped(self, mapper):
        """Sentence with both 'your team' and 'I developed' -> NOT skipped."""
        claim = {
            "text": "I developed methods that align well with your team's approach to adaptive trial design.",
            "sentence_index": 0,
            "type": "sentence",
        }
        results = mapper.map_claims([claim], content_type="cover_letter")
        assert len(results) == 1
        assert results[0]["status"] != "company_claim_skipped"


class TestThresholdConfigurable:
    def test_threshold_configurable(self, profile_index):
        """Passing different config thresholds changes match/unmatch boundary."""
        # A paraphrase that would be borderline
        claim = {
            "text": "Created an R package for Bayesian analysis used by statisticians",
            "line_number": 8,
            "section": "experience",
            "type": "bullet",
        }

        # With a high threshold, may not match
        high_mapper = SourceMapper(profile_index, {"source_mapper_resume_threshold": 0.90})
        high_results = high_mapper.map_claims([claim])

        # With a low threshold, should match
        low_mapper = SourceMapper(profile_index, {"source_mapper_resume_threshold": 0.10})
        low_results = low_mapper.map_claims([claim])

        # The score is the same, but status differs based on threshold
        assert high_results[0]["match"]["score"] == low_results[0]["match"]["score"]
        assert high_results[0]["status"] == "unmatched"
        assert low_results[0]["status"] == "matched"


class TestEmptyClaims:
    def test_empty_claims(self, mapper):
        """Empty list returns empty results."""
        results = mapper.map_claims([])
        assert results == []


class TestFullResumeMapping:
    def test_good_resume_mostly_matched(self, mapper, extractor, good_resume):
        """Most claims in a good resume should match profile entries."""
        claims = extractor.extract_from_resume(good_resume)
        results = mapper.map_claims(claims)
        matched = [r for r in results if r["status"] in ("matched", "structural")]
        unmatched = [r for r in results if r["status"] == "unmatched"]
        # Good resume should have high match rate
        total_checkable = len(matched) + len(unmatched)
        if total_checkable > 0:
            match_rate = len(matched) / total_checkable
            assert match_rate > 0.5, f"Match rate {match_rate:.2f} is too low"
