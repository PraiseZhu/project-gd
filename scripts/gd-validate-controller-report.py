#!/usr/bin/env python3
"""
gd-validate-controller-report.py

Validator for the GD controller-report JSON format.

Usage:
    python3 gd-validate-controller-report.py <path-to-report.json>
    python3 gd-validate-controller-report.py --self-test-minimal

Exit codes:
    0  — CONTROLLER_REPORT_VALID (or all self-tests passed)
    1  — CONTROLLER_REPORT_INVALID: fixture_mode_rejected
    2  — CONTROLLER_REPORT_INVALID: missing_required_field
    3  — CONTROLLER_REPORT_INVALID: unreadable_or_malformed_json
"""

import json
import sys
import os

# ---------------------------------------------------------------------------
# Required top-level fields (mirrors schema required[])
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = [
    "schema_version",
    "run_mode",
    "started_at",
    "finished_at",
    "aggregate_path",
    "manifest_path",
    "primary_gate",
    "secondary_gate",
    "gate_consistent",
    "dirty_detected",
    "jobs",
]

# Required fields inside each job entry
REQUIRED_JOB_FIELDS = [
    "queue_job_id",
    "target_role",
    "primary_target",
    "bridge_exit",
    "bridge_stderr_path",
    "bridge_stderr_summary",
    "raw_verdict",
    "mapped_status",
    "aggregate_bucket",
]

# Fixture-mode sentinel values that make a report closure-ineligible
FIXTURE_BRIDGE_SUMMARY = "fixture_mode_no_real_bridge"
FIXTURE_GIT_GATE_STATUS = "fixture_mode"


def is_fixture_report(report: dict) -> bool:
    """Return True if this report should be rejected as fixture-mode."""
    if report.get("run_mode") == "fixture":
        return True
    for job in report.get("jobs", []):
        if job.get("bridge_stderr_summary") == FIXTURE_BRIDGE_SUMMARY:
            return True
        if job.get("git_gate_status") == FIXTURE_GIT_GATE_STATUS:
            return True
    return False


def find_missing_required_field(report: dict):
    """Return the name of the first missing required top-level field, or None."""
    for field in REQUIRED_FIELDS:
        if field not in report:
            return field
    # Validate sub-structure for primary_gate and secondary_gate
    for gate_key in ("primary_gate", "secondary_gate"):
        gate = report.get(gate_key)
        if not isinstance(gate, dict):
            return f"{gate_key} (must be object)"
        for sub in ("verdict", "blocking"):
            if sub not in gate:
                return f"{gate_key}.{sub}"
    # Validate jobs array entries
    for i, job in enumerate(report.get("jobs", [])):
        if not isinstance(job, dict):
            return f"jobs[{i}] (must be object)"
        for jf in REQUIRED_JOB_FIELDS:
            if jf not in job:
                return f"jobs[{i}].{jf}"
    return None


def validate_report(report: dict):
    """
    Validate a parsed controller-report dict.

    Returns (exit_code: int, message: str).
    """
    # 1. Check fixture-mode first (highest priority rejection)
    if is_fixture_report(report):
        return 1, "CONTROLLER_REPORT_INVALID: fixture_mode_rejected"

    # 2. Check required fields
    missing = find_missing_required_field(report)
    if missing is not None:
        return 2, f"CONTROLLER_REPORT_INVALID: missing_required_field ({missing})"

    return 0, "CONTROLLER_REPORT_VALID"


# ---------------------------------------------------------------------------
# Self-test harness
# ---------------------------------------------------------------------------

def _minimal_live_report():
    """Return a minimal valid live controller-report dict."""
    return {
        "schema_version": "1.0",
        "run_mode": "live",
        "started_at": "2026-05-17T10:00:00Z",
        "finished_at": "2026-05-17T10:05:00Z",
        "aggregate_path": "baselines/aggregate.json",
        "manifest_path": "manifest.json",
        "primary_gate": {"verdict": "APPROVED", "blocking": []},
        "secondary_gate": {"verdict": "APPROVED", "blocking": []},
        "gate_consistent": True,
        "dirty_detected": False,
        "jobs": [
            {
                "queue_job_id": "job-001",
                "target_role": "plan",
                "primary_target": "plans/step-2.md",
                "bridge_exit": 0,
                "bridge_stderr_path": None,
                "bridge_stderr_summary": "none",
                "raw_verdict": "APPROVED",
                "mapped_status": "approved",
                "aggregate_bucket": "primary",
            }
        ],
    }


SELF_TESTS = [
    {
        "name": "pass — live run with all required fields",
        "report": _minimal_live_report(),
        "expected_exit": 0,
    },
    {
        "name": "fail — run_mode=fixture → fixture_mode_rejected",
        "report": {**_minimal_live_report(), "run_mode": "fixture"},
        "expected_exit": 1,
    },
    {
        "name": "fail — missing required field 'jobs'",
        "report": {k: v for k, v in _minimal_live_report().items() if k != "jobs"},
        "expected_exit": 2,
    },
]


def run_self_tests() -> int:
    """Run in-memory self tests. Returns 0 if all pass, 1 otherwise."""
    all_passed = True
    for test in SELF_TESTS:
        exit_code, message = validate_report(test["report"])
        ok = exit_code == test["expected_exit"]
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {test['name']}")
        if not ok:
            print(f"       expected exit={test['expected_exit']}, got exit={exit_code} ({message})")
            all_passed = False
    return 0 if all_passed else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = sys.argv[1:]

    if not args:
        print("Usage: gd-validate-controller-report.py <report.json>", file=sys.stderr)
        print("       gd-validate-controller-report.py --self-test-minimal", file=sys.stderr)
        return 3

    if args[0] == "--self-test-minimal":
        return run_self_tests()

    report_path = args[0]
    if not os.path.isfile(report_path):
        print(f"CONTROLLER_REPORT_INVALID: file not found: {report_path}", file=sys.stderr)
        return 3

    try:
        with open(report_path, "r", encoding="utf-8") as fh:
            report = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"CONTROLLER_REPORT_INVALID: unreadable_or_malformed_json ({exc})", file=sys.stderr)
        return 3

    if not isinstance(report, dict):
        print("CONTROLLER_REPORT_INVALID: top-level value must be a JSON object", file=sys.stderr)
        return 3

    exit_code, message = validate_report(report)
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
