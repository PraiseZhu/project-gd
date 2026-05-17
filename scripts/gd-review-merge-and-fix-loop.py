#!/usr/bin/env python3
"""
gd-review-merge-and-fix-loop.py — Plan H2a lock_revision=3 (v2 partial)

Drives the /gd review plan dual review + bounded auto-fix loop.

Production usage (Plan H2a v2 partial):
  python3 scripts/gd-review-merge-and-fix-loop.py --plan <plan.md> [--output-dir DIR]

  Branches:
    Codex bridge unavailable → fail-closed: writes loop report with
      outcome=codex_transport_unavailable, capability_status=
      blocked_missing_artifact; exits 1 with CODEX_TRANSPORT_UNAVAILABLE.
    Codex bridge available  → NOT YET IMPLEMENTED (FW-H2A-3a; requires W2
      unblock for live testing). Returns exit 1 NOT_IMPLEMENTED today.

  Critical invariant: must never produce APPROVED when Codex is unreachable.

Fixture / test mode:
  python3 scripts/gd-review-merge-and-fix-loop.py --fixture <scenario.json>

  Replays a pre-recorded scenario from a JSON file and exits with the code
  declared in expected_outcome.exit_code, printing a human-readable loop
  trace so the caller can confirm the right error codes are produced.

  Supported scenarios (fixture field "scenario"):
    codex_unavailable    — Codex transport blocked; must not produce fake approval
    split_findings       — Claude and Codex each find different issues; both preserved
    fix_then_rereview    — one fix round followed by a passing re-review
    four_rounds_required — three fix rounds exhausted; still REQUIRES_CHANGES at round 4

Error codes emitted to stderr:
  CODEX_TRANSPORT_UNAVAILABLE   Codex bridge not reachable
  AUTO_FIX_EXHAUSTED            max fix rounds (3) reached, plan still failing
  PLAN_FILE_NOT_FOUND           --plan path does not exist
  PLAN_PATH_NOT_FILE            --plan path exists but is not a regular file
  NOT_IMPLEMENTED               Codex-available happy path pending FW-H2A-3a
  FIXTURE_NOT_FOUND             --fixture path does not exist
  FIXTURE_INVALID_JSON          --fixture file is not valid JSON
  FIXTURE_SCHEMA_ERROR          fixture is missing required fields
  FIXTURE_UNKNOWN_SCENARIO      scenario value not recognised
  FIXTURE_VALIDATION_FAILED     fixture internal consistency check failed
  MERGE_INCOMPLETE              merged findings missing a reviewer's contributions
  MERGE_COUNT_MISMATCH          merged finding count differs from expected
  VERDICT_MISMATCH              final verdict differs from expected_outcome
  FIX_ROUND_COUNT_MISMATCH      fix round count differs from expected
  MERGE_FIX_LOOP_NOT_APPLICABLE Plan 8 v4.1 Step 7: caller passed a non-plan
                                review_kind; this script is plan-only (exit 2)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_AUTO_FIX_ROUNDS = 3
LOCK_REVISION = 3  # H2a contract revision; bump when contract semantics change

# Plan 8 v4.1 Step 7: this script remains plan-only. Non-plan v2 review kinds
# are rejected with a clear MERGE_FIX_LOOP_NOT_APPLICABLE error so callers do
# not assume the bounded auto-fix loop applies to execution_outcome / code_diff
# / combined reviews. The valid set is sourced from the SSOT contract module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gd_review_contract import (  # noqa: E402
    REVIEW_KIND_ENUM as _SSOT_REVIEW_KIND_ENUM,
)

DEFAULT_REVIEW_KIND = "plan"
NON_PLAN_REVIEW_KINDS = frozenset(_SSOT_REVIEW_KIND_ENUM) - {DEFAULT_REVIEW_KIND}

# Q3: env var set BY gd-review-router.py for scripts it spawns.
# In production mode (--plan), this must be set; fixture mode (--fixture) is exempt.
INVOCATION_ID_ENV = "GD_REVIEW_ROUTER_INVOCATION_ID"

# Production closure does not depend on passive ~/.claude/handoff probe; use GD_ENABLE_HANDOFF_PROBE=1 for legacy debug only.
# Codex bridge probe: only checked if GD_ENABLE_HANDOFF_PROBE=1 is set in the environment.
# If not set, the passive probe is skipped entirely and execution proceeds directly.
CODEX_BRIDGE_STATUS_FILE = Path.home() / ".claude" / "handoff" / "codex-bridge-status.json"


def err(code: str, message: str) -> int:
    """Print structured error to stderr and return exit code 1."""
    print(f"ERROR: {code}: {message}", file=sys.stderr)
    return 1


def load_fixture(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: FIXTURE_NOT_FOUND: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: FIXTURE_INVALID_JSON: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Scenario handlers
# ---------------------------------------------------------------------------

def run_codex_unavailable(fx: dict) -> int:
    """
    Scenario: Codex transport is unavailable.
    Expected: exit 1 with CODEX_TRANSPORT_UNAVAILABLE.
    Fail-closed: must never produce fake dual-review approval.
    """
    transport = fx.get("codex_transport", {})
    if transport.get("status") != "unavailable":
        print(
            "ERROR: FIXTURE_SCHEMA_ERROR: codex_transport.status must be 'unavailable'",
            file=sys.stderr,
        )
        return 1

    claude_review = fx.get("claude_review", {})
    print(f"Round 1 — Claude self-review: {claude_review.get('verdict', '?')}")
    for finding in claude_review.get("findings", []):
        print(
            f"  [{finding.get('reviewer', 'claude')}] "
            f"{finding.get('severity', '?')}: {finding.get('description', '?')}"
        )

    print("Round 1 — Codex cross-review: TRANSPORT_UNAVAILABLE")
    error_detail = transport.get("error", "bridge not reachable")
    rc = err("CODEX_TRANSPORT_UNAVAILABLE", error_detail)
    print(
        "FAIL-CLOSED: cannot produce dual-review approval without Codex cross-review.",
        file=sys.stderr,
    )
    return rc


def run_split_findings(fx: dict) -> int:
    """
    Scenario: Claude and Codex each find different issues.
    Expected: exit 0; merged output preserves both reviewers' findings.
    """
    transport = fx.get("codex_transport", {})
    if transport.get("status") != "available":
        print(
            "ERROR: FIXTURE_SCHEMA_ERROR: codex_transport.status must be 'available'",
            file=sys.stderr,
        )
        return 1

    claude_review = fx.get("claude_review", {})
    codex_review = fx.get("codex_review", {})

    claude_findings = claude_review.get("findings", [])
    codex_findings = codex_review.get("findings", [])

    print(f"Round 1 — Claude self-review: {claude_review.get('verdict', '?')}")
    for f in claude_findings:
        print(
            f"  [{f.get('reviewer', 'claude')}] "
            f"{f.get('severity', '?')}: {f.get('description', '?')}"
        )

    print(f"Round 1 — Codex cross-review: {codex_review.get('verdict', '?')}")
    for f in codex_findings:
        print(
            f"  [{f.get('reviewer', 'codex')}] "
            f"{f.get('severity', '?')}: {f.get('description', '?')}"
        )

    # Merge: preserve both, deduplicate exact duplicates
    seen = set()
    merged = []
    for f in claude_findings + codex_findings:
        key = (f.get("reviewer"), f.get("severity"), f.get("description"))
        if key not in seen:
            seen.add(key)
            merged.append(f)

    reviewers_present = {f.get("reviewer") for f in merged}

    print(f"\nMerged findings ({len(merged)} total):")
    for f in merged:
        print(
            f"  [{f.get('reviewer')}] "
            f"{f.get('severity')}: {f.get('description')}"
        )

    if "claude" not in reviewers_present or "codex" not in reviewers_present:
        return err(
            "MERGE_INCOMPLETE",
            "merged findings must contain contributions from both claude and codex reviewers",
        )

    expected = fx.get("expected_outcome", {})
    exp_count = expected.get("merged_finding_count")
    if exp_count is not None and len(merged) != exp_count:
        return err(
            "MERGE_COUNT_MISMATCH",
            f"expected {exp_count} merged findings, got {len(merged)}",
        )

    # Determine merge verdict
    all_verdicts = [claude_review.get("verdict"), codex_review.get("verdict")]
    if any(v in ("REQUIRES_CHANGES", "FAILED") for v in all_verdicts):
        merge_verdict = "REQUIRES_CHANGES"
    else:
        merge_verdict = "APPROVED"

    print(
        f"\nGD_REVIEW_DECISION: {merge_verdict} "
        f"(merged {len(merged)} findings from both reviewers)"
    )
    return 0


def run_fix_then_rereview(fx: dict) -> int:
    """
    Scenario: one fix round followed by a re-review that produces APPROVED.
    Expected: exit 0; loop trace shows fix round then review round.
    """
    rounds = fx.get("rounds", [])
    fix_seen = False
    rereview_after_fix = False
    final_verdict = None

    for entry in rounds:
        rtype = entry.get("type")
        rnum = entry.get("round")

        if rtype == "review":
            claude_v = entry.get("claude_verdict", "?")
            codex_v = entry.get("codex_verdict", "?")
            print(f"Round {rnum} review — Claude: {claude_v}, Codex: {codex_v}")
            for f in entry.get("findings", []):
                print(
                    f"  [{f.get('reviewer', '?')}] "
                    f"{f.get('severity', '?')}: {f.get('description', '?')}"
                )

            if fix_seen:
                rereview_after_fix = True

            if claude_v in ("REQUIRES_CHANGES", "FAILED") or codex_v in (
                "REQUIRES_CHANGES",
                "FAILED",
            ):
                final_verdict = "REQUIRES_CHANGES"
            else:
                final_verdict = "APPROVED"

        elif rtype == "fix":
            print(f"Round {rnum} fix — changes: {entry.get('changes', [])}")
            fix_seen = True

    expected = fx.get("expected_outcome", {})

    if expected.get("has_fix_round") and not fix_seen:
        return err(
            "FIXTURE_VALIDATION_FAILED",
            "expected a fix round in fixture but none found",
        )

    if expected.get("has_rereview_after_fix") and not rereview_after_fix:
        return err(
            "FIXTURE_VALIDATION_FAILED",
            "expected a re-review after fix round but none found",
        )

    exp_verdict = expected.get("final_verdict")
    if exp_verdict and final_verdict != exp_verdict:
        return err(
            "VERDICT_MISMATCH",
            f"expected final verdict '{exp_verdict}', got '{final_verdict}'",
        )

    print(f"\nGD_REVIEW_DECISION: {final_verdict}")
    return 0


def run_four_rounds_required(fx: dict) -> int:
    """
    Scenario: three auto-fix rounds exhausted; plan still REQUIRES_CHANGES at round 4.
    Expected: exit 1 with AUTO_FIX_EXHAUSTED.
    """
    rounds = fx.get("rounds", [])
    fix_count = 0
    last_review_verdict = None

    for entry in rounds:
        rtype = entry.get("type")
        rnum = entry.get("round")

        if rtype == "review":
            claude_v = entry.get("claude_verdict", "?")
            codex_v = entry.get("codex_verdict", "?")
            print(f"Round {rnum} review — Claude: {claude_v}, Codex: {codex_v}")
            for f in entry.get("findings", []):
                print(
                    f"  [{f.get('reviewer', '?')}] "
                    f"{f.get('severity', '?')}: {f.get('description', '?')}"
                )

            if claude_v in ("REQUIRES_CHANGES", "FAILED") or codex_v in (
                "REQUIRES_CHANGES",
                "FAILED",
            ):
                last_review_verdict = "REQUIRES_CHANGES"
            else:
                last_review_verdict = "APPROVED"

        elif rtype == "fix":
            print(f"Round {rnum} fix — changes: {entry.get('changes', [])}")
            fix_count += 1

    expected = fx.get("expected_outcome", {})
    exp_fix_rounds = expected.get("fix_rounds_attempted", MAX_AUTO_FIX_ROUNDS)

    if fix_count != exp_fix_rounds:
        return err(
            "FIX_ROUND_COUNT_MISMATCH",
            f"expected {exp_fix_rounds} fix rounds, got {fix_count}",
        )

    if fix_count >= MAX_AUTO_FIX_ROUNDS and last_review_verdict == "REQUIRES_CHANGES":
        rc = err(
            "AUTO_FIX_EXHAUSTED",
            f"auto-fix ran {fix_count} rounds (max={MAX_AUTO_FIX_ROUNDS}); "
            f"final review still REQUIRES_CHANGES — stopping",
        )
        print(
            f"auto_fix_exhausted after {fix_count} fix rounds.",
            file=sys.stderr,
        )
        return rc

    return 0


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

SCENARIO_HANDLERS = {
    "codex_unavailable": run_codex_unavailable,
    "split_findings": run_split_findings,
    "fix_then_rereview": run_fix_then_rereview,
    "four_rounds_required": run_four_rounds_required,
}


# ---------------------------------------------------------------------------
# Production --plan path (Plan H2a v2: Codex-unavailable fail-closed branch)
# ---------------------------------------------------------------------------

def probe_codex_bridge() -> tuple[str, str | None]:
    """
    Probe whether the Codex bridge (W2) is reachable.

    Returns (status, error_message).
      status ∈ {"available", "unavailable", "unknown"}.
      error_message is None for "available", a human description otherwise.

    Reachability signal: ~/.claude/handoff/codex-bridge-status.json exists and
    parses to a JSON object whose top-level "status" field is "available".
    Anything else (file missing, JSON broken, status not "available") is
    treated as not reachable. This is intentionally a passive probe — it does
    NOT spawn the bridge or run network I/O, so it is safe to call from the
    Claude command runtime without side effects.

    IMPORTANT: This probe is only executed when GD_ENABLE_HANDOFF_PROBE=1 is set.
    In production, the caller skips this function entirely and proceeds directly.
    """
    if not CODEX_BRIDGE_STATUS_FILE.exists():
        return (
            "unavailable",
            f"W2 bridge status file not present at {CODEX_BRIDGE_STATUS_FILE} "
            f"(W2 sandbox whitelist + bridge daemon pending)",
        )
    try:
        data = json.loads(CODEX_BRIDGE_STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (
            "unknown",
            f"W2 bridge status file unreadable or invalid JSON: {exc}",
        )
    declared = data.get("status")
    if declared != "available":
        return (
            "unavailable" if declared in ("unavailable", "unknown") else "unknown",
            f"W2 bridge declares status={declared!r} (need 'available')",
        )
    return "available", None


def write_loop_report(
    output_dir: Path,
    plan_file: Path,
    outcome: str,
    capability_status: str,
    rounds: list[dict],
    codex_transport: dict,
    fallback_reason: str | None = None,
) -> Path:
    """
    Write a loop_report JSON that conforms to
    templates/gd-plan-review-loop-report-template.md.

    Returns the absolute path of the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = output_dir / f"gd-review-loop-report-{timestamp}.json"

    fix_rounds = sum(1 for r in rounds if r.get("type") == "fix")
    total_rounds = sum(1 for r in rounds if r.get("type") == "review")

    report = {
        "loop_report_version": "1.0",
        "plan_file": str(plan_file),
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lock_revision": LOCK_REVISION,
        "outcome": outcome,
        "capability_status": capability_status,
        "codex_transport": codex_transport,
        "total_rounds": total_rounds,
        "fix_rounds": fix_rounds,
        "rounds": rounds,
    }
    if fallback_reason:
        report["fallback_reason"] = fallback_reason

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report_path


