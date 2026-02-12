"""JobDeduplicator: Discovery-time dedup for job postings.

Uses URL exact match first, then embedding similarity on
title+company+description for cross-platform duplicate detection.
"""

import os
import json
import sqlite3
from difflib import SequenceMatcher


class JobDeduplicator:
    """Deduplicates job postings at discovery time.

    Uses SQLite for persistence and text similarity for matching.
    Note: Full embedding-based similarity (sentence-transformers) is
    available but we use SequenceMatcher as a lightweight fallback
    that doesn't require GPU/model loading. Can be upgraded later.
    """

    def __init__(self, db_path: str = "data/seen_jobs.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                url TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                description TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def add_seen(self, job: dict):
        """Add a job to the seen set."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO seen_jobs (url, title, company, description) VALUES (?, ?, ?, ?)",
                (
                    job.get("url", ""),
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("description", "")[:5000],  # Truncate large descriptions
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def is_duplicate(self, job: dict, similarity_threshold: float = 0.90) -> tuple[bool, str]:
        """Check if a job is a duplicate of one we've already seen.

        Returns:
            (is_duplicate, reason)
        """
        url = job.get("url", "")
        conn = sqlite3.connect(self.db_path)
        try:
            # 1. Exact URL match
            cursor = conn.execute("SELECT url FROM seen_jobs WHERE url = ?", (url,))
            if cursor.fetchone():
                return (True, "exact_url_match")

            # 2. Text similarity on title + company + description
            job_text = f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')[:500]}"
            job_text_lower = job_text.lower()

            cursor = conn.execute("SELECT url, title, company, description FROM seen_jobs")
            for row in cursor:
                seen_text = f"{row[1]} {row[2]} {row[3][:500]}".lower()
                sim = SequenceMatcher(None, job_text_lower, seen_text).ratio()
                if sim >= similarity_threshold:
                    return (True, f"text_similarity={sim:.2f} with {row[0]}")

            return (False, "")
        finally:
            conn.close()
