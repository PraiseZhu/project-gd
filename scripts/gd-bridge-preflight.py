#!/usr/bin/env python3
"""GD Bridge Preflight Diagnostic (v3.1)

Runs 4 smoke tests to diagnose why gpt-5.5 + xhigh fails in the GD bridge path.
Does NOT modify any production code. Produces preflight-report.json for route decision.

Usage:
  python3 scripts/gd-bridge-preflight.py \
    --capsule /Users/praise/.claude/handoff/archive/20260518T142755Z-54689.capsule \
    --output-dir reports/bridge-preflight/$(date -u +%Y%m%dT%H%M%SZ) \
    --max-xhigh-calls 15

Route decision rules (written to decision.md after report):
  1. xhigh_short unstable/inconclusive
       -> if config_matrix.clean_home stable: route=config_isolation
       -> else: route=escalate_outside_scope
  2. xhigh_short stable, xhigh_real_capsule unstable: route=shard
  3. xhigh_real_capsule stable: route=no_fix_needed_or_intermittent
  4. else: route=inconclusive
"""
from __future__ import annotations
import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHORT_PROMPT = "Say only the word OK and nothing else."

STDERR_CLASSES = {
    "invalid_grant": "auth",
    "token refresh": "auth",
    "invalid peer certificate": "tls",
    "failed to refresh available models": "model_manager",
    "timeout waiting for child process": "model_manager",
    "stream disconnected": "stream",
    "VERDICT": None,  # success indicator — not an error
}

CODEX_BIN = "codex"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify_stderr(stderr: str) -> str:
    if not stderr:
        return "none"
    s = stderr.lower()
    for fragment, cls in STDERR_CLASSES.items():
        if fragment.lower() in s:
            return cls or "none"
    return "unknown"


def has_verdict(stdout: str) -> bool:
    return "VERDICT:" in stdout or "APPROVED" in stdout or "REQUIRES_CHANGES" in stdout


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_codex(
    prompt_or_file: str,
    *,
    from_file: bool = False,
    model: str = "gpt-5.5",
    reasoning: str = "xhigh",
    sandbox: str = "read-only",
    extra_flags: list[str] | None = None,
    timeout: int = 300,
    cwd: str | None = None,
) -> dict:
    """Run codex exec and return trial dict."""
    cmd = [CODEX_BIN, "exec"]
    cmd += ["-m", model]
    cmd += ["-c", f"model_reasoning_effort={reasoning}"]
    cmd += ["-s", sandbox]
    if extra_flags:
        cmd += extra_flags
    if from_file:
        cmd += ["--", "cat", prompt_or_file]
        # Actually pass capsule as stdin
        cmd = [CODEX_BIN, "exec", "-m", model,
               "-c", f"model_reasoning_effort={reasoning}",
               "-s", sandbox]
        if extra_flags:
            cmd += extra_flags
    else:
        cmd += [prompt_or_file]

    start = time.monotonic()
    verdict_present = False
    stdout_buf = ""
    stderr_buf = ""
    exit_code = -1

    try:
        if from_file:
            capsule_text = Path(prompt_or_file).read_text(encoding="utf-8", errors="replace")
            proc = subprocess.run(
                cmd,
                input=capsule_text,
                capture_output=True, text=True, timeout=timeout,
                cwd=cwd,
            )
        else:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout,
                cwd=cwd,
            )
        stdout_buf = proc.stdout or ""
        stderr_buf = proc.stderr or ""
        exit_code = proc.returncode
        verdict_present = has_verdict(stdout_buf)
    except subprocess.TimeoutExpired as e:
        stderr_buf = f"exec_timeout: process did not return within {timeout}s"
        exit_code = -2
    except Exception as e:
        stderr_buf = f"runner_exception: {e}"
        exit_code = -3

    duration = time.monotonic() - start
    return {
        "exit_code": exit_code,
        "duration_sec": round(duration, 1),
        "verdict_present": verdict_present,
        "stderr_class": classify_stderr(stderr_buf),
        "tokens_used": None,  # codex CLI doesn't expose this directly
        "stdout_tail": stdout_buf[-500:],
        "stderr_tail": stderr_buf[-500:],
    }


