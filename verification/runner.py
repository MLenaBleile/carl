"""VerificationRunner: Unified orchestration of all programmatic verification checks.

Runs ClaimExtractor, SourceMapper, NumberChecker, BlacklistScanner,
StructuralAIDetector, and SkillLevelChecker in sequence.
"""

from verification.claim_extractor import ClaimExtractor
from verification.source_mapper import SourceMapper
from verification.number_checker import NumberChecker
from verification.blacklist_scanner import BlacklistScanner
from verification.structural_detector import StructuralAIDetector
from verification.skill_checker import SkillLevelChecker


class VerificationRunner:
    def __init__(self, profile_index, config: dict):
        self.profile_index = profile_index
        self.claims = ClaimExtractor()
        self.mapper = SourceMapper(profile_index, config.get("generation", {}))
        self.numbers = NumberChecker(profile_index)
        self.blacklist = BlacklistScanner(config.get("blacklist_path", "config/ai_blacklist.yaml"))
        self.structural = StructuralAIDetector(config.get("structural_rules", {}))
        self.skill_checker = SkillLevelChecker(profile_index)

    def verify_resume(self, content: str, claimed_ids: list[str] | None = None) -> dict:
        """Run full verification pipeline on a resume.

        Returns dict with status, issues, source_map, quality_score, counts.
        """
        issues = []

        # 1. Extract claims and build source map
        claims = self.claims.extract_from_resume(content)
        source_map = self.mapper.map_claims(claims, claimed_ids, content_type="resume")
        issues.extend(r["issue"] for r in source_map if r["status"] == "unmatched")

        # 2. Number verification
        issues.extend(self.numbers.check(content))

        # 3. Blacklist scan
        issues.extend(self.blacklist.check(content))

        # 4. Structural AI detection
        issues.extend(self.structural.check(content, "resume"))

        # 5. Skill level checking
        issues.extend(self.skill_checker.check(content))

        return {
            "status": "PASS" if not any(i["severity"] == "HIGH" for i in issues) else "FAIL",
            "issues": issues,
            "source_map": source_map,
            "quality_score": self._score(issues),
            "high_count": sum(1 for i in issues if i["severity"] == "HIGH"),
            "medium_count": sum(1 for i in issues if i["severity"] == "MEDIUM"),
            "low_count": sum(1 for i in issues if i["severity"] == "LOW"),
        }

    def verify_cover_letter(
        self,
        content: str,
        claimed_ids: list[str] | None = None,
        company_facts: list[dict] | None = None,
        job_text: str = "",
    ) -> dict:
        """Run full verification pipeline on a cover letter.

        Returns dict with status, issues, source_map, quality_score.
        """
        issues = []
        company_facts = company_facts or []

        # 1. Extract claims and build source map
        claims = self.claims.extract_from_cover_letter(content)
        source_map = self.mapper.map_claims(claims, claimed_ids, content_type="cover_letter")
        issues.extend(r["issue"] for r in source_map if r["status"] == "unmatched")

        # 2. Company fact verification
        for fact in company_facts:
            if fact.get("source") == "job_posting" and fact.get("source_text"):
                if fact["source_text"].lower() not in job_text.lower():
                    issues.append({
                        "type": "UNVERIFIED_COMPANY_CLAIM",
                        "severity": "HIGH",
                        "message": f"Company claim not in posting: '{fact['claim'][:80]}'",
                    })

        # 3. Number verification
        issues.extend(self.numbers.check(content))

        # 4. Blacklist scan
        issues.extend(self.blacklist.check(content))

        # 5. Structural AI detection (cover letter mode — no parallel bullet check)
        issues.extend(self.structural.check(content, "cover_letter"))

        # 6. Skill level checking
        issues.extend(self.skill_checker.check(content))

        return {
            "status": "PASS" if not any(i["severity"] == "HIGH" for i in issues) else "FAIL",
            "issues": issues,
            "source_map": source_map,
            "quality_score": self._score(issues),
            "high_count": sum(1 for i in issues if i["severity"] == "HIGH"),
            "medium_count": sum(1 for i in issues if i["severity"] == "MEDIUM"),
            "low_count": sum(1 for i in issues if i["severity"] == "LOW"),
        }

    def verify_app_questions(
        self,
        answers: list[dict],
        profile: dict,
    ) -> dict:
        """Verify application question answers against profile.

        Simplified pipeline: check grounding, run blacklist, skip structural.
        Addresses v3.1 review finding that verify_app_questions was missing.
        """
        issues = []

        for answer in answers:
            answer_text = answer.get("answer", "")
            source = answer.get("source", "")

            # Check blacklist on each answer
            answer_issues = self.blacklist.check(answer_text)
            for issue in answer_issues:
                issue["context"] = f"Question: {answer.get('question_text', '?')}"
            issues.extend(answer_issues)

            # Flag profile_derived answers that can't be verified
            if source == "profile_derived":
                # Check if the answer text can be matched to profile content
                claims = self.claims.extract_from_cover_letter(answer_text)
                if claims:
                    source_map = self.mapper.map_claims(
                        claims, content_type="cover_letter"
                    )
                    unmatched = [r for r in source_map if r["status"] == "unmatched"]
                    for r in unmatched:
                        issues.append({
                            "type": "UNGROUNDED_APP_ANSWER",
                            "severity": "MEDIUM",
                            "message": (
                                f"Answer to '{answer.get('question_text', '?')}' "
                                f"claims profile-derived but unmatched: "
                                f"'{r['claim']['text'][:60]}'"
                            ),
                        })

        return {
            "status": "PASS" if not any(i["severity"] == "HIGH" for i in issues) else "FAIL",
            "issues": issues,
            "quality_score": self._score(issues),
            "high_count": sum(1 for i in issues if i["severity"] == "HIGH"),
            "medium_count": sum(1 for i in issues if i["severity"] == "MEDIUM"),
            "low_count": sum(1 for i in issues if i["severity"] == "LOW"),
        }

    def _score(self, issues: list[dict]) -> int:
        """Objective quality score. Higher = better.

        100 minus (HIGH * 15 + MEDIUM * 5 + LOW * 1), floor 0.
        """
        score = 100
        for i in issues:
            score -= {"HIGH": 15, "MEDIUM": 5, "LOW": 1}.get(i["severity"], 0)
        return max(0, score)
