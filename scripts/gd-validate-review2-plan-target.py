#!/usr/bin/env python3
"""gd-validate-review2-plan-target.py — field-based plan preflight for /review2.

Validates that a plan file passed as --target to /review2 plan_review is a
genuine plan (not a capsule, not an old /rev-style file) and contains the
minimum required fields.

Exit codes:
  0  PLAN_TEMPLATE_STATUS: pass
  1  PLAN_TEMPLATE_STATUS: fail
  2  usage error

Output (stdout):
  PLAN_TEMPLATE_STATUS: pass | fail
  PLAN_ERROR: <description>          (only on fail, one line per error)
  BRIDGE_INVOCATION_STATUS: not_started | allowed
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.sc_extraction import extract_sc_ids  # noqa: E402
from lib.path_classification import is_review2_capsule_path  # noqa: E402

# Patterns required in a compliant plan (either template style)
_REVIEW_DOMAIN_RE = re.compile(r"REVIEW_DOMAIN[：:]", re.IGNORECASE)
_REVIEW_FOCUS_RE = re.compile(r"REVIEW_FOCUS[：:]", re.IGNORECASE)

# At least one of the four step-field keywords must appear
_WHERE_RE = re.compile(r"^\s*WHERE[：:]", re.MULTILINE)
_WHAT_RE = re.compile(r"^\s*WHAT[：:]", re.MULTILINE)
_WHY_RE = re.compile(r"^\s*WHY[：:]", re.MULTILINE)
_VERIFY_RE = re.compile(r"^\s*VERIFY[：:]", re.MULTILINE)

# Old /rev-style markers that must NOT appear
_REV_VERDICT_RE = re.compile(r"^REV_VERDICT[：:]", re.MULTILINE)
_BARE_VERDICT_RE = re.compile(r"^VERDICT[：:]", re.MULTILINE)
_REVIEW_STANDARD_RE = re.compile(r"^REVIEW_STANDARD[：:]", re.MULTILINE)


def _validate(target_path: str) -> list[str]:
    """Return list of error strings; empty list = pass."""
    errors: list[str] = []

    # --- Guard: capsule target ---
    if is_review2_capsule_path(target_path):
        errors.append(
            f"target is a capsule file ({Path(target_path).name}), "
            "not an original plan — use original plan path for /review2 plan_review"
        )
        return errors  # no point checking further

    # --- Read file ---
    p = Path(target_path)
    if not p.exists():
        errors.append(f"target file not found: {target_path}")
        return errors

    text = p.read_text(encoding="utf-8")

    # --- SC-IDs (≥1 required) ---
    sc_ids = extract_sc_ids(text)
    if not sc_ids:
        errors.append("no SC-IDs found (≥1 required: SC-1, SC-W2, etc.)")

    # --- REVIEW_DOMAIN / REVIEW_FOCUS ---
    if not _REVIEW_DOMAIN_RE.search(text):
        errors.append("missing REVIEW_DOMAIN field")
    if not _REVIEW_FOCUS_RE.search(text):
        errors.append("missing REVIEW_FOCUS field")

    # --- WHERE / WHAT / WHY / VERIFY (all 4 must appear) ---
    for field, pattern in [
        ("WHERE", _WHERE_RE),
        ("WHAT", _WHAT_RE),
        ("WHY", _WHY_RE),
        ("VERIFY", _VERIFY_RE),
    ]:
        if not pattern.search(text):
            errors.append(
                f"missing step field {field}: plan steps must include "
                "WHERE / WHAT / WHY / VERIFY for each step"
            )

    # --- Old /rev-style markers ---
    if _REV_VERDICT_RE.search(text):
        errors.append(
            "contains line-leading REV_VERDICT: — old /rev template style; "
            "update to GD_STANDARD-based plan"
        )
    if _BARE_VERDICT_RE.search(text):
        errors.append(
            "contains line-leading VERDICT: — this looks like a review output, "
            "not a plan file"
        )
    if _REVIEW_STANDARD_RE.search(text):
        errors.append(
            "contains line-leading REVIEW_STANDARD: — old /rev template style; "
            "replace with GD_STANDARD:"
        )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Field-based plan preflight for /review2 plan_review."
    )
    parser.add_argument("--target", required=True, help="Path to the plan file.")
    args = parser.parse_args()

    errors = _validate(args.target)

    if not errors:
        print("PLAN_TEMPLATE_STATUS: pass")
        print("BRIDGE_INVOCATION_STATUS: allowed")
        sys.exit(0)
    else:
        print("PLAN_TEMPLATE_STATUS: fail")
        for e in errors:
            print(f"PLAN_ERROR: {e}")
        print("BRIDGE_INVOCATION_STATUS: not_started")
        sys.exit(1)


if __name__ == "__main__":
    main()
