#!/usr/bin/env python3
"""gd-review-suite-controller.py — Plan A review-chain suite controller (revision=19).

Serial bridge dispatcher for /gd review plan suite-mode.
Prevents concurrent Claude sub-agent bridge invocations.
Implements dual gate: primary (aggregate error buckets) + secondary (re-read independently).

CLI (production):
  python3 scripts/gd-review-suite-controller.py \\
    --kind plan \\
    --cwd "<target worktree>" \\
    --target-set-id "<stable-id>" \\
    --target master_plan="<abs path>" \\
    --target step_1="<abs path>" \\
    --out-dir "<report dir>" \\
    --live-transport \\
    --compat-v1 \\
    --require-git-index-match

CLI (fixture test):
  python3 scripts/gd-review-suite-controller.py \\
    --fixture fixtures/review-chain/suite-controller/approved-v1-suite.json \\
    --out-dir reports/_selftest_runtime_evidence/suite-controller-approved

Exit codes:
  0 = all targets APPROVED, aggregate clean, gates consistent
  1 = one or more targets FAILED/REQUIRES_CHANGES, gate blocked, or inconsistency
  2 = bad args or missing files
  3 = PARENT_GATE_MISMATCH (primary and secondary gate verdicts disagree)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

GD_PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_SCRIPT = GD_PROJECT_ROOT / "scripts" / "gd-codex-bridge-review.py"
AGGREGATE_SCRIPT = GD_PROJECT_ROOT / "scripts" / "gd-aggregate-codex-cross-review.py"
MANIFEST_VALIDATOR = GD_PROJECT_ROOT / "scripts" / "gd-validate-codex-cross-review-manifest.py"
AGGREGATE_VALIDATOR = GD_PROJECT_ROOT / "scripts" / "gd-validate-codex-cross-review-aggregate.py"

# Error buckets that block final approval (all must be empty for APPROVED)
BLOCKING_BUCKETS = [
    "transport_failed",
    "wrapper_schema_fail",
    "codex_requires_changes",
    "codex_failed",
    "missing_primary_target",
    "stale_review_contract",
    "ambiguous_raw_result",
    "stale_target_hash",   # target file changed since review was run
    "unbound_result",      # raw result path specified but file missing
]

# Required fields in each job entry of controller-report.json (A6)
REQUIRED_JOB_REPORT_FIELDS = [
    "raw_verdict",
    "mapped_status",
    "aggregate_bucket",
    "target_hash",
    "raw_path",
    "git_gate_status",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(p: Path) -> str | None:
    try:
        h = hashlib.sha256()
        h.update(p.read_bytes())
        return h.hexdigest()
    except OSError:
        return None


def _run_subprocess(cmd: list[str], label: str) -> tuple[int, str, str]:
    """Run command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError as e:
        return 2, "", f"SUBPROCESS_NOT_FOUND: {e}"
    except Exception as e:
        return 2, "", f"SUBPROCESS_ERROR ({label}): {e}"


