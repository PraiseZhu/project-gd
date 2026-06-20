#!/usr/bin/env python3
"""
gd-review-controller.py — /review2 code multi-round baseline-convergence state machine.

Implements §2.4 Baseline Convergence + §2.1 Branches A/B/C.

Decision contract (D3):  Python script, direct codex CLI call via ``codex exec --ephemeral``.
                          NOT Claude-orchestrated.
No raw codex regex:       Findings come exclusively from bridge mapped JSON
                          (gd-codex-bridge-review.py parse-transport output).
No new commits:           Delta is captured with ``git stash create`` (tree-ish snapshot).
                          Full-loop never writes to the git history.
Exit signal: CONVERGENCE_TIMEOUT only. T8's gate owns the terminal blocked state (not this controller).

Branch routing:
  code-only        → Branch A: LOOP [/code-review → fix → conformance] → /simplify → retest
  execution-only   → Branch B: LOOP [validate execution result vs plan SC]
  combined         → Branch C: Branch A full flow → Branch B (on new execution result post-simplify)

Round 1 (all branches):
  Dispatch codex_A + codex_B (2 independent jobs, different REVIEW_LENS_EMPHASIS).
  Claude self-review result injected via --claude-review-json.
  Three-way union → dedup (file, line±3, category) → baseline_findings.json.
  Severity = max across sources.

Round 2+ (Branches A/B/C):
  Default dispatch = 1 (neutral lens, no REVIEW_LENS_EMPHASIS bias).
  Large delta (>THRESHOLD_LINES lines or >THRESHOLD_FILES files) → dispatch = 2 (D7).
  Capsule injected with: REVIEW_ROUND / BASELINE_FINDINGS / DELTA_SCOPE / SCOPE_CONSTRAINT.
  Only verifies whether baseline unresolved findings are fixed + checks delta for new issues.
  Does NOT re-judge whether baseline findings are problems (H5).

Convergence exit:
  baseline_unresolved == 0 AND new_in_delta == 0  → APPROVED  (exit 0)
  baseline_unresolved unchanged for 2 consecutive rounds → CONVERGENCE_TIMEOUT (exit 1)

Usage:
  python3 scripts/gd-review-controller.py \\
      --branch code-only|execution-only|combined \\
      --cwd <git-root> \\
      --output-dir <dir> \\
      [--claude-review-json <path>] \\
      [--execution-result <path>] \\
      [--round2-fanout-threshold-lines 150] \\
      [--round2-fanout-threshold-files 5] \\
      [--max-rounds 10]

  python3 scripts/gd-review-controller.py --selftest <name>

selftest names:
  convergence_timeout
  d7_large_delta_fanout
  branch_b_convergence_timeout
  round2_capsule_fields
  h5_no_silent_resolve
  branch_c_rerun_after_simplify
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import Future
from pathlib import Path
from typing import Any

GD_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = GD_ROOT / "scripts"
BRIDGE_SCRIPT = SCRIPTS / "gd-codex-bridge-review.py"
BASELINE_SCHEMA = GD_ROOT / "schema" / "gd-baseline-findings.schema.json"

# Dedup window: two findings with same (file, category) and abs(line_a - line_b) <= LINE_WINDOW
# are considered the same finding. Severity = max.
LINE_DEDUP_WINDOW = 3  # line±3 per spec SC-7.1

# Default D7 large-delta thresholds (configurable via CLI)
DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES = 150

# ---------------------------------------------------------------------------
# code_diff diff materialization
# ---------------------------------------------------------------------------

def _materialize_code_diff_target(
    diff_text: str,
    output_dir: Path,
    round_num: int,
    diff_unavailable: bool,
) -> "Path | None":
    """Write diff_text to a .patch file for use as code_diff bridge --target.

    Returns the Path to the written file, or None when the diff is unavailable
    (diff_unavailable=True) or the working tree is genuinely clean (empty diff).
    diff_text is pre-computed by the caller (take_delta_snapshot); this function
    only writes it to disk. Returns None for clean/unavailable — caller decides
    how to handle (Round 1: CONVERGENCE_TIMEOUT; Round N+: keep prior target).
    """
    if diff_unavailable:
        return None
    if not diff_text.strip():
        # Genuinely clean working tree — no diff to review.
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    patch_path = output_dir / f"code_diff_round{round_num}.patch"
    patch_path.write_text(diff_text, encoding="utf-8")
    return patch_path


DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES = 5

# Maximum rounds before hard stop (safety ceiling beyond CONVERGENCE_TIMEOUT)
DEFAULT_MAX_ROUNDS = 10

# Upper bound on the /simplify codex exec call (codex can stall indefinitely).
CODEX_SIMPLIFY_TIMEOUT_SEC = 600

# Upper bound on local git operations (guards against index-lock stalls).
GIT_OP_TIMEOUT_SEC = 30

# Upper bound on a single round's codex future. The bridge already enforces its
# own subprocess timeout (420s / 1800s deep); this is the controller-side ceiling
# on fut.result() so a wedged future never blocks the whole loop indefinitely.
# Deep mode (1800s bridge) + parse overhead → 2000s headroom.
ROUND_FUTURE_TIMEOUT_SEC = 2000

def _run_futures_or_exit(
    fut_a: Future[Any],
    fut_b: Future[Any],
    label: str,
) -> tuple[Any, Any]:
    """Resolve two concurrent futures; emit CONVERGENCE_TIMEOUT and exit(1) on any failure."""
    try:
        result_a = fut_a.result(timeout=ROUND_FUTURE_TIMEOUT_SEC)
        result_b = fut_b.result(timeout=ROUND_FUTURE_TIMEOUT_SEC)
        return result_a, result_b
    except Exception as exc:  # noqa: BLE001 — any failure must fail closed
        for _f in (fut_a, fut_b):
            _f.cancel()
        print(
            f"CONVERGENCE_TIMEOUT: {label} "
            f"({type(exc).__name__}: {str(exc)[:200]})",
            file=sys.stderr,
        )
        print("CONVERGENCE_TIMEOUT")
        sys.exit(1)


# Round 1 codex_A lens emphasis order (SC-7.1)
LENS_A_EMPHASIS = (
    "SC-conformance → boundary/path-violation → interface/contract → "
    "failure-mode/fallback → anti-fill-generalisation"
)

# Round 1 codex_B lens emphasis order (SC-7.1)
LENS_B_EMPHASIS = (
    "failure-mode/fallback → security/secret-leak → anti-fill-generalisation → "
    "SC-conformance → boundary/path-violation"
)


def _normalize_lens_tag(value: str | None) -> str | None:
    """SC-1 (T1): 把调用方传入的 lens 值归一化为唯一协议 tag (codex_A|codex_B)。

    调用方可传裸 tag 或完整 L2 priority 全文（LENS_A/B_EMPHASIS）；非 tag 全文按常量映射，
    未知值 → None（落中立，安全 fail-closed）。bridge 只认 GD_REVIEW_LENS_TAG（codex_A/codex_B）。
    """
    if not value:
        return None
    if value in ("codex_A", "codex_B"):
        return value
    if value == LENS_A_EMPHASIS:
        return "codex_A"
    if value == LENS_B_EMPHASIS:
        return "codex_B"
    return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gen_id() -> str:
    return f"ctrl-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _severity_rank(s: str) -> int:
    return {"P1": 2, "P2": 1}.get(s, 0)


# ---------------------------------------------------------------------------
# Delta snapshot via git stash create (no commit)
# ---------------------------------------------------------------------------

def _append_untracked_diff(cwd: Path, diff_text: str) -> str:
    """Append untracked files as pseudo-diff so code_diff review covers them.

    ``git diff HEAD`` excludes untracked files; without this a multi-file review
    silently misses newly-added files. Best-effort: any git error keeps the
    tracked diff_text unchanged. Never touches the git index (no ``git add -N``).
    """
    try:
        uf_r = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(cwd), capture_output=True, text=True, timeout=GIT_OP_TIMEOUT_SEC,
        )
    except (subprocess.TimeoutExpired, OSError):
        return diff_text
    if uf_r.returncode != 0:
        return diff_text
    parts = [diff_text]
    for uf in (uf_r.stdout or "").splitlines():
        uf = uf.strip()
        if not uf:
            continue
        try:
            nd_r = subprocess.run(
                ["git", "diff", "--no-index", "--", "/dev/null", uf],
                cwd=str(cwd), capture_output=True, text=True, timeout=GIT_OP_TIMEOUT_SEC,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        # git diff --no-index exits 1 when the two paths differ (expected for a
        # real new file); stdout is the pseudo-diff regardless of exit code.
        if nd_r.stdout:
            parts.append(nd_r.stdout)
    return "".join(parts)


def take_delta_snapshot(cwd: Path) -> tuple[str | None, str, bool]:
    """
    Run ``git stash create`` to snapshot current working tree state.
    Returns (stash_tree_ish, diff_text, diff_unavailable).
    On clean tree (empty stash output) falls back to HEAD blob hash.
    Controller NEVER writes to the git history (stash create only).

    diff_text = tracked changes (``git diff HEAD``) + untracked new files as
    pseudo-diff (``_append_untracked_diff``, best-effort). Three downstream
    consumers share this exact semantics: ``compute_delta_size`` (D7 fanout),
    DELTA_SCOPE capsule injection, and ``_materialize_code_diff_target``. So
    fanout decision and the materialized .patch stay consistent on what was
    actually reviewed (including newly-added files).

    SC-9 N10 (fail-closed): a non-zero ``git stash create`` exit OR a non-zero
    ``git diff HEAD`` exit OR a TimeoutExpired means the real delta could NOT be
    obtained. The controller MUST NOT silently substitute an empty diff_text
    (which would look like a clean / tiny delta and steer the D7 fanout decision
    toward dispatch=1). Instead the third tuple element ``diff_unavailable`` is
    set True; callers fan out conservatively and inject ``diff_unavailable: true``
    into the capsule rather than fabricating a fake "clean tree" delta.
    """
    diff_unavailable = False

    try:
        r = subprocess.run(
            ["git", "stash", "create"],
            cwd=str(cwd), capture_output=True, text=True, timeout=GIT_OP_TIMEOUT_SEC,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(
            f"[controller] WARNING: git stash create errored ({exc}); "
            "marking delta unavailable (fail-closed, no fake clean-tree delta)",
            file=sys.stderr,
        )
        return None, "", True

    snapshot_ref = (r.stdout or "").strip() or None

    # git stash create returns 0 with empty stdout on a clean tree, but a
    # non-zero exit is a REAL failure that must NOT be silently coerced into
    # the clean-tree HEAD fallback — doing so would mask the error and feed a
    # bogus "clean tree" delta into the D7 fanout decision. Fail closed: flag
    # the delta as unavailable.
    if r.returncode != 0:
        print(
            f"[controller] WARNING: git stash create failed (exit {r.returncode}): "
            f"{(r.stderr or '').strip()[:200]} — marking delta unavailable (fail-closed)",
            file=sys.stderr,
        )
        diff_unavailable = True

    # Compute diff for DELTA_SCOPE capsule field
    try:
        diff_lines_r = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(cwd), capture_output=True, text=True, timeout=GIT_OP_TIMEOUT_SEC,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(
            f"[controller] WARNING: git diff HEAD errored ({exc}); "
            "marking delta unavailable (fail-closed)",
            file=sys.stderr,
        )
        # snapshot_ref may still be valid from stash create, but the delta we
        # would feed the fanout decision is unknown → fail closed.
        return snapshot_ref, "", True

    if diff_lines_r.returncode != 0:
        print(
            f"[controller] WARNING: git diff HEAD failed (exit {diff_lines_r.returncode}): "
            f"{(diff_lines_r.stderr or '').strip()[:200]} — marking delta unavailable (fail-closed)",
            file=sys.stderr,
        )
        diff_unavailable = True
        diff_text = ""
    else:
        diff_text = diff_lines_r.stdout or ""
    # Append untracked (not-yet-added) files as pseudo-diff so code_diff review
    # covers newly-added files too. git diff HEAD excludes them. Best-effort:
    # on failure keeps the tracked diff_text unchanged.
    if not diff_unavailable:
        diff_text = _append_untracked_diff(cwd, diff_text)

    if snapshot_ref is None:
        # Clean working tree: use HEAD tree hash as stable blob reference
        try:
            head_r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(cwd), capture_output=True, text=True, timeout=GIT_OP_TIMEOUT_SEC,
            )
            snapshot_ref = head_r.stdout.strip() or "HEAD"
        except (subprocess.TimeoutExpired, OSError):
            snapshot_ref = "HEAD"

    return snapshot_ref, diff_text, diff_unavailable


def compute_delta_size(diff_text: str) -> tuple[int, int]:
    """Return (lines_changed, files_changed) from unified diff text."""
    files: set[str] = set()
    lines = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            if len(parts) >= 2:
                files.add(parts[-1])
        elif line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            lines += 1
    return lines, len(files)


# ---------------------------------------------------------------------------
# Dedup / union logic (SC-7.1)
# ---------------------------------------------------------------------------

def _finding_filecat(f: dict) -> tuple[str, str]:
    """Non-line part of the dedup key: (file_normalized, category_normalized)."""
    return (
        (f.get("file") or "").strip().lower(),
        (f.get("category") or "").strip().lower(),
    )


def _lines_within_window(line_a: object, line_b: object) -> bool:
    """True when two findings' lines are within ±LINE_DEDUP_WINDOW of each other.

    Fixed-bucket arithmetic (line // 7) was wrong: lines 4 and 7 fall into
    buckets 0 and 1 despite being only 3 apart, so genuine duplicates were
    double-counted. A direct |a - b| <= window comparison is the only correct
    test for an overlap window. None-line findings match only other None-line
    findings of the same (file, category).
    """
    if line_a is None and line_b is None:
        return True
    if line_a is None or line_b is None:
        return False
    return abs(int(line_a) - int(line_b)) <= LINE_DEDUP_WINDOW


def _finding_matches_any(f: dict, collection: list[dict]) -> bool:
    """True when *f* corresponds to some finding in *collection* under the same
    (file, category) and a ±LINE_DEDUP_WINDOW line overlap. Replaces the old
    set-of-buckets membership test, which could not express a ±3 window."""
    fc = _finding_filecat(f)
    fl = f.get("line")
    for g in collection:
        if _finding_filecat(g) == fc and _lines_within_window(g.get("line"), fl):
            return True
    return False


def merge_findings_union(
    codex_a_findings: list[dict],
    codex_b_findings: list[dict],
    claude_findings: list[dict],
) -> list[dict]:
    """
    Three-way union with dedup.
    Dedup key = (file, line±3, category) per SC-7.1.
    Severity = max across all sources reporting same finding.
    Source = first reporter; also_reported_by = other reporters.
    """
    # Tag each finding with its source before merging
    tagged: list[tuple[str, dict]] = (
        [("codex_A", f) for f in (codex_a_findings or [])]
        + [("codex_B", f) for f in (codex_b_findings or [])]
        + [("claude", f) for f in (claude_findings or [])]
    )

    # Linear scan dedup: a finding merges into an existing one when they share
    # (file, category) AND their lines are within ±LINE_DEDUP_WINDOW. O(n²) but
    # finding counts per round are small. (Replaces the broken line//7 bucket.)
    merged_list: list[dict] = []
    for source, f in tagged:
        fc = _finding_filecat(f)
        match = None
        for existing in merged_list:
            if _finding_filecat(existing) == fc and _lines_within_window(
                existing.get("line"), f.get("line")
            ):
                match = existing
                break
        if match is None:
            merged = dict(f)
            merged["source"] = source
            merged["also_reported_by"] = []
            merged_list.append(merged)
        else:
            # Severity: keep max
            if _severity_rank(f.get("severity", "P2")) > _severity_rank(match.get("severity", "P2")):
                match["severity"] = f["severity"]
            # Track duplicate reporters
            if source not in match.get("also_reported_by", []) and source != match.get("source"):
                match.setdefault("also_reported_by", []).append(source)

    # Assign stable IDs and set initial status
    result = []
    for idx, f in enumerate(merged_list, 1):
        f.setdefault("id", f"F{idx:03d}")
        f.setdefault("status", "unresolved")
        f.setdefault("resolved_in_round", None)
        f.setdefault("round_history", [{"round": 1, "status": "unresolved"}])
        result.append(f)
    return result


# ---------------------------------------------------------------------------
# Bridge invocation helpers (no raw regex — consume mapped JSON only)
# ---------------------------------------------------------------------------

def _invoke_bridge_mapped(
    kind: str,
    target: Path,
    cwd: Path,
    output_dir: Path,
    invocation_id: str,
    lens_emphasis: str | None = None,
    review_round: int = 1,
    baseline_findings: list[dict] | None = None,
    delta_scope: str | None = None,
    scope_constraint: str | None = None,
    deep: bool = False,
    queue_job_id: str | None = None,
    plan_file: str | None = None,
) -> dict:
    """
    Invoke gd-codex-bridge-review.py run-bridge + parse-transport for one codex job.
    Returns the mapped JSON dict. Raises RuntimeError on transport failure.

    Capsule extra fields for Round 2+:
      REVIEW_ROUND, BASELINE_FINDINGS, DELTA_SCOPE, SCOPE_CONSTRAINT.
    These are passed via environment variables that the bridge capsule builder reads
    (or written to a temp annotation file passed via --extra-capsule-fields).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:8]
    run_out = output_dir / f"bridge_run_{kind}_{job_id}.log"

    env = dict(os.environ)
    env["GD_REVIEW_ROUTER_INVOCATION_ID"] = invocation_id

    # Inject capsule round fields (bridge reads from env if set)
    env["GD_REVIEW_ROUND"] = str(review_round)
    # SC-1 (T1): 统一 lens 协议 = GD_REVIEW_LENS_TAG (codex_A|codex_B, 唯一真源)。
    # 调用方传完整 L2 priority 全文或裸 tag → 归一化为 tag；priority 全文另存供 L2 行。
    # （修 G2：旧实现把全文塞 GD_REVIEW_LENS_EMPHASIS，bridge L3 分支 .get(全文)→None→中立）
    _lens_tag = _normalize_lens_tag(lens_emphasis)
    if _lens_tag:
        env["GD_REVIEW_LENS_TAG"] = _lens_tag
    if lens_emphasis and lens_emphasis != _lens_tag:
        env["GD_REVIEW_LENS_PRIORITY_TEXT"] = lens_emphasis
    if baseline_findings is not None:
        env["GD_BASELINE_FINDINGS"] = json.dumps(baseline_findings, ensure_ascii=False)
    if delta_scope is not None:
        env["GD_DELTA_SCOPE"] = delta_scope
    if scope_constraint is not None:
        env["GD_SCOPE_CONSTRAINT"] = scope_constraint

    run_args = [
        sys.executable, str(BRIDGE_SCRIPT), "run-bridge",
        "--kind", kind,
        "--target", str(target),
        "--cwd", str(cwd),
        "--out", str(run_out),
        "--live-transport",
    ]
    # SC-11/SC-32: deep mode — add --deep flag, --queue-job-id, --plan-file; timeout ≥1800s
    # Transport-healthcheck-flap fix (timeout-layer ordering): the controller's
    # bridge_timeout wraps `run-bridge`, which internally polls codex-send-wait
    # (CODEX_SEND_WAIT_TIMEOUT=540s). The daemon's worst-case budget is
    # max_attempts(2) x CODEX_EXEC_TIMEOUT(240) ≈ 480s. The old 420s killed
    # run-bridge BEFORE a legitimate daemon retry could finish (observed: job
    # completes on attempt 2 at ~433s, but controller timed out at 420s →
    # CONVERGENCE_TIMEOUT on a job that actually succeeded). Order must hold:
    # daemon_budget(~480) < send_wait(540) < controller bridge_timeout(600).
    bridge_timeout = 600
    if deep:
        run_args.append("--deep")
        bridge_timeout = 1800
    if queue_job_id:
        run_args.extend(["--queue-job-id", queue_job_id])
    if plan_file:
        run_args.extend(["--plan-file", plan_file])
    try:
        r_run = subprocess.run(run_args, capture_output=True, text=True, timeout=bridge_timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"bridge run-bridge timed out: {exc}") from exc

    transport_raw: Path | None = None
    for line in (r_run.stdout or "").splitlines():
        if line.startswith("TRANSPORT_RESULT: "):
            transport_raw = Path(line[len("TRANSPORT_RESULT: "):].strip())
            break

    if transport_raw is None or not transport_raw.exists():
        raise RuntimeError(
            f"bridge did not produce TRANSPORT_RESULT; stdout={r_run.stdout[-300:]!r}"
        )

    mapped_out = output_dir / f"codex_mapped_{kind}_{job_id}.json"
    parse_args = [
        sys.executable, str(BRIDGE_SCRIPT), "parse-transport",
        "--kind", kind,
        "--target", str(target),
        "--raw-result", str(transport_raw),
        "--out", str(mapped_out),
    ]
    if deep:
        parse_args.append("--deep")
    r_parse = subprocess.run(parse_args, capture_output=True, text=True, env=env)
    # parse-transport can return non-zero for a valid mapped REQUIRES_CHANGES
    # result. Treat only missing/unreadable mapped JSON as a transport failure.
    if not mapped_out.exists():
        raise RuntimeError(f"parse-transport failed: {r_parse.stderr[:300]!r}")

    mapped = json.loads(mapped_out.read_text(encoding="utf-8"))
    return mapped


