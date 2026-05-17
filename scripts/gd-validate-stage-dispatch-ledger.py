#!/usr/bin/env python3
"""
gd-validate-stage-dispatch-ledger.py

Validate a GD stage dispatch ledger JSON file against the schema
gd-stage-dispatch-ledger.schema.json.

Usage:
    python3 gd-validate-stage-dispatch-ledger.py <ledger.json>
    python3 gd-validate-stage-dispatch-ledger.py --self-test-minimal

Exit codes:
    0  — valid (or all self-tests passed)
    1  — invalid / test failure
"""

import json
import os
import re
import sys
import tempfile

# ---------------------------------------------------------------------------
# Schema path (relative to this script)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.join(_SCRIPT_DIR, "..", "schema", "gd-stage-dispatch-ledger.schema.json")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VALID_STAGES = {"plan", "review_plan", "execute", "review_execution_code"}
_VALID_STATUSES = {"completed", "failed", "transport_failed"}
_VALID_DECISIONS = {"APPROVED", "REQUIRES_CHANGES", "FAILED", "CLOSURE_INELIGIBLE"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Manual validator (fallback when jsonschema is not available)
# ---------------------------------------------------------------------------
def _validate_manual(data):
    """Return list of error strings; empty list means valid."""
    errors = []

    def check(condition, msg):
        if not condition:
            errors.append(msg)

    if not isinstance(data, dict):
        return ["top-level value must be an object"]

    # schema_version
    check(data.get("schema_version") == "1.0",
          "schema_version must be '1.0'")

    # stage
    check(data.get("stage") in _VALID_STAGES,
          f"stage must be one of {sorted(_VALID_STAGES)}, got {data.get('stage')!r}")

    # parent_run_id
    prid = data.get("parent_run_id")
    check(isinstance(prid, str) and len(prid) >= 1,
          "parent_run_id must be a non-empty string")

    # recorded_at
    check(isinstance(data.get("recorded_at"), str),
          "recorded_at must be a string")

    # child_agent_count
    cac = data.get("child_agent_count")
    check(isinstance(cac, int) and not isinstance(cac, bool),
          "child_agent_count must be an integer")
    if isinstance(cac, int) and not isinstance(cac, bool):
        check(cac >= 1, f"child_agent_count minimum is 1, got {cac}")
        check(cac <= 2, f"child_agent_count maximum is 2, got {cac}")

    # max_parallel
    mp = data.get("max_parallel")
    check(isinstance(mp, int) and not isinstance(mp, bool),
          "max_parallel must be an integer")
    if isinstance(mp, int) and not isinstance(mp, bool):
        check(mp >= 1, f"max_parallel minimum is 1, got {mp}")
        check(mp <= 2, f"max_parallel maximum is 2, got {mp}")

    # child_jobs
    cj = data.get("child_jobs")
    check(isinstance(cj, list),
          "child_jobs must be an array")
    if isinstance(cj, list):
        for idx, job in enumerate(cj):
            prefix = f"child_jobs[{idx}]"
            if not isinstance(job, dict):
                errors.append(f"{prefix} must be an object")
                continue
            check(isinstance(job.get("job_id"), str),
                  f"{prefix}.job_id must be a string")
            check(isinstance(job.get("result_path"), str),
                  f"{prefix}.result_path must be a string")
            rh = job.get("result_hash")
            check(isinstance(rh, str) and bool(_SHA256_RE.match(rh or "")),
                  f"{prefix}.result_hash must be a 64-char lowercase hex SHA-256, got {rh!r}")
            check(job.get("status") in _VALID_STATUSES,
                  f"{prefix}.status must be one of {sorted(_VALID_STATUSES)}, got {job.get('status')!r}")

    # cross-check: len(child_jobs) must equal child_agent_count
    if isinstance(cj, list) and isinstance(cac, int) and not isinstance(cac, bool):
        check(len(cj) == cac,
              f"len(child_jobs)={len(cj)} must equal child_agent_count={cac}")

    # cross-check: child_agent_count must not exceed max_parallel
    if isinstance(cac, int) and not isinstance(cac, bool) and isinstance(mp, int) and not isinstance(mp, bool):
        check(cac <= mp,
              f"child_agent_count={cac} must be <= max_parallel={mp}")

    # cross-check: if final_decision=APPROVED, all child jobs must have status=completed
    mam_pre = data.get("main_agent_merge")
    if isinstance(mam_pre, dict) and mam_pre.get("final_decision") == "APPROVED" and isinstance(cj, list):
        for idx, job in enumerate(cj):
            if isinstance(job, dict) and job.get("status") != "completed":
                errors.append(
                    f"child_jobs[{idx}].status={job.get('status')!r} but "
                    f"final_decision=APPROVED requires all jobs to be completed"
                )

    # main_agent_merge
    mam = data.get("main_agent_merge")
    check(isinstance(mam, dict),
          "main_agent_merge must be an object")
    if isinstance(mam, dict):
        check(isinstance(mam.get("merge_report_path"), str),
              "main_agent_merge.merge_report_path must be a string")
        mrh = mam.get("merge_report_hash")
        check(isinstance(mrh, str) and bool(_SHA256_RE.match(mrh or "")),
              f"main_agent_merge.merge_report_hash must be a 64-char lowercase hex SHA-256, got {mrh!r}")
        check(mam.get("final_decision") in _VALID_DECISIONS,
              f"main_agent_merge.final_decision must be one of {sorted(_VALID_DECISIONS)}, "
              f"got {mam.get('final_decision')!r}")
        check(isinstance(mam.get("blocking_buckets"), list),
              "main_agent_merge.blocking_buckets must be an array")

    # required top-level keys
    required = {
        "schema_version", "stage", "parent_run_id", "recorded_at",
        "child_agent_count", "max_parallel", "child_jobs", "main_agent_merge",
    }
    missing = required - set(data.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    return errors


# ---------------------------------------------------------------------------
# jsonschema-based validator (preferred when available)
# ---------------------------------------------------------------------------
def _validate_with_jsonschema(data, schema):
    """Return list of error strings; empty list means valid."""
    try:
        import jsonschema
        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        return [e.message for e in errs]
    except ImportError:
        return None  # signal caller to fall back


# ---------------------------------------------------------------------------
# Unified validate entry point
# ---------------------------------------------------------------------------
def _validate_cross_checks(data):
    """Semantic cross-checks that run regardless of jsonschema availability."""
    errors = []
    if not isinstance(data, dict):
        return errors

    cac = data.get("child_agent_count")
    mp = data.get("max_parallel")
    cj = data.get("child_jobs")
    mam = data.get("main_agent_merge")

    if isinstance(cac, int) and not isinstance(cac, bool) and isinstance(cj, list):
        if len(cj) != cac:
            errors.append(f"len(child_jobs)={len(cj)} must equal child_agent_count={cac}")

    if (isinstance(cac, int) and not isinstance(cac, bool) and
            isinstance(mp, int) and not isinstance(mp, bool)):
        if cac > mp:
            errors.append(f"child_agent_count={cac} must be <= max_parallel={mp}")

    if isinstance(mam, dict) and mam.get("final_decision") == "APPROVED" and isinstance(cj, list):
        for idx, job in enumerate(cj):
            if isinstance(job, dict) and job.get("status") != "completed":
                errors.append(
                    f"child_jobs[{idx}].status={job.get('status')!r} but "
                    f"final_decision=APPROVED requires all jobs to be completed"
                )

    return errors


def validate(data):
    """Return list of error strings. Empty == valid."""
    # Try loading schema for jsonschema validation
    try:
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)
        result = _validate_with_jsonschema(data, schema)
        if result is not None:
            return result + _validate_cross_checks(data)
    except (OSError, json.JSONDecodeError):
        pass  # schema file not found or malformed — fall through to manual

    return _validate_manual(data)


# ---------------------------------------------------------------------------
# Self-test fixtures
# ---------------------------------------------------------------------------
_GOOD_JOB = {
    "job_id": "job-001",
    "result_path": "results/child-001.json",
    "result_hash": "a" * 64,
    "status": "completed",
}

_GOOD_MERGE = {
    "merge_report_path": "reports/merge-001.md",
    "merge_report_hash": "b" * 64,
    "final_decision": "APPROVED",
    "blocking_buckets": [],
}


def _make_base(**overrides):
    base = {
        "schema_version": "1.0",
        "stage": "plan",
        "parent_run_id": "run-abc-123",
        "recorded_at": "2026-05-17T10:00:00Z",
        "child_agent_count": 1,
        "max_parallel": 1,
        "child_jobs": [_GOOD_JOB],
        "main_agent_merge": _GOOD_MERGE,
    }
    base.update(overrides)
    return base


_SELF_TESTS = [
    # (description, data, expect_valid)
    (
        "pass: 1 child, all valid fields",
        _make_base(),
        True,
    ),
    (
        "pass: 2 children, all valid fields",
        _make_base(
            child_agent_count=2,
            max_parallel=2,
            child_jobs=[
                _GOOD_JOB,
                {**_GOOD_JOB, "job_id": "job-002", "result_hash": "c" * 64},
            ],
        ),
        True,
    ),
    (
        "fail: child_agent_count=0 (below minimum 1)",
        _make_base(child_agent_count=0, child_jobs=[]),
        False,
    ),
    (
        "fail: child_agent_count=3 (above maximum 2)",
        _make_base(child_agent_count=3),
        False,
    ),
    (
        "fail: len(child_jobs) != child_agent_count (mismatch)",
        _make_base(child_agent_count=2, child_jobs=[_GOOD_JOB]),  # count=2 but 1 job
        False,
    ),
    (
        "fail: child_agent_count > max_parallel",
        _make_base(child_agent_count=2, max_parallel=1, child_jobs=[_GOOD_JOB, {**_GOOD_JOB, "job_id": "job-002", "result_hash": "c" * 64}]),
        False,
    ),
    (
        "fail: final_decision=APPROVED but child job status=failed",
        _make_base(
            child_jobs=[{**_GOOD_JOB, "status": "failed"}],
            main_agent_merge={**_GOOD_MERGE, "final_decision": "APPROVED"},
        ),
        False,
    ),
    (
        "fail: missing main_agent_merge.merge_report_path",
        _make_base(
            main_agent_merge={
                k: v for k, v in _GOOD_MERGE.items() if k != "merge_report_path"
            }
        ),
        False,
    ),
]


def run_self_tests():
    all_pass = True
    for desc, data, expect_valid in _SELF_TESTS:
        errors = validate(data)
        is_valid = len(errors) == 0
        if is_valid == expect_valid:
            print(f"PASS: {desc}")
        else:
            verdict = "valid" if is_valid else "invalid"
            expected = "valid" if expect_valid else "invalid"
            print(f"FAIL: {desc}")
            print(f"      expected={expected}, got={verdict}")
            if errors:
                for e in errors:
                    print(f"      error: {e}")
            all_pass = False
    return all_pass


# ---------------------------------------------------------------------------
# File validation entry point
# ---------------------------------------------------------------------------
def validate_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"LEDGER_INVALID: file not found: {path}")
        return False
    except json.JSONDecodeError as exc:
        print(f"LEDGER_INVALID: JSON parse error: {exc}")
        return False

    errors = validate(data)
    if errors:
        print("LEDGER_INVALID")
        for e in errors:
            print(f"  reason: {e}")
        return False

    print("LEDGER_VALID")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]

    if "--self-test-minimal" in args:
        ok = run_self_tests()
        sys.exit(0 if ok else 1)

    if not args:
        print("Usage: gd-validate-stage-dispatch-ledger.py <ledger.json>", file=sys.stderr)
        print("       gd-validate-stage-dispatch-ledger.py --self-test-minimal", file=sys.stderr)
        sys.exit(1)

    path = args[0]
    ok = validate_file(path)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
