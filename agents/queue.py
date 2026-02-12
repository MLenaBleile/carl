"""Queue Agent: Deterministic code for packaging, sorting, and managing the review queue.

Not an LLM agent — all logic is code-based.
"""

from datetime import datetime


def package_for_review(
    job: dict,
    match_result: dict,
    resume: dict,
    cover_letter: dict | None,
    app_questions: list[dict] | None,
    verification: dict,
    cost_summary: dict,
) -> dict:
    """Package all generation results into a queue entry for human review.

    Returns the queue package dict per §4.7.
    """
    return {
        "queue_id": f"q_{job.get('job_id', 'unknown')}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "job_id": job.get("job_id", ""),
        "company": job.get("company", {}).get("name", "") if isinstance(job.get("company"), dict) else job.get("company", ""),
        "title": job.get("role", {}).get("title", "") if isinstance(job.get("role"), dict) else job.get("title", ""),
        "source_url": job.get("role", {}).get("url", "") if isinstance(job.get("role"), dict) else job.get("url", ""),
        "composite_score": match_result.get("composite_score", 0),
        "classification": match_result.get("classification", ""),
        "deadline": job.get("role", {}).get("application_deadline") if isinstance(job.get("role"), dict) else job.get("deadline"),
        "one_liner": generate_one_liner(match_result),
        "resume": resume,
        "cover_letter": cover_letter,
        "app_questions": app_questions,
        "verification": verification,
        "cost_summary": cost_summary,
        "match_result": match_result,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "posting_verified_live": True,
        "needs_human_help": verification.get("status") == "FAIL",
    }


def generate_one_liner(match_result: dict) -> str:
    """Produce the queue card summary line.

    Format: "{classification} fit — {key_selling_points[0]}; gap: {gaps[0]}"
    """
    classification = match_result.get("classification", "UNKNOWN")
    selling_points = match_result.get("key_selling_points", [])
    gaps = match_result.get("gaps", [])

    parts = [f"{classification} fit"]

    if selling_points:
        parts.append(f"— {selling_points[0]}")

    if gaps:
        parts.append(f"[gap: {gaps[0]}]")

    return " ".join(parts)


def sort_queue(entries: list[dict]) -> list[dict]:
    """Sort queue entries: deadline first, then score descending.

    Entries with deadlines sort before entries without.
    Within same deadline presence, sort by deadline ASC then score DESC.
    """
    def sort_key(entry):
        has_deadline = 1 if entry.get("deadline") else 0
        deadline = entry.get("deadline", "9999-99-99")
        score = entry.get("composite_score", 0)
        return (-has_deadline, deadline, -score)

    return sorted(entries, key=sort_key)
