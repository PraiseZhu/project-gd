#!/usr/bin/env python3
"""gd-test-bridge-parser.py — Regression test for gd-codex-bridge-review.py parser logic.

Imports RESULT_PATH_RE from bridge to keep parser behaviour locked across both
the bridge implementation and this test driver (any change to the regex breaks
tests here, making parser drift visible immediately).

Usage:
  python3 scripts/gd-test-bridge-parser.py
  python3 scripts/gd-test-bridge-parser.py --verbose

Exit codes:
  0 = all tests passed
  1 = one or more tests failed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Import the canonical parser constant from bridge (SSOT lock).
# Uses importlib because the filename contains hyphens (not valid Python identifiers).
import importlib.util as _ilu

_bridge_path = Path(__file__).resolve().parent / "gd-codex-bridge-review.py"
_spec = _ilu.spec_from_file_location("gd_codex_bridge_review", _bridge_path)
_bridge = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_bridge)  # type: ignore[union-attr]
RESULT_PATH_RE = _bridge.RESULT_PATH_RE
parse_writer_result_path = _bridge.parse_writer_result_path


PASS = "PASS"
FAIL = "FAIL"

CASES: list[tuple[str, str | None, str]] = [
    # (description, expected_result, writer_stdout_sample)
    (
        "APPROVED: Full result at end of line",
        "/path/to/result.json",
        "Review complete. Full result: /path/to/result.json",
    ),
    (
        "REQUIRES_CHANGES: inline Full result",
        "/path/to/result.json",
        "REQUIRES_CHANGES. Full result: /path/to/result.json",
    ),
    (
        "MALFORMED: inline with shell var literal",
        "${RESULT_FILE}",
        "Some output. Full result: ${RESULT_FILE}",
    ),
    (
        "Full result on its own line",
        "/results/run-id/result.json",
        "Line before.\nFull result: /results/run-id/result.json\nLine after.",
    ),
    (
        "No Full result → None",
        None,
        "Writer output with no result path marker.",
    ),
    (
        "Empty string → None",
        None,
        "",
    ),
    (
        "Full result with leading whitespace",
        "/path/to/result.json",
        "    Full result: /path/to/result.json",
    ),
    (
        "Multiple occurrences: return first",
        "/first/result.json",
        "Full result: /first/result.json\nFull result: /second/result.json",
    ),
]


def run_tests(verbose: bool) -> int:
    failures = 0
    for desc, expected, stdout in CASES:
        got = parse_writer_result_path(stdout)
        status = PASS if got == expected else FAIL
        if status == FAIL:
            failures += 1
        if verbose or status == FAIL:
            print(f"  [{status}] {desc}")
            if status == FAIL:
                print(f"         expected: {expected!r}")
                print(f"         got:      {got!r}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge parser regression tests.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    total = len(CASES)
    failures = run_tests(args.verbose)
    passed = total - failures

    if failures:
        print(f"\nBRIDGE_PARSER_TEST: {failures}/{total} FAILED", file=sys.stderr)
        return 1

    print(f"OK: bridge parser tests {passed}/{total} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
