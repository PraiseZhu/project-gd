#!/usr/bin/env python3
"""
gd-validate-controller-report.py

Validator for the GD controller-report JSON format (schema_version 1.0 and 1.1).

NOTE: This validator accepts run_mode='fixture' reports. Fixture-mode rejection
is the responsibility of the parent close gate (Rule 1), not this validator.

Usage:
    python3 gd-validate-controller-report.py <path-to-report.json>
    python3 gd-validate-controller-report.py --self-test-minimal

Exit codes:
    0  — CONTROLLER_REPORT_VALID (or all self-tests passed)
    1  — all self-tests: one or more tests failed
    2  — CONTROLLER_REPORT_INVALID: missing_required_field or structural error
    3  — CONTROLLER_REPORT_INVALID: unreadable_or_malformed_json
    4  — CONTROLLER_REPORT_INVALID: batch_ledger_hash_mismatch or file_not_found
    5  — CONTROLLER_REPORT_INVALID: suite_target_closure_incomplete
"""

import hashlib
import json
import os
import sys
from pathlib import Path

# Canonical schema (single source of truth for field whitelist /
# additionalProperties:false enforcement). Hash/closure checks that the schema
# cannot express stay in the hand-written validators below.
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "gd-controller-report.schema.json"

# ---------------------------------------------------------------------------
# Required fields
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

VALID_EVIDENCE_KINDS = frozenset({"controller_approved", "mapped_status_approved", "n_a"})


# ---------------------------------------------------------------------------
# Shared structural validation
# ---------------------------------------------------------------------------
def find_missing_required_field(report: dict):
    """Return name of first missing required field, or None."""
    for f in REQUIRED_FIELDS:
        if f not in report:
            return f
    for gate_key in ("primary_gate", "secondary_gate"):
        gate = report.get(gate_key)
        if not isinstance(gate, dict):
            return f"{gate_key} (must be object)"
        for sub in ("verdict", "blocking"):
            if sub not in gate:
                return f"{gate_key}.{sub}"
    for i, job in enumerate(report.get("jobs", [])):
        if not isinstance(job, dict):
            return f"jobs[{i}] (must be object)"
        for jf in REQUIRED_JOB_FIELDS:
            if jf not in job:
                return f"jobs[{i}].{jf}"
    return None


# ---------------------------------------------------------------------------
# v1.1-specific validation
# ---------------------------------------------------------------------------
def _validate_v11(report: dict, report_path: Path) -> tuple[int, str]:
    """Validate v1.1-specific fields: batch_ledgers hashes + suite_target_closure closure."""

    # batch_ledgers -----------------------------------------------------------
    batch_ledgers = report.get("batch_ledgers")
    if batch_ledgers is None:
        return 2, "CONTROLLER_REPORT_INVALID: missing_required_field (batch_ledgers)"
    if not isinstance(batch_ledgers, list):
        return 2, "CONTROLLER_REPORT_INVALID: batch_ledgers must be array"

    for i, entry in enumerate(batch_ledgers):
        if not isinstance(entry, dict):
            return 2, f"CONTROLLER_REPORT_INVALID: batch_ledgers[{i}] must be object"
        path_str = entry.get("path")
        expected_hash = entry.get("hash")
        if not path_str:
            return 2, f"CONTROLLER_REPORT_INVALID: batch_ledgers[{i}].path missing"
        if not expected_hash:
            return 2, f"CONTROLLER_REPORT_INVALID: batch_ledgers[{i}].hash missing"

        p = Path(path_str)
        if not p.is_absolute():
            p = report_path.parent / p
        if not p.is_file():
            return 4, f"CONTROLLER_REPORT_INVALID: batch_ledger_file_not_found — {path_str!r}"
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected_hash:
            return 4, (
                f"CONTROLLER_REPORT_INVALID: batch_ledger_hash_mismatch — "
                f"{path_str!r}: expected {expected_hash!r}, got {actual!r}"
            )

    # suite_target_closure ----------------------------------------------------
    stc = report.get("suite_target_closure")
    if stc is None:
        return 2, "CONTROLLER_REPORT_INVALID: missing_required_field (suite_target_closure)"
    if not isinstance(stc, list):
        return 2, "CONTROLLER_REPORT_INVALID: suite_target_closure must be array"

    job_ids = {
        j.get("queue_job_id")
        for j in report.get("jobs", [])
        if isinstance(j, dict) and j.get("queue_job_id")
    }
    closure_ids = {
        e.get("target_id")
        for e in stc
        if isinstance(e, dict) and e.get("target_id")
    }
    missing_ids = job_ids - closure_ids
    if missing_ids:
        return 5, (
            f"CONTROLLER_REPORT_INVALID: suite_target_closure_incomplete — "
            f"missing entries for: {sorted(missing_ids)}"
        )

    for i, entry in enumerate(stc):
        if not isinstance(entry, dict):
            continue
        ek = entry.get("evidence_kind")
        if ek not in VALID_EVIDENCE_KINDS:
            return 2, (
                f"CONTROLLER_REPORT_INVALID: suite_target_closure[{i}].evidence_kind="
                f"{ek!r} not in {sorted(VALID_EVIDENCE_KINDS)}"
            )

    return 0, "CONTROLLER_REPORT_VALID"


