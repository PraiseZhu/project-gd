#!/usr/bin/env python3
# Plan 6.5-C candidate — owned-path audit (stdlib-only)
# scripts/gd-owned-path-audit.py
#
# 用途：post-wave audit 主 agent 校验 child executor 实际 changed paths
#       是否全部落在该 track owned_paths（或可选 wave union）内。
#
# CLI:
#   python3 scripts/gd-owned-path-audit.py \
#     --dispatch-map <path> \
#     --track-id <id> \
#     --changed-paths-file <path>          # 一行一个相对路径
#     [--wave-id <id> --wave-union]        # 校验范围扩到 wave 内全部 owned_paths union
#
# Exit:
#   0 = pass（全部 changed paths 在 owned_paths / wave union 内）
#   1 = 越界（至少一个 path 不在 scope 内）
#   2 = 参数 / 输入格式错误

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _is_under(p: str, owned: list[str]) -> bool:
    """p 是否在 owned_paths 任一前缀下（按 / 边界匹配）。"""
    if not isinstance(p, str) or not p:
        return False
    pn = p.strip("/")
    for op in owned or []:
        if not isinstance(op, str):
            continue
        opn = op.strip("/")
        if not opn:
            continue
        if pn == opn:
            return True
        if pn.startswith(opn + "/"):
            return True
    return False


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="/gd owned-path audit (Plan 6.5-C)")
    parser.add_argument("--dispatch-map", required=True)
    parser.add_argument("--track-id", required=True)
    parser.add_argument("--changed-paths-file", required=True)
    parser.add_argument("--wave-id", help="若 --wave-union 时必填")
    parser.add_argument("--wave-union", action="store_true",
                        help="校验范围扩到 wave 内全部 owned_paths union")

    args = parser.parse_args(argv[1:])

    dm = Path(args.dispatch_map)
    cp = Path(args.changed_paths_file)
    if not dm.exists():
        print(f"错误: dispatch map 不存在 {dm}", file=sys.stderr)
        return 2
    if not cp.exists():
        print(f"错误: changed-paths-file 不存在 {cp}", file=sys.stderr)
        return 2

    try:
        dispatch = json.loads(dm.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"错误: dispatch map JSON 语法错误: {e}", file=sys.stderr)
        return 2

    if args.wave_union and not args.wave_id:
        print("错误: --wave-union 必须配 --wave-id", file=sys.stderr)
        return 2

    # 找 track
    track = None
    track_by_id = {}
    for t in dispatch.get("tracks", []):
        if isinstance(t, dict) and t.get("track_id"):
            track_by_id[t["track_id"]] = t
            if t["track_id"] == args.track_id:
                track = t
    if track is None:
        print(f"错误: track_id={args.track_id!r} 不在 dispatch map", file=sys.stderr)
        return 2

    # 决定 owned scope
    if args.wave_union:
        wave = None
        for w in dispatch.get("waves", []):
            if isinstance(w, dict) and w.get("wave_id") == args.wave_id:
                wave = w
                break
        if wave is None:
            print(f"错误: wave_id={args.wave_id!r} 不在 dispatch map", file=sys.stderr)
            return 2
        wave_track_ids = wave.get("track_ids", [])
        if args.track_id not in wave_track_ids:
            print(
                f"错误: track={args.track_id!r} 不属 wave={args.wave_id!r}",
                file=sys.stderr,
            )
            return 2
        owned: list[str] = []
        for tid in wave_track_ids:
            tr = track_by_id.get(tid)
            if tr:
                owned.extend(tr.get("owned_paths", []) or [])
        scope_label = f"wave={args.wave_id} union of {sorted(wave_track_ids)}"
    else:
        owned = list(track.get("owned_paths", []) or [])
        scope_label = f"track={args.track_id}"

    if not owned:
        print(
            f"错误: {scope_label} owned_paths 为空，无法做 audit",
            file=sys.stderr,
        )
        return 2

    # 读 changed paths
    raw_lines = cp.read_text(encoding="utf-8").splitlines()
    changed = [ln.strip() for ln in raw_lines if ln.strip() and not ln.lstrip().startswith("#")]
    if not changed:
        print(
            f"错误: changed-paths-file 没有有效路径行（非空 / 非注释）",
            file=sys.stderr,
        )
        return 2

    # 越界检查
    out_of_bounds: list[str] = []
    forbidden_protected: list[str] = []
    for p in changed:
        # ~/.claude/** 直接 fail（即使在 owned_paths 内也禁止）
        if p.startswith("/Users/praise/.claude") or p.startswith("~/.claude"):
            forbidden_protected.append(p)
            continue
        if not _is_under(p, owned):
            out_of_bounds.append(p)

    if forbidden_protected or out_of_bounds:
        print(f"audit FAIL ({scope_label}):", file=sys.stderr)
        for p in forbidden_protected:
            print(f"  - protected runtime ~/.claude/**: {p!r}", file=sys.stderr)
        for p in out_of_bounds:
            print(f"  - 越界 (不在 owned scope): {p!r}", file=sys.stderr)
        print(f"  scope owned_paths: {owned}", file=sys.stderr)
        print(
            f"共 {len(forbidden_protected) + len(out_of_bounds)} 条违规 / "
            f"{len(changed)} 条 changed paths",
            file=sys.stderr,
        )
        return 1

    print(
        f"audit PASS: {len(changed)} changed paths 全部在 {scope_label} owned scope 内"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
