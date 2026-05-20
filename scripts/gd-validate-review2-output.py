#!/usr/bin/env python3
"""gd-validate-review2-output.py — Validate Codex output for mandatory_read coverage.

Parses MANDATORY_READ_COVERAGE section from Codex output and compares against
the capsule's MANDATORY_READ list. For release_closure: 'missing' blocks result.

Usage:
  python3 scripts/gd-validate-review2-output.py \
    --capsule <capsule.md> \
    --output <codex-output.md>

Exit codes:
  0  — coverage complete (all mandatory reads accounted for)
  1  — coverage fail (missing entries, or release_closure with 'missing' status)
  2  — file not found or parse error
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_STATUSES = {"read", "summarized_by_preflight", "out_of_scope", "missing"}


def extract_mandatory_reads_from_capsule(text: str) -> list[str]:
    """Extract MANDATORY_READ path list from capsule.md."""
    paths = re.findall(r"^\s*-\s*path:\s*(.+)$", text, re.MULTILINE)
    return [p.strip() for p in paths]


def extract_profile(text: str) -> str:
    m = re.search(r"^REVIEW_PROFILE:\s*(\S+)", text, re.MULTILINE)
    return m.group(1) if m else "unknown"


def extract_coverage_from_output(text: str) -> tuple[dict[str, str], list[str]]:
    """Parse MANDATORY_READ_COVERAGE: section from Codex output.

    Expects lines like:
      - path/to/file: read
      - path/to/file: out_of_scope
    Returns ({path: status}, [duplicate_paths]) — enforces exactly-once per path.
    """
    coverage: dict[str, str] = {}
    duplicates: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line.strip() == "MANDATORY_READ_COVERAGE:":
            in_section = True
            continue
        if in_section:
            if not line.strip() or (line.strip() and not line.startswith(" ") and not line.startswith("-")):
                break
            m = re.match(r"\s*-\s*(.+?):\s*(\S+)", line)
            if m:
                path = m.group(1).strip()
                status = m.group(2).strip().lower()
                if path in coverage:
                    duplicates.append(path)
                else:
                    coverage[path] = status
    return coverage, duplicates


def validate_coverage(capsule_path: Path, output_path: Path) -> list[str]:
    if not capsule_path.is_file():
        return [f"capsule not found: {capsule_path}"]
    if not output_path.is_file():
        return [f"output not found: {output_path}"]

    capsule_text = capsule_path.read_text(encoding="utf-8")
    output_text = output_path.read_text(encoding="utf-8")
    errors = []

    profile = extract_profile(capsule_text)
    mandatory_paths = extract_mandatory_reads_from_capsule(capsule_text)

    if not mandatory_paths:
        if "MANDATORY_READ_COVERAGE:" not in output_text:
            errors.append("output missing MANDATORY_READ_COVERAGE: section")
        return errors

    # Parse coverage from output (exactly-once enforced)
    coverage, duplicates = extract_coverage_from_output(output_text)
    for dup in duplicates:
        errors.append(f"mandatory_read path appears more than once in coverage: {dup} (must be exactly once)")

    for path in mandatory_paths:
        if path not in coverage:
            errors.append(f"mandatory_read not covered in output: {path} (MISSING)")
            # validator infers 'missing' for unlisted entries
            if profile == "release_closure":
                errors.append(f"  release_closure: 'missing' for {path} blocks RELEASE_VERDICT")
        else:
            status = coverage[path]
            if status not in ALLOWED_STATUSES:
                errors.append(f"{path}: invalid status '{status}' (allowed: {sorted(ALLOWED_STATUSES)})")
            elif status == "missing":
                errors.append(f"{path}: status='missing' — Codex did not cover this mandatory read")
                if profile == "release_closure":
                    errors.append(f"  release_closure: 'missing' blocks RELEASE_VERDICT")
            elif status == "out_of_scope":
                # Must have OUT_OF_SCOPE_REASON
                if f"OUT_OF_SCOPE_REASON: {path}:" not in output_text:
                    errors.append(f"{path}: out_of_scope requires OUT_OF_SCOPE_REASON: {path}: <reason>")

    # Check for extra coverage entries not in capsule (informational only)
    for path, status in coverage.items():
        if path not in mandatory_paths:
            pass  # extra coverage is fine, not an error

    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate mandatory_read coverage in Codex output")
    p.add_argument("--capsule", required=True, help="Path to capsule.md (contains MANDATORY_READ list)")
    p.add_argument("--output", required=True, help="Path to Codex output markdown")
    args = p.parse_args()

    capsule_path = Path(args.capsule)
    output_path = Path(args.output)

    for f, label in [(capsule_path, "capsule"), (output_path, "output")]:
        if not f.exists():
            print(f"COVERAGE_VALIDATE_FAIL: {label} not found: {f}", file=sys.stderr)
            return 2

    errors = validate_coverage(capsule_path, output_path)

    capsule_text = capsule_path.read_text(encoding="utf-8")
    profile = extract_profile(capsule_text)
    coverage, _ = extract_coverage_from_output(output_path.read_text(encoding="utf-8"))
    mandatory_paths = extract_mandatory_reads_from_capsule(capsule_text)

    if errors:
        print("COVERAGE_VALIDATE_FAIL")
        print(f"  PROFILE: {profile}")
        print(f"  MANDATORY_READ_COUNT: {len(mandatory_paths)}")
        print(f"  COVERED_COUNT: {sum(1 for p in mandatory_paths if p in coverage and coverage[p] != 'missing')}")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    print("COVERAGE_VALIDATE_PASS")
    print(f"  PROFILE: {profile}")
    print(f"  MANDATORY_READ_COUNT: {len(mandatory_paths)}")
    print(f"  COVERED_COUNT: {len(mandatory_paths)}")
    for path, status in coverage.items():
        print(f"  {path}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
