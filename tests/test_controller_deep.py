"""Tests for SC-11, SC-12, SC-32: controller deep flags."""
import os
import sys
import subprocess
import json
import pathlib
import tempfile

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


class TestControllerMappedResults:
    """L2 controller must consume valid red mapped results as review evidence."""

    def test_controller_accepts_requires_changes_mapped_when_parse_exits_nonzero(self):
        """parse-transport exit!=0 can still produce a valid mapped REQUIRES_CHANGES."""
        import unittest.mock as mock
        from gd_review_controller import _invoke_bridge_mapped

        with tempfile.TemporaryDirectory() as td:
            out_dir = pathlib.Path(td)
            raw = out_dir / "raw.md"
            raw.write_text("# Code Review Result\nVERDICT: REQUIRES_CHANGES\n", encoding="utf-8")
            captured_calls = []

            def fake_run(args, **kwargs):
                captured_calls.append(args)
                if "run-bridge" in args:
                    return mock.MagicMock(
                        stdout=f"TRANSPORT_RESULT: {raw}\n",
                        stderr="",
                        returncode=1,
                    )
                if "parse-transport" in args:
                    mapped_path = pathlib.Path(args[args.index("--out") + 1])
                    mapped_path.write_text(json.dumps({
                        "review_kind": "code_diff",
                        "review_run_status": "completed",
                        "gd_review_decision": "REQUIRES_CHANGES",
                        "findings": [{"severity": "P1", "title": "x"}],
                    }), encoding="utf-8")
                    return mock.MagicMock(stdout="", stderr="", returncode=1)
                raise AssertionError(args)

            with mock.patch("gd_review_controller.subprocess.run", side_effect=fake_run):
                mapped = _invoke_bridge_mapped(
                    kind="code_diff",
                    target=out_dir / "target.patch",
                    cwd=out_dir,
                    output_dir=out_dir,
                    invocation_id="test-id",
                    deep=True,
                )

            assert mapped["gd_review_decision"] == "REQUIRES_CHANGES"
            assert mapped["findings"][0]["severity"] == "P1"
            parse_call = next(args for args in captured_calls if "parse-transport" in args)
            assert "--deep" in parse_call

    def test_failed_mapped_becomes_bridge_failure_finding(self):
        """FAILED/degraded mapped with empty findings must not become a clean round."""
        from gd_review_controller import _extract_findings_from_mapped

        findings = _extract_findings_from_mapped(
            {
                "review_run_status": "degraded",
                "gd_review_decision": "FAILED",
                "findings": [],
                "merge_notes": {"degraded_reason": "DEEP_RUN_EVIDENCE_MISSING"},
                "_controller_meta": {"mapped_result_path": "/tmp/mapped.json"},
            },
            source="codex_A",
            round_num=1,
        )

        assert len(findings) == 1
        assert findings[0]["bridge_failure"] is True
        assert findings[0]["severity"] == "P1"
        assert findings[0]["status"] == "unresolved"
        assert findings[0]["mapped_result_path"] == "/tmp/mapped.json"

    def test_baseline_empty_round_without_object_change_does_not_resolve(self):
        """A missing finding needs object-change evidence before being resolved."""
        from gd_review_controller import update_baseline_statuses

        baseline = [{
            "id": "F001",
            "status": "unresolved",
            "file": "auth.py",
            "line": 42,
            "category": "sc_conformance",
            "round_history": [],
        }]

        updated, unresolved, new_delta = update_baseline_statuses(
            baseline,
            [],
            2,
            previous_meta={"diff_hash": "same", "target_hash": None, "modified_files": ["auth.py"]},
            current_meta={"diff_hash": "same", "target_hash": None, "modified_files": ["auth.py"], "diff_unavailable": False},
        )

        assert unresolved == 1
        assert new_delta == 0
        assert updated[0]["status"] == "unresolved"
        assert updated[0]["round_history"][-1]["resolution_gate"] == "blocked_without_change_evidence"

    def test_baseline_resolves_only_with_relevant_change_evidence(self):
        """Absent finding resolves when the reviewed object changed and referenced file is touched."""
        from gd_review_controller import update_baseline_statuses

        baseline = [{
            "id": "F001",
            "status": "unresolved",
            "file": "auth.py",
            "line": 42,
            "category": "sc_conformance",
            "evidence": "auth.py:42 wrong branch",
            "round_history": [],
        }]

        updated, unresolved, new_delta = update_baseline_statuses(
            baseline,
            [],
            2,
            previous_meta={"diff_hash": "before", "target_hash": None, "modified_files": ["auth.py"]},
            current_meta={"diff_hash": "after", "target_hash": None, "modified_files": ["auth.py"], "diff_unavailable": False},
        )

        assert unresolved == 0
        assert new_delta == 0
        assert updated[0]["status"] == "resolved"
        assert updated[0]["resolution_evidence"]["diff_hash_before"] == "before"
        assert updated[0]["resolution_evidence"]["diff_hash_after"] == "after"

    def test_bridge_failure_baseline_never_auto_resolves(self):
        """Bridge failure sentinel must remain unresolved even when later rounds are empty."""
        from gd_review_controller import update_baseline_statuses

        baseline = [{
            "id": "BRIDGE-FAIL-r1-codex_A",
            "status": "unresolved",
            "file": "<bridge:codex_A>",
            "line": None,
            "category": "bridge_failure",
            "bridge_failure": True,
            "round_history": [],
        }]

        updated, unresolved, _ = update_baseline_statuses(
            baseline,
            [],
            2,
            previous_meta={"diff_hash": "before"},
            current_meta={"diff_hash": "after", "modified_files": ["x.py"], "diff_unavailable": False},
        )

        assert unresolved == 1
        assert updated[0]["status"] == "unresolved"
        assert updated[0]["round_history"][-1]["resolution_gate"] == "bridge_failure_never_auto_resolves"

    def test_controller_final_report_written_with_bridge_failure_summary(self):
        """Final controller report must bind verdict, baseline, rounds, and mapped failures."""
        from gd_review_controller import _write_controller_final_report

        with tempfile.TemporaryDirectory() as td:
            out_dir = pathlib.Path(td)
            mapped = out_dir / "codex_mapped_execution_outcome_deadbeef.json"
            mapped.write_text(json.dumps({
                "review_kind": "execution_outcome",
                "review_run_status": "degraded",
                "gd_review_decision": "FAILED",
                "findings": [],
                "merge_notes": {"degraded_reason": "DEEP_RUN_EVIDENCE_MISSING"},
            }), encoding="utf-8")
            baseline = [{
                "id": "BRIDGE-FAIL-r1-codex_A",
                "status": "unresolved",
                "bridge_failure": True,
                "category": "bridge_failure",
            }]

            report_path = _write_controller_final_report(
                output_dir=out_dir,
                invocation_id="ctrl-test",
                branch_label="execution-only",
                kind="execution_outcome",
                target=out_dir / "outcome.json",
                cwd=out_dir,
                final_verdict="REQUIRES_CHANGES",
                exit_reason="baseline_unresolved_stagnant",
                baseline=baseline,
                rounds=[{"round": 1, "bridge_failure_count": 1}],
                initial_state={"baseline_unresolved_count": 1},
                final_state={"baseline_unresolved_count": 1},
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            assert report["final_verdict"] == "REQUIRES_CHANGES"
            assert report["bridge_failure_count"] == 1
            assert report["mapped_results"][0]["bridge_failure"] is True
            assert report["mapped_results"][0]["degraded_reason"] == "DEEP_RUN_EVIDENCE_MISSING"

    def test_combined_writes_top_level_final_report(self):
        """Combined branch must write a top-level report binding A/B/simplify state."""
        from gd_review_controller import (
            DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
            DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
            StubDispatch,
            _make_temp_git_repo,
            gen_id,
            run_branch_c,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            _make_temp_git_repo(td)
            exec_result = tdp / "execution_result.json"
            exec_result.write_text(json.dumps({"execution_status": "ok"}), encoding="utf-8")

            stub = StubDispatch()
            stub._round_n_sequence = [[], []]
            stub._new_exec_result = exec_result
            out_dir = tdp / "out"
            result = run_branch_c(
                cwd=tdp,
                output_dir=out_dir,
                invocation_id=gen_id(),
                execution_result=exec_result,
                claude_findings=[],
                threshold_lines=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
                threshold_files=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
                max_rounds=10,
                stub_dispatch=stub,
            )

            report = json.loads((out_dir / "controller-final-report.json").read_text(encoding="utf-8"))
            assert result == "APPROVED"
            assert report["branch"] == "combined"
            assert report["review_kind"] == "combined"
            assert report["final_verdict"] == "APPROVED"
            assert report["final_state"]["branch_a_report_loaded"] is True
            assert report["final_state"]["branch_b_report_loaded"] is True
            assert report["final_state"]["simplify_status"]["completed"] is True
            assert (out_dir / "branch_a" / "controller-final-report.json").exists()
            assert (out_dir / "branch_b" / "controller-final-report.json").exists()

    def test_main_fallback_report_is_auditable_on_early_system_exit(self):
        """Early controller exits must write wrapper failure evidence, not an empty shell."""
        import gd_review_controller as controller

        with tempfile.TemporaryDirectory() as td:
            out_dir = pathlib.Path(td) / "out"
            old_argv = sys.argv
            old_run_branch_a = controller.run_branch_a

            def fail_before_report(**_kwargs):
                raise SystemExit(1)

            controller.run_branch_a = fail_before_report
            sys.argv = [
                "gd-review-controller.py",
                "--branch",
                "code-only",
                "--cwd",
                td,
                "--output-dir",
                str(out_dir),
            ]
            try:
                with pytest.raises(SystemExit):
                    controller.main()
            finally:
                controller.run_branch_a = old_run_branch_a
                sys.argv = old_argv

            report = json.loads((out_dir / "controller-final-report.json").read_text(encoding="utf-8"))
            assert report["final_verdict"] == "REQUIRES_CHANGES"
            assert report["baseline_findings"]
            assert report["baseline_findings"][0]["bridge_failure"] is True
            assert report["rounds"]
            assert report["rounds"][0]["bridge_failure_count"] == 1
