#!/usr/bin/env python3
# Plan 5 v5 — active validator (manifest revisions[1.2.1])；与 commands/gd.md /gd execute=local_only 同步上线
# gd-validate-execution-batch.py — /gd execution batch 校验器（stdlib-only）
#
# 职责分层（按 Plan 5 v5 设计）：
#   - dispatch map 预校验：链式调用 gd-validate-dispatch.py，exit ≠ 0 → fail-fast
#   - JSON 语法合法性：json.load()
#   - 结构 / required field / enum / type：手写 if-else，不依赖 jsonschema 库
#   - 语义校验（v2 既有）：task_id 唯一 / track_ref 存在 / not_run_reason 条件
#                          / sc_refs vs verify coupling / gd_execution_status_json 一致性
#                          / path traversal / anti-fill 规则
#   - 语义校验（v5 新增 4 类）：
#       1) wave membership: set(task_results.track_ref) == set(wave.track_ids)
#       2) deliverable truth: dispatch must_exist=true 必须在 deliverables_produced 中且 verified=true
#       3) owned_paths containment: produced path 必须在对应 track owned_paths 内
#       4) physical existence: produced path 必须实际存在（cwd-relative）
#   - closure report 校验（--closure 模式）：CLOSURE_STATUS 判定规则 / 条件必填字段
#
# CLI:
#   python3 scripts/gd-validate-execution-batch.py <batch.json> <dispatch-map.json>
#   python3 scripts/gd-validate-execution-batch.py --closure <closure-report.json>
#
# 路径解析：v5 物理存在与 owned_paths 校验都按当前工作目录（cwd）解析相对路径。
# 调用者必须 cd 到 project root 后运行。
#
# Exit codes:
#   0 = pass
#   1 = schema/semantic fail
#   2 = usage error

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


# ----------------------------- Constants ----------------------------- #

VALID_EXEC_STATUS = {
    "not_started", "in_progress", "completed",
    "completed_with_skips", "failed", "blocked", "skipped",
}
VALID_VERIFY_METHODS = {"command", "path", "assertion", "test"}
VALID_VERIFY_RESULTS = {"PASS", "FAIL", "SKIP"}
VALID_EXEC_MODES = {"dry_run", "human_exec", "agent_exec"}
VALID_DELIVERABLE_KINDS = {"file", "directory", "report"}
VALID_SC_RESULT_VALUES = {"pass", "fail", "skip"}
VALID_CLOSURE_STATUS = {"closed", "closed_with_constraints", "blocked", "failed"}

REQUIRED_BATCH_FIELDS = [
    "batch_id", "dispatch_id", "wave_ref",
    "batch_created_at", "execution_mode", "task_results",
]
REQUIRED_TASK_FIELDS = [
    "task_id", "track_ref", "exec_status", "not_run_reason",
    "deliverables_produced", "verify_results", "gd_execution_status_json",
]
REQUIRED_VERIFY_FIELDS = ["sc_ref", "method", "cmd", "result"]
REQUIRED_DELIVERABLE_FIELDS = ["path", "kind", "verified"]
REQUIRED_STATUS_JSON_FIELDS = ["task_id", "exec_status", "sc_results"]

REQUIRED_CLOSURE_FIELDS = [
    "closure_id", "source_batch", "closure_status",
    "track_results", "failed_tracks", "not_run_aggregation", "generated_at",
]
REQUIRED_NOT_RUN_AGG_FIELDS = ["total", "skipped", "blocked", "in_progress"]

ANTIFILL_VERIFY_KEYWORDS = ["目视确认", "目视检查", "看看是否正确", "自检即可"]
ANTIFILL_NEXT_ACTION_KEYWORDS = ["继续执行", "请人工检查", "后续处理"]
ANTIFILL_CONSTRAINT_KEYWORDS = ["有一些问题", "需要注意"]


# ----------------------------- Dispatch validator chain (Patch #2) ----------------------------- #

