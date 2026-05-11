#!/usr/bin/env python3
"""
rev-codex-exec.py — shared Codex subprocess runner for bin/rev.

Usage:
  python3 rev-codex-exec.py <prompt_path> <raw_path> \
      --gd-root <root> --timeout <secs> --stderr-path <path>

Exit codes:
  0  — Codex exited 0 (raw output written)
  2  — Codex exited non-zero (FAILED verdict written to raw)
  3  — Codex timed out (FAILED verdict written to raw)
  1  — bad arguments / setup error
"""

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="rev-codex-exec: run codex exec --ephemeral")
    parser.add_argument("prompt", help="Path to prompt.md")
    parser.add_argument("raw", help="Path to raw-output.txt (output)")
    parser.add_argument("--gd-root", required=True, help="GD project root")
    parser.add_argument("--timeout", type=int, default=240, help="Timeout in seconds")
    parser.add_argument("--stderr-path", required=True, help="Path for codex stderr")
    args = parser.parse_args()

    prompt_path = args.prompt
    raw_path = args.raw
    gd_root = args.gd_root
    timeout_s = args.timeout
    stderr_path = args.stderr_path

    partial_path = os.path.join(os.path.dirname(raw_path), "raw-output.partial.txt")

    proc = subprocess.Popen(
        [
            "codex", "exec", "--ephemeral", "--sandbox", "read-only",
            "--skip-git-repo-check", "--cd", gd_root, "-",
        ],
        stdin=open(prompt_path, "rb"),
        stdout=open(raw_path, "wb"),
        stderr=open(stderr_path, "wb"),
        start_new_session=True,
    )

    try:
        proc.wait(timeout=timeout_s)
        rc = proc.returncode
        if rc != 0:
            # Non-zero exit: preserve partial, overwrite raw with FAILED
            if os.path.isfile(raw_path):
                shutil.copy2(raw_path, partial_path)
            with open(raw_path, "w") as f:
                f.write("REV_VERDICT: FAILED\nfailure_reason=codex_nonzero\n")
            sys.exit(2)
        # exit 0 — raw output already written by stdout redirect
        sys.exit(0)

    except subprocess.TimeoutExpired:
        # Timeout: SIGTERM → wait 2s → SIGKILL
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(2)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        # Preserve partial, overwrite raw with FAILED
        if os.path.isfile(raw_path):
            shutil.copy2(raw_path, partial_path)
        with open(raw_path, "w") as f:
            f.write("REV_VERDICT: FAILED\nfailure_reason=codex_timeout\n")
        sys.exit(3)


if __name__ == "__main__":
    main()
