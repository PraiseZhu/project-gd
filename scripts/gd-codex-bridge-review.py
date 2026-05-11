#!/usr/bin/env python3
# Plan 6.5-B candidate — Codex cross-review bridge wrapper（stdlib-only）
# scripts/gd-codex-bridge-review.py
#
# 设计：
#   - 旧 /review writer (~/.claude/scripts/review-result-writer.sh) 负责 Codex 投递与 raw 结构校验
#   - 本 wrapper 负责 SC-N 校验 + mapped JSON schema + merge matrix + verdict 隔离
#   - 默认离线；run-bridge 必须显式 --live-transport 才调用旧 writer
#
# 子命令：
#   build-capsule --kind plan|code --target <path> --cwd <root> --out <path>
#   run-bridge    --kind plan|code --target <path> --cwd <root> --out <mapped-json> --live-transport
#                 （未传 --live-transport → exit 2，stderr "live-transport flag required"）
#   parse-transport --kind plan|code --target <path> --raw-result <file> --out <mapped-json>
#   merge --claude <gd-json> --codex <gd-json> --out <merged-json>
#   self-test     （仅 fixture，不调旧 writer，不写 ~/.claude/**）
#
# 退出码:
#   0 = success
#   1 = mapped FAILED / merge FAILED / schema fail
#   2 = usage error / required flag missing / file not found
#
# 严格遵守 prompts/gd-review-standard.md §8 (Plan 6.5-B candidate)。

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ----------------------------- Paths ----------------------------- #

GD_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = GD_PROJECT_ROOT / "schema" / "gd-review-result.schema.json"
STANDARD_PATH = GD_PROJECT_ROOT / "prompts" / "gd-review-standard.md"
GOAL_PATH = GD_PROJECT_ROOT / "docs" / "gd-v7-project-goal.md"
TEMPLATE_BY_KIND = {
    "plan": GD_PROJECT_ROOT / "templates" / "gd-plan-review-template.md",
    "code": GD_PROJECT_ROOT / "templates" / "gd-execution-review-template.md",
}
WRITER_PATH = Path("/Users/praise/.claude/scripts/review-result-writer.sh")
SEND_WAIT_PATH = Path("/Users/praise/.claude/handoff/bin/codex-send-wait")

FIXTURES_DIR = GD_PROJECT_ROOT / "fixtures" / "review-bridge"
SIDECAR_FIXTURES_DIR = GD_PROJECT_ROOT / "fixtures" / "review-sidecar"

# ----------------------------- Constants ----------------------------- #

VALID_KINDS = {"plan", "code"}
TEMPLATE_KIND_BY_REVIEW_KIND = {
    "plan": "gd-plan-review",
    "code": "gd-execution-review",
}
TITLE_BY_KIND = {
    "plan": "Plan Review Result",
    "code": "Code Review Result",
}
REQUIRED_FINDING_FIELDS_CN = ["问题", "证据", "影响", "最小修复", "验收"]
SC_REF_RE = re.compile(r"\bSC-\d+\b")
VERDICT_LINE_RE = re.compile(r"^VERDICT:\s*(APPROVED|REQUIRES_CHANGES)\s*$", re.MULTILINE)
BARE_VERDICT_ANY_RE = re.compile(r"^(VERDICT|REV_VERDICT)\s*:", re.MULTILINE)
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")

# ----------------------------- Helpers ----------------------------- #


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _slugify(p: str) -> str:
    base = Path(p).name
    return re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()[:32] or "target"


def _gd_baseline_key(kind: str, target_abs_path: str, target_hash: str, run_id: str) -> str:
    digest = hashlib.sha256(
        f"{target_abs_path}{target_hash}{run_id}".encode("utf-8")
    ).hexdigest()[:12]
    return f"gd-{kind}-{_slugify(target_abs_path)}-{digest}"


def _new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{secrets.token_hex(3)}"


def _failed_mapped(
    reviewer: str,
    kind: str,
    target: str,
    reason: str,
    run_status: str = "failed_to_run",
) -> dict:
    """生成 fail-closed mapped JSON，通过 schema。"""
    template_kind = TEMPLATE_KIND_BY_REVIEW_KIND.get(kind, "gd-plan-review")
    return {
        "template_kind": template_kind,
        "reviewer": reviewer,
        "review_target": target,
        "review_kind": kind,
        "review_run_status": run_status,
        "gd_review_decision": "FAILED",
        "scope_checked": [
            {
                "facet": "bridge runtime",
                "result": "fail",
                "evidence": reason[:60],
            }
        ],
        "findings": [],
        "merge_notes": {
            "conflict_with_other_reviewer": False,
            "degraded_reason": reason,
        },
        "residual_risk": [],
        "timestamp": _now_iso(),
    }


