"""Tests for StateManager."""

import json
import os
import pytest

from agents.state import StateManager


@pytest.fixture
def state_mgr(tmp_path):
    path = str(tmp_path / "state.json")
    return StateManager(path)


class TestStateManager:
    def test_load_creates_default(self, state_mgr):
        """When no file exists, returns valid default state."""
        state = state_mgr.load()
        assert "applications" in state
        assert "queue" in state
        assert state["paused"] is False
        assert isinstance(state["applications"], dict)
        assert isinstance(state["queue"], list)

    def test_save_and_reload(self, state_mgr):
        """Save state, reload, verify identical."""
        state = state_mgr.load()
        state["applications"]["job_1"] = {"status": "queued", "score": 7.5}
        state_mgr.save()

        # Create new manager pointing to same file
        mgr2 = StateManager(state_mgr.state_path)
        state2 = mgr2.load()
        assert state2["applications"]["job_1"]["score"] == 7.5

    def test_update_application(self, state_mgr):
        """Update fields, verify persisted."""
        state_mgr.load()
        state_mgr.update_application("job_1", status="generating", score=8.0)

        app = state_mgr.get_application("job_1")
        assert app["status"] == "generating"
        assert app["score"] == 8.0
        assert "created_at" in app
        assert "updated_at" in app

        # Verify persisted to disk
        mgr2 = StateManager(state_mgr.state_path)
        state2 = mgr2.load()
        assert state2["applications"]["job_1"]["status"] == "generating"

    def test_update_application_preserves_fields(self, state_mgr):
        """Updating specific fields doesn't remove others."""
        state_mgr.load()
        state_mgr.update_application("job_1", status="generating", score=8.0)
        state_mgr.update_application("job_1", status="queued")

        app = state_mgr.get_application("job_1")
        assert app["status"] == "queued"
        assert app["score"] == 8.0  # Preserved

    def test_get_application_missing(self, state_mgr):
        """Non-existent job returns None."""
        state_mgr.load()
        assert state_mgr.get_application("nonexistent") is None

    def test_queue_sorting(self, state_mgr):
        """Entries with deadlines sort before entries without; higher scores first."""
        state_mgr.load()
        state_mgr.add_to_queue({
            "job_id": "no_deadline_high",
            "composite_score": 9.0,
            "status": "pending",
        })
        state_mgr.add_to_queue({
            "job_id": "deadline_low",
            "composite_score": 5.0,
            "deadline": "2026-03-01",
            "status": "pending",
        })
        state_mgr.add_to_queue({
            "job_id": "deadline_high",
            "composite_score": 8.0,
            "deadline": "2026-02-15",
            "status": "pending",
        })
        state_mgr.add_to_queue({
            "job_id": "no_deadline_low",
            "composite_score": 4.0,
            "status": "pending",
        })

        queue = state_mgr.get_queue()
        job_ids = [e["job_id"] for e in queue]

        # Deadline entries first (earlier deadline first)
        assert job_ids.index("deadline_high") < job_ids.index("no_deadline_high")
        assert job_ids.index("deadline_low") < job_ids.index("no_deadline_high")
        # Earlier deadline before later
        assert job_ids.index("deadline_high") < job_ids.index("deadline_low")
        # No-deadline entries sorted by score descending
        assert job_ids.index("no_deadline_high") < job_ids.index("no_deadline_low")

    def test_circuit_breaker(self, state_mgr):
        """5 errors -> state.paused = True."""
        state_mgr.load()
        for _ in range(4):
            state_mgr.record_error("resume_agent")
        assert state_mgr.get_state()["paused"] is False

        state_mgr.record_error("resume_agent")
        assert state_mgr.get_state()["paused"] is True