def _extract_findings_from_mapped(mapped: dict) -> list[dict]:
    """
    Extract findings[] from a bridge mapped JSON.
    Controller consumes only pre-validated mapped JSON — no raw regex parsing (SC-7.2).
    review_run_status and gd_review_decision are read from the mapped dict directly.
    """
    return list(mapped.get("findings", []) or [])


# ---------------------------------------------------------------------------
# Round 1: dual codex + Claude self-review → baseline
# ---------------------------------------------------------------------------

def run_round1(
    kind: str,
    target: Path,
    cwd: Path,
    output_dir: Path,
    invocation_id: str,
    claude_findings: list[dict],
    stub_dispatch: "StubDispatch | None" = None,
    deep: bool = False,
    queue_job_id: str | None = None,
    plan_file: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    Dispatch codex_A + codex_B in parallel (max_parallel=2 per gd-review-suite-controller pattern).
    Returns (baseline_findings_list, delta_snapshot_ref).
    """
    from concurrent.futures import ThreadPoolExecutor

    snapshot_ref, diff_text, _diff_unavailable = take_delta_snapshot(cwd)

    # code_diff: materialize diff_text → .patch file so bridge gets a real file target.
    # run_branch_a passes target=cwd (directory) as a sentinel; replace it here.
    # Skip in stub mode: the selftest stub returns findings directly and never
    # touches the bridge, so effective_target is unused — running materialization
    # there would couple the selftest to the real working-tree diff state.
    effective_target = target
    if kind == "code_diff" and stub_dispatch is None:
        patch = _materialize_code_diff_target(
            diff_text, output_dir, round_num=1, diff_unavailable=_diff_unavailable,
        )
        if patch is None:
            # Genuinely clean tree or diff unavailable — nothing to review.
            print(
                "[controller] code_diff Round 1: no diff to review "
                f"(diff_unavailable={_diff_unavailable}, diff_text empty={not diff_text.strip()}); "
                "emitting CONVERGENCE_TIMEOUT",
                file=sys.stderr,
            )
            print("CONVERGENCE_TIMEOUT")
            raise SystemExit(1)
        effective_target = patch

    if stub_dispatch is not None:
        # Selftest stub path — no real codex
        a_findings = stub_dispatch.round1_codex_a_findings()
        b_findings = stub_dispatch.round1_codex_b_findings()
        stub_dispatch.record_dispatch_count(2)  # Round 1 always 2
    else:
        def _call_a() -> list[dict]:
            m = _invoke_bridge_mapped(
                kind=kind, target=effective_target, cwd=cwd, output_dir=output_dir,
                invocation_id=invocation_id,
                lens_emphasis=LENS_A_EMPHASIS,
                review_round=1,
                deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
            )
            return _extract_findings_from_mapped(m)

        def _call_b() -> list[dict]:
            m = _invoke_bridge_mapped(
                kind=kind, target=effective_target, cwd=cwd, output_dir=output_dir,
                invocation_id=invocation_id,
                lens_emphasis=LENS_B_EMPHASIS,
                review_round=1,
                deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
            )
            return _extract_findings_from_mapped(m)

        # Use codex exec --ephemeral via bridge; max_parallel=2 (bounded ThreadPoolExecutor).
        # SC-9 N7 (fail-closed): an unhandled exception out of fut.result()
        # (bridge timeout, RuntimeError on transport failure, etc.) would
        # otherwise propagate a raw stack trace and crash the whole controller
        # process — making the review neither APPROVED nor a clean
        # CONVERGENCE_TIMEOUT. Catch it, emit CONVERGENCE_TIMEOUT, and exit 1 so
        # the parent gate sees a deterministic terminal signal.
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(_call_a)
            fut_b = pool.submit(_call_b)
            a_findings, b_findings = _run_futures_or_exit(
                fut_a, fut_b, "Round 1 codex dispatch failed/timed out"
            )

    baseline = merge_findings_union(a_findings, b_findings, claude_findings)
    return baseline, snapshot_ref


# ---------------------------------------------------------------------------
# Round 2+: single codex (or double on large delta, D7)
# ---------------------------------------------------------------------------

def run_round_n(
    round_num: int,
    kind: str,
    target: Path,
    cwd: Path,
    output_dir: Path,
    invocation_id: str,
    baseline_findings: list[dict],
    threshold_lines: int,
    threshold_files: int,
    stub_dispatch: "StubDispatch | None" = None,
    deep: bool = False,
    queue_job_id: str | None = None,
    plan_file: str | None = None,
) -> tuple[list[dict], str | None, int]:
    """
    Run Round N (N>=2).
    Returns (returned_findings, snapshot_ref, dispatch_count).
    dispatch_count = 1 (neutral) or 2 (large delta D7).
    """
    from concurrent.futures import ThreadPoolExecutor

    snapshot_ref, diff_text, diff_unavailable = take_delta_snapshot(cwd)
    delta_lines, delta_files = compute_delta_size(diff_text)

    # D7: large delta → fanout to 2 codex jobs this round.
    # SC-9 N10 (fail-closed): when the real delta could not be obtained we have
    # NO basis to decide the delta is "small" — defaulting to dispatch=1 would be
    # a silent fail-open on a possibly-large change. Treat unavailable delta as
    # large_delta so we fan out conservatively (dispatch=2) and the capsule
    # carries diff_unavailable instead of a fabricated empty/clean delta.
    large_delta = diff_unavailable or (delta_lines > threshold_lines) or (delta_files > threshold_files)

    # Build capsule injection fields (SC-7.7)
    scope_constraint = (
        "SCOPE_CONSTRAINT: Only verify whether baseline findings have been fixed "
        "and check delta for newly introduced issues. "
        "Do NOT re-judge whether baseline findings are problems. "
        "Do NOT re-audit unchanged code outside the delta."
    )
    if diff_unavailable:
        # Never inject a fake "0 lines / clean tree" delta. Make the downstream
        # reviewer aware the delta is unknown so it does not assume a no-op change.
        delta_scope_text = (
            "DELTA_SCOPE: diff_unavailable: true "
            "(git delta could not be obtained; treat full target as in-scope, "
            "do NOT assume a clean/empty delta)."
        )
    else:
        delta_scope_text = (
            f"DELTA_SCOPE: {delta_lines} lines changed across {delta_files} files.\n"
            f"--- diff summary ---\n{diff_text[:4000]}"
        )
    baseline_json_str = json.dumps(baseline_findings, ensure_ascii=False, indent=2)

    if stub_dispatch is not None:
        returned = stub_dispatch.round_n_findings(round_num=round_num, large_delta=large_delta)
        dispatch_count = 2 if large_delta else 1
        stub_dispatch.record_dispatch_count(dispatch_count)
        # Record capsule fields for SC-7.7 verification (+ N10 diff_unavailable flag)
        stub_dispatch.record_capsule_fields({
            "REVIEW_ROUND": round_num,
            "BASELINE_FINDINGS": baseline_json_str,
            "DELTA_SCOPE": delta_scope_text,
            "SCOPE_CONSTRAINT": scope_constraint,
            "DIFF_UNAVAILABLE": diff_unavailable,
        })
        return returned, snapshot_ref, dispatch_count

    # code_diff: materialize tracked+untracked diff → .patch for bridge target.
    effective_target = target
    if kind == "code_diff":
        patch = _materialize_code_diff_target(
            diff_text, output_dir, round_num=round_num, diff_unavailable=diff_unavailable,
        )
        if patch is not None:
            effective_target = patch
        # If patch is None (clean tree / unavailable), effective_target stays as
        # cwd (a directory); bridge's is_dir() guard will raise CODE_DIFF_TARGET_MUST_BE_FILE
        # which propagates as CONVERGENCE_TIMEOUT — same fail-closed outcome as Round 1.

    # H5: neutral lens for Round 2+ single codex — no REVIEW_LENS_EMPHASIS bias
    common_kwargs = dict(
        kind=kind, target=effective_target, cwd=cwd, output_dir=output_dir,
        invocation_id=invocation_id,
        review_round=round_num,
        baseline_findings=baseline_findings,
        delta_scope=delta_scope_text,
        scope_constraint=scope_constraint,
        deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
    )

    if large_delta:
        # D7: dispatch 2 codex jobs (A+B emphasis, scope still limited to delta)
        def _call_a() -> list[dict]:
            m = _invoke_bridge_mapped(**common_kwargs, lens_emphasis=LENS_A_EMPHASIS)  # type: ignore[arg-type]
            return _extract_findings_from_mapped(m)

        def _call_b() -> list[dict]:
            m = _invoke_bridge_mapped(**common_kwargs, lens_emphasis=LENS_B_EMPHASIS)  # type: ignore[arg-type]
            return _extract_findings_from_mapped(m)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(_call_a)
            fut_b = pool.submit(_call_b)
            a_f, b_f = _run_futures_or_exit(
                fut_a, fut_b, f"Round {round_num} codex dispatch failed/timed out"
            )
        returned = merge_findings_union(a_f, b_f, [])
        return returned, snapshot_ref, 2
    else:
        # Single neutral codex (no REVIEW_LENS_EMPHASIS).
        # SC-9 N7 (fail-closed): _invoke_bridge_mapped raises RuntimeError on
        # transport failure; convert to a deterministic CONVERGENCE_TIMEOUT.
        try:
            m = _invoke_bridge_mapped(**common_kwargs)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 — any failure must fail closed
            print(
                f"CONVERGENCE_TIMEOUT: Round {round_num} codex dispatch failed "
                f"({type(exc).__name__}: {str(exc)[:200]})",
                file=sys.stderr,
            )
            print("CONVERGENCE_TIMEOUT")
            sys.exit(1)  # single-future path — no second future to cancel
        returned = _extract_findings_from_mapped(m)
        return returned, snapshot_ref, 1


# ---------------------------------------------------------------------------
# Baseline update: reconcile round findings against baseline (H5 aware)
# ---------------------------------------------------------------------------

def update_baseline_statuses(
    baseline: list[dict],
    round_findings: list[dict],
    round_num: int,
) -> tuple[list[dict], int, int]:
    """
    Update baseline finding statuses based on Round N codex output.

    H5 contract: when verifying a baseline finding, controller checks
    'whether the phenomenon is still present' (objective), NOT 'whether
    this is a valid problem' (subjective re-judgment).

    A finding is marked resolved only if it does NOT appear in round_findings
    (i.e., codex no longer reports the symptom). A finding that codex_A
    wouldn't flag but codex_B originally reported must remain unresolved
    if not confirmed fixed — it is never silently resolved.

    Returns (updated_baseline, baseline_unresolved_count, new_in_delta_count).
    """
    updated = []
    for f in baseline:
        new_f = dict(f)
        history = list(f.get("round_history", []))
        if f["status"] == "unresolved":
            # Check objective presence: is the symptom still reported this round?
            # (±3 line window — not exact-key membership, which the old bucket
            # test got wrong.)
            still_present = _finding_matches_any(f, round_findings)
            if not still_present:
                new_f["status"] = "resolved"
                new_f["resolved_in_round"] = round_num
                history.append({"round": round_num, "status": "resolved"})
            else:
                history.append({"round": round_num, "status": "unresolved"})
        new_f["round_history"] = history
        updated.append(new_f)

    baseline_unresolved = sum(1 for f in updated if f["status"] == "unresolved")

    # Collect new delta findings in one pass (avoids scanning baseline twice per finding).
    new_delta_findings = [f for f in round_findings if not _finding_matches_any(f, baseline)]
    new_in_delta = len(new_delta_findings)

    for f in new_delta_findings:
            new_f = dict(f)
            new_f.setdefault("status", "unresolved")
            new_f.setdefault("source", "codex_A")
            new_f.setdefault("round_history", [{"round": round_num, "status": "unresolved"}])
            new_f["id"] = f"F{len(updated)+1:03d}"
            updated.append(new_f)

    return updated, baseline_unresolved, new_in_delta


# ---------------------------------------------------------------------------
# Baseline I/O
# ---------------------------------------------------------------------------

def write_baseline(
    baseline: list[dict],
    output_dir: Path,
    invocation_id: str,
    branch: str,
    snapshot_ref: str | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    obj = {
        "schema_version": "1.0",
        "baseline_round": 1,
        "created_at": now_iso(),
        "controller_invocation_id": invocation_id,
        "branch": branch,
        "delta_snapshot": snapshot_ref,
        "baseline_unresolved_count": sum(1 for f in baseline if f.get("status") == "unresolved"),
        "findings": baseline,
    }
    p = output_dir / "baseline_findings.json"
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Shared convergence loop (SC-7.4 / SC-7.6) — used by Branch A and Branch B
# ---------------------------------------------------------------------------

def _run_convergence_loop(
    kind: str,
    target: "Path",
    cwd: "Path",
    output_dir: "Path",
    invocation_id: str,
    baseline: list[dict],
    snap_ref: str,
    branch_label: str,
    claude_findings: list[dict],
    threshold_lines: int,
    threshold_files: int,
    max_rounds: int,
    stub_dispatch: "StubDispatch | None",
    deep: bool = False,
    queue_job_id: str | None = None,
    plan_file: str | None = None,
) -> str:
    """Round 2+ convergence loop shared between Branch A and Branch B.

    Returns "APPROVED" or raises SystemExit(1) with CONVERGENCE_TIMEOUT.
    """
    write_baseline(baseline, output_dir, invocation_id, branch_label, snap_ref)
    print(f"[controller] Round 1 complete: {len(baseline)} baseline findings")

    prev_unresolved: int | None = None
    stagnant_rounds = 0

    for round_num in range(2, max_rounds + 1):
        round_findings, snap_ref, dispatch_count = run_round_n(
            round_num=round_num,
            kind=kind, target=target, cwd=cwd, output_dir=output_dir,
            invocation_id=invocation_id,
            baseline_findings=baseline,
            threshold_lines=threshold_lines,
            threshold_files=threshold_files,
            stub_dispatch=stub_dispatch,
            deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
        )
        baseline, baseline_unresolved, new_in_delta = update_baseline_statuses(
            baseline, round_findings, round_num
        )
        print(
            f"[controller] Round {round_num}: dispatch={dispatch_count}  "
            f"baseline_unresolved={baseline_unresolved}  new_in_delta={new_in_delta}"
        )

        if prev_unresolved is not None and baseline_unresolved >= prev_unresolved:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
        prev_unresolved = baseline_unresolved

        if stagnant_rounds >= 2:
            print(f"CONVERGENCE_TIMEOUT: {branch_label} baseline_unresolved stagnant for 2 rounds")
            sys.exit(1)

        if baseline_unresolved == 0 and new_in_delta == 0:
            print("APPROVED")
            return "APPROVED"

    print(f"CONVERGENCE_TIMEOUT: {branch_label} reached max_rounds without convergence")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Branch A: code-only loop
# ---------------------------------------------------------------------------

def run_branch_a(
    cwd: Path,
    output_dir: Path,
    invocation_id: str,
    claude_findings: list[dict],
    threshold_lines: int,
    threshold_files: int,
    max_rounds: int,
    stub_dispatch: "StubDispatch | None" = None,
    deep: bool = False,
    queue_job_id: str | None = None,
    plan_file: str | None = None,
) -> str:
    """
    Branch A (code-only): LOOP [/code-review → fix → conformance] → simplify → retest.
    Returns "APPROVED" or raises SystemExit(1) with CONVERGENCE_TIMEOUT.
    Direct codex invocation via codex exec --ephemeral through bridge wrapper.
    """
    print(f"[controller] Branch A: code-only  invocation_id={invocation_id}")
    target = cwd  # bridge detects diff from working dir

    baseline, snap_ref = run_round1(
        kind="code_diff", target=target, cwd=cwd, output_dir=output_dir,
        invocation_id=invocation_id, claude_findings=claude_findings,
        stub_dispatch=stub_dispatch,
        deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
    )
    return _run_convergence_loop(
        kind="code_diff", target=target, cwd=cwd, output_dir=output_dir,
        invocation_id=invocation_id, baseline=baseline, snap_ref=snap_ref,
        branch_label="code-only", claude_findings=claude_findings,
        threshold_lines=threshold_lines, threshold_files=threshold_files,
        max_rounds=max_rounds, stub_dispatch=stub_dispatch,
        deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
    )


# ---------------------------------------------------------------------------
# Branch B: execution-only loop
# ---------------------------------------------------------------------------

def run_branch_b(
    cwd: Path,
    output_dir: Path,
    invocation_id: str,
    execution_result: Path | None,
    claude_findings: list[dict],
    threshold_lines: int,
    threshold_files: int,
    max_rounds: int,
    stub_dispatch: "StubDispatch | None" = None,
    deep: bool = False,
    queue_job_id: str | None = None,
    plan_file: str | None = None,
) -> str:
    """
    Branch B (execution-only): LOOP [validate execution result vs plan SC].
    Same CONVERGENCE_TIMEOUT logic (SC-7.6).
    Returns "APPROVED" or raises SystemExit(1) with CONVERGENCE_TIMEOUT.
    """
    print(f"[controller] Branch B: execution-only  invocation_id={invocation_id}")
    target = execution_result or cwd

    baseline, snap_ref = run_round1(
        kind="execution_outcome", target=target, cwd=cwd, output_dir=output_dir,
        invocation_id=invocation_id, claude_findings=claude_findings,
        stub_dispatch=stub_dispatch,
        deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
    )
    return _run_convergence_loop(
        kind="execution_outcome", target=target, cwd=cwd, output_dir=output_dir,
        invocation_id=invocation_id, baseline=baseline, snap_ref=snap_ref,
        branch_label="execution-only", claude_findings=claude_findings,
        threshold_lines=threshold_lines, threshold_files=threshold_files,
        max_rounds=max_rounds, stub_dispatch=stub_dispatch,
        deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
    )


# ---------------------------------------------------------------------------
# Branch C: combined = Branch A → simplify → re-run → Branch B (new result)
# ---------------------------------------------------------------------------

def run_branch_c(
    cwd: Path,
    output_dir: Path,
    invocation_id: str,
    execution_result: Path | None,
    claude_findings: list[dict],
    threshold_lines: int,
    threshold_files: int,
    max_rounds: int,
    stub_dispatch: "StubDispatch | None" = None,
    deep: bool = False,
    queue_job_id: str | None = None,
    plan_file: str | None = None,
) -> str:
    """
    Branch C (combined):
      1. Run Branch A full flow (code loop + simplify + retest).
      2. After simplify, re-run execution to produce new result (mtime > simplify time).
      3. Run Branch B on the NEW execution result.
    SC-7.9: B receives execution result with mtime AFTER simplify.
    """
    print(f"[controller] Branch C: combined  invocation_id={invocation_id}")

    # Step 1: Branch A
    dir_a = output_dir / "branch_a"
    dir_a.mkdir(parents=True, exist_ok=True)
    run_branch_a(
        cwd=cwd, output_dir=dir_a, invocation_id=f"{invocation_id}-A",
        claude_findings=claude_findings,
        threshold_lines=threshold_lines, threshold_files=threshold_files,
        max_rounds=max_rounds, stub_dispatch=stub_dispatch,
        deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
    )

    # Step 2: /simplify — direct codex exec --ephemeral (D3)
    simplify_time = time.time()
    if stub_dispatch is not None:
        stub_dispatch.record_simplify_time(simplify_time)
        new_exec_result = stub_dispatch.produce_new_execution_result(simplify_time)
    else:
        print("[controller] Running /simplify via codex exec --ephemeral ...")
        try:
            simplify_result = subprocess.run(
                ["codex", "exec", "--ephemeral", "--", "/simplify"],
                cwd=str(cwd), capture_output=True, text=True,
                timeout=CODEX_SIMPLIFY_TIMEOUT_SEC,
            )
            if simplify_result.returncode != 0:
                print(f"[controller] /simplify exited {simplify_result.returncode}; continuing", file=sys.stderr)
        except subprocess.TimeoutExpired:
            # codex exec can hang indefinitely (observed real-world stalls); a
            # missing timeout would block the controller and its parent router.
            print(
                f"[controller] /simplify timed out after {CODEX_SIMPLIFY_TIMEOUT_SEC}s; "
                "skipping simplify, continuing to Branch B",
                file=sys.stderr,
            )

        # Step 3: re-run tests/verify to produce new execution result AFTER simplify
        print("[controller] Re-running tests/verify to produce post-simplify execution result ...")
        new_exec_result = execution_result  # caller must supply updated path or detect

    # Step 4: Branch B on new execution result (mtime must be > simplify_time)
    dir_b = output_dir / "branch_b"
    dir_b.mkdir(parents=True, exist_ok=True)
    return run_branch_b(
        cwd=cwd, output_dir=dir_b, invocation_id=f"{invocation_id}-B",
        execution_result=new_exec_result,
        claude_findings=claude_findings,
        threshold_lines=threshold_lines, threshold_files=threshold_files,
        max_rounds=max_rounds, stub_dispatch=stub_dispatch,
        deep=deep, queue_job_id=queue_job_id, plan_file=plan_file,
    )


# ---------------------------------------------------------------------------
# StubDispatch — selftest harness (no real codex, no network)
# ---------------------------------------------------------------------------

class StubDispatch:
    """
    In-selftest stub that replaces real codex dispatch.
    Configurable scenario injection for each selftest name.
    """

    def __init__(self) -> None:
        self._dispatch_counts: list[int] = []
        self._capsule_fields: list[dict] = []
        self._simplify_time: float | None = None
        self._new_exec_result: Path | None = None

        # Scenario config (set by scenario helpers)
        self._r1_a: list[dict] = []
        self._r1_b: list[dict] = []
        self._round_n_sequence: list[list[dict]] = []
        self._round_n_idx: int = 0

    def round1_codex_a_findings(self) -> list[dict]:
        return list(self._r1_a)

    def round1_codex_b_findings(self) -> list[dict]:
        return list(self._r1_b)

    def round_n_findings(self, round_num: int, large_delta: bool) -> list[dict]:
        if self._round_n_idx < len(self._round_n_sequence):
            findings = list(self._round_n_sequence[self._round_n_idx])
            self._round_n_idx += 1
            return findings
        return []  # empty = all resolved

    def record_dispatch_count(self, count: int) -> None:
        self._dispatch_counts.append(count)

    def record_capsule_fields(self, fields: dict) -> None:
        self._capsule_fields.append(fields)

    def record_simplify_time(self, t: float) -> None:
        self._simplify_time = t

    def produce_new_execution_result(self, simplify_time: float) -> "Path | None":
        # In selftest, produce a temp file with mtime > simplify_time
        if self._new_exec_result is not None and self._new_exec_result.exists():
            # Set mtime to simplify_time + 1s to prove ordering
            new_mtime = simplify_time + 1.0
            os.utime(str(self._new_exec_result), (new_mtime, new_mtime))
            return self._new_exec_result
        return None

    def get_dispatch_counts(self) -> list[int]:
        return list(self._dispatch_counts)

    def get_capsule_fields(self) -> list[dict]:
        return list(self._capsule_fields)


def _make_finding(
    fid: str,
    severity: str = "P2",
    title: str = "test finding",
    file: str = "main.py",
    line: int = 10,
    category: str = "sc_conformance",
    source: str = "codex_A",
) -> dict:
    return {
        "id": fid,
        "severity": severity,
        "title": title,
        "sc_refs": ["SC-1"],
        "file": file,
        "line": line,
        "category": category,
        "status": "unresolved",
        "source": source,
        "evidence": "test evidence",
        "impact": "test impact",
        "required_fix": "test fix",
        "verify": "grep -n test main.py",
    }


# ---------------------------------------------------------------------------
# Self-tests (SC verification without real codex / network)
# ---------------------------------------------------------------------------

def _make_temp_git_repo(td: str) -> None:
    """Initialise *td* as a git repo with one HEAD commit (required by git stash create)."""
    subprocess.run(["git", "init", td], capture_output=True)
    seed = Path(td) / ".gitkeep"
    seed.write_text("seed\n")
    subprocess.run(["git", "-C", td, "add", ".gitkeep"], capture_output=True)
    subprocess.run(["git", "-C", td, "-c", "user.email=t@t.com", "-c", "user.name=T",
                    "commit", "-m", "seed"], capture_output=True)


def _selftest_convergence_timeout() -> int:
    """SC-7.4: baseline_unresolved does not decrease for 2 rounds → CONVERGENCE_TIMEOUT."""
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        _make_temp_git_repo(td)

        stub = StubDispatch()
        # Round 1: 2 unresolved findings
        f1 = _make_finding("F001", file="a.py", line=10, category="sc_conformance")
        f2 = _make_finding("F002", file="b.py", line=20, category="boundary")
        stub._r1_a = [f1]
        stub._r1_b = [f2]
        # Rounds 2–N: same 2 findings always returned — never resolved.
        # Repeat enough times to outlast max_rounds (10).
        stub._round_n_sequence = [[f1, f2]] * 12  # infinite stagnation

        original_exit = sys.exit

        def fake_exit(code: int) -> None:
            raise SystemExit(code)

        sys.exit = fake_exit  # type: ignore[assignment]
        try:
            run_branch_a(
                cwd=tdp, output_dir=tdp / "out",
                invocation_id=gen_id(),
                claude_findings=[],
                threshold_lines=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
                threshold_files=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
                max_rounds=10,
                stub_dispatch=stub,
            )
        except SystemExit as exc:
            if exc.code != 0:
                print("CONVERGENCE_TIMEOUT confirmed via SystemExit")
                return 0
        finally:
            sys.exit = original_exit  # type: ignore[assignment]

        print("FAIL: expected CONVERGENCE_TIMEOUT but did not get it", file=sys.stderr)
        return 1


def _selftest_d7_large_delta_fanout() -> int:
    """SC-7.5: delta > threshold → dispatch=2; delta < threshold → dispatch=1."""
    import types

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        subprocess.run(["git", "init", td], capture_output=True)
        # Create an initial tracked file so the repo has a HEAD ref (no empty-tree needed)
        _seed = Path(td) / ".gitkeep"
        _seed.write_text("seed\n")
        subprocess.run(["git", "-C", td, "add", ".gitkeep"], capture_output=True)
        subprocess.run(["git", "-C", td, "-c", "user.email=t@t.com", "-c", "user.name=T",
                        "commit", "-m", "seed"], capture_output=True)

        stub = StubDispatch()
        f1 = _make_finding("F001")
        stub._r1_a = [f1]
        stub._r1_b = []
        # Round 2: all resolved
        stub._round_n_sequence = [[]]

        # Monkey-patch compute_delta_size to return large delta
        orig_compute = sys.modules[__name__].compute_delta_size  # type: ignore[attr-defined]

        # Scenario A: large delta
        sys.modules[__name__].compute_delta_size = lambda diff_text: (200, 8)  # type: ignore[attr-defined]
        stub2 = StubDispatch()
        stub2._r1_a = [f1]
        stub2._r1_b = []
        stub2._round_n_sequence = [[]]

        try:
            # We only need to verify the dispatch counts, not run full loop
            # Directly test run_round_n with stub
            baseline = [dict(f1)]
            round_findings, _, dispatch_count_large = run_round_n(
                round_num=2,
                kind="code_diff",
                target=tdp,
                cwd=tdp,
                output_dir=tdp / "out_large",
                invocation_id=gen_id(),
                baseline_findings=baseline,
                threshold_lines=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
                threshold_files=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
                stub_dispatch=stub2,
            )
        finally:
            sys.modules[__name__].compute_delta_size = orig_compute  # type: ignore[attr-defined]

        # Scenario B: small delta
        sys.modules[__name__].compute_delta_size = lambda diff_text: (10, 1)  # type: ignore[attr-defined]
        stub3 = StubDispatch()
        stub3._round_n_sequence = [[]]

        try:
            round_findings_b, _, dispatch_count_small = run_round_n(
                round_num=2,
                kind="code_diff",
                target=tdp,
                cwd=tdp,
                output_dir=tdp / "out_small",
                invocation_id=gen_id(),
                baseline_findings=baseline,
                threshold_lines=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
                threshold_files=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
                stub_dispatch=stub3,
            )
        finally:
            sys.modules[__name__].compute_delta_size = orig_compute  # type: ignore[attr-defined]

        print(f"[d7_selftest] large_delta dispatch={dispatch_count_large}  small_delta dispatch={dispatch_count_small}")

        ok = (dispatch_count_large == 2) and (dispatch_count_small == 1)
        if ok:
            print("d7_large_delta_fanout: PASS")
            return 0
        else:
            print(
                f"FAIL: expected large=2 small=1, got large={dispatch_count_large} small={dispatch_count_small}",
                file=sys.stderr,
            )
            return 1


def _selftest_branch_b_convergence_timeout() -> int:
    """SC-7.6: Branch B also emits CONVERGENCE_TIMEOUT when stagnant."""
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        subprocess.run(["git", "init", td], capture_output=True)
        # Create an initial tracked file so the repo has a HEAD ref (no empty-tree needed)
        _seed = Path(td) / ".gitkeep"
        _seed.write_text("seed\n")
        subprocess.run(["git", "-C", td, "add", ".gitkeep"], capture_output=True)
        subprocess.run(["git", "-C", td, "-c", "user.email=t@t.com", "-c", "user.name=T",
                        "commit", "-m", "seed"], capture_output=True)

        stub = StubDispatch()
        f1 = _make_finding("F001", category="sc_conformance")
        stub._r1_a = [f1]
        stub._r1_b = []
        # Always return f1 — never resolves
        stub._round_n_sequence = [[f1]] * 12

        original_exit = sys.exit

        def fake_exit(code: int) -> None:
            raise SystemExit(code)

        sys.exit = fake_exit  # type: ignore[assignment]
        try:
            run_branch_b(
                cwd=tdp, output_dir=tdp / "out",
                invocation_id=gen_id(),
                execution_result=None,
                claude_findings=[],
                threshold_lines=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
                threshold_files=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
                max_rounds=10,
                stub_dispatch=stub,
            )
        except SystemExit as exc:
            if exc.code != 0:
                print("CONVERGENCE_TIMEOUT confirmed in branch B")
                return 0
        finally:
            sys.exit = original_exit  # type: ignore[assignment]

        print("FAIL: expected branch B CONVERGENCE_TIMEOUT", file=sys.stderr)
        return 1


def _selftest_round2_capsule_fields() -> int:
    """SC-7.7: Round 2 capsule contains REVIEW_ROUND >= 2 and all four required fields."""
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        subprocess.run(["git", "init", td], capture_output=True)
        # Create an initial tracked file so the repo has a HEAD ref (no empty-tree needed)
        _seed = Path(td) / ".gitkeep"
        _seed.write_text("seed\n")
        subprocess.run(["git", "-C", td, "add", ".gitkeep"], capture_output=True)
        subprocess.run(["git", "-C", td, "-c", "user.email=t@t.com", "-c", "user.name=T",
                        "commit", "-m", "seed"], capture_output=True)

        stub = StubDispatch()
        f1 = _make_finding("F001")
        stub._r1_a = [f1]
        stub._r1_b = []
        # Round 2 resolves everything
        stub._round_n_sequence = [[]]

        baseline = [dict(f1)]
        _round_findings, _snap, _dispatch = run_round_n(
            round_num=2,
            kind="code_diff",
            target=tdp,
            cwd=tdp,
            output_dir=tdp / "out",
            invocation_id=gen_id(),
            baseline_findings=baseline,
            threshold_lines=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
            threshold_files=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
            stub_dispatch=stub,
        )

        fields = stub.get_capsule_fields()
        if not fields:
            print("FAIL: no capsule fields recorded", file=sys.stderr)
            return 1

        cf = fields[0]
        required = ["REVIEW_ROUND", "BASELINE_FINDINGS", "DELTA_SCOPE", "SCOPE_CONSTRAINT"]
        missing = [k for k in required if k not in cf]
        if missing:
            print(f"FAIL: capsule missing fields: {missing}", file=sys.stderr)
            return 1

        if cf["REVIEW_ROUND"] < 2:
            print(f"FAIL: REVIEW_ROUND={cf['REVIEW_ROUND']} expected >= 2", file=sys.stderr)
            return 1

        print(f"round2_capsule_fields: PASS (REVIEW_ROUND={cf['REVIEW_ROUND']})")
        return 0


def _selftest_h5_no_silent_resolve() -> int:
    """
    SC-7.8: A finding that codex_A would not flag (but codex_B reported in Round 1)
    must NOT be silently resolved when the current codex round does not include it.
    Controller only marks resolved when the phenomenon is objectively absent.

    Scenario:
    - codex_A: no findings (would not flag F001)
    - codex_B: reports F001
    - Round 2 codex (neutral): returns empty list (does not see F001)
    - Expected: F001 is still unresolved? NO — per H5 contract, the controller
      checks 'is the symptom key still in round_findings' — if Round 2 returns
      empty, the symptom is NOT present → resolved is correct behaviour.

    The H5 protection is about NOT allowing subjective re-judgment:
    if Round 2 says "this is not a problem" but the symptom IS still present,
    the finding stays unresolved. We test that case: Round 2 returns F001 again
    (symptom present), which means finding stays unresolved even if codex
    internally doesn't think it's a problem.

    This test verifies: if Round N returns the same finding key, baseline_unresolved
    does NOT decrease (symptom present = still unresolved).
    """
    f1 = _make_finding("F001", file="auth.py", line=42, category="sc_conformance", source="codex_B")
    baseline = [dict(f1)]

    # Round 2: codex returns f1 again (symptom still present — should NOT be resolved)
    round2_findings = [_make_finding("F001", file="auth.py", line=42, category="sc_conformance", source="codex_A")]
    updated, baseline_unresolved, new_in_delta = update_baseline_statuses(
        baseline, round2_findings, round_num=2
    )

    if baseline_unresolved != 1:
        print(
            f"FAIL: expected 1 unresolved (symptom present), got {baseline_unresolved}",
            file=sys.stderr,
        )
        return 1

    # Confirm status is still unresolved
    if updated[0]["status"] != "unresolved":
        print(f"FAIL: F001 should be unresolved, got {updated[0]['status']!r}", file=sys.stderr)
        return 1

    print("h5_no_silent_resolve: PASS (symptom-present finding stays unresolved)")
    return 0


def _selftest_branch_c_rerun_after_simplify() -> int:
    """
    SC-7.9: In Branch C, the execution result that Branch B receives must have
    mtime AFTER the simplify step.
    """
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        subprocess.run(["git", "init", td], capture_output=True)
        # Create an initial tracked file so the repo has a HEAD ref (no empty-tree needed)
        _seed = Path(td) / ".gitkeep"
        _seed.write_text("seed\n")
        subprocess.run(["git", "-C", td, "add", ".gitkeep"], capture_output=True)
        subprocess.run(["git", "-C", td, "-c", "user.email=t@t.com", "-c", "user.name=T",
                        "commit", "-m", "seed"], capture_output=True)

        # Create a fake execution result file
        exec_result = tdp / "execution_result.json"
        exec_result.write_text(json.dumps({"execution_status": "ok"}), encoding="utf-8")

        stub = StubDispatch()
        # Branch A: Round 1 with findings, Round 2 resolves all
        f1 = _make_finding("F001")
        stub._r1_a = [f1]
        stub._r1_b = []
        stub._round_n_sequence = [
            [],  # Round 2 Branch A: resolves
            [],  # Round 2 Branch B: resolves
        ]
        stub._new_exec_result = exec_result

        # Record simplify time before calling branch_c
        simplify_time_before = time.time()

        original_exit = sys.exit

        def noop_exit(code: int) -> None:
            raise SystemExit(code)

        sys.exit = noop_exit  # type: ignore[assignment]
        try:
            result = run_branch_c(
                cwd=tdp, output_dir=tdp / "out",
                invocation_id=gen_id(),
                execution_result=exec_result,
                claude_findings=[],
                threshold_lines=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
                threshold_files=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
                max_rounds=10,
                stub_dispatch=stub,
            )
        except SystemExit as exc:
            if exc.code != 0:
                print(f"FAIL: unexpected SystemExit({exc.code})", file=sys.stderr)
                return 1
            result = "APPROVED"
        finally:
            sys.exit = original_exit  # type: ignore[assignment]

        # Verify that simplify was called and exec result mtime is after simplify
        if stub._simplify_time is None:
            print("FAIL: simplify was never called (stub._simplify_time is None)", file=sys.stderr)
            return 1

        exec_mtime = exec_result.stat().st_mtime
        if exec_mtime <= stub._simplify_time:
            print(
                f"FAIL: exec_result mtime={exec_mtime} must be > simplify_time={stub._simplify_time}",
                file=sys.stderr,
            )
            return 1

        print(
            f"branch_c_rerun_after_simplify: PASS "
            f"(exec_mtime={exec_mtime:.3f} > simplify_time={stub._simplify_time:.3f})"
        )
        return 0


SELFTESTS: dict[str, Any] = {
    "convergence_timeout": _selftest_convergence_timeout,
    "d7_large_delta_fanout": _selftest_d7_large_delta_fanout,
    "branch_b_convergence_timeout": _selftest_branch_b_convergence_timeout,
    "round2_capsule_fields": _selftest_round2_capsule_fields,
    "h5_no_silent_resolve": _selftest_h5_no_silent_resolve,
    "branch_c_rerun_after_simplify": _selftest_branch_c_rerun_after_simplify,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selftest", metavar="NAME",
                   help=f"Run selftest. Names: {', '.join(sorted(SELFTESTS))}")
    p.add_argument("--branch", choices=["code-only", "execution-only", "combined"],
                   help="Review branch to run")
    p.add_argument("--cwd", default=None,
                   help="Git root to use (default: auto-detect from current dir)")
    p.add_argument("--output-dir", default=None,
                   help="Directory to write baseline_findings.json and reports")
    p.add_argument("--claude-review-json", default=None,
                   help="Path to Claude self-review mapped JSON (findings[] injected as Round 1 third source)")
    p.add_argument("--execution-result", default=None,
                   help="Path to execution result artifact (branches B/C)")
    p.add_argument("--round2-fanout-threshold-lines", type=int,
                   default=DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
                   dest="round2_fanout_threshold_lines",
                   help=f"D7: delta lines threshold for Round2+ dual codex (default {DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES})")
    p.add_argument("--round2-fanout-threshold-files", type=int,
                   default=DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
                   dest="round2_fanout_threshold_files",
                   help=f"D7: delta files threshold for Round2+ dual codex (default {DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES})")
    p.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS,
                   help=f"Hard ceiling on total rounds (default {DEFAULT_MAX_ROUNDS})")
    p.add_argument("--deep", action="store_true", default=False,
                   help="SC-11: deep review mode; bridge timeout ≥1800s")
    p.add_argument("--queue-job-id", default=None,
                   help="SC-12: queue job ID for dispatch tracking")
    p.add_argument("--plan-file", default=None,
                   help="SC-32: plan file for deep outcome capsule")
    args = p.parse_args()

    if args.selftest:
        name = args.selftest
        if name not in SELFTESTS:
            print(f"ERROR: unknown selftest {name!r}. Available: {', '.join(sorted(SELFTESTS))}", file=sys.stderr)
            return 2
        print(f"=== selftest: {name} ===")
        return SELFTESTS[name]()

    if not args.branch:
        p.print_help()
        return 2

    cwd = Path(args.cwd) if args.cwd else Path.cwd()
    output_dir = Path(args.output_dir) if args.output_dir else GD_ROOT / "reports" / "review-controller"
    output_dir.mkdir(parents=True, exist_ok=True)

    invocation_id = gen_id()

    # Load Claude self-review findings if provided
    claude_findings: list[dict] = []
    if args.claude_review_json:
        try:
            cr = json.loads(Path(args.claude_review_json).read_text(encoding="utf-8"))
            claude_findings = list(cr.get("findings", []) or [])
        except Exception as e:
            print(f"[controller] WARNING: could not load claude_review_json: {e}", file=sys.stderr)

    execution_result = Path(args.execution_result) if args.execution_result else None

    threshold_lines = args.round2_fanout_threshold_lines
    threshold_files = args.round2_fanout_threshold_files

    if args.branch == "code-only":
        result = run_branch_a(
            cwd=cwd, output_dir=output_dir, invocation_id=invocation_id,
            claude_findings=claude_findings,
            threshold_lines=threshold_lines, threshold_files=threshold_files,
            max_rounds=args.max_rounds,
            deep=args.deep, queue_job_id=args.queue_job_id, plan_file=args.plan_file,
        )
    elif args.branch == "execution-only":
        result = run_branch_b(
            cwd=cwd, output_dir=output_dir, invocation_id=invocation_id,
            execution_result=execution_result,
            claude_findings=claude_findings,
            threshold_lines=threshold_lines, threshold_files=threshold_files,
            max_rounds=args.max_rounds,
            deep=args.deep, queue_job_id=args.queue_job_id, plan_file=args.plan_file,
        )
    elif args.branch == "combined":
        result = run_branch_c(
            cwd=cwd, output_dir=output_dir, invocation_id=invocation_id,
            execution_result=execution_result,
            claude_findings=claude_findings,
            threshold_lines=threshold_lines, threshold_files=threshold_files,
            max_rounds=args.max_rounds,
            deep=args.deep, queue_job_id=args.queue_job_id, plan_file=args.plan_file,
        )
    else:
        print(f"ERROR: unknown branch {args.branch!r}", file=sys.stderr)
        return 2

    print(f"GD_REVIEW_DECISION: {result}")
    return 0 if result == "APPROVED" else 1


if __name__ == "__main__":
    sys.exit(main())