# ----------------------------- Schema validator ----------------------------- #


def _is_valid_reviewer(s: str) -> bool:
    return s in {"claude_main", "codex"} or bool(
        re.match(r"^claude_subagent_[a-z0-9_]+$", s)
    )


def validate_mapped_schema(d: dict) -> list[str]:
    """校验 mapped JSON 是否符合 schema/gd-review-result.schema.json。stdlib-only。"""
    errs: list[str] = []
    if not isinstance(d, dict):
        return ["顶层不是 JSON object"]

    required = [
        "template_kind", "reviewer", "review_target", "review_kind",
        "review_run_status", "gd_review_decision", "scope_checked",
        "findings", "merge_notes", "timestamp",
    ]
    allowed = set(required) | {"residual_risk"}
    for f in required:
        if f not in d:
            errs.append(f"缺字段 {f}")
    for f in d:
        if f not in allowed:
            errs.append(f"多余字段 {f}（schema additionalProperties=false）")
    if errs:
        return errs

    if d["template_kind"] not in {"gd-plan-review", "gd-execution-review"}:
        errs.append(f"template_kind 不合法: {d['template_kind']!r}")
    if not _is_valid_reviewer(d["reviewer"]):
        errs.append(f"reviewer 不合法: {d['reviewer']!r}")
    if d["review_kind"] not in VALID_KINDS:
        errs.append(f"review_kind 不合法: {d['review_kind']!r}")
    if d["review_run_status"] not in {"completed", "completed_with_constraint", "degraded", "failed_to_run"}:
        errs.append(f"review_run_status 不合法: {d['review_run_status']!r}")
    if d["gd_review_decision"] not in {"APPROVED", "REQUIRES_CHANGES", "FAILED"}:
        errs.append(f"gd_review_decision 不合法: {d['gd_review_decision']!r}")
    if not TIMESTAMP_RE.match(str(d.get("timestamp", ""))):
        errs.append(f"timestamp 不合法: {d.get('timestamp')!r}")

    sc = d["scope_checked"]
    if not isinstance(sc, list) or not sc:
        errs.append("scope_checked 必须非空数组")
    else:
        for i, item in enumerate(sc):
            if not isinstance(item, dict) or "facet" not in item or "result" not in item:
                errs.append(f"scope_checked[{i}] 缺 facet/result")
                continue
            if not isinstance(item["facet"], str) or len(item["facet"]) < 3:
                errs.append(f"scope_checked[{i}].facet 长度<3")
            if item["result"] not in {"pass", "fail", "n_a"}:
                errs.append(f"scope_checked[{i}].result 不合法")

    findings = d["findings"]
    if not isinstance(findings, list):
        errs.append("findings 必须是数组")
    else:
        for i, fd in enumerate(findings):
            if not isinstance(fd, dict):
                errs.append(f"findings[{i}] 不是 object")
                continue
            for k in ["severity", "title", "sc_refs", "evidence", "impact", "required_fix", "verify"]:
                if k not in fd:
                    errs.append(f"findings[{i}] 缺 {k}")
            if "severity" in fd and fd["severity"] not in {"P1", "P2"}:
                errs.append(f"findings[{i}].severity 不合法")
            if "sc_refs" in fd:
                if not isinstance(fd["sc_refs"], list) or not fd["sc_refs"]:
                    errs.append(f"findings[{i}].sc_refs 必须非空数组")
                else:
                    for sc_ref in fd["sc_refs"]:
                        if not isinstance(sc_ref, str) or not re.match(r"^SC-\d+$", sc_ref):
                            errs.append(f"findings[{i}].sc_refs 含不合法 {sc_ref!r}")

    mn = d["merge_notes"]
    if not isinstance(mn, dict) or "conflict_with_other_reviewer" not in mn:
        errs.append("merge_notes 缺 conflict_with_other_reviewer")

    return errs


# ----------------------------- Raw markdown parser ----------------------------- #


