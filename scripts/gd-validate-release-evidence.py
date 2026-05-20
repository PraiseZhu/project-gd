#!/usr/bin/env python3
"""gd-validate-release-evidence.py — Validate results/release-evidence/<run-id>/run-manifest.json.

Usage:
  python3 scripts/gd-validate-release-evidence.py <run-dir>

Exit codes:
  0 — run-manifest.json valid and all required_committed artifacts present
  1 — validation failure
  2 — file not found
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REQUIRED_MANIFEST_FIELDS = {"run_id", "created_at", "profile", "artifacts"}
REQUIRED_ARTIFACT_FIELDS = {"path", "sha256", "kind", "commit_policy"}
VALID_COMMIT_POLICIES = {"required_committed", "optional_committed", "gitignored_local_only"}
VALID_KINDS = {"capsule", "codex_output", "command_log", "manifest", "summary"}


def validate(run_dir: Path) -> list[str]:
    manifest_path = run_dir / "run-manifest.json"
    if not manifest_path.is_file():
        return [f"run-manifest.json not found in {run_dir}"]

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return [f"run-manifest.json invalid JSON: {e}"]

    errors = []
    missing = REQUIRED_MANIFEST_FIELDS - set(data.keys())
    if missing:
        errors.append(f"run-manifest.json missing fields: {sorted(missing)}")
        return errors

    artifacts = data["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty array")
        return errors

    for i, artifact in enumerate(artifacts):
        prefix = f"artifacts[{i}]"
        missing_a = REQUIRED_ARTIFACT_FIELDS - set(artifact.keys())
        if missing_a:
            errors.append(f"{prefix}: missing fields {sorted(missing_a)}")
            continue

        if not artifact["sha256"]:
            errors.append(f"{prefix}: sha256 must be non-empty")

        if len(artifact["sha256"]) != 64:
            errors.append(f"{prefix}: sha256 must be 64-char hex, got {len(artifact['sha256'])} chars")

        if artifact["kind"] not in VALID_KINDS:
            errors.append(f"{prefix}: kind '{artifact['kind']}' not in {sorted(VALID_KINDS)}")

        if artifact["commit_policy"] not in VALID_COMMIT_POLICIES:
            errors.append(f"{prefix}: commit_policy '{artifact['commit_policy']}' not in {sorted(VALID_COMMIT_POLICIES)}")

        if artifact["commit_policy"] == "required_committed":
            artifact_path = Path(artifact["path"])
            if not artifact_path.is_file():
                errors.append(f"{prefix}: required_committed but file not found: {artifact_path}")
            else:
                actual_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
                if actual_sha != artifact["sha256"]:
                    errors.append(f"{prefix}: sha256 mismatch — manifest={artifact['sha256'][:16]}... actual={actual_sha[:16]}...")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: gd-validate-release-evidence.py <run-dir>", file=sys.stderr)
        return 2

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"EVIDENCE_VALIDATE_FAIL: run-dir not found: {run_dir}", file=sys.stderr)
        return 2

    errors = validate(run_dir)
    if errors:
        print("EVIDENCE_VALIDATE_FAIL")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    print("EVIDENCE_VALIDATE_PASS")
    print(f"  RUN_DIR: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
