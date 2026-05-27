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
import time
from datetime import datetime, timezone
from pathlib import Path

# ----------------------------- Paths ----------------------------- #

GD_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH_V1 = GD_PROJECT_ROOT / "schema" / "gd-review-result.schema.json"
SCHEMA_PATH_V2 = GD_PROJECT_ROOT / "schema" / "gd-review-result-v2.schema.json"
# Backward-compat alias (legacy code may still reference SCHEMA_PATH).
SCHEMA_PATH = SCHEMA_PATH_V1
STANDARD_PATH = GD_PROJECT_ROOT / "prompts" / "gd-review-standard.md"
GOAL_PATH = GD_PROJECT_ROOT / "docs" / "gd-v7-project-goal.md"

# v1 (compat) template files
TEMPLATE_BY_KIND_V1 = {
    "plan": GD_PROJECT_ROOT / "templates" / "gd-plan-review-template.md",
    "code": GD_PROJECT_ROOT / "templates" / "gd-execution-review-template.md",
    # revision=20: execution kinds added for compat-v1 parse-transport.
    "execution_outcome": GD_PROJECT_ROOT / "templates" / "gd-execution-outcome-review-template.md",
    "combined": GD_PROJECT_ROOT / "templates" / "gd-combined-review-template.md",
    # R8/R9: code_diff writer emits v1 VERDICT markdown; uses execution-review template as base.
    "code_diff": GD_PROJECT_ROOT / "templates" / "gd-execution-review-template.md",
}
# v2 (default) template files — Agent E owns the file content; this map only
# carries the path strings. The bridge does not load the v2 templates' bytes
# until Agent E delivers them; missing file is rendered as "(missing)".
# Keys are SSOT REVIEW_KIND_ENUM members; allowlisted in
# fixtures/review-contract-drift/allowlist.json (mapping keys are not drift).
TEMPLATE_BY_KIND_V2 = {
    "plan": GD_PROJECT_ROOT / "templates" / "gd-plan-review-v2-template.md",
    "execution_outcome": GD_PROJECT_ROOT / "templates" / "gd-execution-outcome-review-template.md",
    "code_diff": GD_PROJECT_ROOT / "templates" / "gd-code-diff-review-template.md",
    "combined": GD_PROJECT_ROOT / "templates" / "gd-combined-review-template.md",
}
# Back-compat alias (kept so any legacy reference still resolves to v1 map).
TEMPLATE_BY_KIND = TEMPLATE_BY_KIND_V1
WRITER_PATH = Path(os.environ.get("GD_WRITER_PATH_OVERRIDE", "/Users/praise/.claude/scripts/review-result-writer.sh"))
SEND_WAIT_PATH = Path("/Users/praise/.claude/handoff/bin/codex-send-wait")

FIXTURES_DIR = GD_PROJECT_ROOT / "fixtures" / "review-bridge"
SIDECAR_FIXTURES_DIR = GD_PROJECT_ROOT / "fixtures" / "review-sidecar"
# Plan 8 v4.1 Step 7: routing fixtures for v2 vs v1-compat capsule build.
BRIDGE_V2_FIXTURES_DIR = GD_PROJECT_ROOT / "fixtures" / "codex-bridge-v2"

# Review Trust §Step 1: shared writer-stdout result-path parser.
# writer 在 3 种情况打印 "Full result: <path>"：
#   APPROVED case (writer line 357):           独占一行
#   REQUIRES_CHANGES case (writer line 360):   inline ". Full result: <path>"
#   MALFORMED case (writer line 192):          inline ". Full result: ${RESULT_FILE}"
# 旧 regex `^Full result:` (MULTILINE) 只匹配独占行 → 5-month 漏 result path bug。
# 现 regex 接受行首 OR 空白前置后的 `Full result:`。Test driver imports same constant
# (scripts/gd-test-bridge-parser.py) to keep parser behaviour locked across both.
RESULT_PATH_RE = re.compile(r"(?:^|\s)Full result:\s*(\S.+?)\s*$", re.MULTILINE)


def parse_writer_result_path(writer_stdout: str) -> str | None:
    """Extract `Full result:` raw path from writer stdout. Returns None if no match.
    Caller is responsible for checking Path(result_path).exists() — this function
    only does regex parsing so test fixtures can probe parser without touching disk.
    """
    m = RESULT_PATH_RE.search(writer_stdout)
    if not m:
        return None
    return m.group(1).strip()


# ----------------------------- Constants ----------------------------- #

# Plan 8 v4.1 Step 7: bridge supports both v2 (default) and v1 (--compat-v1).
# All enums and review_kind→template_kind mappings come from the SSOT module.
# Local definitions are forbidden (gd-validate-review-contract-drift.py would flag).
sys.path.insert(0, str(GD_PROJECT_ROOT / "scripts"))
from gd_review_contract import (  # noqa: E402
    REVIEW_KIND_ENUM,
    REVIEW_KIND_V1_ENUM,
    REVIEW_TARGET_KIND_ENUM,
    TEMPLATE_KIND_ENUM,
    TEMPLATE_KIND_V1_ENUM,
    REVIEW_KIND_TO_TEMPLATE_KIND,
    TARGET_KIND_TO_REVIEW_KIND,
    TARGET_ROLE_ENUM,
    NEXT_ACTION_ENUM,
    REVIEW_KIND_TO_TARGET_ROLE,
)

# Legacy alias kept for back-compat references inside this module.
# Default mode (v2) accepts the v2 enum; --compat-v1 narrows to v1.
VALID_KINDS = REVIEW_KIND_V1_ENUM  # legacy alias used by old build_capsule_text guard

# v1-only review_kind→template_kind mapping (v1 "code" → "gd-execution-review").
# v2 mapping is sourced from SSOT REVIEW_KIND_TO_TEMPLATE_KIND.
TEMPLATE_KIND_BY_REVIEW_KIND_V1 = {
    "plan": "gd-plan-review",
    "code": "gd-execution-review",
    # revision=20: compat-v1 extended for execution kinds so parse-transport
    # --compat-v1 can map real Codex execution raw into a valid v2 mapped JSON.
    "execution_outcome": "gd-execution-outcome-review",
    "combined": "gd-combined-review",
    # R8 fix: code_diff writer still emits v1 "Code Review Result" header.
    # In compat-v1 mode code_diff is treated as "code" for parsing purposes.
    "code_diff": "gd-code-diff-review",
}
# Back-compat alias (older callers expect the v1-shaped dict).
TEMPLATE_KIND_BY_REVIEW_KIND = TEMPLATE_KIND_BY_REVIEW_KIND_V1

TITLE_BY_KIND_V1 = {
    "plan": "Plan Review Result",
    "code": "Code Review Result",
    # R8: code_diff writer emits same "Code Review Result" title as code.
    "code_diff": "Code Review Result",
    # revision=20: execution_outcome and combined added so that --compat-v1
    # parse-transport can handle real Codex raw that uses v1-style headers.
    # Codex execution review raw uses "# Code Review Result" header at present;
    # parse_v1 looks for the title in this dict and accepts the v1 body format.
    "execution_outcome": "Code Review Result",
    "combined": "Code Review Result",
}
# v2 review kind → human-readable title for capsule reviewer instructions.
# v2 templates use "(v2)" suffix in the H1 title (per Agent E templates).
# The string keys here are SSOT enum members; they are explicitly allowlisted
# in fixtures/review-contract-drift/allowlist.json since dict keys are an
# unavoidable form of literal use (enums-as-mapping-keys is not enum drift).
TITLE_BY_KIND_V2 = {
    "plan": "Plan Review Result (v2)",
    "execution_outcome": "Execution Outcome Review Result (v2)",
    "code_diff": "Code Diff Review Result (v2)",
    "combined": "Combined Review Result (v2)",
}
# Back-compat alias.
TITLE_BY_KIND = TITLE_BY_KIND_V1

# v2 review_kind → required target_role (sourced from SSOT; see gd_review_contract).
# REVIEW_KIND_TO_TARGET_ROLE and TARGET_ROLE_ENUM are imported from SSOT above.
# Back-compat aliases so callers using the _V2 suffix still resolve.
REVIEW_KIND_TO_TARGET_ROLE_V2 = REVIEW_KIND_TO_TARGET_ROLE
TARGET_ROLE_ENUM_V2 = TARGET_ROLE_ENUM
# v2 review_kind → required review_target_kind. Derived by inverting the SSOT
# TARGET_KIND_TO_REVIEW_KIND map so the literals stay sourced from SSOT.
REVIEW_KIND_TO_REVIEW_TARGET_KIND_V2 = {
    rk: tk for tk, rk in TARGET_KIND_TO_REVIEW_KIND.items()
}
# Allowed review_target_kind values: re-export SSOT enum so we never duplicate.
REVIEW_TARGET_KIND_ENUM_V2 = REVIEW_TARGET_KIND_ENUM
# v2 schema timestamp regex (allows Z or ±HH:MM offsets).
TIMESTAMP_V2_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
# v2 review markdown JSON block extractor (HTML-comment-fenced).
V2_JSON_BLOCK_RE = re.compile(
    r"<!--\s*gd-review-result-json:start\s*-->\s*```json\s*\n(.*?)\n```\s*<!--\s*gd-review-result-json:end\s*-->",
    re.DOTALL,
)


