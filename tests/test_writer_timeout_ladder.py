"""SC-1.1 / SC-1.2 / SC-1.3 — writer timeout ladder for the codex review dispatch.

Root cause guarded here: a non-deep review previously passed NO timeout flags
(`else []`), so codex-watch fell back to the daemon default exec_timeout=240 /
client send_wait=540. But the daemon actually runs at plist CODEX_EXEC_TIMEOUT=720
(raised from 240), so worst-case = 2*720 = 1440s; the old fast-path send_wait=540/900
< 1440 broke the invariant and killed a retrying review mid-flight (2026-06-22 AKB2
CQL run; T-P0 archive: attempt=2 exit=124). `_writer_timeout_args` now gives ALL
kinds the same 720/1500/1700 ladder (deep adds --mode workspace-write) so the
invariant daemon_worst(1440) < send_wait(1500) < writer(1700) holds uniformly.
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
    _NON_DEEP_EXEC_TIMEOUT_SEC,
    _NON_DEEP_SEND_TIMEOUT_SEC,
    _NON_DEEP_WRITER_TIMEOUT_SEC,
    _REVIEW_LADDER_OUTER_CAP_SEC,
)

# Non-deep, non-plan kinds — T-P0: now ALSO use the ladder (was fast 600/no-flags,
# which broke daemon_worst(1440) < send_wait and killed retrying reviews).
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


class TestOtherKindsUseLadder:
    """T-P0: non-deep non-plan kinds ALSO use the ladder (720/1500/1700), read-only.

    The old fast path (600/no flags) broke daemon_worst(1440) < send_wait and killed
    retrying reviews mid-flight. Now all kinds hold the invariant uniformly.
    """

    @pytest.mark.parametrize("kind", _OTHER_KINDS)
    def test_other_nondeep_carries_full_ladder(self, kind):
        writer_timeout, extra = _writer_timeout_args(deep=False, kind=kind)
        assert writer_timeout == _NON_DEEP_WRITER_TIMEOUT_SEC == 1700, f"{kind} writer_timeout"
        assert _flag_value(extra, "--exec-timeout") == str(_NON_DEEP_EXEC_TIMEOUT_SEC) == "720", f"{kind} exec"
        assert _flag_value(extra, "--send-timeout") == str(_NON_DEEP_SEND_TIMEOUT_SEC) == "1500", f"{kind} send"

    @pytest.mark.parametrize("kind", _OTHER_KINDS)
    def test_other_nondeep_stays_read_only(self, kind):
        _, extra = _writer_timeout_args(deep=False, kind=kind)
        assert "--mode" not in extra
        assert "workspace-write" not in extra

    @pytest.mark.parametrize("kind", _OTHER_KINDS)
    def test_other_nondeep_ignores_legacy_fast_default(self, kind):
        """The legacy 600s writer_timeout_sec arg is ignored — ladder is mandatory (T-P0)."""
        writer_timeout, extra = _writer_timeout_args(deep=False, kind=kind, writer_timeout_sec=600)
        assert writer_timeout == 1700
        assert _flag_value(extra, "--send-timeout") == "1500"


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
            (_NON_DEEP_EXEC_TIMEOUT_SEC, _NON_DEEP_SEND_TIMEOUT_SEC, _NON_DEEP_WRITER_TIMEOUT_SEC),
        ],
    )
    def test_ladder_is_monotonic_and_capped(self, exec_s, send_s, writer_s):
        assert 2 * exec_s <= send_s, "send_wait must cover 2 retry attempts"
        assert send_s <= writer_s, "writer subprocess timeout must outlast the client wait"
        assert writer_s <= _REVIEW_LADDER_OUTER_CAP_SEC, "writer must stay under controller/router cap"