def is_trial_success(trial: dict) -> bool:
    return trial["exit_code"] == 0 and trial["verdict_present"]


def stability_verdict(trials: list[dict]) -> str:
    successes = sum(1 for t in trials if is_trial_success(t))
    total = len(trials)
    if successes == total and total > 0:
        return "stable"
    if successes == 0:
        return "unstable"
    return "inconclusive"


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

def smoke_xhigh_short(n_trials: int, budget: dict, output_dir: Path) -> dict:
    """Smoke 1: Ultra-short prompt + gpt-5.5 + xhigh (default config)."""
    print("[preflight] smoke: xhigh_short", flush=True)
    trials = []
    for i in range(n_trials):
        if budget["xhigh_calls_used"] >= budget["xhigh_calls_max"]:
            print(f"  [budget exhausted at trial {i}]", flush=True)
            budget["exhausted"] = True
            break
        print(f"  trial {i+1}/{n_trials}...", end=" ", flush=True)
        trial = run_codex(SHORT_PROMPT, model="gpt-5.5", reasoning="xhigh",
                          sandbox="read-only", timeout=120)
        budget["xhigh_calls_used"] += 1
        trials.append(trial)
        status = "OK" if is_trial_success(trial) else f"FAIL({trial['stderr_class']})"
        print(f"{trial['duration_sec']}s {status}", flush=True)
    return {"id": "xhigh_short", "trials": trials,
            "stability_verdict": stability_verdict(trials)}


def smoke_xhigh_real_capsule(capsule_path: str, n_trials: int, budget: dict, output_dir: Path) -> dict:
    """Smoke 2: Real 50KB capsule + xhigh (default config)."""
    print("[preflight] smoke: xhigh_real_capsule", flush=True)
    trials = []
    for i in range(n_trials):
        if budget["xhigh_calls_used"] >= budget["xhigh_calls_max"]:
            budget["exhausted"] = True
            print(f"  [budget exhausted at trial {i}]", flush=True)
            break
        print(f"  trial {i+1}/{n_trials}...", end=" ", flush=True)
        trial = run_codex(capsule_path, from_file=True,
                          model="gpt-5.5", reasoning="xhigh",
                          sandbox="read-only", timeout=300)
        budget["xhigh_calls_used"] += 1
        trials.append(trial)
        status = "OK" if is_trial_success(trial) else f"FAIL({trial['stderr_class']})"
        print(f"{trial['duration_sec']}s {status}", flush=True)
    return {"id": "xhigh_real_capsule", "trials": trials,
            "stability_verdict": stability_verdict(trials)}


def smoke_high_real_capsule(capsule_path: str, output_dir: Path) -> dict:
    """Smoke 3: Same capsule + high (control group, no budget cost)."""
    print("[preflight] smoke: high_real_capsule (control, 1 trial)", flush=True)
    trial = run_codex(capsule_path, from_file=True,
                      model="gpt-5.5", reasoning="high",
                      sandbox="read-only", timeout=300)
    status = "OK" if is_trial_success(trial) else f"FAIL({trial['stderr_class']})"
    print(f"  {trial['duration_sec']}s {status}", flush=True)
    return {"id": "high_real_capsule", "trials": [trial],
            "stability_verdict": stability_verdict([trial])}