def _split_findings(raw: str) -> list[str]:
    """把 raw markdown 切分为 finding 块。"""
    if "## Findings" not in raw:
        return []
    after = raw.split("## Findings", 1)[1]
    # stop at next ## section
    after = re.split(r"\n## ", after)[0]
    blocks = re.split(r"\n### Finding ", after)
    return [b for b in blocks[1:] if b.strip()]  # blocks[0] is preamble


def _parse_finding(block: str) -> dict | None:
    """解析单个 finding 块，提取 severity/title/sc_refs/5 中文字段。"""
    # title line: "1 [P1] xxx" or "2 [P2] yyy"
    title_match = re.match(r"\s*\d+\s*\[(P[12])\]\s*(.+?)\s*$", block.split("\n", 1)[0])
    if not title_match:
        return None
    severity = title_match.group(1)
    title = title_match.group(2).strip()

    fields: dict[str, str] = {}
    # SC: SC-N (or 多个，逗号分隔)
    sc_match = re.search(r"^\s*SC:\s*(.+?)\s*$", block, re.MULTILINE)
    sc_refs: list[str] = []
    if sc_match:
        sc_refs = SC_REF_RE.findall(sc_match.group(1))
    # 也兼容直接在文本内嵌 SC-N
    if not sc_refs:
        sc_refs = SC_REF_RE.findall(block)

    for cn in REQUIRED_FINDING_FIELDS_CN:
        m = re.search(rf"^\s*{cn}:\s*(.+?)\s*$", block, re.MULTILINE)
        fields[cn] = m.group(1).strip() if m else ""

    return {
        "severity": severity,
        "title": title,
        "sc_refs": sc_refs,
        "evidence": fields["证据"],
        "impact": fields["影响"],
        "required_fix": fields["最小修复"],
        "verify": fields["验收"],
        "_problem": fields["问题"],  # 旁挂供 wrapper 检查
    }


def parse_raw_to_mapped(
    kind: str,
    target: str,
    raw_text: str,
) -> tuple[dict, list[str]]:
    """raw markdown → mapped JSON。返回 (mapped, errors)。errors 非空 → mapped 是 fail_closed JSON。"""
    target_str = str(target)

    # 0. writer 已校验的结构最小前置（防御）
    title = TITLE_BY_KIND[kind]
    if f"# {title}" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              f"raw 缺标题 # {title}", "degraded"), [f"missing title {title}"]
    if "Scope Checked" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              "raw 缺 Scope Checked", "degraded"), ["missing Scope Checked"]
    if "## Findings" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              "raw 缺 ## Findings", "degraded"), ["missing Findings"]
    if "## Residual Risk" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              "raw 缺 ## Residual Risk", "degraded"), ["missing Residual Risk"]

    # 1. VERDICT 唯一性
    verdicts = VERDICT_LINE_RE.findall(raw_text)
    if not verdicts:
        return _failed_mapped("codex", kind, target_str,
                              "raw 无有效 VERDICT", "degraded"), ["no valid VERDICT"]
    if len(verdicts) > 1:
        return _failed_mapped("codex", kind, target_str,
                              f"raw 含 {len(verdicts)} 个 VERDICT", "degraded"), ["multiple VERDICT"]
    verdict = verdicts[0]

    # 2. findings 解析 + 5 中文字段 + SC-N 提取
    finding_blocks = _split_findings(raw_text)
    if verdict == "REQUIRES_CHANGES" and not finding_blocks:
        return _failed_mapped("codex", kind, target_str,
                              "REQUIRES_CHANGES 但无 finding", "degraded"), ["no finding"]

    findings_mapped: list[dict] = []
    parse_errors: list[str] = []
    for i, blk in enumerate(finding_blocks):
        f = _parse_finding(blk)
        if f is None:
            parse_errors.append(f"finding[{i}] 标题无法解析")
            continue
        # 5 中文字段都必须有
        for cn in REQUIRED_FINDING_FIELDS_CN:
            if cn == "问题":
                if not f["_problem"]:
                    parse_errors.append(f"finding[{i}] 缺 问题")
            elif not f.get(
                {"证据": "evidence", "影响": "impact", "最小修复": "required_fix", "验收": "verify"}[cn]
            ):
                parse_errors.append(f"finding[{i}] 缺 {cn}")
        # SC-N 必须有 (wrapper 加严)
        if not f["sc_refs"]:
            parse_errors.append(f"finding[{i}] 缺 SC: SC-<N>（wrapper schema 加严）")

    if parse_errors:
        return _failed_mapped("codex", kind, target_str,
                              "; ".join(parse_errors[:3]), "degraded"), parse_errors

    # 3. 拼 mapped JSON
    mapped = {
        "template_kind": TEMPLATE_KIND_BY_REVIEW_KIND[kind],
        "reviewer": "codex",
        "review_target": target_str,
        "review_kind": kind,
        "review_run_status": "completed",
        "gd_review_decision": verdict,
        "scope_checked": [
            {
                "facet": "raw markdown structure",
                "result": "pass",
                "evidence": f"writer-validated; verdict={verdict}",
            }
        ],
        "findings": [
            {
                "severity": f["severity"],
                "title": f["title"],
                "sc_refs": f["sc_refs"],
                "evidence": f["evidence"],
                "impact": f["impact"],
                "required_fix": f["required_fix"],
                "verify": f["verify"],
            }
            for f in (_parse_finding(b) for b in finding_blocks)
            if f is not None
        ],
        "merge_notes": {
            "conflict_with_other_reviewer": False,
        },
        "residual_risk": [],
        "timestamp": _now_iso(),
    }

    # 4. 最终 schema 自校验
    schema_errs = validate_mapped_schema(mapped)
    if schema_errs:
        return _failed_mapped("codex", kind, target_str,
                              f"mapped schema fail: {schema_errs[0]}", "degraded"), schema_errs

    return mapped, []


