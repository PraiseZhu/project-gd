#!/usr/bin/env python3
"""
gd-validate-parent-close-gate.py — Plan H parent close gate (PH-SC-5)

Replaces fragile `grep -q "GD_REVIEW_DECISION: APPROVED"` (which silently
matches `APPROVED_PARTIAL`) with a parent-status-aware close gate that takes
the parent close report as input and refuses to close higher than the report
itself declares.

CLI:
  python3 scripts/gd-validate-parent-close-gate.py \
    --plans-dir <dir> --reports-dir <dir> \
    --parent-report <path/to/parent-close-report.md> \
    [--w2-deferred <id>:<reason-substring>] \
    [--allow-constrained-reason <reason-substring>]

Two parent close modes (parsed from the parent report):

  local_only_complete_with_w2_blocked
    - Sub-plans may be APPROVED + completed (strict), OR
    - APPROVED + completed_with_constraint (provided
      merge_notes.degraded_reason contains a substring on
      --allow-constrained-reason allowlist), OR
    - APPROVED_PARTIAL + completed_with_constraint, provided the sub-plan id is
      declared in --w2-deferred AND merge_notes.degraded_reason contains the
      declared deferred-reason substring.

  fully_completed
    - Every sub-plan MUST be exact `GD_REVIEW_DECISION: APPROVED` AND exact
      `REVIEW_RUN_STATUS: completed`.
    - No --w2-deferred entries may be applied (any declared deferred → fail).
    - merge_notes.degraded_reason MUST be empty or absent for every sub-plan
      (a non-empty degraded_reason proves the sub-plan ran under constraint).

Parent status parsing:

  - Strips Markdown bold (`**`), surrounding whitespace, and trailing
    table-cell characters.
  - Collects every `PARENT_CLOSE_STATUS:` line in the report.
  - Zero matches → PARENT_STATUS_MISSING (fail).
  - ≥2 matches → all normalized values must be equal; otherwise
    PARENT_STATUS_INCONSISTENT (fail).

Exit:
  0 = parent close gate satisfied for the declared parent status
  1 = at least one sub-plan or parent declaration fails the gate
  2 = bad input (missing files, unknown parent status, bad CLI flag format)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SUBPLANS = ["h1", "h2a", "h4a", "h3", "h4b", "h2b", "h5"]

# Plan 6: SSOT runtime evidence validator (called via subprocess only).
RUNTIME_EVIDENCE_VALIDATOR = (
    Path(__file__).resolve().parent / "gd-validate-runtime-evidence.py"
)

# Plan 7: SSOT subplan codex binding validator (called via subprocess only).
SUBPLAN_BINDING_VALIDATOR = (
    Path(__file__).resolve().parent / "gd-validate-subplan-codex-binding.py"
)

VALID_PARENT_STATUSES = {
    "requires_changes",
    "local_only_complete_with_w2_blocked",
    "local_only_complete_with_codex_signoff",
    "fully_completed",
}

# Plan I §7 + 补 B: parent_status → strict-mode contract
#   requires_changes:                       parent has acknowledged unfixed Codex findings
#   local_only_complete_with_w2_blocked:    bridge 0%-tested at parent build time (deprecated post-Plan-I-batch-1)
#   local_only_complete_with_codex_signoff: bridge OK + 7 sub-plan Codex APPROVED (no unfixed findings)
#   fully_completed:                        + Desktop 6/6 + live child dispatch validated

PARENT_STATUS_TOKEN_RE = re.compile(r"PARENT_CLOSE_STATUS:\s*([^\n|]+?)\s*(?:\||$)")
TRAILING_PUNCT = ".,;:。，；：、"

MANUAL_EVIDENCE_KIND_ENUM = {
    "partial_manual_evidence",
    "manual_evidence_complete",
    "manual_external_codex_review",
}
MANUAL_EVIDENCE_ENTRY_RE = re.compile(
    r"MANUAL_EVIDENCE_ENTRY:\s*\n\s*kind:\s*([^\n]+)\n\s*date:\s*([^\n]+)\n\s*scope:\s*([^\n]+)",
    re.MULTILINE,
)
DUAL_RUNTIME_HEADER_RE = re.compile(
    r"^##\s+1\.\s*Dual-runtime smoke coverage matrix", re.MULTILINE
)
SECTION_HEADER_RE = re.compile(r"^##\s+\d+\.\s+", re.MULTILINE)


def err(code: str, msg: str, exit_code: int = 1) -> int:
    print(f"ERROR: {code}: {msg}", file=sys.stderr)
    return exit_code


def normalize_status(raw: str) -> str:
    """Strip markdown bold, backticks, whitespace, trailing ASCII+Chinese punctuation."""
    cleaned = raw.strip()
    cleaned = cleaned.replace("**", "").replace("`", "").strip()
    while cleaned and cleaned[-1] in TRAILING_PUNCT:
        cleaned = cleaned[:-1]
    return cleaned.strip()


def parse_parent_status(parent_path: Path) -> tuple[str | None, list[str]]:
    """Scan the parent report line-by-line for PARENT_CLOSE_STATUS declarations.

    A line counts as a real declaration only if the `PARENT_CLOSE_STATUS:` token
    is NOT wrapped in backticks (`...`), since backtick-wrapped occurrences are
    descriptive prose (e.g. "rewrite §10's `PARENT_CLOSE_STATUS: fully_completed`
    after FW-H5-2 unblocks").
    """
    text = parent_path.read_text(encoding="utf-8")
    declarations: list[str] = []
    for line in text.splitlines():
        if "PARENT_CLOSE_STATUS:" not in line:
            continue
        # Skip prose lines where the token is wrapped in backticks.
        # Detect by removing all backtick spans then re-checking for the token.
        stripped_backticks = re.sub(r"`[^`]*`", "", line)
        if "PARENT_CLOSE_STATUS:" not in stripped_backticks:
            continue
        m = PARENT_STATUS_TOKEN_RE.search(line)
        if m:
            declarations.append(normalize_status(m.group(1)))
    if not declarations:
        return None, []
    return declarations[0], declarations


def extract_section(text: str, header_re: re.Pattern) -> str:
    """Return text of one numbered top-level section (## N. ...) or empty string."""
    m = header_re.search(text)
    if not m:
        return ""
    start = m.start()
    after = SECTION_HEADER_RE.search(text, m.end())
    end = after.start() if after else len(text)
    return text[start:end]


def lint_aggregate_for_signoff(aggregate_path: Path | None, parent_status: str) -> list[str]:
    """Review Trust §Step 5: parent_status `local_only_complete_with_codex_signoff`
    or `fully_completed` requires aggregate v2 input where:
      - every required role has a job
      - every job has transport_status=transport_ok with non-null raw_result_path AND raw_result_hash
      - no job in transport_failed / wrapper_schema_fail / missing_primary_target buckets
      - no job has codex_verdict=REQUIRES_CHANGES (would mean unfixed findings)

    For requires_changes: aggregate is OPTIONAL (parent can self-record findings),
    but if provided, it must show codex_requires_changes is non-empty (no faking).

    For local_only_complete_with_w2_blocked: aggregate is OPTIONAL (legacy mode);
    pass-through.
    """
    failures: list[str] = []
    if parent_status not in {
        "local_only_complete_with_codex_signoff",
        "fully_completed",
        "requires_changes",
    }:
        return failures

    if aggregate_path is None:
        if parent_status in {"local_only_complete_with_codex_signoff", "fully_completed"}:
            failures.append(
                f"AGGREGATE_REQUIRED_FOR_SIGNOFF: parent_status={parent_status} requires "
                f"--aggregate-json pointing to a v2 aggregate JSON; no aggregate provided"
            )
        return failures

    if not aggregate_path.is_file():
        failures.append(f"AGGREGATE_FILE_MISSING: --aggregate-json {aggregate_path} not found")
        return failures

    try:
        agg = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        failures.append(f"AGGREGATE_INVALID_JSON: {e}")
        return failures

    if agg.get("schema_version") != "2.0":
        failures.append(
            f"AGGREGATE_SCHEMA_VERSION_MISMATCH: expected '2.0' got {agg.get('schema_version')!r}"
        )
        return failures

    coverage = agg.get("coverage") or {}
    summary = agg.get("summary") or {}
    jobs = agg.get("jobs") or []

    if parent_status == "requires_changes":
        # Honest mode: aggregate must record at least one REQUIRES_CHANGES job
        # (otherwise the parent's claim is unfounded).
        if not summary.get("codex_requires_changes"):
            failures.append(
                "AGGREGATE_NO_REQUIRES_CHANGES: parent_status=requires_changes but "
                "aggregate.summary.codex_requires_changes is empty — fix parent or re-run aggregate"
            )
        return failures

    # Strict modes: codex_signoff / fully_completed
    missing_roles = coverage.get("missing_roles") or []
    if missing_roles:
        failures.append(
            f"AGGREGATE_COVERAGE_INCOMPLETE: parent_status={parent_status} but "
            f"missing_roles={missing_roles}"
        )

    transport_failed = summary.get("transport_failed") or []
    if transport_failed:
        failures.append(
            f"AGGREGATE_TRANSPORT_FAILED: jobs with no raw result: {transport_failed}"
        )

    wrapper_schema_fail = summary.get("wrapper_schema_fail") or []
    if wrapper_schema_fail:
        failures.append(
            f"AGGREGATE_WRAPPER_FAIL: jobs with malformed raw: {wrapper_schema_fail}"
        )

    requires_changes = summary.get("codex_requires_changes") or []
    if requires_changes:
        failures.append(
            f"AGGREGATE_HAS_REQUIRES_CHANGES: parent_status={parent_status} forbids "
            f"unfixed Codex findings; jobs={requires_changes}"
        )

    missing_primary = summary.get("missing_primary_target") or []
    if missing_primary:
        failures.append(
            f"AGGREGATE_MISSING_PRIMARY_TARGET: jobs={missing_primary}"
        )

    # Plan 1: new blocking arrays
    stale = summary.get("stale_target_hash") or []
    if stale:
        failures.append(
            f"AGGREGATE_STALE_TARGET_HASH: raw result does not match current plan hash; jobs={stale}"
        )

    unbound = summary.get("unbound_result") or []
    if unbound:
        failures.append(
            f"AGGREGATE_UNBOUND_RESULT: raw result cannot be bound to any known target; jobs={unbound}"
        )

    unconsumed = summary.get("unconsumed_result") or []
    if unconsumed:
        failures.append(
            f"AGGREGATE_UNCONSUMED_RESULT: raw result exists but was not consumed; jobs={unconsumed}"
        )

    constrained = summary.get("constrained_review_not_final_approval") or []
    if constrained:
        failures.append(
            f"AGGREGATE_CONSTRAINED_REVIEW: completed_with_constraint cannot serve as final approval; jobs={constrained}"
        )

    # GD-1 revision=18: stale_review_contract blocking (SC-3)
    stale_contract = summary.get("stale_review_contract") or []
    if stale_contract:
        failures.append(
            f"AGGREGATE_STALE_REVIEW_CONTRACT: review was produced under a different review contract "
            f"(commands/gd.md or prompts/gd-review-standard.md changed since review); jobs={stale_contract}. "
            f"Re-run Codex review with current contract to get a valid aggregate-final.json."
        )

    # GD-1 revision=18: ambiguous_raw_result blocking (SC-4)
    ambiguous = summary.get("ambiguous_raw_result") or []
    if ambiguous:
        failures.append(
            f"AGGREGATE_AMBIGUOUS_RAW_RESULT: multiple late raw files match the same job; "
            f"cannot determine which review is canonical; jobs={ambiguous}. "
            f"Remove duplicate raws or provide explicit codex_raw_result_path in manifest."
        )

    # Each transport_ok job MUST have non-null raw_result_path + raw_result_hash
    for j in jobs:
        if j.get("transport_status") != "transport_ok":
            continue
        if not j.get("raw_result_path"):
            failures.append(
                f"AGGREGATE_JOB_MISSING_RAW_PATH: queue_job_id={j.get('queue_job_id')!r}"
            )
        if not j.get("raw_result_hash"):
            failures.append(
                f"AGGREGATE_JOB_MISSING_RAW_HASH: queue_job_id={j.get('queue_job_id')!r}"
            )

    return failures


def lint_subplan_codex_binding(
    aggregate_path: Path | None,
    reports_dir: Path,
    parent_status: str,
) -> list[str]:
    """Plan 7 SC-2: parent_status in {local_only_complete_with_codex_signoff,
    fully_completed} requires every APPROVED sub-plan review report to bind to
    a specific Codex round 2 raw result via gd-validate-subplan-codex-binding.py.

    SSOT pattern: parent gate ONLY subprocesses the canonical binding validator;
    it MUST NOT re-implement header / hash / file comparison logic locally.
    Plan 6 SC-6 static check still passes because we only reference the script
    name and CLI flags, not any binding-validator schema fields.
    """
    failures: list[str] = []
    if parent_status not in {
        "local_only_complete_with_codex_signoff",
        "fully_completed",
    }:
        return failures  # not applicable

    if aggregate_path is None or not aggregate_path.is_file():
        # AGGREGATE_REQUIRED_FOR_SIGNOFF already raised by lint_aggregate_for_signoff.
        return failures

    if not SUBPLAN_BINDING_VALIDATOR.exists():
        failures.append(
            f"SUBPLAN_BINDING_VALIDATOR_MISSING: expected at {SUBPLAN_BINDING_VALIDATOR}; "
            f"cannot subprocess SSOT validator"
        )
        return failures

    cmd = [
        sys.executable,
        str(SUBPLAN_BINDING_VALIDATOR),
        "--reports-dir", str(reports_dir),
        "--aggregate-json", str(aggregate_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        failures.append(
            f"SUBPLAN_BINDING_VALIDATION_FAIL (parent_status={parent_status}): "
            f"{r.stderr.strip()[:600] or 'binding validator exited non-zero with no stderr'}"
        )
    return failures


def lint_runtime_evidence_for_status(
    runtime_evidence_path: Path | None, parent_status: str
) -> list[str]:
    """Plan 6 §6 truth table: parent_status=fully_completed requires --runtime-evidence-json,
    and the runtime evidence must pass the SSOT validator under that parent status.

    We DO NOT parse the runtime evidence JSON here — all schema/hash/pairing semantics
    live in the SSOT validator. We only:
      - enforce the CLI requirement (presence)
      - subprocess the SSOT validator and propagate failure

    Plan 5 v3 Q2 lesson: consumer must subprocess the canonical validator, never
    re-implement schema field semantics.
    """
    failures: list[str] = []
    requires_runtime_evidence = parent_status == "fully_completed"

    if runtime_evidence_path is None:
        if requires_runtime_evidence:
            failures.append(
                f"RUNTIME_EVIDENCE_REQUIRED_FOR_STATUS: parent_status={parent_status} "
                f"requires --runtime-evidence-json pointing to a Plan 6 evidence JSON"
            )
        return failures

    if not runtime_evidence_path.is_file():
        failures.append(
            f"RUNTIME_EVIDENCE_FILE_MISSING: --runtime-evidence-json {runtime_evidence_path} not found"
        )
        return failures

    if not RUNTIME_EVIDENCE_VALIDATOR.exists():
        failures.append(
            f"RUNTIME_EVIDENCE_VALIDATOR_MISSING: expected at {RUNTIME_EVIDENCE_VALIDATOR}; "
            f"cannot subprocess SSOT validator"
        )
        return failures

    cmd = [
        sys.executable,
        str(RUNTIME_EVIDENCE_VALIDATOR),
        str(runtime_evidence_path),
    ]
    if requires_runtime_evidence:
        cmd.extend(["--for-parent-status", parent_status])
    elif parent_status in {"local_only_complete_with_codex_signoff", "requires_changes"}:
        cmd.extend(["--for-parent-status", parent_status])

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        failures.append(
            f"RUNTIME_EVIDENCE_VALIDATION_FAIL (parent_status={parent_status}): "
            f"{r.stderr.strip()[:400] or 'validator exited non-zero with no stderr'}"
        )
    return failures


def lint_codex_status_consistency(parent_text: str, parent_status: str) -> list[str]:
    """Plan I §7 + 补 B:
    - parent_status `requires_changes` must record at least 1 Codex finding (in
      a `CODEX_FINDING:` block or §"Codex round 1 cross-review findings" section).
    - parent_status `local_only_complete_with_codex_signoff` (or `fully_completed`)
      must NOT contain stale `codex_transport_unavailable` (Plan I batch 1
      removed transport blockage).
    """
    failures: list[str] = []
    contains_finding_record = (
        "CODEX_FINDING:" in parent_text
        or "Codex round 1 cross-review findings" in parent_text
        or "Codex round 1 cross-review" in parent_text
    )
    if parent_status == "requires_changes" and not contains_finding_record:
        failures.append(
            "REQUIRES_CHANGES_WITHOUT_FINDINGS: parent declares requires_changes but "
            "records no `CODEX_FINDING:` block or 'Codex round 1 cross-review findings' section"
        )
    if parent_status in {"local_only_complete_with_codex_signoff", "fully_completed"}:
        # Strip backtick-wrapped occurrences (descriptive prose) before lint.
        scrubbed = re.sub(r"`[^`]*`", "", parent_text)
        if "codex_transport_unavailable" in scrubbed:
            failures.append(
                f"STALE_CODEX_TRANSPORT_LABEL: parent status {parent_status} but "
                f"non-prose text still mentions `codex_transport_unavailable` — "
                f"bridge is now available, re-run cross-review and remove stale labels"
            )
    return failures


def lint_dual_runtime_escalation(parent_text: str, manual_entries: list[dict]) -> list[str]:
    """Round 5 reinforcement #1: Desktop column 'passed' requires
    manual_evidence_complete + scope contains '6/6'.
    """
    failures: list[str] = []
    section = extract_section(parent_text, DUAL_RUNTIME_HEADER_RE)
    if not section:
        return ["dual-runtime matrix section (## 1.) not found in parent report"]

    desktop_passed_lines: list[str] = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        # table layout per parent report: | 命令 | terminal | Desktop | 证据 |
        # cells: ['', 命令, terminal, Desktop, 证据, '']
        if len(cells) < 5:
            continue
        desktop_cell = cells[3]
        # Header row check — skip the column-header line itself
        if desktop_cell.lower() in ("claude desktop", "---", ""):
            continue
        # 'passed' present (case-insensitive) but NOT 'not_applicable'
        cell_lower = desktop_cell.lower()
        if "passed" in cell_lower and "not_applicable" not in cell_lower:
            desktop_passed_lines.append(line.strip())

    if not desktop_passed_lines:
        return failures

    # Any Desktop=passed needs a backing manual_evidence_complete entry whose
    # scope mentions 6/6.
    backing = [
        e for e in manual_entries
        if e["kind"] == "manual_evidence_complete" and "6/6" in e["scope"]
    ]
    if not backing:
        for ln in desktop_passed_lines:
            failures.append(
                "DESKTOP_ESCALATION_WITHOUT_EVIDENCE: §1 Desktop column has 'passed' "
                "without §9 manual_evidence_complete entry whose scope contains '6/6'. "
                f"offending row: {ln[:120]}"
            )
    return failures


def lint_manual_evidence_kind(parent_text: str) -> tuple[list[dict], list[str]]:
    """Round 5 reinforcement #2: every MANUAL_EVIDENCE_ENTRY block must declare
    kind ∈ MANUAL_EVIDENCE_KIND_ENUM. Unknown kinds → fail.
    Returns (parsed_entries, failures).
    """
    failures: list[str] = []
    entries: list[dict] = []
    for m in MANUAL_EVIDENCE_ENTRY_RE.finditer(parent_text):
        kind = m.group(1).strip().rstrip(",。")
        date = m.group(2).strip()
        scope = m.group(3).strip()
        # Skip the schema example block (kinds wrapped in <...> placeholder)
        if kind.startswith("<") and kind.endswith(">"):
            continue
        if kind not in MANUAL_EVIDENCE_KIND_ENUM:
            failures.append(
                f"MANUAL_EVIDENCE_KIND_INVALID: kind={kind!r} not in "
                f"{sorted(MANUAL_EVIDENCE_KIND_ENUM)}"
            )
        entries.append({"kind": kind, "date": date, "scope": scope})
    return entries, failures


def read_json_block(text: str) -> dict | None:
    m = re.search(
        r"<!-- gd-review-result-json:start -->\n```json\n(.+?)\n```\n<!-- gd-review-result-json:end -->",
        text,
        re.S,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def has_exact_header_line(text: str, line: str) -> bool:
    pattern = rf"^{re.escape(line)}\s*$"
    return any(re.match(pattern, ln) for ln in text.splitlines())


def parse_deferred(args_w2: list[str]) -> tuple[dict[str, str] | None, int]:
    deferred: dict[str, str] = {}
    for entry in args_w2:
        if ":" not in entry:
            err("BAD_DEFERRED_FORMAT", f"expect <id>:<reason>, got {entry!r}", 2)
            return None, 2
        sid, reason = entry.split(":", 1)
        if sid not in SUBPLANS:
            err("UNKNOWN_DEFERRED_ID", f"{sid!r} not in {SUBPLANS}", 2)
            return None, 2
        deferred[sid] = reason
    return deferred, 0


def evaluate_subplan(
    sid: str,
    plans_dir: Path,
    reports_dir: Path,
    deferred: dict[str, str],
    allow_constrained: list[str],
    parent_status: str,
) -> tuple[dict, list[str]]:
    plan_path = plans_dir / f"{sid}-master-plan.md"
    report_path = reports_dir / f"gd-v7-plan-h-{sid}-review.md"
    failures: list[str] = []

    record: dict = {
        "sub_plan": sid,
        "plan_present": plan_path.is_file(),
        "report_present": report_path.is_file(),
    }

    if not plan_path.is_file():
        failures.append(f"{sid}: plan missing ({plan_path})")
        return record, failures
    if not report_path.is_file():
        failures.append(f"{sid}: review report missing ({report_path})")
        return record, failures

    text = report_path.read_text(encoding="utf-8")
    decision_full = has_exact_header_line(text, "GD_REVIEW_DECISION: APPROVED")
    decision_partial = has_exact_header_line(text, "GD_REVIEW_DECISION: APPROVED_PARTIAL")
    status_completed = has_exact_header_line(text, "REVIEW_RUN_STATUS: completed")
    status_constraint = has_exact_header_line(
        text, "REVIEW_RUN_STATUS: completed_with_constraint"
    )
    data = read_json_block(text)
    recorded_reason = ""
    if data:
        recorded_reason = (data.get("merge_notes") or {}).get("degraded_reason") or ""

    is_deferred = sid in deferred

    record.update(
        {
            "decision_full": decision_full,
            "decision_partial": decision_partial,
            "status_completed": status_completed,
            "status_constraint": status_constraint,
            "deferred_declared": is_deferred,
            "deferred_reason_declared": deferred.get(sid),
            "recorded_degraded_reason": recorded_reason,
        }
    )

    # ── requires_changes mode: parent has acknowledged unfixed Codex findings.
    # No sub-plan-level constraints — gate just confirms the status is honest.
    # Acceptance: at least 1 sub-plan in this run produced Codex findings.
    if parent_status == "requires_changes":
        # No per-sub-plan failures — caller is allowed to take this status.
        # The parent_text-level lint (after this loop) checks that the parent
        # actually records the codex findings instead of vague claims.
        return record, failures

    # ── local_only_complete_with_codex_signoff mode: bridge OK + every
    # non-deferred sub-plan must be APPROVED (exact) AND Codex APPROVED for it
    # (recorded in residual_risk / forward tracks of parent report).
    if parent_status == "local_only_complete_with_codex_signoff":
        if is_deferred:
            failures.append(
                f"{sid}: parent status local_only_complete_with_codex_signoff forbids "
                f"--w2-deferred (saw {sid}:{deferred[sid]!r})"
            )
        if not decision_full:
            failures.append(
                f"{sid}: codex_signoff requires exact `GD_REVIEW_DECISION: APPROVED` "
                f"(decision_partial={decision_partial})"
            )
        if decision_partial:
            failures.append(
                f"{sid}: codex_signoff forbids `GD_REVIEW_DECISION: APPROVED_PARTIAL`"
            )
        # codex_signoff allows REVIEW_RUN_STATUS: completed_with_constraint IFF
        # the constraint reason is no longer codex_transport_unavailable (Plan I
        # batch 1 removed that). Other operational constraints are tolerated.
        if status_constraint and "codex_transport_unavailable" in recorded_reason:
            failures.append(
                f"{sid}: codex_signoff forbids stale `codex_transport_unavailable` "
                f"in degraded_reason — bridge is now available, re-run cross-review"
            )
        return record, failures

    # ── fully_completed mode is strictest: no deferred, no constraint, no degraded_reason ──
    if parent_status == "fully_completed":
        if is_deferred:
            failures.append(
                f"{sid}: parent status fully_completed forbids --w2-deferred declarations "
                f"(saw {sid}:{deferred[sid]!r})"
            )
        if not decision_full:
            failures.append(
                f"{sid}: fully_completed requires exact `GD_REVIEW_DECISION: APPROVED` "
                f"(decision_partial={decision_partial})"
            )
        if decision_partial:
            failures.append(
                f"{sid}: fully_completed forbids `GD_REVIEW_DECISION: APPROVED_PARTIAL`"
            )
        if not status_completed:
            failures.append(
                f"{sid}: fully_completed requires exact `REVIEW_RUN_STATUS: completed` "
                f"(status_constraint={status_constraint})"
            )
        if status_constraint:
            failures.append(
                f"{sid}: fully_completed forbids `REVIEW_RUN_STATUS: completed_with_constraint`"
            )
        if recorded_reason.strip():
            failures.append(
                f"{sid}: fully_completed requires empty merge_notes.degraded_reason "
                f"(recorded={recorded_reason!r})"
            )
        return record, failures

    # ── local_only_complete_with_w2_blocked mode ──
    if is_deferred:
        if not (decision_partial or decision_full):
            failures.append(
                f"{sid}: declared --w2-deferred but report has neither APPROVED nor APPROVED_PARTIAL header"
            )
            return record, failures
        if not (status_completed or status_constraint):
            failures.append(
                f"{sid}: declared --w2-deferred but report has no REVIEW_RUN_STATUS header"
            )
            return record, failures
        if deferred[sid] not in recorded_reason:
            failures.append(
                f"{sid}: declared --w2-deferred reason {deferred[sid]!r} "
                f"not present in merge_notes.degraded_reason={recorded_reason!r}"
            )
        return record, failures

    # Non-deferred sub-plan under local_only mode:
    #   must be APPROVED (exact); APPROVED_PARTIAL → fail unless declared deferred.
    if not decision_full:
        failures.append(
            f"{sid}: missing exact `GD_REVIEW_DECISION: APPROVED` header "
            f"(decision_partial={decision_partial})"
        )
    if decision_partial:
        failures.append(
            f"{sid}: has `GD_REVIEW_DECISION: APPROVED_PARTIAL` but not declared --w2-deferred"
        )

    # REVIEW_RUN_STATUS rule: completed (clean) OR completed_with_constraint
    # provided the recorded degraded_reason matches the allowlist.
    if not status_completed and not status_constraint:
        failures.append(
            f"{sid}: missing both `REVIEW_RUN_STATUS: completed` and "
            f"`REVIEW_RUN_STATUS: completed_with_constraint` header"
        )
    elif status_constraint and not status_completed:
        if not allow_constrained:
            failures.append(
                f"{sid}: has `REVIEW_RUN_STATUS: completed_with_constraint` but "
                f"--allow-constrained-reason is not set"
            )
        else:
            allowed = any(reason in recorded_reason for reason in allow_constrained)
            if not allowed:
                failures.append(
                    f"{sid}: degraded_reason={recorded_reason!r} matches no "
                    f"--allow-constrained-reason ({allow_constrained})"
                )
            else:
                record["constrained_reason_allowlisted"] = True

    return record, failures


def validate_closure_json(path: Path) -> int:
    """JSON-mode close gate: validate a closure/aggregate JSON fixture for final closure eligibility.

    Called when the script receives a single positional JSON file argument (no flags).
    Applies Step 6 rejection rules:
      1. Fixture/mock-tagged reports → rejected
      2. Missing controller_report_path → rejected
      3. Missing stage_dispatch_ledger_path → rejected
      4. Non-approval mapped_status with APPROVED verdict → rejected
      5. Stale aggregate → rejected
      6. Codex-only approval (claude_review_missing/skipped) → rejected

    Exit codes: 0 = gate satisfied, 1 = rejected, 2 = bad input.
    """
    if not path.is_file():
        print(f"PARENT_CLOSE_GATE_INVALID: file_not_found — {path}", file=sys.stderr)
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"PARENT_CLOSE_GATE_INVALID: json_parse_error — {e}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("PARENT_CLOSE_GATE_INVALID: root_not_object", file=sys.stderr)
        return 2

    failures: list[str] = []

    # Rule 1: Reject fixture/mock-tagged reports
    if data.get("run_mode") == "fixture":
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: fixture_mode_rejected — fixture/mock evidence cannot be final closure"
        )
    if data.get("controller_run_mode") == "fixture":
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: fixture_mode_rejected — fixture/mock evidence cannot be final closure"
        )
    closure_ev = data.get("closure_evidence") or {}
    if closure_ev.get("controller_run_mode") == "fixture":
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: fixture_mode_rejected — fixture/mock evidence cannot be final closure"
        )
    jobs = data.get("jobs") or []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("git_gate_status") == "fixture_mode":
            failures.append(
                "PARENT_CLOSE_GATE_INVALID: fixture_mode_rejected — fixture/mock evidence cannot be final closure"
            )
            break
        if job.get("bridge_stderr_summary") == "fixture_mode_no_real_bridge":
            failures.append(
                "PARENT_CLOSE_GATE_INVALID: fixture_mode_rejected — fixture/mock evidence cannot be final closure"
            )
            break

    # Rule 5: Reject stale aggregate
    if data.get("is_stale_aggregate") is True:
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: stale_aggregate_rejected — is_stale_aggregate=true"
        )
    agg_source = data.get("aggregate_source", "")
    if isinstance(agg_source, str) and agg_source == "aggregate.json":
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: stale_aggregate_rejected — aggregate_source must be aggregate-final.json, not aggregate.json"
        )

    # Rule 2: Require controller_report_path
    has_ctrl_report = bool(
        (closure_ev.get("controller_report_path"))
        or (data.get("controller_report_path"))
    )
    if not has_ctrl_report:
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: missing_controller_report — schema-validated controller/merge report required for final closure"
        )

    # Rule 3: Require stage_dispatch_ledger_path
    has_ledger = bool(
        (closure_ev.get("stage_dispatch_ledger_path"))
        or (data.get("stage_dispatch_ledger_path"))
    )
    if not has_ledger:
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: missing_stage_dispatch_ledger — stage dispatch ledger required for final closure"
        )

    # Rule 4: Reject non-approval mapped_status when verdict=APPROVED
    top_verdict = data.get("verdict") or data.get("decision") or ""
    is_top_approved = str(top_verdict).upper() == "APPROVED"
    INELIGIBLE_STATUSES = frozenset({
        "transport_failed", "failed_to_run", "timeout", "degraded",
        "wrapper_schema_fail", "local_only", "human_exec",
    })
    if is_top_approved:
        for job in jobs:
            if not isinstance(job, dict):
                continue
            ms = job.get("mapped_status", "")
            if ms in INELIGIBLE_STATUSES:
                job_id = job.get("queue_job_id") or job.get("job_id") or "(unknown)"
                failures.append(
                    f"PARENT_CLOSE_GATE_INVALID: closure_ineligible: {ms} in job {job_id}"
                )

    # Rule 6: Reject codex-only approval (no Claude review evidence)
    if data.get("claude_review_missing") is True or data.get("claude_review_status") == "skipped":
        failures.append(
            "PARENT_CLOSE_GATE_INVALID: claude_review_missing — Claude review evidence required for APPROVED verdict"
        )

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        return 1

    print(f"PARENT_CLOSE_GATE_VALID: {path.name}")
    return 0


