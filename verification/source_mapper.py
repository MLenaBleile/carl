"""SourceMapper: Matches claim units against ProfileIndex to find source entries.

The KEY v3 change — source maps are built by code, not by the LLM.
Uses difflib.SequenceMatcher for similarity scoring.
"""

from difflib import SequenceMatcher


class SourceMapper:
    """Maps extracted claims to profile entries.

    Threshold tuning guidance:
    - Start at 0.30 for resume, 0.25 for cover letters
    - Run against test fixtures, count false positives vs false negatives
    - Adjust in config.yaml without code changes
    - CL threshold is lower because CL sentences mix candidate claims with
      company claims in the same sentence, deflating SequenceMatcher scores
    """

    def __init__(self, profile_index, config=None):
        self.index = profile_index
        config = config or {}
        self.resume_threshold = config.get("source_mapper_resume_threshold", 0.30)
        self.cover_letter_threshold = config.get("source_mapper_cover_letter_threshold", 0.25)

    def map_claims(self, claims, claimed_entry_ids=None, content_type="resume"):
        """For each claim, find best matching profile entry.

        claimed_entry_ids: coarse IDs from LLM (prioritizes search, not trusted blindly)
        content_type: "resume" or "cover_letter" — selects threshold
        """
        threshold = self.resume_threshold if content_type == "resume" else self.cover_letter_threshold
        results = []

        for claim in claims:
            if claim["type"] == "structural":
                results.append({
                    "claim": claim,
                    "match": self._match_structural(claim),
                    "status": "structural",
                })
                continue

            # For CL sentences that are pure company claims, skip source mapping
            if content_type == "cover_letter" and self._is_company_claim(claim["text"]):
                results.append({
                    "claim": claim,
                    "match": None,
                    "status": "company_claim_skipped",
                })
                continue

            best = self._find_best_match(claim["text"], claimed_entry_ids)
            status = "matched" if best["score"] >= threshold else "unmatched"
            entry = {"claim": claim, "match": best, "status": status}

            if status == "unmatched":
                entry["issue"] = {
                    "type": "UNGROUNDED_CLAIM",
                    "severity": "HIGH",
                    "message": (
                        f"Line {claim.get('line_number', '?')}: "
                        f"'{claim['text'][:80]}' — "
                        f"best match: {best['entry_id']} at {best['score']:.2f}"
                    ),
                }

            results.append(entry)

        return results

    def _is_company_claim(self, text):
        """Heuristic: detect pure company-claim sentences in cover letters.

        Skip sentences primarily about the company that don't contain
        candidate-specific claims. Mixed sentences (both company and candidate
        signals) are NOT skipped — they contain candidate claims that need
        verification.
        """
        text_lower = text.lower()
        company_signals = any(
            w in text_lower
            for w in ["your ", "the company", "the team", "the role", "this position"]
        )
        # Check for candidate signals — handle "I" at start of sentence too
        candidate_signals = any(
            w in text_lower
            for w in [" i ", "i've", "i'd", " my ", " we "]
        ) or text_lower.startswith("i ") or text_lower.startswith("i'")
        # Pure company claim = has company signals, no candidate signals
        return company_signals and not candidate_signals

    def _find_best_match(self, claim_text, priority_ids=None):
        """Find the best matching profile entry for a claim.

        Search priority entries first (from LLM's claimed_entry_ids),
        then all entries. Returns the best match regardless of where found.
        """
        claim_lower = claim_text.lower()
        best = {"entry_id": None, "score": 0, "matched_field": None, "matched_text": ""}

        # Build search order: priority IDs first, then all experience
        experience = self.index.profile.get("experience", [])
        if priority_ids:
            priority_set = set(priority_ids)
            ordered = (
                [e for e in experience if e["id"] in priority_set]
                + [e for e in experience if e["id"] not in priority_set]
            )
        else:
            ordered = experience

        # Search experience accomplishments + responsibilities
        for exp in ordered:
            eid = exp["id"]
            for field_name, items in [
                ("accomplishments", exp.get("accomplishments", [])),
                ("responsibilities", exp.get("responsibilities", [])),
            ]:
                for i, item in enumerate(items):
                    score = SequenceMatcher(None, claim_lower, item.lower()).ratio()
                    if score > best["score"]:
                        best = {
                            "entry_id": eid,
                            "score": score,
                            "matched_field": f"{field_name}[{i}]",
                            "matched_text": item,
                        }

        # Publications
        for pid, ptitle in self.index.pub_titles.items():
            score = SequenceMatcher(None, claim_lower, ptitle.lower()).ratio()
            if score > best["score"]:
                best = {
                    "entry_id": pid,
                    "score": score,
                    "matched_field": "title",
                    "matched_text": ptitle,
                }

        # Education
        for edu in self.index.profile.get("education", []):
            edu_text = (
                f"{edu.get('degree', '')} {edu.get('field', '')} "
                f"{edu.get('institution', '')}"
            ).lower()
            score = SequenceMatcher(None, claim_lower, edu_text).ratio()
            if score > best["score"]:
                best = {
                    "entry_id": edu["id"],
                    "score": score,
                    "matched_field": "education",
                    "matched_text": edu_text,
                }

        return best

    def _match_structural(self, claim):
        """Verify structural elements (company names, titles) against ProfileIndex."""
        text_lower = claim["text"].lower()
        best = {"entry_id": None, "score": 0, "matched_field": None, "matched_text": ""}

        # Check org names
        for eid, org in self.index.orgs.items():
            if org.lower() in text_lower:
                return {
                    "entry_id": eid,
                    "score": 1.0,
                    "matched_field": "organization",
                    "matched_text": org,
                }

        # Check titles
        for eid, title in self.index.titles.items():
            if title.lower() in text_lower:
                return {
                    "entry_id": eid,
                    "score": 1.0,
                    "matched_field": "title",
                    "matched_text": title,
                }

        # Fuzzy match as fallback
        for eid, org in self.index.orgs.items():
            score = SequenceMatcher(None, text_lower, org.lower()).ratio()
            if score > best["score"]:
                best = {
                    "entry_id": eid,
                    "score": score,
                    "matched_field": "organization",
                    "matched_text": org,
                }

        return best
