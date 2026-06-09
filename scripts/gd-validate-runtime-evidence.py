#!/usr/bin/env python3
"""gd-validate-runtime-evidence.py — Plan 6 runtime evidence validator (SSOT).

Validates a runtime evidence JSON file for parent close gate.
Called via subprocess from gd-validate-parent-close-gate.py when
parent_status requires runtime evidence (fully_completed, etc.).

Usage:
  python3 scripts/gd-validate-runtime-evidence.py <evidence_json_path>
  python3 scripts/gd-validate-runtime-evidence.py <evidence_json_path> --for-parent-status <status>

Exit codes:
  0 = evidence is valid
  1 = validation failures found (failures printed to stderr)
  2 = usage error / file not found
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = frozenset({
    "schema_version",
    "stage_id",
    "parent_status",
    "evidence_kind",
    "timestamp",
})

VALID_EVIDENCE_KINDS = frozenset({
    "stage_dispatch_ledger",
    "codex_aggregate",
    "combined",
})

VALID_PARENT_STATUSES = frozenset({
    "fully_completed",
    "complete_with_live_parallelism",
    "local_only_complete_with_codex_signoff",
    "requires_changes",
    "partial_completed",
})


def validate(path: Path, for_parent_status: str | None) -> list[str]:
    errors: list[str] = []

    if not path.exists():
        return [f"FILE_NOT_FOUND: {path}"]

    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"JSON_PARSE_ERROR: {e}"]

    if not isinstance(d, dict):
        return ["ROOT_NOT_OBJECT"]

    # Required fields present
    for f in REQUIRED_FIELDS:
        if f not in d:
            errors.append(f"MISSING_FIELD: {f!r}")

    if errors:
        return errors

    # schema_version
    if d.get("schema_version") != "1.0":
        errors.append(f"WRONG_SCHEMA_VERSION: expected '1.0', got {d.get('schema_version')!r}")

    # evidence_kind
    ek = d.get("evidence_kind")
    if ek not in VALID_EVIDENCE_KINDS:
        errors.append(f"INVALID_EVIDENCE_KIND: {ek!r}, expected one of {sorted(VALID_EVIDENCE_KINDS)}")

    # parent_status consistency
    recorded_status = d.get("parent_status")
    if recorded_status not in VALID_PARENT_STATUSES:
        errors.append(f"INVALID_PARENT_STATUS: {recorded_status!r}")

    if for_parent_status and recorded_status != for_parent_status:
        errors.append(
            f"PARENT_STATUS_MISMATCH: evidence records {recorded_status!r}, "
            f"caller expects {for_parent_status!r}"
        )

    # stage_id non-empty
    if not d.get("stage_id"):
        errors.append("EMPTY_STAGE_ID")

    # timestamp non-empty
    if not d.get("timestamp"):
        errors.append("EMPTY_TIMESTAMP")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a GD Plan 6 runtime evidence JSON."
    )
    parser.add_argument("evidence_json", help="Path to runtime evidence JSON file")
    parser.add_argument(
        "--for-parent-status",
        help="Expected parent_status value; checked for consistency with recorded value",
    )
    args = parser.parse_args()

    path = Path(args.evidence_json)
    failures = validate(path, args.for_parent_status)

    if failures:
        for f in failures:
            print(f"RUNTIME_EVIDENCE_INVALID: {f}", file=sys.stderr)
        return 1

    print(f"OK: runtime evidence valid ({path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
