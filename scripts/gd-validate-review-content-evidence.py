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
from lib.sc_extraction import extract_reviewable_ids as _extract_target_ids  # noqa: E402  — structured (T-头+checklist)
from lib.sc_extraction import extract_referenced_ids as _extract_review_ids  # noqa: E402  — broad (全文 SC+T-N)

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
    """Review-side referenced IDs（宽：全文 SC + T-N，placeholder 过滤）。

    Issue3: codex 在 `| T0 |` / `SC: T0` 引用 ID，需宽口径。target_sc_ids 用
    ``_extract_target_ids``（结构化）—— 见下方 main 调用点，两者分工。
    """
    return _extract_review_ids(text)


# Lenient SC-ID variants accepted ONLY inside the Scope Checked section, to
# tolerate reviewer formatting drift like "SC1" (missing dash), "sc-1" (lower
# case) or "SC 1" (space) that the canonical SC_ID_RE rejects. Kept local to
# scope-coverage so the shared SC_ID_RE stays strict everywhere else (finding /
# line-ref / bogus checks), avoiding false positives outside this small section.
_SC_ID_LENIENT_RE = re.compile(r"\bSC[\s\-]?0*(\d+)\b", re.IGNORECASE)


def _extract_sc_ids_lenient(text: str) -> set[str]:
    """Canonical+T-N reviewable IDs plus normalized SC variants (SC1 / sc-1 / SC 1 → SC-N).

    Issue3: Scope Checked 的 `| T0 |` 行 + SC1/sc-1 变体都接受，让 T 系计划 APPROVED
    覆盖 T0-T7 不再被判 missing scope。
    """
    ids = _extract_review_ids(text)  # 宽：全文 SC(placeholder-filtered) + T-N
    for num in _SC_ID_LENIENT_RE.findall(text):
        ids.add(f"SC-{int(num)}")
    return ids


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
    degraded_findings: "Optional[list[str]]" = None,
) -> None:
    """Every ### Finding block must contain at least one path:line ref that resolves
    to the target file (matched by name or path suffix). Refs to unrelated files
    do not satisfy the evidence requirement.

    SC-12 (误拒收口): when ``degraded_findings`` is provided AND the overall review
    is structurally valid (legit verdict + substantive findings), an individual
    finding that merely lacks a target-pointing line ref is recorded as a degraded
    finding (a per-finding reference-quality warning) instead of collapsing the
    whole review into FAKE_EVIDENCE_DETECTED. With ``degraded_findings`` None the
    legacy hard-fail behaviour is preserved.
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
            msg = (
                f"Finding #{i} has no path:line evidence "
                f"pointing to target '{target_name}' "
                f"(found {len(refs)} ref(s) to other files — "
                f"reviewer must cite '{target_name}:<line>')"
            )
            if degraded_findings is not None:
                degraded_findings.append(f"DEGRADED_FINDING: {msg}")
            else:
                errors.append(f"FAKE_EVIDENCE_DETECTED: {msg}")


def _check_scope_coverage(
    review_text: str,
    target_sc_ids: set[str],
    verdict: str,
    errors: list[str],
) -> set[str]:
    """If verdict is APPROVED AND target has SC-IDs, reviewer must declare scope_checked.

    Returns the set of target SC-IDs that are missing from the Scope Checked section.
    Returns an empty set when the check is skipped or all SC-IDs are covered.
    """
    if verdict != "APPROVED":
        return set()  # REQUIRES_CHANGES / FAILED: findings carry the SC refs
    if not target_sc_ids:
        return set()  # target has no SC-IDs to verify; skip scope coverage check
    scope_match = _SCOPE_CHECKED_RE.search(review_text)
    if not scope_match:
        errors.append(
            "FAKE_EVIDENCE_DETECTED: APPROVED verdict with no SCOPE_CHECKED section "
            "(reviewer must list which SC-IDs were verified)"
        )
        # All target SC-IDs are missing because the section doesn't exist
        return set(target_sc_ids)
    scope_text = scope_match.group(0)
    scope_sc_ids = _extract_sc_ids_lenient(scope_text)
    if not scope_sc_ids:
        errors.append(
            "FAKE_EVIDENCE_DETECTED: APPROVED verdict — SCOPE_CHECKED section has no SC-IDs"
        )
        # All target SC-IDs are missing because the section has no SC-IDs
        return set(target_sc_ids)
    bogus = scope_sc_ids - target_sc_ids
    if bogus:
        errors.append(
            f"FAKE_EVIDENCE_DETECTED: APPROVED scope_checked lists SC-IDs not in target: "
            f"{sorted(bogus)}"
        )
    # Return target SC-IDs that do not appear in the Scope Checked section
    return target_sc_ids - scope_sc_ids


def _check_requires_changes_has_findings(
    review_text: str,
    verdict: str,
    errors: list[str],
    degraded_findings: "Optional[list[str]]" = None,
) -> None:
    """REQUIRES_CHANGES must have ≥1 finding with sc_refs.

    SC-3 (V16): REQUIRES_CHANGES with zero ### Finding blocks is a hard fail — the
    no-findings case is a genuine fake-review signal and is never softened.

    SC-12 (误拒收口): an individual finding that merely lacks an SC-ID reference is
    a per-finding citation-style defect; when ``degraded_findings`` is provided
    (review is structurally valid) it is recorded as a degraded finding rather than
    collapsing the otherwise-valid REQUIRES_CHANGES review. With ``degraded_findings``
    None the legacy hard-fail behaviour is preserved.
    """
    if verdict != "REQUIRES_CHANGES":
        return
    findings = _FINDING_BLOCK_RE.findall(review_text)
    if not findings:
        # SC-3: hard fail — never softened. No findings ⇒ no verifiable substance.
        errors.append(
            "FAKE_EVIDENCE_DETECTED: REQUIRES_CHANGES verdict with no ### Finding sections"
        )
        return
    for i, block in enumerate(findings, 1):
        if not _extract_sc_ids(block):
            msg = f"Finding #{i} has no SC-ID reference"
            if degraded_findings is not None:
                degraded_findings.append(f"DEGRADED_FINDING: {msg}")
            else:
                errors.append(f"FAKE_EVIDENCE_DETECTED: {msg}")


# 5 mandatory Chinese finding fields (mirrors gd-codex-bridge-review.py
# REQUIRED_FINDING_FIELDS_CN). A finding that carries these substance fields is a
# concrete conclusion, not a hollow placeholder — used by SC-12 to decide whether
# a review is "structurally valid" enough to only degrade (not collapse) on minor
# citation-style defects.
_FINDING_SUBSTANCE_FIELDS_CN = ("问题", "证据", "影响", "最小修复", "验收")


def _finding_is_substantive(block: str) -> bool:
    """A finding block is substantive if it carries at least one filled-in
    mandatory substance field (问题/证据/影响/最小修复/验收) with non-empty content.
    """
    for cn in _FINDING_SUBSTANCE_FIELDS_CN:
        m = re.search(rf"^\s*{cn}\s*[:：]\s*(\S.*)$", block, re.MULTILINE)
        if m and m.group(1).strip():
            return True
    return False


def _review_is_structurally_valid(
    review_text: str,
    verdict: str,
    target_path: Path,
    target_sc_ids: set[str],
) -> bool:
    """SC-12 gate: a review is eligible for per-finding *degradation* (instead of
    whole-review *collapse*) only when it has already demonstrated citation
    competence. It is structurally valid when ALL of:

      * verdict is a legit canonical value (NOT UNKNOWN), and
      * it has at least one ### Finding block, and
      * at least one finding is substantive (carries a filled-in 中文 field), and
      * citation competence is demonstrated: at least one finding carries a valid
        target-pointing ``target:NN`` line ref AND (when the target has SC-IDs) at
        least one finding cites a real target SC-ID.

    This is the explicit boundary between SC-2/SC-3 (reject genuine fakery: UNKNOWN
    verdict, zero findings, or a review that NEVER cites the target correctly) and
    SC-12 (don't misfire on a single citation-style nitpick inside an otherwise
    well-cited, valid review). A review that cannot cite the target at all in ANY
    finding has NOT proven competence → strict fail-closed, so legacy stub fixtures
    whose findings carry no machine-checkable ``target:NN`` ref stay rejected.
    """
    if verdict not in {"APPROVED", "REQUIRES_CHANGES", "FAILED"}:
        return False
    findings = _FINDING_BLOCK_RE.findall(review_text)
    if not findings:
        return False
    target_name = target_path.name
    target_str = str(target_path)
    has_substantive = False
    has_valid_line_ref = False
    has_valid_sc_id = False
    for block in findings:
        has_substantive = has_substantive or _finding_is_substantive(block)
        for ref in _LINE_REF_RE.findall(block):
            if ref[0] == target_name or target_str.endswith(ref[0]):
                has_valid_line_ref = True
                break
        if _extract_sc_ids(block) & target_sc_ids:
            has_valid_sc_id = True
    if not has_substantive:
        return False
    if not has_valid_line_ref:
        return False
    # When the target declares SC-IDs, at least one finding must cite a real one.
    if target_sc_ids and not has_valid_sc_id:
        return False
    return True


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
    # Issue1: target_sc_ids 用结构化提取（checklist SC + T-头），不含正文散提（如
    # REVIEW_FOCUS 的 SC-conformance）。review 侧（findings/scope）用宽 _extract_sc_ids。
    target_sc_ids = _extract_target_ids(target_text)
    target_line_count = _extract_line_count(target_text)
    verdict = _extract_verdict(review_text) or "UNKNOWN"

    errors: list[str] = []
    error_codes: list[str] = []
    degraded_findings: list[str] = []
    skip_line_ref = getattr(args_ns, "skip_line_ref_check", False) if args_ns else False

    # SC-2 (V1): an unrecognizable / missing verdict is NOT a free pass. Previously
    # an UNKNOWN verdict early-exited every verdict-gated anti-fake check, so a
    # review with no parseable verdict sailed through as EVIDENCE_VALID. Treat it as
    # a fake-review signal: the reviewer must emit a single canonical
    # GD_REVIEW_DECISION (APPROVED|REQUIRES_CHANGES|FAILED).
    if verdict not in {"APPROVED", "REQUIRES_CHANGES", "FAILED"}:
        errors.append(
            "FAKE_EVIDENCE_DETECTED: no recognizable GD_REVIEW_DECISION verdict "
            "(APPROVED|REQUIRES_CHANGES|FAILED) — anti-fake checks cannot be "
            "skipped on an unverifiable verdict"
        )
        error_codes.append("unknown_verdict")

    # SC-12 (误拒收口): only when the review is structurally valid (legit verdict,
    # ≥1 substantive finding) do we soften per-finding citation defects into degraded
    # findings instead of collapsing the whole review. UNKNOWN verdict or zero
    # findings keep the strict fail-closed path (SC-2 / SC-3).
    structurally_valid = _review_is_structurally_valid(
        review_text, verdict, target_path, target_sc_ids
    )
    _df_sink = degraded_findings if structurally_valid else None

    _check_sc_refs(review_text, target_sc_ids, errors, reference_sc_ids=reference_sc_ids)
    _check_line_refs(review_text, target_path, target_line_count, errors)
    missing_scope_sc_ids = _check_scope_coverage(review_text, target_sc_ids, verdict, errors)
    if missing_scope_sc_ids:
        error_codes.append("missing_scope_sc_ids")
    _check_requires_changes_has_findings(review_text, verdict, errors, degraded_findings=_df_sink)
    if not skip_line_ref:
        _check_finding_has_line_evidence(
            review_text, target_path, errors, degraded_findings=_df_sink
        )
    # F3: execution JSON targets require verify rerun evidence.
    if target_path.suffix.lower() == ".json":
        _check_execution_verify_evidence(target_text, review_text, errors)

    report = {
        "status": "EVIDENCE_VALID" if not errors else "FAKE_EVIDENCE_DETECTED",
        "target_path": str(target_path),
        "target_sc_id_count": len(target_sc_ids),
        "target_line_count": target_line_count,
        "verdict": verdict,
        "verdict_preserved": verdict if not errors else None,
        "structurally_valid": structurally_valid,
        "errors": errors,
        "error_codes": error_codes,
        "degraded_findings": degraded_findings,
        "missing_scope_sc_ids": sorted(missing_scope_sc_ids),
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

    # SC-3 / F5 fix (V16): --skip-line-ref-check is a legacy compatibility flag
    # for parser-stub fixtures. It must NOT be usable to bypass line-evidence
    # checks for any review that carries a REQUIRES_CHANGES verdict — regardless
    # of target file type. The original guard covered only .json targets; this
    # extends it to all REQUIRES_CHANGES reviews (Markdown or JSON) because
    # skipping line-ref on an RC review re-opens the exact fail-open hole SC-3
    # was designed to close.
    #
    # Legacy fixture exemption: the 4 legacy .md RC fixtures in
    # tests/gd-l3-regression-v1-fixtures.sh that rely on --skip-line-ref-check
    # must be updated to remove the flag (or use APPROVED verdicts) — they
    # should not have been testing skip+RC as a passing case.
    if args.review == "-":
        review_text = sys.stdin.read()
    else:
        review_path = Path(args.review)
        if not review_path.is_file():
            print(f"ERROR: review file not found: {review_path}", file=sys.stderr)
            return 2
        review_text = review_path.read_text(encoding="utf-8")

    # F5 fix: reject --skip-line-ref-check for .json targets or any RC review.
    # Moved after review_text load to reuse the already-read text (no early double-read).
    if getattr(args, "skip_line_ref_check", False):
        _is_rc = "REQUIRES_CHANGES" in review_text
        if target.suffix.lower() == ".json" or _is_rc:
            _reason = (
                "execution-outcome JSON target" if target.suffix.lower() == ".json"
                else "REQUIRES_CHANGES verdict (line evidence cannot be skipped for RC reviews)"
            )
            print(
                f"ERROR: --skip-line-ref-check is rejected for {_reason}",
                file=sys.stderr,
            )
            print("L3_RESULT: FAKE_EVIDENCE_DETECTED (skip flag rejected)")
            return 1

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

    # SC-12: surface per-finding citation defects without collapsing the verdict.
    # Written to stderr so the snapshotted stdout (L3_RESULT line) stays
    # byte-identical for callers/tests that freeze the validator's stdout.
    for d in report.get("degraded_findings", []):
        print(f"WARN: {d}", file=sys.stderr)

    print(
        f"L3_RESULT: EVIDENCE_VALID "
        f"(verdict={report['verdict']}, "
        f"target_sc_ids={report['target_sc_id_count']}, "
        f"review_sc_ids={report['review_sc_id_count']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