def _get_active_kind_enum(compat_v1: bool) -> frozenset:
    """Return the active review_kind enum given the mode flag.

    R8 fix: compat_v1 mode also accepts code_diff (writer emits v1 markdown).
    REVIEW_KIND_V1_ENUM comes from SSOT and does not include code_diff, so we
    extend it locally for compat-v1 parse paths only.
    """
    if compat_v1:
        return REVIEW_KIND_V1_ENUM | frozenset({"code_diff"})
    return REVIEW_KIND_ENUM


def _get_active_template_kind_enum(compat_v1: bool) -> frozenset:
    """Return the active template_kind enum given the mode flag."""
    return TEMPLATE_KIND_V1_ENUM if compat_v1 else TEMPLATE_KIND_ENUM


def _get_active_schema_path(compat_v1: bool) -> Path:
    """Return the schema path for the active mode."""
    return SCHEMA_PATH_V1 if compat_v1 else SCHEMA_PATH_V2


def _expected_output_schema(compat_v1: bool) -> str:
    """Return the EXPECTED_OUTPUT_SCHEMA string written into the capsule."""
    if compat_v1:
        return "schema/gd-review-result.schema.json"
    return "schema/gd-review-result-v2.schema.json"


def _get_template_path(kind: str, compat_v1: bool) -> Path | None:
    """Resolve template file path for kind in active mode; None on bad mapping."""
    if compat_v1:
        return TEMPLATE_BY_KIND_V1.get(kind)
    return TEMPLATE_BY_KIND_V2.get(kind)


def _get_template_kind_for_capsule(kind: str, compat_v1: bool) -> str:
    """Return TEMPLATE_KIND value to write into the capsule.

    Both v1 and v2 modes return the SSOT-aligned unsuffixed name. v1/v2
    disambiguation comes from --compat-v1 flag and v2's schema_version: 2.0
    field in the JSON block, not from a name suffix. This matches v2 schema's
    template_kind enum and SSOT TEMPLATE_KIND_ENUM (both unsuffixed).
    """
    if compat_v1:
        return TEMPLATE_KIND_BY_REVIEW_KIND_V1[kind]
    return REVIEW_KIND_TO_TEMPLATE_KIND[kind]


def _get_title_by_kind(kind: str, compat_v1: bool) -> str:
    if compat_v1:
        return TITLE_BY_KIND_V1[kind]
    return TITLE_BY_KIND_V2[kind]
REQUIRED_FINDING_FIELDS_CN = ["问题", "证据", "影响", "最小修复", "验收"]
SC_REF_RE = re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*-)?SC-[A-Za-z]*[0-9]+(?:-[0-9]+)?\b")
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
    compat_v1: bool = True,
) -> dict:
    """生成 fail-closed mapped JSON，通过 schema。

    Default compat_v1=True keeps callers that don't pass the flag on the legacy
    v1 schema shape. New v2 callers must pass compat_v1=False.
    """
    if compat_v1:
        template_kind = TEMPLATE_KIND_BY_REVIEW_KIND_V1.get(kind, "gd-plan-review")
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
    # v2 fail-closed shape (schema/gd-review-result-v2.schema.json).
    template_kind = REVIEW_KIND_TO_TEMPLATE_KIND.get(kind, "gd-plan-review")
    target_role = REVIEW_KIND_TO_TARGET_ROLE.get(kind, "plan_artifact")
    review_target_kind = REVIEW_KIND_TO_REVIEW_TARGET_KIND_V2.get(kind, "plan_only")
    return {
        "schema_version": "2.0",
        "template_kind": template_kind,
        "review_kind": kind,
        "review_target_kind": review_target_kind,
        "target_role": target_role,
        "reviewer": reviewer,
        "review_target": target,
        "review_run_status": run_status,
        "gd_review_decision": "FAILED",
        "source_of_truth_decision": {
            "location": "top_level_machine_header",
            "value": "FAILED",
        },
        "scope_checked": [
            {
                "area": "bridge runtime",
                "result": "fail",
                "evidence": reason[:200],
            }
        ],
        "findings": [],
        "merge_notes": {
            "conflict_with_other_reviewer": False,
            "degraded_reason": reason,
        },
        "residual_risk": "",
        "timestamp": _now_iso(),
    }


# ----------------------------- Schema validator ----------------------------- #


def _is_valid_reviewer(s: str) -> bool:
    return s in {"claude_main", "codex"} or bool(
        re.match(r"^claude_subagent_[a-z0-9_]+$", s)
    )


def validate_mapped_schema_v1(d: dict) -> list[str]:
    """校验 mapped JSON 是否符合 schema/gd-review-result.schema.json (v1)。stdlib-only。"""
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

    # R8: code_diff is allowed in v1 compat mode (writer emits v1 VERDICT markdown).
    # Extend the SSOT enums locally rather than modifying the SSOT module.
    _v1_kind_enum_extended = REVIEW_KIND_V1_ENUM | frozenset({"code_diff"})
    _v1_template_kind_extended = TEMPLATE_KIND_V1_ENUM | frozenset({"gd-code-diff-review"})
    if d["template_kind"] not in _v1_template_kind_extended:
        errs.append(f"template_kind 不合法: {d['template_kind']!r}")
    if not _is_valid_reviewer(d["reviewer"]):
        errs.append(f"reviewer 不合法: {d['reviewer']!r}")
    if d["review_kind"] not in _v1_kind_enum_extended:
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
                        if not isinstance(sc_ref, str) or not re.match(r"^(?:[A-Za-z][A-Za-z0-9]*-)?SC-[A-Za-z]*[0-9]+(?:-[0-9]+)?$", sc_ref):
                            errs.append(f"findings[{i}].sc_refs 含不合法 {sc_ref!r}")

    mn = d["merge_notes"]
    if not isinstance(mn, dict) or "conflict_with_other_reviewer" not in mn:
        errs.append("merge_notes 缺 conflict_with_other_reviewer")

    return errs


def validate_mapped_schema_v2(d: dict) -> list[str]:
    """Minimal v2 schema sanity check (required fields + enum membership +
    cross-kind→target_role allOf). Bridge intentionally does NOT implement the
    full v2 schema (Agent D owns the canonical v2 validator); we only enforce
    enough to fail-closed on shape mismatches before merge / aggregator.
    """
    errs: list[str] = []
    if not isinstance(d, dict):
        return ["顶层不是 JSON object"]

    required = [
        "schema_version",
        "template_kind",
        "review_kind",
        "review_target_kind",
        "target_role",
        "reviewer",
        "review_target",
        "review_run_status",
        "gd_review_decision",
        "source_of_truth_decision",
        "scope_checked",
        "findings",
        "merge_notes",
        "residual_risk",
        "timestamp",
    ]
    allowed = set(required) | {"compatibility_mode", "cross_validation_findings"}
    for f in required:
        if f not in d:
            errs.append(f"缺字段 {f}")
    for f in d:
        if f not in allowed:
            errs.append(f"多余字段 {f}（v2 schema additionalProperties=false）")
    if errs:
        return errs

    if d["schema_version"] != "2.0":
        errs.append(f"schema_version 必须 '2.0', got {d['schema_version']!r}")
    if d["template_kind"] not in TEMPLATE_KIND_ENUM:
        errs.append(f"template_kind 不合法: {d['template_kind']!r}（SSOT 期望无 -v2 后缀）")
    if d["review_kind"] not in REVIEW_KIND_ENUM:
        errs.append(f"review_kind 不合法: {d['review_kind']!r}")
    if d["review_target_kind"] not in REVIEW_TARGET_KIND_ENUM_V2:
        errs.append(f"review_target_kind 不合法: {d['review_target_kind']!r}")
    if d["target_role"] not in TARGET_ROLE_ENUM:
        errs.append(f"target_role 不合法: {d['target_role']!r}")
    if not isinstance(d["reviewer"], str) or not d["reviewer"]:
        errs.append("reviewer 必须非空字符串")
    if not isinstance(d["review_target"], str) or not d["review_target"]:
        errs.append("review_target 必须非空字符串")
    if d["review_run_status"] not in {
        "completed", "completed_with_constraint", "degraded", "failed_to_run"
    }:
        errs.append(f"review_run_status 不合法: {d['review_run_status']!r}")
    if d["gd_review_decision"] not in {"APPROVED", "REQUIRES_CHANGES", "FAILED"}:
        errs.append(f"gd_review_decision 不合法: {d['gd_review_decision']!r}")
    if not TIMESTAMP_V2_RE.match(str(d.get("timestamp", ""))):
        errs.append(f"timestamp 不合法（v2 ISO 8601 with tz）: {d.get('timestamp')!r}")
    if not isinstance(d["residual_risk"], str):
        errs.append("residual_risk 必须是 string（v2 schema：string 字段）")

    sotd = d["source_of_truth_decision"]
    if not isinstance(sotd, dict):
        errs.append("source_of_truth_decision 必须是 object")
    else:
        if sotd.get("location") not in {"top_level_machine_header", "fenced_json_block"}:
            errs.append(f"source_of_truth_decision.location 不合法: {sotd.get('location')!r}")
        if sotd.get("value") not in {"APPROVED", "REQUIRES_CHANGES", "FAILED"}:
            errs.append(f"source_of_truth_decision.value 不合法: {sotd.get('value')!r}")

    sc = d["scope_checked"]
    if not isinstance(sc, list) or not sc:
        errs.append("scope_checked 必须非空数组")
    else:
        for i, item in enumerate(sc):
            if not isinstance(item, dict):
                errs.append(f"scope_checked[{i}] 不是 object")
                continue
            for k in ("area", "result", "evidence"):
                if k not in item:
                    errs.append(f"scope_checked[{i}] 缺 {k}（v2 用 'area' 而非 'facet'）")
            if "result" in item and item["result"] not in {"pass", "fail", "n_a"}:
                errs.append(f"scope_checked[{i}].result 不合法: {item['result']!r}")

    findings = d["findings"]
    if not isinstance(findings, list):
        errs.append("findings 必须是数组")
    else:
        for i, fd in enumerate(findings):
            if not isinstance(fd, dict):
                errs.append(f"findings[{i}] 不是 object")
                continue
            for k in ("severity", "title", "sc_refs", "evidence", "impact", "required_fix", "verify"):
                if k not in fd:
                    errs.append(f"findings[{i}] 缺 {k}")
            if fd.get("severity") not in {"P1", "P2"}:
                errs.append(f"findings[{i}].severity 不合法")
            sc_refs = fd.get("sc_refs")
            if not isinstance(sc_refs, list) or not sc_refs:
                errs.append(f"findings[{i}].sc_refs 必须非空数组")

    mn = d["merge_notes"]
    if not isinstance(mn, dict):
        errs.append("merge_notes 必须是 object")

    # allOf cross-rules: review_kind 决定 target_role；非 combined 禁止 cross_validation_findings
    rk = d.get("review_kind")
    expected_role = REVIEW_KIND_TO_TARGET_ROLE.get(rk)
    if expected_role and d.get("target_role") != expected_role:
        errs.append(
            f"target_role 必须与 review_kind 一致：review_kind={rk!r} 要求 "
            f"target_role={expected_role!r}, got {d.get('target_role')!r}"
        )
    if rk != "combined" and "cross_validation_findings" in d:
        errs.append("cross_validation_findings 仅 review_kind=='combined' 允许")

    return errs


