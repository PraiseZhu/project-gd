"""Regression: router APPROVED-path must write the child ledger BEFORE validating
the route report.

Bug history: ``gd-review-router.py`` validated the route report (which references a
``child_review_ledger_path``) BEFORE writing that ledger. The route-report
validator requires the ledger to exist on disk, so every APPROVED run through the
``execution_only`` / ``combined`` paths failed validation and the router exited 1
(``CLOSURE_INELIGIBLE: ledger_file_not_found``) despite a clean APPROVED verdict —
which silently broke the plan SC-14 ``router && assert`` acceptance command.

Fix: write route report -> write child ledger -> THEN validate. This test drives
the real ``_run_live_execution_only`` APPROVED path fully offline (Path A raw
injection; no live Codex) and asserts the router exits 0 with the referenced
ledger present on disk.
"""
import importlib.util
import json
import os
import subprocess
import sys
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
ROUTER = PROJECT_ROOT / "scripts/gd-review-router.py"
INVOCATION_ID_ENV = "GD_REVIEW_ROUTER_INVOCATION_ID"


def _load_router():
    """Import gd-review-router.py as a module (it self-inserts scripts/ on sys.path)."""
    spec = importlib.util.spec_from_file_location("gd_review_router_under_test", ROUTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# Minimal execution-outcome target: passes gd-validate-execution-outcome.py
# (required top-level + task fields, one pass SC) and carries no deliverables,
# so the outcome validator has no on-disk hash dependency.
_TARGET = {
    "outcome_version": "1.0",
    "outcome_id": "router-ordering-regression",
    "task_outcomes": [
        {
            "task_id": "t-reg",
            "exec_status": "completed",
            "sc_acceptance": [{"sc_ref": "SC-1", "status": "pass"}],
        }
    ],
}

# Minimal v1-header Codex raw result (parsed with --compat-v1): APPROVED with a
# Scope Checked section covering the target's only SC-ID. Injected via Path A so
# the route report carries a real raw path + hash (Path B's synthetic placeholder
# is rejected by the route-report validator on APPROVED).
_RAW_APPROVED = """# Code Review Result
VERDICT: APPROVED
REVIEW_DOMAIN: ai_infra
REVIEW_MODE: single_pass
REVIEW_DELTA_SCOPE: full_matrix

## Scope Checked

| 检查面 | 结论 | 证据（≤30字） |
|---|---|---|
| sc_acceptance_coverage | PASS | SC-1 pass |

## Findings

none

## Residual Risk

none
"""


def test_router_approved_path_writes_ledger_before_validation(tmp_path):
    """APPROVED execution_only run must exit 0 with the child ledger on disk.

    Guards against re-introducing the ordering bug where the route report is
    validated before the child ledger it references is written.
    """
    target = tmp_path / "target.json"
    target.write_text(json.dumps(_TARGET), encoding="utf-8")

    raw = tmp_path / "codex_raw_approved.md"
    raw.write_text(_RAW_APPROVED, encoding="utf-8")

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    # Upstream quality gate evidence: filenames must contain code+review /
    # simplify (content is only hashed, not parsed).
    (evidence / "code-review-stub.md").write_text("stub", encoding="utf-8")
    (evidence / "simplify-stub.md").write_text("stub", encoding="utf-8")

    out_dir = tmp_path / "out"

    env = os.environ.copy()
    env["GD_UPSTREAM_QUALITY_EVIDENCE"] = str(evidence)
    # Router refuses to run if the side-door invocation-id env is already set.
    env.pop(INVOCATION_ID_ENV, None)

    r = subprocess.run(
        [
            sys.executable, str(ROUTER),
            "--mode", "live",
            "--target", str(target),
            "--codex-raw-result", str(raw),
            "--output-dir", str(out_dir),
        ],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env, timeout=120,
    )

    # Regression assertion: pre-fix this exited 1 (ledger_file_not_found) because
    # the route report was validated before the ledger was written.
    assert r.returncode == 0, (
        f"router must exit 0 on the APPROVED path; got {r.returncode}.\n"
        f"stdout={r.stdout[-500:]}\nstderr={r.stderr[-500:]}"
    )

    reports = list(out_dir.glob("route_report_*.json"))
    assert len(reports) == 1, f"expected exactly one route report, got {reports}"
    report = json.loads(reports[0].read_text(encoding="utf-8"))

    assert report.get("decision") == "APPROVED", f"decision={report.get('decision')}"
    assert report.get("findings") == [], f"findings={report.get('findings')}"

    ledger_path = report.get("child_review_ledger_path")
    assert ledger_path, "route report missing child_review_ledger_path"
    assert os.path.isfile(ledger_path), (
        f"child ledger must exist on disk when the route report is validated: {ledger_path}"
    )


def test_router_combined_path_writes_ledger_before_validation(tmp_path, monkeypatch):
    """execution_plus_code (combined) APPROVED path: same ledger-ordering guard.

    The CLI detector cannot route a lone execution-JSON target to
    execution_plus_code (it classifies as execution_only_no_code), so this variant
    drives ``_run_live_execution_plus_code`` directly. That function carries the
    same write-report -> write-ledger -> validate fix as the execution_only path;
    this test guards its ledger ordering independently.
    """
    target = tmp_path / "target.json"
    target.write_text(json.dumps(_TARGET), encoding="utf-8")

    raw = tmp_path / "codex_raw_approved.md"
    raw.write_text(_RAW_APPROVED, encoding="utf-8")

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "code-review-stub.md").write_text("stub", encoding="utf-8")
    (evidence / "simplify-stub.md").write_text("stub", encoding="utf-8")
    monkeypatch.setenv("GD_UPSTREAM_QUALITY_EVIDENCE", str(evidence))
    monkeypatch.delenv(INVOCATION_ID_ENV, raising=False)

    out_dir = tmp_path / "out"

    router = _load_router()
    rc = router._run_live_execution_plus_code(
        target, out_dir, "test-combined-0001",
        codex_raw_result=raw,
    )

    # Regression assertion: pre-fix this exited 1 (ledger_file_not_found).
    assert rc == 0, f"combined APPROVED path must exit 0; got {rc}"

    reports = list(out_dir.glob("route_report_*.json"))
    assert len(reports) == 1, f"expected exactly one route report, got {reports}"
    report = json.loads(reports[0].read_text(encoding="utf-8"))

    assert report.get("decision") == "APPROVED", f"decision={report.get('decision')}"
    assert report.get("review_target_kind") == "execution_plus_code"
    assert report.get("codex_review_kind") == "combined"
    assert report.get("findings") == [], f"findings={report.get('findings')}"

    ledger_path = report.get("child_review_ledger_path")
    assert ledger_path, "route report missing child_review_ledger_path"
    assert os.path.isfile(ledger_path), (
        f"child ledger must exist on disk when the route report is validated: {ledger_path}"
    )