def run_dispatch_validator(dispatch_map_path: str, script_dir: Path) -> bool:
    """链式调用 gd-validate-dispatch.py。exit ≠ 0 → fail-fast。"""
    validator = script_dir / "gd-validate-dispatch.py"
    if not validator.exists():
        print(
            f"错误: dispatch 校验器不存在 {validator}",
            file=sys.stderr,
        )
        return False
    result = subprocess.run(
        [sys.executable, str(validator), dispatch_map_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"dispatch map 校验失败（exit={result.returncode}）：",
            file=sys.stderr,
        )
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return False
    return True


# ----------------------------- Batch structural checks ----------------------------- #

def check_batch_structural(d: dict, errs: list[str]) -> None:
    if not isinstance(d, dict):
        errs.append("batch 必须是 JSON object")
        return

    for f in REQUIRED_BATCH_FIELDS:
        if f not in d:
            errs.append(f"top-level: 缺字段 {f}")

    if "execution_mode" in d and d["execution_mode"] not in VALID_EXEC_MODES:
        errs.append(f"execution_mode 不合法: {d['execution_mode']!r}")

    task_results = d.get("task_results", [])
    if not isinstance(task_results, list) or not task_results:
        errs.append("task_results 必须是非空数组")
        return

    for i, t in enumerate(task_results):
        if not isinstance(t, dict):
            errs.append(f"task_results[{i}] 必须是 object")
            continue
        _check_task_structural(t, i, errs)


def _check_task_structural(t: dict, i: int, errs: list[str]) -> None:
    tid = t.get("task_id", f"?[{i}]")
    for f in REQUIRED_TASK_FIELDS:
        if f not in t:
            errs.append(f"task_results[{tid}]: 缺字段 {f}")

    if "exec_status" in t and t["exec_status"] not in VALID_EXEC_STATUS:
        errs.append(f"task_results[{tid}].exec_status 不合法: {t['exec_status']!r}")

    # verify_results 非空
    vrs = t.get("verify_results", [])
    if not isinstance(vrs, list) or not vrs:
        errs.append(f"task_results[{tid}].verify_results 必须是非空数组")
    else:
        for j, vr in enumerate(vrs):
            if not isinstance(vr, dict):
                errs.append(f"task_results[{tid}].verify_results[{j}] 必须是 object")
                continue
            for f in REQUIRED_VERIFY_FIELDS:
                if f not in vr:
                    errs.append(f"task_results[{tid}].verify_results[{j}] 缺字段 {f}")
            if "method" in vr and vr["method"] not in VALID_VERIFY_METHODS:
                errs.append(
                    f"task_results[{tid}].verify_results[{j}].method 不合法: {vr['method']!r}"
                )
            if "result" in vr and vr["result"] not in VALID_VERIFY_RESULTS:
                errs.append(
                    f"task_results[{tid}].verify_results[{j}].result 不合法: {vr['result']!r}"
                )
            # Anti-fill 规则 A
            cmd = vr.get("cmd", "")
            if isinstance(cmd, str):
                if len(cmd) < 3:
                    errs.append(
                        f"task_results[{tid}].verify_results[{j}].cmd 必须是 ≥3 字符"
                    )
                for kw in ANTIFILL_VERIFY_KEYWORDS:
                    if kw in cmd:
                        errs.append(
                            f"task_results[{tid}].verify_results[{j}].cmd 含 anti-fill "
                            f"违规词 {kw!r}"
                        )

    # deliverables_produced
    dps = t.get("deliverables_produced", [])
    if not isinstance(dps, list):
        errs.append(f"task_results[{tid}].deliverables_produced 必须是数组")
    else:
        for j, dp in enumerate(dps):
            if not isinstance(dp, dict):
                errs.append(
                    f"task_results[{tid}].deliverables_produced[{j}] 必须是 object"
                )
                continue
            for f in REQUIRED_DELIVERABLE_FIELDS:
                if f not in dp:
                    errs.append(
                        f"task_results[{tid}].deliverables_produced[{j}] 缺字段 {f}"
                    )
            if "kind" in dp and dp["kind"] not in VALID_DELIVERABLE_KINDS:
                errs.append(
                    f"task_results[{tid}].deliverables_produced[{j}].kind 不合法: "
                    f"{dp['kind']!r}"
                )

    # gd_execution_status_json
    gsj = t.get("gd_execution_status_json", {})
    if not isinstance(gsj, dict):
        errs.append(f"task_results[{tid}].gd_execution_status_json 必须是 object")
    else:
        for f in REQUIRED_STATUS_JSON_FIELDS:
            if f not in gsj:
                errs.append(f"task_results[{tid}].gd_execution_status_json 缺字段 {f}")
        sc_results = gsj.get("sc_results", {})
        if isinstance(sc_results, dict):
            for sc_k, sc_v in sc_results.items():
                if sc_v not in VALID_SC_RESULT_VALUES:
                    errs.append(
                        f"task_results[{tid}].gd_execution_status_json.sc_results"
                        f"[{sc_k!r}] 值不合法: {sc_v!r}（合法: pass/fail/skip）"
                    )


# ----------------------------- Batch semantic checks ----------------------------- #

def check_batch_semantic(
    d: dict, dispatch_map: dict | None, errs: list[str]
) -> None:
    task_results = d.get("task_results", [])
    if not isinstance(task_results, list):
        return

    # task_id 唯一
    seen_task_ids: set[str] = set()
    for t in task_results:
        if not isinstance(t, dict):
            continue
        tid = t.get("task_id", "?")
        if tid in seen_task_ids:
            errs.append(f"task_id 重复: {tid!r}")
        seen_task_ids.add(tid)

    # dispatch_id 一致
    if dispatch_map and "dispatch_id" in d:
        if d["dispatch_id"] != dispatch_map.get("dispatch_id"):
            errs.append(
                f"batch.dispatch_id={d['dispatch_id']!r} 与 "
                f"dispatch_map.dispatch_id={dispatch_map.get('dispatch_id')!r} 不一致"
            )

    # wave_ref 存在于 dispatch map
    wave_ref = d.get("wave_ref", "")
    if dispatch_map:
        wave_ids = {
            w.get("wave_id")
            for w in dispatch_map.get("waves", [])
            if isinstance(w, dict)
        }
        if wave_ref and wave_ref not in wave_ids:
            errs.append(
                f"batch.wave_ref={wave_ref!r} 在 dispatch map waves 中不存在 "
                f"（已知 wave_ids: {sorted(wave_ids)}）"
            )

    # 构建 dispatch track_by_id
    track_by_id: dict[str, dict] = {}
    if dispatch_map:
        for tr in dispatch_map.get("tracks", []):
            if isinstance(tr, dict) and "track_id" in tr:
                track_by_id[tr["track_id"]] = tr

    for t in task_results:
        if not isinstance(t, dict):
            continue
        tid = t.get("task_id", "?")
        track_ref = t.get("track_ref", "")

        # track_ref 存在
        if dispatch_map and track_ref and track_ref not in track_by_id:
            errs.append(
                f"task_results[{tid}].track_ref={track_ref!r} 在 dispatch map 不存在"
            )

        # not_run_reason 条件
        exec_status = t.get("exec_status", "")
        not_run_reason = t.get("not_run_reason")
        if exec_status in {"skipped", "blocked"} and not not_run_reason:
            errs.append(
                f"task_results[{tid}].exec_status={exec_status!r} 但 not_run_reason 为 null"
            )
        if exec_status not in {"skipped", "blocked"} and not_run_reason is not None:
            errs.append(
                f"task_results[{tid}].not_run_reason 非 null "
                f"但 exec_status={exec_status!r} 不是 skipped/blocked"
            )

        # exec_status vs gd_execution_status_json 一致
        gsj = t.get("gd_execution_status_json", {})
        if isinstance(gsj, dict) and gsj.get("exec_status") != exec_status:
            errs.append(
                f"task_results[{tid}].exec_status={exec_status!r} 与 "
                f"gd_execution_status_json.exec_status={gsj.get('exec_status')!r} 不一致"
            )
        if isinstance(gsj, dict) and gsj.get("task_id") != tid:
            errs.append(
                f"task_results[{tid}].gd_execution_status_json.task_id="
                f"{gsj.get('task_id')!r} 与外层 task_id={tid!r} 不一致"
            )

        # sc_refs ↔ verify[].sc_ref 关联校验（继承 Plan 4 anti-fill 规则 C）
        dispatch_track = track_by_id.get(track_ref, {})
        sc_refs = set(dispatch_track.get("sc_refs", []))
        verify_refs: set[str] = set()
        for vr in t.get("verify_results", []):
            if isinstance(vr, dict) and "sc_ref" in vr:
                verify_refs.add(vr["sc_ref"])
        if sc_refs:
            missing_verify = sc_refs - verify_refs
            if missing_verify:
                errs.append(
                    f"task_results[{tid}]: sc_refs {sorted(missing_verify)} "
                    f"缺对应 verify_results 项（anti-fill 规则 C）"
                )
            extra_verify = verify_refs - sc_refs
            if extra_verify:
                errs.append(
                    f"task_results[{tid}]: verify_results 引用未在 sc_refs 中的 SC: "
                    f"{sorted(extra_verify)}（SC 覆盖被伪造）"
                )

        # machine-readable JSON block 在 exec_status != not_started 时必须一致
        # (batch JSON 本身已有 gd_execution_status_json 字段，无需再解析 Markdown 块)
        # batch JSON 直接携带 gd_execution_status_json — 已在结构校验中验证

        # path traversal 防护：deliverables_produced 路径不能含 ..
        for dp in t.get("deliverables_produced", []):
            if isinstance(dp, dict):
                p = dp.get("path", "")
                if ".." in str(p).split("/"):
                    errs.append(
                        f"task_results[{tid}].deliverables_produced 路径含 '..' "
                        f"路径穿越: {p!r}"
                    )
                if isinstance(p, str) and p.startswith("/Users/praise/.claude"):
                    errs.append(
                        f"task_results[{tid}].deliverables_produced 路径指向 "
                        f"protected runtime ~/.claude/**"
                    )


# ----------------------------- v5 semantic checks (4 类) ----------------------------- #


def _is_under_owned_path(produced_path: str, owned_paths: list[str]) -> bool:
    """produced_path 是否在 owned_paths 任一前缀下（按 / 边界匹配，禁单字符前缀通过）。"""
    if not isinstance(produced_path, str):
        return False
    p = produced_path.strip("/")
    for op in owned_paths or []:
        if not isinstance(op, str):
            continue
        opn = op.strip("/")
        if not opn:
            continue
        if p == opn:
            return True
        if p.startswith(opn + "/"):
            return True
    return False


def check_v5_wave_membership(
    batch: dict, dispatch: dict | None, errs: list[str]
) -> None:
    """v5 校验 1：set(task_results.track_ref) == set(wave.track_ids)"""
    if not dispatch:
        return
    wave_ref = batch.get("wave_ref", "")
    if not wave_ref:
        return
    wave_track_ids: set[str] = set()
    for w in dispatch.get("waves", []):
        if isinstance(w, dict) and w.get("wave_id") == wave_ref:
            wave_track_ids = set(w.get("track_ids", []))
            break
    if not wave_track_ids:
        # wave_ref 不存在已由 v2 校验报告，这里不重复
        return
    batch_track_refs: set[str] = set()
    for t in batch.get("task_results", []):
        if isinstance(t, dict) and "track_ref" in t:
            batch_track_refs.add(t["track_ref"])
    missing = wave_track_ids - batch_track_refs
    extra = batch_track_refs - wave_track_ids
    if missing:
        errs.append(
            f"v5 wave membership: wave={wave_ref!r} 缺 task_results 覆盖 "
            f"tracks {sorted(missing)}（dispatch wave.track_ids={sorted(wave_track_ids)}）"
        )
    if extra:
        errs.append(
            f"v5 wave membership: wave={wave_ref!r} 含未在 wave.track_ids 中的 "
            f"task_results tracks {sorted(extra)}"
        )


def check_v5_deliverable_and_path(
    batch: dict, dispatch: dict | None, errs: list[str]
) -> None:
    """v5 校验 2/3/4：deliverable truth + owned_paths containment + physical existence"""
    if not dispatch:
        return
    track_by_id: dict[str, dict] = {}
    for tr in dispatch.get("tracks", []):
        if isinstance(tr, dict) and "track_id" in tr:
            track_by_id[tr["track_id"]] = tr

    for t in batch.get("task_results", []):
        if not isinstance(t, dict):
            continue
        tid = t.get("task_id", "?")
        track_ref = t.get("track_ref", "")
        dispatch_track = track_by_id.get(track_ref)
        if not dispatch_track:
            # track_ref 不存在已由 v2 校验报告
            continue

        # ---------- 校验 2：deliverable truth ----------
        required_paths: list[str] = []
        for dlv in dispatch_track.get("deliverables", []):
            if isinstance(dlv, dict) and dlv.get("must_exist") is True:
                p = dlv.get("path")
                if isinstance(p, str):
                    required_paths.append(p)

        produced_by_path: dict[str, dict] = {}
        for dp in t.get("deliverables_produced", []):
            if isinstance(dp, dict):
                p = dp.get("path")
                if isinstance(p, str):
                    produced_by_path[p] = dp

        for req in required_paths:
            dp = produced_by_path.get(req)
            if dp is None:
                errs.append(
                    f"v5 deliverable truth: task_results[{tid}] 缺 dispatch "
                    f"required deliverable {req!r}（must_exist=true 未在 "
                    f"deliverables_produced 中出现）"
                )
                continue
            if dp.get("verified") is not True:
                errs.append(
                    f"v5 deliverable truth: task_results[{tid}] deliverable "
                    f"{req!r} 必须 verified=true"
                )

        # ---------- 校验 3 + 4：owned_paths containment + physical existence ----------
        owned_paths = dispatch_track.get("owned_paths", []) or []
        for dp in t.get("deliverables_produced", []):
            if not isinstance(dp, dict):
                continue
            p = dp.get("path")
            if not isinstance(p, str):
                continue

            # 校验 3：owned_paths containment（绝对路径或 ~/.claude/** 已由 v2 path traversal 拦截）
            if not _is_under_owned_path(p, owned_paths):
                errs.append(
                    f"v5 owned_paths: task_results[{tid}] produced path "
                    f"{p!r} 不在 track={track_ref!r} owned_paths "
                    f"{owned_paths} 内"
                )

            # 校验 4：physical existence（仅当 verified=true 才要求，避免对 SKIP/FAIL 误判）
            if dp.get("verified") is True:
                if not os.path.exists(p):
                    errs.append(
                        f"v5 physical existence: task_results[{tid}] deliverable "
                        f"{p!r} 声明 verified=true 但物理文件/目录不存在 "
                        f"（cwd={os.getcwd()}）"
                    )


# ----------------------------- Closure report checks ----------------------------- #

def check_closure_structural(d: dict, errs: list[str]) -> None:
    if not isinstance(d, dict):
        errs.append("closure report 必须是 JSON object")
        return

    for f in REQUIRED_CLOSURE_FIELDS:
        if f not in d:
            errs.append(f"top-level: 缺字段 {f}")

    if "closure_status" in d and d["closure_status"] not in VALID_CLOSURE_STATUS:
        errs.append(f"closure_status 不合法: {d['closure_status']!r}")

    # track_results 非空
    trs = d.get("track_results", [])
    if not isinstance(trs, list) or not trs:
        errs.append("track_results 必须是非空数组")

    # not_run_aggregation 字段
    nra = d.get("not_run_aggregation", {})
    if isinstance(nra, dict):
        for f in REQUIRED_NOT_RUN_AGG_FIELDS:
            if f not in nra:
                errs.append(f"not_run_aggregation 缺字段 {f}")


def check_closure_semantic(d: dict, errs: list[str]) -> None:
    status = d.get("closure_status", "")

    # 条件必填：next_action
    next_action = d.get("next_action")
    if status in {"blocked", "failed"}:
        if not next_action or (isinstance(next_action, str) and len(next_action) < 10):
            errs.append(
                f"closure_status={status!r} 时 next_action 必填（≥10 字符）"
            )
        if isinstance(next_action, str):
            for kw in ANTIFILL_NEXT_ACTION_KEYWORDS:
                if kw in next_action:
                    errs.append(
                        f"next_action 含 anti-fill 占位词 {kw!r}；"
                        f"必须描述具体人工干预路径"
                    )

    # 条件必填：constraint_notes
    constraint_notes = d.get("constraint_notes")
    if status == "closed_with_constraints":
        if not constraint_notes or (
            isinstance(constraint_notes, str) and len(constraint_notes) < 10
        ):
            errs.append(
                "closure_status='closed_with_constraints' 时 constraint_notes 必填（≥10 字符）"
            )
        if isinstance(constraint_notes, str):
            for kw in ANTIFILL_CONSTRAINT_KEYWORDS:
                if kw in constraint_notes:
                    errs.append(
                        f"constraint_notes 含 anti-fill 占位词 {kw!r}"
                    )

    # failed_tracks 一致性
    failed_tracks = d.get("failed_tracks", [])
    if status == "failed" and isinstance(failed_tracks, list) and not failed_tracks:
        errs.append(
            "closure_status='failed' 但 failed_tracks 为空（至少含 1 个失败 track_id）"
        )

    # CLOSURE_STATUS 判定规则自检（soft check：如果 track_results 给出，验证逻辑一致性）
    trs = d.get("track_results", [])
    if isinstance(trs, list):
        has_failed = any(
            isinstance(t, dict) and t.get("exec_status") == "failed"
            for t in trs
        )
        has_blocked = any(
            isinstance(t, dict) and t.get("exec_status") == "blocked"
            for t in trs
        )
        if status == "closed" and (has_failed or has_blocked):
            errs.append(
                "closure_status='closed' 但 track_results 含 failed/blocked track "
                "（状态与 track_results 不一致）"
            )
        if status == "failed" and not has_failed:
            errs.append(
                "closure_status='failed' 但 track_results 无 failed track "
                "（状态与 track_results 不一致）"
            )


# ----------------------------- Main ----------------------------- #

def main(argv: list[str]) -> int:
    # --closure 模式
    if len(argv) >= 2 and argv[1] == "--closure":
        if len(argv) != 3:
            print(
                "用法: python3 scripts/gd-validate-execution-batch.py --closure <closure-report.json>",
                file=sys.stderr,
            )
            return 2
        closure_path = argv[2]
        if not os.path.exists(closure_path):
            print(f"错误: 文件不存在 {closure_path}", file=sys.stderr)
            return 2
        try:
            with open(closure_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"JSON 语法错误: {e}", file=sys.stderr)
            return 1
        errs: list[str] = []
        check_closure_structural(data, errs)
        check_closure_semantic(data, errs)
        return _report(errs, f"closure_id={data.get('closure_id', '?')}", "closure_status")

    # batch 模式（或单文件 closure_ineligible 快速拒绝）
    if len(argv) < 2 or len(argv) > 3:
        print(
            "用法: python3 scripts/gd-validate-execution-batch.py <batch.json> <dispatch-map.json>",
            file=sys.stderr,
        )
        return 2

    batch_path = argv[1]
    if not os.path.exists(batch_path):
        print(f"错误: 文件不存在 {batch_path}", file=sys.stderr)
        return 2

    # ── closure_ineligible fast-reject（必须在 dispatch validator 之前运行）──
    try:
        with open(batch_path) as _f:
            _quick = json.load(_f)
    except json.JSONDecodeError as e:
        print(f"JSON 语法错误 ({batch_path}): {e}", file=sys.stderr)
        return 1

    _mode = _quick.get("execution_mode")
    _CLOSURE_INELIGIBLE_MODES = {"dry_run"}  # agent_exec 已实装（rev22）；dry_run 仍 pending
    if _mode in _CLOSURE_INELIGIBLE_MODES:
        print(
            f"EXECUTION_BATCH_PENDING_FUTURE_PLAN: "
            f"{_mode} is pending_future_plan",
            file=__import__("sys").stderr,
        )
        return 1

    if len(argv) != 3:
        print(
            "用法: python3 scripts/gd-validate-execution-batch.py <batch.json> <dispatch-map.json>",
            file=sys.stderr,
        )
        return 2

    dispatch_map_path = argv[2]
    if not os.path.exists(dispatch_map_path):
        print(f"错误: 文件不存在 {dispatch_map_path}", file=sys.stderr)
        return 2

    # Patch #2：先运行 dispatch validator
    script_dir = Path(__file__).parent
    if not run_dispatch_validator(dispatch_map_path, script_dir):
        print(
            "dispatch map 校验失败，无法校验 batch。请先修复 dispatch map。",
            file=sys.stderr,
        )
        return 1

    # batch JSON 已由 closure_ineligible fast-reject 加载（_quick），直接复用
    batch_data = _quick

    # 加载 dispatch map JSON（已由 dispatch validator 验证合法）
    with open(dispatch_map_path) as f:
        dispatch_data = json.load(f)

    errs: list[str] = []
    check_batch_structural(batch_data, errs)
    check_batch_semantic(batch_data, dispatch_data, errs)
    # v5 新增 4 类语义校验
    check_v5_wave_membership(batch_data, dispatch_data, errs)
    check_v5_deliverable_and_path(batch_data, dispatch_data, errs)
    return _report(
        errs,
        f"batch_id={batch_data.get('batch_id', '?')}",
        "task_results",
    )


def _report(errs: list[str], identity: str, entity_label: str) -> int:
    if errs:
        task_ids: list[str] = []
        for e in errs:
            m = re.search(r"task_results\[([^\]]+)\]", e)
            if m and m.group(1) not in task_ids:
                task_ids.append(m.group(1))
        print("校验失败：")
        for e in errs:
            print(f"  - {e}")
        if task_ids:
            print(f"涉及 task id: {', '.join(task_ids)}")
        print(f"共 {len(errs)} 条违规。")
        return 1
    print(f"校验通过：{identity}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
