"""tests/test_l3_code_only_codex_sidecar.py — L3 code-only Codex code_diff sidecar.

SC-6: code_only route has a real Codex code_diff sidecar (codex raw/mapped/ledger).
SC-7: code-only APPROVED rejected under transport_failed / wrapper_schema_fail /
      missing child ledger / invalid child ledger / hash mismatch.

The router path is exercised by monkeypatching _run_live_codex_bridge (no live Codex,
no network, no key). The validator negatives are exercised via validate_route_report on
constructed route reports pointing at real temp files with correct/declared hashes.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ROUTER_PATH = ROOT / "scripts" / "gd-review-router.py"
VALIDATOR_PATH = ROOT / "scripts" / "gd-validate-route-report.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def router():
    return _load_module("gd_review_router_st", ROUTER_PATH)


@pytest.fixture(scope="module")
def validator():
    return _load_module("gd_validate_route_report_st", VALIDATOR_PATH)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _stub_gate_pass(monkeypatch, router_mod):
    """Force the upstream quality gate to pass so we reach the Codex sidecar stage."""
    monkeypatch.setattr(
        router_mod, "_run_upstream_quality_gate",
        lambda *a, **k: {"steps": [], "fail_closed": False, "failure_code": None},
    )


def _stub_bridge(monkeypatch, router_mod, tmp_path, *, status="completed",
                 decision="APPROVED", mapped_kind="code_diff"):
    """Replace _run_live_codex_bridge with a fake returning files in tmp_path."""
    raw = tmp_path / "codex-raw.md"
    raw.write_text("# Code Diff Review Result (v2)\n\nVERDICT: APPROVED\n")
    mapped = tmp_path / "codex-mapped.json"
    mapped.write_text(json.dumps({
        "review_kind": mapped_kind, "target_role": mapped_kind,
        "template_kind": "gd-code-diff-review", "gd_review_decision": decision,
    }))
    def fake_bridge(kind, target, output_dir, invocation_id, timeout_sec,
                    deep=False, plan_file=None):
        assert kind == "code_diff", f"expected code_diff, got {kind}"
        return {
            "status": status, "decision": decision,
            "raw_path": str(raw), "raw_hash": _sha(raw),
            "mapped_path": str(mapped), "mapped_hash": _sha(mapped),
            "findings": [], "failure_description": None,
        }
    monkeypatch.setattr(router_mod, "_run_live_codex_bridge", fake_bridge)


def _stub_no_quality_tools(monkeypatch, router_mod):
    """Make the router environment look like Claude slash commands are not PATH tools."""
    monkeypatch.delenv("GD_UPSTREAM_QUALITY_EVIDENCE", raising=False)
    monkeypatch.delenv("GD_UPSTREAM_QUALITY_GATE", raising=False)
    original_run = router_mod.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd == ["which", "code-review"] or cmd == ["which", "simplify"]:
            class Result:
                returncode = 1
                stdout = ""
                stderr = ""
            return Result()
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(router_mod.subprocess, "run", fake_run)


def _run_code_only(router_mod, tmp_path):
    target = tmp_path / "target.py"
    target.write_text("print('x')\n")
    out = tmp_path / "out"
    out.mkdir()
    rc = router_mod._run_live_code_only(
        target, out, "router-20260101T000000Z-abcdef12")
    rps = sorted(out.glob("route_report_*.json"))
    assert rps, "no route report written"
    report = json.loads(rps[-1].read_text())
    return rc, report


# ─── SC-6 positive: approved code_only route has completed code_diff sidecar ───

def test_approved_code_only_has_completed_code_diff_sidecar(router, monkeypatch, tmp_path):
    _stub_gate_pass(monkeypatch, router)
    _stub_bridge(monkeypatch, router, tmp_path, status="completed", decision="APPROVED")
    rc, report = _run_code_only(router, tmp_path)
    assert rc == 0
    assert report["review_target_kind"] == "code_only"
    assert report["decision"] == "APPROVED"
    assert report["codex_review_kind"] == "code_diff"
    assert report["codex_review_status"] == "completed"
    assert report["codex_raw_result_path"]
    assert report["codex_raw_result_hash"]
    assert report["codex_mapped_result_path"]
    assert report["codex_mapped_result_hash"]
    assert report["child_review_ledger_path"]
    assert report["child_review_ledger_hash"]
    assert report.get("failure_code") != "LOCAL_STATIC_ONLY"
    # ledger file physically exists and hash matches
    ledger = Path(report["child_review_ledger_path"])
    assert ledger.exists()
    assert _sha(ledger) == report["child_review_ledger_hash"]


def test_code_only_default_gate_does_not_block_sidecar_when_slash_commands_absent(
    router, monkeypatch, tmp_path
):
    """Regression: router subprocess cannot resolve Claude slash commands with `which`.

    Default mode must record the upstream quality gate as skipped/observe-only and still
    run the Codex code_diff sidecar. Strict mode keeps unavailable→fail-closed coverage
    in router self-test and the dedicated test below.
    """
    _stub_no_quality_tools(monkeypatch, router)
    _stub_bridge(monkeypatch, router, tmp_path, status="completed", decision="APPROVED")
    rc, report = _run_code_only(router, tmp_path)
    assert rc == 0
    assert report["decision"] == "APPROVED"
    assert report["codex_review_kind"] == "code_diff"
    assert report["codex_review_status"] == "completed"
    gate = report["upstream_quality_gate"]
    assert gate["fail_closed"] is False
    assert {s["status"] for s in gate["steps"]} == {"skipped"}
    assert {s["origin"] for s in gate["steps"]} == {"slash_command_not_in_router"}
    assert report.get("failure_code") != "CODE_REVIEW_UNAVAILABLE"


def test_code_only_strict_gate_still_fails_closed_when_slash_commands_absent(
    router, monkeypatch, tmp_path
):
    _stub_no_quality_tools(monkeypatch, router)
    monkeypatch.setenv("GD_UPSTREAM_QUALITY_GATE", "strict")
    _stub_bridge(monkeypatch, router, tmp_path, status="completed", decision="APPROVED")
    rc, report = _run_code_only(router, tmp_path)
    assert rc != 0
    assert report["decision"] == "REQUIRES_CHANGES"
    assert report["failure_code"] == "CODE_REVIEW_UNAVAILABLE"
    assert report["codex_review_status"] == "not_run_blocked"
    assert report["upstream_quality_gate"]["fail_closed"] is True


def test_requires_changes_route(router, monkeypatch, tmp_path):
    _stub_gate_pass(monkeypatch, router)
    _stub_bridge(monkeypatch, router, tmp_path, status="requires_changes",
                 decision="REQUIRES_CHANGES")
    rc, report = _run_code_only(router, tmp_path)
    assert rc != 0
    assert report["decision"] == "REQUIRES_CHANGES"
    assert report["codex_review_status"] == "requires_changes"


def test_injection_path_reaches_approved(router, monkeypatch, tmp_path):
    """SC-6 injection path (codex_mapped_result kwarg, no bridge monkeypatch):
    a valid APPROVED mapped fixture WITHOUT review_run_status must reach APPROVED.
    Guards the bug where codex_review_status_from_evidence forced wrapper_schema_fail
    for run_status-less fixtures (HIGH from /code-review)."""
    _stub_gate_pass(monkeypatch, router)
    target = tmp_path / "target.py"
    target.write_text("print('x')\n")
    raw = tmp_path / "inj-raw.md"
    raw.write_text("# Code Diff Review Result (v2)\n\nVERDICT: APPROVED\n")
    mapped = tmp_path / "inj-mapped.json"
    mapped.write_text(json.dumps({
        "review_kind": "code_diff", "target_role": "code_diff",
        "template_kind": "gd-code-diff-review", "gd_review_decision": "APPROVED",
    }))
    out = tmp_path / "out"
    out.mkdir()
    rc = router._run_live_code_only(
        target, out, "router-20260101T000000Z-abcdef12",
        codex_mapped_result=mapped, codex_raw_result=raw,
    )
    rps = sorted(out.glob("route_report_*.json"))
    report = json.loads(rps[-1].read_text())
    assert rc == 0
    assert report["decision"] == "APPROVED"
    assert report["codex_review_status"] == "completed"
    assert report["codex_review_kind"] == "code_diff"


# ─── SC-7 negatives (router path) ───

def test_transport_failed_negative(router, monkeypatch, tmp_path):
    _stub_gate_pass(monkeypatch, router)
    _stub_bridge(monkeypatch, router, tmp_path, status="transport_failed", decision="FAILED")
    rc, report = _run_code_only(router, tmp_path)
    assert report["decision"] != "APPROVED"
    assert report["codex_review_status"] == "transport_failed"


def test_wrapper_schema_fail_negative(router, monkeypatch, tmp_path):
    _stub_gate_pass(monkeypatch, router)
    _stub_bridge(monkeypatch, router, tmp_path, status="wrapper_schema_fail", decision="FAILED")
    rc, report = _run_code_only(router, tmp_path)
    assert report["decision"] != "APPROVED"
    assert report["codex_review_status"] == "wrapper_schema_fail"


# ─── SC-7 negatives (validator integration) ───

def _build_approved_report(tmp_path, *, drop_ledger=False, ledger_valid=True,
                           raw_hash_wrong=False, mapped_kind="code_diff"):
    raw = tmp_path / "v-raw.md"
    raw.write_text("# raw\nVERDICT: APPROVED\n")
    mapped = tmp_path / "v-mapped.json"
    mapped.write_text(json.dumps({
        "review_kind": mapped_kind, "target_role": mapped_kind,
        "template_kind": "gd-code-diff-review", "gd_review_decision": "APPROVED",
    }))
    patch = tmp_path / "v.patch"
    patch.write_text("diff --git\n")
    child = tmp_path / "v-child.json"
    child.write_text("{}")
    merge = tmp_path / "v-merge.json"
    merge.write_text("{}")
    ledger_body = {
        "schema_version": "1.0", "stage": "review_execution_code",
        "parent_run_id": "run-1", "batch_id": "b1",
        "recorded_at": "2026-01-01T00:00:00Z",
        "child_agent_count": 1, "max_parallel": 2,
        "child_jobs": [{"job_id": "j1", "result_path": str(child),
                        "result_hash": _sha(child), "status": "completed"}],
        "main_agent_merge": {"merge_report_path": str(merge),
                             "merge_report_hash": _sha(merge),
                             "final_decision": "APPROVED", "blocking_buckets": []},
    }
    if not ledger_valid:
        ledger_body = {k: v for k, v in ledger_body.items() if k != "batch_id"}
    ledger = tmp_path / "v-ledger.json"
    ledger.write_text(json.dumps(ledger_body))
    patch_hash = _sha(patch)
    report = {
        "schema_version": "2.0",
        "router_invocation_id": "router-20260101T000000Z-abcdef12",
        "mode": "live", "review_target_kind": "code_only", "decision": "APPROVED",
        "validator_signature": {"validator": "gd-validate-route-report.py", "schema_version": "2.0"},
        "recorded_at": "2026-01-01T00:00:00Z", "findings": [],
        "diff_source": "git", "diff_hash": patch_hash,
        "patch_generation_method": "git_diff",
        "raw_result_path": str(patch), "raw_result_hash": patch_hash,
        "codex_raw_result_path": str(raw),
        "codex_raw_result_hash": ("a" * 64) if raw_hash_wrong else _sha(raw),
        "codex_mapped_result_path": str(mapped),
        "codex_mapped_result_hash": _sha(mapped),
        "codex_review_status": "completed", "codex_review_kind": "code_diff",
        "child_review_ledger_path": str(ledger),
        "child_review_ledger_hash": _sha(ledger),
    }
    if drop_ledger:
        report.pop("child_review_ledger_path", None)
        report.pop("child_review_ledger_hash", None)
    return report


def test_missing_child_review_ledger_negative(validator, tmp_path):
    report = _build_approved_report(tmp_path, drop_ledger=True)
    v = validator.validate_route_report(report)
    assert any("child_review_ledger_path" in x and "required" in x for x in v), v


def test_invalid_child_review_ledger_negative(validator, tmp_path):
    report = _build_approved_report(tmp_path, ledger_valid=False)
    v = validator.validate_route_report(report)
    assert any("stage-dispatch-ledger" in x for x in v), v


def test_hash_mismatch_negative(validator, tmp_path):
    report = _build_approved_report(tmp_path, raw_hash_wrong=True)
    v = validator.validate_route_report(report)
    assert any("does not match actual file hash" in x for x in v), v


def test_mapped_review_kind_mismatch_negative(validator, tmp_path):
    report = _build_approved_report(tmp_path, mapped_kind="plan")
    v = validator.validate_route_report(report)
    assert any("mapped JSON review_kind must be 'code_diff'" in x for x in v), v


def test_local_static_only_rejected_negative(validator, tmp_path):
    report = _build_approved_report(tmp_path)
    report["failure_code"] = "LOCAL_STATIC_ONLY"
    v = validator.validate_route_report(report)
    assert any("LOCAL_STATIC_ONLY" in x for x in v), v
