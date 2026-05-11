#!/usr/bin/env python3
# gd-validate-dispatch.py — /gd dispatch map 校验器（stdlib-only）
#
# 职责分层（按 Plan 4 v2 patch #4）：
#   - JSON 语法合法性：json.load()
#   - 结构 / required field / enum / type：手写 if-else，不依赖 jsonschema 库
#   - 语义校验：见 §"Semantic checks"
#
# 路径重叠算法（patch #1）：pathlib.PurePosixPath，禁止纯 str.startswith
# required_context 双类校验（patch #2）：静态文件 vs deliverable 引用 cross-check
#
# CLI:
#   python3 scripts/gd-validate-dispatch.py <dispatch-map.json>
#
# Exit codes:
#   0 = pass
#   1 = schema/semantic fail
#   2 = usage error

from __future__ import annotations

import json
import os
import sys
from pathlib import PurePosixPath


# ----------------------------- Path helpers ----------------------------- #

def normalize(p: str) -> PurePosixPath:
    """规范化路径：去 ./ 前缀，PurePath 即可（不解析 symlink）。"""
    if p.startswith("./"):
        p = p[2:]
    return PurePosixPath(p)


def overlaps(a: str, b: str) -> bool:
    """True 当且仅当 A 和 B 是同一路径或父子关系。
    禁止纯 str.startswith：'/foo' 与 '/foobar' 不算 overlap。
    """
    pa, pb = normalize(a), normalize(b)
    if pa == pb:
        return True
    try:
        pa.relative_to(pb)
        return True
    except ValueError:
        pass
    try:
        pb.relative_to(pa)
        return True
    except ValueError:
        pass
    return False


def is_under_protected_runtime(p: str) -> bool:
    """检查路径是否落在 /Users/praise/.claude/** 内。"""
    pn = normalize(p)
    try:
        pn.relative_to(PurePosixPath("/Users/praise/.claude"))
        return True
    except ValueError:
        return False


# ----------------------------- Structural checks (no jsonschema) ----------------------------- #

VALID_MODES = {"plan", "execute", "review", "validate"}
VALID_AGENT_ROLES = {"child_planner", "child_executor", "child_reviewer", "child_validator"}
VALID_VERIFY_METHODS = {"command", "path", "assertion", "test"}
VALID_DELIVERABLE_KINDS = {"file", "directory", "report"}

REQUIRED_TOP_FIELDS = [
    "dispatch_id", "source_master_plan", "goal_chain",
    "max_parallel_planning", "max_parallel_execution",
    "max_parallel_review", "max_parallel_validation",
    "tracks", "waves", "merge_gates",
]

REQUIRED_TRACK_FIELDS = [
    "track_id", "mode", "agent_role",
    "owned_paths", "forbidden_paths",
    "required_context", "deliverables",
    "blocked_by", "can_parallel_with",
    "sc_refs", "verify",
]

REQUIRED_VERIFY_FIELDS = ["sc_ref", "method", "cmd"]
REQUIRED_DELIVERABLE_FIELDS = ["path", "kind", "must_exist"]


