"""
Synthetic skip target for deep-review e2e testing.
This test unconditionally skips - used to verify Codex can detect
golden_replay placeholder skips in workspace-write sandbox.
"""
import pytest


@pytest.mark.skip(reason="golden_replay placeholder — verify commands not yet replayed against live data")
def test_golden_replay_execution():
    """Placeholder test that simulates a golden_replay verification SC."""
    # This should be replaced with actual golden replay logic
    assert False, "This test must not be counted as passing — it is always skipped"