def validate_mapped_schema(d: dict, *, compat_v1: bool = True) -> list[str]:
    """Schema validator router. compat_v1=True (default) preserves legacy
    behaviour for callers that don't pass the flag (e.g. older self-test
    paths and merge() with v1 inputs)."""
    if compat_v1:
        return validate_mapped_schema_v1(d)
    return validate_mapped_schema_v2(d)


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


def _parse_raw_to_mapped_v1(
    kind: str,
    target: str,
    raw_text: str,
) -> tuple[dict, list[str]]:
    """Legacy v1 raw-markdown parser. Only invoked under --compat-v1.

    raw markdown → mapped JSON。返回 (mapped, errors)。errors 非空 → mapped 是 fail_closed JSON。
    """
    target_str = str(target)

    # 0. writer 已校验的结构最小前置（防御）
    title = TITLE_BY_KIND_V1[kind]
    if f"# {title}" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              f"raw 缺标题 # {title}", "degraded", compat_v1=True), [f"missing title {title}"]
    if "Scope Checked" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              "raw 缺 Scope Checked", "degraded", compat_v1=True), ["missing Scope Checked"]
    if "## Findings" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              "raw 缺 ## Findings", "degraded", compat_v1=True), ["missing Findings"]
    if "## Residual Risk" not in raw_text:
        return _failed_mapped("codex", kind, target_str,
                              "raw 缺 ## Residual Risk", "degraded", compat_v1=True), ["missing Residual Risk"]

    # 1. VERDICT 唯一性
    verdicts = VERDICT_LINE_RE.findall(raw_text)
    if not verdicts:
        return _failed_mapped("codex", kind, target_str,
                              "raw 无有效 VERDICT", "degraded", compat_v1=True), ["no valid VERDICT"]
    if len(verdicts) > 1:
        return _failed_mapped("codex", kind, target_str,
                              f"raw 含 {len(verdicts)} 个 VERDICT", "degraded", compat_v1=True), ["multiple VERDICT"]
    verdict = verdicts[0]

    # 2. findings 解析 + 5 中文字段 + SC-N 提取
    finding_blocks = _split_findings(raw_text)
    if verdict == "REQUIRES_CHANGES" and not finding_blocks:
        return _failed_mapped("codex", kind, target_str,
                              "REQUIRES_CHANGES 但无 finding", "degraded", compat_v1=True), ["no finding"]

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
                              "; ".join(parse_errors[:3]), "degraded", compat_v1=True), parse_errors

    # 3. 拼 mapped JSON
    mapped = {
        "template_kind": TEMPLATE_KIND_BY_REVIEW_KIND_V1[kind],
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
    schema_errs = validate_mapped_schema(mapped, compat_v1=True)
    if schema_errs:
        return _failed_mapped("codex", kind, target_str,
                              f"mapped schema fail: {schema_errs[0]}", "degraded", compat_v1=True), schema_errs

    return mapped, []


def _parse_raw_to_mapped_v2(
    kind: str,
    target: str,
    raw_text: str,
) -> tuple[dict, list[str]]:
    """v2 raw-markdown parser. The v2 review templates carry a fenced JSON block
    (between `<!-- gd-review-result-json:start --> ... <!-- gd-review-result-json:end -->`)
    that is the single source of truth for the structured form. The bridge
    extracts it, normalises a couple of `target_role` / `review_target_kind`
    defaults if the reviewer omitted them, then runs the minimal v2 sanity
    validator. We also cross-check the top-level `GD_REVIEW_DECISION:` header
    against the JSON block when both are present (per Plan 8 v4.1 Step 4).
    """
    target_str = str(target)

    # 0. v2 H1 title presence (defensive — writer should already have asserted)
    title = TITLE_BY_KIND_V2[kind]
    if f"# {title}" not in raw_text:
        return (
            _failed_mapped(
                "codex", kind, target_str,
                f"raw 缺 v2 标题 # {title}", "degraded", compat_v1=False,
            ),
            [f"missing v2 title {title}"],
        )

    # 1. JSON block extraction (single occurrence required).
    matches = V2_JSON_BLOCK_RE.findall(raw_text)
    if not matches:
        return (
            _failed_mapped(
                "codex", kind, target_str,
                "raw 缺 gd-review-result-json fenced block", "degraded", compat_v1=False,
            ),
            ["missing gd-review-result-json block"],
        )
    if len(matches) > 1:
        return (
            _failed_mapped(
                "codex", kind, target_str,
                f"raw 含 {len(matches)} 个 gd-review-result-json block",
                "degraded", compat_v1=False,
            ),
            ["multiple gd-review-result-json blocks"],
        )

    try:
        mapped = json.loads(matches[0])
    except json.JSONDecodeError as e:
        return (
            _failed_mapped(
                "codex", kind, target_str,
                f"v2 JSON block 解析失败: {e}", "degraded", compat_v1=False,
            ),
            [f"v2 json decode error: {e}"],
        )

    if not isinstance(mapped, dict):
        return (
            _failed_mapped(
                "codex", kind, target_str,
                "v2 JSON block 顶层不是 object", "degraded", compat_v1=False,
            ),
            ["v2 json top-level not object"],
        )

    # 2. Cross-check top-level GD_REVIEW_DECISION (source-of-truth header)
    #    against the JSON block. If both present and conflict → fail.
    top_decision_match = re.search(
        r"^GD_REVIEW_DECISION:\s*(APPROVED|REQUIRES_CHANGES|FAILED)\s*$",
        raw_text,
        re.MULTILINE,
    )
    if top_decision_match:
        top_decision = top_decision_match.group(1)
        json_decision = mapped.get("gd_review_decision")
        if json_decision and top_decision != json_decision:
            return (
                _failed_mapped(
                    "codex", kind, target_str,
                    f"top GD_REVIEW_DECISION={top_decision!r} 与 JSON "
                    f"gd_review_decision={json_decision!r} 冲突",
                    "degraded", compat_v1=False,
                ),
                ["v2 top-vs-json decision conflict"],
            )

    # 3. Normalize fields the bridge can fill defensively without overwriting
    #    reviewer-supplied values: kind/target/timestamp.
    if "review_kind" not in mapped:
        mapped["review_kind"] = kind
    elif mapped["review_kind"] != kind:
        return (
            _failed_mapped(
                "codex", kind, target_str,
                f"v2 review_kind 不一致：CLI={kind!r} JSON={mapped['review_kind']!r}",
                "degraded", compat_v1=False,
            ),
            ["v2 review_kind mismatch"],
        )
    if not mapped.get("review_target"):
        mapped["review_target"] = target_str
    if not mapped.get("timestamp"):
        mapped["timestamp"] = _now_iso()
    if "schema_version" not in mapped:
        mapped["schema_version"] = "2.0"

    # 4. Minimal v2 schema sanity.
    schema_errs = validate_mapped_schema_v2(mapped)
    if schema_errs:
        return (
            _failed_mapped(
                "codex", kind, target_str,
                f"v2 mapped schema fail: {schema_errs[0]}", "degraded", compat_v1=False,
            ),
            schema_errs,
        )

    return mapped, []


def parse_raw_to_mapped(
    kind: str,
    target: str,
    raw_text: str,
    *,
    compat_v1: bool = False,
) -> tuple[dict, list[str]]:
    """raw markdown → mapped JSON。返回 (mapped, errors)。errors 非空 → mapped 是 fail_closed JSON。

    Plan 8 v4.1 Fix P1-1: v2 is the default. v1 path only under compat_v1=True.
    Mode-mismatch (kind not in active enum) returns a fail-closed JSON with
    a clear INVALID_REVIEW_KIND_FOR_MODE reason.
    """
    target_str = str(target)
    active_enum = _get_active_kind_enum(compat_v1)
    if kind not in active_enum:
        mode_label = "v1 compat" if compat_v1 else "v2 default"
        reason = (
            f"INVALID_REVIEW_KIND_FOR_MODE: --kind={kind!r} not in "
            f"{mode_label} enum {sorted(active_enum)}"
        )
        return (
            _failed_mapped(
                "codex",
                # Use a kind safe for the mode so _failed_mapped does not KeyError.
                "plan",
                target_str,
                reason,
                "failed_to_run",
                compat_v1=compat_v1,
            ),
            [reason],
        )

    if compat_v1:
        return _parse_raw_to_mapped_v1(kind, target_str, raw_text)
    return _parse_raw_to_mapped_v2(kind, target_str, raw_text)


# ----------------------------- Capsule builder ----------------------------- #


VALID_TARGET_ROLES = {
    "master_plan",
    "subplan",
    "parent_close",
    "release_evidence",
}

# Back-compat constant (legacy callers may still reference it).
# New code paths must use _expected_output_schema(compat_v1).
EXPECTED_OUTPUT_SCHEMA = "schema/gd-review-result.schema.json"


def _related_context_summary(related_context: list[dict] | None) -> str:
    """Render RELATED_CONTEXT as a compact summary block, NOT inline full text.
    Each entry: {"role": "...", "path": "...", "hash": "..."}.
    The capsule must NOT inline other sub-plans' full markdown — Codex needs to
    review the PRIMARY target only. Related context is shown as path/hash refs.
    """
    if not related_context:
        return "(none)"
    lines = []
    for entry in related_context:
        role = entry.get("role", "unknown")
        path = entry.get("path", "")
        h = entry.get("hash", "")
        lines.append(f"- role={role} path={path} hash={h[:16]}")
    return "\n".join(lines)


def build_capsule_text(
    kind: str,
    target: Path,
    cwd: Path,
    queue_job_id: str | None = None,
    target_role: str | None = None,
    related_context: list[dict] | None = None,
    compat_v1: bool = False,
) -> tuple[str, str, str, str, str]:
    """返回 (capsule_text, target_hash, capsule_hash, gd_baseline_key, run_id)。

    Review Trust §Step 2: capsule 必含 QUEUE_JOB_ID / TARGET_ROLE / PRIMARY_TARGET /
    TARGET_HASH / REVIEW_KIND / EXPECTED_OUTPUT_SCHEMA / RELATED_CONTEXT 七字段。
    PRIMARY_TARGET 只有一个（capsule 的全文 review 对象）；RELATED_CONTEXT 是
    path/hash 摘要，不内联全文，避免单 capsule 包多 plan。

    Plan 8 v4.1 Step 7: when compat_v1=False (default), `kind` accepts the v2
    enum {plan, execution_outcome, code_diff, combined} and the capsule writes
    the v2 schema/template references. With compat_v1=True it accepts only v1
    {plan, code} and writes the legacy v1 references. Mixing is rejected with
    INVALID_REVIEW_KIND_FOR_MODE in the CLI handler.
    """
    active_enum = _get_active_kind_enum(compat_v1)
    if kind not in active_enum:
        # Build a clear error name so callers can grep / detect the mismatch.
        mode_label = "v1 compat" if compat_v1 else "v2 default"
        raise ValueError(
            f"INVALID_REVIEW_KIND_FOR_MODE: --kind={kind!r} not in "
            f"{mode_label} enum {sorted(active_enum)}"
        )
    if not target.exists():
        raise FileNotFoundError(f"target 不存在: {target}")
    if target_role is not None and target_role not in VALID_TARGET_ROLES:
        raise ValueError(
            f"--target-role 必须是 {sorted(VALID_TARGET_ROLES)}, got {target_role!r}"
        )

    template_path = _get_template_path(kind, compat_v1)
    if template_path is None:
        raise ValueError(
            f"INVALID_REVIEW_KIND_FOR_MODE: no template path for kind={kind!r} compat_v1={compat_v1}"
        )
    # B3: if the v2 template for this kind is missing and compat_v1 was not requested,
    # refuse to build a degraded capsule.  Caller should retry with --compat-v1.
    if (not compat_v1
            and kind in _KINDS_REQUIRING_COMPAT_V1_WHEN_V2_TEMPLATE_MISSING
            and not template_path.exists()):
        raise ValueError(
            f"V2_TEMPLATE_NOT_READY: v2 template for kind={kind!r} does not exist at "
            f"{template_path}. Use --compat-v1 until the template is delivered."
        )
    target_hash = _sha256_file(target)
    # L1: Target externalized — capsule no longer inlines target_text (47KB savings on
    # Sentinel-sized plans). Reviewer must Read the path; bridge enforces via L3
    # content-evidence validator (gd-validate-review-content-evidence.py).
    standard_text = STANDARD_PATH.read_text(encoding="utf-8") if STANDARD_PATH.exists() else "(missing)"
    template_text = template_path.read_text(encoding="utf-8") if template_path.exists() else "(missing)"
    goal_text = GOAL_PATH.read_text(encoding="utf-8")[:3000] if GOAL_PATH.exists() else "(missing)"

    run_id = _new_run_id()
    target_abs = str(target.resolve())
    gd_baseline_key = _gd_baseline_key(kind, target_abs, target_hash, run_id)

    # Review Trust §Step 2 default fallbacks
    effective_role = target_role or "subplan"
    effective_queue_id = queue_job_id or f"adhoc-{run_id}"
    related_summary = _related_context_summary(related_context)

    expected_schema = _expected_output_schema(compat_v1)
    schema_path_for_capsule = _get_active_schema_path(compat_v1)
    template_kind_for_capsule = _get_template_kind_for_capsule(kind, compat_v1)
    title_for_kind = _get_title_by_kind(kind, compat_v1)
    mode_label = "v1 compat" if compat_v1 else "v2 default"

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
        f"BRIDGE_MODE: {mode_label}\n"
        f"COMPATIBILITY_MODE: {str(compat_v1).lower()}\n"
        f"GD_STANDARD: {STANDARD_PATH}\n"
        f"GOAL_SOURCE: {GOAL_PATH}\n"
        f"REVIEW_TARGET: {target_abs}\n"
        f"TARGET_HASH: {target_hash}\n"
        f"GD_BASELINE_KEY: {gd_baseline_key}\n"
        f"GD_REVIEW_SCHEMA: {schema_path_for_capsule}\n"
        f"EXPECTED_SC_IDS: (extracted from target on review)\n\n"
        # Review Trust §Step 2 required metadata block
        f"QUEUE_JOB_ID: {effective_queue_id}\n"
        f"TARGET_ROLE: {effective_role}\n"
        f"PRIMARY_TARGET: {target_abs}\n"
        f"EXPECTED_OUTPUT_SCHEMA: {expected_schema}\n"
        f"TEMPLATE_KIND: {template_kind_for_capsule}\n"
        f"RELATED_CONTEXT:\n{related_summary}\n\n"
        f"## Goal Chain\n\n```\n{goal_text}\n```\n\n"
        f"## Review Standard\n\n```\n{standard_text}\n```\n\n"
        f"## Review Template ({template_path.name})\n\n```\n{template_text}\n```\n\n"
        f"## Target Artifact\n\n"
        f"PRIMARY_TARGET_PATH: {target_abs}\n"
        f"PRIMARY_TARGET_HASH: {target_hash}\n"
        f"\n"
        f"**MANDATORY READ STEP** — Before producing any output, you MUST use your Read tool\n"
        f"to open the file at PRIMARY_TARGET_PATH and consume its full content. The capsule\n"
        f"does NOT inline the target text; reviewing without Read is impossible and will be\n"
        f"detected by the L3 content-evidence validator (see Reviewer Instructions).\n"
        f"\n"
        + (
            f"## MANDATORY VERIFY STEP\n\n"
            f"Before producing your verdict, you MUST:\n"
            f"1. Read PRIMARY_TARGET_PATH and locate every `deliverables_produced[].path` entry.\n"
            f"   For each deliverable path: run `test -f <path>` (or equivalent Read) and echo the actual exit code.\n"
            f"2. Locate every `verify_results[].cmd` entry.\n"
            f"   Rerun each command and echo the actual stdout + exit code.\n"
            f"   Do NOT trust the stored `result` field — it may be stale.\n"
            f"3. Report each check as PASS/FAIL with the real observed output.\n"
            f"Skipping this step will be detected by the L3 content-evidence validator and rejected as wrapper_schema_fail.\n\n"
            if kind in {"execution_outcome", "combined"} else ""
        )
        + f"## Reviewer Instructions\n\n"
        f"- 你是 Codex sidecar reviewer\n"
        f"- **第一步**：Read PRIMARY_TARGET_PATH 全文（capsule 内未内联）\n"
        f"- 按 §Review Standard 给出 review\n"
        f"- 输出 raw markdown，必须含: 行首 'VERDICT: APPROVED' 或 'VERDICT: REQUIRES_CHANGES'\n"
        f"- 标题: '# {title_for_kind}'；包含 'Scope Checked' / '## Findings' / '## Residual Risk' 段\n"
        f"- 每个 Finding 含 severity 标记 + 'SC: SC-<N>' 行 + 5 中文字段 (问题/证据/影响/最小修复/验收)\n"
        f"- REQUIRES_CHANGES 必须含 ≥1 ### Finding\n"
        f"- **每条 finding 必须 evidence: 含真实 path:line 引用**（L3 validator 会校验行号指向 target 真实内容）\n"
        f"- **每条 finding 的 sc_refs / SC-<N> 必须是 target 中真实存在的 SC-ID**（L3 validator 会校验）\n"
        f"- **APPROVED 时**必须输出 SCOPE_CHECKED 表，列出已审查的 SC-IDs（必须在 target 中真实存在）\n"
    )
    capsule_hash = _sha256_str(capsule)
    return capsule, target_hash, capsule_hash, gd_baseline_key, run_id


