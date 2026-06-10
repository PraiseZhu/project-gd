#!/usr/bin/env python3
"""gd-codex-transport-guard.py — Transport prevention four-layer guard module.

stdlib-only. Deterministic code (not prompts). All four layers:

  1. preflight_probe()    — lightweight subprocess-based liveness probe
  2. probe_with_retry()   — bounded retry with configurable backoff
  3. PROBE_TIMEOUT_SEC    — deterministic short timeout constant (not bridge writer timeout)
  4. healthcheck()        — final confirmation gate before dispatch

Public API:
  ensure_codex_available(max_retries=MAX_RETRIES) -> dict
    Returns {"available": bool, "outcome": str, "fail_closed": bool}
    If fail_closed=True: do NOT dispatch to Codex — block with transport_failed.

CLI:
  python3 scripts/gd-codex-transport-guard.py
  Exit 0 = available, Exit 1 = fail-closed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

# ── Constants ────────────────────────────────────────────────────────────────

PROBE_TIMEOUT_SEC: float = 10.0   # short probe timeout; decoupled from bridge --writer-timeout-sec (600)
MAX_RETRIES: int = 2               # bounded retry ceiling; 2 = at most 3 total attempts
RETRY_BACKOFF_SEC: float = 1.0    # sleep between failed attempts


# ── Layer 1: preflight probe ─────────────────────────────────────────────────

def preflight_probe(timeout_sec: float = PROBE_TIMEOUT_SEC) -> dict:
    """Lightweight liveness probe — no side effects, no real review capsule dispatched.

    Runs ``codex --version`` via subprocess to check transport availability.

    Returns:
      {"available": bool, "returncode": int, "stdout": str, "stderr": str}

    Timeout → available=False, returncode=-1, stderr="timeout"
    Exception → available=False, returncode=-2, stderr=str(e)
    """
    try:
        result = subprocess.run(
            ["codex", "--version"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        available = result.returncode == 0
        return {
            "available": available,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "timeout",
        }
    except Exception as e:  # FileNotFoundError, PermissionError, etc.
        return {
            "available": False,
            "returncode": -2,
            "stdout": "",
            "stderr": str(e),
        }


# ── Layer 2: bounded retry ────────────────────────────────────────────────────

def probe_with_retry(
    preflight_fn=None,
    max_retries: int = MAX_RETRIES,
    backoff_sec: float = RETRY_BACKOFF_SEC,
) -> dict:
    """Bounded retry wrapper around preflight_fn.

    Attempts at most max_retries+1 calls. On first success returns immediately.
    On all-failure returns fail_closed=True.

    preflight_fn signature: (timeout_sec: float) -> namespace/dict with .returncode,
    .stdout, .stderr attributes (or keys). Defaults to preflight_probe.

    Returns:
      {"available": bool, "fail_closed": bool, "attempts": int}

    SC-5 invariants:
      - All failures → available=False, fail_closed=True (no downgrade to "close enough")
      - Transient failure followed by success → available=True, fail_closed=False
    """
    if preflight_fn is None:
        preflight_fn = preflight_probe

    total_attempts = max_retries + 1
    for attempt in range(1, total_attempts + 1):
        probe_result = preflight_fn(PROBE_TIMEOUT_SEC)

        # Normalise: accept both dict and object with attribute access
        if isinstance(probe_result, dict):
            available = probe_result.get("available", False)
            rc = probe_result.get("returncode", -1)
        else:
            available = getattr(probe_result, "available", False)
            rc = getattr(probe_result, "returncode", -1)

        # Treat returncode==0 as available regardless of the `available` flag
        # (allows SimpleNamespace stubs in tests that only set returncode).
        if rc == 0:
            available = True

        if available:
            return {
                "available": True,
                "fail_closed": False,
                "attempts": attempt,
            }

        # Sleep before next attempt (not after the last one)
        if attempt < total_attempts:
            time.sleep(backoff_sec)

    # All attempts exhausted — fail-closed, no downgrade
    return {
        "available": False,
        "fail_closed": True,
        "attempts": total_attempts,
    }


# ── Layer 3/4: healthcheck ────────────────────────────────────────────────────

def healthcheck() -> bool:
    """Final confirmation gate. Called after probe_with_retry succeeds.

    Performs one more preflight_probe call to confirm the transport is still
    healthy right before dispatch. Any failure here triggers fail-closed.

    Returns True if Codex transport is healthy, False otherwise.
    """
    result = preflight_probe(timeout_sec=PROBE_TIMEOUT_SEC)
    return result["available"]


# ── Public entry point ────────────────────────────────────────────────────────

def ensure_codex_available(max_retries: int = MAX_RETRIES) -> dict:
    """Four-layer transport prevention guard.

    Combines preflight probe + bounded retry + healthcheck into a single
    fail-closed gate. Controller must call this before dispatching to Codex.

    Returns:
      {"available": bool, "outcome": str, "fail_closed": bool}

    outcome values:
      "codex_available"               — all layers passed, safe to dispatch
      "codex_transport_unavailable"   — fail-closed; do not dispatch

    SC-5: fail_closed=True means controller MUST write aggregate_bucket=transport_failed
    and exit non-zero. Never downgrade to "Claude-only" fallback.
    """
    retry_result = probe_with_retry(
        preflight_fn=preflight_probe,
        max_retries=max_retries,
    )

    if retry_result.get("available"):
        # Layer 4: final healthcheck confirmation
        hc_ok = healthcheck()
        if hc_ok:
            return {
                "available": True,
                "outcome": "codex_available",
                "fail_closed": False,
            }
        else:
            # Healthcheck failed after retry succeeded — treat as transport failure
            return {
                "available": False,
                "outcome": "codex_transport_unavailable",
                "fail_closed": True,
            }
    else:
        # All retries exhausted — fail-closed
        return {
            "available": False,
            "outcome": "codex_transport_unavailable",
            "fail_closed": True,
        }


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = ensure_codex_available()
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result.get("available") else 1)