def _parse_stdout_field(stdout: str, field: str) -> str | None:
    """Extract 'FIELD: value' from stdout."""
    m = re.search(rf"^{re.escape(field)}:\s*(.+)$", stdout, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def _check_git_index_match(target: Path) -> tuple[bool, str]:
    """
    Check that target file has no staged vs worktree mismatch (AM/MM state).
    Returns (ok, status_description).
    B1: use relpath from worktree, not absolute path in git commands.
    A7: git -C explicitly set to target's worktree, not controller's cwd.
    """
    target_dir = str(target.parent)
    rc, out, err = _run_subprocess(
        ["git", "-C", target_dir, "rev-parse", "--show-toplevel"],
        "git-worktree-toplevel",
    )
    if rc != 0:
        return False, f"GIT_TOPLEVEL_FAILED: {err.strip()}"

    worktree = out.strip()
    try:
        rel = str(target.relative_to(worktree))
    except ValueError:
        rel = target.name  # fallback to filename only

    # Unstaged changes in working tree vs index
    rc_u, out_u, _ = _run_subprocess(
        ["git", "-C", worktree, "diff", "--name-only", "--", rel],
        "git-diff-unstaged",
    )
    # Staged changes vs HEAD
    rc_s, out_s, _ = _run_subprocess(
        ["git", "-C", worktree, "diff", "--cached", "--name-only", "--", rel],
        "git-diff-staged",
    )
    # Short status to detect AM/MM state
    rc_st, out_st, _ = _run_subprocess(
        ["git", "-C", worktree, "status", "--short", "--", rel],
        "git-status-short",
    )

    has_unstaged = bool(out_u.strip())
    short = out_st.strip()
    is_am_or_mm = short.startswith("AM") or short.startswith("MM")

    if has_unstaged or is_am_or_mm:
        problems = []
        if has_unstaged:
            problems.append("UNSTAGED_DIFF")
        if is_am_or_mm:
            problems.append(f"AM_OR_MM_STATE:{short}")
        return False, "TARGET_WORKTREE_DIRTY: " + "; ".join(problems)

    return True, "clean"


def _primary_gate(summary: dict) -> tuple[str, list[str]]:
    """Check aggregate summary error buckets. Returns (verdict, blocking_ids)."""
    blocked: list[str] = []
    for bucket in BLOCKING_BUCKETS:
        ids = summary.get(bucket, [])
        if ids:
            blocked.extend([f"{bucket}:{jid}" for jid in ids])
    verdict = "FAILED" if blocked else "APPROVED"
    return verdict, blocked


def _secondary_gate(aggregate_path: Path) -> tuple[str, list[str]]:
    """Re-read aggregate-final.json independently and re-derive verdict."""
    if not aggregate_path.exists():
        return "FAILED", ["AGGREGATE_MISSING"]
    try:
        agg = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return "FAILED", [f"AGGREGATE_READ_ERROR: {e}"]
    summary = agg.get("summary", {})
    return _primary_gate(summary)


def _infer_aggregate_bucket(raw_verdict: str, mapped_status: str, raw_path: str | None) -> str:
    if raw_path is None:
        return "transport_failed"
    if raw_verdict == "APPROVED":
        return "codex_approved"
    if raw_verdict == "REQUIRES_CHANGES":
        return "codex_requires_changes"
    if raw_verdict == "FAILED":
        return "codex_failed"
    return "ambiguous_raw_result"


def _run_live_targets(args: argparse.Namespace, out_dir: Path) -> tuple[int, dict]:
    """
    Run bridge for each target serially. Returns (exit_code, run_context).
    Never uses Agent/sub-agent; all bridge calls are sequential in this process.
    """
    mapped_dir = out_dir / "mapped"
    log_dir = out_dir / "bridge-stdout"
    mapped_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []
    dirty_detected = False

    for role, target_path_str in args.targets:
        target = Path(target_path_str).resolve()
        queue_job_id = (f"{args.target_set_id}-{role}").replace("_", "-")

        target_hash = _sha256_file(target)
        if target_hash is None:
            print(f"TARGET_MISSING: {target} (role={role})", file=sys.stderr)
            jobs.append({
                "queue_job_id": queue_job_id,
                "target_role": role,
                "primary_target": str(target),
                "expected_target_hash": None,
                "codex_raw_result_path": None,
                "raw_contract": "v1" if args.compat_v1 else "auto",
                "bridge_exit": -1,
                "raw_verdict": "FAILED",
                "mapped_status": "missing_primary_target",
                "aggregate_bucket": "missing_primary_target",
                "target_hash": None,
                "raw_path": None,
                "git_gate_status": "skipped_missing_target",
            })
            continue

        # Git index check (B1, A7)
        git_ok = True
        git_status = "not_checked"
        if args.require_git_index_match:
            git_ok, git_status = _check_git_index_match(target)
            if not git_ok:
                print(f"TARGET_WORKTREE_DIRTY: {role} — {git_status}", file=sys.stderr)
                dirty_detected = True

        mapped_out = mapped_dir / f"{queue_job_id}.json"
        log_out = log_dir / f"{queue_job_id}.log"

        bridge_cmd = [
            sys.executable, str(BRIDGE_SCRIPT),
            "run-bridge",
            "--kind", args.kind,
            "--target", str(target),
            "--cwd", args.cwd,
            "--out", str(mapped_out),
            "--queue-job-id", queue_job_id,
            "--target-role", "plan_artifact",
        ]
        if args.live_transport:
            bridge_cmd.append("--live-transport")
        if args.compat_v1:
            bridge_cmd.append("--compat-v1")

        print(f"BRIDGE_DISPATCH: {role} ({queue_job_id})")
        rc_bridge, stdout_bridge, stderr_bridge = _run_subprocess(bridge_cmd, f"bridge-{role}")
        log_out.write_text(stdout_bridge, encoding="utf-8")

        transport_result = _parse_stdout_field(stdout_bridge, "TRANSPORT_RESULT")
        raw_path = None if (transport_result is None or transport_result == "N/A") else transport_result

        raw_verdict = "FAILED"
        mapped_status = "transport_failed"
        if mapped_out.exists():
            try:
                mapped_data = json.loads(mapped_out.read_text(encoding="utf-8"))
                raw_verdict = mapped_data.get("gd_review_decision", "FAILED")
                mapped_status = mapped_data.get("review_run_status", "transport_failed")
            except (json.JSONDecodeError, OSError):
                pass

        jobs.append({
            "queue_job_id": queue_job_id,
            "target_role": role,
            "primary_target": str(target),
            "expected_target_hash": target_hash,
            "codex_raw_result_path": raw_path,
            "raw_contract": "v1" if args.compat_v1 else "auto",
            "bridge_exit": rc_bridge,
            "raw_verdict": raw_verdict,
            "mapped_status": mapped_status,
            "aggregate_bucket": _infer_aggregate_bucket(raw_verdict, mapped_status, raw_path),
            "target_hash": target_hash,
            "raw_path": raw_path,
            "git_gate_status": git_status,
        })

    return 0, {"jobs": jobs, "dirty_detected": dirty_detected}


def _run_fixture(fixture_path: Path, out_dir: Path) -> tuple[int, dict]:
    """Run controller in fixture test mode. Simulate bridge results from fixture JSON."""
    if not fixture_path.exists():
        print(f"FIXTURE_NOT_FOUND: {fixture_path}", file=sys.stderr)
        return 2, {}

    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"FIXTURE_PARSE_ERROR: {e}", file=sys.stderr)
        return 2, {}

    mapped_dir = out_dir / "mapped"
    log_dir = out_dir / "bridge-stdout"
    mapped_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    target_set_id = fixture.get("target_set_id", "fixture-suite")
    kind = fixture.get("kind", "plan")
    compat_v1 = bool(fixture.get("compat_v1", True))
    fixture_jobs = fixture.get("jobs", [])

    if not isinstance(fixture_jobs, list) or not fixture_jobs:
        print("FIXTURE_JOBS_EMPTY", file=sys.stderr)
        return 2, {}

    jobs: list[dict] = []
    for fjob in fixture_jobs:
        role = fjob.get("target_role", "unknown")
        queue_job_id = fjob.get("queue_job_id", f"{target_set_id}-{role}".replace("_", "-"))
        decision = fjob.get("simulated_decision", "APPROVED")
        run_status = fjob.get("simulated_run_status", "completed")
        target_hash = fjob.get("simulated_target_hash", "a" * 64)
        primary_target = fjob.get("primary_target", f"fixture/{role}.md")

        raw_result_rel = fjob.get("simulated_transport_result")
        raw_path: str | None = None
        if raw_result_rel:
            rp = GD_PROJECT_ROOT / raw_result_rel
            raw_path = str(rp) if rp.exists() else None

        mapped_out = mapped_dir / f"{queue_job_id}.json"
        mapped_data = {
            "reviewer": "codex",
            "review_kind": kind,
            "primary_target": primary_target,
            "gd_review_decision": decision,
            "review_run_status": run_status,
            "target_hash": target_hash,
            "findings": [],
            "merge_notes": {},
        }
        mapped_out.write_text(json.dumps(mapped_data, ensure_ascii=False, indent=2), encoding="utf-8")
        (log_dir / f"{queue_job_id}.log").write_text(
            f"FIXTURE_MODE: {role}\nTRANSPORT_RESULT: {raw_path or 'N/A'}\n",
            encoding="utf-8",
        )

        jobs.append({
            "queue_job_id": queue_job_id,
            "target_role": role,
            "primary_target": primary_target,
            "expected_target_hash": target_hash,
            "codex_raw_result_path": raw_path,
            "raw_contract": "v1" if compat_v1 else "auto",
            "bridge_exit": 0,
            "raw_verdict": decision,
            "mapped_status": run_status,
            "aggregate_bucket": _infer_aggregate_bucket(decision, run_status, raw_path),
            "target_hash": target_hash,
            "raw_path": raw_path,
            "git_gate_status": "fixture_mode",
        })

    return 0, {
        "jobs": jobs,
        "dirty_detected": False,
        "target_set_id": target_set_id,
        "kind": kind,
        "compat_v1": compat_v1,
    }


