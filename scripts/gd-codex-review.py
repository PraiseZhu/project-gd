#!/usr/bin/env python3
# DEPRECATED: Plan 6 v3 direct codex exec sidecar; replaced by Plan 6.5-B bridge candidate
#             (scripts/gd-codex-bridge-review.py). Kept for audit/recovery; do not use in
#             active /gd workflow. Manifest revisions[1.3.0] = completed_with_constraint.
#             /gd review standard §8.0 / §8.9 documents the deprecation.
# Plan 6 v3 — Codex sidecar runner（stdlib-only）
# scripts/gd-codex-review.py — /gd Codex cross-review sidecar
#
# 子命令：
#   build-capsule --kind plan|code --target <path> [--out <out_path>]
#       拼接 review capsule（目标文件 + goal chain + review standard + 对应 review template）
#   run-codex --capsule <capsule_path> [--root <project_root>] [--timeout <sec>]
#       调用 codex exec --ephemeral --sandbox read-only --skip-git-repo-check --cd <root> -
#       默认 timeout 240s，可由 --timeout 或 GD_CODEX_TIMEOUT 覆盖
#       command missing / non-zero / timeout → 输出 failed_to_run JSON
#   parse <raw_review.md> [--kind plan|code]
#       提取唯一 gd-review-result-json block，schema 校验，拒绝裸 VERDICT:/REV_VERDICT:
#   merge <claude.json> <codex.json>
#       按 prompts/gd-review-standard.md §8.1 Merge Matrix 合并；输出 merged JSON
#
# 路径规则：
#   - capsule / output 都在 Project GD 内
#   - 不写 ~/.claude/**
#   - 不调用 codex-send-wait / review-result-writer.sh / codex-watch
#
# Exit codes:
#   0 = pass
#   1 = parse / schema / merge fail (FAILED verdict)
#   2 = usage error / file not found

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ----------------------------- Constants ----------------------------- #

GD_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = GD_PROJECT_ROOT / "schema" / "gd-review-result.schema.json"
STANDARD_PATH = GD_PROJECT_ROOT / "prompts" / "gd-review-standard.md"
GOAL_PATH = GD_PROJECT_ROOT / "docs" / "gd-v7-project-goal.md"
TEMPLATE_BY_KIND = {
    "plan": GD_PROJECT_ROOT / "templates" / "gd-plan-review-template.md",
    "code": GD_PROJECT_ROOT / "templates" / "gd-execution-review-template.md",
}

JSON_BLOCK_RE = re.compile(
    r"<!--\s*gd-review-result-json:start\s*-->(.*?)<!--\s*gd-review-result-json:end\s*-->",
    re.DOTALL,
)
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
BARE_VERDICT_RE = re.compile(r"^\s*(VERDICT|REV_VERDICT)\s*:", re.MULTILINE)

VALID_REVIEWERS = {"claude_main", "codex"}  # plus claude_subagent_*
VALID_REVIEW_KINDS = {"plan", "code"}
VALID_RUN_STATUS = {"completed", "completed_with_constraint", "degraded", "failed_to_run"}
VALID_DECISIONS = {"APPROVED", "REQUIRES_CHANGES", "FAILED"}
VALID_SCOPE_RESULTS = {"pass", "fail", "n_a"}
VALID_SEVERITIES = {"P1", "P2"}

DEFAULT_TIMEOUT = 240
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


# ----------------------------- Helpers ----------------------------- #


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _failed_run_result(reviewer: str, kind: str, target: str, reason: str) -> dict:
    """生成 failed_to_run 的可解析 JSON（用于 run-codex 失败场景）。"""
    return {
        "template_kind": "gd-plan-review" if kind == "plan" else "gd-execution-review",
        "reviewer": reviewer,
        "review_target": target,
        "review_kind": kind,
        "review_run_status": "failed_to_run",
        "gd_review_decision": "FAILED",
        "scope_checked": [
            {"facet": "sidecar runtime", "result": "fail", "evidence": reason[:60]}
        ],
        "findings": [],
        "merge_notes": {
            "conflict_with_other_reviewer": False,
            "degraded_reason": reason,
        },
        "residual_risk": [],
        "timestamp": _now_iso(),
    }


# ----------------------------- Schema validator (stdlib-only) ----------------------------- #


def _is_valid_reviewer(s: str) -> bool:
    return s in VALID_REVIEWERS or bool(re.match(r"^claude_subagent_[a-z0-9_]+$", s))


