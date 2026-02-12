"""ApplicationDeduplicator: Prevents duplicate applications to same company/role.

Uses SequenceMatcher on company name + title at submission time.
"""

from difflib import SequenceMatcher


class ApplicationDeduplicator:
    """Checks if we already applied to a similar role at the same company.

    Different from the discovery-time JobDeduplicator — this operates at
    submission time and uses title-based matching rather than embeddings.
    """

    def __init__(self, company_threshold: float = 0.80, title_threshold: float = 0.75):
        self.company_threshold = company_threshold
        self.title_threshold = title_threshold

    def check(
        self, job: dict, application_history: list[dict]
    ) -> tuple[bool, dict | None, float]:
        """Check if a job duplicates a past application.

        Args:
            job: dict with "company" and "title" keys
            application_history: list of past application dicts with
                "company", "title", and "status" keys

        Returns:
            (is_duplicate, past_application, title_similarity)
        """
        job_company = job.get("company", "").lower()
        job_title = job.get("title", "").lower()

        for past in application_history:
            # Skip past applications with terminal non-success states
            if past.get("status") in ("skipped", "error"):
                continue

            past_company = past.get("company", "").lower()
            company_sim = SequenceMatcher(None, job_company, past_company).ratio()

            if company_sim < self.company_threshold:
                continue

            past_title = past.get("title", "").lower()
            title_sim = SequenceMatcher(None, job_title, past_title).ratio()

            if title_sim > self.title_threshold:
                return (True, past, title_sim)

        return (False, None, 0.0)
