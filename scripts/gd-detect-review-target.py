#!/usr/bin/env python3
"""gd-detect-review-target.py — CLI wrapper for gd_review_detection.

Usage:
  python3 scripts/gd-detect-review-target.py <path> [--expect-kind <kind>]

Exits 0 if detected kind matches --expect-kind (or no --expect-kind given).
Exits 1 if kind is no_artifact or mismatch with --expect-kind.
Prints: REVIEW_TARGET_KIND: <kind>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gd_review_detection import (  # noqa: E402
    classify_artifacts,
    has_execution_artifacts_in_dir,
    is_execution_json,
)


def detect_kind(target: Path) -> str:
    if not target.exists():
        return "no_artifact"
    if target.is_file():
        if target.suffix == ".md":
            return classify_artifacts(True, False, False)
        if target.suffix == ".json" and is_execution_json(target):
            return classify_artifacts(False, True, False)
        return "no_artifact"
    if target.is_dir():
        has_plan = any(target.glob("**/*.md"))
        has_exec = has_execution_artifacts_in_dir(target)
        return classify_artifacts(has_plan, has_exec, False)
    return "no_artifact"


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect /gd review target kind")
    parser.add_argument("target", nargs="?", help="Path to plan file, execution JSON, or directory")
    parser.add_argument("--expect-kind", dest="expect_kind", default=None,
                        help="Expected target kind (optional; non-match → exit 1)")
    parser.add_argument("--cwd", default=None, help="Working directory (unused, for compat)")
    args = parser.parse_args()

    if args.target is None:
        kind = "no_artifact"
    else:
        kind = detect_kind(Path(args.target))

    print(f"REVIEW_TARGET_KIND: {kind}")

    if args.expect_kind and args.expect_kind != kind:
        print(f"MISMATCH: expected={args.expect_kind} got={kind}", file=sys.stderr)
        return 1
    if kind == "no_artifact":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
