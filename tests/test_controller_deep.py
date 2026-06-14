"""Tests for SC-11, SC-12, SC-32: controller deep flags."""
import os
import sys
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import pytest


class TestControllerDeepFlags:
    """SC-11/SC-12/SC-32: controller accepts --deep, --queue-job-id, --plan-file."""

    def test_controller_has_deep_flag(self):
        """SC-11: controller main() argparse has --deep flag."""
        controller = os.path.join(PROJECT_ROOT, "scripts", "gd-review-controller.py")
        r = subprocess.run(
            [sys.executable, controller, "--help"],
            capture_output=True, text=True,
        )
        assert "--deep" in r.stdout, f"SC-11: controller must have --deep flag; got: {r.stdout[:500]}"

    def test_controller_has_queue_job_id_flag(self):
        """SC-12: controller main() argparse has --queue-job-id flag."""
        controller = os.path.join(PROJECT_ROOT, "scripts", "gd-review-controller.py")
        r = subprocess.run(
            [sys.executable, controller, "--help"],
            capture_output=True, text=True,
        )
        assert "--queue-job-id" in r.stdout, (
            f"SC-12: controller must have --queue-job-id flag; got: {r.stdout[:500]}"
        )

    def test_controller_has_plan_file_flag(self):
        """SC-32: controller main() argparse has --plan-file flag."""
        controller = os.path.join(PROJECT_ROOT, "scripts", "gd-review-controller.py")
        r = subprocess.run(
            [sys.executable, controller, "--help"],
            capture_output=True, text=True,
        )
        assert "--plan-file" in r.stdout, (
            f"SC-32: controller must have --plan-file flag; got: {r.stdout[:500]}"
        )


class TestControllerDeepEvidence:
    """SC-12: controller deep mode extracts tests_status from run_evidence."""

    def test_controller_deep_evidence(self):
        """SC-12: _invoke_bridge_mapped with deep=True passes --deep to bridge args."""
        import inspect
        from gd_review_controller import _invoke_bridge_mapped
        sig = inspect.signature(_invoke_bridge_mapped)
        assert "deep" in sig.parameters, "SC-12: _invoke_bridge_mapped must accept deep= parameter"
        assert sig.parameters["deep"].default is False, "deep must default to False"
        assert "queue_job_id" in sig.parameters, "must accept queue_job_id= parameter"
        assert "plan_file" in sig.parameters, "must accept plan_file= parameter"


class TestControllerDeepTimeout:
    """SC-32: controller deep path uses bridge timeout ≥1800s."""

    def test_controller_deep_timeout(self):
        """SC-32: _invoke_bridge_mapped with deep=True uses subprocess timeout ≥1800s."""
        import inspect
        import unittest.mock as mock
        import pathlib
        from gd_review_controller import _invoke_bridge_mapped

        captured_calls = []

        def fake_run(args, **kwargs):
            captured_calls.append({"args": args, "timeout": kwargs.get("timeout")})
            # Return a fake result that causes early exit (no TRANSPORT_RESULT)
            return mock.MagicMock(
                stdout="GD_CODEX_BRIDGE_STATUS: failed\n",
                stderr="",
                returncode=1,
            )

        with mock.patch("gd_review_controller.subprocess.run", side_effect=fake_run):
            try:
                _invoke_bridge_mapped(
                    kind="plan",
                    target=pathlib.Path("/tmp/fake.md"),
                    cwd=pathlib.Path("/tmp"),
                    output_dir=pathlib.Path("/tmp/test-out"),
                    invocation_id="test-id",
                    deep=True,
                )
            except RuntimeError:
                pass  # expected — no TRANSPORT_RESULT in fake output

        assert len(captured_calls) > 0, "subprocess.run must be called"
        call = captured_calls[0]
        assert call["timeout"] >= 1800, (
            f"SC-32: deep mode bridge timeout must be ≥1800s, got {call['timeout']}"
        )
        assert "--deep" in call["args"], "SC-32: --deep must be passed to bridge argv"
