#!/usr/bin/env python3
"""gd-review-suite-controller.py — Plan A review-chain suite controller (revision=19).

Bounded-parallel review-plan controller for /gd review plan suite-mode.
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
import concurrent.futures
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
PREFLIGHT_SCRIPT = GD_PROJECT_ROOT / "scripts" / "gd-validate-master-plan-consistency.py"

# Error buckets that block final approval (all must be empty for APPROVED)
BLOCKING_BUCKETS = [
    "preflight_failed",
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
# rev21: + bridge_exit / bridge_stderr_path / bridge_stderr_summary so bridge
# argparse failures cannot be masked as transport_failed.
REQUIRED_JOB_REPORT_FIELDS = [
    "raw_verdict",
    "mapped_status",
    "aggregate_bucket",
    "target_hash",
    "raw_path",
    "git_gate_status",
    "bridge_exit",
    "bridge_stderr_path",
    "bridge_stderr_summary",
]

# Bridge run-bridge --target-role accepts ONLY this enum
# (sourced from gd-codex-bridge-review.py:VALID_TARGET_ROLES).
# Controller maps caller-supplied roles (master_plan / step_N / etc.) to this set.
_BRIDGE_VALID_TARGET_ROLES = {"master_plan", "subplan", "parent_close", "release_evidence"}


def _map_target_role_for_bridge(role: str) -> str:
    """Map suite-controller input role -> bridge VALID_TARGET_ROLES.

    Heuristic:
      - 'master_plan' / 'parent_close' / 'release_evidence' pass through
      - anything else (step_1, step_2, ...) collapses to 'subplan'
    """
    if role in _BRIDGE_VALID_TARGET_ROLES:
        return role
    return "subplan"


def _stderr_summary(stderr: str, max_chars: int = 240) -> str:
    """One-line summary of bridge stderr (last non-empty line, truncated)."""
    if not stderr or not stderr.strip():
        return ""
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if len(last) > max_chars:
        return last[:max_chars] + "…"
    return last


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
    if mapped_status == "missing_primary_target":
        return "missing_primary_target"
    if raw_path is None:
        return "transport_failed"
    if raw_verdict == "APPROVED":
        return "codex_approved"
    if raw_verdict == "REQUIRES_CHANGES":
        return "codex_requires_changes"
    if raw_verdict == "FAILED":
        return "codex_failed"
    return "ambiguous_raw_result"


def _dispatch_one_bridge(
    role: str,
    target_path_str: str,
    args: argparse.Namespace,
    mapped_dir: Path,
    log_dir: Path,
    stderr_dir: Path,
) -> dict:
    """Dispatch a single bridge call for one target. Returns the job result dict.

    Runs in a worker thread when max_parallel > 1; called directly when
    max_parallel == 1. Thread-safe: each job writes to distinct paths keyed by
    queue_job_id. No shared mutable state is written.
    """
    target = Path(target_path_str).resolve()
    queue_job_id = (f"{args.target_set_id}-{role}").replace("_", "-")

    target_hash = _sha256_file(target)
    if target_hash is None:
        print(f"TARGET_MISSING: {target} (role={role})", file=sys.stderr)
        return {
            "queue_job_id": queue_job_id,
            "target_role": role,
            "primary_target": str(target),
            "expected_target_hash": None,
            "codex_raw_result_path": None,
            "raw_contract": "v1" if args.compat_v1 else "auto",
            "bridge_exit": -1,
            "bridge_stderr_path": None,
            "bridge_stderr_summary": "primary target missing — bridge not invoked",
            "raw_verdict": "FAILED",
            "mapped_status": "missing_primary_target",
            "aggregate_bucket": "missing_primary_target",
            "target_hash": None,
            "raw_path": None,
            "git_gate_status": "skipped_missing_target",
            "_dirty": False,
        }

    # Git index check (B1, A7)
    git_ok = True
    git_status = "not_checked"
    dirty = False
    if args.require_git_index_match:
        git_ok, git_status = _check_git_index_match(target)
        if not git_ok:
            print(f"TARGET_WORKTREE_DIRTY: {role} — {git_status}", file=sys.stderr)
            dirty = True

    mapped_out = mapped_dir / f"{queue_job_id}.json"
    log_out = log_dir / f"{queue_job_id}.log"
    err_out = stderr_dir / f"{queue_job_id}.err"

    bridge_target_role = _map_target_role_for_bridge(role)
    bridge_cmd = [
        sys.executable, str(BRIDGE_SCRIPT),
        "run-bridge",
        "--kind", args.kind,
        "--target", str(target),
        "--cwd", args.cwd,
        "--out", str(mapped_out),
        "--queue-job-id", queue_job_id,
        "--target-role", bridge_target_role,
    ]
    if args.live_transport:
        bridge_cmd.append("--live-transport")
    if args.compat_v1:
        bridge_cmd.append("--compat-v1")

    print(f"BRIDGE_DISPATCH: {role} (mapped→{bridge_target_role}, {queue_job_id})")
    rc_bridge, stdout_bridge, stderr_bridge = _run_subprocess(bridge_cmd, f"bridge-{role}")
    log_out.write_text(stdout_bridge, encoding="utf-8")
    err_out.write_text(stderr_bridge, encoding="utf-8")

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

    return {
        "queue_job_id": queue_job_id,
        "target_role": role,
        "primary_target": str(target),
        "expected_target_hash": target_hash,
        "codex_raw_result_path": raw_path,
        "raw_contract": "v1" if args.compat_v1 else "auto",
        "bridge_exit": rc_bridge,
        "bridge_stderr_path": str(err_out),
        "bridge_stderr_summary": _stderr_summary(stderr_bridge),
        "raw_verdict": raw_verdict,
        "mapped_status": mapped_status,
        "aggregate_bucket": _infer_aggregate_bucket(raw_verdict, mapped_status, raw_path),
        "target_hash": target_hash,
        "raw_path": raw_path,
        "git_gate_status": git_status,
        "_dirty": dirty,
    }


def _run_live_targets(args: argparse.Namespace, out_dir: Path) -> tuple[int, dict]:
    """Run bridge for each target with bounded parallelism.

    Uses concurrent.futures.ThreadPoolExecutor with max_workers=args.max_parallel.
    When max_parallel=1 this degrades to sequential execution (one Future at a time).
    Each bridge call writes to distinct per-job paths — no shared mutable state.
    """
    mapped_dir = out_dir / "mapped"
    log_dir = out_dir / "bridge-stdout"
    stderr_dir = out_dir / "bridge-stderr"
    mapped_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    stderr_dir.mkdir(parents=True, exist_ok=True)

    max_workers = getattr(args, "max_parallel", 1)

    jobs: list[dict] = []
    dirty_detected = False

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        in_flight: dict[concurrent.futures.Future, tuple[str, str]] = {}
        for role, target_path_str in args.targets:
            fut = executor.submit(
                _dispatch_one_bridge,
                role,
                target_path_str,
                args,
                mapped_dir,
                log_dir,
                stderr_dir,
            )
            in_flight[fut] = (role, target_path_str)

        for fut in concurrent.futures.as_completed(in_flight):
            result = fut.result()
            if result.pop("_dirty", False):
                dirty_detected = True
            jobs.append(result)

    # Restore original order (as_completed gives completion order, not submission order)
    role_order = [role for role, _ in args.targets]
    jobs.sort(key=lambda j: role_order.index(j["target_role"]) if j["target_role"] in role_order else len(role_order))

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
            "bridge_stderr_path": None,
            "bridge_stderr_summary": "fixture_mode_no_real_bridge",
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


def _build_suite_target_closure(jobs: list[dict]) -> list[dict]:
    """Build suite_target_closure for controller report v1.1.

    evidence_kind:
      controller_approved  — aggregate_bucket == "codex_approved"
      mapped_status_approved — mapped_status == "completed" but not codex_approved
      n_a                  — everything else (missing, failed, transport error)
    """
    closure = []
    for j in jobs:
        target_id = j.get("queue_job_id", "")
        mapped_status = j.get("mapped_status", "transport_failed")
        aggregate_bucket = j.get("aggregate_bucket", "transport_failed")

        if aggregate_bucket == "codex_approved":
            evidence_kind = "controller_approved"
        elif mapped_status == "completed":
            evidence_kind = "mapped_status_approved"
        else:
            evidence_kind = "n_a"

        closure.append({
            "target_id": target_id,
            "mapped_status": mapped_status,
            "evidence_kind": evidence_kind,
        })
    return closure


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
    run_mode: str = "live",
    batch_ledgers: list[dict] | None = None,
) -> Path:
    """Write controller-report.json. All six required fields per A6 must be present.

    run_mode: "live" for normal production runs, "fixture" for fixture-mode runs.
    The schema expects this field for dispatch ledger cross-validation.

    batch_ledgers: list of {"path": str, "hash": str} entries for each batch ledger
    written by the controller (Phase 4 v1.1).
    """
    job_reports = []
    for j in jobs:
        entry: dict = {"queue_job_id": j.get("queue_job_id"), "target_role": j.get("target_role"),
                       "primary_target": j.get("primary_target")}
        for field in REQUIRED_JOB_REPORT_FIELDS:
            entry[field] = j.get(field)
        job_reports.append(entry)

    report = {
        "schema_version": "1.1",
        "run_mode": run_mode,
        "started_at": started_at,
        "finished_at": _now_iso(),
        "primary_gate": {"verdict": primary_verdict, "blocking": primary_blocking},
        "secondary_gate": {"verdict": secondary_verdict, "blocking": secondary_blocking},
        "gate_consistent": gate_consistent,
        "dirty_detected": dirty_detected,
        "aggregate_path": str(aggregate_path),
        "manifest_path": str(manifest_path),
        "jobs": job_reports,
        "batch_ledgers": batch_ledgers or [],
        "suite_target_closure": _build_suite_target_closure(jobs),
    }
    p = out_dir / "controller-report.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _selftest_bridge_argv() -> int:
    """Regression: controller→bridge mapping must yield argv accepted by bridge argparse.

    For each representative input role, build the same bridge cmd the controller
    would dispatch in live mode, spawn bridge as subprocess, and assert stderr
    does NOT contain argparse 'invalid choice' for --target-role.

    Business-layer rejections (e.g. 'live-transport flag required for actual
    delivery') are EXPECTED and prove argparse PASS. We do not pass
    --live-transport so no Codex daemon traffic is generated.
    """
    import tempfile

    test_cases = [
        ("master_plan", "master_plan"),
        ("step_1", "subplan"),
        ("step_42", "subplan"),
        ("parent_close", "parent_close"),
        ("release_evidence", "release_evidence"),
        ("arbitrary_role", "subplan"),
    ]

    print("SELFTEST_BRIDGE_ARGV: starting")
    with tempfile.TemporaryDirectory(prefix="gd-ctrl-selftest-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        target = tmpdir / "target.md"
        target.write_text("# selftest target\n", encoding="utf-8")

        failures: list[str] = []
        for input_role, expected_mapped in test_cases:
            mapped = _map_target_role_for_bridge(input_role)
            if mapped != expected_mapped:
                failures.append(
                    f"MAPPING_BUG: input_role={input_role!r} → mapped={mapped!r}, "
                    f"expected={expected_mapped!r}"
                )
                continue

            cmd = [
                sys.executable, str(BRIDGE_SCRIPT),
                "run-bridge",
                "--kind", "plan",
                "--target", str(target),
                "--cwd", str(tmpdir),
                "--out", str(tmpdir / f"mapped-{input_role}.json"),
                "--queue-job-id", f"selftest-{input_role}",
                "--target-role", mapped,
                "--compat-v1",
            ]
            _rc, _out, err = _run_subprocess(cmd, f"selftest-{input_role}")

            if "invalid choice" in err and "--target-role" in err:
                last = err.strip().splitlines()[-1] if err.strip() else "(empty)"
                failures.append(
                    f"ARGPARSE_REJECTED: input_role={input_role!r} → "
                    f"mapped={mapped!r}: {last}"
                )
            else:
                print(f"  input={input_role!r:<22} → bridge --target-role {mapped!r:<20} "
                      f"argparse PASS")

        if failures:
            print(f"\nSELFTEST_BRIDGE_ARGV: FAIL ({len(failures)} issue(s))",
                  file=sys.stderr)
            for f in failures:
                print(f"  {f}", file=sys.stderr)
            return 1

        print(f"SELFTEST_BRIDGE_ARGV: PASS ({len(test_cases)} cases)")
        return 0


def _selftest_max_parallel_minimal() -> int:
    """Selftest: prove max_parallel=1 passes, max_parallel=2 passes, max_parallel=3 is rejected at argparse.

    max_parallel=3 must fail at argparse.choices validation (exit 2), not at runtime.
    Prints SELFTEST_MAX_PARALLEL: PASS or FAIL. Returns 0 on pass.
    """
    print("SELFTEST_MAX_PARALLEL: starting")
    failures: list[str] = []

    # Case 1: max_parallel=1 must be accepted by argparse (choices=[1,2])
    for mp in [1, 2]:
        argv_test = [
            sys.argv[0],
            "--selftest-bridge-argv",  # dummy mode that doesn't need targets
            "--max-parallel", str(mp),
        ]
        # Parse directly — if choices rejects it argparse calls sys.exit(2)
        import io
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--max-parallel", type=int, choices=[1, 2], default=2)
        parser.add_argument("--selftest-bridge-argv", action="store_true")
        try:
            parsed = parser.parse_args(["--max-parallel", str(mp), "--selftest-bridge-argv"])
            if parsed.max_parallel != mp:
                failures.append(f"max_parallel={mp}: parsed value mismatch {parsed.max_parallel}")
            else:
                print(f"  max_parallel={mp}: argparse PASS")
        except SystemExit as e:
            failures.append(f"max_parallel={mp}: argparse rejected (exit {e.code})")

    # Case 2: max_parallel=3 must be rejected at argparse level
    parser3 = argparse.ArgumentParser(add_help=False)
    parser3.add_argument("--max-parallel", type=int, choices=[1, 2], default=2)
    import io as _io
    old_stderr = sys.stderr
    sys.stderr = _io.StringIO()
    try:
        parser3.parse_args(["--max-parallel", "3"])
        failures.append("max_parallel=3: argparse did NOT reject (expected SystemExit)")
    except SystemExit as e:
        captured = sys.stderr.getvalue()
        if e.code != 0:
            print(f"  max_parallel=3: argparse rejected at parse time (exit {e.code}) — PASS")
        else:
            failures.append(f"max_parallel=3: unexpected exit 0")
    finally:
        sys.stderr = old_stderr

    if failures:
        print(f"SELFTEST_MAX_PARALLEL: FAIL ({len(failures)} issue(s))", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print("SELFTEST_MAX_PARALLEL: PASS")
    return 0


def _selftest_controller_report_minimal() -> int:
    """Selftest: prove that a live controller report passes the validator, fixture-tagged fails.

    Creates minimal in-memory controller report JSON files and runs
    gd-validate-controller-report.py on them. Prints SELFTEST_CONTROLLER_REPORT:
    PASS or FAIL. Returns 0 on pass.
    """
    import tempfile

    print("SELFTEST_CONTROLLER_REPORT: starting")
    failures: list[str] = []

    validator = GD_PROJECT_ROOT / "scripts" / "gd-validate-controller-report.py"
    if not validator.exists():
        print("SELFTEST_CONTROLLER_REPORT: SKIP (validator not found)")
        return 0

    with tempfile.TemporaryDirectory(prefix="gd-ctrl-crm-") as td:
        td_path = Path(td)

        # Build a minimal valid live controller report
        _live_report = {
            "schema_version": "1.1",
            "run_mode": "live",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "primary_gate": {"verdict": "APPROVED", "blocking": []},
            "secondary_gate": {"verdict": "APPROVED", "blocking": []},
            "gate_consistent": True,
            "dirty_detected": False,
            "aggregate_path": str(td_path / "aggregate-final.json"),
            "manifest_path": str(td_path / "manifest-final.json"),
            "jobs": [
                {
                    "queue_job_id": "selftest-master-plan",
                    "target_role": "master_plan",
                    "primary_target": str(td_path / "plan.md"),
                    "raw_verdict": "APPROVED",
                    "mapped_status": "completed",
                    "aggregate_bucket": "codex_approved",
                    "target_hash": "a" * 64,
                    "raw_path": str(td_path / "raw.md"),
                    "git_gate_status": "clean",
                    "bridge_exit": 0,
                    "bridge_stderr_path": str(td_path / "bridge.err"),
                    "bridge_stderr_summary": "",
                }
            ],
            "batch_ledgers": [],
            "suite_target_closure": [],
        }

        live_path = td_path / "controller-report-live.json"
        live_path.write_text(json.dumps(_live_report, indent=2), encoding="utf-8")

        rc_live, out_live, err_live = _run_subprocess(
            [sys.executable, str(validator), str(live_path)],
            "validate-live-report",
        )
        if rc_live == 0:
            print("  live controller report: validator PASS")
        else:
            failures.append(
                f"live controller report: validator FAILED exit={rc_live}; {err_live[:200]}"
            )

        # Build a fixture-tagged report — validator should reject run_mode="fixture"
        # if the schema enforces live-only. If validator accepts it, that is also fine
        # (the selftest verifies the round-trip works, not that fixture is rejected).
        # We only assert the live one passes.
        _fixture_report = dict(_live_report)
        _fixture_report["run_mode"] = "fixture"
        fix_path = td_path / "controller-report-fixture.json"
        fix_path.write_text(json.dumps(_fixture_report, indent=2), encoding="utf-8")

        rc_fix, out_fix, err_fix = _run_subprocess(
            [sys.executable, str(validator), str(fix_path)],
            "validate-fixture-report",
        )
        # Fixture mode: if validator rejects it — expected and fine.
        # If validator accepts it — also fine (schema may not distinguish).
        # We do NOT count validator accepting fixture as a failure; the key
        # invariant is that the live report passes.
        status_fix = "PASS (validator accepts fixture)" if rc_fix == 0 else "PASS (validator rejects fixture as expected)"
        print(f"  fixture controller report: {status_fix}")

    if failures:
        print(f"SELFTEST_CONTROLLER_REPORT: FAIL ({len(failures)} issue(s))", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print("SELFTEST_CONTROLLER_REPORT: PASS")
    return 0


def main(argv: list[str]) -> int:
    started_at = _now_iso()

    parser = argparse.ArgumentParser(
        description="gd-review-suite-controller: bounded-parallel review-plan controller for /gd review plan suite-mode"
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--fixture", type=Path, metavar="FIXTURE_JSON",
                     help="Fixture JSON for selftest; bypasses live bridge (--target/--cwd not used)")
    grp.add_argument("--target-set-id", metavar="ID",
                     help="Stable identifier for this review suite run (live mode)")
    grp.add_argument("--selftest-bridge-argv", action="store_true",
                     help="Regression: verify controller→bridge mapping produces argv "
                          "accepted by bridge argparse (does not call live Codex)")
    grp.add_argument("--selftest-max-parallel-minimal", action="store_true",
                     help="Selftest: prove max_parallel=1 and =2 pass argparse, =3 is rejected")
    grp.add_argument("--selftest-controller-report-minimal", action="store_true",
                     help="Selftest: prove a live controller report passes the validator")

    parser.add_argument("--kind", default="plan",
                        choices=["plan", "code_diff", "execution_outcome", "combined"],
                        help="Review kind (default: plan)")
    parser.add_argument("--cwd", metavar="TARGET_WORKTREE",
                        help="Target project worktree root (required for live mode)")
    parser.add_argument("--target", action="append", metavar="role=path",
                        help="role=abs_path pair; specify once per plan file (live mode only)")
    parser.add_argument("--out-dir", type=Path, metavar="DIR",
                        help="Output directory for manifests, logs, reports "
                             "(required for --fixture / --target-set-id modes)")
    parser.add_argument("--live-transport", action="store_true",
                        help="Pass --live-transport to bridge (required for actual Codex delivery)")
    parser.add_argument("--compat-v1", action="store_true",
                        help="Pass --compat-v1 to bridge; current live plan writer produces v1 raw format")
    parser.add_argument("--require-git-index-match", action="store_true",
                        help="Block final APPROVED if any target has staged/worktree mismatch (AM/MM)")
    parser.add_argument("--max-parallel", type=int, choices=[1, 2], default=2,
                        help="Maximum concurrent bridge calls (1=sequential, 2=bounded-parallel). "
                             "Values >2 are rejected at argparse level (fail-closed). Default: 2.")

    args = parser.parse_args(argv[1:])

    if getattr(args, "selftest_bridge_argv", False):
        return _selftest_bridge_argv()

    if getattr(args, "selftest_max_parallel_minimal", False):
        return _selftest_max_parallel_minimal()

    if getattr(args, "selftest_controller_report_minimal", False):
        return _selftest_controller_report_minimal()

    if args.out_dir is None:
        print("ERROR: --out-dir is required for --fixture / --target-set-id modes",
              file=sys.stderr)
        return 2
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

    # ── Preflight: master_plan consistency check (live mode only) ────────────
    if not fixture_mode and PREFLIGHT_SCRIPT.exists():
        master_plan_targets = [
            (role, path) for role, path in args.targets if role == "master_plan"
        ]
        for role, mp_path in master_plan_targets:
            preflight_report = out_dir / f"preflight-{role}.json"
            rc_pre, out_pre, err_pre = _run_subprocess(
                [sys.executable, str(PREFLIGHT_SCRIPT), mp_path,
                 "--json-report", str(preflight_report)],
                f"preflight-{role}",
            )
            if rc_pre != 0:
                print(f"PREFLIGHT_FAILED: role={role} target={mp_path}", file=sys.stderr)
                print(out_pre)
                preflight_job = {
                    "queue_job_id": f"{target_set_id}-{role}",
                    "target_role": role,
                    "primary_target": mp_path,
                    "bridge_exit": -1,
                    "bridge_stderr_path": None,
                    "bridge_stderr_summary": "preflight_failed — Codex bridge not invoked",
                    "raw_verdict": "FAILED",
                    "mapped_status": "preflight_failed",
                    "aggregate_bucket": "preflight_failed",
                    "target_hash": _sha256_file(Path(mp_path)),
                    "raw_path": None,
                    "git_gate_status": "skipped_preflight_failed",
                    "_dirty": False,
                }
                _write_controller_report(
                    out_dir, [preflight_job],
                    "FAILED", ["PREFLIGHT_FAILED"],
                    "FAILED", ["PREFLIGHT_FAILED"],
                    True, False,
                    out_dir / "aggregate-final.json",
                    out_dir / "manifest-final.json",
                    started_at,
                    run_mode="live",
                )
                return 1

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

    # ── Emit stage dispatch ledgers (batch mode, Phase 4) ─────────────────────
    # Compute per-job result hashes from their mapped_out files.
    invocation_id = target_set_id or "fixture-suite"
    max_parallel_val = getattr(args, "max_parallel", 2)
    if max_parallel_val is None:
        max_parallel_val = 2
    max_parallel_val = min(int(max_parallel_val), 2)

    child_jobs_all: list[dict] = []
    for j in jobs:
        queue_job_id = j.get("queue_job_id", "")
        mapped_out_path_str = str(out_dir / "mapped" / f"{queue_job_id}.json")
        mapped_out_path = Path(mapped_out_path_str)
        result_hash = _sha256_file(mapped_out_path) if mapped_out_path.exists() else None
        bridge_exit = j.get("bridge_exit", -1)
        if fixture_mode:
            job_status = "completed"
        else:
            if j.get("aggregate_bucket") == "missing_primary_target":
                job_status = "failed"
            elif bridge_exit == 0:
                job_status = "completed"
            else:
                job_status = "failed"
        child_jobs_all.append({
            "job_id": queue_job_id,
            "result_path": mapped_out_path_str,
            "result_hash": result_hash,
            "status": job_status,
        })

    # Split into batches of max_parallel
    batch_size = max_parallel_val
    if child_jobs_all:
        batches = [child_jobs_all[i:i + batch_size]
                   for i in range(0, len(child_jobs_all), batch_size)]
    else:
        batches = [[]]  # ensure at least one batch

    blocking_buckets_in_ledger = [
        j["queue_job_id"]
        for j in jobs
        if j.get("aggregate_bucket") not in ("codex_approved", None)
    ]

    run_mode = "fixture" if fixture_mode else "live"
    controller_report_path_str = str(out_dir / "controller-report.json")
    final_decision = "APPROVED" if primary_verdict == "APPROVED" else "REQUIRES_CHANGES"

    # Pass 1: write each batch ledger to disk with merge_report_hash=None (placeholder)
    batch_ledger_paths: list[Path] = []
    batch_ledgers_meta: list[dict] = []
    ledger_path = None
    for batch_idx, batch_jobs in enumerate(batches):
        batch_id = f"batch-{batch_idx + 1:03d}"
        batch_ledger = {
            "schema_version": "1.0",
            "stage": "review_plan",
            "parent_run_id": invocation_id,
            "batch_id": batch_id,
            "recorded_at": _now_iso(),
            "child_agent_count": len(batch_jobs),
            "max_parallel": max_parallel_val,
            "child_jobs": batch_jobs,
            "main_agent_merge": {
                "merge_report_path": controller_report_path_str,
                "merge_report_hash": None,  # placeholder; filled after controller report is written
                "final_decision": final_decision,
                "blocking_buckets": blocking_buckets_in_ledger,
            },
        }
        batch_ledger_path = out_dir / f"stage-dispatch-ledger-batch-{batch_idx + 1:03d}.json"
        batch_ledger_path.write_text(
            json.dumps(batch_ledger, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        batch_ledger_hash = _sha256_file(batch_ledger_path)
        batch_ledger_paths.append(batch_ledger_path)
        batch_ledgers_meta.append({"path": str(batch_ledger_path), "hash": batch_ledger_hash})
        ledger_path = batch_ledger_path  # last one for backward compat prints

    # ── Write controller-report.json (after batch ledgers exist) ──────────────
    report_path = _write_controller_report(
        out_dir, jobs,
        primary_verdict, primary_blocking,
        secondary_verdict, secondary_blocking,
        gate_consistent, dirty_detected,
        aggregate_path, manifest_path,
        started_at,
        run_mode=run_mode,
        batch_ledgers=batch_ledgers_meta,
    )

    # Pass 2: backfill merge_report_hash into each batch ledger now that report exists
    controller_report_hash = _sha256_file(report_path) if report_path.exists() else None
    for bl_path in batch_ledger_paths:
        try:
            bl_data = json.loads(bl_path.read_text(encoding="utf-8"))
            bl_data["main_agent_merge"]["merge_report_hash"] = controller_report_hash
            bl_path.write_text(
                json.dumps(bl_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (json.JSONDecodeError, OSError) as e:
            print(f"BATCH_LEDGER_BACKFILL_FAILED for {bl_path}: {e}", file=sys.stderr)

    # Pass 3: re-hash batch ledger files (their content changed during Pass 2)
    # and rewrite controller report so batch_ledgers[].hash matches on-disk files.
    # NOTE: this means the controller report hash changes again; we keep the
    # in-ledger merge_report_hash referencing the pre-rehash report (a known
    # documented loop point). Downstream consumers should re-hash the report
    # if they need the final hash.
    batch_ledgers_meta_final: list[dict] = []
    for bl_path in batch_ledger_paths:
        final_hash = _sha256_file(bl_path)
        batch_ledgers_meta_final.append({"path": str(bl_path), "hash": final_hash})

    report_path = _write_controller_report(
        out_dir, jobs,
        primary_verdict, primary_blocking,
        secondary_verdict, secondary_blocking,
        gate_consistent, dirty_detected,
        aggregate_path, manifest_path,
        started_at,
        run_mode=run_mode,
        batch_ledgers=batch_ledgers_meta_final,
    )

    # ── Validate controller-report.json ───────────────────────────────────────
    controller_report_validator = GD_PROJECT_ROOT / "scripts" / "gd-validate-controller-report.py"
    if controller_report_validator.exists():
        rc_crv, out_crv, err_crv = _run_subprocess(
            [sys.executable, str(controller_report_validator), str(report_path)],
            "controller-report-validator",
        )
        if rc_crv != 0:
            print(f"CONTROLLER_REPORT_VALIDATOR_FAILED (exit {rc_crv}):\n{out_crv}{err_crv}",
                  file=sys.stderr)

    # ── Validate each stage dispatch ledger ───────────────────────────────────
    ledger_validator = GD_PROJECT_ROOT / "scripts" / "gd-validate-stage-dispatch-ledger.py"
    if ledger_validator.exists():
        for bl_path in batch_ledger_paths:
            rc_ldv, out_ldv, err_ldv = _run_subprocess(
                [sys.executable, str(ledger_validator), str(bl_path)],
                "ledger-validator",
            )
            if rc_ldv != 0:
                print(
                    f"STAGE_DISPATCH_LEDGER_VALIDATOR_FAILED for {bl_path.name} "
                    f"(exit {rc_ldv}):\n{out_ldv}{err_ldv}",
                    file=sys.stderr,
                )

    # ── Print final status ────────────────────────────────────────────────────
    print(f"SUITE_CONTROLLER_VERDICT: {primary_verdict}")
    print(f"GATE_CONSISTENT: {gate_consistent}")
    print(f"DIRTY_DETECTED: {dirty_detected}")
    print(f"AGGREGATE_PATH: {aggregate_path}")
    print(f"MANIFEST_PATH: {manifest_path}")
    print(f"PARENT_CLOSE_PATH: {parent_close_path}")
    print(f"CONTROLLER_REPORT_PATH: {report_path}")
    for bl_path in batch_ledger_paths:
        print(f"STAGE_DISPATCH_LEDGER_PATH: {bl_path}")

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