# ----------------------------- Capsule builder ----------------------------- #


def build_capsule_text(kind: str, target: Path, cwd: Path) -> tuple[str, str, str]:
    """返回 (capsule_text, target_hash, capsule_hash)。"""
    if kind not in VALID_KINDS:
        raise ValueError(f"--kind 必须是 plan|code")
    if not target.exists():
        raise FileNotFoundError(f"target 不存在: {target}")

    template_path = TEMPLATE_BY_KIND[kind]
    target_hash = _sha256_file(target)
    target_text = target.read_text(encoding="utf-8")
    standard_text = STANDARD_PATH.read_text(encoding="utf-8") if STANDARD_PATH.exists() else "(missing)"
    template_text = template_path.read_text(encoding="utf-8") if template_path.exists() else "(missing)"
    goal_text = GOAL_PATH.read_text(encoding="utf-8")[:3000] if GOAL_PATH.exists() else "(missing)"

    run_id = _new_run_id()
    target_abs = str(target.resolve())
    gd_baseline_key = _gd_baseline_key(kind, target_abs, target_hash, run_id)

    # writer 实际 grep 的 3 字段必须出现在行首
    capsule = (
        f"REVIEW_DOMAIN: ai_infra\n"
        f"REVIEW_FOCUS: bridge candidate review of {target.name}\n"
        f"REVIEW_FOCUS_SOURCE: plan\n"
        f"REVIEW_KIND: {kind}\n"
        f"REVIEW_ROUND: initial\n"
        f"REVIEW_DELTA_SCOPE: full_matrix\n"
        f"PLAN_ALIGNMENT_PRESENT: true\n"
        f"PLAN_REVIEW_ALIGNMENT: Plan 6.5-B bridge review of {target.name}\n"
        f"DOMAIN_OVERRIDE_REASON: N/A\n"
        f"PROJECT_ROOT: {cwd}\n"
        f"REPO_ROOT: {cwd}\n"
        f"BRANCH: N/A\n"
        f"IN_SCOPE: {target}\n"
        f"OUT_OF_SCOPE: 旧 /review、旧 /rev、hooks、daemon\n"
        f"USER_ACCEPTED_DECISIONS: bridge candidate via Plan 6.5-B\n"
        f"SUCCESS_CRITERIA: see {target}\n"
        f"KNOWN_LIMITATIONS: bridge candidate; not active\n"
        f"BASELINE_CONFIDENCE: medium\n"
        f"REVIEW_RULES: prompts/gd-review-standard.md §8 Plan 6.5-B\n"
        f"\n"
        f"# /gd Bridge Capsule (Plan 6.5-B candidate)\n\n"
        f"GD_STANDARD: {STANDARD_PATH}\n"
        f"GOAL_SOURCE: {GOAL_PATH}\n"
        f"REVIEW_TARGET: {target_abs}\n"
        f"TARGET_HASH: {target_hash}\n"
        f"GD_BASELINE_KEY: {gd_baseline_key}\n"
        f"GD_REVIEW_SCHEMA: {SCHEMA_PATH}\n"
        f"EXPECTED_SC_IDS: (extracted from target on review)\n\n"
        f"## Goal Chain\n\n```\n{goal_text}\n```\n\n"
        f"## Review Standard\n\n```\n{standard_text}\n```\n\n"
        f"## Review Template ({template_path.name})\n\n```\n{template_text}\n```\n\n"
        f"## Target Artifact ({target_abs})\n\n```\n{target_text}\n```\n\n"
        f"## Reviewer Instructions\n\n"
        f"- 你是 Codex sidecar reviewer\n"
        f"- 按 §Review Standard 给出 review\n"
        f"- 输出 raw markdown，必须含: 行首 'VERDICT: APPROVED' 或 'VERDICT: REQUIRES_CHANGES'\n"
        f"- 标题: '# {TITLE_BY_KIND[kind]}'；包含 'Scope Checked' / '## Findings' / '## Residual Risk' 段\n"
        f"- 每个 Finding 含 severity 标记 + 'SC: SC-<N>' 行 + 5 中文字段 (问题/证据/影响/最小修复/验收)\n"
        f"- REQUIRES_CHANGES 必须含 ≥1 ### Finding\n"
    )
    capsule_hash = _sha256_str(capsule)
    return capsule, target_hash, capsule_hash, gd_baseline_key, run_id


