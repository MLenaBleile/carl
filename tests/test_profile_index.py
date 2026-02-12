"""Tests for ProfileIndex."""

import json
import os
import pytest

from verification.profile_index import ProfileIndex

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def complete_profile():
    with open(os.path.join(FIXTURES_DIR, "profile_complete.json")) as f:
        return json.load(f)


@pytest.fixture
def sparse_profile():
    with open(os.path.join(FIXTURES_DIR, "profile_sparse.json")) as f:
        return json.load(f)


@pytest.fixture
def complete_index(complete_profile):
    return ProfileIndex(complete_profile)


@pytest.fixture
def sparse_index(sparse_profile):
    return ProfileIndex(sparse_profile)


class TestExperienceText:
    def test_experience_text_built_correctly(self, complete_index):
        """Verify all experience entries are indexed."""
        assert "exp_001" in complete_index.experience_text
        assert "exp_002" in complete_index.experience_text
        assert "exp_003" in complete_index.experience_text
        assert "exp_004" in complete_index.experience_text

    def test_experience_text_contains_accomplishments(self, complete_index):
        """Verify accomplishments are included in experience text."""
        text = complete_index.experience_text["exp_001"]
        assert "adaptive enrichment design" in text
        assert "22%" in text
        assert "sanofi" in text

    def test_experience_text_is_lowercase(self, complete_index):
        """Verify text is lowercased."""
        for text in complete_index.experience_text.values():
            assert text == text.lower()


class TestLegitimateNumbers:
    def test_legitimate_numbers_extracted(self, complete_index):
        """Verify numbers from accomplishments appear in legitimate_numbers."""
        # "22%" from exp_001 accomplishment
        assert "22%" in complete_index.legitimate_numbers
        # "$2.3M" -> "2.3" should be extracted
        assert "2.3" in complete_index.legitimate_numbers
        # "15 statisticians" from exp_001
        assert "15" in complete_index.legitimate_numbers
        # "3 departments" from exp_001
        assert "3" in complete_index.legitimate_numbers

    def test_numbers_from_publications(self, complete_index):
        """Verify numbers from publications are extracted."""
        # Citation counts and impact factors
        assert "47" in complete_index.legitimate_numbers
        assert "31" in complete_index.legitimate_numbers

    def test_numbers_from_nested_fields(self, complete_index):
        """Verify recursive extraction finds numbers in nested structures."""
        # Salary range numbers
        assert "160000" in complete_index.legitimate_numbers
        assert "220000" in complete_index.legitimate_numbers


class TestDates:
    def test_dates_extracted(self, complete_index):
        """Verify years from start_date/end_date/year_completed."""
        # Education years
        assert "2018" in complete_index.dates
        assert "2014" in complete_index.dates
        assert "2012" in complete_index.dates
        # Experience years
        assert "2021" in complete_index.dates
        # Publication years
        assert "2019" in complete_index.dates
        assert "2020" in complete_index.dates

    def test_presentation_dates_extracted(self, complete_index):
        """Verify years from presentation dates are included."""
        assert "2017" in complete_index.dates
        assert "2023" in complete_index.dates


class TestDerivedCounts:
    def test_derived_counts(self, complete_index):
        """Verify num_publications matches actual count."""
        assert complete_index.derived_counts["num_publications"] == "4"
        assert complete_index.derived_counts["num_presentations"] == "3"


class TestSkills:
    def test_skills_flattened(self, complete_index):
        """Verify expert/proficient/familiar levels preserved."""
        assert complete_index.skills_flat["r"] == "expert"
        assert complete_index.skills_flat["sas"] == "expert"
        assert complete_index.skills_flat["python"] == "proficient"
        assert complete_index.skills_flat["stan"] == "proficient"
        assert complete_index.skills_flat["julia"] == "familiar"
        assert complete_index.skills_flat["sql"] == "familiar"

    def test_other_skills_listed(self, complete_index):
        """Verify non-programming skills are flattened with 'listed' level."""
        assert complete_index.skills_flat["bayesian methods"] == "listed"
        assert complete_index.skills_flat["survival analysis"] == "listed"
        assert complete_index.skills_flat["clinical trial design"] == "listed"


class TestTitlesAndOrgs:
    def test_titles(self, complete_index):
        assert complete_index.titles["exp_001"] == "Senior Biostatistician"
        assert complete_index.titles["exp_002"] == "Biostatistician II"

    def test_orgs(self, complete_index):
        assert complete_index.orgs["exp_001"] == "Sanofi"
        assert complete_index.orgs["exp_002"] == "Dana-Farber Cancer Institute"


class TestPubTitles:
    def test_pub_titles(self, complete_index):
        assert "pub_001" in complete_index.pub_titles
        assert "Adaptive Enrichment" in complete_index.pub_titles["pub_001"]


class TestSparseProfile:
    def test_sparse_profile_doesnt_crash(self, sparse_index):
        """Verify ProfileIndex works with profile_sparse.json."""
        assert sparse_index is not None
        assert "exp_001" in sparse_index.experience_text
        assert sparse_index.derived_counts["num_publications"] == "0"
        assert sparse_index.derived_counts["num_presentations"] == "0"

    def test_sparse_skills(self, sparse_index):
        """Verify sparse profile skills work."""
        assert sparse_index.skills_flat["python"] == "proficient"

    def test_sparse_empty_collections(self, sparse_index):
        """Verify empty collections don't cause issues."""
        assert len(sparse_index.pub_titles) == 0
