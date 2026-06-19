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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

MAX_AUTO_FIX_ROUNDS = 3  # legacy: kept for fixture handler backward-compat
MAX_REVIEW_ROUNDS = 5    # SC-4: production convergence loop hard ceiling
LOCK_REVISION = 3  # H2a contract revision; bump when contract semantics change

# Plan 8 v4.1 Step 7: this script remains plan-only. Non-plan v2 review kinds
# are rejected with a clear MERGE_FIX_LOOP_NOT_APPLICABLE error so callers do
# not assume the bounded auto-fix loop applies to execution_outcome / code_diff
# / combined reviews. The valid set is sourced from the SSOT contract module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gd_review_contract import (  # noqa: E402
    REVIEW_KIND_ENUM as _SSOT_REVIEW_KIND_ENUM,
    codex_review_status_from_evidence as _codex_review_status_from_evidence,
)

DEFAULT_REVIEW_KIND = "plan"
NON_PLAN_REVIEW_KINDS = frozenset(_SSOT_REVIEW_KIND_ENUM) - {DEFAULT_REVIEW_KIND}

# Q3: env var set BY gd-review-router.py for scripts it spawns.
# In production mode (--plan), this must be set; fixture mode (--fixture) is exempt.
INVOCATION_ID_ENV = "GD_REVIEW_ROUTER_INVOCATION_ID"

# N1 fail-closed sentinel: when a bridge job aborts (exception / timeout /
# non-zero returncode / unparseable mapped result) it MUST NOT return an empty
# findings list, because downstream treats "no findings" as "nothing wrong →
# can resolve / approve". Instead it injects a synthetic blocking finding whose
# category is BRIDGE_FAILURE_CATEGORY. update_baseline_statuses() refuses to
# ever mark such a finding resolved, so a silent bridge failure can never
# collapse into an approval (mirrors gd-codex-bridge-review.py cmd_run_bridge's
# _failed_mapped behaviour).
BRIDGE_FAILURE_CATEGORY = "BRIDGE_FAILURE"

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
# L2 convergence helpers (SC-2 / SC-3 / SC-4)
# ---------------------------------------------------------------------------

LINE_DEDUP_WINDOW = 3


def _severity_rank(s: object) -> int:
    return {"P1": 2, "P2": 1}.get(str(s).strip(), 0)


def _finding_filecat(f: dict) -> tuple[str, str]:
    return (
        str(f.get("file", "")).strip().lower(),
        str(f.get("category", "")).strip().lower(),
    )


def _lines_within_window(a: object, b: object) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(int(a) - int(b)) <= LINE_DEDUP_WINDOW
    except (TypeError, ValueError):
        return False


def merge_findings_union(
    codex_a: list[dict] | None,
    codex_b: list[dict] | None,
    claude: list[dict] | None,
) -> list[dict]:
    """三方并集去重。去重键=(file归一化小写, category归一化小写, line±3)。severity取高。
    首报方记 source，其余记 also_reported_by。
    """
    sources = [
        ("codex_a", codex_a or []),
        ("codex_b", codex_b or []),
        ("claude", claude or []),
    ]
    merged: list[dict] = []
    counter = [0]

    def _get_id() -> str:
        counter[0] += 1
        return f"F{counter[0]:03d}"

    for src_name, findings in sources:
        for f in findings:
            fc = _finding_filecat(f)
            line = f.get("line")
            matched: dict | None = None
            for m in merged:
                if _finding_filecat(m) == fc and _lines_within_window(m.get("line"), line):
                    matched = m
                    break
            if matched is None:
                merged.append(
                    {
                        "id": _get_id(),
                        "file": f.get("file", ""),
                        "line": line,
                        "category": f.get("category", ""),
                        "severity": f.get("severity", ""),
                        "description": f.get("description", f.get("desc", "")),
                        "status": "unresolved",
                        "source": src_name,
                        "also_reported_by": [],
                        "resolved_in_round": None,
                        "round_history": [{"round": 1, "status": "unresolved"}],
                    }
                )
            else:
                # severity 取高
                if _severity_rank(f.get("severity", "")) > _severity_rank(matched.get("severity", "")):
                    matched["severity"] = f.get("severity", "")
                if src_name not in matched["also_reported_by"] and src_name != matched["source"]:
                    matched["also_reported_by"].append(src_name)
    return merged