# ----------------------------- Subcommand handlers ----------------------------- #


def cmd_build_capsule(args: argparse.Namespace) -> int:
    try:
        capsule, target_hash, capsule_hash, gd_baseline_key, run_id = build_capsule_text(
            args.kind, Path(args.target), Path(args.cwd)
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.write_text(capsule, encoding="utf-8")
    print(f"capsule 写入: {out}")
    print(f"target_hash: {target_hash}")
    print(f"capsule_hash: {capsule_hash}")
    print(f"gd_baseline_key: {gd_baseline_key}")
    print(f"run_id: {run_id}")
    return 0


def cmd_run_bridge(args: argparse.Namespace) -> int:
    if not args.live_transport:
        print("live-transport flag required for actual delivery", file=sys.stderr)
        return 2

    target = Path(args.target)
    cwd = Path(args.cwd)
    out_path = Path(args.out)

    try:
        capsule, target_hash, capsule_hash, gd_baseline_key, run_id = build_capsule_text(
            args.kind, target, cwd
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    target_str = str(target.resolve())

    if not WRITER_PATH.exists():
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"writer 不存在: {WRITER_PATH}")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"GD_CODEX_BRIDGE_STATUS: failed_to_run")
        print(f"GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print(f"TRANSPORT_RESULT: N/A")
        return 1

    tmpdir = Path(os.environ.get("TMPDIR", "/tmp"))
    capsule_tmp = tmpdir / f"gd-codex-bridge-{run_id}.capsule.txt"
    capsule_tmp.write_text(capsule, encoding="utf-8")

    try:
        result = subprocess.run(
            [
                "bash", str(WRITER_PATH),
                "--capsule-file", str(capsule_tmp),
                "--baseline-key", gd_baseline_key,
                "--review-kind", args.kind,
                "--cwd", str(cwd),
                "--no-stop-marker",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        mapped = _failed_mapped("codex", args.kind, target_str,
                                "writer subprocess timeout >600s")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print("TRANSPORT_RESULT: N/A")
        return 1

    writer_stdout = result.stdout
    writer_stderr = result.stderr
    writer_exit = result.returncode

    # 解析 writer stdout 找 result path
    result_path = None
    full_match = re.search(r"^Full result:\s*(.+?)\s*$", writer_stdout, re.MULTILINE)
    if full_match:
        result_path = full_match.group(1)

    # writer 任意非 ✓ APPROVED / ✗ REQUIRES_CHANGES → mapped FAILED
    if "[REVIEW] ⚠️ DEGRADED" in writer_stdout or "DEGRADED" in writer_stdout:
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"writer DEGRADED: {writer_stdout.strip()[:200]}", "degraded")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: degraded")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print(f"TRANSPORT_RESULT: {result_path or 'N/A'}")
        return 1
    if "[REVIEW] ✗ MALFORMED" in writer_stdout:
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"writer MALFORMED: {writer_stdout.strip()[:200]}", "degraded")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: degraded")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print(f"TRANSPORT_RESULT: {result_path or 'N/A'}")
        return 1
    if "[REVIEW] ✗ FAILED" in writer_stdout or writer_exit != 0:
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"writer FAILED exit={writer_exit}: "
                                f"{(writer_stdout + writer_stderr).strip()[:200]}")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print(f"TRANSPORT_RESULT: {result_path or 'N/A'}")
        return 1

    # writer ✓ APPROVED 或 ✗ REQUIRES_CHANGES → 解析 raw result 做 SC-N + schema 加严
    if not result_path or not Path(result_path).exists():
        mapped = _failed_mapped("codex", args.kind, target_str,
                                "writer 成功但找不到 result path")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print("TRANSPORT_RESULT: N/A")
        return 1

    raw_text = Path(result_path).read_text(encoding="utf-8")
    mapped, errs = parse_raw_to_mapped(args.kind, target_str, raw_text)
    out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")

    decision = mapped["gd_review_decision"]
    status = mapped["review_run_status"]
    print(f"GD_CODEX_BRIDGE_STATUS: {status}")
    print(f"GD_REVIEW_DECISION: {decision}")
    print(f"MAPPED_RESULT: {out_path}")
    print(f"TRANSPORT_RESULT: {result_path}")
    return 0 if decision == "APPROVED" else (1 if decision == "FAILED" else 0)


