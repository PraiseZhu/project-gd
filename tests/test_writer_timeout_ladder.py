"""SC-1.1 / SC-1.2 / SC-1.3 — writer timeout ladder for the codex review dispatch.

Root cause guarded here: a non-deep PLAN review previously passed NO timeout flags
(`else []`), so codex-watch fell back to the daemon default exec_timeout=240 /
client send_wait=540. gpt-5.x at xhigh reasoning needs >240s on a large plan
capsule, so both attempts timed out and the review FAILED (2026-06-22 AKB2 CQL run).
`_writer_timeout_args` now gives non-deep plan reviews the same 720/1500/1700 ladder
the deep path already uses — but read-only (no --mode workspace-write).
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import pytest

from gd_codex_bridge_review import (
    _writer_timeout_args,
    _DEEP_EXEC_TIMEOUT_SEC,
    _DEEP_SEND_TIMEOUT_SEC,
    _DEEP_WRITER_TIMEOUT_SEC,
    _PLAN_EXEC_TIMEOUT_SEC,
    _PLAN_SEND_TIMEOUT_SEC,
    _PLAN_WRITER_TIMEOUT_SEC,
    _REVIEW_LADDER_OUTER_CAP_SEC,
)

# Non-deep, non-plan kinds that must keep the fast (unchanged) budget.
_OTHER_KINDS = ["code", "code_diff", "execution_outcome", "combined", "discuss"]


def _flag_value(args, flag):
    """Return the value following `flag` in an arg list, or None if absent."""
    return args[args.index(flag) + 1] if flag in args else None


class TestPlanNonDeepLadder:
    """SC-1.1: non-deep plan review gets 720/1500/1700, read-only."""

    def test_plan_nondeep_carries_full_ladder(self):
        writer_timeout, extra = _writer_timeout_args(deep=False, kind="plan")
        assert writer_timeout == _PLAN_WRITER_TIMEOUT_SEC == 1700
        assert _flag_value(extra, "--exec-timeout") == str(_PLAN_EXEC_TIMEOUT_SEC) == "720"
        assert _flag_value(extra, "--send-timeout") == str(_PLAN_SEND_TIMEOUT_SEC) == "1500"

    def test_plan_nondeep_stays_read_only(self):
        """Plan review must NOT escalate to workspace-write (it only reads the plan)."""
        _, extra = _writer_timeout_args(deep=False, kind="plan")
        assert "--mode" not in extra
        assert "workspace-write" not in extra

    def test_plan_nondeep_ignores_caller_fast_default(self):
        """Even if a caller passes the legacy 600s writer default, plan uses 1700."""
        writer_timeout, _ = _writer_timeout_args(deep=False, kind="plan", writer_timeout_sec=600)
        assert writer_timeout == 1700


class TestOtherKindsUnchanged:
    """SC-1.2 regression guard: non-deep non-plan kinds keep 240/540/600, no flags."""

    @pytest.mark.parametrize("kind", _OTHER_KINDS)
    def test_other_nondeep_has_no_timeout_flags(self, kind):
        writer_timeout, extra = _writer_timeout_args(deep=False, kind=kind)
        assert extra == [], f"{kind} must not pass timeout/mode flags"
        assert writer_timeout == 600, f"{kind} must keep the fast 600s writer default"

    @pytest.mark.parametrize("kind", _OTHER_KINDS)
    def test_other_nondeep_honors_explicit_writer_timeout(self, kind):
        writer_timeout, extra = _writer_timeout_args(deep=False, kind=kind, writer_timeout_sec=900)
        assert writer_timeout == 900
        assert extra == []


class TestDeepUnchanged:
    """Deep path behavior is preserved (workspace-write + 720/1500/1700)."""

    @pytest.mark.parametrize("kind", ["plan", "code_diff", "execution_outcome", "combined"])
    def test_deep_keeps_workspace_write_and_ladder(self, kind):
        writer_timeout, extra = _writer_timeout_args(deep=True, kind=kind)
        assert writer_timeout == _DEEP_WRITER_TIMEOUT_SEC == 1700
        assert _flag_value(extra, "--mode") == "workspace-write"
        assert _flag_value(extra, "--exec-timeout") == str(_DEEP_EXEC_TIMEOUT_SEC) == "720"
        assert _flag_value(extra, "--send-timeout") == str(_DEEP_SEND_TIMEOUT_SEC) == "1500"


class TestLadderInvariant:
    """SC-1.3: 2*exec <= send <= writer <= outer cap (1800), for both ladders."""

    @pytest.mark.parametrize(
        "exec_s,send_s,writer_s",
        [
            (_DEEP_EXEC_TIMEOUT_SEC, _DEEP_SEND_TIMEOUT_SEC, _DEEP_WRITER_TIMEOUT_SEC),
            (_PLAN_EXEC_TIMEOUT_SEC, _PLAN_SEND_TIMEOUT_SEC, _PLAN_WRITER_TIMEOUT_SEC),
        ],
    )
    def test_ladder_is_monotonic_and_capped(self, exec_s, send_s, writer_s):
        assert 2 * exec_s <= send_s, "send_wait must cover 2 retry attempts"
        assert send_s <= writer_s, "writer subprocess timeout must outlast the client wait"
        assert writer_s <= _REVIEW_LADDER_OUTER_CAP_SEC, "writer must stay under controller/router cap"