def check_structural(d: dict, errs: list[str]) -> None:
    """手写结构 / required field / enum / type 检查。"""
    if not isinstance(d, dict):
        errs.append("dispatch map 必须是 JSON object")
        return

    # Top-level required
    for f in REQUIRED_TOP_FIELDS:
        if f not in d:
            errs.append(f"top-level: 缺字段 {f}")

    # Top-level types
    for f in ["max_parallel_planning", "max_parallel_execution",
              "max_parallel_review", "max_parallel_validation"]:
        if f in d:
            v = d[f]
            if not isinstance(v, int) or v < 1 or v > 2:
                errs.append(
                    f"top-level: {f} 必须是整数 [1, 2]（Plan 6.5-C 锁定并发上限）"
                    f"，实际 {v!r}"
                )

    # Tracks
    tracks = d.get("tracks", [])
    if not isinstance(tracks, list) or not tracks:
        errs.append("tracks 必须是非空数组")
        return
    for i, t in enumerate(tracks):
        if not isinstance(t, dict):
            errs.append(f"tracks[{i}] 必须是 object")
            continue
        for f in REQUIRED_TRACK_FIELDS:
            if f not in t:
                errs.append(f"tracks[{i}] (track_id={t.get('track_id', '?')}) 缺字段 {f}")
        if "mode" in t and t["mode"] not in VALID_MODES:
            errs.append(f"tracks[{i}].mode 不合法: {t['mode']!r}（合法: {sorted(VALID_MODES)}）")
        if "agent_role" in t and t["agent_role"] not in VALID_AGENT_ROLES:
            errs.append(f"tracks[{i}].agent_role 不合法: {t['agent_role']!r}")
        for arr_field in ["owned_paths", "forbidden_paths", "blocked_by",
                          "can_parallel_with", "required_context", "sc_refs"]:
            if arr_field in t and not isinstance(t[arr_field], list):
                errs.append(f"tracks[{i}].{arr_field} 必须是数组")
        if "owned_paths" in t and isinstance(t["owned_paths"], list) and not t["owned_paths"]:
            errs.append(f"tracks[{i}].owned_paths 不能为空")
        if "forbidden_paths" in t and isinstance(t["forbidden_paths"], list) and not t["forbidden_paths"]:
            errs.append(f"tracks[{i}].forbidden_paths 不能为空")
        if "sc_refs" in t and isinstance(t["sc_refs"], list) and not t["sc_refs"]:
            errs.append(f"tracks[{i}].sc_refs 不能为空")

        # Verify items
        verify = t.get("verify", [])
        if not isinstance(verify, list) or not verify:
            errs.append(f"tracks[{i}].verify 必须是非空数组")
        else:
            for j, v in enumerate(verify):
                if not isinstance(v, dict):
                    errs.append(f"tracks[{i}].verify[{j}] 必须是 object")
                    continue
                for f in REQUIRED_VERIFY_FIELDS:
                    if f not in v:
                        errs.append(f"tracks[{i}].verify[{j}] 缺字段 {f}")
                if "method" in v and v["method"] not in VALID_VERIFY_METHODS:
                    errs.append(f"tracks[{i}].verify[{j}].method 不合法: {v['method']!r}")
                if "cmd" in v:
                    cmd = v.get("cmd", "")
                    if not isinstance(cmd, str) or len(cmd) < 3:
                        errs.append(f"tracks[{i}].verify[{j}].cmd 必须是 ≥3 字符")
                    # Anti-fill 规则 A：禁止仅"目视确认"
                    bad_kw = ["目视确认", "目视检查", "看看是否正确", "自检即可"]
                    if any(k in cmd for k in bad_kw):
                        errs.append(
                            f"tracks[{i}].verify[{j}].cmd 含 anti-fill 规则 A 违规词 "
                            f"({cmd!r})；必须含命令/路径/断言/测试用例之一"
                        )

        # Deliverables
        deliverables = t.get("deliverables", [])
        if isinstance(deliverables, list):
            for j, dv in enumerate(deliverables):
                if not isinstance(dv, dict):
                    errs.append(f"tracks[{i}].deliverables[{j}] 必须是 object")
                    continue
                for f in REQUIRED_DELIVERABLE_FIELDS:
                    if f not in dv:
                        errs.append(f"tracks[{i}].deliverables[{j}] 缺字段 {f}")
                if "kind" in dv and dv["kind"] not in VALID_DELIVERABLE_KINDS:
                    errs.append(f"tracks[{i}].deliverables[{j}].kind 不合法: {dv['kind']!r}")


# ----------------------------- Semantic checks ----------------------------- #

