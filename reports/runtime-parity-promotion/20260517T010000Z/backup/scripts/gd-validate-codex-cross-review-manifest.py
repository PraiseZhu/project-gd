#!/usr/bin/env python3
"""gd-validate-codex-cross-review-manifest.py — manifest schema validator.

Usage: python3 scripts/gd-validate-codex-cross-review-manifest.py <manifest.json>
Exit 0 = valid; Exit 1 = invalid; Exit 2 = bad args.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "gd-codex-cross-review-manifest.schema.json"
ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
JOB_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def validate(manifest_path: str) -> list[str]:
    errors: list[str] = []
    p = Path(manifest_path)
    if not p.exists():
        return [f"FILE_NOT_FOUND: {manifest_path}"]
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"JSON_PARSE_ERROR: {e}"]

    if not isinstance(d, dict):
        return ["ROOT_NOT_OBJECT"]

    # target_set_id
    tid = d.get("target_set_id", "")
    if not isinstance(tid, str) or not ROLE_PATTERN.match(tid):
        errors.append(f"INVALID_TARGET_SET_ID: {tid!r} (must match ^[a-z][a-z0-9_-]{{0,63}}$)")

    jobs = d.get("required_jobs", [])
    if not isinstance(jobs, list) or len(jobs) == 0:
        errors.append("REQUIRED_JOBS_EMPTY_OR_MISSING")
        return errors
    if len(jobs) > 50:
        errors.append(f"TOO_MANY_JOBS: {len(jobs)} > 50")

    seen_ids: set[str] = set()
    seen_roles: set[str] = set()

    for i, job in enumerate(jobs):
        prefix = f"job[{i}]"
        if not isinstance(job, dict):
            errors.append(f"{prefix}: not an object")
            continue

        for field in ("queue_job_id", "target_role", "primary_target", "review_kind",
                      "expected_target_hash", "codex_raw_result_path", "raw_contract"):
            if field not in job:
                errors.append(f"{prefix}: missing required field '{field}'")

        qid = job.get("queue_job_id", "")
        if isinstance(qid, str) and qid:
            if not JOB_ID_PATTERN.match(qid):
                errors.append(f"{prefix}: invalid queue_job_id {qid!r}")
            if qid in seen_ids:
                errors.append(f"{prefix}: duplicate queue_job_id {qid!r}")
            seen_ids.add(qid)

        role = job.get("target_role", "")
        if isinstance(role, str) and role:
            if not ROLE_PATTERN.match(role):
                errors.append(f"{prefix}: invalid target_role {role!r} — must match ^[a-z][a-z0-9_-]{{0,63}}$ (no spaces, slashes, dots)")
            if role in seen_roles:
                errors.append(f"{prefix}: duplicate target_role {role!r}")
            seen_roles.add(role)

        rk = job.get("review_kind")
        if rk not in ("plan", "code"):
            errors.append(f"{prefix}: invalid review_kind {rk!r}")

        eth = job.get("expected_target_hash")
        if eth is not None and not (isinstance(eth, str) and HASH_PATTERN.match(eth)):
            errors.append(f"{prefix}: expected_target_hash must be 64-char hex or null, got {eth!r}")

        rc = job.get("raw_contract")
        if rc not in ("auto", "v1", "v2"):
            errors.append(f"{prefix}: invalid raw_contract {rc!r}")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <manifest.json>", file=sys.stderr)
        return 2
    errors = validate(sys.argv[1])
    if errors:
        print(f"MANIFEST_INVALID: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    njobs = len(d.get("required_jobs", []))
    print(f"MANIFEST_VALID: target_set_id={d['target_set_id']!r} jobs={njobs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
