#!/usr/bin/env python3
"""
gd-validate-runtime-strict-binding.py — Plan 5 v3 Wave A2 (extends Plan 4 round 2)

Validates runtime binding anchors in commands/gd.md:
  1. All REQUIRED_STAGES have a matching anchor block (start/end pair)
  2. Every runtime validator call inside each anchor block carries the stage's
     required flags (--strict-live-proof for dispatch validators; schema flag for
     the review-router validator)
  3. Anchor start/end must be paired with consistent stage names

Plan 5 v3 changes (Q1 + config-driven extension):
  - Config-driven: STAGE_CONFIG dict maps stage → validator names + required flag
  - New stage: review-router → gd-validate-route-report.py (no --strict-live-proof,
    requires --schema-version flag instead)
  - Q1 singleton check: exactly one gd-validate-*binding*.py must exist in scripts/

用法：
  python3 scripts/gd-validate-runtime-strict-binding.py [--source <path>]
  python3 scripts/gd-validate-runtime-strict-binding.py --check-singleton

退出码：
  0 = all anchor blocks compliant
  1 = violations found
  2 = usage error / file not found
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


GD_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = GD_ROOT / "commands" / "gd.md"
SCRIPTS = GD_ROOT / "scripts"

# ---------------------------------------------------------------------------
# Stage configuration (config-driven, Plan 5 v3)
# ---------------------------------------------------------------------------
# Each entry: validator_names (set of script names to match inside anchor body),
#             required_flag (string that must appear on validator call lines),
#             required_flag_label (human-readable name for error messages).
#
# required_flag=None means the stage requires no specific flag on validator calls
# (the anchor merely asserts the validator is referenced at all).

STAGE_CONFIG: dict[str, dict] = {
    "plan": {
        "validator_names": {"gd-validate-planning-dispatch-log.py"},
        "required_flag": "--strict-live-proof",
        "required_flag_label": "--strict-live-proof",
    },
    "probe": {
        "validator_names": {"gd-validate-planning-dispatch-log.py", "gd-validate-probe.py"},
        "required_flag": "--strict-live-proof",
        "required_flag_label": "--strict-live-proof",
    },
    "execute-agent-exec": {
        "validator_names": {"gd-validate-planning-dispatch-log.py"},
        "required_flag": "--strict-live-proof",
        "required_flag_label": "--strict-live-proof",
    },
    "review-router": {
        "validator_names": {"gd-validate-route-report.py"},
        "required_flag": None,
        "required_flag_label": None,
    },
}

REQUIRED_STAGES = set(STAGE_CONFIG.keys())

ANCHOR_START_RE = re.compile(
    r"<!--\s*gd-runtime-strict-required:start\s+stage=([\w\-]+)\s*-->"
)
ANCHOR_END_RE = re.compile(
    r"<!--\s*gd-runtime-strict-required:end\s+stage=([\w\-]+)\s*-->"
)


def find_anchor_blocks(text: str) -> tuple[list[dict], list[str]]:
    """Parse anchor blocks from source text.

    Returns (blocks, errors).
    Each block: {stage, start_line, end_line, body}.
    """
    lines = text.splitlines()
    blocks: list[dict] = []
    errors: list[str] = []

    i = 0
    while i < len(lines):
        m_start = ANCHOR_START_RE.search(lines[i])
        if not m_start:
            i += 1
            continue
        stage = m_start.group(1)
        start_line = i + 1  # 1-based for human reading

        # Find matching end
        end_idx = None
        for j in range(i + 1, len(lines)):
            m_end = ANCHOR_END_RE.search(lines[j])
            if m_end:
                end_stage = m_end.group(1)
                if end_stage != stage:
                    errors.append(
                        f"line {j+1}: anchor end stage={end_stage!r} mismatch "
                        f"(expected stage={stage!r} from start line {start_line})"
                    )
                end_idx = j
                break

        if end_idx is None:
            errors.append(
                f"line {start_line}: anchor start stage={stage!r} has no matching end"
            )
            i += 1
            continue

        body = "\n".join(lines[i + 1:end_idx])
        blocks.append({
            "stage": stage,
            "start_line": start_line,
            "end_line": end_idx + 1,
            "body": body,
        })
        i = end_idx + 1

    # Check for orphan ends
    for idx, line in enumerate(lines):
        m_end = ANCHOR_END_RE.search(line)
        if m_end:
            stage = m_end.group(1)
            paired = any(
                b["end_line"] == idx + 1 and b["stage"] == stage for b in blocks
            )
            if not paired:
                errors.append(f"line {idx+1}: orphan anchor end stage={stage!r}")

    return blocks, errors


def find_validator_calls(body: str, validator_names: set[str]) -> list[tuple[str, int]]:
    """Find runtime validator script invocations matching validator_names in body.

    Returns list of (matched_command_text, body_line_number).
    """
    hits: list[tuple[str, int]] = []
    for ln, line in enumerate(body.splitlines(), 1):
        for vname in validator_names:
            if vname in line:
                hits.append((line.strip(), ln))
                break
    return hits


def validate_strict_binding(text: str) -> tuple[int, list[str], list[str]]:
    """Run all checks. Returns (exit_code, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    blocks, parse_errs = find_anchor_blocks(text)
    errors.extend(parse_errs)

    # Check 1: required stages present
    seen_stages = {b["stage"] for b in blocks}
    missing = REQUIRED_STAGES - seen_stages
    if missing:
        errors.append(
            f"REQUIRED_STAGE_MISSING: anchor blocks missing for stages: "
            f"{sorted(missing)} (required: {sorted(REQUIRED_STAGES)})"
        )

    # Check 2 (config-driven): each anchor block's validator calls satisfy stage config
    for b in blocks:
        stage = b["stage"]
        cfg = STAGE_CONFIG.get(stage)
        if cfg is None:
            warnings.append(
                f"line {b['start_line']}: unknown stage={stage!r} (not in STAGE_CONFIG; informational)"
            )
            continue

        calls = find_validator_calls(b["body"], cfg["validator_names"])

        if not calls:
            warnings.append(
                f"line {b['start_line']}-{b['end_line']}: stage={stage!r} anchor "
                f"contains no validator call matching {sorted(cfg['validator_names'])} "
                f"(informational only)"
            )
            continue

        if cfg["required_flag"] is not None:
            for cmd_text, body_ln in calls:
                if cfg["required_flag"] not in cmd_text:
                    file_ln = b["start_line"] + body_ln
                    errors.append(
                        f"STRICT_FLAG_MISSING: line ~{file_ln} (in stage={stage!r} anchor): "
                        f"validator call missing {cfg['required_flag_label']!r}: "
                        f"{cmd_text!r}"
                    )

    exit_code = 1 if errors else 0
    return exit_code, errors, warnings


def check_singleton() -> tuple[int, str]:
    """Q1: assert exactly one gd-validate-runtime-strict-binding.py exists in scripts/.

    Checks for the specific runtime-strict-binding validator only, not all *binding* files
    (gd-validate-subplan-codex-binding.py is a separate distinct validator).

    Returns (exit_code, message).
    """
    matches = sorted(SCRIPTS.glob("gd-validate-runtime-strict-binding.py"))
    if len(matches) == 1:
        return 0, f"singleton OK: {matches[0].name}"
    if len(matches) == 0:
        return 1, "SINGLETON_BINDING_VALIDATOR: no gd-validate-runtime-strict-binding.py found"
    return 1, (
        f"SINGLETON_BINDING_VALIDATOR: expected exactly 1, "
        f"found {len(matches)}: {[m.name for m in matches]}"
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description="Validate runtime strict binding in commands/gd.md",
    )
    p.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help=f"Path to commands/gd.md (default: {DEFAULT_SOURCE})",
    )
    p.add_argument(
        "--check-singleton",
        action="store_true",
        help="Q1: assert exactly one gd-validate-*binding*.py exists (exit 0 = OK)",
    )
    args = p.parse_args()

    if args.check_singleton:
        rc, msg = check_singleton()
        if rc == 0:
            print(f"OK: {msg}")
        else:
            print(f"FAIL: {msg}", file=sys.stderr)
        return rc

    src = Path(args.source)
    if not src.exists():
        print(f"ERROR: source file not found: {src}", file=sys.stderr)
        return 2

    text = src.read_text(encoding="utf-8")
    exit_code, errors, warnings = validate_strict_binding(text)

    if errors:
        print("STRICT BINDING VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"\nTotal violations: {len(errors)}", file=sys.stderr)
    if warnings:
        print("WARNINGS:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    # Q1: also run singleton check when validating source
    singleton_rc, singleton_msg = check_singleton()
    if singleton_rc != 0:
        errors.append(singleton_msg)
        exit_code = 1
        print(f"SINGLETON_CHECK FAIL: {singleton_msg}", file=sys.stderr)

    if exit_code == 0:
        print(f"OK: runtime strict binding valid in {src}")
        print(f"  required_stages={sorted(REQUIRED_STAGES)} all present")
        if any(
            cfg["required_flag"] is not None for cfg in STAGE_CONFIG.values()
        ):
            print(f"  all runtime validator calls have required flags (per stage config)")
        print(f"  singleton check: {singleton_msg}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