def _parse_raw_result_verdict(raw_text: str) -> tuple[str, str]:
    """Extract VERDICT and review_run_status from raw .result markdown.
    Returns (verdict, run_status).
    """
    # Look for VERDICT: line (not REV_VERDICT, not PLAN_VERDICT etc.)
    for line in raw_text.splitlines():
        stripped = line.strip()
        # Match "VERDICT: APPROVED/REQUIRES_CHANGES/FAILED" at line start
        m = re.match(r'^VERDICT:\s+(APPROVED|REQUIRES_CHANGES|FAILED)\s*$', stripped)
        if m:
            return m.group(1), "completed"
    return "FAILED", "degraded"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _consume_and_merge(
    plan_path: Path,
    output_dir: Path,
    claude_review_path: str | None,
    codex_raw_result_path: str | None,
    codex_mapped_result_path: str | None,
    review_contract: str,
    expected_target_hash: str | None,
) -> int:
    """Plan 1 consumption path: parse existing raw results + merge with Claude review.

    SC-3: raw exists → transport_ok, no codex_transport_unavailable.
    SC-4: malformed raw → wrapper_schema_fail; missing raw → transport_failed.
    SC-5: stale target hash → stale_target_hash, not APPROVED.
    """
    import datetime
    print("=== gd-review-merge-and-fix-loop: consumption path (Plan 1) ===")
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Target binding check (SC-5) ---
    current_plan_hash = _sha256_file(plan_path)
    binding_status = "bound"
    if expected_target_hash and expected_target_hash != current_plan_hash:
        binding_status = "stale_target_hash"
        print(f"BINDING: stale_target_hash (expected={expected_target_hash[:16]}... actual={current_plan_hash[:16]}...)")
    else:
        print(f"BINDING: bound (plan_hash={current_plan_hash[:16]}...)")

    # --- Claude review load ---
    claude_review = None
    if claude_review_path:
        cp = Path(claude_review_path)
        if not cp.exists():
            print(f"ERROR: CLAUDE_REVIEW_REQUIRED: file not found: {claude_review_path}", file=sys.stderr)
            return 1
        try:
            claude_review = json.loads(cp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"ERROR: CLAUDE_REVIEW_INVALID: JSON parse error: {e}", file=sys.stderr)
            return 1
    else:
        print("ERROR: CLAUDE_REVIEW_REQUIRED: --claude-review is required for consumption path", file=sys.stderr)
        return 1

    # --- Codex raw/mapped result load and classification (SC-3, SC-4) ---
    transport_status = "transport_failed"
    codex_verdict = "MISSING"
    codex_run_status = "failed_to_run"
    raw_result_path_str = None
    raw_result_hash = None
    classification = "transport_failed"

    if codex_mapped_result_path:
        mp = Path(codex_mapped_result_path)
        if mp.exists():
            try:
                mapped = json.loads(mp.read_text(encoding="utf-8"))
                transport_status = "transport_ok"
                codex_verdict = mapped.get("gd_review_decision", "FAILED")
                codex_run_status = mapped.get("review_run_status", "completed")
                classification = "transport_ok"
                raw_result_path_str = codex_mapped_result_path
                raw_result_hash = _sha256_file(mp)
                print(f"CODEX: loaded mapped result from {codex_mapped_result_path}")
            except json.JSONDecodeError:
                classification = "wrapper_schema_fail"
                transport_status = "transport_ok"  # file exists, parsing failed = wrapper fail
    elif codex_raw_result_path:
        rp = Path(codex_raw_result_path)
        if rp.exists():
            raw_text = rp.read_text(encoding="utf-8")
            verdict, run_st = _parse_raw_result_verdict(raw_text)
            if verdict == "FAILED" and run_st == "degraded":
                # Parse failed = wrapper_schema_fail (raw exists but content is bad)
                classification = "wrapper_schema_fail"
                transport_status = "transport_ok"
                codex_verdict = "FAILED"
                codex_run_status = "degraded"
                raw_result_path_str = codex_raw_result_path
                raw_result_hash = _sha256_file(rp)
                print(f"CODEX: wrapper_schema_fail (raw exists but no valid VERDICT) {codex_raw_result_path}")
            else:
                # Valid parse
                transport_status = "transport_ok"
                codex_verdict = verdict
                codex_run_status = run_st
                classification = "transport_ok"
                raw_result_path_str = codex_raw_result_path
                raw_result_hash = _sha256_file(rp)
                print(f"CODEX: transport_ok verdict={codex_verdict} from {codex_raw_result_path}")
        else:
            classification = "transport_failed"
            print(f"CODEX: transport_failed (raw file missing: {codex_raw_result_path})")
    else:
        print("CODEX: no raw or mapped result supplied → transport_failed")

    # --- Merge decision ---
    claude_verdict = claude_review.get("gd_review_decision", "FAILED")
    claude_status = claude_review.get("review_run_status", "completed")

    # completed_with_constraint → REQUIRES_CHANGES (Plan 1 matrix #1.5)
    if codex_run_status == "completed_with_constraint" or claude_status == "completed_with_constraint":
        merged_decision = "REQUIRES_CHANGES"
        merge_reason = "constrained_review_not_final_approval"
    elif classification == "wrapper_schema_fail":
        merged_decision = "REQUIRES_CHANGES"
        merge_reason = f"wrapper_schema_fail: {classification}"
    elif classification == "transport_failed":
        merged_decision = "REQUIRES_CHANGES"
        merge_reason = "transport_failed: no codex result to merge"
    elif binding_status == "stale_target_hash":
        merged_decision = "REQUIRES_CHANGES"
        merge_reason = "stale_target_hash: cannot approve with unbound result"
    elif codex_verdict == "REQUIRES_CHANGES" or claude_verdict == "REQUIRES_CHANGES":
        merged_decision = "REQUIRES_CHANGES"
        merge_reason = "matrix #2: reviewer REQUIRES_CHANGES"
    elif codex_verdict == "APPROVED" and claude_verdict == "APPROVED":
        merged_decision = "APPROVED"
        merge_reason = "matrix #1: both APPROVED"
    else:
        merged_decision = "REQUIRES_CHANGES"
        merge_reason = f"fallback: codex={codex_verdict} claude={claude_verdict}"

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "schema_version": "2.0",
        "plan_file": str(plan_path),
        "plan_hash": current_plan_hash,
        "transport_status": transport_status,
        "classification": classification,
        "binding_status": binding_status,
        "raw_result_path": raw_result_path_str,
        "raw_result_hash": str(raw_result_hash) if raw_result_hash else None,
        "claude_verdict": claude_verdict,
        "codex_verdict": codex_verdict,
        "gd_review_decision": merged_decision,
        "merge_reason": merge_reason,
        "recorded_at": now,
    }

    report_fname = f"loop_report_{now}.json"
    report_path = output_dir / report_fname
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"LOOP_REPORT_WRITTEN: {report_path}")
    print(f"gd_review_decision={merged_decision}")
    print(f"transport_status={transport_status}")

    if merged_decision == "APPROVED":
        return 0
    return 1  # REQUIRES_CHANGES or FAILED = non-zero


