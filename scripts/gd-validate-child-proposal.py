#!/usr/bin/env python3
# Plan 6.5-C candidate — child planner proposal validator (stdlib-only)
# scripts/gd-validate-child-proposal.py
#
# 用途：校验 child planner 输出的 gd-child-plan-proposal-json block
#       或裸 JSON 文件，按 schema/gd-child-plan-proposal.schema.json 校验。
#
# CLI:
#   python3 scripts/gd-validate-child-proposal.py <input>
#     input: .json 文件 → 直接 JSON
#            .md 文件 → 提取 <!-- gd-child-plan-proposal-json:start --> ... :end --> block
#
# Exit:
#   0 = pass
#   1 = schema/semantic fail
#   2 = usage error / 文件不存在 / JSON 语法错误

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROPOSAL_BLOCK_RE = re.compile(
    r"<!--\s*gd-child-plan-proposal-json:start\s*-->(.*?)<!--\s*gd-child-plan-proposal-json:end\s*-->",
    re.DOTALL,
)
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
ANTI_FILL_KEYWORDS = ["见上文", "按之前讨论", "接续刚才的任务", "完善", "优化", "全面", "系统性", "增强"]
SC_REF_RE = re.compile(r"^SC-[0-9]+$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def validate(d: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(d, dict):
        return ["顶层不是 JSON object"]

    required = [
        "proposal_id", "parent_dispatch_id", "parent_track_id", "agent_role",
        "output_status", "summary_cn", "task_packets", "sc_refs", "verify",
        "blocked_reason",
    ]
    for f in required:
        if f not in d:
            errs.append(f"缺字段 {f}")
    allowed = set(required)
    for f in d:
        if f not in allowed:
            errs.append(f"多余字段 {f}（schema additionalProperties=false）")
    if errs:
        return errs

    if d["agent_role"] != "child_planner":
        errs.append(f"agent_role 必须为 child_planner，实际 {d['agent_role']!r}")
    if d["output_status"] not in {"completed", "blocked_missing_context", "blocked_other"}:
        errs.append(f"output_status 不合法: {d['output_status']!r}")

    for f in ["proposal_id"]:
        if not ID_RE.match(str(d[f])):
            errs.append(f"{f} 格式不合法: {d[f]!r}")
    for f in ["parent_dispatch_id", "parent_track_id"]:
        if not isinstance(d[f], str) or not d[f]:
            errs.append(f"{f} 必须非空字符串")

    if not isinstance(d["summary_cn"], str) or not d["summary_cn"]:
        errs.append("summary_cn 必须非空")
    else:
        for kw in ANTI_FILL_KEYWORDS[:3]:
            if kw in d["summary_cn"]:
                errs.append(f"summary_cn 含 anti-fill 占位词 {kw!r}")

    # output_status 条件字段
    status = d["output_status"]
    if status == "completed":
        if not isinstance(d["task_packets"], list) or not d["task_packets"]:
            errs.append("output_status=completed 但 task_packets 为空")
        if not isinstance(d["sc_refs"], list) or not d["sc_refs"]:
            errs.append("output_status=completed 但 sc_refs 为空")
        if not isinstance(d["verify"], list) or not d["verify"]:
            errs.append("output_status=completed 但 verify 为空")
        if d["blocked_reason"] is not None:
            errs.append("output_status=completed 但 blocked_reason 非 null")
    else:
        br = d["blocked_reason"]
        if not isinstance(br, str) or len(br) < 10:
            errs.append(f"output_status={status!r} 时 blocked_reason 必须 ≥10 字符")

    # task_packets
    if isinstance(d["task_packets"], list):
        for i, tp in enumerate(d["task_packets"]):
            if not isinstance(tp, dict):
                errs.append(f"task_packets[{i}] 不是 object")
                continue
            for k in ["task_id", "owned_paths", "required_context"]:
                if k not in tp:
                    errs.append(f"task_packets[{i}] 缺 {k}")
            if "task_id" in tp and not ID_RE.match(str(tp["task_id"])):
                errs.append(f"task_packets[{i}].task_id 格式不合法: {tp['task_id']!r}")
            if "owned_paths" in tp:
                if not isinstance(tp["owned_paths"], list) or not tp["owned_paths"]:
                    errs.append(f"task_packets[{i}].owned_paths 必须非空数组")
                else:
                    for p in tp["owned_paths"]:
                        if not isinstance(p, str) or not p:
                            errs.append(f"task_packets[{i}].owned_paths 含非法路径")
                        elif p.startswith(
                            os.path.expanduser("~/.claude")
                        ) or ".." in p.split("/"):
                            errs.append(f"task_packets[{i}].owned_paths 含越界 / 穿越路径: {p!r}")

    # sc_refs
    if isinstance(d["sc_refs"], list):
        for sc in d["sc_refs"]:
            if not isinstance(sc, str) or not SC_REF_RE.match(sc):
                errs.append(f"sc_refs 含不合法值 {sc!r}")

    # verify
    if isinstance(d["verify"], list):
        for i, v in enumerate(d["verify"]):
            if not isinstance(v, dict):
                errs.append(f"verify[{i}] 不是 object")
                continue
            for k in ["sc_ref", "method", "cmd"]:
                if k not in v:
                    errs.append(f"verify[{i}] 缺 {k}")
            if "sc_ref" in v and not (isinstance(v["sc_ref"], str) and SC_REF_RE.match(v["sc_ref"])):
                errs.append(f"verify[{i}].sc_ref 不合法 {v.get('sc_ref')!r}")
            if "method" in v and v["method"] not in {"command", "path", "assertion", "test"}:
                errs.append(f"verify[{i}].method 不合法 {v['method']!r}")
            if "cmd" in v and (not isinstance(v["cmd"], str) or len(v["cmd"]) < 3):
                errs.append(f"verify[{i}].cmd 必须 ≥3 字符")
            for kw in ANTI_FILL_KEYWORDS[:3]:
                if isinstance(v.get("cmd"), str) and kw in v["cmd"]:
                    errs.append(f"verify[{i}].cmd 含 anti-fill 占位词 {kw!r}")

    return errs


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: python3 scripts/gd-validate-child-proposal.py <input.{json|md}>", file=sys.stderr)
        return 2
    p = Path(argv[1])
    if not p.exists():
        print(f"错误: 文件不存在 {p}", file=sys.stderr)
        return 2

    text = p.read_text(encoding="utf-8")
    if p.suffix == ".md":
        matches = PROPOSAL_BLOCK_RE.findall(text)
        if len(matches) == 0:
            print("PARSE_FAIL: 缺 gd-child-plan-proposal-json block", file=sys.stderr)
            return 1
        if len(matches) > 1:
            print(f"PARSE_FAIL: 含 {len(matches)} 个 gd-child-plan-proposal-json block", file=sys.stderr)
            return 1
        block = matches[0].strip()
        fence = JSON_FENCE_RE.search(block)
        if fence:
            block = fence.group(1).strip()
    else:
        block = text

    try:
        d = json.loads(block)
    except json.JSONDecodeError as e:
        print(f"JSON 语法错误: {e}", file=sys.stderr)
        return 1

    errs = validate(d)
    if errs:
        print("校验失败：")
        for e in errs:
            print(f"  - {e}")
        print(f"共 {len(errs)} 条违规。")
        return 1

    print(f"校验通过：proposal_id={d['proposal_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
