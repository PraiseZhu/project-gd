#!/usr/bin/env python3
"""gd-validate-subplan-codex-binding.py — Plan 7 subplan Codex binding validator (SSOT).

Validates that the Codex cross-review aggregate JSON records proper bindings for
all subplan review jobs in a parent close gate context.

Schema validation is delegated to gd-validate-codex-cross-review-aggregate.py
(which loads the canonical schema/gd-codex-cross-review-aggregate.schema.json).
This script adds binding-completeness checks on top.

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
import importlib.util
import json
import sys
from pathlib import Path

GD_ROOT = Path(__file__).resolve().parent.parent
_agg_val_path = GD_ROOT / "scripts" / "gd-validate-codex-cross-review-aggregate.py"

# Delegate schema validation to the canonical aggregate validator.
def _schema_errors(aggregate_path: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location("agg_val", _agg_val_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.validate(str(aggregate_path))


def validate(reports_dir: Path, aggregate_path: Path) -> list[str]:
    errors: list[str] = []

    if not reports_dir.is_dir():
        return [f"REPORTS_DIR_NOT_FOUND: {reports_dir}"]

    if not aggregate_path.exists():
        return [f"AGGREGATE_NOT_FOUND: {aggregate_path}"]

    # 1. Schema validation via canonical aggregate validator.
    schema_errs = _schema_errors(aggregate_path)
    if schema_errs:
        return [f"AGGREGATE_SCHEMA_INVALID: {e}" for e in schema_errs]

    try:
        agg = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"AGGREGATE_JSON_PARSE_ERROR: {e}"]

    # 2. Binding-completeness checks (jobs must reference valid roles/kinds).
    # SC-8 V13: an empty jobs[] means no subplan was actually bound to a Codex
    # round-2 result. The binding loop below would vacuously pass on []; reject
    # it explicitly so "no jobs" cannot serve as a signoff. (The delegated
    # aggregate schema validator also enforces minItems>=1, but this guard keeps
    # the binding check fail-closed even if that path ever relaxes.)
    jobs = agg.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return [
            "JOBS_EMPTY_OR_MISSING: aggregate has no jobs[] to bind — "
            "an empty job set cannot satisfy subplan Codex binding"
        ]
    for i, job in enumerate(jobs):
        if not isinstance(job, dict):
            errors.append(f"JOB[{i}]: not an object")
            continue
        job_id = job.get("queue_job_id", job.get("target_role", f"<job-{i}>"))
        prefix = f"JOB[{job_id}]"
        if not job.get("target_role"):
            errors.append(f"{prefix}: missing target_role")
        if not job.get("primary_target"):
            errors.append(f"{prefix}: missing primary_target")
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
