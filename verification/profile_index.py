"""ProfileIndex: Normalized index built from profile dict at load time.

Provides fast lookups for claim verification, number checking, and skill matching.
NOT stored on disk — built in memory from the profile JSON.
"""

import re


class ProfileIndex:
    def __init__(self, profile: dict):
        self.profile = profile

        # Experience text: id -> concatenated lowercase text
        self.experience_text = {}
        for exp in profile.get("experience", []):
            parts = [
                exp.get("title", ""),
                exp.get("organization", ""),
                " ".join(exp.get("responsibilities", [])),
                " ".join(exp.get("accomplishments", [])),
                " ".join(exp.get("tools_used", [])),
                " ".join(exp.get("keywords", [])),
            ]
            self.experience_text[exp["id"]] = " ".join(parts).lower()

        # All numbers extracted from every string field in the profile
        self.legitimate_numbers = self._extract_all_numbers()

        # All date components (years, months) from experience and education
        self.dates = self._extract_all_dates()

        # Titles and orgs: id -> string
        self.titles = {
            e["id"]: e.get("title", "") for e in profile.get("experience", [])
        }
        self.orgs = {
            e["id"]: e.get("organization", "") for e in profile.get("experience", [])
        }

        # Skills flattened: skill_name -> proficiency_level
        self.skills_flat = self._flatten_skills()

        # Publication titles: id -> title
        self.pub_titles = {
            p["id"]: p.get("title", "") for p in profile.get("publications", [])
        }

        # Derived counts
        self.derived_counts = {
            "num_publications": str(len(profile.get("publications", []))),
            "num_presentations": str(len(profile.get("presentations", []))),
        }

    def _extract_all_numbers(self) -> set:
        """Recursively walk the entire profile JSON and extract numbers from every string value."""
        numbers = set()
        self._walk_and_extract(self.profile, numbers)
        return numbers

    def _walk_and_extract(self, obj, numbers: set):
        """Recursively walk a JSON-like structure and extract numbers from strings."""
        if isinstance(obj, str):
            # Use a pattern that captures numbers with optional decimal and percent,
            # without requiring word boundary after % (since % is not a word char)
            for match in re.finditer(r'\b(\d+(?:\.\d+)?%?)', obj):
                numbers.add(match.group(1))
        elif isinstance(obj, (int, float)):
            # Handle numeric JSON values (not strings)
            if obj != 0 and obj is not True and obj is not False:
                # Store both the raw number and common string representations
                if isinstance(obj, int):
                    numbers.add(str(obj))
                else:
                    numbers.add(str(obj))
                    # Also store without trailing zeros for matching
                    if obj == int(obj):
                        numbers.add(str(int(obj)))
        elif isinstance(obj, dict):
            for value in obj.values():
                self._walk_and_extract(value, numbers)
        elif isinstance(obj, list):
            for item in obj:
                self._walk_and_extract(item, numbers)

    def _extract_all_dates(self) -> set:
        """Extract all date components from experience and education entries."""
        dates = set()

        for exp in self.profile.get("experience", []):
            for date_field in ("start_date", "end_date"):
                date_val = exp.get(date_field, "")
                if date_val:
                    # Extract year components
                    for match in re.finditer(r'\b(\d{4})\b', str(date_val)):
                        dates.add(match.group(1))
                    # Extract month components
                    for match in re.finditer(r'\b(\d{1,2})\b', str(date_val)):
                        dates.add(match.group(1))

        for edu in self.profile.get("education", []):
            year = edu.get("year_completed", "")
            if year:
                dates.add(str(year))

        # Also extract years from publications
        for pub in self.profile.get("publications", []):
            year = pub.get("year", "")
            if year:
                dates.add(str(year))

        # And from presentations
        for pres in self.profile.get("presentations", []):
            date_val = pres.get("date", "")
            if date_val:
                for match in re.finditer(r'\b(\d{4})\b', str(date_val)):
                    dates.add(match.group(1))

        return dates

    def _flatten_skills(self) -> dict:
        """Produce a dict mapping skill_name -> proficiency_level."""
        skills_flat = {}
        skills = self.profile.get("skills", {})

        # Handle programming skills with proficiency levels
        programming = skills.get("programming", {})
        if isinstance(programming, dict):
            for level, skill_list in programming.items():
                if isinstance(skill_list, list):
                    for skill in skill_list:
                        skills_flat[skill.lower()] = level

        # Handle other skill categories (flat lists without proficiency)
        for category in ("statistical_methods", "domain_expertise",
                         "tools_and_platforms", "soft_skills"):
            skill_list = skills.get(category, [])
            if isinstance(skill_list, list):
                for skill in skill_list:
                    if isinstance(skill, str):
                        skills_flat[skill.lower()] = "listed"

        return skills_flat