def cmd_parse_transport(args: argparse.Namespace) -> int:
    target = Path(args.target)
    raw_path = Path(args.raw_result)
    if not raw_path.exists():
        print(f"ERROR: raw 文件不存在 {raw_path}", file=sys.stderr)
        return 2

    raw_text = raw_path.read_text(encoding="utf-8")
    mapped, errs = parse_raw_to_mapped(args.kind, str(target.resolve() if target.exists() else target), raw_text)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")

    decision = mapped["gd_review_decision"]
    status = mapped["review_run_status"]
    print(f"GD_CODEX_BRIDGE_STATUS: {status}")
    print(f"GD_REVIEW_DECISION: {decision}")
    print(f"MAPPED_RESULT: {out_path}")
    print(f"TRANSPORT_RESULT: {raw_path}")
    if errs:
        for e in errs[:5]:
            print(f"  parse-error: {e}", file=sys.stderr)
    return 0 if decision == "APPROVED" else (1 if decision == "FAILED" else 0)


def _merge_decision(claude: dict, codex: dict) -> tuple[str, str, str]:
    """按 §8.7 matrix 计算 merged decision。返回 (decision, status, reason)。"""
    # Matrix #5: schema fail (检查在 caller)
    # Matrix #4: 任一 degraded/failed_to_run → FAILED
    statuses = [claude["review_run_status"], codex["review_run_status"]]
    if any(s in {"degraded", "failed_to_run"} for s in statuses):
        return "FAILED", "failed_to_run", "matrix #4: reviewer degraded/failed_to_run"

    # Matrix #3: 任一 FAILED → FAILED
    decisions = [claude["gd_review_decision"], codex["gd_review_decision"]]
    if "FAILED" in decisions:
        return "FAILED", "completed", "matrix #3: reviewer FAILED"

    # Matrix #2: 任一 REQUIRES_CHANGES → REQUIRES_CHANGES
    if "REQUIRES_CHANGES" in decisions:
        return "REQUIRES_CHANGES", "completed", "matrix #2: reviewer REQUIRES_CHANGES"

    # Matrix #1: 双方 APPROVED + completed → APPROVED
    if all(d == "APPROVED" for d in decisions) and all(s in {"completed", "completed_with_constraint"} for s in statuses):
        return "APPROVED", "completed", "matrix #1: both APPROVED"

    return "FAILED", "failed_to_run", f"matrix unknown: decisions={decisions} statuses={statuses}"


