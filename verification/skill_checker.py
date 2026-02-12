"""SkillLevelChecker: Verifies skills claimed in resume don't exceed profile proficiency.

Addresses the v3.1 review gap: the Verify Agent prompt said "No skills above
proficiency level" was already checked by code, but no code did this.
"""

import re


# Proficiency levels in ascending order
LEVEL_ORDER = {
    "familiar": 1,
    "proficient": 2,
    "expert": 3,
    "listed": 2,  # Listed skills (no explicit level) treated as proficient
}

# Words indicating expertise level, mapped to their level
EXPERT_INDICATORS = [
    "expert", "advanced", "deep expertise", "extensive experience", "mastery",
]
PROFICIENT_INDICATORS = [
    "proficient", "experienced", "strong", "solid",
]
FAMILIAR_INDICATORS = [
    "familiar", "exposure", "basic", "some experience",
]


class SkillLevelChecker:
    def __init__(self, profile_index):
        self.index = profile_index

    def check(self, content: str) -> list[dict]:
        """Check if skills claimed in content exceed profile proficiency levels.

        Returns list of issue dicts for over-claimed skills.
        """
        issues = []
        content_lower = content.lower()

        for skill_name, profile_level in self.index.skills_flat.items():
            # Find skill mentions in the content
            # Use word boundary to avoid false matches (e.g., "R" in "Research")
            # For single-letter skills like "R", require surrounding context
            if len(skill_name) <= 2:
                # Short skill names need more careful matching
                pattern = rf'\b{re.escape(skill_name)}\b'
                matches = list(re.finditer(pattern, content))
            else:
                pattern = rf'\b{re.escape(skill_name)}\b'
                matches = list(re.finditer(pattern, content_lower))

            if not matches:
                continue

            for match in matches:
                # Check 10-word window around the skill mention for level indicators
                start = max(0, match.start() - 80)
                end = min(len(content), match.end() + 80)
                window = content[start:end].lower()

                claimed_level = self._detect_level(window, skill_name)
                if claimed_level is None:
                    # No level indicator found — skill is just listed, no flag
                    continue

                profile_rank = LEVEL_ORDER.get(profile_level, 2)
                claimed_rank = LEVEL_ORDER.get(claimed_level, 2)

                if claimed_rank > profile_rank:
                    severity = "HIGH" if claimed_rank - profile_rank >= 2 else "MEDIUM"
                    issues.append({
                        "type": "SKILL_LEVEL_OVERCLAIM",
                        "severity": severity,
                        "skill": skill_name,
                        "claimed_level": claimed_level,
                        "profile_level": profile_level,
                        "message": (
                            f"Skill '{skill_name}' claimed as '{claimed_level}' "
                            f"but profile says '{profile_level}'"
                        ),
                    })
                    break  # One flag per skill is enough

        return issues

    def _detect_level(self, window: str, skill_name: str) -> str | None:
        """Detect what proficiency level is being claimed in the text window.

        Returns "expert", "proficient", "familiar", or None if no indicator found.
        """
        for indicator in EXPERT_INDICATORS:
            if indicator in window:
                return "expert"

        for indicator in PROFICIENT_INDICATORS:
            if indicator in window:
                return "proficient"

        for indicator in FAMILIAR_INDICATORS:
            if indicator in window:
                return "familiar"

        return None