def check_semantic(d: dict, errs: list[str]) -> None:
    tracks = d.get("tracks", [])
    if not isinstance(tracks, list) or not tracks:
        return  # structural already errored
    track_ids = []
    for t in tracks:
        if isinstance(t, dict) and "track_id" in t:
            track_ids.append(t["track_id"])

    # Uniqueness
    seen = set()
    for tid in track_ids:
        if tid in seen:
            errs.append(f"track_id 重复: {tid}")
        seen.add(tid)

    track_by_id = {t["track_id"]: t for t in tracks if isinstance(t, dict) and "track_id" in t}

    # blocked_by + can_parallel_with: existence + no self
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        for ref in t.get("blocked_by", []):
            if ref == tid:
                errs.append(f"tracks[{tid}].blocked_by 自依赖: {ref}")
            if ref not in track_by_id:
                errs.append(f"tracks[{tid}].blocked_by 引用不存在 track: {ref}")
        for ref in t.get("can_parallel_with", []):
            if ref == tid:
                errs.append(f"tracks[{tid}].can_parallel_with 自引用: {ref}")
            if ref not in track_by_id:
                errs.append(f"tracks[{tid}].can_parallel_with 引用不存在 track: {ref}")

    # Pair must not be in both blocked_by & can_parallel_with
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        bb = set(t.get("blocked_by", []))
        cp = set(t.get("can_parallel_with", []))
        common = bb & cp
        if common:
            errs.append(
                f"tracks[{tid}] 同时声明 blocked_by 与 can_parallel_with: {sorted(common)}"
                f"（依赖与并行互斥）"
            )

    # can_parallel_with symmetry
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        for peer in t.get("can_parallel_with", []):
            if peer not in track_by_id:
                continue  # already errored
            peer_track = track_by_id[peer]
            peer_cp = peer_track.get("can_parallel_with", [])
            if tid not in peer_cp:
                errs.append(
                    f"can_parallel_with 不对称: {tid}.can_parallel_with 含 {peer}, "
                    f"但 {peer}.can_parallel_with 不含 {tid}"
                )

    # Path overlap for pairs claimed parallel (must NOT overlap on owned_paths)
    seen_pairs = set()
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        for peer in t.get("can_parallel_with", []):
            if peer not in track_by_id:
                continue
            pair = tuple(sorted([tid, peer]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            t_owned = t.get("owned_paths", [])
            p_owned = track_by_id[peer].get("owned_paths", [])
            for a in t_owned:
                for b in p_owned:
                    if overlaps(a, b):
                        errs.append(
                            f"并行 track 路径重叠: {tid}.owned_paths={a!r} 与 "
                            f"{peer}.owned_paths={b!r} 是同路径或父子关系"
                        )

    # Protected runtime: owned_paths / deliverables / required_context 不得指向 ~/.claude/**
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        for p in t.get("owned_paths", []):
            if is_under_protected_runtime(p):
                errs.append(f"tracks[{tid}].owned_paths {p!r} 指向 protected runtime ~/.claude/**")
        for dv in t.get("deliverables", []):
            p = dv.get("path") if isinstance(dv, dict) else dv
            if isinstance(p, str) and is_under_protected_runtime(p):
                errs.append(f"tracks[{tid}].deliverables {p!r} 指向 protected runtime")
        for p in t.get("required_context", []):
            if is_under_protected_runtime(p):
                errs.append(f"tracks[{tid}].required_context {p!r} 指向 protected runtime")

    # required_context 双类校验（patch #2）
    deliverables_index: dict[str, str] = {}  # normalized path -> producer track_id
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        for dv in t.get("deliverables", []):
            p = dv.get("path") if isinstance(dv, dict) else dv
            if isinstance(p, str):
                deliverables_index[str(normalize(p))] = tid

    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        blocked_by_set = set(t.get("blocked_by", []))
        for ctx_path in t.get("required_context", []):
            norm = str(normalize(ctx_path))
            if norm in deliverables_index:
                producer = deliverables_index[norm]
                if producer == tid:
                    errs.append(
                        f"tracks[{tid}].required_context {ctx_path!r} 自引用："
                        f"该路径是本 track 的 deliverable"
                    )
                elif producer not in blocked_by_set:
                    errs.append(
                        f"tracks[{tid}].required_context {ctx_path!r} 是 {producer} 的 deliverable, "
                        f"但 {tid}.blocked_by 不含 {producer}（缺依赖声明 → 可能与 producer 并行运行）"
                    )
            else:
                # 静态文件类：必须 validate-time 存在
                if not os.path.exists(ctx_path):
                    errs.append(
                        f"tracks[{tid}].required_context {ctx_path!r} 是静态文件类引用 "
                        f"（不在任何 deliverables 中），但 validate-time 不存在"
                    )

    # sc_refs ↔ verify[].sc_ref 关联校验（P1.2）
    # 规则：set(sc_refs) == set(verify[].sc_ref)
    # - sc_refs 中每条都必须有对应 verify（否则 anti-fill 规则 C：SC 无可执行 verify）
    # - verify 不允许引用未在 sc_refs 中的 SC（否则 SC 覆盖被伪造）
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id", "?")
        sc_refs = set(t.get("sc_refs", []))
        verify_refs = set()
        for v in t.get("verify", []):
            if isinstance(v, dict) and "sc_ref" in v:
                verify_refs.add(v["sc_ref"])
        missing_verify = sc_refs - verify_refs
        if missing_verify:
            errs.append(
                f"tracks[{tid}].sc_refs {sorted(missing_verify)} 缺对应 verify 项"
                f"（anti-fill 规则 C：SC 必须绑定可执行 verify）"
            )
        extra_verify = verify_refs - sc_refs
        if extra_verify:
            errs.append(
                f"tracks[{tid}].verify 引用未在 sc_refs 中的 SC: {sorted(extra_verify)} "
                f"（SC 覆盖被伪造）"
            )

    # waves 语义校验（P1.1）
    waves = d.get("waves", [])
    wave_index_by_track: dict[str, int] = {}  # track_id -> 0-based wave index
    if isinstance(waves, list):
        for w_idx, w in enumerate(waves):
            if not isinstance(w, dict):
                continue
            wave_id = w.get("wave_id", f"w?{w_idx}")
            track_ids_in_wave = w.get("track_ids", [])
            if not isinstance(track_ids_in_wave, list):
                continue
            seen_in_wave: set[str] = set()
            for tid in track_ids_in_wave:
                # Duplicate within wave
                if tid in seen_in_wave:
                    errs.append(f"waves[{wave_id}].track_ids 同 wave 内重复: {tid}")
                seen_in_wave.add(tid)
                # Existence
                if tid not in track_by_id:
                    errs.append(f"waves[{wave_id}].track_ids 引用不存在 track: {tid}")
                    continue
                # Track in multiple waves
                if tid in wave_index_by_track:
                    errs.append(
                        f"track {tid} 出现在多个 wave: "
                        f"先在 wave[{wave_index_by_track[tid]}], 又在 wave[{w_idx}]"
                    )
                else:
                    wave_index_by_track[tid] = w_idx

        # 同 wave 任意两条 track 必须互在 can_parallel_with
        for w_idx, w in enumerate(waves):
            if not isinstance(w, dict):
                continue
            wave_id = w.get("wave_id", f"w?{w_idx}")
            valid_in_wave = [
                tid for tid in w.get("track_ids", [])
                if tid in track_by_id
            ]
            for i, tid_a in enumerate(valid_in_wave):
                for tid_b in valid_in_wave[i + 1:]:
                    cp_a = set(track_by_id[tid_a].get("can_parallel_with", []))
                    cp_b = set(track_by_id[tid_b].get("can_parallel_with", []))
                    if tid_b not in cp_a or tid_a not in cp_b:
                        errs.append(
                            f"waves[{wave_id}] 内 {tid_a} 与 {tid_b} 同时调度但未声明可并行"
                            f"（{tid_a}.can_parallel_with={sorted(cp_a)}, "
                            f"{tid_b}.can_parallel_with={sorted(cp_b)}）"
                        )

        # blocked_by 必须在更早 wave（不能同 wave 也不能更晚 wave）
        for tid, w_idx in wave_index_by_track.items():
            t = track_by_id.get(tid, {})
            for dep in t.get("blocked_by", []):
                if dep not in wave_index_by_track:
                    # 引用不存在 / 未排入 wave，前面已 error
                    continue
                dep_idx = wave_index_by_track[dep]
                if dep_idx == w_idx:
                    errs.append(
                        f"track {tid}.blocked_by {dep} 但二者在同 wave[{w_idx}]"
                        f"（依赖必须在更早 wave）"
                    )
                elif dep_idx > w_idx:
                    errs.append(
                        f"track {tid}.blocked_by {dep} 但 {dep} 在 wave[{dep_idx}] "
                        f"晚于本 track 的 wave[{w_idx}]（依赖必须在更早 wave）"
                    )


# ----------------------------- Main ----------------------------- #

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: python3 scripts/gd-validate-dispatch.py <dispatch-map.json>", file=sys.stderr)
        return 2

    path = argv[1]
    if not os.path.exists(path):
        print(f"错误: 文件不存在 {path}", file=sys.stderr)
        return 2

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"JSON 语法错误: {e}", file=sys.stderr)
        return 1

    errs: list[str] = []
    check_structural(data, errs)
    # 仅当结构基本合法时才跑语义检查（避免连带噪声）
    if not any("缺字段" in e or "必须是" in e for e in errs):
        check_semantic(data, errs)
    else:
        # 即使有结构错也尽量跑能跑的语义检查
        check_semantic(data, errs)

    if errs:
        track_ids = []
        for e in errs:
            # 提取 track_id 形式 tracks[xxx]
            import re as _re
            m = _re.search(r"tracks\[([^\]]+)\]", e)
            if m and m.group(1) not in track_ids:
                track_ids.append(m.group(1))
        print("校验失败：")
        for e in errs:
            print(f"  - {e}")
        if track_ids:
            print(f"涉及 track id: {', '.join(track_ids)}")
        print(f"共 {len(errs)} 条违规。")
        return 1

    dispatch_id = data.get("dispatch_id", "?")
    n_tracks = len(data.get("tracks", []))
    n_waves = len(data.get("waves", []))
    print(f"校验通过：dispatch_id={dispatch_id}, tracks={n_tracks}, waves={n_waves}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