def smoke_config_matrix(capsule_path: str, budget: dict, output_dir: Path) -> dict:
    """Smoke 4: Config variations to isolate MCP/plugin overhead."""
    print("[preflight] smoke: config_matrix", flush=True)
    # Subtest definitions
    subtests = [
        {
            "id": "default",
            "desc": "Default config (plugins + xhigh from ~/.codex/config.toml)",
            "extra_flags": [],
        },
        {
            "id": "ignore_user_config",
            "desc": "--ignore-user-config (no plugins, no xhigh default)",
            # When --ignore-user-config, model/reasoning must be explicit
            "extra_flags": ["--ignore-user-config"],
        },
        {
            "id": "ignore_rules",
            "desc": "--ignore-rules (no .rules exec policy files)",
            "extra_flags": ["--ignore-rules"],
        },
        {
            "id": "clean_home",
            "desc": "Fresh CODEX_HOME via env override (minimal config)",
            "extra_flags": ["--ignore-user-config"],  # same as ignore_user_config for now
            "env_extra": {"CODEX_HOME": str(output_dir / "clean_codex_home")},
        },
    ]

    sub_results = []
    for st in subtests:
        if budget["xhigh_calls_used"] >= budget["xhigh_calls_max"]:
            budget["exhausted"] = True
            print(f"  [budget exhausted, skipping {st['id']}]", flush=True)
            sub_results.append({"id": st["id"], "desc": st["desc"],
                                 "stability_verdict": "inconclusive",
                                 "trials": [], "note": "budget_exhausted"})
            continue
        print(f"  [{st['id']}]...", end=" ", flush=True)
        # Use short prompt for matrix (faster, cheaper)
        env_extra = st.get("env_extra", {})
        env = {**os.environ, **env_extra}
        cmd = [CODEX_BIN, "exec", "-m", "gpt-5.5",
               "-c", "model_reasoning_effort=xhigh",
               "-s", "read-only"] + st["extra_flags"] + [SHORT_PROMPT]
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=120, env=env)
            trial = {
                "exit_code": proc.returncode,
                "duration_sec": round(time.monotonic() - start, 1),
                "verdict_present": has_verdict(proc.stdout or ""),
                "stderr_class": classify_stderr(proc.stderr or ""),
                "tokens_used": None,
                "stdout_tail": (proc.stdout or "")[-300:],
                "stderr_tail": (proc.stderr or "")[-300:],
            }
        except subprocess.TimeoutExpired:
            trial = {
                "exit_code": -2, "duration_sec": 120.0,
                "verdict_present": False, "stderr_class": "exec_timeout",
                "tokens_used": None, "stdout_tail": "", "stderr_tail": "timeout",
            }
        budget["xhigh_calls_used"] += 1
        sv = stability_verdict([trial])
        print(f"{trial['duration_sec']}s {sv}", flush=True)
        sub_results.append({"id": st["id"], "desc": st["desc"],
                             "stability_verdict": sv, "trials": [trial]})

    # Overall verdict: stable if any subtest is stable with isolation flag
    any_isolated_stable = any(
        s["stability_verdict"] == "stable" and s["id"] != "default"
        for s in sub_results
    )
    clean_home_stable = next(
        (s["stability_verdict"] == "stable" for s in sub_results if s["id"] == "clean_home"),
        False
    )
    overall = "stable" if clean_home_stable else (
        "inconclusive" if any_isolated_stable else "unstable"
    )
    return {"id": "config_matrix", "subtests": sub_results,
            "stability_verdict": overall,
            "any_isolated_stable": any_isolated_stable,
            "clean_home_stable": clean_home_stable}


# ---------------------------------------------------------------------------
# Route decision
# ---------------------------------------------------------------------------