# ----------------------------- Subcommand handlers ----------------------------- #


def _load_related_context(path: str | None) -> list[dict] | None:
    if not path:
        return None
    # Detect JSON-as-path: caller passed inline JSON instead of a file path
    if path.lstrip().startswith(("[", "{")):
        print(
            "ERROR: --related-context value looks like inline JSON, not a file path. "
            "Write the JSON to a file and pass the path instead.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        print(f"ERROR: --related-context file not found: {e}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR: --related-context invalid JSON: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(data, list):
        print(
            f"ERROR: --related-context must be a JSON array, got {type(data).__name__}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return data


def cmd_build_capsule(args: argparse.Namespace) -> int:
    related = _load_related_context(getattr(args, "related_context", None))
    compat_v1 = _resolve_compat_v1(args.kind, getattr(args, "compat_v1", None))
    try:
        capsule, target_hash, capsule_hash, gd_baseline_key, run_id = build_capsule_text(
            args.kind, Path(args.target), Path(args.cwd),
            queue_job_id=getattr(args, "queue_job_id", None),
            target_role=getattr(args, "target_role", None),
            related_context=related,
            compat_v1=compat_v1,
        )
    except ValueError as e:
        msg = str(e)
        # Strict mode-mismatch / guard errors exit 1 so callers can distinguish from
        # generic usage errors (exit 2 for missing flags / file-not-found).
        if msg.startswith("INVALID_REVIEW_KIND_FOR_MODE") or msg.startswith("V2_TEMPLATE_NOT_READY"):
            print(f"ERROR: {msg}", file=sys.stderr)
            return 1
        print(f"ERROR: {msg}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.write_text(capsule, encoding="utf-8")
    print(f"capsule 写入: {out}")
    print(f"target_hash: {target_hash}")
    print(f"capsule_hash: {capsule_hash}")
    print(f"gd_baseline_key: {gd_baseline_key}")
    print(f"run_id: {run_id}")
    # Review Trust §Step 2: surface queue/role for downstream aggregator/parser
    print(f"QUEUE_JOB_ID: {getattr(args, 'queue_job_id', None) or f'adhoc-{run_id}'}")
    print(f"TARGET_ROLE: {getattr(args, 'target_role', None) or 'subplan'}")
    print(f"TARGET_HASH: {target_hash}")
    print(f"CAPSULE_HASH: {capsule_hash}")
    return 0


# G1 sentinel: execution_outcome and combined must be dispatched via router.
_EXECUTION_KINDS_REQUIRING_ROUTER: frozenset[str] = frozenset({"execution_outcome", "combined"})
_GD_ROUTER_INVOCATION_ENV = "GD_REVIEW_ROUTER_INVOCATION_ID"

# All kinds where the live writer still emits v1 VERDICT markdown.
# code_diff is included because the current codex-send-wait / writer pipeline
# has no v2 JSON fenced block support for code_diff yet (R8 fix).
_COMPAT_V1_DEFAULT_KINDS: frozenset[str] = frozenset({
    "execution_outcome", "combined", "code_diff",
})

# B3: kinds where compat_v1=False (v2 default) cannot proceed because the v2 template
# file does not yet exist.  Derived from Phase 1 report (v2-dependency-check.md):
# plan=MISSING, code_diff=MISSING.  When this guard fires, build_capsule_text raises
# ValueError("V2_TEMPLATE_NOT_READY: ...") so callers can exit 1 cleanly.
_KINDS_REQUIRING_COMPAT_V1_WHEN_V2_TEMPLATE_MISSING: frozenset[str] = frozenset({
    "plan", "code_diff",
})


def _resolve_compat_v1(kind: str, explicit: "bool | None") -> bool:
    """G2: infer compat_v1 from --kind when the flag is omitted (None).

    execution_outcome / combined / code_diff → True  (writer emits v1 header).
    plan → False                                      (v2 default).
    Explicit --compat-v1 / --no-compat-v1 always overrides inference.
    """
    if explicit is not None:
        return explicit
    return kind in _COMPAT_V1_DEFAULT_KINDS


def cmd_run_bridge(args: argparse.Namespace) -> int:
    if not args.live_transport:
        print("live-transport flag required for actual delivery", file=sys.stderr)
        return 2

    # G1 sentinel: execution_outcome/combined --live-transport must arrive via
    # gd-review-router.py, which sets GD_REVIEW_ROUTER_INVOCATION_ID. Direct
    # invocation is forbidden to prevent models from hand-composing bridge args.
    if args.kind in _EXECUTION_KINDS_REQUIRING_ROUTER:
        if not os.environ.get(_GD_ROUTER_INVOCATION_ENV):
            print(
                f"DIRECT_BRIDGE_FORBIDDEN_FOR_EXECUTION_KIND: --kind={args.kind!r} "
                f"--live-transport must be invoked via gd-review-router.py "
                f"(which sets {_GD_ROUTER_INVOCATION_ENV}). "
                "Direct bridge invocation for execution review is forbidden.",
                file=sys.stderr,
            )
            return 1

    # Plan live guard: for plan review, the target must be the original plan file,
    # NOT a /review2 capsule.  A capsule path (filename == "capsule.md") indicates
    # the caller is forwarding the L2 audit context instead of the plan itself.
    if args.kind == "plan":
        sys.path.insert(0, str(GD_PROJECT_ROOT / "scripts"))
        from lib.path_classification import is_review2_capsule_path  # noqa: E402
        if is_review2_capsule_path(args.target):
            print(
                "PLAN_TARGET_MUST_BE_ORIGINAL_PLAN: --kind=plan received a capsule "
                f"file as target ({args.target!r}). Pass the original plan file, "
                "not the /review2 capsule.",
                file=sys.stderr,
            )
            return 1

    # Bounded-parallel controller (revision=19+) manages concurrency at the
    # suite level via ThreadPoolExecutor. The per-bridge global lock file is
    # no longer needed and has been removed. Each bridge invocation is
    # independently dispatched by the controller with max_parallel=1 or 2.
    return _cmd_run_bridge_inner(args)


def _cmd_run_bridge_inner(args: argparse.Namespace) -> int:
    target = Path(args.target)
    cwd = Path(args.cwd)
    out_path = Path(args.out)
    compat_v1 = _resolve_compat_v1(args.kind, getattr(args, "compat_v1", None))

    related = _load_related_context(getattr(args, "related_context", None))
    try:
        capsule, target_hash, capsule_hash, gd_baseline_key, run_id = build_capsule_text(
            args.kind, target, cwd,
            queue_job_id=getattr(args, "queue_job_id", None),
            target_role=getattr(args, "target_role", None),
            related_context=related,
            compat_v1=compat_v1,
        )
    except ValueError as e:
        msg = str(e)
        if msg.startswith("INVALID_REVIEW_KIND_FOR_MODE") or msg.startswith("V2_TEMPLATE_NOT_READY"):
            print(f"ERROR: {msg}", file=sys.stderr)
            return 1
        print(f"ERROR: {msg}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    target_str = str(target.resolve())
    # Review Trust §Step 2: surface queue/role/hash so aggregator can capture
    effective_queue_id = getattr(args, "queue_job_id", None) or f"adhoc-{run_id}"
    effective_role = getattr(args, "target_role", None) or "subplan"
    print(f"QUEUE_JOB_ID: {effective_queue_id}")
    print(f"TARGET_ROLE: {effective_role}")
    print(f"TARGET_HASH: {target_hash}")
    print(f"CAPSULE_HASH: {capsule_hash}")

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
            timeout=getattr(args, "writer_timeout_sec", 600),
        )
    except subprocess.TimeoutExpired:
        timeout_sec = getattr(args, "writer_timeout_sec", 600)
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"writer subprocess timeout >{timeout_sec}s")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print("TRANSPORT_RESULT: N/A")
        return 1

    writer_stdout = result.stdout
    writer_stderr = result.stderr
    writer_exit = result.returncode

    # 解析 writer stdout 找 result path（Review Trust §Step 1：用共享 helper）。
    # 严格防御：path 存在性下游另查；这里只做正则提取，让 test driver 能纯离线探测。
    result_path = parse_writer_result_path(writer_stdout)

    # writer 任意非 ✓ APPROVED / ✗ REQUIRES_CHANGES → mapped FAILED
    # Plan I §1: 修去除 bare "DEGRADED" 模糊匹配 — 该子串可能出现在 capsule 内容或
    # codex 输出中（误把成功 review 当 transport degraded）。只匹配 writer 自己的 marker。
    if "[REVIEW] ⚠️ DEGRADED" in writer_stdout:
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
        # Plan I §1: 区分 "未匹配到 path" 与 "匹配到但文件不存在"
        head = "\n".join(writer_stdout.splitlines()[:20])
        if not result_path:
            reason = f"WRITER_RESULT_PATH_MISSING: regex 在 writer stdout 未匹配到 'Full result:'。head[20]:\n{head}"
        else:
            reason = f"WRITER_RESULT_PATH_MISSING: writer 报 path={result_path!r} 但文件不存在。head[20]:\n{head}"
        mapped = _failed_mapped("codex", args.kind, target_str, reason)
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print("TRANSPORT_RESULT: N/A")
        print(f"ERROR: WRITER_RESULT_PATH_MISSING")
        return 1

    raw_text = Path(result_path).read_text(encoding="utf-8")
    mapped, errs = parse_raw_to_mapped(args.kind, target_str, raw_text, compat_v1=compat_v1)
    out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")

    # L3: run content-evidence validator on the live transport result (same as
    # parse-transport path). Fail-closed on failure, timeout, missing script, or
    # missing target (F2+F5 fix). Also updates source_of_truth_decision.value (F-R6-2).
    l3_script = GD_PROJECT_ROOT / "scripts" / "gd-validate-review-content-evidence.py"
    target_for_l3 = Path(args.target)
    raw_path_for_l3 = Path(result_path)
    _l3_precond_failed = False
    _l3_precond_reason = ""
    if not l3_script.exists():
        _l3_precond_failed = True
        _l3_precond_reason = "L3 content-evidence script missing — fail-closed"
        print("L3_CONTENT_EVIDENCE: script missing — fail-closed", file=sys.stderr)
    elif not target_for_l3.exists():
        _l3_precond_failed = True
        _l3_precond_reason = f"L3 target not found ({target_for_l3}) — fail-closed"
        print(f"L3_CONTENT_EVIDENCE: target not found ({target_for_l3}) — fail-closed", file=sys.stderr)
    if _l3_precond_failed:
        _apply_l3_failure(mapped, _l3_precond_reason, out_path)
    else:
        l3_failed = False
        l3_reason = ""
        try:
            l3_result = subprocess.run(
                [sys.executable, str(l3_script),
                 "--target", str(target_for_l3), "--review", str(raw_path_for_l3)],
                capture_output=True, text=True, timeout=30,
            )
            if l3_result.returncode != 0:
                l3_failed = True
                l3_reason = "L3 content-evidence validator rejected review: " + l3_result.stdout.strip()[:200]
                print(f"L3_CONTENT_EVIDENCE: FAILED — {l3_result.stdout.strip()[:200]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            l3_failed = True
            l3_reason = "L3 content-evidence validator timed out (30s) — fail-closed"
            print("L3_CONTENT_EVIDENCE: timeout (30s) — fail-closed", file=sys.stderr)
        except Exception as l3_err:
            l3_failed = True
            l3_reason = f"L3 content-evidence validator error — {l3_err}"
            print(f"L3_CONTENT_EVIDENCE: error — {l3_err}", file=sys.stderr)

        if l3_failed:
            _apply_l3_failure(mapped, l3_reason, out_path)

    decision = mapped["gd_review_decision"]
    status = mapped["review_run_status"]
    print(f"GD_CODEX_BRIDGE_STATUS: {status}")
    print(f"GD_REVIEW_DECISION: {decision}")
    print(f"MAPPED_RESULT: {out_path}")
    print(f"TRANSPORT_RESULT: {result_path}")
    return 0 if decision == "APPROVED" else (1 if decision == "FAILED" else 0)


def _apply_l3_failure(mapped: dict, reason: str, out_path: "Path") -> None:
    """Apply L3 failure to mapped result and write to disk (F-R6-2 fix).

    Updates review_run_status, gd_review_decision, merge_notes.degraded_reason,
    and source_of_truth_decision.value so all decision fields stay consistent.
    """
    mapped["review_run_status"] = "degraded"
    mapped["gd_review_decision"] = "FAILED"
    mapped["merge_notes"]["degraded_reason"] = reason
    # Sync source_of_truth_decision.value so v2 consumers see a consistent picture.
    sotd = mapped.get("source_of_truth_decision")
    if isinstance(sotd, dict):
        sotd["value"] = "FAILED"
    out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_parse_transport(args: argparse.Namespace) -> int:
    target = Path(args.target)
    raw_path = Path(args.raw_result)
    if not raw_path.exists():
        print(f"ERROR: raw 文件不存在 {raw_path}", file=sys.stderr)
        return 2

    compat_v1 = _resolve_compat_v1(args.kind, getattr(args, "compat_v1", None))
    active_enum = _get_active_kind_enum(compat_v1)
    if args.kind not in active_enum:
        mode_label = "v1 compat" if compat_v1 else "v2 default"
        print(
            f"ERROR: INVALID_REVIEW_KIND_FOR_MODE: --kind={args.kind!r} not in "
            f"{mode_label} enum {sorted(active_enum)}",
            file=sys.stderr,
        )
        return 1

    raw_text = raw_path.read_text(encoding="utf-8")
    mapped, errs = parse_raw_to_mapped(
        args.kind,
        str(target.resolve() if target.exists() else target),
        raw_text,
        compat_v1=compat_v1,
    )

    out_path = Path(args.out)
    out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")

    # L3: content-evidence validator (SC-W1-1)
    # Failure → aggregate bucket "wrapper_schema_fail" (blocking).
    # review_run_status must stay schema-valid ("degraded"); wrapper_schema_fail
    # is an aggregate-level bucket, not a review_run_status enum value (F1 fix).
    # Timeout, exceptions, missing script/target are all fail-closed (F2+F5 fix).
    l3_script = GD_PROJECT_ROOT / "scripts" / "gd-validate-review-content-evidence.py"
    _l3_pre_fail = False
    _l3_pre_reason = ""
    if not l3_script.exists():
        _l3_pre_fail = True
        _l3_pre_reason = "L3 content-evidence script missing — fail-closed"
        print("L3_CONTENT_EVIDENCE: script missing — fail-closed", file=sys.stderr)
    elif not target.exists():
        _l3_pre_fail = True
        _l3_pre_reason = f"L3 target not found ({target}) — fail-closed"
        print(f"L3_CONTENT_EVIDENCE: target not found ({target}) — fail-closed", file=sys.stderr)
    if _l3_pre_fail:
        _apply_l3_failure(mapped, _l3_pre_reason, out_path)
    else:
        l3_failed = False
        l3_reason = ""
        try:
            l3_result = subprocess.run(
                [sys.executable, str(l3_script), "--target", str(target), "--review", str(raw_path)],
                capture_output=True, text=True, timeout=30,
            )
            if l3_result.returncode != 0:
                l3_failed = True
                l3_reason = "L3 content-evidence validator rejected review: " + l3_result.stdout.strip()[:200]
                print(f"L3_CONTENT_EVIDENCE: FAILED — {l3_result.stdout.strip()[:200]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            l3_failed = True
            l3_reason = "L3 content-evidence validator timed out (30s) — fail-closed"
            print("L3_CONTENT_EVIDENCE: timeout (30s) — fail-closed", file=sys.stderr)
        except Exception as l3_err:
            l3_failed = True
            l3_reason = f"L3 content-evidence validator error — {l3_err}"
            print(f"L3_CONTENT_EVIDENCE: error — {l3_err}", file=sys.stderr)

        if l3_failed:
            _apply_l3_failure(mapped, l3_reason, out_path)

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

    # Matrix #1.5: any completed_with_constraint → REQUIRES_CHANGES (Plan 1)
    if any(s == "completed_with_constraint" for s in statuses):
        return "REQUIRES_CHANGES", "completed", "matrix #1.5: constrained_review_not_final_approval"

    # Matrix #1: 双方 APPROVED + completed → APPROVED
    if all(d == "APPROVED" for d in decisions) and all(s == "completed" for s in statuses):
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

    # cmd_merge has no --kind arg; infer from the loaded JSON (review_kind field).
    _merge_kind = claude.get("review_kind") or codex.get("review_kind") or "plan"
    compat_v1 = _resolve_compat_v1(_merge_kind, getattr(args, "compat_v1", None))

    # Matrix #5: 任一 schema fail → FAILED
    schema_errs = []
    for label, d in [("claude", claude), ("codex", codex)]:
        es = validate_mapped_schema(d, compat_v1=compat_v1)
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
            compat_v1=compat_v1,
        )
        merged["merge_notes"]["arbitration_reason"] = "schema fail"
    else:
        decision, status, reason = _merge_decision(claude, codex)
        if compat_v1:
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
        else:
            # v2-shaped merged result (mirrors source review_kind/target_role).
            merged_template_kind = claude.get(
                "template_kind",
                REVIEW_KIND_TO_TEMPLATE_KIND.get(review_kind, "gd-plan-review"),
            )
            merged_target_role = claude.get(
                "target_role",
                REVIEW_KIND_TO_TARGET_ROLE.get(review_kind, "plan_artifact"),
            )
            merged_review_target_kind = claude.get(
                "review_target_kind",
                REVIEW_KIND_TO_REVIEW_TARGET_KIND_V2.get(review_kind, "plan_only"),
            )
            merged = {
                "schema_version": "2.0",
                "template_kind": merged_template_kind,
                "review_kind": review_kind,
                "review_target_kind": merged_review_target_kind,
                "target_role": merged_target_role,
                "reviewer": "claude_subagent_merge",
                "review_target": review_target,
                "review_run_status": status,
                "gd_review_decision": decision,
                "source_of_truth_decision": {
                    "location": "top_level_machine_header",
                    "value": decision,
                },
                "scope_checked": [
                    {
                        "area": "claude vs codex merge",
                        "result": "pass" if decision == "APPROVED" else ("fail" if decision == "FAILED" else "n_a"),
                        "evidence": reason[:200],
                    }
                ],
                "findings": [],
                "merge_notes": {
                    "conflict_with_other_reviewer": claude["gd_review_decision"] != codex["gd_review_decision"],
                    "arbitration_reason": reason,
                },
                "residual_risk": "",
                "timestamp": _now_iso(),
            }
        # 透传 reviewer findings 摘要：按优先级保留 REQUIRES_CHANGES > FAILED 的 findings
        for src in (codex, claude):
            if src["gd_review_decision"] == "REQUIRES_CHANGES":
                merged["findings"] = src.get("findings", [])
                break

    final_errs = validate_mapped_schema(merged, compat_v1=compat_v1)
    if final_errs:
        # 自身 schema fail → 裸 FAILED
        merged = _failed_mapped(
            "claude_subagent_merge", review_kind, review_target,
            f"merge result schema fail: {final_errs[0]}",
            compat_v1=compat_v1,
        )

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
        mapped, errs = parse_raw_to_mapped(
            kind, f"fixtures/review-bridge/{fname}", raw, compat_v1=True,
        )
        got = (mapped["review_run_status"], mapped["gd_review_decision"])
        if got != (exp_status, exp_decision):
            failures.append(f"parse {fname}: want=({exp_status},{exp_decision}) got={got}")
        else:
            print(f"  ✓ parse {fname}: {got[0]} / {got[1]}")

    # ---------- Plan 8 v4.1 Fix P1-1: v2 parse fixtures ----------
    # Each case: (relative_fixture, kind, exp_status, exp_decision, compat_v1)
    # The v2 parser extracts the gd-review-result-json fenced block, validates
    # against the minimal v2 sanity validator, and asserts top-vs-json decision
    # consistency.
    v2_dir = FIXTURES_DIR / "v2"
    v2_parse_cases = [
        # default v2 path: all four kinds + one malformed
        ("v2-plan-approved.md", "plan", "completed", "APPROVED", False, "v2"),
        ("v2-execution-outcome-requires-changes.md", "execution_outcome",
         "completed", "REQUIRES_CHANGES", False, "v2"),
        ("v2-code-diff-approved.md", "code_diff", "completed", "APPROVED", False, "v2"),
        ("v2-combined-approved.md", "combined", "completed", "APPROVED", False, "v2"),
        ("v2-plan-malformed.md", "plan", "degraded", "FAILED", False, "v2"),
        # mode-mismatch: v1 kind without --compat-v1 → fail-closed
        ("v2-plan-approved.md", "code", "failed_to_run", "FAILED", False, "v2"),
        # mode-mismatch: v2 plan raw with --compat-v1 kind=execution_outcome → degraded/FAILED
        # (v1 title "Code Review Result" not found in v2 plan body; result is degraded not failed_to_run
        # because revision=20 added execution_outcome to V1_ENUM so the kind gate passes but body parsing degrades)
        ("v2-plan-approved.md", "execution_outcome", "degraded", "FAILED", True, "v2"),
        # v1 kind under --compat-v1 still works on the legacy v1 fixtures
        ("raw-approved-plan.md", "plan", "completed", "APPROVED", True, "v1"),
        ("raw-approved-code.md", "code", "completed", "APPROVED", True, "v1"),
    ]
    for fname, kind, exp_status, exp_decision, compat_v1, where in v2_parse_cases:
        base = v2_dir if where == "v2" else FIXTURES_DIR
        fp = base / fname
        if not fp.exists():
            failures.append(f"v2-parse {fname} compat_v1={compat_v1}: fixture missing ({fp})")
            continue
        raw = fp.read_text(encoding="utf-8")
        target_label = f"fixtures/review-bridge/{'v2/' if where == 'v2' else ''}{fname}"
        mapped, errs = parse_raw_to_mapped(kind, target_label, raw, compat_v1=compat_v1)
        got = (mapped["review_run_status"], mapped["gd_review_decision"])
        if got != (exp_status, exp_decision):
            failures.append(
                f"v2-parse {fname} kind={kind} compat_v1={compat_v1}: "
                f"want=({exp_status},{exp_decision}) got={got} errs={errs[:2]!r}"
            )
        else:
            print(f"  ✓ v2-parse {fname} kind={kind} compat={compat_v1}: {got[0]} / {got[1]}")

    # ---------- Plan 8 v4.1 Fix P1-1: v2 merge fixture ----------
    # Sanity: feed two v2-shaped APPROVED parses into _merge_decision and
    # ensure validate_mapped_schema(compat_v1=False) accepts the result.
    v2_plan = v2_dir / "v2-plan-approved.md"
    if v2_plan.exists():
        raw = v2_plan.read_text(encoding="utf-8")
        mapped_a, _ = parse_raw_to_mapped("plan", "fixtures/review-bridge/v2/v2-plan-approved.md", raw, compat_v1=False)
        mapped_b, _ = parse_raw_to_mapped("plan", "fixtures/review-bridge/v2/v2-plan-approved.md", raw, compat_v1=False)
        es_a = validate_mapped_schema(mapped_a, compat_v1=False)
        es_b = validate_mapped_schema(mapped_b, compat_v1=False)
        if es_a or es_b:
            failures.append(f"v2-merge: parsed v2 inputs failed v2 validator: a={es_a[:2]!r} b={es_b[:2]!r}")
        else:
            decision, status, _ = _merge_decision(mapped_a, mapped_b)
            if decision != "APPROVED" or status != "completed":
                failures.append(f"v2-merge: want=(APPROVED,completed) got=({decision},{status})")
            else:
                print(f"  ✓ v2-merge: APPROVED / completed (matrix #1)")

    # ---------- Merge fixtures ----------
    sf = SIDECAR_FIXTURES_DIR
    merge_cases = [
        ("claude-approved.json", "codex-approved.json", "APPROVED"),
        ("claude-approved.json", "codex-requires-changes.json", "REQUIRES_CHANGES"),
        ("claude-approved.json", "codex-timeout.json", "FAILED"),  # codex failed_to_run → matrix #4
        ("claude-failed.json", "codex-approved.json", "FAILED"),
        ("claude-failed.json", "codex-requires-changes.json", "FAILED"),
        # Plan 1: completed_with_constraint must not produce APPROVED (matrix #1.5)
        ("claude-approved.json", "codex-approved-completed-with-constraint.json", "REQUIRES_CHANGES"),
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
        # 模拟 cmd_merge 内部逻辑（merge fixtures are v1-shape）
        schema_errs_c = validate_mapped_schema(claude, compat_v1=True)
        schema_errs_k = validate_mapped_schema(codex, compat_v1=True)
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

    # ---------- Plan 8 v4.1 Step 7 + Fix P1-1: v2 routing fixtures ----------
    # Each descriptor exercises either:
    #   - subcommand="build-capsule" → build_capsule_text() routing assertion
    #   - subcommand="parse-transport" → parse_raw_to_mapped() v2 path assertion
    # Both honour `compat_v1` and `_test_meta._expect`.
    if BRIDGE_V2_FIXTURES_DIR.exists():
        for fp in sorted(BRIDGE_V2_FIXTURES_DIR.glob("*.json")):
            try:
                desc = json.loads(fp.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                failures.append(f"v2-routing {fp.name}: invalid JSON: {e}")
                continue
            meta = desc.get("_test_meta", {})
            expect = meta.get("_expect")
            if expect not in {"PASS", "FAIL"}:
                failures.append(f"v2-routing {fp.name}: _test_meta._expect must be PASS|FAIL")
                continue

            subcommand = desc.get("subcommand", "build-capsule")
            kind = desc.get("kind")
            compat_v1 = bool(desc.get("compat_v1", False))
            if not kind:
                failures.append(f"v2-routing {fp.name}: missing 'kind'")
                continue

            if subcommand == "build-capsule":
                target_rel = desc.get("target")
                if not target_rel:
                    failures.append(f"v2-routing {fp.name}: missing 'target' for build-capsule")
                    continue
                target_abs = GD_PROJECT_ROOT / target_rel
                try:
                    capsule_text, _, _, _, _ = build_capsule_text(
                        kind, target_abs, GD_PROJECT_ROOT, compat_v1=compat_v1,
                    )
                    got_status = "PASS"
                    err_msg = ""
                except (ValueError, FileNotFoundError) as exc:
                    capsule_text = ""
                    got_status = "FAIL"
                    err_msg = str(exc)

                if got_status != expect:
                    failures.append(
                        f"v2-routing {fp.name}: want={expect} got={got_status} "
                        f"err={err_msg!r}"
                    )
                    continue
                if expect == "PASS":
                    exp_template = desc.get("expected_template_kind")
                    exp_schema = desc.get("expected_schema_path")
                    if exp_template and f"TEMPLATE_KIND: {exp_template}\n" not in capsule_text:
                        failures.append(
                            f"v2-routing {fp.name}: capsule missing 'TEMPLATE_KIND: {exp_template}'"
                        )
                        continue
                    if exp_schema and f"EXPECTED_OUTPUT_SCHEMA: {exp_schema}\n" not in capsule_text:
                        failures.append(
                            f"v2-routing {fp.name}: capsule missing 'EXPECTED_OUTPUT_SCHEMA: {exp_schema}'"
                        )
                        continue
                    print(f"  ✓ v2-routing {fp.name}: PASS (template={exp_template})")
                else:
                    exp_err = desc.get("expected_error_substring", "")
                    if exp_err and exp_err not in err_msg:
                        failures.append(
                            f"v2-routing {fp.name}: error msg missing {exp_err!r}; got {err_msg!r}"
                        )
                        continue
                    print(f"  ✓ v2-routing {fp.name}: FAIL as expected ({exp_err})")
                continue

            if subcommand == "parse-transport":
                raw_rel = desc.get("raw_fixture")
                if not raw_rel:
                    failures.append(f"v2-routing {fp.name}: missing 'raw_fixture'")
                    continue
                raw_path = GD_PROJECT_ROOT / raw_rel
                if not raw_path.exists():
                    failures.append(f"v2-routing {fp.name}: raw fixture missing {raw_path}")
                    continue
                raw_text = raw_path.read_text(encoding="utf-8")
                mapped, errs = parse_raw_to_mapped(
                    kind, raw_rel, raw_text, compat_v1=compat_v1,
                )
                got_status = (
                    mapped["review_run_status"], mapped["gd_review_decision"]
                )
                want_status = (
                    desc.get("expected_review_run_status"),
                    desc.get("expected_gd_review_decision"),
                )
                if got_status != want_status:
                    failures.append(
                        f"v2-routing {fp.name}: want={want_status} got={got_status} errs={errs[:2]!r}"
                    )
                    continue

                if expect == "PASS":
                    for fld, want_key in (
                        ("template_kind", "expected_template_kind"),
                        ("target_role", "expected_target_role"),
                        ("review_target_kind", "expected_review_target_kind"),
                    ):
                        wanted = desc.get(want_key)
                        if wanted is not None and mapped.get(fld) != wanted:
                            failures.append(
                                f"v2-routing {fp.name}: mapped[{fld}]={mapped.get(fld)!r} != {wanted!r}"
                            )
                            break
                    else:
                        print(
                            f"  ✓ v2-routing {fp.name}: parse-transport PASS "
                            f"({got_status[0]}/{got_status[1]})"
                        )
                else:
                    exp_err = desc.get("expected_error_substring", "")
                    err_blob = "; ".join(errs)
                    if exp_err and exp_err not in err_blob:
                        failures.append(
                            f"v2-routing {fp.name}: errs missing {exp_err!r}; got {err_blob!r}"
                        )
                        continue
                    print(f"  ✓ v2-routing {fp.name}: parse-transport FAIL as expected ({exp_err})")
                continue

            failures.append(f"v2-routing {fp.name}: unknown subcommand {subcommand!r}")
    else:
        print(f"  (skip v2-routing: {BRIDGE_V2_FIXTURES_DIR} not present)")

    # ---------- Lock sentinel regression (SC-1, GD-1 revision=18) ----------
    # NOTE: revision=19+ removed the per-bridge global lock file. Concurrency
    # is now managed by the suite controller's ThreadPoolExecutor (max_parallel).
    # The per-bridge exit-3 concurrent-bridge path no longer exists in run-bridge.
    # This regression block is intentionally skipped (lock sentinel deprecated).
    print(f"  (lock-sentinel: SKIPPED — global lock removed in revision=19; "
          f"concurrency managed by bounded-parallel controller)")

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

    # Plan 8 v4.1 Step 7: --kind accepts the union of v1+v2 enums; the actual
    # enum is selected at runtime based on --compat-v1 (see build_capsule_text
    # which raises INVALID_REVIEW_KIND_FOR_MODE for the wrong combination).
    _all_kind_choices = sorted(REVIEW_KIND_ENUM | REVIEW_KIND_V1_ENUM)

    p_b = sub.add_parser("build-capsule")
    p_b.add_argument("--kind", required=True, choices=_all_kind_choices)
    p_b.add_argument("--target", required=True)
    p_b.add_argument("--cwd", required=True)
    p_b.add_argument("--out", required=True)
    p_b.add_argument("--compat-v1", action=argparse.BooleanOptionalAction, default=None,
                     help="Opt-in/out of legacy v1 enum. If omitted, inferred from --kind "
                          "(code_diff/execution_outcome/combined → True; plan → False).")
    # Review Trust §Step 2: queue metadata
    p_b.add_argument("--queue-job-id", default=None,
                     help="Optional queue job id (e.g. 'q1-master_plan'); default=adhoc-<run_id>")
    p_b.add_argument("--target-role", default=None,
                     choices=sorted(VALID_TARGET_ROLES),
                     help="Capsule target role; default=subplan")
    p_b.add_argument("--related-context", default=None,
                     help="Path to JSON file with related context entries (role/path/hash)")

    p_r = sub.add_parser("run-bridge")
    p_r.add_argument("--kind", required=True, choices=_all_kind_choices)
    p_r.add_argument("--target", required=True)
    p_r.add_argument("--cwd", required=True)
    p_r.add_argument("--out", required=True)
    p_r.add_argument("--compat-v1", action=argparse.BooleanOptionalAction, default=None,
                     help="execution_outcome/combined: default True (Codex still outputs v1 header); plan/code_diff: default False (v2). Explicit --compat-v1/--no-compat-v1 overrides.")
    p_r.add_argument("--queue-job-id", default=None)
    p_r.add_argument("--target-role", default=None,
                     choices=sorted(VALID_TARGET_ROLES))
    p_r.add_argument("--related-context", default=None)
    p_r.add_argument("--live-transport", action="store_true",
                     help="必须显式传入才允许调用旧 writer 投递 Codex")
    p_r.add_argument("--writer-timeout-sec", type=int, default=600,
                     metavar="SEC",
                     help="Writer subprocess timeout in seconds (300-1800). Default: 600.")

    p_p = sub.add_parser("parse-transport")
    p_p.add_argument("--kind", required=True, choices=_all_kind_choices)
    p_p.add_argument("--target", required=True)
    p_p.add_argument("--raw-result", required=True)
    p_p.add_argument("--out", required=True)
    p_p.add_argument("--compat-v1", action=argparse.BooleanOptionalAction, default=None,
                     help="execution_outcome/combined: default True; plan/code_diff: default False. Explicit flag overrides kind-based inference.")

    p_m = sub.add_parser("merge")
    p_m.add_argument("--claude", required=True)
    p_m.add_argument("--codex", required=True)
    p_m.add_argument("--out", required=True)
    p_m.add_argument("--compat-v1", action=argparse.BooleanOptionalAction, default=None,
                     help="Opt-in/out of v1 schema validation. If omitted, inferred from "
                          "review_kind in the input JSONs (code_diff/execution_outcome → True; plan → False).")

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