def validate_review_result(d: dict) -> list[str]:
    """手写 schema 校验（与 gd-review-result.schema.json 对齐，stdlib-only）。"""
    errs: list[str] = []
    if not isinstance(d, dict):
        return ["顶层不是 JSON object"]

    required = [
        "template_kind", "reviewer", "review_target", "review_kind",
        "review_run_status", "gd_review_decision", "scope_checked",
        "findings", "merge_notes", "timestamp",
    ]
    for f in required:
        if f not in d:
            errs.append(f"缺字段: {f}")
    if errs:
        return errs

    if d["template_kind"] not in {"gd-plan-review", "gd-execution-review"}:
        errs.append(f"template_kind 不合法: {d['template_kind']!r}")
    if not _is_valid_reviewer(d["reviewer"]):
        errs.append(f"reviewer 不合法: {d['reviewer']!r}")
    if not isinstance(d["review_target"], str) or not d["review_target"]:
        errs.append("review_target 必须是非空字符串")
    if d["review_kind"] not in VALID_REVIEW_KINDS:
        errs.append(f"review_kind 不合法: {d['review_kind']!r}")
    if d["review_run_status"] not in VALID_RUN_STATUS:
        errs.append(f"review_run_status 不合法: {d['review_run_status']!r}")
    if d["gd_review_decision"] not in VALID_DECISIONS:
        errs.append(f"gd_review_decision 不合法: {d['gd_review_decision']!r}")

    if not TIMESTAMP_RE.match(str(d.get("timestamp", ""))):
        errs.append(f"timestamp 不是 ISO 8601 UTC: {d.get('timestamp')!r}")

    sc = d["scope_checked"]
    if not isinstance(sc, list) or not sc:
        errs.append("scope_checked 必须是非空数组")
    else:
        for i, item in enumerate(sc):
            if not isinstance(item, dict):
                errs.append(f"scope_checked[{i}] 必须是 object")
                continue
            for f in ["facet", "result"]:
                if f not in item:
                    errs.append(f"scope_checked[{i}] 缺 {f}")
            if "facet" in item and (not isinstance(item["facet"], str) or len(item["facet"]) < 3):
                errs.append(f"scope_checked[{i}].facet 长度 < 3")
            if "result" in item and item["result"] not in VALID_SCOPE_RESULTS:
                errs.append(f"scope_checked[{i}].result 不合法: {item['result']!r}")

    findings = d["findings"]
    if not isinstance(findings, list):
        errs.append("findings 必须是数组")
    else:
        for i, fd in enumerate(findings):
            if not isinstance(fd, dict):
                errs.append(f"findings[{i}] 必须是 object")
                continue
            for f in ["severity", "title", "sc_refs", "evidence", "impact", "required_fix", "verify"]:
                if f not in fd:
                    errs.append(f"findings[{i}] 缺 {f}")
            if "severity" in fd and fd["severity"] not in VALID_SEVERITIES:
                errs.append(f"findings[{i}].severity 不合法: {fd['severity']!r}")
            if "sc_refs" in fd:
                if not isinstance(fd["sc_refs"], list) or not fd["sc_refs"]:
                    errs.append(f"findings[{i}].sc_refs 必须是非空数组")
                else:
                    for sc_ref in fd["sc_refs"]:
                        if not isinstance(sc_ref, str) or not re.match(r"^SC-\d+$", sc_ref):
                            errs.append(f"findings[{i}].sc_refs 含不合法值: {sc_ref!r}")
            for f in ["title", "evidence", "impact", "required_fix", "verify"]:
                if f in fd and (not isinstance(fd[f], str) or len(fd[f]) < 5):
                    errs.append(f"findings[{i}].{f} 长度 < 5")

    mn = d["merge_notes"]
    if not isinstance(mn, dict):
        errs.append("merge_notes 必须是 object")
    elif "conflict_with_other_reviewer" not in mn:
        errs.append("merge_notes 缺 conflict_with_other_reviewer")

    return errs


# ----------------------------- build-capsule ----------------------------- #


def cmd_build_capsule(args: argparse.Namespace) -> int:
    kind = args.kind
    if kind not in TEMPLATE_BY_KIND:
        print(f"错误: --kind 必须是 plan 或 code，得到 {kind!r}", file=sys.stderr)
        return 2

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"错误: target 文件不存在 {target_path}", file=sys.stderr)
        return 2

    template_path = TEMPLATE_BY_KIND[kind]
    for p in [STANDARD_PATH, template_path]:
        if not p.exists():
            print(f"错误: 必读 artifact 缺失 {p}", file=sys.stderr)
            return 2

    standard = STANDARD_PATH.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")
    target_content = target_path.read_text(encoding="utf-8")
    goal = GOAL_PATH.read_text(encoding="utf-8") if GOAL_PATH.exists() else "(goal source missing)"

    capsule = (
        f"# /gd Codex Sidecar Review Capsule\n\n"
        f"REVIEW_KIND: {kind}\n"
        f"REVIEW_TARGET: {target_path}\n"
        f"GENERATED_AT: {_now_iso()}\n\n"
        f"## Goal Chain\n\n```\n{goal[:4000]}\n```\n\n"
        f"## Review Standard (gd-review-standard.md)\n\n```\n{standard}\n```\n\n"
        f"## Review Template ({template_path.name})\n\n```\n{template}\n```\n\n"
        f"## Target Artifact ({target_path})\n\n```\n{target_content}\n```\n\n"
        f"## Reviewer Instructions\n\n"
        f"- 你是 Codex sidecar reviewer\n"
        f"- 仅按 §Review Standard 给出 review 结论\n"
        f"- 输出必须按 §Review Template 第 6 节填充唯一 `gd-review-result-json` block\n"
        f"- reviewer 字段填 `codex`\n"
        f"- 禁止裸 `VERDICT:` 或 `REV_VERDICT:`\n"
    )

    if args.out:
        Path(args.out).write_text(capsule, encoding="utf-8")
        print(f"capsule 写入: {args.out}")
    else:
        sys.stdout.write(capsule)
    return 0


