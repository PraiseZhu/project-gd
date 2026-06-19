#!/usr/bin/env python3
"""gd-finalize-codex-watch-job.py — batch-mode atomic finalization.

Invoked by codex-watch's finalize_batch_job (:621 batch branch) when a job's
meta carries BATCH_RUN_ID (dispatched from /gd multi-wave batch dispatch).
Holds fcntl.flock on the daemon lock file for the whole critical section:
status write + event append + worker marker cleanup.

Normal path: raw_status in {done, failed}.
Cancel-marker branch is best-effort — the cancel marker (``<base>.cancel``)
has no creator in the current codebase, so ``stale_completed`` never triggers;
handled defensively per design intent (:621 comment) but result rename is a
TODO until the cancel protocol is implemented.

Args mirror finalize_batch_job's invocation exactly:
  --base --batch-run-id --queue-job-id --raw-status --result-tmp
  --state-dir --worker-pid
"""
import argparse
import fcntl
import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# status-file enum  →  event-log enum (see codex-watch :622-623)
_EVENT_TYPE = {
    "done": "finished",
    "failed": "failed",
    "stale_completed": "stale_completed",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _count_running(state_dir: Path) -> int:
    """Best-effort count of *.worker.running markers.

    The active jobs dir is a sibling of HANDOFF_STATE in the current layout; the
    helper only receives --state-dir, so we glob the most likely locations. This
    only feeds running_count_after_event (observability), not correctness.
    """
    seen = set()
    for pat in (
        str(state_dir / "*.worker.running"),
        str(state_dir.parent / "active" / "*.worker.running"),
    ):
        seen.update(glob.glob(pat))
    return len(seen)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True)
    p.add_argument("--batch-run-id", required=True)
    p.add_argument("--queue-job-id", required=True)
    p.add_argument("--raw-status", required=True)
    p.add_argument("--result-tmp", default="")
    p.add_argument("--state-dir", required=True)
    p.add_argument("--worker-pid", required=True)
    args = p.parse_args()

    state_dir = Path(args.state_dir)
    lock_file = state_dir / "codex-watch.lock"
    base = Path(args.base)
    worker_marker = Path(str(base) + ".worker.running")

    # Cancel marker (best-effort, never triggered today): stale_completed if present.
    cancel_marker = Path(str(base) + ".cancel")
    final_status = "stale_completed" if cancel_marker.exists() else args.raw_status
    event_type = _EVENT_TYPE.get(final_status, "finished")

    # Acquire daemon-wide lock for the whole critical section (P1-1 fix).
    # state_dir is assumed to exist (daemon deploys it); missing → clean fail.
    try:
        lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except OSError as e:
        print(f"[finalize] FATAL: cannot acquire lock {lock_file}: {e}", file=sys.stderr)
        return 2

    try:
        # 1. status file write — legacy byte-exact (just the enum string).
        Path(str(base) + ".status").write_text(final_status, encoding="utf-8")

        # 2. event log append — mirrors emit_event's JSON record schema.
        running_count = max(0, _count_running(state_dir) - 1)  # this job is ending
        record = {
            "batch_run_id": args.batch_run_id,
            "queue_job_id": args.queue_job_id,
            "event_type": event_type,
            "status": final_status,
            "running_count_after_event": running_count,
            "trusted": True,  # finalize is an observed, not inferred, outcome
            "recorded_at": _now_iso(),
            "worker_pid": int(args.worker_pid) if str(args.worker_pid).isdigit() else None,
        }
        events_file = state_dir / f"{args.batch_run_id}.events.jsonl"
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 3. worker marker cleanup — legacy parity with codex-watch :627.
        if worker_marker.exists():
            worker_marker.unlink()

        # TODO(result-tmp): when the cancel protocol is implemented, a cancel
        # marker should rename <base>.result → <base>.result.stale here. The
        # cancel marker has no creator yet, so this is deferred.
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
