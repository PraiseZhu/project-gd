#!/usr/bin/env python3
"""gd-validate-codex-cross-review-aggregate.py — aggregate schema validator.

Validates an aggregate JSON against the canonical schema
`schema/gd-codex-cross-review-aggregate.schema.json` (single source of truth —
no hardcoded field list, so the validator never drifts from the schema).

Usage: python3 scripts/gd-validate-codex-cross-review-aggregate.py <aggregate.json>
Exit 0 = valid; Exit 1 = invalid; Exit 2 = bad args / schema load error.

Consumed by gd-review-suite-controller.py:982.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

GD_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = GD_ROOT / "schema" / "gd-codex-cross-review-aggregate.schema.json"


def _structural_check(data: dict, schema: dict) -> list[str]:
    """Fallback validation (jsonschema unavailable): check top-level required +
    aggregate_version const, derived from the schema file so field expectations
    still come from the SSOT schema rather than a hardcoded list.

    Fail-closed hardening (SC-8 V13): the fallback must NOT pass an empty jobs[]
    just because jsonschema's minItems is unavailable — an empty job set means
    no review actually ran, which can never be a valid aggregate. We honor the
    schema's own jobs.minItems so the fallback stays SSOT-derived."""
    errors: list[str] = []
    for f in schema.get("required", []):
        if f not in data:
            errors.append(f"MISSING_REQUIRED: {f!r}")
    av_spec = schema.get("properties", {}).get("aggregate_version", {})
    if "const" in av_spec and data.get("aggregate_version") != av_spec["const"]:
        errors.append(
            f"WRONG_AGGREGATE_VERSION: expected {av_spec['const']!r}, "
            f"got {data.get('aggregate_version')!r}"
        )
    jobs = data.get("jobs")
    if "jobs" in data and not isinstance(jobs, list):
        errors.append("JOBS_NOT_ARRAY")
    elif isinstance(jobs, list):
        # Enforce jobs.minItems from the schema (default 1) so empty jobs[] is
        # rejected even in the no-jsonschema fallback path.
        min_items = schema.get("properties", {}).get("jobs", {}).get("minItems", 1)
        if len(jobs) < min_items:
            errors.append(
                f"JOBS_EMPTY: jobs[] has {len(jobs)} item(s), schema requires "
                f"minItems={min_items} (empty job set means no review ran)"
            )
    return errors


def validate(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return [f"FILE_NOT_FOUND: {path}"]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"JSON_PARSE_ERROR: {e}"]
    if not isinstance(data, dict):
        return ["ROOT_NOT_OBJECT"]

    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return [f"SCHEMA_LOAD_ERROR: {e}"]

    # Prefer full jsonschema validation; fall back to structural check.
    # SC-8 V5: do NOT silently downgrade to the lax fallback. Warn on stderr so
    # the missing-library degradation is visible, then run the (now fail-closed)
    # structural check rather than passing freely.
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
        return [
            f"{'/'.join(str(x) for x in err.path) or '<root>'}: {err.message}"
            for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        ]
    except ImportError:
        print(
            "WARN: jsonschema unavailable — falling back to structural check "
            "(additionalProperties / nested constraints NOT enforced). "
            "Install jsonschema for full validation.",
            file=sys.stderr,
        )
        return _structural_check(data, schema)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: gd-validate-codex-cross-review-aggregate.py <aggregate.json>", file=sys.stderr)
        return 2
    errors = validate(argv[1])
    if errors:
        for e in errors:
            print(f"AGGREGATE_INVALID: {e}", file=sys.stderr)
        return 1
    print(f"AGGREGATE_VALID: {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
