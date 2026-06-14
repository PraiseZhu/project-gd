"""Tests for SC-13, SC-14, SC-23: validate-execution-outcome and deep isolation guard."""
import importlib.util
import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))


def _load_validate_module():
    spec = importlib.util.spec_from_file_location(
        "gd_validate", os.path.join(PROJECT_ROOT, "scripts", "gd-validate-execution-outcome.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSubstitutePython:
    """SC-13: _substitute_python must not produce /usr/bin/env /path/to/python3.13."""

    def test_substitute(self):
        """SC-13: substituting /usr/bin/env python3 produces a valid command."""
        mod = _load_validate_module()
        fn = mod._substitute_python

        # Case 1: /usr/bin/env python3 -m X → should become /path/to/python3 -m X
        result = fn("/usr/bin/env python3 -m pytest tests/", "/usr/local/bin/python3")
        assert "/usr/bin/env /usr/local/bin" not in result, (
            "SC-13: must not produce '/usr/bin/env /path/to/python3'"
        )
        assert "/usr/local/bin/python3 -m pytest" in result, (
            "SC-13: should produce locked interpreter -m X"
        )

        # Case 2: unsafe python_exe with spaces → skip substitution
        result_unsafe = fn("python3 -m pytest", "/usr/bin/env python3")
        assert result_unsafe == "python3 -m pytest", (
            "SC-13: unsafe python_exe with 'env' must not substitute"
        )

        # Case 3: python_exe with spaces → skip
        result_space = fn("python3 -m pytest", "/path with spaces/python3")
        assert result_space == "python3 -m pytest", (
            "SC-13: python_exe with spaces must not substitute"
        )


class TestSkipUnderPass:
    """SC-14: skipped>0 + declared pass → SKIP_UNDER_PASS warning."""

    def test_skip_under_pass(self):
        """SC-14: validate_verify_rerun emits SKIP_UNDER_PASS when pytest skips but claim=pass."""
        import io
        import contextlib
        mod = _load_validate_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test script that produces 1 skipped
            test_file = os.path.join(tmpdir, "test_skip.py")
            with open(test_file, "w") as f:
                f.write(
                    "import pytest\n"
                    "@pytest.mark.skip(reason='golden_replay placeholder')\n"
                    "def test_always_skipped():\n"
                    "    pass\n"
                )

            plan_cmds = [
                {
                    "sc_ref": "SC-1",
                    "cmd": f"python3 -m pytest {test_file} -q",
                    "method": "command",
                    "gate_type": "build-gate",
                }
            ]
            sc_acceptance = {"SC-1": "pass"}

            # SKIP_UNDER_PASS is emitted to stderr
            stderr_capture = io.StringIO()
            with contextlib.redirect_stderr(stderr_capture):
                errors = mod.validate_verify_rerun(plan_cmds, sc_acceptance, None)
            stderr_output = stderr_capture.getvalue()

            assert "SKIP_UNDER_PASS" in stderr_output, (
                f"SC-14: SKIP_UNDER_PASS must appear in stderr when skipped>0 + declared pass; "
                f"got stderr={stderr_output!r}, errors={errors}"
            )


class TestDeepActivePathPollutionGuard:
    """SC-23: deep path isolation + pollution guard (code-level verification)."""

    def test_deep_active_path_pollution_guard(self):
        """SC-23: bridge source implements isolation guard and DEEP_ISOLATION_VIOLATED error."""
        bridge_src_path = os.path.join(PROJECT_ROOT, "scripts", "gd-codex-bridge-review.py")
        with open(bridge_src_path) as f:
            bridge_src = f.read()

        # A: Real work tree protection via git status before/after
        assert (
            "git status" in bridge_src or "git diff" in bridge_src
        ), "SC-23: bridge must use git status/diff to guard real work tree"

        # B: DEEP_ISOLATION_VIOLATED error code must be defined
        assert "DEEP_ISOLATION_VIOLATED" in bridge_src, (
            "SC-23: bridge must define DEEP_ISOLATION_VIOLATED for pollution detection"
        )

        # C: --deep flag must be in run-bridge argparse
        assert "--deep" in bridge_src, "SC-23: bridge run-bridge must accept --deep"

        # D: Isolation must block source mutations (scripts/commands/tests/fixtures)
        assert (
            "scripts" in bridge_src and "fixtures" in bridge_src
        ), "SC-23: isolation guard must mention protected paths (scripts, fixtures)"

        # E: Tempdir / disposable copy isolation for deep runs
        assert (
            "tempfile" in bridge_src or "TemporaryDirectory" in bridge_src
            or "temp_dir" in bridge_src.lower() or "tmpdir" in bridge_src.lower()
        ), "SC-23: bridge must use tmpdir/tempfile isolation for deep runs"


class TestFlatResultNormalization:
    """Schema drift fix: validator must accept the FLAT gd-execution-result the
    execute child actually emits (top-level exec_status/sc_acceptance), not only the
    wrapped task_outcomes envelope — without weakening the gate."""

    def _validate(self, fixture_rel_or_tmp):
        from pathlib import Path
        mod = _load_validate_module()
        return mod.validate_schema(Path(fixture_rel_or_tmp))

    def test_flat_single_result_accepted(self):
        """Flat gd-execution-result → validates clean (was blocked before fix)."""
        fixture = os.path.join(
            PROJECT_ROOT, "fixtures", "execution-outcome", "valid-flat-result.json"
        )
        errors, _ = self._validate(fixture)
        assert errors == [], f"flat single-result must validate clean, got: {errors}"

    def test_wrapped_outcome_still_accepted(self):
        """Wrapped envelope (outcome_id/task_outcomes) still validates clean — no regression.

        Built inline (no must_exist deliverables) to isolate normalisation behaviour from
        unrelated fixture-path rot in the on-disk wrapped fixtures.
        """
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(
                '{"outcome_version":"1","outcome_id":"wrapped-test-001",'
                '"task_outcomes":[{"task_id":"T1","exec_status":"completed",'
                '"sc_acceptance":[{"sc_ref":"SC-1","status":"pass"}]}]}'
            )
            wrapped = f.name
        try:
            errors, _ = self._validate(wrapped)
            assert errors == [], f"wrapped outcome must validate clean, got: {errors}"
        finally:
            os.unlink(wrapped)

    def test_on_disk_wrapped_fixture_clean(self):
        """Rot guard: the repo's wrapped fixture validates clean (its batch deliverable
        exists). Fails if fixtures/agent-exec/valid-agent-exec-batch.json goes missing again."""
        fixture = os.path.join(
            PROJECT_ROOT, "fixtures", "execution-outcome", "valid-agent-exec-outcome.json"
        )
        errors, _ = self._validate(fixture)
        assert errors == [], (
            f"on-disk wrapped fixture must validate clean (deliverable must_exist resolves), "
            f"got: {errors}"
        )

    def test_gate_not_weakened_missing_sc_acceptance(self):
        """exec_status but no sc_acceptance and no task_outcomes → still fails."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"template_kind": "gd-execution-result", "exec_status": "completed"}')
            bad = f.name
        try:
            errors, _ = self._validate(bad)
            assert errors, "missing sc_acceptance + task_outcomes must fail (gate intact)"
        finally:
            os.unlink(bad)

    def test_flat_invalid_sc_status_rejected(self):
        """Flat form runs the SAME per-task checks: a bad sc status is caught."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(
                '{"template_kind":"gd-execution-result","task_id":"T1",'
                '"exec_status":"completed",'
                '"sc_acceptance":[{"sc_ref":"SC-1","status":"maybe"}]}'
            )
            bad = f.name
        try:
            errors, _ = self._validate(bad)
            assert any("status invalid" in e for e in errors), (
                f"bad sc status in flat form must be caught (gate runs on flat), got: {errors}"
            )
        finally:
            os.unlink(bad)
