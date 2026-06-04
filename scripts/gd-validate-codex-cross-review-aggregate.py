#!/usr/bin/env python3
"""gd-validate-codex-cross-review-aggregate.py — aggregate schema validator wrapper.

Validates an aggregate JSON against the extended gd-codex-cross-review-aggregate.schema.json.
Uses structural checks (no jsonschema dep required).

Usage: python3 scripts/gd-validate-codex-cross-review-aggregate.py <aggregate.json>
Exit 0 = valid; Exit 1 = invalid; Exit 2 = bad args.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TRANSPORT_OK = frozenset(["transport_ok", "transport_failed", "missing_primary_target"])
RUN_STATUS   = frozenset(["completed", "completed_with_constraint", "degraded", "failed_to_run"])
DECISION     = frozenset(["APPROVED", "REQUIRES_CHANGES", "FAILED"])
CODEX_VERD   = frozenset(["APPROVED", "REQUIRES_CHANGES", "FAILED", "MISSING"])


def validate(path: str) -> list[str]:
    errors: list[str] = []
    p = Path(path)
    if not p.exists():
        return [f"FILE_NOT_FOUND: {path}"]
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"JSON_PARSE_ERROR: {e}"]
    if not isinstance(d, dict):
        return ["ROOT_NOT_OBJECT"]

    # Required top-level fields
    for f in ("schema_version", "started_at", "finished_at", "queue_limit", "jobs", "coverage", "summary"):
        if f not in d:
            errors.append(f"MISSING_TOP_LEVEL: {f!r}")

    if d.get("schema_version") != "2.0":
        errors.append(f"WRONG_SCHEMA_VERSION: {d.get('schema_version')!r}")

    ql = d.get("queue_limit", 0)
    if not isinstance(ql, int) or ql < 1 or ql > 50:
        errors.append(f"INVALID_QUEUE_LIMIT: {ql}")

    # Jobs
    jobs = d.get("jobs", [])
    if not isinstance(jobs, list):
        errors.append("JOBS_NOT_ARRAY")
        jobs = []

    seen_ids: set[str] = set()
    for i, job in enumerate(jobs):
        prefix = f"job[{i}]"
        if not isinstance(job, dict):
            errors.append(f"{prefix}: not object"); continue

        for rf in ("queue_job_id", "target_role", "primary_target", "review_kind",
                   "transport_status", "review_run_status", "gd_review_decision", "codex_verdict", "findings"):
            if rf not in job:
                errors.append(f"{prefix}: missing {rf!r}")

        qid = job.get("queue_job_id", "")
        if isinstance(qid, str) and qid in seen_ids:
            errors.append(f"{prefix}: duplicate queue_job_id {qid!r}")
        if isinstance(qid, str): seen_ids.add(qid)

        role = job.get("target_role", "")
        if isinstance(role, str) and role and not ROLE_PATTERN.match(role):
            errors.append(f"{prefix}: target_role {role!r} violates pattern (no spaces, slashes, dots)")

        if job.get("transport_status") not in TRANSPORT_OK:
            errors.append(f"{prefix}: invalid transport_status {job.get('transport_status')!r}")
        if job.get("review_run_status") not in RUN_STATUS:
            errors.append(f"{prefix}: invalid review_run_status {job.get('review_run_status')!r}")
        if job.get("gd_review_decision") not in DECISION:
            errors.append(f"{prefix}: invalid gd_review_decision {job.get('gd_review_decision')!r}")
        if job.get("codex_verdict") not in CODEX_VERD:
            errors.append(f"{prefix}: invalid codex_verdict {job.get('codex_verdict')!r}")

        # transport_ok => raw_result_path and raw_result_hash required
        if job.get("transport_status") == "transport_ok":
            rrp = job.get("raw_result_path")
            rrh = job.get("raw_result_hash")
            if not isinstance(rrp, str) or not rrp:
                errors.append(f"{prefix}: transport_ok requires raw_result_path")
            if not isinstance(rrh, str) or not HASH_PATTERN.match(rrh or ""):
                errors.append(f"{prefix}: transport_ok requires raw_result_hash (64-char hex)")

    # Summary
    summary = d.get("summary", {})
    if not isinstance(summary, dict):
        errors.append("SUMMARY_NOT_OBJECT")
    else:
        for sf in ("transport_failed", "wrapper_schema_fail", "codex_approved",
                   "codex_requires_changes", "codex_failed", "missing_primary_target",
                   "stale_review_contract", "ambiguous_raw_result"):
            if sf not in summary:
                errors.append(f"SUMMARY_MISSING: {sf!r}")
            elif not isinstance(summary[sf], list):
                errors.append(f"SUMMARY_{sf.upper()}_NOT_ARRAY")

    # Coverage
    coverage = d.get("coverage", {})
    if not isinstance(coverage, dict):
        errors.append("COVERAGE_NOT_OBJECT")
    else:
        for cf in ("required_roles", "missing_roles"):
            if cf not in coverage:
                errors.append(f"COVERAGE_MISSING: {cf!r}")
        for role in coverage.get("required_roles", []):
            if not isinstance(role, str) or not ROLE_PATTERN.match(role):
                errors.append(f"COVERAGE: required_role {role!r} violates pattern")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <aggregate.json>", file=sys.stderr)
        return 2
    errors = validate(sys.argv[1])
    if errors:
        print(f"AGGREGATE_INVALID: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    njobs = len(d.get("jobs", []))
    print(f"AGGREGATE_VALID: jobs={njobs} schema_version={d.get('schema_version')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