def run_production_plan(
    plan_path_str: str,
    output_dir_str: str | None = None,
    claude_review_path: str | None = None,
    codex_raw_result_path: str | None = None,
    codex_mapped_result_path: str | None = None,
    review_contract: str = 'auto',
    expected_target_hash: str | None = None,
) -> int:
    """
    Production --plan path (Plan H2a v2 partial).

    Current scope: the Codex-unavailable fail-closed branch is fully wired:
      1. Validate plan file exists.
      2. Probe Codex bridge (passive: status file presence).
      3. If bridge is NOT available → write a loop report with
         outcome=codex_transport_unavailable, capability_status=
         blocked_missing_artifact, and exit 1 with CODEX_TRANSPORT_UNAVAILABLE.
      4. If bridge IS available → exit 1 with NOT_IMPLEMENTED, pointing at
         FW-H2A-3a (Codex-available happy path requires W2 unblock to test).

    Critical invariant: this function MUST NOT produce APPROVED when Codex
    is not reachable. That would be a fake dual-review (P1 finding from the
    H1/H2a code review).
    """
    plan_path = Path(plan_path_str)
    if not plan_path.exists():
        print(
            f"ERROR: PLAN_FILE_NOT_FOUND: {plan_path}",
            file=sys.stderr,
        )
        return 1
    if not plan_path.is_file():
        print(
            f"ERROR: PLAN_PATH_NOT_FILE: {plan_path}",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(output_dir_str) if output_dir_str else plan_path.parent

    print("=== gd-review-merge-and-fix-loop: production --plan path ===")
    print(f"plan_file  : {plan_path}")
    print(f"output_dir : {output_dir}")
    print()

    # Plan 1: if Claude review JSON is supplied, we can consume existing raw results.
    # This bypasses the codex-bridge-status.json gate (which was a stub gate,
    # not a true transport check) and goes directly to consumption + merge.
    if claude_review_path is not None or codex_raw_result_path is not None or codex_mapped_result_path is not None:
        return _consume_and_merge(
            plan_path=plan_path,
            output_dir=output_dir,
            claude_review_path=claude_review_path,
            codex_raw_result_path=codex_raw_result_path,
            codex_mapped_result_path=codex_mapped_result_path,
            review_contract=review_contract,
            expected_target_hash=expected_target_hash,
        )

    # Production closure does not depend on passive ~/.claude/handoff probe; use GD_ENABLE_HANDOFF_PROBE=1 for legacy debug only.
    # The passive probe is only executed when GD_ENABLE_HANDOFF_PROBE=1 is explicitly set.
    # Without the env var, skip the probe and proceed directly to the NOT_IMPLEMENTED path.
    if os.environ.get("GD_ENABLE_HANDOFF_PROBE") == "1":
        bridge_status, bridge_error = probe_codex_bridge()
        print(f"Codex bridge probe: status={bridge_status}")
        if bridge_error:
            print(f"  detail: {bridge_error}")

        if bridge_status != "available":
            report_path = write_loop_report(
                output_dir=output_dir,
                plan_file=plan_path,
                outcome="codex_transport_unavailable",
                capability_status="blocked_missing_artifact",
                rounds=[],
                codex_transport={"status": bridge_status, "error": bridge_error},
                fallback_reason=(
                    "Codex bridge unreachable; per H2a Fail-closed rule the dual "
                    "review cannot proceed. Loop report written so the runtime "
                    "still produces an auditable artifact."
                ),
            )
            print(f"LOOP_REPORT_WRITTEN: {report_path}")
            print("CAPABILITY_STATUS: blocked_missing_artifact", file=sys.stderr)
            return err(
                "CODEX_TRANSPORT_UNAVAILABLE",
                bridge_error or "Codex bridge not reachable",
            )

    # Bridge available but no review inputs supplied — still not implemented via live writer.
    print(
        "ERROR: NOT_IMPLEMENTED: Codex-available live writer path is FW-H2A-3a. "
        "Supply --claude-review and --codex-raw-result to use existing results.",
        file=sys.stderr,
    )
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "gd-review-merge-and-fix-loop.py — Plan H2a lock_revision=3 "
            "review loop driver"
        )
    )
    parser.add_argument(
        "--fixture",
        metavar="FIXTURE_JSON",
        help="Run in fixture simulation mode (for testing)",
    )
    parser.add_argument(
        "--plan",
        metavar="PLAN_MD",
        help="(production) Plan file to drive the full dual-review loop",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=None,
        help="(production) Where to write the loop report JSON. Defaults to the plan file's parent directory.",
    )
    parser.add_argument(
        "--claude-review",
        metavar="CLAUDE_JSON",
        default=None,
        help="(production) Path to Claude review mapped JSON. Required for live Codex consumption.",
    )
    parser.add_argument(
        "--codex-raw-result",
        metavar="RAW_MD",
        default=None,
        help="(production) Path to existing Codex raw .result file. Read-only parse; writer not invoked.",
    )
    parser.add_argument(
        "--codex-mapped-result",
        metavar="MAPPED_JSON",
        default=None,
        help="(production) Path to pre-mapped Codex result JSON. Used instead of raw parse if provided.",
    )
    parser.add_argument(
        "--review-contract",
        metavar="CONTRACT",
        default="auto",
        choices=["auto", "v1", "v2"],
        help="Raw result parse contract: auto (try v2 then v1), v1, or v2. Default: auto.",
    )
    parser.add_argument(
        "--expected-target-hash",
        metavar="HASH",
        default=None,
        help="SHA-256 of plan file at review submit time. Used for target binding check.",
    )
    parser.add_argument(
        "--legacy-direct",
        action="store_true",
        help="Set GD_REVIEW_ROUTER_DIRECT_LEGACY=1 implicitly — bypass Q3 side-door for legacy/debug use.",
    )
    parser.add_argument(
        "--review-kind",
        default=DEFAULT_REVIEW_KIND,
        help=(
            "Plan 8 v4.1 Step 7: review kind this loop is being asked to drive. "
            "Only 'plan' is supported; non-plan v2 kinds (execution_outcome, "
            "code_diff, combined) are rejected with MERGE_FIX_LOOP_NOT_APPLICABLE "
            "and exit 2 because there is no bounded auto-fix loop for them."
        ),
    )
    args = parser.parse_args()

    # Plan 8 v4.1 Step 7: reject non-plan review_kinds with a clear, structured
    # error. Validation runs first so callers cannot accidentally drive the
    # plan-only loop with a non-plan kind even via --fixture or --plan modes.
    if args.review_kind in NON_PLAN_REVIEW_KINDS:
        print(
            "ERROR: MERGE_FIX_LOOP_NOT_APPLICABLE: "
            f"{args.review_kind} — gd-review-merge-and-fix-loop.py is plan-only; "
            "non-plan review kinds do not have an auto-fix loop",
            file=sys.stderr,
        )
        sys.exit(2)
    if args.review_kind != DEFAULT_REVIEW_KIND:
        # Anything outside the SSOT v2 enum (and not plan) is also a usage error.
        print(
            f"ERROR: MERGE_FIX_LOOP_NOT_APPLICABLE: {args.review_kind!r} is not a "
            f"recognised review_kind; only {DEFAULT_REVIEW_KIND!r} is supported here",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.legacy_direct:
        os.environ["GD_REVIEW_ROUTER_DIRECT_LEGACY"] = "1"

    # Q3: production mode must be invoked via the router state machine.
    # --plan without GD_REVIEW_ROUTER_INVOCATION_ID set means the caller bypassed
    # gd-review-router.py. Fail-closed (exit 2) to prevent silent side-door runs.
    # Use GD_REVIEW_ROUTER_DIRECT_LEGACY=1 only for explicit legacy/debug invocations.
    if args.plan and not os.environ.get(INVOCATION_ID_ENV):
        if not os.environ.get("GD_REVIEW_ROUTER_DIRECT_LEGACY"):
            print(
                f"ERROR: Q3_SIDE_DOOR: {INVOCATION_ID_ENV} is not set. "
                "gd-review-merge-and-fix-loop --plan must be invoked via gd-review-router.py, "
                "which sets this env var. Direct invocation bypasses the state machine. "
                "Set GD_REVIEW_ROUTER_DIRECT_LEGACY=1 to override for legacy/debug use.",
                file=sys.stderr,
            )
            sys.exit(2)
        print(
            f"WARN: Q3_SIDE_DOOR: direct invocation via GD_REVIEW_ROUTER_DIRECT_LEGACY override.",
            file=sys.stderr,
        )

    if args.fixture:
        fx = load_fixture(args.fixture)
        scenario = fx.get("scenario")
        if not scenario:
            print(
                "ERROR: FIXTURE_SCHEMA_ERROR: 'scenario' field required in fixture",
                file=sys.stderr,
            )
            sys.exit(1)
        handler = SCENARIO_HANDLERS.get(scenario)
        if not handler:
            print(
                f"ERROR: FIXTURE_UNKNOWN_SCENARIO: '{scenario}' not recognised; "
                f"valid: {sorted(SCENARIO_HANDLERS)}",
                file=sys.stderr,
            )
            sys.exit(1)

        plan_file = fx.get("plan_file", "<unknown>")
        print("=== gd-review-merge-and-fix-loop: fixture mode ===")
        print(f"scenario  : {scenario}")
        print(f"plan_file : {plan_file}")
        print()

        rc = handler(fx)
        sys.exit(rc)

    if args.plan:
        rc = run_production_plan(
            args.plan,
            output_dir_str=args.output_dir,
            claude_review_path=getattr(args, 'claude_review', None),
            codex_raw_result_path=getattr(args, 'codex_raw_result', None),
            codex_mapped_result_path=getattr(args, 'codex_mapped_result', None),
            review_contract=getattr(args, 'review_contract', 'auto'),
            expected_target_hash=getattr(args, 'expected_target_hash', None),
        )
        sys.exit(rc)

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