def cmd_merge(args: argparse.Namespace) -> int:
    paths = [Path(args.claude), Path(args.codex)]
    for p in paths:
        if not p.exists():
            print(f"ERROR: 文件不存在 {p}", file=sys.stderr)
            return 2

    try:
        claude = json.loads(paths[0].read_text(encoding="utf-8"))
        codex = json.loads(paths[1].read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON 语法错误 {e}", file=sys.stderr)
        return 1

    # Matrix #5: 任一 schema fail → FAILED
    schema_errs = []
    for label, d in [("claude", claude), ("codex", codex)]:
        es = validate_mapped_schema(d)
        if es:
            schema_errs.append((label, es))

    review_target = claude.get("review_target") or codex.get("review_target") or "unknown"
    review_kind = claude.get("review_kind") or codex.get("review_kind") or "plan"

    if schema_errs:
        merged = _failed_mapped(
            "claude_subagent_merge",
            review_kind,
            review_target,
            f"matrix #5 schema fail: " + "; ".join(
                f"{lbl}:{es[0]}" for lbl, es in schema_errs
            ),
            "failed_to_run",
        )
        merged["merge_notes"]["arbitration_reason"] = "schema fail"
    else:
        decision, status, reason = _merge_decision(claude, codex)
        merged = {
            "template_kind": claude.get("template_kind", "gd-plan-review"),
            "reviewer": "claude_subagent_merge",
            "review_target": review_target,
            "review_kind": review_kind,
            "review_run_status": status,
            "gd_review_decision": decision,
            "scope_checked": [
                {
                    "facet": "claude vs codex merge",
                    "result": "pass" if decision == "APPROVED" else ("fail" if decision == "FAILED" else "n_a"),
                    "evidence": reason[:60],
                }
            ],
            "findings": [],
            "merge_notes": {
                "conflict_with_other_reviewer": claude["gd_review_decision"] != codex["gd_review_decision"],
                "arbitration_reason": reason,
            },
            "residual_risk": [],
            "timestamp": _now_iso(),
        }
        # 透传 reviewer findings 摘要：按优先级保留 REQUIRES_CHANGES > FAILED 的 findings
        for src in (codex, claude):
            if src["gd_review_decision"] == "REQUIRES_CHANGES":
                merged["findings"] = src["findings"]
                break

    final_errs = validate_mapped_schema(merged)
    if final_errs:
        # 自身 schema fail → 裸 FAILED
        merged = _failed_mapped("claude_subagent_merge", review_kind, review_target,
                                f"merge result schema fail: {final_errs[0]}")

    out_path = Path(args.out)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MERGED_DECISION: {merged['gd_review_decision']}")
    print(f"MERGED_STATUS: {merged['review_run_status']}")
    print(f"MERGED_REASON: {merged['merge_notes'].get('arbitration_reason', 'N/A')[:120]}")
    print(f"OUT: {out_path}")
    return 0 if merged["gd_review_decision"] == "APPROVED" else (
        1 if merged["gd_review_decision"] == "FAILED" else 0
    )


def cmd_self_test(args: argparse.Namespace) -> int:
    """fixture 自测；不调旧 writer，不写 ~/.claude/**。"""
    failures: list[str] = []

    # ---------- Parse fixtures ----------
    parse_cases = [
        ("raw-approved-plan.md", "plan", "completed", "APPROVED"),
        ("raw-requires-changes-plan.md", "plan", "completed", "REQUIRES_CHANGES"),
        ("raw-approved-code.md", "code", "completed", "APPROVED"),
        ("raw-requires-changes-code.md", "code", "completed", "REQUIRES_CHANGES"),
        ("raw-missing-verdict.md", "plan", "degraded", "FAILED"),
        ("raw-multiple-verdict.md", "plan", "degraded", "FAILED"),
        ("raw-malformed-missing-field.md", "plan", "degraded", "FAILED"),
        ("raw-requires-changes-missing-sc.md", "plan", "degraded", "FAILED"),
    ]
    for fname, kind, exp_status, exp_decision in parse_cases:
        fp = FIXTURES_DIR / fname
        if not fp.exists():
            failures.append(f"parse {fname}: fixture missing")
            continue
        raw = fp.read_text(encoding="utf-8")
        mapped, errs = parse_raw_to_mapped(kind, f"fixtures/review-bridge/{fname}", raw)
        got = (mapped["review_run_status"], mapped["gd_review_decision"])
        if got != (exp_status, exp_decision):
            failures.append(f"parse {fname}: want=({exp_status},{exp_decision}) got={got}")
        else:
            print(f"  ✓ parse {fname}: {got[0]} / {got[1]}")

    # ---------- Merge fixtures ----------
    sf = SIDECAR_FIXTURES_DIR
    merge_cases = [
        ("claude-approved.json", "codex-approved.json", "APPROVED"),
        ("claude-approved.json", "codex-requires-changes.json", "REQUIRES_CHANGES"),
        ("claude-approved.json", "codex-timeout.json", "FAILED"),  # codex failed_to_run → matrix #4
        ("claude-failed.json", "codex-approved.json", "FAILED"),
        ("claude-failed.json", "codex-requires-changes.json", "FAILED"),
    ]
    for cf, kf, exp in merge_cases:
        cp = sf / cf
        kp = sf / kf
        if not cp.exists() or not kp.exists():
            failures.append(f"merge {cf}+{kf}: fixture missing")
            continue
        try:
            claude = json.loads(cp.read_text(encoding="utf-8"))
            codex = json.loads(kp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            failures.append(f"merge {cf}+{kf}: json {e}")
            continue
        # 模拟 cmd_merge 内部逻辑
        schema_errs_c = validate_mapped_schema(claude)
        schema_errs_k = validate_mapped_schema(codex)
        if schema_errs_c or schema_errs_k:
            decision = "FAILED"
        else:
            decision, _, _ = _merge_decision(claude, codex)
        if decision != exp:
            failures.append(f"merge {cf}+{kf}: want={exp} got={decision}")
        else:
            print(f"  ✓ merge {cf}+{kf}: {decision}")

    # ---------- writer stdout fixtures ----------
    writer_fixtures = [
        ("writer-degraded.out", "degraded", "FAILED"),
        ("writer-failed.out", "failed_to_run", "FAILED"),
    ]
    for fname, exp_status, exp_decision in writer_fixtures:
        fp = FIXTURES_DIR / fname
        if not fp.exists():
            failures.append(f"writer {fname}: fixture missing")
            continue
        stdout_text = fp.read_text(encoding="utf-8")
        # 模拟 run-bridge 的 stdout 解析路径
        if "[REVIEW] ⚠️ DEGRADED" in stdout_text or "DEGRADED" in stdout_text:
            got = ("degraded", "FAILED")
        elif "[REVIEW] ✗ FAILED" in stdout_text:
            got = ("failed_to_run", "FAILED")
        elif "[REVIEW] ✗ MALFORMED" in stdout_text:
            got = ("degraded", "FAILED")
        else:
            got = ("unknown", "unknown")
        if got != (exp_status, exp_decision):
            failures.append(f"writer {fname}: want=({exp_status},{exp_decision}) got={got}")
        else:
            print(f"  ✓ writer {fname}: {got[0]} / {got[1]}")

    if failures:
        print("\nself-test FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nself-test PASS")
    return 0


# ----------------------------- Main ----------------------------- #


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="/gd Codex Cross-Review Bridge (Plan 6.5-B candidate)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("build-capsule")
    p_b.add_argument("--kind", required=True, choices=["plan", "code"])
    p_b.add_argument("--target", required=True)
    p_b.add_argument("--cwd", required=True)
    p_b.add_argument("--out", required=True)

    p_r = sub.add_parser("run-bridge")
    p_r.add_argument("--kind", required=True, choices=["plan", "code"])
    p_r.add_argument("--target", required=True)
    p_r.add_argument("--cwd", required=True)
    p_r.add_argument("--out", required=True)
    p_r.add_argument("--live-transport", action="store_true",
                     help="必须显式传入才允许调用旧 writer 投递 Codex")

    p_p = sub.add_parser("parse-transport")
    p_p.add_argument("--kind", required=True, choices=["plan", "code"])
    p_p.add_argument("--target", required=True)
    p_p.add_argument("--raw-result", required=True)
    p_p.add_argument("--out", required=True)

    p_m = sub.add_parser("merge")
    p_m.add_argument("--claude", required=True)
    p_m.add_argument("--codex", required=True)
    p_m.add_argument("--out", required=True)

    sub.add_parser("self-test")

    args = parser.parse_args(argv[1:])

    if args.cmd == "build-capsule":
        return cmd_build_capsule(args)
    if args.cmd == "run-bridge":
        return cmd_run_bridge(args)
    if args.cmd == "parse-transport":
        return cmd_parse_transport(args)
    if args.cmd == "merge":
        return cmd_merge(args)
    if args.cmd == "self-test":
        return cmd_self_test(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