# ----------------------------- run-codex ----------------------------- #


def cmd_run_codex(args: argparse.Namespace) -> int:
    capsule_path = Path(args.capsule)
    if not capsule_path.exists():
        print(f"错误: capsule 不存在 {capsule_path}", file=sys.stderr)
        return 2

    root = Path(args.root) if args.root else GD_PROJECT_ROOT
    timeout = int(args.timeout or os.environ.get("GD_CODEX_TIMEOUT", DEFAULT_TIMEOUT))

    capsule_text = capsule_path.read_text(encoding="utf-8")
    cmd = [
        "codex", "exec", "--ephemeral",
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "--cd", str(root),
        "-",
    ]

    try:
        result = subprocess.run(
            cmd,
            input=capsule_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        failed = _failed_run_result(
            "codex", "plan", str(capsule_path), "codex CLI 不存在"
        )
        if args.out:
            Path(args.out).write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            sys.stdout.write(json.dumps(failed, ensure_ascii=False, indent=2) + "\n")
        return 1
    except subprocess.TimeoutExpired:
        failed = _failed_run_result(
            "codex", "plan", str(capsule_path), f"codex 超时 (>{timeout}s)"
        )
        if args.out:
            Path(args.out).write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            sys.stdout.write(json.dumps(failed, ensure_ascii=False, indent=2) + "\n")
        return 1

    if result.returncode != 0:
        failed = _failed_run_result(
            "codex", "plan", str(capsule_path),
            f"codex non-zero exit {result.returncode}: {result.stderr[:200]}"
        )
        if args.out:
            Path(args.out).write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            sys.stdout.write(json.dumps(failed, ensure_ascii=False, indent=2) + "\n")
        return 1

    if args.out:
        Path(args.out).write_text(result.stdout, encoding="utf-8")
        print(f"codex 输出写入: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(result.stdout)
    return 0


# ----------------------------- parse ----------------------------- #


def cmd_parse(args: argparse.Namespace) -> int:
    raw_path = Path(args.raw)
    if not raw_path.exists():
        print(f"错误: raw 文件不存在 {raw_path}", file=sys.stderr)
        return 2

    raw = raw_path.read_text(encoding="utf-8")

    # 拒绝裸 VERDICT: / REV_VERDICT:
    bare = BARE_VERDICT_RE.search(raw)
    if bare:
        print(f"PARSE_FAIL: 含禁用字段 {bare.group(1)}: (line {raw[:bare.start()].count(chr(10))+1})", file=sys.stderr)
        return 1

    matches = JSON_BLOCK_RE.findall(raw)
    if len(matches) == 0:
        print("PARSE_FAIL: 缺 gd-review-result-json block", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print(f"PARSE_FAIL: 含多个 gd-review-result-json block (n={len(matches)})", file=sys.stderr)
        return 1

    block = matches[0].strip()
    # 允许 ```json fenced 或纯 JSON
    fence = JSON_FENCE_RE.search(block)
    if fence:
        block = fence.group(1).strip()

    try:
        data = json.loads(block)
    except json.JSONDecodeError as e:
        print(f"PARSE_FAIL: JSON 语法错误: {e}", file=sys.stderr)
        return 1

    errs = validate_review_result(data)
    if errs:
        print("PARSE_FAIL: schema 校验失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # --kind 校验（如果指定）
    if args.kind and data.get("review_kind") != args.kind:
        print(
            f"PARSE_FAIL: --kind={args.kind} 但 JSON review_kind={data.get('review_kind')!r}",
            file=sys.stderr,
        )
        return 1

    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"parse OK: {raw_path} → {args.out}")
    else:
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return 0


# ----------------------------- merge ----------------------------- #


def cmd_merge(args: argparse.Namespace) -> int:
    paths = [Path(args.claude), Path(args.codex)]
    for p in paths:
        if not p.exists():
            print(f"错误: 文件不存在 {p}", file=sys.stderr)
            return 2

    try:
        claude = json.loads(paths[0].read_text(encoding="utf-8"))
        codex = json.loads(paths[1].read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"MERGE_FAIL: JSON 语法错误: {e}", file=sys.stderr)
        return 1

    # 任一 schema fail → MERGED FAILED（matrix #5）
    for label, d in [("claude", claude), ("codex", codex)]:
        errs = validate_review_result(d)
        if errs:
            merged = {
                "merged_decision": "FAILED",
                "merged_run_status": "failed_to_run",
                "merge_reason": f"{label} input schema fail: {errs[0]}",
                "claude": claude,
                "codex": codex,
                "timestamp": _now_iso(),
            }
            sys.stdout.write(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
            return 1

    decisions = [claude["gd_review_decision"], codex["gd_review_decision"]]
    statuses = [claude["review_run_status"], codex["review_run_status"]]

    # Matrix #3: 任一 FAILED → FAILED (priority 最高)
    if "FAILED" in decisions:
        merged_decision = "FAILED"
        merged_status = "failed_to_run" if "failed_to_run" in statuses else "completed"
        reason = "matrix #3: 任一 reviewer FAILED"
    # Matrix #2: 任一 REQUIRES_CHANGES
    elif "REQUIRES_CHANGES" in decisions:
        merged_decision = "REQUIRES_CHANGES"
        merged_status = "completed_with_constraint" if any(s in {"degraded", "failed_to_run"} for s in statuses) else "completed"
        reason = "matrix #2: 任一 reviewer REQUIRES_CHANGES"
    # Matrix #4: degraded/failed_to_run + 无更严重 verdict → completed_with_constraint
    elif any(s in {"degraded", "failed_to_run"} for s in statuses):
        merged_decision = "REQUIRES_CHANGES"  # 不得 APPROVED；按 §7 不能 APPROVED 但也不是 FAILED
        merged_status = "completed_with_constraint"
        reason = "matrix #4: 任一 reviewer degraded/failed_to_run，不得 APPROVED"
    # Matrix #1: 全 APPROVED + 全 completed
    elif all(d == "APPROVED" for d in decisions) and all(s == "completed" for s in statuses):
        merged_decision = "APPROVED"
        merged_status = "completed"
        reason = "matrix #1: 全部 APPROVED + completed"
    else:
        merged_decision = "FAILED"
        merged_status = "failed_to_run"
        reason = f"unknown matrix combination: decisions={decisions}, statuses={statuses}"

    merged = {
        "merged_decision": merged_decision,
        "merged_run_status": merged_status,
        "merge_reason": reason,
        "claude": claude,
        "codex": codex,
        "timestamp": _now_iso(),
    }
    sys.stdout.write(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
    return 0 if merged_decision == "APPROVED" else (1 if merged_decision == "FAILED" else 0)


# ----------------------------- main ----------------------------- #


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="/gd Codex Sidecar Runner (Plan 6 v3)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build-capsule", help="拼接 review capsule")
    p_build.add_argument("--kind", required=True, choices=["plan", "code"])
    p_build.add_argument("--target", required=True, help="待 review 文件路径")
    p_build.add_argument("--out", help="输出路径；省略则写 stdout")

    p_run = sub.add_parser("run-codex", help="调用 codex CLI")
    p_run.add_argument("--capsule", required=True)
    p_run.add_argument("--root", help="codex --cd 根；默认 Project GD root")
    p_run.add_argument("--timeout", type=int, help=f"秒；默认 {DEFAULT_TIMEOUT} 或 GD_CODEX_TIMEOUT")
    p_run.add_argument("--out", help="输出 codex 原文路径；省略则写 stdout")

    p_parse = sub.add_parser("parse", help="提取并校验 gd-review-result-json block")
    p_parse.add_argument("raw", help="原始 review markdown 文件")
    p_parse.add_argument("--kind", choices=["plan", "code"], help="校验 review_kind 字段")
    p_parse.add_argument("--out", help="输出已 parse JSON 路径；省略则写 stdout")

    p_merge = sub.add_parser("merge", help="合并 Claude + Codex 两份 review JSON")
    p_merge.add_argument("claude", help="Claude review JSON")
    p_merge.add_argument("codex", help="Codex review JSON")

    args = parser.parse_args(argv[1:])

    if args.cmd == "build-capsule":
        return cmd_build_capsule(args)
    if args.cmd == "run-codex":
        return cmd_run_codex(args)
    if args.cmd == "parse":
        return cmd_parse(args)
    if args.cmd == "merge":
        return cmd_merge(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
