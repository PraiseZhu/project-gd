#!/usr/bin/env python3
"""gd-build-review2-capsule.py — Build a /review2 profile-aware Codex review capsule.

Usage:
  python3 scripts/gd-build-review2-capsule.py \
    --profile release_closure \
    --target <path>          # file or dir to review (optional for release_closure) \
    --cwd <path>             # project root (default: git rev-parse --show-toplevel) \
    --out-dir <dir>          # output directory for capsule + run-manifest

Profiles:
  code_diff        — standard code diff review (default)
  release_closure  — full release readiness review (includes git state, gate outputs)
  runtime_parity   — parity matrix review

Exit codes:
  0  — capsule built and validated
  1  — validation failure (incomplete inline_facts or mandatory_read)
  2  — environment error (not in git repo, required tool missing)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


PROFILES = {"code_diff", "plan_review", "release_closure", "runtime_parity"}

# --- Mandatory read lists per profile ---
MANDATORY_READ = {
    "plan_review": [],  # bridge sends original plan directly; no additional mandatory reads
    "release_closure": [
        {"path": "config/gd-runtime-parity-manifest.json",
         "reason": "SSOT for L1/L2/L3 bundle classification and must_include",
         "section_or_range": "bundles.* / top_level_classification"},
        {"path": "config/secret-scan-regexes.json",
         "reason": "Secret scan SSOT used by sync and release gate",
         "section_or_range": "patterns[*].regex"},
        {"path": "mirrors/codex-chain/sync-manifest.json",
         "reason": "Mirror freshness and manifest_only_metadata completeness",
         "section_or_range": "manifest_only_metadata / per_bucket_hash"},
        {"path": "tools/gd-codex-chain-release-status.sh",
         "reason": "Release gate logic: L1/L2/L3 checks, exit codes, SSOT loading",
         "section_or_range": "all"},
        {"path": "tools/gd-final-closure-status.sh",
         "reason": "Final status contract: MACHINE/HUMAN field declarations, aggregate",
         "section_or_range": "Runtime Parity Bundle Summary section"},
    ],
    "runtime_parity": [
        {"path": "config/gd-runtime-parity-manifest.json",
         "reason": "Parity manifest SSOT",
         "section_or_range": "bundles.*"},
        {"path": "tools/gd-parity-verify.sh",
         "reason": "Parity verify script implementation",
         "section_or_range": "all"},
        {"path": "tools/check-gd-command-parity.sh",
         "reason": "L3 install gate script",
         "section_or_range": "all"},
    ],
    "code_diff": [],  # capsule only contains diff; no mandatory reads by default
}


def run(cmd: list[str], cwd: Path, capture: bool = True) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=capture, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return "FILE_MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_root(cwd: Path) -> Path | None:
    rc, out = run(["git", "rev-parse", "--show-toplevel"], cwd)
    return Path(out) if rc == 0 else None


def collect_inline_facts_release_closure(cwd: Path) -> dict[str, str]:
    facts: dict[str, str] = {}

    # Git state
    _, staged = run(["git", "diff", "--cached", "--name-status"], cwd)
    _, unstaged = run(["git", "diff", "--name-status"], cwd)
    _, status_short = run(["git", "status", "--short"], cwd)
    facts["git_status_short"] = status_short or "(clean)"
    facts["staged_files"] = staged or "(none)"
    facts["unstaged_files"] = unstaged or "(none)"

    # Release gate summary
    gate_script = cwd / "tools" / "gd-codex-chain-release-status.sh"
    if gate_script.is_file():
        _, gate_out = run(["bash", str(gate_script)], cwd)
        # Extract key lines
        key_lines = [l for l in gate_out.splitlines()
                     if any(t in l for t in ("L1_RELEASE_STATUS", "L2_RELEASE_STATUS",
                                              "L3_RELEASE_STATUS", "OVERALL_RELEASE_STATUS",
                                              "mm_state", "untracked_release_files",
                                              "MANIFEST_SYNC_DRIFT", "SECRET_FOUND"))]
        facts["release_gate_summary"] = "\n".join(key_lines) or "(script not runnable)"
    else:
        facts["release_gate_summary"] = "(gd-codex-chain-release-status.sh not found)"

    # Final status summary
    final_script = cwd / "tools" / "gd-final-closure-status.sh"
    if final_script.is_file():
        _, final_out = run(["bash", str(final_script)], cwd)
        key_lines = [l for l in final_out.splitlines()
                     if any(t in l for t in ("GD_REPAIR_RESULT", "OVERALL_RELEASE_STATUS",
                                              "MACHINE_RELEASE_VERDICT_FIELD",
                                              "HUMAN_REPAIR_SUMMARY_FIELD",
                                              "AMBIGUITY_STATUS", "pass=", "fail="))]
        facts["final_status_summary"] = "\n".join(key_lines) or "(script not runnable)"
    else:
        facts["final_status_summary"] = "(gd-final-closure-status.sh not found)"

    return facts


def build_mandatory_read_section(cwd: Path, profile: str) -> list[dict]:
    items = MANDATORY_READ.get(profile, [])
    result = []
    for item in items:
        p = cwd / item["path"]
        result.append({
            "path": item["path"],
            "sha256": sha256_file(p),
            "reason": item["reason"],
            "section_or_range": item["section_or_range"],
            "exists": p.is_file(),
        })
    return result


def validate_capsule_data(profile: str, inline_facts: dict, mandatory_reads: list) -> list[str]:
    errors = []
    if profile == "release_closure":
        required_facts = ["git_status_short", "staged_files", "unstaged_files",
                          "release_gate_summary", "final_status_summary"]
        for f in required_facts:
            if not inline_facts.get(f):
                errors.append(f"missing required inline_fact: {f}")
        for mr in mandatory_reads:
            if not mr.get("exists"):
                errors.append(f"mandatory_read file missing: {mr['path']}")
    return errors


def render_capsule(profile: str, target: str | None, inline_facts: dict,
                   mandatory_reads: list, run_id: str) -> str:
    if profile == "plan_review":
        goal = "Review the plan for Goal-Driven completeness and anti-fill compliance."
    elif profile == "release_closure":
        goal = "Verify release readiness and correctness of the current worktree changes."
    else:
        goal = "Review code changes for correctness and quality."

    lines = [
        f"# /review2 Capsule — {run_id}",
        "",
        f"REVIEW_PROFILE: {profile}",
        f"REVIEW_GOAL: {goal}",
        "",
        "SCOPE:",
        "  - Changes in staged / working tree relative to HEAD",
        "  - Release gate correctness (L1/L2/L3 parity and mirror status)" if profile == "release_closure" else "  - Code correctness and style",
        "",
        "OUT_OF_SCOPE:",
        "  - /gd review core semantics (unchanged)",
        "  - ~/.claude/** runtime (not modified in this scope)",
        "  - mirrors/codex-chain as install source (read-only audit mirror)",
        "",
        "INLINE_FACTS:",
    ]
    for k, v in inline_facts.items():
        lines.append(f"  {k}:")
        for sub in v.splitlines():
            lines.append(f"    {sub}")
    lines.append("")

    if target:
        lines += ["REVIEW_TARGET:", f"  {target}", ""]
        if profile == "plan_review":
            target_hash = sha256_file(Path(target)) if Path(target).is_file() else "FILE_MISSING"
            lines += [f"REVIEW_TARGET_HASH: {target_hash}", ""]
            lines += ["BRIDGE_TARGET_POLICY: original_plan_only", ""]

    lines += [
        "MANDATORY_READ:",
    ]
    for mr in mandatory_reads:
        lines += [
            f"  - path: {mr['path']}",
            f"    sha256: {mr['sha256']}",
            f"    reason: {mr['reason']}",
            f"    section_or_range: {mr['section_or_range']}",
        ]
    lines.append("")

    lines += [
        "BLOCKING_CHECKS:" if profile == "release_closure" else "CHECKS:",
    ]
    if profile == "release_closure":
        lines += [
            "  - OVERALL_RELEASE_STATUS must be READY_FOR_COMMIT",
            "  - No mm_state or untracked_release_files",
            "  - Secret scan PASS in all mirror buckets",
            "  - manifest_only_metadata covers all 6 items (3 files + 3 dirs)",
            "  - No manifest_sync_drift (EXCLUDE/MANIFEST_ONLY files not in mirror)",
        ]
    else:
        lines += [
            "  - Code correctness and error handling",
            "  - No hardcoded paths or credentials",
            "  - Exit codes match documented contract",
        ]
    lines.append("")

    lines += [
        "OUTPUT_CONTRACT:",
        "  Format: Finding -> Evidence -> Root Cause -> Fix",
        "  Severity: P1 (blocker) | P2 (warning) | P3 (minor)",
        "",
        "  After findings, output mandatory read coverage as follows (one line per path):",
        "  MANDATORY_READ_COVERAGE:",
    ]
    for mr in mandatory_reads:
        lines.append(f"  - {mr['path']}: read")
    lines += [
        "  Allowed statuses: read | summarized_by_preflight | out_of_scope | missing",
        "  If out_of_scope, add: OUT_OF_SCOPE_REASON: <path>: <reason>",
        "  For release_closure: 'missing' is not allowed — it causes RELEASE_VERDICT: BLOCKED",
        "",
        "RELEASE_VERDICT_NOTE:",
        "  This capsule does NOT grant release approval.",
        "  L3_GD_REVIEW_SEMANTICS: unchanged",
        "  RELEASE_VERDICT: NOT_APPLICABLE (unless profile=release_closure with full evidence contract)",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Build /review2 profile-aware capsule")
    p.add_argument("--profile", default="code_diff", choices=sorted(PROFILES),
                   help="Review profile: plan_review | code_diff | release_closure | runtime_parity")
    p.add_argument("--target", default=None, help="File or directory to review")
    p.add_argument("--cwd", default=None, help="Project root (default: git root)")
    p.add_argument("--out-dir", required=True, help="Output directory")
    args = p.parse_args()

    # plan_review requires --target (original plan file)
    if args.profile == "plan_review":
        if not args.target:
            print("PLAN_REVIEW_TARGET_REQUIRED: --profile plan_review requires --target <plan-file>",
                  file=sys.stderr)
            return 1
        target_path = Path(args.target)
        if not target_path.exists():
            print(f"PLAN_REVIEW_TARGET_NOT_FOUND: target file does not exist: {args.target}",
                  file=sys.stderr)
            return 1

    # Resolve cwd
    cwd = Path(args.cwd) if args.cwd else Path.cwd()
    git_r = git_root(cwd)
    if git_r:
        cwd = git_r

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Collect inline facts
    if args.profile == "release_closure":
        inline_facts = collect_inline_facts_release_closure(cwd)
    else:
        inline_facts = {}
        if args.target:
            inline_facts["target"] = args.target

    # Build mandatory reads
    mandatory_reads = build_mandatory_read_section(cwd, args.profile)

    # Validate
    errors = validate_capsule_data(args.profile, inline_facts, mandatory_reads)
    if errors:
        print("CAPSULE_BUILD_FAIL")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    # Render capsule
    capsule_text = render_capsule(args.profile, args.target, inline_facts,
                                  mandatory_reads, run_id)
    capsule_path = out_dir / "capsule.md"
    capsule_path.write_text(capsule_text, encoding="utf-8")
    capsule_sha = hashlib.sha256(capsule_text.encode()).hexdigest()

    # Write run-manifest.json
    run_manifest = {
        "run_id": run_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "profile": args.profile,
        "artifacts": [
            {
                "path": str(capsule_path),
                "sha256": capsule_sha,
                "kind": "capsule",
                "commit_policy": "optional_committed",
            }
        ],
    }
    manifest_path = out_dir / "run-manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    print(f"CAPSULE_BUILD_PASS")
    print(f"RUN_ID: {run_id}")
    print(f"PROFILE: {args.profile}")
    print(f"CAPSULE_PATH: {capsule_path}")
    print(f"CAPSULE_SHA256: {capsule_sha}")
    print(f"RUN_MANIFEST: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
