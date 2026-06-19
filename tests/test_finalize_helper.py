"""Tests for gd-finalize-codex-watch-job.py — batch-mode atomic finalization.

The helper is invoked by codex-watch's finalize_batch_job() (:621 batch branch)
when a job's meta carries BATCH_RUN_ID (i.e. dispatched from /gd multi-wave
batch dispatch). It holds fcntl.flock on the daemon lock file for the whole
critical section: status write + event append + worker marker cleanup.

These tests pin the NORMAL completion path (done/failed). The cancel-marker
branch (stale_completed) has no creator in the codebase and is best-effort
(never triggered in practice) — not asserted here beyond "does not crash".
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).resolve().parents[1] / "vendor" / "l3-transport" / "handoff" / "bin" / "gd-finalize-codex-watch-job.py"
CWD = Path(__file__).resolve().parents[1]


def _setup_job(tmp_path: Path, raw_status: str = "done", batch_id: str = "batch-2026-001"):
    """Create a fake active job dir mimicking codex-watch layout. Returns (state_dir, base)."""
    state_dir = tmp_path / "state"
    active_dir = tmp_path / "active"
    state_dir.mkdir()
    active_dir.mkdir()
    base = active_dir / "job-001"
    base.with_suffix("").touch()  # placeholder
    # Files codex-watch creates before finalize:
    base.with_suffix(".meta").write_text(f"BATCH_RUN_ID={batch_id}\n", encoding="utf-8")
    base.with_suffix(".result").write_text("# review result", encoding="utf-8")
    base.with_suffix(".worker.running").write_text(str(os.getpid()), encoding="utf-8")
    return state_dir, base.with_suffix("")  # base = ".../job-001" (no suffix)


def _run_helper(state_dir: Path, base: Path, raw_status: str, batch_id: str = "batch-2026-001", worker_pid: int = 99999):
    """Invoke the helper exactly like finalize_batch_job does (subprocess python3)."""
    return subprocess.run(
        [
            sys.executable, str(HELPER),
            "--base", str(base),
            "--batch-run-id", batch_id,
            "--queue-job-id", "job-001",
            "--raw-status", raw_status,
            "--result-tmp", "",
            "--state-dir", str(state_dir),
            "--worker-pid", str(worker_pid),
        ],
        capture_output=True, text=True, timeout=30,
    )


def test_finalize_done_writes_status_file(tmp_path):
    """raw_status=done → ${base}.status contains 'done' (legacy byte-exact)."""
    state_dir, base = _setup_job(tmp_path, raw_status="done")
    r = _run_helper(state_dir, base, raw_status="done")
    assert r.returncode == 0, f"helper failed: {r.stderr}"
    assert Path(str(base) + ".status").read_text().strip() == "done"


def test_finalize_failed_writes_status_file(tmp_path):
    """raw_status=failed → ${base}.status contains 'failed'."""
    state_dir, base = _setup_job(tmp_path, raw_status="failed")
    r = _run_helper(state_dir, base, raw_status="failed")
    assert r.returncode == 0, f"helper failed: {r.stderr}"
    assert Path(str(base) + ".status").read_text().strip() == "failed"


def test_finalize_appends_event_jsonl(tmp_path):
    """Batch finalize appends one JSON line to ${state}/${batch_id}.events.jsonl."""
    batch_id = "batch-2026-001"
    state_dir, base = _setup_job(tmp_path, batch_id=batch_id)
    r = _run_helper(state_dir, base, raw_status="done")
    assert r.returncode == 0, f"helper failed: {r.stderr}"
    events_file = state_dir / f"{batch_id}.events.jsonl"
    assert events_file.exists(), "events.jsonl not created"
    lines = [json.loads(l) for l in events_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 1, f"expected 1 event, got {len(lines)}: {lines}"
    ev = lines[0]
    assert ev["batch_run_id"] == batch_id
    assert ev["queue_job_id"] == "job-001"
    assert ev["event_type"] == "finished"  # done → finished event
    assert ev["status"] == "done"
    assert "recorded_at" in ev
    assert "running_count_after_event" in ev


def test_finalize_cleans_worker_running_marker(tmp_path):
    """Batch finalize removes ${base}.worker.running marker (legacy parity with :627)."""
    state_dir, base = _setup_job(tmp_path)
    worker_marker = Path(str(base) + ".worker.running")
    assert worker_marker.exists(), "precondition: worker marker present"
    r = _run_helper(state_dir, base, raw_status="done")
    assert r.returncode == 0, f"helper failed: {r.stderr}"
    assert not worker_marker.exists(), "worker.running marker not cleaned"


def test_finalize_uses_flock_no_corrupt(tmp_path):
    """Two concurrent finalizes on DIFFERENT bases must both succeed (flock on shared daemon lock, not per-job)."""
    state_dir = tmp_path / "state"
    active = tmp_path / "active"
    state_dir.mkdir(); active.mkdir()
    results = []
    import threading

    def run_one(job_suffix: str):
        b = active / f"job-{job_suffix}"
        b.with_suffix("").touch()
        b.with_suffix(".meta").write_text("BATCH_RUN_ID=batch-shared\n", encoding="utf-8")
        b.with_suffix(".result").write_text("ok", encoding="utf-8")
        b.with_suffix(".worker.running").write_text("1", encoding="utf-8")
        rc = _run_helper(state_dir, b.with_suffix(""), raw_status="done", batch_id="batch-shared")
        results.append((job_suffix, rc.returncode, rc.stderr))

    threads = [threading.Thread(target=run_one, args=(s,)) for s in ("a", "b")]
    for t in threads: t.start()
    for t in threads: t.join()
    for job_suffix, rc, err in results:
        assert rc == 0, f"job {job_suffix} failed under concurrency: {err}"
    # Both status files written, both events appended
    events = (state_dir / "batch-shared.events.jsonl").read_text().splitlines()
    assert len([l for l in events if l.strip()]) == 2


def test_finalize_missing_state_dir_fails_clean(tmp_path):
    """Helper must not crash with traceback if state-dir missing — clear exit code."""
    base = tmp_path / "active" / "job-x"
    base.parent.mkdir(parents=True)
    base.touch()
    base.with_suffix(".meta").write_text("BATCH_RUN_ID=batch-x\n", encoding="utf-8")
    base.with_suffix(".worker.running").write_text("1", encoding="utf-8")
    r = _run_helper(tmp_path / "nonexistent-state", base, raw_status="done", batch_id="batch-x")
    assert r.returncode != 0, "should fail when state-dir missing"
