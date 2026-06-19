"""Regression tests for bridge finding sc_refs policy.

execution_outcome findings must bind to a real SC reference and fail closed when
they do not. code_diff keeps the legacy exception because those findings review
code quality rather than plan SC IDs.

Run either way:
    python3 tests/test_bridge_sc_refs_policy.py
    pytest tests/test_bridge_sc_refs_policy.py
"""
import importlib.util
import os
import sys
from pathlib import Path


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PROJECT_ROOT, "scripts")
sys.path.insert(0, SCRIPTS)


def _load_bridge():
    path = os.path.join(SCRIPTS, "gd-codex-bridge-review.py")
    spec = importlib.util.spec_from_file_location("gd_codex_bridge_review_sc_refs_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bridge = _load_bridge()
TEMPLATE_KIND_BY_REVIEW_KIND = {
    "execution_outcome": "gd-execution-outcome-review",
    "code_diff": "gd-code-diff-review",
}
PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")
        if "PYTEST_CURRENT_TEST" in os.environ:
            raise AssertionError(label)


def _raw_requires_changes_without_sc():
    return """# Code Review Result

VERDICT: REQUIRES_CHANGES

## Scope Checked

| Facet | Result | Evidence |
|-------|--------|----------|
| execution evidence | fail | verify output is missing |

## Findings

### Finding 1 [P1] missing verify output
问题: verify output is missing
证据: task_outcomes[0].verify_output is null
影响: cannot prove the run completed
最小修复: rerun verify and update the outcome artifact
验收: verify_output contains the command result

## Residual Risk

none
"""


def _v2_payload(kind, sc_refs):
    return {
        "schema_version": "2.0",
        "template_kind": TEMPLATE_KIND_BY_REVIEW_KIND[kind],
        "review_kind": kind,
        "review_target_kind": "execution_only_no_code" if kind == "execution_outcome" else "code_only",
        "target_role": "execution_artifact" if kind == "execution_outcome" else "code_diff",
        "reviewer": "codex",
        "review_target": str(Path("reports/example/result.json")),
        "review_run_status": "completed",
        "gd_review_decision": "REQUIRES_CHANGES",
        "source_of_truth_decision": {
            "location": "top_level_machine_header",
            "value": "REQUIRES_CHANGES",
        },
        "scope_checked": [
            {"area": "evidence", "result": "fail", "evidence": "verify output is missing"}
        ],
        "findings": [
            {
                "severity": "P1",
                "title": "missing verify output",
                "sc_refs": sc_refs,
                "evidence": "task_outcomes[0].verify_output is null",
                "impact": "cannot prove the run completed",
                "required_fix": "rerun verify and update the outcome artifact",
                "verify": "verify_output contains the command result",
            }
        ],
        "merge_notes": {"conflict_with_other_reviewer": False},
        "residual_risk": "",
        "timestamp": "2026-06-18T00:00:00Z",
    }


def test_v1_execution_outcome_empty_sc_refs_fail_closed():
    print("[v1 parser] execution_outcome empty sc_refs")
    mapped, errs = _bridge.parse_raw_to_mapped(
        "execution_outcome",
        "reports/example/execution-outcome.json",
        _raw_requires_changes_without_sc(),
        compat_v1=True,
    )
    check(errs and any("缺 SC" in e for e in errs), "returns missing-SC parse error")
    check(mapped["review_run_status"] == "degraded", "run status degraded")
    check(mapped["gd_review_decision"] == "FAILED", "decision FAILED")


def test_v1_code_diff_empty_sc_refs_legacy_exception():
    print("[v1 parser] code_diff empty sc_refs legacy exception")
    mapped, errs = _bridge.parse_raw_to_mapped(
        "code_diff",
        "reports/example/code.patch",
        _raw_requires_changes_without_sc(),
        compat_v1=True,
    )
    check(errs == [], "code_diff accepts empty sc_refs")
    check(mapped["review_run_status"] == "completed", "run status completed")
    check(mapped["gd_review_decision"] == "REQUIRES_CHANGES", "decision preserved")
    check(mapped["findings"][0]["sc_refs"] == [], "finding keeps empty sc_refs")


def test_v2_execution_outcome_empty_sc_refs_rejected():
    print("[v2 schema] execution_outcome empty sc_refs")
    errs = _bridge.validate_mapped_schema_v2(_v2_payload("execution_outcome", []))
    check(any("sc_refs" in e and "非空" in e for e in errs), "schema rejects empty sc_refs")


def test_v2_code_diff_empty_sc_refs_legacy_exception():
    print("[v2 schema] code_diff empty sc_refs legacy exception")
    errs = _bridge.validate_mapped_schema_v2(_v2_payload("code_diff", []))
    check(errs == [], "code_diff accepts empty sc_refs")


def main():
    test_v1_execution_outcome_empty_sc_refs_fail_closed()
    test_v1_code_diff_empty_sc_refs_legacy_exception()
    test_v2_execution_outcome_empty_sc_refs_rejected()
    test_v2_code_diff_empty_sc_refs_legacy_exception()
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
