#!/usr/bin/env python3
"""gd-validate-review2-capsule.py — Validate a /review2 capsule before sending to Codex.

Usage:
  python3 scripts/gd-validate-review2-capsule.py --capsule <capsule.md>

Exit codes:
  0  — capsule valid, ready to send
  1  — validation failure
  2  — file not found
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_FIELDS = {
    "all": ["REVIEW_PROFILE:", "REVIEW_GOAL:", "OUTPUT_CONTRACT:"],
    "release_closure": [
        "INLINE_FACTS:",
        "git_status_short:",
        "staged_files:",
        "unstaged_files:",
        "release_gate_summary:",
        "final_status_summary:",
        "MANDATORY_READ:",
        "BLOCKING_CHECKS:",
    ],
    "runtime_parity": ["MANDATORY_READ:", "BLOCKING_CHECKS:"],
    "code_diff": [],
}

REQUIRED_OUTPUT_CONTRACT = [
    "MANDATORY_READ_COVERAGE:",
    "L3_GD_REVIEW_SEMANTICS: unchanged",
    "RELEASE_VERDICT:",
]


def validate(capsule_path: Path) -> list[str]:
    if not capsule_path.is_file():
        return [f"capsule file not found: {capsule_path}"]

    text = capsule_path.read_text(encoding="utf-8")
    errors = []

    # Extract profile
    m = re.search(r"^REVIEW_PROFILE:\s*(\S+)", text, re.MULTILINE)
    if not m:
        return ["missing REVIEW_PROFILE field"]
    profile = m.group(1)

    # Check all required fields
    for field in REQUIRED_FIELDS["all"] + REQUIRED_FIELDS.get(profile, []):
        if field not in text:
            errors.append(f"missing required field: {field}")

    # Check OUTPUT_CONTRACT contains required elements
    for elem in REQUIRED_OUTPUT_CONTRACT:
        if elem not in text:
            errors.append(f"OUTPUT_CONTRACT missing: {elem}")

    # For release_closure: ensure MANDATORY_READ has ≥1 entry with sha256
    if profile == "release_closure":
        sha_entries = re.findall(r"sha256:\s*([a-f0-9]{64})", text)
        if not sha_entries:
            errors.append("release_closure: MANDATORY_READ must include at least 1 sha256 entry")

        # Ensure OVERALL_RELEASE_STATUS appears in inline_facts/release_gate_summary
        if "OVERALL_RELEASE_STATUS" not in text and "release_gate_summary" in text:
            errors.append("release_closure: release_gate_summary must include OVERALL_RELEASE_STATUS")

        # Ensure NOT_APPLICABLE or explicit RELEASE_VERDICT: READY_FOR_COMMIT is declared
        if "RELEASE_VERDICT:" not in text:
            errors.append("release_closure: must declare RELEASE_VERDICT:")

    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate /review2 capsule before sending")
    p.add_argument("--capsule", required=True, help="Path to capsule.md")
    args = p.parse_args()

    capsule_path = Path(args.capsule)
    if not capsule_path.exists():
        print(f"CAPSULE_VALIDATE_FAIL: file not found: {capsule_path}", file=sys.stderr)
        return 2

    errors = validate(capsule_path)
    if errors:
        print("CAPSULE_VALIDATE_FAIL")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    m = __import__("re").search(r"REVIEW_PROFILE:\s*(\S+)",
                                 capsule_path.read_text(encoding="utf-8"), __import__("re").MULTILINE)
    profile = m.group(1) if m else "unknown"
    print(f"CAPSULE_VALIDATE_PASS")
    print(f"PROFILE: {profile}")
    print(f"CAPSULE: {capsule_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
