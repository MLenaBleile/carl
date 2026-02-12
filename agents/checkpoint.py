"""CheckpointManager: Crash recovery via per-stage checkpoint files.

Saves and loads checkpoint data for each pipeline stage, enabling
recovery from incomplete generation runs.
"""

import json
import os
import glob
from datetime import datetime


class CheckpointManager:
    def __init__(self, checkpoint_dir: str = "data/checkpoints"):
        self.checkpoint_dir = checkpoint_dir

    def save(self, job_id: str, stage: str, data: dict):
        """Save a checkpoint for a job at a specific stage.

        Writes to data/checkpoints/{job_id}/{stage}.json
        """
        job_dir = os.path.join(self.checkpoint_dir, job_id)
        os.makedirs(job_dir, exist_ok=True)

        filepath = os.path.join(job_dir, f"{stage}.json")

        # Atomic write via temp file
        tmp_path = filepath + ".tmp"
        try:
            with open(tmp_path, 'w') as f:
                json.dump({
                    "stage": stage,
                    "data": data,
                    "ts": datetime.now().isoformat(),
                }, f, indent=2, default=str)
            os.replace(tmp_path, filepath)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self, job_id: str, stage: str) -> dict | None:
        """Load a specific checkpoint."""
        filepath = os.path.join(self.checkpoint_dir, job_id, f"{stage}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath) as f:
            return json.load(f)

    def load_latest(self, job_id: str) -> dict | None:
        """Load the most recent checkpoint file for a job.

        Returns the checkpoint with the latest timestamp.
        """
        job_dir = os.path.join(self.checkpoint_dir, job_id)
        if not os.path.exists(job_dir):
            return None

        checkpoints = []
        for filepath in glob.glob(os.path.join(job_dir, "*.json")):
            try:
                with open(filepath) as f:
                    cp = json.load(f)
                    cp["_filepath"] = filepath
                    checkpoints.append(cp)
            except (json.JSONDecodeError, KeyError):
                continue

        if not checkpoints:
            return None

        # Sort by timestamp, return latest
        checkpoints.sort(key=lambda c: c.get("ts", ""), reverse=True)
        latest = checkpoints[0]
        latest.pop("_filepath", None)
        return latest

    def list_incomplete(self, state: dict) -> list[str]:
        """Scan checkpoint dir for jobs that have checkpoints but state shows 'generating'.

        Returns list of job_ids that need recovery.
        """
        if not os.path.exists(self.checkpoint_dir):
            return []

        incomplete = []
        applications = state.get("applications", {})

        for job_id in os.listdir(self.checkpoint_dir):
            job_dir = os.path.join(self.checkpoint_dir, job_id)
            if not os.path.isdir(job_dir):
                continue
            # Check if this job has checkpoints AND state shows "generating"
            app = applications.get(job_id, {})
            if app.get("status") == "generating":
                # Verify there are actual checkpoint files
                if any(f.endswith(".json") for f in os.listdir(job_dir)):
                    incomplete.append(job_id)

        return incomplete

    def cleanup(self, job_id: str):
        """Remove all checkpoints for a completed job."""
        job_dir = os.path.join(self.checkpoint_dir, job_id)
        if not os.path.exists(job_dir):
            return

        for filepath in glob.glob(os.path.join(job_dir, "*.json")):
            os.unlink(filepath)

        # Remove empty directory
        try:
            os.rmdir(job_dir)
        except OSError:
            pass

    def cleanup_old(self, state: dict, retention: str = "until_queued"):
        """Clean up checkpoints based on retention policy.

        retention="until_queued": remove checkpoints for apps that are
        no longer in "generating" status.
        """
        if not os.path.exists(self.checkpoint_dir):
            return

        applications = state.get("applications", {})

        for job_id in os.listdir(self.checkpoint_dir):
            job_dir = os.path.join(self.checkpoint_dir, job_id)
            if not os.path.isdir(job_dir):
                continue

            app = applications.get(job_id, {})
            status = app.get("status", "")

            if retention == "until_queued":
                if status not in ("generating", ""):
                    self.cleanup(job_id)