def decide_route(smokes: list[dict]) -> tuple[str, str]:
    by_id = {s["id"]: s for s in smokes}
    xhigh_short = by_id.get("xhigh_short", {})
    xhigh_real = by_id.get("xhigh_real_capsule", {})
    config_mx = by_id.get("config_matrix", {})

    short_sv = xhigh_short.get("stability_verdict", "inconclusive")
    real_sv = xhigh_real.get("stability_verdict", "inconclusive")
    clean_home_stable = config_mx.get("clean_home_stable", False)

    if short_sv in ("unstable", "inconclusive"):
        if clean_home_stable:
            return "config_isolation", (
                "xhigh_short unstable/inconclusive, but clean_home stable → "
                "MCP/plugin overhead is culprit; config isolation should fix bridge"
            )
        return "escalate_outside_scope", (
            "xhigh_short unstable/inconclusive even with clean_home → "
            "Codex CLI xhigh itself is broken in this environment; "
            "fix is outside GD scope (Codex upstream / account / model backend)"
        )
    if real_sv == "unstable":
        return "shard", (
            "xhigh_short stable but real 50KB capsule unstable → "
            "capsule size triggers instability; split capsule into shards"
        )
    if real_sv == "stable":
        return "no_fix_needed_or_intermittent", (
            "Both xhigh_short and xhigh_real_capsule stable in direct mode → "
            "problem may have been intermittent or daemon-specific; "
            "recommend monitoring + optional daemon bypass"
        )
    return "inconclusive", "Insufficient trial data to determine route"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capsule", required=True,
                   help="Path to the archived failure capsule (.capsule file)")
    p.add_argument("--output-dir", required=True,
                   help="Directory to write preflight-report.json and decision.md")
    p.add_argument("--max-xhigh-calls", type=int, default=15,
                   help="Hard budget limit for xhigh codex calls (default 15)")
    p.add_argument("--n-trials", type=int, default=3,
                   help="Trials per xhigh smoke (default 3; 3/3=stable, 0/3=unstable)")
    p.add_argument("--skip-real-capsule", action="store_true",
                   help="Skip xhigh_real_capsule smoke (saves budget if short smoke fails)")
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    capsule_path = args.capsule

    if not Path(capsule_path).exists():
        print(f"ERROR: capsule not found: {capsule_path}", file=sys.stderr)
        return 2

    budget = {
        "xhigh_calls_max": args.max_xhigh_calls,
        "xhigh_calls_used": 0,
        "exhausted": False,
    }

    started_at = now_iso()

    # Step 0: Verify codex exec can start at all (no xhigh, no budget cost)
    print("[preflight] step-0: verify codex exec startup...", flush=True)
    echo_result = subprocess.run(
        [CODEX_BIN, "exec", "--help"], capture_output=True, text=True, timeout=10
    )
    if echo_result.returncode != 0 and "exec" not in (echo_result.stdout + echo_result.stderr):
        print("FATAL: codex exec is not available or broken", file=sys.stderr)
        return 2
    print("  codex exec: available", flush=True)

    smokes: list[dict] = []

    # Smoke 1: xhigh short
    s1 = smoke_xhigh_short(args.n_trials, budget, out_dir)
    smokes.append(s1)

    # Smoke 4: config_matrix (run in parallel intent — actually sequential but lightweight)
    s4 = smoke_config_matrix(capsule_path, budget, out_dir)
    smokes.append(s4)

    # Smoke 2: xhigh real capsule (skip if budget exhausted or short already failed)
    if not args.skip_real_capsule and not budget["exhausted"]:
        s2 = smoke_xhigh_real_capsule(capsule_path, args.n_trials, budget, out_dir)
        smokes.append(s2)
    else:
        smokes.append({"id": "xhigh_real_capsule", "trials": [],
                        "stability_verdict": "inconclusive",
                        "note": "skipped (budget or --skip-real-capsule)"})

    # Smoke 3: high control (no budget cost)
    s3 = smoke_high_real_capsule(capsule_path, out_dir)
    smokes.append(s3)

    # Route decision
    route, evidence = decide_route(smokes)
    print(f"[preflight] route_decision: {route}", flush=True)
    print(f"[preflight] evidence: {evidence}", flush=True)

    ended_at = now_iso()

    report = {
        "preflight_version": "1.0",
        "started_at": started_at,
        "ended_at": ended_at,
        "capsule_path": capsule_path,
        "budget": budget,
        "smokes": smokes,
        "route_decision": route,
        "decision_evidence": evidence,
    }

    report_path = out_dir / "preflight-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[preflight] report written: {report_path}", flush=True)

    # Decision doc
    decision_md = f"""# Bridge Preflight Decision

Date: {ended_at}
Capsule: {capsule_path}

## Route Decision

**{route}**

{evidence}

## Budget

- xhigh calls used: {budget["xhigh_calls_used"]} / {budget["xhigh_calls_max"]}
- Budget exhausted: {budget["exhausted"]}

## Next Steps

See plans/bridge-fix-v3.1 for route-specific implementation.
"""
    (out_dir / "decision.md").write_text(decision_md, encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
