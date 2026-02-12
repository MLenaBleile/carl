"""StructuralAIDetector: spaCy NLP-based detection of AI-generated text patterns.

Detects: parallel bullet patterns, tricolons, connector excess,
paragraph balance, and sentence uniformity.
"""

import re
import spacy

nlp = spacy.load("en_core_web_sm")


class StructuralAIDetector:
    def __init__(self, config: dict):
        self.max_parallel = config.get("max_consecutive_parallel_bullets", 3)
        self.max_tricolons = config.get("max_tricolon_lists", 1)
        self.max_connectors = config.get("max_connector_words_per_document", 2)
        self.connectors = set(
            w.lower() for w in config.get("connector_words", [])
        )
        self.paragraph_cv_threshold = config.get("paragraph_balance_cv_threshold", 0.15)
        self.sentence_cv_threshold = config.get("sentence_uniformity_cv_threshold", 0.20)
        self.min_sentences = config.get("min_sentences_for_uniformity", 5)

    def check(self, content: str, content_type: str = "resume") -> list[dict]:
        """Run all structural checks on content.

        Args:
            content: The text to analyze
            content_type: "resume" or "cover_letter"

        Returns list of issue dicts.
        """
        issues = []
        if content_type == "resume":
            issues.extend(self._parallel_bullets(content))
        issues.extend(self._tricolons(content))
        issues.extend(self._connector_excess(content))
        issues.extend(self._paragraph_balance(content))
        issues.extend(self._sentence_uniformity(content))
        return issues

    def _parallel_bullets(self, content: str) -> list[dict]:
        """Detect consecutive bullets with identical POS opening pattern.

        v3.1 fix: bullets are partitioned by section BEFORE checking runs.
        A section break (header line) resets the run counter.
        """
        issues = []
        lines = content.split('\n')

        # Partition bullets by section
        sections = []
        current_section_bullets = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                # Section break — save current section and start new one
                if current_section_bullets:
                    sections.append(current_section_bullets)
                current_section_bullets = []
                continue
            bullet_match = re.match(r'^[-*•]\s+(.+)$', stripped)
            if bullet_match:
                current_section_bullets.append(bullet_match.group(1))
            elif stripped and not stripped.startswith('#'):
                # Non-bullet, non-header line also breaks the section
                if current_section_bullets:
                    sections.append(current_section_bullets)
                current_section_bullets = []

        if current_section_bullets:
            sections.append(current_section_bullets)

        # Check each section independently
        for bullets in sections:
            if len(bullets) < 2:
                continue

            patterns = []
            for b in bullets:
                doc = nlp(b)
                tokens = list(doc)[:4]
                pattern = tuple(t.pos_ for t in tokens)
                patterns.append(pattern)

            run = 1
            for i in range(1, len(patterns)):
                if patterns[i] == patterns[i - 1]:
                    run += 1
                    if run > self.max_parallel:
                        issues.append({
                            "type": "PARALLEL_BULLETS",
                            "severity": "MEDIUM",
                            "message": (
                                f"{run} consecutive bullets with pattern "
                                f"{' '.join(patterns[i])}"
                            ),
                        })
                else:
                    run = 1

        return issues

    def _tricolons(self, content: str) -> list[dict]:
        """Detect "X, Y, and Z" patterns.

        v3.1: uses broader regex to catch multi-word tricolons.
        Severity is LOW since listing 3 items is sometimes natural.
        """
        issues = []
        # Broader pattern: matches multi-word items like
        # "statistical modeling, causal inference, and reinforcement learning"
        count = len(re.findall(r'([^,]+),\s+([^,]+),\s+and\s+([^,.]+)', content))
        if count > self.max_tricolons:
            issues.append({
                "type": "TRICOLON_EXCESS",
                "severity": "LOW",
                "message": f"{count} tricolon patterns (max {self.max_tricolons})",
            })
        return issues

    def _connector_excess(self, content: str) -> list[dict]:
        """Count connector words (Moreover, Furthermore, etc.)."""
        found = []
        for w in self.connectors:
            matches = re.findall(rf'\b{re.escape(w)}\b', content, re.I)
            found.extend([w] * len(matches))
        if len(found) > self.max_connectors:
            return [{
                "type": "CONNECTOR_EXCESS",
                "severity": "MEDIUM",
                "message": (
                    f"{len(found)} connectors (max {self.max_connectors}): "
                    f"{', '.join(found)}"
                ),
            }]
        return []

    def _paragraph_balance(self, content: str) -> list[dict]:
        """Check if paragraphs are suspiciously uniform in length."""
        paras = [
            p for p in content.split('\n\n')
            if p.strip() and not p.strip().startswith('#')
        ]
        if len(paras) < 3:
            return []

        lengths = [len(p.split()) for p in paras]
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return []

        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        cv = variance ** 0.5 / mean

        if cv < self.paragraph_cv_threshold:
            return [{
                "type": "PARAGRAPH_BALANCE",
                "severity": "LOW",
                "message": f"Paragraph lengths uniform (CV={cv:.2f}): {lengths}",
            }]
        return []

    def _sentence_uniformity(self, content: str) -> list[dict]:
        """Check if sentence lengths are suspiciously uniform using spaCy."""
        doc = nlp(content)
        sents = list(doc.sents)

        if len(sents) < self.min_sentences:
            return []

        lengths = [len(s) for s in sents]
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return []

        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        cv = variance ** 0.5 / mean

        if cv < self.sentence_cv_threshold:
            return [{
                "type": "SENTENCE_UNIFORMITY",
                "severity": "LOW",
                "message": f"Sentence lengths uniform (CV={cv:.2f})",
            }]
        return []