def _write_baseline(
    output_dir: Path,
    findings: list[dict],
    invocation_id: str | None = None,
) -> Path:
    """Write baseline_findings.json to output_dir. Returns the written path."""
    baseline = {
        "schema_version": "1.0",
        "baseline_round": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "controller_invocation_id": invocation_id or "unknown",
        "branch": "plan",
        "baseline_unresolved_count": len(
            [f for f in findings if f.get("status") == "unresolved"]
        ),
        "findings": findings,
    }
    path = output_dir / "baseline_findings.json"
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _norm_path(p: object) -> str:
    return str(p or "").strip().lstrip("./").lower()


def update_baseline_statuses(
    baseline_findings: list[dict],
    round_findings: list[dict],
    round_num: int,
    modified_files: set[str] | None = None,
) -> tuple[int, list[dict]]:
    """用本轮 finding 更新 baseline 状态。
    #3 fail-closed: 一个 finding 只有在它所属文件本轮被**实际修改过**
    (modified_files 命中) 且 codex 不再报该 symptom (±3窗口不命中) 时才标
    resolved。仅靠 codex "本轮没再报" 不足以判定 resolved —— 那可能是 bridge
    静默失败 / codex 抖动。modified_files=None 时退化为"无任何文件被改"，因此
    没有 finding 会被判定 resolved。
    delta 中不在 baseline 的 finding 追加为新 unresolved。
    返回 (baseline_unresolved_count, new_in_delta_findings)。
    """
    new_in_delta: list[dict] = []
    modified = {_norm_path(m) for m in (modified_files or set())}

    for bf in baseline_findings:
        if bf.get("status") == "resolved":
            bf.setdefault("round_history", []).append(
                {"round": round_num, "status": "resolved"}
            )
            continue
        # BRIDGE_FAILURE sentinels are never auto-resolved: their absence in a
        # later round just means that round also failed/recovered; resolution
        # of a transport failure is not a code fix.
        if bf.get("bridge_failure") or str(bf.get("category", "")).strip() == BRIDGE_FAILURE_CATEGORY:
            bf.setdefault("round_history", []).append(
                {"round": round_num, "status": bf["status"]}
            )
            continue
        fc = _finding_filecat(bf)
        line = bf.get("line")
        still_reported = any(
            _finding_filecat(rf) == fc and _lines_within_window(line, rf.get("line"))
            for rf in round_findings
        )
        file_touched = _norm_path(bf.get("file")) in modified
        # #3: require an actual modification to the finding's file before a
        # "no longer reported" symptom is accepted as resolved.
        if not still_reported and file_touched:
            bf["status"] = "resolved"
            bf["resolved_in_round"] = round_num
        bf.setdefault("round_history", []).append(
            {"round": round_num, "status": bf["status"]}
        )

    # Append delta findings not in baseline
    counter = len(baseline_findings)
    for rf in round_findings:
        fc = _finding_filecat(rf)
        line = rf.get("line")
        in_baseline = any(
            _finding_filecat(bf) == fc and _lines_within_window(bf.get("line"), line)
            for bf in baseline_findings
        )
        if not in_baseline:
            counter += 1
            entry: dict = {
                "id": f"F{counter:03d}",
                "file": rf.get("file", ""),
                "line": line,
                "category": rf.get("category", ""),
                "severity": rf.get("severity", ""),
                "description": rf.get("description", rf.get("desc", "")),
                "status": "unresolved",
                "source": "delta",
                "also_reported_by": [],
                "resolved_in_round": None,
                "round_history": [{"round": round_num, "status": "unresolved"}],
                "new_in_delta": True,
            }
            baseline_findings.append(entry)
            new_in_delta.append(entry)

    baseline_unresolved = len(
        [f for f in baseline_findings if f.get("status") == "unresolved"]
    )
    return baseline_unresolved, new_in_delta


