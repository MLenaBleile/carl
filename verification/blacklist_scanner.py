"""BlacklistScanner: Checks for AI-telltale vocabulary and phrases.

Supports exact phrase matching, word-boundary matching with common inflections,
and context-dependent exceptions (e.g., "robust" exempt in statistical context).
"""

import re
import yaml


class BlacklistScanner:
    def __init__(self, path: str = "config/ai_blacklist.yaml"):
        with open(path) as f:
            config = yaml.safe_load(f)
        self.words = config.get("words", [])
        self.phrases = config.get("phrases", [])
        self.context_dependent = config.get("context_dependent", {})

    def check(self, content: str) -> list[dict]:
        """Scan content for blacklisted phrases and words.

        Returns list of issue dicts with type, severity, text, message.
        """
        issues = []
        content_lower = content.lower()

        # Phrase matching: exact substring, case-insensitive (HIGH severity)
        for phrase in self.phrases:
            if phrase.lower() in content_lower:
                issues.append({
                    "type": "AI_PHRASE",
                    "severity": "HIGH",
                    "text": phrase,
                    "message": f"Blacklisted phrase: '{phrase}'",
                })

        # Word matching: word-boundary regex with common inflections (MEDIUM severity)
        for word in self.words:
            word_lower = word.lower()

            # Build regex pattern that matches the word plus common suffixes
            # e.g., "leverage" matches "leverage", "leveraged", "leverages"
            pattern = rf'\b{re.escape(word_lower)}[ds]?\b'

            if not re.search(pattern, content_lower):
                continue

            if word_lower in self.context_dependent:
                # Context-dependent: check each occurrence independently
                exceptions = self.context_dependent[word_lower]
                for m in re.finditer(pattern, content, re.I):
                    window_start = max(0, m.start() - 80)
                    window_end = min(len(content), m.end() + 80)
                    window = content[window_start:window_end].lower()
                    if not any(t.lower() in window for t in exceptions):
                        issues.append({
                            "type": "AI_VOCABULARY",
                            "severity": "MEDIUM",
                            "text": word,
                            "message": f"Blacklisted: '{word}' (no exception context)",
                        })
            else:
                # Non-context-dependent: flag each occurrence
                for _ in re.finditer(pattern, content, re.I):
                    issues.append({
                        "type": "AI_VOCABULARY",
                        "severity": "MEDIUM",
                        "text": word,
                        "message": f"Blacklisted: '{word}'",
                    })

        return issues