def main() -> int:
    # JSON-mode: single positional arg that ends in .json → run closure JSON gate.
    # This is the Step 6 entry point for validating closure/aggregate JSON fixtures.
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        candidate = Path(sys.argv[1])
        if candidate.suffix == ".json" or candidate.name.endswith(".json"):
            return validate_closure_json(candidate)

    parser = argparse.ArgumentParser(
        description="Parent close gate (PH-SC-5) — parent-status-aware sub-plan check"
    )
    parser.add_argument("--plans-dir", required=True, type=Path)
    parser.add_argument("--reports-dir", required=True, type=Path)
    parser.add_argument(
        "--parent-report",
        required=True,
        type=Path,
        help="Path to parent close report (must contain PARENT_CLOSE_STATUS line)",
    )
    parser.add_argument("--w2-deferred", action="append", default=[])
    parser.add_argument("--allow-constrained-reason", action="append", default=[])
    parser.add_argument(
        "--aggregate-json",
        type=Path,
        default=None,
        help="Optional aggregate v2 JSON (schema/gd-codex-cross-review-aggregate.schema.json). "
             "Required for parent_status=local_only_complete_with_codex_signoff or fully_completed.",
    )
    parser.add_argument(
        "--runtime-evidence-json",
        type=Path,
        default=None,
        help="Optional Plan 6 runtime evidence JSON. Required for parent_status=fully_completed. "
             "Validated via subprocess to gd-validate-runtime-evidence.py (SSOT).",
    )
    args = parser.parse_args()

    if not args.parent_report.is_file():
        return err("PARENT_REPORT_MISSING", str(args.parent_report), 2)

    parent_status, all_matches = parse_parent_status(args.parent_report)
    if parent_status is None:
        return err(
            "PARENT_STATUS_MISSING",
            f"no `PARENT_CLOSE_STATUS:` line found in {args.parent_report}",
        )
    if len(set(all_matches)) > 1:
        return err(
            "PARENT_STATUS_INCONSISTENT",
            f"multiple parent statuses disagree after normalization: {sorted(set(all_matches))}",
        )
    if parent_status not in VALID_PARENT_STATUSES:
        return err(
            "PARENT_STATUS_UNKNOWN",
            f"{parent_status!r} not in {sorted(VALID_PARENT_STATUSES)}",
            2,
        )

    deferred, rc = parse_deferred(args.w2_deferred)
    if deferred is None:
        return rc

    # fully_completed: parent disallows any deferred declaration upfront
    # (we still feed deferred to evaluate_subplan so per-sub-plan failure is
    # explicit rather than silently swallowed).

    summary: list[dict] = []
    failures: list[str] = []
    for sid in SUBPLANS:
        rec, errs = evaluate_subplan(
            sid,
            args.plans_dir,
            args.reports_dir,
            deferred,
            args.allow_constrained_reason,
            parent_status,
        )
        summary.append(rec)
        failures.extend(errs)

    # Round 5 reinforcements: manual evidence appendix lint + dual-runtime
    # escalation guard. Both checks are only meaningful when the parent has
    # a real ## 1. dual-runtime section (skipped for raw-fixture parent files
    # that only declare PARENT_CLOSE_STATUS: ...).
    parent_text = args.parent_report.read_text(encoding="utf-8")
    manual_entries, manual_failures = lint_manual_evidence_kind(parent_text)
    failures.extend(manual_failures)
    if DUAL_RUNTIME_HEADER_RE.search(parent_text):
        failures.extend(lint_dual_runtime_escalation(parent_text, manual_entries))
    # Plan I §7 + 补 B: Codex status consistency lint
    failures.extend(lint_codex_status_consistency(parent_text, parent_status))
    # Review Trust §Step 5: aggregate JSON consumption (parent close gate trusts
    # aggregate v2 over self-declarations).
    failures.extend(lint_aggregate_for_signoff(args.aggregate_json, parent_status))
    # Plan 6: runtime evidence subprocess gate (SSOT — never re-parse schema here).
    failures.extend(
        lint_runtime_evidence_for_status(args.runtime_evidence_json, parent_status)
    )
    # Plan 7: subplan codex binding subprocess gate (SSOT — same pattern).
    failures.extend(
        lint_subplan_codex_binding(args.aggregate_json, args.reports_dir, parent_status)
    )

    approved_exact = sum(
        1
        for r in summary
        if r.get("decision_full") and r.get("status_completed") and not r.get("deferred_declared")
    )
    constrained = sum(
        1
        for r in summary
        if r.get("decision_full")
        and r.get("status_constraint")
        and not r.get("deferred_declared")
    )
    deferred_count = sum(1 for r in summary if r.get("deferred_declared"))

    print(
        json.dumps(
            {
                "parent_status": parent_status,
                "approved_exact_count": approved_exact,
                "constrained_count": constrained,
                "deferred_count": deferred_count,
                "manual_evidence_entries": manual_entries,
                "sub_plans": summary,
                "failures": failures,
            },
            indent=2,
        )
    )

    if failures:
        return 1
    print(
        f"OK: parent close gate satisfied; "
        f"parent_status={parent_status}; "
        f"approved_exact={approved_exact}; constrained={constrained}; deferred={deferred_count}; "
        f"manual_evidence_entries={len(manual_entries)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