def _bridge_failure_finding(round_num: int, lens: str, reason: str) -> dict:
    """N1: build a non-empty, never-resolvable blocking finding for a bridge
    job that aborted. Mirrors gd-codex-bridge-review.py _failed_mapped: a
    failure is surfaced as a concrete blocking item, not an empty list."""
    return {
        "id": f"BRIDGE-FAIL-r{round_num}-{lens}",
        "file": f"<bridge:{lens}>",
        "line": None,
        "category": BRIDGE_FAILURE_CATEGORY,
        "severity": "P1",
        "description": (
            f"Codex bridge job failed (round={round_num}, lens={lens}): {reason}. "
            "Fail-closed: a bridge failure is NOT 'no findings'."
        ),
        "bridge_failure": True,
    }


def _run_bridge_job(
    plan_path: Path,
    cwd: Path,
    output_dir: Path,
    round_num: int,
    lens: str,
    env: dict,
) -> list[dict]:
    """Run bridge run-bridge + parse-transport; return findings list.

    N1 fail-closed: on any failure (exception, timeout, non-zero returncode,
    missing/unparseable mapped result) this returns a NON-EMPTY list holding a
    BRIDGE_FAILURE sentinel finding — never []. An empty list is reserved for
    the genuine "bridge ran cleanly and reported zero findings" case, which is
    the only case downstream may treat as a clean lens.
    """
    out_log = output_dir / f"bridge-r{round_num}-{lens}.log"
    mapped_out = output_dir / f"bridge-r{round_num}-{lens}-mapped.json"
    try:
        # N2: check returncode of run-bridge; non-zero → fail-closed sentinel.
        run_res = subprocess.run(
            [
                sys.executable,
                "scripts/gd-codex-bridge-review.py",
                "run-bridge",
                "--kind", "plan",
                "--target", str(plan_path),
                "--cwd", str(cwd),
                "--out", str(out_log),
                "--live-transport",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if run_res.returncode != 0:
            # F4 fix (SC-1 × SC-5 interaction): bridge exit 1 means REQUIRES_CHANGES
            # or FAILED — both are VALID review verdicts per gd.md Review Trust §8.1.
            # Before injecting a BRIDGE_FAILURE sentinel we check whether run-bridge
            # actually produced a TRANSPORT_RESULT (raw result path). If it did, the
            # bridge reached the codex result stage and we should attempt parse-transport
            # to surface the real decision/findings. Only when no transport result is
            # available (failed_to_run / transport failure before codex responded) do we
            # fall through to the BRIDGE_FAILURE sentinel.
            transport_result_path: Path | None = None
            for line in out_log.read_text(encoding="utf-8").splitlines() if out_log.exists() else []:
                if line.startswith("TRANSPORT_RESULT:"):
                    raw_val = line.split(":", 1)[1].strip()
                    if raw_val and raw_val != "N/A":
                        transport_result_path = Path(raw_val)
                    break
            if transport_result_path is None or not transport_result_path.exists():
                return [_bridge_failure_finding(
                    round_num, lens,
                    f"run-bridge returncode={run_res.returncode} and no valid "
                    f"TRANSPORT_RESULT (failed_to_run / transport failure): "
                    f"{(run_res.stderr or run_res.stdout).strip()[:200]}",
                )]
            # Transport result exists — fall through to parse-transport so the
            # real REQUIRES_CHANGES/FAILED verdict and findings are surfaced.

        # N2: check returncode of parse-transport too.
        parse_res = subprocess.run(
            [
                sys.executable,
                "scripts/gd-codex-bridge-review.py",
                "parse-transport",
                "--kind", "plan",
                "--target", str(plan_path),
                "--raw-result", str(out_log),
                "--out", str(mapped_out),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if parse_res.returncode != 0:
            return [_bridge_failure_finding(
                round_num, lens,
                f"parse-transport returncode={parse_res.returncode}: "
                f"{(parse_res.stderr or parse_res.stdout).strip()[:200]}",
            )]

        if not mapped_out.exists():
            return [_bridge_failure_finding(
                round_num, lens, "mapped result file not written by parse-transport",
            )]
        mapped = json.loads(mapped_out.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired as exc:
        return [_bridge_failure_finding(round_num, lens, f"subprocess timeout: {exc}")]
    except (OSError, json.JSONDecodeError) as exc:
        return [_bridge_failure_finding(round_num, lens, f"mapped result unreadable: {exc}")]
    except Exception as exc:  # noqa: BLE001 — any failure is fail-closed, never []
        return [_bridge_failure_finding(round_num, lens, f"unexpected bridge error: {exc}")]

    # N1: a mapped result whose decision is FAILED must surface as blocking even
    # if it carries no findings array (writer can fail before emitting findings).
    decision = str(mapped.get("gd_review_decision", "")).strip().upper()
    findings = mapped.get("findings", [])
    if decision == "FAILED" and not findings:
        return [_bridge_failure_finding(
            round_num, lens,
            f"mapped gd_review_decision=FAILED with empty findings "
            f"(run_status={mapped.get('run_status')!r})",
        )]
    return findings


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


def _build_loop_report_payload(
    plan_path: Path,
    plan_hash: str,
    decision: str,
    transport_status: str,
    classification: str,
    codex_verdict: str,
    claude_verdict: str,
    merge_reason: str,
    raw_result_path: str | None,
    raw_result_hash: str | None,
    codex_review_status: str,
    review_run_status: str | None = None,
    binding_status: str = "bound",
) -> dict:
    """Construct the loop_report payload (pure function, unit-testable).

    recorded_at is stamped by _write_loop_report_file at write time. Field set
    aligned with the legacy _consume_and_merge report so router._run_live_plan_review
    (:401-413 glob + read) sees identical keys regardless of which path produced
    the loop_report — consumption path OR convergence-loop exit. Includes
    codex_review_status (the precise 4-state verdict, computed by
    _codex_review_status_from_evidence) and review_run_status (raw run state).
    """
    return {
        "schema_version": "2.0",
        "plan_file": str(plan_path),
        "plan_hash": plan_hash,
        "transport_status": transport_status,
        "classification": classification,
        "binding_status": binding_status,
        "raw_result_path": raw_result_path,
        "raw_result_hash": raw_result_hash,
        "claude_verdict": claude_verdict,
        "codex_verdict": codex_verdict,
        "codex_review_status": codex_review_status,
        "review_run_status": review_run_status,
        "gd_review_decision": decision,
        "merge_reason": merge_reason,
    }


def _write_loop_report_file(output_dir: Path, payload: dict) -> Path:
    """Stamp recorded_at, write output_dir/loop_report_{ts}.json, return path.

    Filename 'loop_report_{ts}.json' is what router globs at :401
    ('loop_report_*.json'). Uses a defensive copy so the caller's dict is not
    mutated when recorded_at is stamped.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = dict(payload)
    out["recorded_at"] = ts
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"loop_report_{ts}.json"
    report_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_path


def _latest_codex_evidence(output_dir: Path, last_round: int) -> tuple[Path | None, str, str | None, str | None]:
    """Locate the most recent codex mapped result produced by _run_bridge_job.

    _run_bridge_job writes bridge-r{round}-{lens}-mapped.json (:582) per lens.
    Prefer the primary lens codex_A; fall back to codex_B. Returns
    (path, codex_verdict, review_run_status, evidence_hash):
      - path is non-None whenever a mapped file EXISTS (even if unparseable), so
        'no file' (transport_failed) is distinguished from 'file present but
        unparseable' (wrapper_schema_fail) — aligning convergence with
        _consume_and_merge's classification (:843-885), which was the pre-fix
        divergence flagged in the altitude review.
      - evidence_hash is pre-computed so the caller need not re-read the file.
    Returns (None, 'FAILED', None, None) when no artifact exists for the round.
    """
    saw_malformed: tuple[Path, str] | None = None
    for lens in ("codex_A", "codex_B"):
        candidate = output_dir / f"bridge-r{last_round}-{lens}-mapped.json"
        if candidate.exists():
            raw = candidate.read_bytes()
            h = hashlib.sha256(raw).hexdigest()
            try:
                mapped = json.loads(raw.decode("utf-8"))
                verdict = str(mapped.get("gd_review_decision", "FAILED")).strip().upper()
                run_status = mapped.get("review_run_status")
                return candidate, verdict or "FAILED", run_status, h
            except (UnicodeDecodeError, json.JSONDecodeError):
                # File exists but unparseable. Remember it (path non-None → wrapper_schema_fail
                # downstream) but keep trying the other lens — codex_A and codex_B are
                # independent bridge runs; a corrupt codex_A must not discard a valid codex_B.
                if saw_malformed is None:
                    saw_malformed = (candidate, h)
                continue
    if saw_malformed is not None:
        # A mapped file existed but NO lens parsed → evidence present but unusable.
        # _codex_review_status_from_evidence maps (present, FAILED, None) → wrapper_schema_fail.
        candidate, h = saw_malformed
        return candidate, "FAILED", None, h
    return None, "FAILED", None, None


def _write_convergence_exit_report(
    output_dir: Path,
    plan_path: Path,
    base_decision: str,
    merge_reason: str,
    last_round: int,
    claude_verdict: str,
) -> Path:
    """Aggregate codex evidence into loop_report_{ts}.json at a convergence exit.

    Called from the 4 convergence exits (A/B APPROVED, C/D CONVERGENCE_TIMEOUT)
    BEFORE return/sys.exit, so router :401 glob finds the codex evidence instead
    of N/A. base_decision ∈ {APPROVED (A/B), REQUIRES_CHANGES (C/D)}.

    Conflict arbitration (SC-4): the exit's base decision is constrained by codex
    evidence state. A readable-but-failed codex result (wrapper_schema_fail), a
    constrained result (requires_changes), or a missing result (transport_failed)
    MUST NOT yield APPROVED — fail-closed:
      codex_review_status == transport_failed      → decision FAILED
      codex_review_status in {wrapper_schema_fail,  → decision REQUIRES_CHANGES
                              requires_changes}
      completed                                     → keep base decision
    So an exit that wants APPROVED but finds codex verdict FAILED / degraded /
    REQUIRES_CHANGES never reports 'completed'.

    claude_verdict is recorded for audit only — it does NOT participate in
    arbitration: Claude's findings are already merged into baseline_findings
    earlier in the loop (:1181), so the codex evidence state is the sole
    arbiter at this exit. (Differs from _consume_and_merge, where claude_verdict
    is a separate input that can override — there findings aren't pre-merged.)
    """
    evidence_path, codex_verdict, run_status, evidence_hash = _latest_codex_evidence(output_dir, last_round)
    evidence_present = evidence_path is not None
    codex_review_status = _codex_review_status_from_evidence(evidence_present, codex_verdict, run_status)

    decision = base_decision
    if codex_review_status == "transport_failed":
        decision = "FAILED"
    elif codex_review_status in ("wrapper_schema_fail", "requires_changes"):
        decision = "REQUIRES_CHANGES"

    transport_status = "transport_ok" if evidence_present else "transport_failed"
    # classification = coarse(codex_review_status), consistent with the precise
    # status rather than raw file-readability (which would report transport_ok
    # for a present-but-FAILED result, contradicting codex_review_status).
    classification = "wrapper_schema_fail" if codex_review_status == "wrapper_schema_fail" else transport_status
    raw_result_path = str(evidence_path) if evidence_present else None
    raw_result_hash = evidence_hash  # pre-computed by _latest_codex_evidence (no re-read)
    payload = _build_loop_report_payload(
        plan_path=plan_path,
        plan_hash=_sha256_file(plan_path),
        decision=decision,
        transport_status=transport_status,
        classification=classification,
        codex_verdict=codex_verdict,
        claude_verdict=claude_verdict,
        merge_reason=merge_reason,
        raw_result_path=raw_result_path,
        raw_result_hash=raw_result_hash,
        codex_review_status=codex_review_status,
        review_run_status=run_status,
    )
    return _write_loop_report_file(output_dir, payload)


def _return_from_convergence_exit(report_path: Path) -> int:
    """Return process status from the report decision, not the pre-arbitration branch."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        decision = str(report.get("gd_review_decision", "FAILED")).strip().upper()
    except Exception as exc:
        print(f"CONVERGENCE_REPORT_UNREADABLE: {exc}", flush=True)
        return 1
    print(decision, flush=True)
    return 0 if decision == "APPROVED" else 1


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

    # Derive codex_review_status via the SAME evidence triple as the convergence
    # loop (SC-2/SC-3): consumption path and convergence exit must produce
    # identical codex_review_status semantics. evidence_present = a codex result
    # file existed (transport_ok parsed OR wrapper_schema_fail malformed).
    codex_review_status = _codex_review_status_from_evidence(
        evidence_present=(classification != "transport_failed"),
        codex_verdict=codex_verdict,
        run_status=codex_run_status,
    )
    if codex_review_status == "wrapper_schema_fail":
        classification = "wrapper_schema_fail"
    if merged_decision == "APPROVED":
        if codex_review_status == "transport_failed":
            merged_decision = "FAILED"
            merge_reason = "codex_review_status=transport_failed: cannot approve without codex evidence"
        elif codex_review_status in ("wrapper_schema_fail", "requires_changes"):
            merged_decision = "REQUIRES_CHANGES"
            merge_reason = f"codex_review_status={codex_review_status}: clean approval not allowed"
    payload = _build_loop_report_payload(
        plan_path=plan_path,
        plan_hash=current_plan_hash,
        decision=merged_decision,
        transport_status=transport_status,
        classification=classification,
        codex_verdict=codex_verdict,
        claude_verdict=claude_verdict,
        merge_reason=merge_reason,
        raw_result_path=raw_result_path_str,
        raw_result_hash=str(raw_result_hash) if raw_result_hash else None,
        codex_review_status=codex_review_status,
        review_run_status=codex_run_status,
        binding_status=binding_status,
    )
    report_path = _write_loop_report_file(output_dir, payload)
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

    # Plan 1 (legacy): if pre-computed raw/mapped results are supplied, consume
    # them directly via the existing merge matrix. This path is preserved for
    # back-compat with callers that pre-compute the codex result outside this
    # script (e.g. manual / CI one-shot invocations).
    if codex_raw_result_path is not None or codex_mapped_result_path is not None:
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
    # Without the env var, skip the probe and proceed directly to the live L2 convergence loop.
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

    # -----------------------------------------------------------------------
    # L2 Convergence loop (SC-2 / SC-3 / SC-4)
    # Round 1: dual-codex (codex_A / codex_B, lens differs) + Claude self-review
    #          → merge_findings_union → baseline_findings.json
    # Round 2+: inject REVIEW_ROUND / BASELINE_FINDINGS / DELTA_SCOPE /
    #           SCOPE_CONSTRAINT, dual-codex only, update baseline each round.
    # Hard ceiling: MAX_REVIEW_ROUNDS = 5. Stagnant 2+ rounds → CONVERGENCE_TIMEOUT.
    # -----------------------------------------------------------------------

    output_dir.mkdir(parents=True, exist_ok=True)
    cwd = Path.cwd()
    invocation_id = os.environ.get(INVOCATION_ID_ENV, "direct")

    # --- Round 1: dual-codex + Claude self-review ---
    print(f"=== Round 1 / {MAX_REVIEW_ROUNDS}: dual-codex (codex_A + codex_B) + Claude self-review ===")

    # Build per-lens env blocks. lens_emphasis name must match what bridge reads.
    env_r1_a = {**os.environ, "GD_REVIEW_LENS_EMPHASIS": "codex_A"}
    env_r1_b = {**os.environ, "GD_REVIEW_LENS_EMPHASIS": "codex_B"}

    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_a = executor.submit(_run_bridge_job, plan_path, cwd, output_dir, 1, "codex_A", env_r1_a)
        fut_b = executor.submit(_run_bridge_job, plan_path, cwd, output_dir, 1, "codex_B", env_r1_b)
        findings_codex_a = fut_a.result()
        findings_codex_b = fut_b.result()

    # Claude self-review findings: load from --claude-review if supplied.
    # N8 fail-closed: if a path was supplied but cannot be loaded, do NOT
    # silently treat it as zero findings (that would let a missing/corrupt
    # self-review masquerade as "Claude found nothing"). Abort the loop.
    findings_claude: list[dict] = []
    claude_verdict = "FAILED"
    if claude_review_path is not None:
        cp = Path(claude_review_path)
        if not cp.exists():
            err("CLAUDE_REVIEW_LOAD_FAILED",
                f"--claude-review path does not exist: {claude_review_path}")
            sys.exit(1)
        try:
            cr = json.loads(cp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            err("CLAUDE_REVIEW_LOAD_FAILED",
                f"--claude-review unreadable/invalid JSON ({claude_review_path}): {exc}")
            sys.exit(1)
        findings_claude = cr.get("findings", [])
        claude_verdict = str(cr.get("gd_review_decision", "FAILED")).strip().upper()

    baseline_findings = merge_findings_union(findings_codex_a, findings_codex_b, findings_claude)
    _write_baseline(output_dir, baseline_findings, invocation_id=invocation_id)
    print(
        f"Round 1 baseline: {len(baseline_findings)} findings total, "
        f"{len([f for f in baseline_findings if f.get('status')=='unresolved'])} unresolved"
    )

    # Early exit: no findings at all after round 1.
    if not baseline_findings:
        report_path = _write_convergence_exit_report(
            output_dir, plan_path, "APPROVED",
            merge_reason="round 1: no baseline findings",
            last_round=1, claude_verdict=claude_verdict,
        )
        return _return_from_convergence_exit(report_path)

    # --- Rounds 2–MAX_REVIEW_ROUNDS: SC-3 scope-constrained dual-codex loop ---
    prev_unresolved: int | None = None
    stagnant_rounds = 0
    SCOPE_CONSTRAINT = (
        "Only verify whether baseline findings have been fixed and check delta "
        "for newly introduced issues. Do NOT re-judge baseline findings. "
        "Do NOT re-audit unchanged content outside the delta."
    )

    for round_num in range(2, MAX_REVIEW_ROUNDS + 1):
        # --- Capture delta ---
        diff_text = ""
        delta_lines = 0
        delta_files = 0
        modified_files: set[str] = set()
        try:
            # delta = working-tree diff against HEAD (plan-file version delta).
            # No git history is written; the stash-create tree-ish is not needed
            # because we read the diff text directly.
            diff_result = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
            diff_text = diff_result.stdout[:4000]
            delta_lines = diff_text.count("\n+") + diff_text.count("\n-")
            modified_files = {
                ln[6:]
                for ln in diff_result.stdout.splitlines()
                if ln.startswith("--- a/") or ln.startswith("+++ b/")
            }
            delta_files = len(modified_files)
        except Exception:
            modified_files = set()

        REVIEW_ROUND = round_num
        DELTA_SCOPE = f"{delta_lines} lines changed across {delta_files} files\n--- diff ---\n{diff_text}"
        BASELINE_FINDINGS = json.dumps({"findings": baseline_findings}, ensure_ascii=False)

        print(
            f"=== Round {REVIEW_ROUND} / {MAX_REVIEW_ROUNDS}: "
            f"dual-codex (codex_A + codex_B), delta={delta_lines} lines ===",
            flush=True,
        )

        # Build env for this round (SC-3 four-field injection)
        base_env = {
            **os.environ,
            "GD_REVIEW_ROUND": str(REVIEW_ROUND),
            "GD_BASELINE_FINDINGS": BASELINE_FINDINGS,
            "GD_DELTA_SCOPE": DELTA_SCOPE,
            "GD_SCOPE_CONSTRAINT": SCOPE_CONSTRAINT,
        }
        round_env_a = {**base_env, "GD_REVIEW_LENS_EMPHASIS": "codex_A"}
        round_env_b = {**base_env, "GD_REVIEW_LENS_EMPHASIS": "codex_B"}

        # Every round is dual-codex (FR-004); large-delta upgrade condition removed per spec.
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(
                _run_bridge_job, plan_path, cwd, output_dir, round_num, "codex_A", round_env_a
            )
            fut_b = executor.submit(
                _run_bridge_job, plan_path, cwd, output_dir, round_num, "codex_B", round_env_b
            )
            round_findings_a = fut_a.result()
            round_findings_b = fut_b.result()

        round_findings = round_findings_a + round_findings_b
        baseline_unresolved, new_in_delta = update_baseline_statuses(
            baseline_findings, round_findings, round_num, modified_files
        )

        # --- SC-4 stagnation check ---
        if prev_unresolved is not None:
            if baseline_unresolved >= prev_unresolved:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
        prev_unresolved = baseline_unresolved

        print(
            f"Round {round_num}: baseline_unresolved={baseline_unresolved}, "
            f"new_in_delta={len(new_in_delta)}, stagnant_rounds={stagnant_rounds}",
            flush=True,
        )

        if stagnant_rounds >= 2:
            _write_convergence_exit_report(
                output_dir, plan_path, "REQUIRES_CHANGES",
                merge_reason=f"CONVERGENCE_TIMEOUT: stagnant_rounds={stagnant_rounds}, unresolved={baseline_unresolved}",
                last_round=round_num, claude_verdict=claude_verdict,
            )
            print(
                f"CONVERGENCE_TIMEOUT: stagnant_rounds={stagnant_rounds}, "
                f"unresolved={baseline_unresolved}",
                flush=True,
            )
            sys.exit(1)

        if baseline_unresolved == 0 and len(new_in_delta) == 0:
            report_path = _write_convergence_exit_report(
                output_dir, plan_path, "APPROVED",
                merge_reason=f"round {round_num}: all baseline resolved, no new findings in delta",
                last_round=round_num, claude_verdict=claude_verdict,
            )
            return _return_from_convergence_exit(report_path)

    # Exhausted MAX_REVIEW_ROUNDS without converging
    _write_convergence_exit_report(
        output_dir, plan_path, "REQUIRES_CHANGES",
        merge_reason=f"CONVERGENCE_TIMEOUT: exhausted {MAX_REVIEW_ROUNDS} rounds, unresolved={prev_unresolved}",
        last_round=MAX_REVIEW_ROUNDS, claude_verdict=claude_verdict,
    )
    print(
        f"CONVERGENCE_TIMEOUT: exhausted {MAX_REVIEW_ROUNDS} rounds, "
        f"unresolved={prev_unresolved}",
        flush=True,
    )
    sys.exit(1)


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
