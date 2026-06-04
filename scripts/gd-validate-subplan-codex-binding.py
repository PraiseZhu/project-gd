#!/usr/bin/env python3
"""gd-validate-subplan-codex-binding.py — Plan 7 subplan Codex binding validator (SSOT).

Validates that the Codex cross-review aggregate JSON records proper bindings for
all subplan review jobs in a parent close gate context.

Called via subprocess from gd-validate-parent-close-gate.py.

Usage:
  python3 scripts/gd-validate-subplan-codex-binding.py \
      --reports-dir <path> \
      --aggregate-json <path>

Exit codes:
  0 = all bindings valid
  1 = binding failures found (failures printed to stderr)
  2 = usage error / file not found
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_AGG_FIELDS = frozenset({"schema_version", "jobs", "summary"})
VALID_TRANSPORT = frozenset({"transport_ok", "transport_failed", "missing_primary_target"})
VALID_DECISIONS = frozenset({"APPROVED", "REQUIRES_CHANGES", "FAILED", "MISSING"})


def validate(reports_dir: Path, aggregate_path: Path) -> list[str]:
    errors: list[str] = []

    if not reports_dir.is_dir():
        return [f"REPORTS_DIR_NOT_FOUND: {reports_dir}"]

    if not aggregate_path.exists():
        return [f"AGGREGATE_NOT_FOUND: {aggregate_path}"]

    try:
        agg = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"AGGREGATE_JSON_PARSE_ERROR: {e}"]

    if not isinstance(agg, dict):
        return ["AGGREGATE_ROOT_NOT_OBJECT"]

    for f in REQUIRED_AGG_FIELDS:
        if f not in agg:
            errors.append(f"AGGREGATE_MISSING_FIELD: {f!r}")

    if errors:
        return errors

    if agg.get("schema_version") != "2.0":
        errors.append(
            f"AGGREGATE_WRONG_SCHEMA_VERSION: expected '2.0', "
            f"got {agg.get('schema_version')!r}"
        )

    jobs = agg.get("jobs", [])
    if not isinstance(jobs, list):
        return ["AGGREGATE_JOBS_NOT_ARRAY"]

    for i, job in enumerate(jobs):
        if not isinstance(job, dict):
            errors.append(f"JOB[{i}]: not an object")
            continue

        job_id = job.get("queue_job_id", f"<job-{i}>")
        prefix = f"JOB[{job_id}]"

        # transport_status must be present and valid
        ts = job.get("transport_status")
        if ts not in VALID_TRANSPORT:
            errors.append(f"{prefix}: invalid transport_status {ts!r}")

        # codex_verdict must be present for transport_ok jobs
        if ts == "transport_ok":
            cv = job.get("codex_verdict")
            if cv not in VALID_DECISIONS:
                errors.append(f"{prefix}: invalid codex_verdict {cv!r} for transport_ok job")

        # target_role must be present
        if not job.get("target_role"):
            errors.append(f"{prefix}: missing target_role")

        # primary_target must be non-empty
        if not job.get("primary_target"):
            errors.append(f"{prefix}: missing primary_target")

        # review_kind must be non-empty
        if not job.get("review_kind"):
            errors.append(f"{prefix}: missing review_kind")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate subplan Codex review binding in aggregate JSON."
    )
    parser.add_argument("--reports-dir", required=True, help="Path to reports directory")
    parser.add_argument("--aggregate-json", required=True, help="Path to aggregate JSON file")
    args = parser.parse_args()

    failures = validate(Path(args.reports_dir), Path(args.aggregate_json))

    if failures:
        for f in failures:
            print(f"SUBPLAN_BINDING_INVALID: {f}", file=sys.stderr)
        return 1

    print(f"OK: subplan Codex binding valid ({args.aggregate_json})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
