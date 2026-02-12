"""Tests for CheckpointManager."""

import json
import os
import time
import pytest

from agents.checkpoint import CheckpointManager


@pytest.fixture
def cp_mgr(tmp_path):
    return CheckpointManager(str(tmp_path / "checkpoints"))


class TestCheckpointManager:
    def test_save_and_load(self, cp_mgr):
        """Save checkpoint, load it back."""
        data = {"content": "resume text", "score": 85}
        cp_mgr.save("job_1", "resume_iter_0", data)

        loaded = cp_mgr.load("job_1", "resume_iter_0")
        assert loaded is not None
        assert loaded["data"]["content"] == "resume text"
        assert loaded["data"]["score"] == 85
        assert loaded["stage"] == "resume_iter_0"
        assert "ts" in loaded

    def test_load_latest(self, cp_mgr):
        """Save 3 checkpoints for same job, load_latest returns the last one."""
        cp_mgr.save("job_1", "resume_iter_0", {"score": 60})
        time.sleep(0.01)
        cp_mgr.save("job_1", "resume_iter_1", {"score": 75})
        time.sleep(0.01)
        cp_mgr.save("job_1", "resume_iter_2", {"score": 85})

        latest = cp_mgr.load_latest("job_1")
        assert latest is not None
        assert latest["stage"] == "resume_iter_2"
        assert latest["data"]["score"] == 85

    def test_load_latest_nonexistent(self, cp_mgr):
        """Non-existent job returns None."""
        assert cp_mgr.load_latest("nonexistent") is None

    def test_list_incomplete(self, cp_mgr):
        """Create checkpoints + state with 'generating' status, verify listed."""
        cp_mgr.save("job_1", "resume_iter_0", {"score": 60})
        cp_mgr.save("job_2", "resume_iter_0", {"score": 70})

        state = {
            "applications": {
                "job_1": {"status": "generating"},
                "job_2": {"status": "queued"},
                "job_3": {"status": "generating"},  # No checkpoints
            }
        }

        incomplete = cp_mgr.list_incomplete(state)
        assert "job_1" in incomplete  # Has checkpoints + generating
        assert "job_2" not in incomplete  # Not generating
        assert "job_3" not in incomplete  # No checkpoints

    def test_cleanup(self, cp_mgr):
        """Cleanup removes checkpoint directory."""
        cp_mgr.save("job_1", "resume_iter_0", {"score": 60})
        cp_mgr.save("job_1", "resume_iter_1", {"score": 75})

        job_dir = os.path.join(cp_mgr.checkpoint_dir, "job_1")
        assert os.path.exists(job_dir)

        cp_mgr.cleanup("job_1")
        assert not os.path.exists(job_dir)

    def test_cleanup_nonexistent(self, cp_mgr):
        """Cleanup on non-existent job doesn't error."""
        cp_mgr.cleanup("nonexistent")  # Should not raise

    def test_atomic_write(self, cp_mgr):
        """Verify save uses temp file (check no .tmp files left)."""
        cp_mgr.save("job_1", "resume_iter_0", {"score": 60})

        job_dir = os.path.join(cp_mgr.checkpoint_dir, "job_1")
        files = os.listdir(job_dir)
        # No .tmp files should remain
        tmp_files = [f for f in files if f.endswith(".tmp")]
        assert len(tmp_files) == 0
        # The checkpoint file should exist
        assert "resume_iter_0.json" in files

    def test_cleanup_old(self, cp_mgr):
        """cleanup_old removes checkpoints for non-generating apps."""
        cp_mgr.save("job_1", "resume", {"score": 60})
        cp_mgr.save("job_2", "resume", {"score": 70})
        cp_mgr.save("job_3", "resume", {"score": 80})

        state = {
            "applications": {
                "job_1": {"status": "generating"},
                "job_2": {"status": "queued"},
                "job_3": {"status": "approved"},
            }
        }

        cp_mgr.cleanup_old(state, retention="until_queued")

        # job_1 still generating -> keep checkpoints
        assert os.path.exists(os.path.join(cp_mgr.checkpoint_dir, "job_1"))
        # job_2 and job_3 not generating -> cleaned up
        assert not os.path.exists(os.path.join(cp_mgr.checkpoint_dir, "job_2"))
        assert not os.path.exists(os.path.join(cp_mgr.checkpoint_dir, "job_3"))