# ---------------------------------------------------------------------------
# Unified validate entry point
# ---------------------------------------------------------------------------
def _schema_structural_errors(report: dict) -> list[str]:
    """SC-8 V9: run the canonical schema (additionalProperties:false) against the
    report so unknown/extra fields are rejected instead of silently accepted.

    Returns a list of error strings (empty == ok). When jsonschema is
    unavailable we emit a stderr WARN and return [] (the hand-written checks
    still run, but additionalProperties cannot be enforced without the library —
    surfaced rather than silent)."""
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARN: controller-report schema unreadable ({exc}); "
              "skipping additionalProperties enforcement", file=sys.stderr)
        return []
    try:
        import jsonschema
        validator = jsonschema.Draft7Validator(schema)
        return [
            f"{'/'.join(str(x) for x in e.path) or '<root>'}: {e.message}"
            for e in sorted(validator.iter_errors(report), key=lambda e: list(e.path))
        ]
    except ImportError:
        pass  # fall through to hand-written checks below

    # F3 fix (SC-8 V9/V11): jsonschema not available — enforce the two most
    # dangerous fail-open gaps with hand-written checks so the validator does
    # not silently accept broken reports in production environments that lack
    # the library (e.g. /usr/bin/python3 3.9.6).
    errs: list[str] = []
    # V9: additionalProperties — reject any key not declared in the schema.
    allowed_keys = set(schema.get("properties", {}).keys())
    if allowed_keys:
        for key in report:
            if key not in allowed_keys:
                errs.append(
                    f"<root>: Additional properties are not allowed "
                    f"('{key}' was unexpected)"
                )
    # V11: boolean fields must be actual booleans, not strings.
    bool_fields = [
        k for k, v in schema.get("properties", {}).items()
        if isinstance(v, dict) and v.get("type") == "boolean"
    ]
    for field in bool_fields:
        if field in report and not isinstance(report[field], bool):
            errs.append(
                f"{field}: must be boolean, got {type(report[field]).__name__!r} "
                f"(value={report[field]!r})"
            )
    return errs


def validate_report(report: dict, report_path: Path = Path(".")) -> tuple[int, str]:
    """Validate a parsed controller-report dict. Returns (exit_code, message)."""
    missing = find_missing_required_field(report)
    if missing is not None:
        return 2, f"CONTROLLER_REPORT_INVALID: missing_required_field ({missing})"

    # SC-8 V9: reject extra/unknown fields via the canonical schema before the
    # hash/closure semantic checks run.
    schema_errs = _schema_structural_errors(report)
    if schema_errs:
        return 2, f"CONTROLLER_REPORT_INVALID: schema_violation ({schema_errs[0]})"

    version = report.get("schema_version", "")
    if version == "1.1":
        return _validate_v11(report, report_path)
    elif version == "1.0":
        return 0, "CONTROLLER_REPORT_VALID"
    else:
        return 2, f"CONTROLLER_REPORT_INVALID: unsupported schema_version={version!r}"


# ---------------------------------------------------------------------------
# Self-test harness
# ---------------------------------------------------------------------------
def _minimal_live_report_v10() -> dict:
    return {
        "schema_version": "1.0",
        "run_mode": "live",
        "started_at": "2026-05-27T10:00:00Z",
        "finished_at": "2026-05-27T10:05:00Z",
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


def _minimal_live_report_v11() -> dict:
    base = _minimal_live_report_v10()
    return {
        **base,
        "schema_version": "1.1",
        "jobs": [],
        "batch_ledgers": [],
        "suite_target_closure": [],
    }


SELF_TESTS = [
    {
        "name": "pass — v1.0 live report with all required fields",
        "report": _minimal_live_report_v10(),
        "expected_exit": 0,
    },
    {
        "name": "pass — v1.1 live report (empty batch_ledgers and jobs)",
        "report": _minimal_live_report_v11(),
        "expected_exit": 0,
    },
    {
        "name": "pass — v1.1 fixture report accepted (not rejected)",
        "report": {**_minimal_live_report_v11(), "run_mode": "fixture"},
        "expected_exit": 0,
    },
    {
        "name": "fail — missing required field 'jobs'",
        "report": {k: v for k, v in _minimal_live_report_v10().items() if k != "jobs"},
        "expected_exit": 2,
    },
    {
        "name": "fail — v1.1 missing batch_ledgers field",
        "report": {k: v for k, v in _minimal_live_report_v11().items() if k != "batch_ledgers"},
        "expected_exit": 2,
    },
    {
        "name": "fail — v1.1 suite_target_closure incomplete (job has no closure entry)",
        "report": {
            **_minimal_live_report_v11(),
            "jobs": [
                {
                    "queue_job_id": "job-orphan",
                    "target_role": "plan",
                    "primary_target": "plans/step.md",
                    "bridge_exit": 0,
                    "bridge_stderr_path": None,
                    "bridge_stderr_summary": "none",
                    "raw_verdict": "APPROVED",
                    "mapped_status": "completed",
                    "aggregate_bucket": "primary",
                }
            ],
            "suite_target_closure": [],  # missing entry for job-orphan
        },
        "expected_exit": 5,
    },
    {
        "name": "fail — unsupported schema_version",
        "report": {**_minimal_live_report_v10(), "schema_version": "9.9"},
        "expected_exit": 2,
    },
]


def run_self_tests() -> int:
    """Run in-memory self-tests. Returns 0 if all pass, 1 otherwise."""
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

    report_path = Path(args[0])
    if not report_path.is_file():
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

    exit_code, message = validate_report(report, report_path)
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
