"""StateManager: Persistent state management for the orchestrator.

Handles application tracking, queue management, circuit breaker,
and atomic disk persistence via temp file + rename.
"""

import json
import os
import tempfile
from datetime import datetime


DEFAULT_STATE = {
    "applications": {},
    "queue": [],
    "paused": False,
    "error_counts": {},
    "last_discovery": None,
    "last_research": None,
    "daily_stats": {
        "date": None,
        "applications_generated": 0,
        "applications_approved": 0,
        "applications_skipped": 0,
        "total_cost": 0.0,
    },
}


class StateManager:
    def __init__(self, state_path: str = "data/state.json"):
        self.state_path = state_path
        self._state = None

    def load(self) -> dict:
        """Load state from disk. Returns default state if file doesn't exist."""
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                self._state = json.load(f)
        else:
            self._state = json.loads(json.dumps(DEFAULT_STATE))
        return self._state

    def save(self):
        """Write state to disk atomically via temp file + rename."""
        if self._state is None:
            return

        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)

        # Atomic write: write to temp file, then rename
        dir_name = os.path.dirname(self.state_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self._state, f, indent=2, default=str)
            os.replace(tmp_path, self.state_path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get_state(self) -> dict:
        """Return current state, loading if needed."""
        if self._state is None:
            self.load()
        return self._state

    def update_application(self, job_id: str, **fields):
        """Update an application entry."""
        state = self.get_state()
        if job_id not in state["applications"]:
            state["applications"][job_id] = {
                "job_id": job_id,
                "created_at": datetime.now().isoformat(),
            }
        state["applications"][job_id].update(fields)
        state["applications"][job_id]["updated_at"] = datetime.now().isoformat()
        self.save()

    def get_application(self, job_id: str) -> dict | None:
        """Returns application dict or None."""
        state = self.get_state()
        return state["applications"].get(job_id)

    def add_to_queue(self, package: dict):
        """Append a package to the review queue."""
        state = self.get_state()
        state["queue"].append(package)
        self.save()

    def get_queue(self) -> list[dict]:
        """Returns pending queue entries sorted by deadline-first-then-score.

        Entries with deadlines sort before entries without.
        Within same deadline status, higher scores first.
        """
        state = self.get_state()
        queue = [e for e in state["queue"] if e.get("status", "pending") == "pending"]

        def sort_key(entry):
            has_deadline = 1 if entry.get("deadline") else 0
            deadline = entry.get("deadline", "9999-99-99")
            score = entry.get("composite_score", 0)
            # Sort: has_deadline DESC (1 first), deadline ASC, score DESC
            return (-has_deadline, deadline, -score)

        return sorted(queue, key=sort_key)

    def record_error(self, agent_name: str):
        """Increment error count. Check circuit breaker (5 failures -> paused)."""
        state = self.get_state()
        counts = state.setdefault("error_counts", {})
        counts[agent_name] = counts.get(agent_name, 0) + 1

        if counts[agent_name] >= 5:
            state["paused"] = True

        self.save()
