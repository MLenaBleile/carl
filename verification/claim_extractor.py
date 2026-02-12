"""ClaimExtractor: Extracts claim units from markdown resumes and cover letters.

Each bullet point = one claim unit. Section headers are skipped.
Cover letter extraction splits on sentence boundaries.
"""

import re


class ClaimExtractor:
    def extract_from_resume(self, markdown_content: str) -> list[dict]:
        """Extract claim units from a markdown resume.

        Returns list of claim dicts with:
        - text: the claim content
        - line_number: position in source
        - section: which resume section
        - type: "bullet" | "structural" | "content"
        """
        claims = []
        lines = markdown_content.strip().split('\n')
        current_section = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('#'):
                current_section = stripped.lstrip('#').strip().lower()
                continue
            if re.match(r'^[-*•]\s+', stripped):
                claims.append({
                    "text": re.sub(r'^[-*•]\s+', '', stripped),
                    "line_number": i + 1,
                    "section": current_section,
                    "type": "bullet",
                })
            elif current_section in ("experience", "education", "publications", "skills"):
                claim_type = "structural" if self._is_structural(stripped) else "content"
                claims.append({
                    "text": stripped,
                    "line_number": i + 1,
                    "section": current_section,
                    "type": claim_type,
                })

        return claims

    def extract_from_cover_letter(self, text: str) -> list[dict]:
        """Extract claim units from a cover letter. Each sentence is one claim unit."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [
            {"text": s.strip(), "sentence_index": i, "type": "sentence"}
            for i, s in enumerate(sentences) if s.strip()
        ]

    def _is_structural(self, line: str) -> bool:
        """Determine if a line is structural (company/title/date) rather than a claim.

        v3.1 fix: reduced short-line threshold from <=4 to <=3 words to avoid
        misclassifying short content like "Published in Nature Communications".
        Added positive structural indicators.
        """
        # Positive structural indicators: pipe or em-dash separators
        if '|' in line or '—' in line or '–' in line:
            return True

        # Date range pattern
        if re.match(r'^[\d]{4}\s*[-–—]\s*([\d]{4}|[Pp]resent)', line, re.I):
            return True

        # Short lines with no sentence-ending punctuation (company names, titles)
        # v3.1 fix: threshold reduced to <=3 words (most structural headers are 1-2 words)
        if len(line.split()) <= 3 and not any(c in line for c in '.!?'):
            return True

        return False