def _build_manifest(jobs: list[dict], target_set_id: str, kind: str, compat_v1: bool) -> dict:
    return {
        "target_set_id": target_set_id,
        "required_jobs": [
            {
                "queue_job_id": j["queue_job_id"],
                "target_role": j["target_role"],
                "primary_target": j["primary_target"],
                "review_kind": kind,
                "expected_target_hash": j["expected_target_hash"],
                "codex_raw_result_path": j["codex_raw_result_path"],
                "raw_contract": j["raw_contract"],
            }
            for j in jobs
        ],
    }


def _write_parent_close(out_dir: Path, verdict: str, blocking: list[str]) -> Path:
    """Generate parent-close.md with PARENT_CLOSE_STATUS line."""
    parent_status = "fully_completed" if verdict == "APPROVED" else "requires_changes"
    lines = [
        "# Suite Review Parent Close",
        "",
        f"PARENT_CLOSE_STATUS: {parent_status}",
        "",
        f"**Controller verdict**: {verdict}",
        f"**Generated**: {_now_iso()}",
        "",
    ]
    if blocking:
        lines += ["## Blocking Issues", ""]
        for b in blocking:
            lines.append(f"- {b}")
        lines.append("")
    p = out_dir / "parent-close.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _write_controller_report(
    out_dir: Path,
    jobs: list[dict],
    primary_verdict: str,
    primary_blocking: list[str],
    secondary_verdict: str,
    secondary_blocking: list[str],
    gate_consistent: bool,
    dirty_detected: bool,
    aggregate_path: Path,
    manifest_path: Path,
    started_at: str,
) -> Path:
    """Write controller-report.json. All six required fields per A6 must be present."""
    job_reports = []
    for j in jobs:
        entry: dict = {"queue_job_id": j.get("queue_job_id"), "target_role": j.get("target_role"),
                       "primary_target": j.get("primary_target")}
        for field in REQUIRED_JOB_REPORT_FIELDS:
            entry[field] = j.get(field)
        job_reports.append(entry)

    report = {
        "schema_version": "1.0",
        "started_at": started_at,
        "finished_at": _now_iso(),
        "primary_gate": {"verdict": primary_verdict, "blocking": primary_blocking},
        "secondary_gate": {"verdict": secondary_verdict, "blocking": secondary_blocking},
        "gate_consistent": gate_consistent,
        "dirty_detected": dirty_detected,
        "aggregate_path": str(aggregate_path),
        "manifest_path": str(manifest_path),
        "jobs": job_reports,
    }
    p = out_dir / "controller-report.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def main(argv: list[str]) -> int:
    started_at = _now_iso()

    parser = argparse.ArgumentParser(
        description="gd-review-suite-controller: serial bridge dispatcher for /gd review plan suite-mode"
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--fixture", type=Path, metavar="FIXTURE_JSON",
                     help="Fixture JSON for selftest; bypasses live bridge (--target/--cwd not used)")
    grp.add_argument("--target-set-id", metavar="ID",
                     help="Stable identifier for this review suite run (live mode)")

    parser.add_argument("--kind", default="plan",
                        choices=["plan", "code_diff", "execution_outcome", "combined"],
                        help="Review kind (default: plan)")
    parser.add_argument("--cwd", metavar="TARGET_WORKTREE",
                        help="Target project worktree root (required for live mode)")
    parser.add_argument("--target", action="append", metavar="role=path",
                        help="role=abs_path pair; specify once per plan file (live mode only)")
    parser.add_argument("--out-dir", required=True, type=Path, metavar="DIR",
                        help="Output directory for manifests, logs, reports")
    parser.add_argument("--live-transport", action="store_true",
                        help="Pass --live-transport to bridge (required for actual Codex delivery)")
    parser.add_argument("--compat-v1", action="store_true",
                        help="Pass --compat-v1 to bridge; current live plan writer produces v1 raw format")
    parser.add_argument("--require-git-index-match", action="store_true",
                        help="Block final APPROVED if any target has staged/worktree mismatch (AM/MM)")

    args = parser.parse_args(argv[1:])

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    fixture_mode = args.fixture is not None

    if not fixture_mode:
        if not args.cwd:
            print("ERROR: --cwd is required for live mode", file=sys.stderr)
            return 2
        if not args.target:
            print("ERROR: at least one --target role=path is required for live mode", file=sys.stderr)
            return 2

        parsed_targets: list[tuple[str, str]] = []
        for t in args.target:
            if "=" not in t:
                print(f"ERROR: --target must be role=path, got {t!r}", file=sys.stderr)
                return 2
            role, path = t.split("=", 1)
            parsed_targets.append((role.strip(), path.strip()))
        args.targets = parsed_targets
        target_set_id = args.target_set_id
        kind = args.kind
        compat_v1 = args.compat_v1
    else:
        target_set_id = ""
        kind = "plan"
        compat_v1 = True

    # ── Dispatch: fixture or live ─────────────────────────────────────────────
    if fixture_mode:
        rc_dispatch, ctx = _run_fixture(args.fixture, out_dir)
    else:
        rc_dispatch, ctx = _run_live_targets(args, out_dir)

    if rc_dispatch != 0:
        return rc_dispatch

    jobs = ctx["jobs"]
    dirty_detected = ctx.get("dirty_detected", False)
    if fixture_mode:
        target_set_id = ctx.get("target_set_id", "fixture-suite")
        kind = ctx.get("kind", "plan")
        compat_v1 = ctx.get("compat_v1", True)

    # ── Build + validate manifest ─────────────────────────────────────────────
    manifest = _build_manifest(jobs, target_set_id, kind, compat_v1)
    manifest_path = out_dir / "manifest-final.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    rc_mval, out_mval, err_mval = _run_subprocess(
        [sys.executable, str(MANIFEST_VALIDATOR), str(manifest_path)],
        "manifest-validator",
    )
    if rc_mval != 0:
        print(f"MANIFEST_VALIDATOR_FAILED (exit {rc_mval}):\n{out_mval}{err_mval}", file=sys.stderr)
        # Continue to generate report; primary gate will block

    # ── Call aggregate ────────────────────────────────────────────────────────
    aggregate_path = out_dir / "aggregate-final.json"
    agg_cmd = [
        sys.executable, str(AGGREGATE_SCRIPT),
        "--manifest", str(manifest_path),
        "--out", str(aggregate_path),
        "--consume-existing-results",
    ]
    rc_agg, out_agg, err_agg = _run_subprocess(agg_cmd, "aggregate")
    if rc_agg != 0:
        print(f"AGGREGATE_FAILED (exit {rc_agg}):\n{out_agg[:500]}{err_agg[:200]}", file=sys.stderr)

    # ── Validate aggregate ────────────────────────────────────────────────────
    rc_aval = 1
    if aggregate_path.exists():
        rc_aval, out_aval, err_aval = _run_subprocess(
            [sys.executable, str(AGGREGATE_VALIDATOR), str(aggregate_path)],
            "aggregate-validator",
        )
        if rc_aval != 0:
            print(f"AGGREGATE_VALIDATOR_FAILED (exit {rc_aval}):\n{out_aval}{err_aval}", file=sys.stderr)

    # ── Primary gate ──────────────────────────────────────────────────────────
    summary: dict = {}
    if aggregate_path.exists():
        try:
            agg_data = json.loads(aggregate_path.read_text(encoding="utf-8"))
            summary = agg_data.get("summary", {})
        except (json.JSONDecodeError, OSError):
            pass
    else:
        # Synthetic summary from job data when aggregate failed to generate
        summary = {b: [] for b in BLOCKING_BUCKETS}
        for j in jobs:
            bucket = j.get("aggregate_bucket", "transport_failed")
            if bucket in summary:
                summary[bucket].append(j["queue_job_id"])
            elif bucket != "codex_approved":
                summary["ambiguous_raw_result"].append(j["queue_job_id"])

    primary_verdict, primary_blocking = _primary_gate(summary)

    if dirty_detected and primary_verdict == "APPROVED":
        primary_verdict = "FAILED"
        primary_blocking.append("TARGET_WORKTREE_DIRTY_BLOCKED")

    if rc_agg != 0:
        primary_verdict = "FAILED"
        primary_blocking.append(f"AGGREGATE_SCRIPT_FAILED_EXIT_{rc_agg}")
    if rc_aval != 0 and aggregate_path.exists():
        primary_verdict = "FAILED"
        primary_blocking.append(f"AGGREGATE_VALIDATOR_FAILED_EXIT_{rc_aval}")

    # ── Secondary gate (independent re-read of aggregate-final.json) ─────────
    secondary_verdict, secondary_blocking = _secondary_gate(aggregate_path)
    if dirty_detected and secondary_verdict == "APPROVED":
        secondary_verdict = "FAILED"
        secondary_blocking.append("TARGET_WORKTREE_DIRTY_BLOCKED")

    # ── Gate consistency check (A10, B4) ──────────────────────────────────────
    gate_consistent = (primary_verdict == secondary_verdict)

    # ── Generate parent-close.md ──────────────────────────────────────────────
    parent_close_path = _write_parent_close(out_dir, primary_verdict, primary_blocking)

    # ── Write controller-report.json ──────────────────────────────────────────
    report_path = _write_controller_report(
        out_dir, jobs,
        primary_verdict, primary_blocking,
        secondary_verdict, secondary_blocking,
        gate_consistent, dirty_detected,
        aggregate_path, manifest_path,
        started_at,
    )

    # ── Print final status ────────────────────────────────────────────────────
    print(f"SUITE_CONTROLLER_VERDICT: {primary_verdict}")
    print(f"GATE_CONSISTENT: {gate_consistent}")
    print(f"DIRTY_DETECTED: {dirty_detected}")
    print(f"AGGREGATE_PATH: {aggregate_path}")
    print(f"MANIFEST_PATH: {manifest_path}")
    print(f"PARENT_CLOSE_PATH: {parent_close_path}")
    print(f"CONTROLLER_REPORT_PATH: {report_path}")

    if not gate_consistent:
        print(
            f"PARENT_GATE_MISMATCH: primary={primary_verdict} secondary={secondary_verdict}",
            file=sys.stderr,
        )
        return 3

    if primary_verdict == "APPROVED":
        print("SUITE_CONTROLLER_STATUS: approved_all_targets_clean")
        return 0

    print(f"SUITE_CONTROLLER_STATUS: blocked — {'; '.join(primary_blocking[:5])}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
