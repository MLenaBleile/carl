"""NumberChecker: Context-aware number verification for generated documents.

Finds all numbers in generated text and classifies them. Only numbers that
need verification AND aren't in the profile get flagged.
"""

import re


class NumberChecker:
    def __init__(self, profile_index):
        self.index = profile_index

    def check(self, content: str) -> list[dict]:
        """Check all numbers in content against the profile.

        Returns list of issue dicts for unverified metrics.
        """
        issues = []
        for match in re.finditer(r'\b(\d+(?:\.\d+)?%?)', content):
            number = match.group(1)
            start = max(0, match.start() - 60)
            end = min(len(content), match.end() + 60)
            context = content[start:end].lower()

            classification = self._classify(number, context)
            if classification == "needs_verification" and not self._in_profile(number):
                issues.append({
                    "type": "UNVERIFIED_METRIC",
                    "severity": "HIGH",
                    "number": number,
                    "context": context.strip(),
                    "message": f"Metric '{number}' not in profile. Context: {context.strip()}",
                })

        return issues

    def _classify(self, number: str, context: str) -> str:
        """Classify a number based on its context.

        Categories:
        - exempt_date: years, date components
        - exempt_derived: counts matching profile (publications, presentations)
        - exempt_structural: experience years, page numbers
        - needs_verification: everything else
        """
        raw = number.rstrip('%')
        try:
            num_val = int(float(raw))
        except (ValueError, OverflowError):
            num_val = None

        # Dates: 4-digit years in range 1950-2030
        if num_val and 1950 <= num_val <= 2030:
            return "exempt_date"

        # Date components from profile
        if number in self.index.dates:
            return "exempt_date"

        # Numbers near month names
        month_names = (
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
            "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
        )
        if any(m in context for m in month_names):
            # Only exempt if the number looks like a day or month number
            if num_val and 1 <= num_val <= 31:
                return "exempt_date"

        # Derived counts: "N publications" where N matches profile
        if re.search(rf'{re.escape(number)}\s+publications?', context):
            if number == self.index.derived_counts.get("num_publications"):
                return "exempt_derived"

        if re.search(rf'{re.escape(number)}\s+presentations?', context):
            if number == self.index.derived_counts.get("num_presentations"):
                return "exempt_derived"

        # Experience years: "N+ years of experience/expertise"
        if re.search(rf'{re.escape(number)}\+?\s+years?\s+of\s+(experience|expertise)', context):
            return "exempt_structural"

        # Page numbers
        if re.search(r'page\s+' + re.escape(number), context):
            return "exempt_structural"

        return "needs_verification"

    def _in_profile(self, number: str) -> bool:
        """Check if a number appears anywhere in the profile."""
        return (
            number in self.index.legitimate_numbers
            or number in self.index.derived_counts.values()
        )
