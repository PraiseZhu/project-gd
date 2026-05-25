#!/usr/bin/env python3
"""gd-validate-review-content-evidence.py — L3 enforcement.

Verifies that a reviewer's raw output references SC-IDs and line ranges that
actually exist in the target file. This catches the failure mode where Codex
(or any reviewer) skips the externalized Target's Read step and fabricates
findings or scope claims.

Exit codes
  0  — EVIDENCE_VALID (all SC-IDs and line refs resolve to target content)
  1  — FAKE_EVIDENCE_DETECTED (one or more refs don't resolve)
  2  — usage / parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional  # noqa: F401 — used in string annotations

sys.path.insert(0, str(Path(__file__).parent))
from lib.sc_extraction import SC_ID_RE as _SC_ID_RE  # noqa: E402

# Evidence line ref: matches "path:NN" or "path:NN-MM". The path part is a
# best-effort match (ends at the colon-digit boundary).
_LINE_REF_RE = re.compile(
    r"([A-Za-z0-9_./\-]+\.(?:md|py|sh|json|yaml|yml|toml|ts|tsx|js|patch|diff)):(\d+)(?:-(\d+))?"
)

# Section markers in standard review template
_FINDING_BLOCK_RE = re.compile(
    r"###\s+Finding\s+\d+.*?(?=###\s+Finding\s+\d+|\Z)",
    re.DOTALL,
)
_SCOPE_CHECKED_RE = re.compile(
    r"##\s+(?:Scope Checked|SCOPE_CHECKED|2\.\s+Scope Checked).*?(?=##\s+\d?\.?\s*\w|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def _extract_sc_ids(text: str) -> set[str]:
    """Return all SC-IDs that appear in `text`."""
    return set(_SC_ID_RE.findall(text))


def _extract_line_count(target_text: str) -> int:
    return len(target_text.splitlines())


def _check_sc_refs(
    review_text: str,
    target_sc_ids: set[str],
    errors: list[str],
    reference_sc_ids: "Optional[set[str]]" = None,
) -> None:
    """Every SC-ID claimed in review findings/scope must exist in target or reference_target."""
    review_sc_ids = _extract_sc_ids(review_text)
    if not review_sc_ids:
        # No SC refs in review — separately handled by _check_scope_coverage
        return
    valid_ids = target_sc_ids | (reference_sc_ids or set())
    bogus = review_sc_ids - valid_ids
    if bogus:
        errors.append(
            f"FAKE_EVIDENCE_DETECTED: SC-ID refs not in target: {sorted(bogus)} "
            f"(target has {sorted(target_sc_ids)})"
        )


def _check_line_refs(
    review_text: str,
    target_path: Path,
    target_line_count: int,
    errors: list[str],
) -> None:
    """Every `file:line` ref pointing to the target file must resolve to a real line."""
    target_name = target_path.name
    target_str = str(target_path)
    refs = _LINE_REF_RE.findall(review_text)
    for path_ref, start_str, end_str in refs:
        # Only check refs that point at the target file (path may be relative or basename)
        if path_ref != target_name and not target_str.endswith(path_ref):
            continue
        start = int(start_str)
        end = int(end_str) if end_str else start
        if start < 1 or end > target_line_count or start > end:
            errors.append(
                f"FAKE_EVIDENCE_DETECTED: line ref {path_ref}:{start_str}"
                f"{'-' + end_str if end_str else ''} out of range "
                f"(target has {target_line_count} lines)"
            )


def _check_finding_has_line_evidence(
    review_text: str,
    target_path: Path,
    errors: list[str],
) -> None:
    """Every ### Finding block must contain at least one path:line ref that resolves
    to the target file (matched by name or path suffix). Refs to unrelated files
    do not satisfy the evidence requirement.
    """
    findings = _FINDING_BLOCK_RE.findall(review_text)
    if not findings:
        return  # _check_requires_changes_has_findings handles the no-findings case
    target_name = target_path.name
    target_str = str(target_path)
    for i, block in enumerate(findings, 1):
        refs = _LINE_REF_RE.findall(block)
        # At least one ref must match the target file
        target_refs = [
            r for r in refs
            if r[0] == target_name or target_str.endswith(r[0])
        ]
        if not target_refs:
            errors.append(
                f"FAKE_EVIDENCE_DETECTED: Finding #{i} has no path:line evidence "
                f"pointing to target '{target_name}' "
                f"(found {len(refs)} ref(s) to other files — "
                f"reviewer must cite '{target_name}:<line>')"
            )


def _check_scope_coverage(
    review_text: str,
    target_sc_ids: set[str],
    verdict: str,
    errors: list[str],
) -> None:
    """If verdict is APPROVED AND target has SC-IDs, reviewer must declare scope_checked."""
    if verdict != "APPROVED":
        return  # REQUIRES_CHANGES / FAILED: findings carry the SC refs
    if not target_sc_ids:
        return  # target has no SC-IDs to verify; skip scope coverage check
    scope_match = _SCOPE_CHECKED_RE.search(review_text)
    if not scope_match:
        errors.append(
            "FAKE_EVIDENCE_DETECTED: APPROVED verdict with no SCOPE_CHECKED section "
            "(reviewer must list which SC-IDs were verified)"
        )
        return
    scope_text = scope_match.group(0)
    scope_sc_ids = _extract_sc_ids(scope_text)
    if not scope_sc_ids:
        errors.append(
            "FAKE_EVIDENCE_DETECTED: APPROVED verdict — SCOPE_CHECKED section has no SC-IDs"
        )
        return
    bogus = scope_sc_ids - target_sc_ids
    if bogus:
        errors.append(
            f"FAKE_EVIDENCE_DETECTED: APPROVED scope_checked lists SC-IDs not in target: "
            f"{sorted(bogus)}"
        )


def _check_requires_changes_has_findings(
    review_text: str,
    verdict: str,
    errors: list[str],
) -> None:
    """REQUIRES_CHANGES must have ≥1 finding with sc_refs."""
    if verdict != "REQUIRES_CHANGES":
        return
    findings = _FINDING_BLOCK_RE.findall(review_text)
    if not findings:
        errors.append(
            "FAKE_EVIDENCE_DETECTED: REQUIRES_CHANGES verdict with no ### Finding sections"
        )
        return
    for i, block in enumerate(findings, 1):
        if not _extract_sc_ids(block):
            errors.append(
                f"FAKE_EVIDENCE_DETECTED: Finding #{i} has no SC-ID reference"
            )


def _extract_verdict(review_text: str) -> Optional[str]:
    """Find GD_REVIEW_DECISION or VERDICT line.

    Skip schema-example lines like 'GD_REVIEW_DECISION: APPROVED | REQUIRES_CHANGES | FAILED'
    (lines containing '|' are echoed contract definitions, not actual verdicts).
    Take the LAST occurrence (final verdict overrides earlier mentions).
    """
    last_verdict: Optional[str] = None
    for line in review_text.splitlines():
        m = re.match(r"^\s*(?:GD_REVIEW_DECISION|VERDICT)\s*:\s*(\w+)", line)
        if not m:
            continue
        # Skip schema-example lines that enumerate all possible values
        if "|" in line:
            continue
        verdict = m.group(1).upper()
        # Only accept canonical verdicts
        if verdict in {"APPROVED", "REQUIRES_CHANGES", "FAILED"}:
            last_verdict = verdict
    return last_verdict


def _extract_execution_fields(target_text: str) -> tuple[list[str], list[str]]:
    """Parse execution JSON target; return (deliverable_paths, verify_cmds).
    Returns ([], []) if target is not a valid execution JSON or fields missing.
    """
    try:
        d = json.loads(target_text)
    except (json.JSONDecodeError, ValueError):
        return [], []
    deliverables: list[str] = []
    verify_cmds: list[str] = []
    for task in d.get("task_results", []):
        for deliv in task.get("deliverables_produced", []):
            p = deliv.get("path", "")
            if p:
                deliverables.append(p)
        for vr in task.get("verify_results", []):
            cmd = vr.get("cmd", "")
            if cmd:
                verify_cmds.append(cmd)
    return deliverables, verify_cmds


# Patterns that indicate real verify output in review text.
_VERIFY_OUTPUT_RE = re.compile(
    r"\b(?:PASS|FAIL|exit\s*(?:code\s*[:\s])?\d|stdout|stderr|returncode)\b",
    re.IGNORECASE,
)


def _check_execution_verify_evidence(
    target_text: str,
    review_text: str,
    errors: list[str],
) -> None:
    """F3: For execution JSON targets, review must contain MANDATORY VERIFY STEP output.

    Checks that reviewer actually executed/quoted verify commands and deliverable
    checks, not just echoed the stored 'result' field. At minimum requires ≥1
    PASS/FAIL/exit-code assertion to appear in the review.
    """
    deliverables, verify_cmds = _extract_execution_fields(target_text)
    if not deliverables and not verify_cmds:
        return  # not an execution target — skip

    # Review must contain at least one verify output signal.
    if not _VERIFY_OUTPUT_RE.search(review_text):
        errors.append(
            "FAKE_EVIDENCE_DETECTED: execution target review has no verify output evidence "
            "(expected PASS/FAIL/exit code assertions from MANDATORY VERIFY STEP; "
            "reviewer may have skipped actual command rerun)"
        )
        return

    # At least one deliverable or verify cmd must be mentioned in the review.
    all_refs = deliverables + verify_cmds
    if all_refs and not any(ref in review_text for ref in all_refs):
        errors.append(
            "FAKE_EVIDENCE_DETECTED: execution target review does not reference any "
            f"deliverable or verify command from target "
            f"(checked {len(all_refs)} items)"
        )


def validate(
    target_path: Path,
    review_text: str,
    reference_sc_ids: "Optional[set[str]]" = None,
    args_ns: "Optional[object]" = None,
) -> tuple[list[str], dict]:
    """Returns (errors, report_dict)."""
    target_text = target_path.read_text(encoding="utf-8")
    target_sc_ids = _extract_sc_ids(target_text)
    target_line_count = _extract_line_count(target_text)
    verdict = _extract_verdict(review_text) or "UNKNOWN"

    errors: list[str] = []
    skip_line_ref = getattr(args_ns, "skip_line_ref_check", False) if args_ns else False
    _check_sc_refs(review_text, target_sc_ids, errors, reference_sc_ids=reference_sc_ids)
    _check_line_refs(review_text, target_path, target_line_count, errors)
    _check_scope_coverage(review_text, target_sc_ids, verdict, errors)
    _check_requires_changes_has_findings(review_text, verdict, errors)
    if not skip_line_ref:
        _check_finding_has_line_evidence(review_text, target_path, errors)
    # F3: execution JSON targets require verify rerun evidence.
    if target_path.suffix.lower() == ".json":
        _check_execution_verify_evidence(target_text, review_text, errors)

    report = {
        "status": "EVIDENCE_VALID" if not errors else "FAKE_EVIDENCE_DETECTED",
        "target_path": str(target_path),
        "target_sc_id_count": len(target_sc_ids),
        "target_line_count": target_line_count,
        "verdict": verdict,
        "errors": errors,
        "review_sc_id_count": len(_extract_sc_ids(review_text)),
    }
    return errors, report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="L3 content-evidence validator for codex review raw output."
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Absolute path to the primary review target (master-plan.md etc.)",
    )
    parser.add_argument(
        "--review",
        required=True,
        help="Path to reviewer raw output (markdown). Use '-' to read stdin.",
    )
    parser.add_argument(
        "--json-report",
        help="Write structured report to this path",
    )
    parser.add_argument(
        "--reference-target",
        help="Secondary reference file (e.g. plan) whose SC-IDs are also valid. "
             "SC-IDs in the review must exist in target OR reference-target.",
    )
    parser.add_argument(
        "--target-kind",
        choices=["auto", "markdown", "json"],
        default="auto",
        help="Target file kind. 'json' uses JSONPath-style SC-ID extraction. "
             "Default 'auto' detects by file extension.",
    )
    parser.add_argument(
        "--skip-line-ref-check",
        action="store_true",
        help="Skip the finding path:line evidence requirement. Use for legacy "
             "regression tests on parser stubs that predate the L3 line-ref rule.",
    )
    args = parser.parse_args(argv[1:])

    target = Path(args.target)
    if not target.is_file():
        print(f"ERROR: target not found: {target}", file=sys.stderr)
        return 2

    if args.review == "-":
        review_text = sys.stdin.read()
    else:
        review_path = Path(args.review)
        if not review_path.is_file():
            print(f"ERROR: review file not found: {review_path}", file=sys.stderr)
            return 2
        review_text = review_path.read_text(encoding="utf-8")

    # Resolve target kind: 'json' mode reads target as JSON text for SC-ID extraction.
    target_kind = args.target_kind
    if target_kind == "auto":
        target_kind = "json" if target.suffix.lower() == ".json" else "markdown"

    # Optional reference target provides additional valid SC-IDs (for code_diff reviews
    # where SC-IDs live in the plan, not in the diff itself).
    reference_sc_ids: set[str] = set()
    if args.reference_target:
        ref_path = Path(args.reference_target)
        if ref_path.is_file():
            reference_sc_ids = _extract_sc_ids(ref_path.read_text(encoding="utf-8"))

    # JSON target mode: extract SC-IDs from the serialized JSON string as text.
    # The underlying _extract_sc_ids already works on any string, so no change
    # needed to validate(); target_kind is recorded in the report for audit only.
    errors, report = validate(target, review_text, reference_sc_ids=reference_sc_ids, args_ns=args)
    report["target_kind"] = target_kind

    if args.json_report:
        Path(args.json_report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(
            f"L3_RESULT: FAKE_EVIDENCE_DETECTED "
            f"({len(errors)} error(s), verdict={report['verdict']})"
        )
        return 1

    print(
        f"L3_RESULT: EVIDENCE_VALID "
        f"(verdict={report['verdict']}, "
        f"target_sc_ids={report['target_sc_id_count']}, "
        f"review_sc_ids={report['review_sc_id_count']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
