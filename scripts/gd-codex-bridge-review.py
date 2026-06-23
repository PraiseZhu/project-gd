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
sys.path.insert(0, str(GD_PROJECT_ROOT / "scripts"))
from lib.sc_extraction import SC_ID_RE, extract_sc_ids, extract_reviewable_ids, _TASK_HEADER_RE  # noqa: E402

SCHEMA_PATH_V1 = GD_PROJECT_ROOT / "schema" / "gd-review-result.schema.json"
SCHEMA_PATH_V2 = GD_PROJECT_ROOT / "schema" / "gd-review-result-v2.schema.json"
# Backward-compat alias (legacy code may still reference SCHEMA_PATH).
SCHEMA_PATH = SCHEMA_PATH_V1
STANDARD_PATH = GD_PROJECT_ROOT / "prompts" / "gd-review-standard.md"
GOAL_PATH = GD_PROJECT_ROOT / "docs" / "gd-v7-project-goal.md"

# SC-0 (T0): 显式塞入 capsule 的 GD 权威上下文（不让 codex 猜）。
# GD 权威 = 项目 CLAUDE.md（commands/gd.md + prompts/gd-review-standard.md）。
_CLAUDE_MD_CONTEXT_SUMMARY = (
    "GD 权威源 = 项目 CLAUDE.md（commands/gd.md lock_revision=22 + prompts/gd-review-standard.md）。"
    "审查规则全部源自 CLAUDE.md；本仓不给 codex 新增 AGENTS.md。\n"
    "- FORBIDDEN（硬边界）：不写 Claude/Codex runtime 基础设施目录（~/.claude、~/.codex）；"
    "不动 release profiles（release_closure / runtime_parity，L2 不授予 release approval）；"
    "不改 daemon / transport 脚本源（改 vendor→install）；不 commit、install 前 SOURCE_READY_INSTALL_BLOCKED。\n"
    "- VERDICT 命名：用 GD_REVIEW_DECISION / REV_VERDICT，绝不输出裸 VERDICT:（触发 live hook regex 误判）。\n"
    "- 三档：L1(/review1) / L2(/review2) / L3(/gd)；plan/code/execution-result 是 review target 类型，不是档位。"
)

# SC-0 (T0): deep 模式允许的查证命令（明确 codex 能跑哪些命令，不只开 workspace-write）。
_DEEP_ALLOWED_COMMANDS_SECTION = (
    "\n## 允许的查证命令（deep）\n\n"
    "deep 模式下为产出真实证据（evidence），应主动运行下列只读查证命令，并把 exit code / 摘要写入 finding evidence：\n"
    "- `rg` / `grep`：在 --cwd 内搜索符号/字符串\n"
    "- `git diff HEAD` / `git log -p -n`：查看 dirty 与历史（code 路；只读，勿改）\n"
    "- `nl -ba <file>` / `cat -n`：带行号读文件，evidence 须含 path:line\n"
    "- `stat` / `test -f`：验证 deliverable / artifact 是否存在\n"
    "- `python3 -c '...'`：必要时做最小自洽检查\n"
    "**禁止**：`git commit` / `git push` / 写 runtime 基础设施 / 改 daemon。workspace-write 仅限本审查 workcopy。\n"
)
_DEEP_EXEC_TIMEOUT_SEC = 720
_DEEP_SEND_TIMEOUT_SEC = 1500
_DEEP_WRITER_TIMEOUT_SEC = 1700
# Non-deep PLAN reviews reuse the deep timeout ladder: gpt-5.x at xhigh reasoning
# needs >240s to review a large (20K+) plan capsule, but the daemon default is
# CODEX_EXEC_TIMEOUT=240 / client CODEX_SEND_WAIT_TIMEOUT=540. A non-deep plan
# review that passes NO timeout flags therefore times out twice and FAILs (root
# cause of the 2026-06-22 AKB2 CQL plan-review failure). Kept separate from _DEEP_*
# so changing one budget never silently moves the other. Plan review stays
# read-only — it must NOT pass --mode workspace-write.
_PLAN_EXEC_TIMEOUT_SEC = 720
_PLAN_SEND_TIMEOUT_SEC = 1500
_PLAN_WRITER_TIMEOUT_SEC = 1700
# Non-deep non-plan (fast path) MUST also hold the ladder invariant
# daemon_worst(2*EXEC=1440) < send_wait < writer: the daemon runs at plist
# CODEX_EXEC_TIMEOUT=720 (not the script default 240), so worst-case = 2*720 = 1440.
# The old fast path passed NO timeout flags → writer default send_wait=900 < 1440
# → a non-deep review whose attempt 1 fails and retries (attempt 2 reaches ~1440s)
# gets killed by the client send_wait(900) mid-flight (root cause of T-P0, witnessed
# in archive: attempt=2 exit=124). Reuse the same ladder as deep/plan so the
# invariant 2*exec(1440) < send(1500) < writer(1700) holds uniformly.
_NON_DEEP_EXEC_TIMEOUT_SEC = 720
_NON_DEEP_SEND_TIMEOUT_SEC = 1500
_NON_DEEP_WRITER_TIMEOUT_SEC = 1700
# Controller/router upper cap the ladder must stay under (documented at the
# dispatch sites; surfaced here so the invariant test can reference it).
_REVIEW_LADDER_OUTER_CAP_SEC = 1800


def _writer_timeout_args(deep: bool, kind: str, writer_timeout_sec: int = 600) -> tuple[int, list[str]]:
    """Compute (writer subprocess timeout, extra writer CLI args) for one dispatch.

    Single source of truth for the timeout ladder, shared by both dispatch sites
    (the plan dual-lens path and the single-lens path) so they can never drift:

    - deep            → workspace-write + 720/1500/1700 ladder.
    - non-deep plan   → read-only + 720/1500/1700 ladder (NO --mode workspace-write).
    - other non-deep  → 720/1500/1700 ladder (T-P0: daemon runs at plist EXEC=720,
                        worst-case 2*720=1440; the old fast-path send_wait=900 broke
                        the invariant and killed retrying reviews mid-flight).

    Ladder invariant (enforced by tests): 2*exec(1440) <= send(1500) <= writer(1700).
    """
    if deep:
        return _DEEP_WRITER_TIMEOUT_SEC, [
            "--mode", "workspace-write",
            "--send-timeout", str(_DEEP_SEND_TIMEOUT_SEC),
            "--exec-timeout", str(_DEEP_EXEC_TIMEOUT_SEC),
        ]
    if kind == "plan":
        return _PLAN_WRITER_TIMEOUT_SEC, [
            "--send-timeout", str(_PLAN_SEND_TIMEOUT_SEC),
            "--exec-timeout", str(_PLAN_EXEC_TIMEOUT_SEC),
        ]
    # T-P0: non-deep non-plan also holds the invariant (daemon plist EXEC=720).
    return _NON_DEEP_WRITER_TIMEOUT_SEC, [
        "--send-timeout", str(_NON_DEEP_SEND_TIMEOUT_SEC),
        "--exec-timeout", str(_NON_DEEP_EXEC_TIMEOUT_SEC),
    ]

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
# HOME resolved at runtime (脱开发者用户名) so this works on the installer's
# machine. WRITER_PATH defaults to the LIVE transport, NOT the legacy ~/.claude
# install: the writer runs directly from vendor (CLAUDE.md §6) and reaches the
# daemon's ${CLAUDE_PLUGIN_DATA}/gd-handoff dir via its own state-paths.sh. The
# old default (~/.claude/scripts/review-result-writer.sh) pointed at a stale,
# daemon-less copy and made every live review fail with a silent
# "codex-send-wait exit 1". GD_WRITER_PATH_OVERRIDE still wins.
WRITER_PATH = Path(
    os.environ.get(
        "GD_WRITER_PATH_OVERRIDE",
        str(GD_PROJECT_ROOT / "vendor" / "l3-transport" / "scripts" / "review-result-writer.sh"),
    )
)

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


# Review Trust §Step 1 companion: parse the writer's structured terminal-status
# line `[REVIEW] STATUS: <status> reason=<reason>`. The writer emits this only
# on non-approved outcomes (transport_unavailable / codex_exit_N / no_verdict /
# malformed) so the bridge can classify a failure mode from stdout alone,
# without parsing stderr or bucketing every failure as a generic transport_failed.
WRITER_STATUS_RE = re.compile(
    r"^\[REVIEW\] STATUS:\s*(\S+)\s+reason=(\S+)\s*$", re.MULTILINE
)


def parse_writer_status_line(writer_stdout: str) -> tuple[str, str] | None:
    """Extract `[REVIEW] STATUS: <status> reason=<reason>` from writer stdout.
    Returns (status, reason) or None when the line is absent (approved /
    requires_changes path, or a writer version that doesn't emit it).
    """
    m = WRITER_STATUS_RE.search(writer_stdout)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


# Layer 4 (downstream gate signal): parse the writer's `[REVIEW] REVIEW_QUALITY:
# <value>` line so the bridge can stamp capsule provenance onto the mapped result.
# The writer emits this on every path (additive — does not alter VERDICT/exit).
# 'pre_fed' means the capsule carried VALIDATION_EVIDENCE (review1-style pre-fed
# conclusions); downstream gates must not treat a pre_fed APPROVED as a trusted
# deep-review. Absent → None; caller defaults to 'standard'.
REVIEW_QUALITY_RE = re.compile(
    r"^\[REVIEW\] REVIEW_QUALITY:\s*(\S+)", re.MULTILINE
)


def parse_writer_review_quality(writer_stdout: str) -> str | None:
    """Extract `[REVIEW] REVIEW_QUALITY: <value>` from writer stdout.

    Returns 'standard' | 'pre_fed' | None (absent → caller defaults to standard).
    Pure regex, like parse_writer_result_path / parse_writer_status_line, so unit
    tests can probe the parser without touching disk.
    """
    m = REVIEW_QUALITY_RE.search(writer_stdout)
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
SC_REF_RE = SC_ID_RE
VERDICT_LINE_RE = re.compile(r"^VERDICT:\s*(APPROVED|REQUIRES_CHANGES)\s*$", re.MULTILINE)
BARE_VERDICT_ANY_RE = re.compile(r"^(VERDICT|REV_VERDICT)\s*:", re.MULTILINE)
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")

# ----------------------------- Lens Emphasis Constants ----------------------------- #

_LENS_EMPHASIS_A = (
    "本视角额外侧重：目标链 / SC 覆盖完整性 / fail-closed 与治理不变量（结构与符合性视角）；"
    "但不改变 §Review Standard 的穷举与 conformance 职责。"
)
_LENS_EMPHASIS_B = (
    "本视角额外侧重：边界条件 / fallback 路径 / 收窄 scope 语义 / 漏报风险（对抗与边角视角）；"
    "但不改变 §Review Standard 的穷举与 conformance 职责。"
)

# L2（检查优先级排序镜头）：描述文本直接写入 REVIEW_LENS_EMPHASIS 行。
_EMPHASIS_CODEX_A = (
    "SC-conformance→边界/路径越界→接口/契约→失败模式/fallback→anti-fill 泛化"
)
_EMPHASIS_CODEX_B = (
    "失败模式/fallback→安全/secret 泄漏→anti-fill 泛化→SC-conformance→边界/路径越界"
)

# ----------------------------- Lens env protocol (SC-1 / T1) ----------------------------- #
# 统一 lens 协议：GD_REVIEW_LENS_TAG=codex_A|codex_B 是 L3 双镜头分化的唯一真源。
# controller / merge-loop 设该 env；bridge 在 _cmd_run_bridge_inner / cmd_build_capsule
# 读它 → build_capsule_text(lens_emphasis=<tag>) 走 L3 分支(:1294)给专属文案。
# 修 G1（断线）：旧实现从不读 lens env，capsule 永远落中立。
# 修 G2（值不对齐）：旧 env 名塞完整 priority 全文，L3 分支 .get(全文)→None→中立。
_GD_REVIEW_LENS_TAG_ENV = "GD_REVIEW_LENS_TAG"
_GD_REVIEW_LENS_PRIORITY_ENV = "GD_REVIEW_LENS_PRIORITY_TEXT"
_GD_REVIEW_LENS_EMPHASIS_ENV_LEGACY = "GD_REVIEW_LENS_EMPHASIS"
_LENS_TAGS: tuple[str, ...] = ("codex_A", "codex_B")


def _lens_params_from_env() -> tuple[str | None, str | None]:
    """从 env 推导 (emphasis, lens_emphasis)，供 build_capsule_text 调用。

    GD_REVIEW_LENS_TAG=codex_A|codex_B → lens_emphasis（L3 分析视角分化，唯一协议）。
    GD_REVIEW_LENS_PRIORITY_TEXT=<全文> → emphasis（L2 检查优先级排序行）；tag 存在时被 L3
      覆盖（build_capsule_text 内 lens_emphasis 优先级高于 emphasis）。
    Legacy GD_REVIEW_LENS_EMPHASIS 仅当其值恰为 codex_A/codex_B 时作为 tag 兜底。
    """
    tag = os.environ.get(_GD_REVIEW_LENS_TAG_ENV)
    if tag not in _LENS_TAGS:
        legacy = os.environ.get(_GD_REVIEW_LENS_EMPHASIS_ENV_LEGACY)
        tag = legacy if legacy in _LENS_TAGS else None
    lens_emphasis = tag  # L3 分化
    priority = os.environ.get(_GD_REVIEW_LENS_PRIORITY_ENV) or None
    return priority, lens_emphasis


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


# SC-1: count unique top-level SC IDs in a plan file for exhaustiveness gate.
# Fix B: 与 L3 用同一口径（extract_reviewable_ids：SC-N/SC-word + T-N 任务头），
# 消除「bridge 用 checklist 正则=0 / L3 用全文正则={SC-conformance}」漂移。
_PLAN_SC_ID_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*(" + SC_ID_RE.pattern + r")\b", re.MULTILINE)


def _count_sc_ids_in_target(target_path: str) -> int:
    """Return number of unique STRUCTURED reviewable IDs in target (排他性 gate 用)。

    Issue1: 用结构化 extract_reviewable_ids（checklist SC + T-头），不含全文散提
    （如 execution_outcome JSON 的 sc_acceptance SC-1、plan REVIEW_FOCUS 的 SC-conformance）。
    数了会让排他性 gate 误开、facet 行被误判 SHALLOW。与 L3 target_sc_ids 同口径。
    """
    try:
        text = Path(target_path).read_text(encoding="utf-8")
        return len(extract_reviewable_ids(text))
    except Exception:
        return 0


# SC-2: extract REVIEW_DOMAIN / REVIEW_FOCUS from plan §2 Review 对齐 section.
_PLAN_DOMAIN_RE = re.compile(r"REVIEW_DOMAIN\s*:\s*`([^`]+)`")
_PLAN_FOCUS_RE = re.compile(r"REVIEW_FOCUS\s*:\s*`([^`\n]+)`")


def _extract_plan_review_meta(target: Path) -> tuple[str | None, str | None]:
    """Return (domain, focus) from plan §2; (None, None) on failure/absence."""
    try:
        text = target.read_text(encoding="utf-8")
        sec2 = re.search(r"## 2[.\s]", text)
        if not sec2:
            return None, None
        snippet = text[sec2.start():]
        nxt = re.search(r"\n## ", snippet[3:])
        if nxt:
            snippet = snippet[: nxt.start() + 3]
        domain = _PLAN_DOMAIN_RE.search(snippet)
        focus = _PLAN_FOCUS_RE.search(snippet)
        return (domain.group(1).strip() if domain else None,
                focus.group(1).strip() if focus else None)
    except Exception:
        return None, None


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
                if not isinstance(fd["sc_refs"], list):
                    errs.append(f"findings[{i}].sc_refs 必须是数组")
                elif not fd["sc_refs"] and d.get("review_kind") != "code_diff":
                    errs.append(f"findings[{i}].sc_refs 必须非空数组（code_diff 除外）")
                else:
                    for sc_ref in fd["sc_refs"]:
                        if not isinstance(sc_ref, str) or not SC_ID_RE.fullmatch(sc_ref):
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
    allowed = set(required) | {"compatibility_mode", "cross_validation_findings", "run_evidence"}
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
            if not isinstance(sc_refs, list) or (not sc_refs and d.get("review_kind") != "code_diff"):
                errs.append(f"findings[{i}].sc_refs 必须非空数组（code_diff 除外）")

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
    # SC: SC-3,SC-W2 (explicit SC line). Use extract_sc_ids so placeholder tokens
    # like "SC-N" are not mistaken for real sc_refs.
    sc_match = re.search(r"^\s*SC:\s*(.+?)\s*$", block, re.MULTILINE)
    sc_refs: list[str] = []
    if sc_match:
        sc_refs = sorted(extract_sc_ids(sc_match.group(1)))
    # fallback: embedded SC refs in body ONLY (exclude title line). Scanning the
    # title picks up descriptive placeholders (e.g. "finding 缺 SC: SC-N 引用")
    # which then pass sc_refs validation and wrongly yield completed instead of
    # degraded for a missing-SC fixture.
    if not sc_refs:
        body_without_title = block.split("\n", 1)[1] if "\n" in block else ""
        sc_refs = sorted(extract_sc_ids(body_without_title))

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

    # SC-1: APPROVED exhaustiveness gate — Scope Checked rows must cover all SC-IDs in target.
    if verdict == "APPROVED":
        expected_sc_count = _count_sc_ids_in_target(target_str)
        # ABC 收尾: sc_rows 提取与 count 同口径认 T-N——count 认 T0-T7（结构化），
        # raw 的 `| T0 | pass |` 表行也须计入，否则 codex 按引导写 T-N 行却被数成 0 → 误判 SHALLOW。
        # 旧正则只 `^\| SC-N \|`，不认 `^\| T0 \|`。现 SC-ID + T-N 表行都算。
        sc_rows_in_raw = len({
            m.group(1)
            for m in re.finditer(
                r"^\|\s*(" + SC_ID_RE.pattern + r"|T\d+)\s*\|",
                raw_text,
                re.MULTILINE,
            )
        })
        if expected_sc_count > 0 and sc_rows_in_raw < expected_sc_count:
            reason = (
                f"SHALLOW_REVIEW_APPROVED: Scope Checked 表仅 {sc_rows_in_raw} 行"
                f" < 目标 SC 数 {expected_sc_count}，判 degraded"
            )
            return _failed_mapped("codex", kind, target_str, reason,
                                  "degraded", compat_v1=True), [reason]

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
        # SC-N 关联（wrapper 加严）— code_diff findings review code quality, not plan SC-IDs.
        if not f["sc_refs"] and kind != "code_diff":
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
    # SC-26: accept both "# Plan Review Result (v2)" and "# Plan Review Result" (without suffix)
    title = TITLE_BY_KIND_V2[kind]
    title_bare = title.replace(" (v2)", "")
    if f"# {title}" not in raw_text and f"# {title_bare}" not in raw_text:
        return (
            _failed_mapped(
                "codex", kind, target_str,
                f"raw 缺 v2 标题 # {title} (也尝试了不带 (v2) 后缀)", "degraded", compat_v1=False,
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


def merge_findings_union(
    findings_lists: list[list[dict]],
) -> list[dict]:
    """三方（codex_A、codex_B、Claude self-review）findings 取并集后去重。

    T1 (L2 parity) — Round 1 双 codex emphasis lens 三方并集去重原语。

    每个 findings_lists 元素是一个 reviewer 的 finding 列表，每条 finding 格式：
      {
        "file":     str,           # 文件路径（相对）
        "line":     int,           # 行号（1-based）
        "category": str,           # 问题类别，如 "anti-fill" / "sc-conformance" 等
        "severity": str,           # "P1" | "P2" | "P3"（大写）
        "title":    str,           # 问题短标题（可选，用于可读性）
        ...                        # 其他字段透传，不参与去重键计算
      }

    去重规则：
    - 去重键：file + 行号 ±3 + category（大小写不敏感）
    - 严重度取高：P1 > P2 > P3
    - 去重后保留严重度最高的那条 finding 的完整字段
    - 同一 finding 多个来源命中时，合并 title 取最先出现的那条（行号最小者优先作 canonical）

    返回去重后的 finding 列表，按 severity（P1 优先）、file、line 排序。

    可被单测覆盖的接口：
      findings_a = [{"file": "a.py", "line": 10, "category": "sc-conformance", "severity": "P2", "title": "x"}]
      findings_b = [{"file": "a.py", "line": 11, "category": "sc-conformance", "severity": "P1", "title": "y"}]
      result = merge_findings_union([findings_a, findings_b])
      # => [{"file": "a.py", "line": 11, "category": "sc-conformance", "severity": "P1", "title": "y"}]
      assert len(result) == 1 and result[0]["severity"] == "P1"
    """
    _SEVERITY_RANK = {"P1": 3, "P2": 2, "P3": 1}

    def _severity_rank(s: str) -> int:
        return _SEVERITY_RANK.get(str(s).upper(), 0)

    def _file_cat(finding: dict) -> tuple[str, str]:
        """Returns (file_normalized, category_normalized) — the non-line part of the key."""
        return (
            str(finding.get("file", "")).strip(),
            str(finding.get("category", "")).strip().lower(),
        )

    def _within_window(line_a: int, line_b: int, window: int = 3) -> bool:
        return abs(line_a - line_b) <= window

    # List of canonical findings; O(n²) but finding counts are small.
    merged_list: list[dict] = []

    for findings in findings_lists:
        for finding in (findings or []):
            fc = _file_cat(finding)
            line = int(finding.get("line", 0))
            # Search for an existing finding within ±3 of the same (file, category)
            match_idx = None
            for idx, existing in enumerate(merged_list):
                if _file_cat(existing) == fc and _within_window(
                    int(existing.get("line", 0)), line
                ):
                    match_idx = idx
                    break
            if match_idx is None:
                merged_list.append(dict(finding))
            else:
                existing = merged_list[match_idx]
                # Severity upgrade: keep the higher-severity entry as canonical
                if _severity_rank(finding.get("severity", "P3")) > _severity_rank(
                    existing.get("severity", "P3")
                ):
                    merged_list[match_idx] = dict(finding)
                # else: keep existing (same or lower severity — existing stays)

    # Sort: P1 first, then P2, then P3; within same severity sort by file + line
    result = sorted(
        merged_list,
        key=lambda f: (
            -_severity_rank(f.get("severity", "P3")),
            str(f.get("file", "")),
            int(f.get("line", 0)),
        ),
    )
    return result


# SC-5 (T5): 双 lens codex mapped 结果仲裁合并 —— G9 修复。
# merge_findings_union 只并 findings；本函数产完整 schema-valid MAPPED_RESULT
# （保留 raw 路径 + source lens 标记 + verdict 从严仲裁）。供 plan 直连路双 lens 调度合并用。
_DUAL_LENS_DEGRADED_STATUSES = {"degraded", "failed_to_run"}


def _tag_lens_source(finding: dict, lens: str) -> dict:
    """给 finding 打 source_lens 标记（合并后可追溯来自 codex_A/B 哪个视角）。"""
    nf = dict(finding)
    nf.setdefault("source_lens", lens)
    return nf


def merge_dual_codex_mapped(mapped_a: dict, mapped_b: dict) -> dict:
    """双 lens（codex_A / codex_B）mapped 结果仲裁合并 → schema-valid MAPPED_RESULT。

    verdict 仲裁（从严）：
      - 任一 degraded / failed_to_run / FAILED → review_run_status=degraded, decision=FAILED
      - 否则任一 REQUIRES_CHANGES → REQUIRES_CHANGES（completed）
      - 否则双 APPROVED → APPROVED（completed）
    findings：codex_A ∪ codex_B，经 merge_findings_union 去重，每条带 source_lens。
    raw_result / source：两 lens 原始路径与判定记入 merge_notes，不丢审计链。

    fixtures（见 tests/test_dual_lens_merge.py）：
      APPROVED + REQUIRES_CHANGES → REQUIRES_CHANGES
      degraded  + APPROVED        → FAILED (degraded)
      APPROVED  + APPROVED        → APPROVED
    """
    _a = mapped_a or {}
    _b = mapped_b or {}
    dec_a = str(_a.get("gd_review_decision", "FAILED")).upper()
    dec_b = str(_b.get("gd_review_decision", "FAILED")).upper()
    stat_a = str(_a.get("review_run_status", "failed_to_run"))
    stat_b = str(_b.get("review_run_status", "failed_to_run"))

    if (stat_a in _DUAL_LENS_DEGRADED_STATUSES
            or stat_b in _DUAL_LENS_DEGRADED_STATUSES
            or dec_a == "FAILED" or dec_b == "FAILED"):
        merged_decision, merged_status = "FAILED", "degraded"
        merge_reason = (f"dual-lens arbitration: ≥1 lens degraded/failed "
                        f"(A={dec_a}/{stat_a}, B={dec_b}/{stat_b})")
    elif dec_a == "REQUIRES_CHANGES" or dec_b == "REQUIRES_CHANGES":
        merged_decision, merged_status = "REQUIRES_CHANGES", "completed"
        merge_reason = (f"dual-lens arbitration: ≥1 REQUIRES_CHANGES "
                        f"(A={dec_a}, B={dec_b})")
    else:
        merged_decision, merged_status = "APPROVED", "completed"
        merge_reason = f"dual-lens arbitration: both APPROVED (A={dec_a}, B={dec_b})"

    fa = [_tag_lens_source(f, "codex_A") for f in (_a.get("findings") or [])]
    fb = [_tag_lens_source(f, "codex_B") for f in (_b.get("findings") or [])]
    merged_findings = merge_findings_union([fa, fb])

    # 取一个非 degraded base 作模板（保留 review_kind/target/template_kind 等结构字段）
    base = _a if stat_a not in _DUAL_LENS_DEGRADED_STATUSES else _b
    merged = dict(base)
    # reviewer 用 schema 枚举内的 "codex"（gd-review-result-v2.schema.json 不允许 codex_dual_lens）；
    # 双 lens 标识走 merge_notes.merge_strategy，raw 路径走 merge_notes.lens_a/b（不入 mapped 顶层，
    # 因 additionalProperties:false）。两 lens 的 raw_result_path 已在 merge_notes.lens_a/b 记录。
    merged.pop("raw_result_path", None)
    merged.update({
        "review_run_status": merged_status,
        "gd_review_decision": merged_decision,
        "findings": merged_findings,
        "scope_checked": list(_a.get("scope_checked") or []) + list(_b.get("scope_checked") or []),
        "reviewer": "codex",
        "merge_notes": {
            "merge_strategy": "dual_lens_verdict_arbitration",
            "merge_reason": merge_reason,
            "lens_a": {"decision": dec_a, "status": stat_a, "findings_count": len(fa),
                       "raw_result_path": _a.get("raw_result_path")},
            "lens_b": {"decision": dec_b, "status": stat_b, "findings_count": len(fb),
                       "raw_result_path": _b.get("raw_result_path")},
        },
    })
    return merged


# T6: kinds where the PRIMARY_TARGET must be a real artifact (diff / execution result)
# and NOT the capsule envelope (filename == capsule.md).
_EXECUTION_ARTIFACT_KINDS: frozenset[str] = frozenset({
    "code_diff", "execution_outcome", "combined",
})


def _kind_requires_l3(kind: str) -> bool:
    """Return True when the L3 content-evidence validator should run for this review kind.

    code_diff / execution_outcome / combined are execution-artifact reviews whose
    SCOPE_CHECKED does not carry plan SC-IDs; L3 SC-ID evidence check does not apply.
    """
    return kind not in _EXECUTION_ARTIFACT_KINDS


def _review_focus_for_kind(kind: str) -> str:
    """T6 SC-6.1: return a kind-specific REVIEW_FOCUS string (not hardcoded).

    Spec §2.3 focus 声明列:
      plan              -> 审计划完整性+anti-fill
      code_diff         -> 质量已由 /code-review 处理，只验 conformance
      execution_outcome -> 只验执行结果 vs 计划 SC
      combined          -> conformance（质量上游已处理）
    """
    _FOCUS_MAP: dict[str, str] = {
        "plan": "审计划完整性+anti-fill",
        "code_diff": "质量已由 /code-review 处理，只验 conformance",
        "execution_outcome": "只验执行结果 vs 计划 SC",
        "combined": "conformance（质量上游已处理）",
    }
    return _FOCUS_MAP.get(kind, f"review of {kind}")


def _primary_target_for_kind(kind: str, target: Path) -> str:
    """T6 SC-6.2: return the PRIMARY_TARGET string for the capsule.

    For plan: original plan file (target itself).
    For code_diff / combined / execution_outcome: the real artifact path (target).
    The caller is responsible for ensuring target IS the real artifact (not capsule.md)
    for non-plan kinds — enforced by _assert_not_capsule_target().
    """
    # In all cases the PRIMARY_TARGET is str(target.resolve()) — the content differs
    # by kind (plan file vs diff patch vs execution result). The guard
    # _assert_not_capsule_target() below ensures non-plan kinds don't receive capsule.md.
    return str(target.resolve())


def _assert_not_capsule_target(kind: str, target: Path) -> None:
    """T6 SC-6.3: guard — raise ValueError when a non-plan kind receives capsule.md.

    code_diff / execution_outcome / combined must point to the real artifact, not
    the L2 capsule envelope. Raises ValueError with CAPSULE_TARGET_FORBIDDEN so
    callers can surface a clear error instead of silently writing bad PRIMARY_TARGET.
    """
    if kind in _EXECUTION_ARTIFACT_KINDS and target.name.lower() == "capsule.md":
        raise ValueError(
            f"CAPSULE_TARGET_FORBIDDEN: --kind={kind!r} received capsule.md as target. "
            "Pass the real diff / execution artifact, not the /review2 capsule envelope. "
            "For code_diff use the .patch file; for execution_outcome use the result JSON; "
            "for combined use the diff or bundle descriptor."
        )
    if target.is_dir():
        raise ValueError(
            f"CODE_DIFF_TARGET_MUST_BE_FILE: --kind={kind!r} received a directory as "
            f"--target ({target}). Pass a regular file (e.g. a .patch file for code_diff, "
            "a result JSON for execution_outcome). Directories cannot be hashed or read "
            "as review targets."
        )


def _assert_out_is_file_path(out_path: Path) -> None:
    """Guard: raise ValueError when --out points to an existing directory."""
    if out_path.is_dir():
        raise ValueError(
            f"OUT_PATH_MUST_BE_FILE: --out received a directory ({out_path}). "
            "Pass a file path for the output JSON/capsule, not a directory."
        )


def _validate_out_path(out_path: Path) -> "int | None":
    """Validate --out path and ensure parent directory exists.

    Returns 2 (CLI error exit code) if out_path is a directory; None on success.
    Prints a diagnostic to stderr on failure.
    """
    try:
        _assert_out_is_file_path(out_path)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return None


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
    emphasis: str | None = None,
    lens_emphasis: str | None = None,
    _run_id_override: str | None = None,
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

    双镜头（dual-codex lens）—— L2 与 L3 各有一套，按参数路由，互不覆盖：
      - `emphasis`（L2 parity）：codex_A/codex_B 走"检查优先级排序"镜头
        (_EMPHASIS_CODEX_A/B)，描述文本直接写入 REVIEW_LENS_EMPHASIS 行；None 省略该行。
      - `lens_emphasis`（L3 review-fusion）：codex_A/codex_B 走"分析视角"镜头
        (模块级 _LENS_EMPHASIS_A/B)，REVIEW_LENS_EMPHASIS 写标签 + Reviewer Instructions
        末尾另起"视角侧重"行。
      - `_run_id_override`（L3 SC-2 镜头隔离）：固定 run_id，使非镜头参数相同的两次调用
        产生相同 QUEUE_JOB_ID / GD_BASELINE_KEY。
      同时传时 lens_emphasis（L3）优先。
    """
    active_enum = _get_active_kind_enum(compat_v1)
    if kind not in active_enum:
        # Build a clear error name so callers can grep / detect the mismatch.
        mode_label = "v1 compat" if compat_v1 else "v2 default"
        raise ValueError(
            f"INVALID_REVIEW_KIND_FOR_MODE: --kind={kind!r} not in "
            f"{mode_label} enum {sorted(active_enum)}"
        )
    # T6 SC-6.3: reject capsule.md as target for non-plan kinds before any I/O.
    _assert_not_capsule_target(kind, target)
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
    # SC-2: extract REVIEW_DOMAIN / REVIEW_FOCUS from plan §2 when kind==plan.
    _plan_domain, _plan_focus = (None, None)
    if kind == "plan":
        _plan_domain, _plan_focus = _extract_plan_review_meta(target)
    review_domain_final = _plan_domain or "ai_infra"
    review_focus_source = "plan_section_2" if _plan_focus else "kind_dynamic"
    review_focus_final = _plan_focus or _review_focus_for_kind(kind)
    # Fix A: 提取 target 的真实可审查 ID 集合（SC-N/SC-word + T-N），内联进 capsule，
    # 让 codex 不靠猜（旧版只写「extracted from target on review」→ codex 填 placeholder「SC-ID」）。
    try:
        _target_ids = sorted(extract_reviewable_ids(target.read_text(encoding="utf-8")))
    except Exception:
        _target_ids = []
    _target_ids_str = ", ".join(_target_ids) if _target_ids else "(none detected — 引用 target 实际任务/SC 编号)"
    # L1: Target externalized — capsule no longer inlines target_text (47KB savings on
    # Sentinel-sized plans). Reviewer must Read the path; bridge enforces via L3
    # content-evidence validator (gd-validate-review-content-evidence.py).
    standard_hash = _sha256_file(STANDARD_PATH) if STANDARD_PATH.exists() else "(missing)"
    template_text = template_path.read_text(encoding="utf-8") if template_path.exists() else "(missing)"
    goal_text = GOAL_PATH.read_text(encoding="utf-8")[:3000] if GOAL_PATH.exists() else "(missing)"

    target_abs = str(target.resolve())
    # run_id（L3 SC-2 镜头隔离）：_run_id_override 固定；否则 live(queue_job_id) 随机；否则 adhoc 稳定。
    if _run_id_override is not None:
        run_id = _run_id_override
    elif queue_job_id is not None:
        # Live transport: random run_id for unique tracking per dispatch.
        run_id = _new_run_id()
    else:
        # Adhoc / test path: stable run_id derived from inputs so two calls
        # with identical non-lens params produce the same QUEUE_JOB_ID and
        # GD_BASELINE_KEY (lens isolation contract for SC-2 verification).
        run_id = "adhoc-" + _sha256_str(f"{kind}{target_abs}{target_hash}")[:16]
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

    # --- 双镜头路由：L3(lens_emphasis) 优先，否则 L2(emphasis)，否则省略 ---
    # 镜头文案见模块级常量：L2 _EMPHASIS_CODEX_A/B，L3 _LENS_EMPHASIS_A/B。
    lens_detail_line = ""
    if lens_emphasis is not None:
        # L3（分析视角镜头）：REVIEW_LENS_EMPHASIS 写标签 + 末尾"视角侧重"行。
        effective_lens = lens_emphasis
        lens_emphasis_line = f"REVIEW_LENS_EMPHASIS: {effective_lens}\n"
        lens_detail_line = (
            f"- **视角侧重（REVIEW_LENS_EMPHASIS: {effective_lens}）**："
            + {"codex_A": _LENS_EMPHASIS_A, "codex_B": _LENS_EMPHASIS_B}.get(
                effective_lens, "中立视角，无额外侧重。"
            )
            + "\n"
        )
    elif emphasis is not None:
        # L2（检查优先级排序镜头）
        if emphasis == "codex_A":
            _lens_value = _EMPHASIS_CODEX_A
        elif emphasis == "codex_B":
            _lens_value = _EMPHASIS_CODEX_B
        else:
            _lens_value = emphasis  # caller-supplied neutral value
        lens_emphasis_line = f"REVIEW_LENS_EMPHASIS: {_lens_value}\n"
    else:
        lens_emphasis_line = ""  # 两者皆无 → 省略该字段

    # T6 SC-6.1: kind-specific REVIEW_FOCUS (not hardcoded "bridge candidate review of")
    review_focus = _review_focus_for_kind(kind)
    # T6 SC-6.2: PRIMARY_TARGET points to the real artifact, not capsule.md.
    primary_target_path = _primary_target_for_kind(kind, target)

    # T6: L2 capsule context is RELATED_CONTEXT (path/hash summary), not PRIMARY_TARGET.
    capsule_as_related: bool = kind in _EXECUTION_ARTIFACT_KINDS
    capsule_related_note = (
        f"- role=l2_capsule_envelope path=(this capsule, sent inline) hash=(see CAPSULE_HASH above)\n"
        if capsule_as_related else ""
    )

    # writer 实际 grep 的 3 字段必须出现在行首
    capsule = (
        f"REVIEW_DOMAIN: {review_domain_final}\n"
        + lens_emphasis_line
        + f"REVIEW_FOCUS: {review_focus_final}\n"
        f"REVIEW_FOCUS_SOURCE: {review_focus_source}\n"
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
        f"EXPECTED_SC_IDS: {_target_ids_str}\n\n"
        # SC-0 (T0): 显式塞入 GD 权威上下文 + 必读清单（codex 不靠猜）
        f"## CLAUDE_MD_CONTEXT（GD 权威规则摘要）\n\n"
        f"{_CLAUDE_MD_CONTEXT_SUMMARY}\n\n"
        f"## MANDATORY_READS（审查必读，逐项 Read 全文）\n\n"
        f"- REVIEW_STANDARD_PATH: {STANDARD_PATH}\n"
        f"- PRIMARY_TARGET: {primary_target_path}\n"
        f"- GOAL_SOURCE: {GOAL_PATH}\n"
        f"- GD 项目 CLAUDE.md（规则权威）\n\n"
        f"⚠️ 跳过上述 Read → 判 degraded（L3 content-evidence validator）。\n\n"
        # Review Trust §Step 2 required metadata block
        f"QUEUE_JOB_ID: {effective_queue_id}\n"
        f"TARGET_ROLE: {effective_role}\n"
        f"PRIMARY_TARGET: {primary_target_path}\n"
        f"EXPECTED_OUTPUT_SCHEMA: {expected_schema}\n"
        f"TEMPLATE_KIND: {template_kind_for_capsule}\n"
        f"RELATED_CONTEXT:\n{capsule_related_note}{related_summary}\n\n"
        f"## Goal Chain\n\n```\n{goal_text}\n```\n\n"
        f"## Review Standard\n\n"
        f"REVIEW_STANDARD_PATH: {STANDARD_PATH}\n"
        f"REVIEW_STANDARD_HASH: {standard_hash}\n"
        f"\n"
        f"**MANDATORY READ STEP (Standard)** — Before producing any output, you MUST use your Read\n"
        f"tool to open the file at REVIEW_STANDARD_PATH and consume its full content. The capsule\n"
        f"does NOT inline the standard text; the §Review Standard rules (§8, §9.1, §10) govern\n"
        f"your output format, 穷举义务 and fail-closed semantics. Reviewing without Read is\n"
        f"impossible and will produce non-conformant output (detected downstream as degraded).\n\n"
        f"## Review Template ({template_path.name})\n\n"
        f"> ⚠️ **FORMAT CONSTRAINT (overrides template §2 example)**:\n"
        f"> Scope Checked 的每一行**必须**是 `| <target 中真实 SC-ID> | pass/fail/n_a | <证据> |`（SC-ID 逐行）。\n"
        f"> 绝对禁止 facet/维度行（如 `| 审计划完整性 |`）——它们不被 validator 计入，判 SHALLOW_REVIEW → degraded。\n"
        f"> 见下方 Reviewer Instructions 中的 CRITICAL OVERRIDE 说明。\n\n"
        f"```\n{template_text}\n```\n\n"
        f"## Target Artifact\n\n"
        f"PRIMARY_TARGET_PATH: {primary_target_path}\n"
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
        f"- 每个 Finding 含 severity 标记 + `SC: <target 中真实 SC-ID>` 行 + 5 中文字段 (问题/证据/影响/最小修复/验收)\n"
        f"- REQUIRES_CHANGES 必须含 ≥1 ### Finding\n"
        f"- **每条 finding 必须 evidence: 含真实 path:line 引用**（L3 validator 会校验行号指向 target 真实内容）\n"
        f"- **每条 finding 的 sc_refs / SC 行必须是 target 中真实存在的 ID**（L3 validator 会校验；"
        f"引用 target 不存在的 ID 判 FAKE_EVIDENCE_DETECTED）。"
        f"**本 target 可引用的 ID 仅限**: {_target_ids_str}。"
        f"若 finding 是跨 ID 的结构性问题（如缺字段、格式不符），挑一个 **上述列表内**、"
        f"且该问题最直接影响的 ID 来挂；**绝不臆造或硬编码编号、绝不写 placeholder「SC-ID」**"
        f"（target 的 ID 体系各异：SC-1 / SC-W1-1 / T0 等，必须从上方列表选）。\n"
        f"- ⚠️ **CRITICAL OVERRIDE（覆盖模板格式）**: '## Scope Checked' 行格式**强制为 SC-ID 逐行**，"
        f"无论 VERDICT 是 APPROVED 还是 REQUIRES_CHANGES 都必须遵守。"
        f"**绝对禁止**用 facet/维度行（如 `| 审计划完整性 | pass |`、`| anti-fill | pass |`）替代 SC-ID 行——"
        f"这是 SHALLOW_REVIEW，L3 validator 直接判 degraded，APPROVED 变 FAILED。"
        f"SC-ID 格式必须严格复用 target 中真实 ID（大写 SC + 连字符，可含字母/数字段，例 `SC-1`、`SC-L1-1`、`SC-Rpt-1`、`SC-Log-Fmt`）；"
        f"**禁止**写成 `SC1` / `sc-1` / `SC 1`。**强制模板**（必须照此格式，不得用其他格式）：\n"
        f"  ## Scope Checked\n"
        f"  | SC-ID | 结论 | 证据(≤30字) |\n"
        f"  |-------|------|-------------|\n"
        f"  | SC-L1-1 | pass | <证据> |\n"
        f"  | SC-Rpt-1 | pass | <证据> |\n"
        f"  | SC-Log-Fmt | pass | <证据> |\n"
        f"  ...（按本 target 实际 SC-ID 逐条覆盖）\n"
        f"  注意：只有 SC-ID 行才被 validator 识别，facet 行一律不计入覆盖数。\n"
        f"- **REVIEW_FOCUS 与 Scope Checked 的关系（粘合规则）**："
        f"REVIEW_FOCUS 描述的是审查侧重维度，你可按这些维度组织审查内容；"
        f"但 Scope Checked 表的**行格式必须逐 SC-ID 落行**（每行 `| <真实 SC-ID> | ...`），"
        f"可选加第三列标注该 SC 所属 REVIEW_FOCUS 维度（如 `fail-closed`）作为组织辅助，"
        f"但不得用 facet 维度行替代 SC-ID 行。"
        f"**只输出 facet 维度行而不输出 SC-ID 行 = SHALLOW_REVIEW，validator 判 degraded。**\n"
        f"- **审查定位（conformance scoping）**：你的主目标是核对「执行结果 / 已实现功能是否符合已批准计划的 SC（conformance）」；代码本身顺带扫一眼，可指出明显问题，但 MUST NOT 把地毯式找 bug 当作职责——地毯式找 bug 由上游 `/code-review` 承担。\n"
        f"- **穷举强制**：见下方 §9.1——一次列全所有 finding，分轮挤牙膏 = degraded。\n"
        f"\n### §9.1 穷举义务（强制）\n\n"
        f"你必须扫完 PRIMARY_TARGET 内全部 SC、模块、fallback 路径，"
        f"**一次列全**所有可发现 finding，不得分批分轮透露；"
        f"分轮挤牙膏 = 协议违规，判定 degraded（见 §Review Standard §10）。\n"
        + lens_detail_line
    )
    capsule_hash = _sha256_str(capsule)
    return capsule, target_hash, capsule_hash, gd_baseline_key, run_id


def _extract_plan_sc_verify_summary(plan_file_path: str) -> str:
    """SC-33: Extract SC verify commands from plan markdown for deep capsule."""
    try:
        text = Path(plan_file_path).read_text(encoding="utf-8")
        sc_hdr = re.compile(r"^\s*-\s*\[[ xX]\]\s*(" + SC_ID_RE.pattern + r")\b", re.MULTILINE)
        verify_re = re.compile(r"-\s+verify\s*\(method:\s*([^)]+)\)\s*:\s*`([^`]+)`", re.MULTILINE | re.DOTALL)
        entries = []
        sc_positions = list(sc_hdr.finditer(text))
        for idx, sc_match in enumerate(sc_positions):
            sc_ref = sc_match.group(1)
            block_start = sc_match.end()
            block_end = sc_positions[idx + 1].start() if idx + 1 < len(sc_positions) else len(text)
            block = text[block_start:block_end]
            for v_match in verify_re.finditer(block):
                entries.append(f"- {sc_ref}: `{v_match.group(2).strip()}`")
        return "\n".join(entries[:20]) if entries else "(no verify commands found)"
    except Exception as e:
        return f"(error extracting verify commands: {e})"


def _extract_run_evidence_into_mapped(mapped: dict) -> bool:
    """SC-17/SC-28: extract weak run_evidence hints from finding prose.

    Codex may report pytest output inside a finding's `evidence` text rather
    than as a structured run_evidence array. This helper keeps those hints for
    diagnosis, but marks them evidence_source=extracted_from_finding_prose.
    Deep execution/combined gates reject that source; prose is not proof that a
    command actually ran.

    Called from BOTH run-bridge and parse-transport (canonical raw→mapped path) so the
    router subcommand — which consumes parse-transport's mapped output — also benefits.

    Returns True if run_evidence was added, False otherwise. No-op if run_evidence
    already present.
    """
    if mapped.get("run_evidence"):
        return False

    def _pytest_count(text: str, label: str) -> int | None:
        patterns = (
            rf"\b(\d+)\s+{label}\s+in\s+[\d.]+s\b",
            rf"`[^`]*?(\d+)\s+{label}(?:\s+in\b|`)",
            rf"[\"'](\d+)\s+{label}[\"']",
            rf"\b(?:output|outputs|reported|reports|got|actual|输出|结果|复跑)[^.;。]*?(\d+)\s+{label}\b",
        )
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    extracted = []
    for finding in mapped.get("findings", []) or []:
        ev_text = finding.get("evidence", "") or ""
        cmd_text = "\n".join(
            str(finding.get(k, "") or "")
            for k in ("evidence", "verify", "required_fix")
        )
        cmd_m = re.search(r"`([^`]*pytest[^`]*)`", cmd_text)
        if not cmd_m:
            continue
        # Prefer pytest summary format (N X in Y.YYs); fall back to backtick/quoted
        skipped_count = _pytest_count(ev_text, "skipped")
        passed_count = _pytest_count(ev_text, "passed")
        failed_count = _pytest_count(ev_text, "failed")
        ver_m = re.search(r"Python\s+([\d.]+)", ev_text)
        failed_count = failed_count or 0
        extracted.append({
            "cmd": cmd_m.group(1),
            "cwd": "",
            "exit": 1 if failed_count > 0 else 0,
            "passed": passed_count or 0,
            "failed": failed_count,
            "skipped": skipped_count or 0,
            "skip_reason": "(extracted from Codex finding evidence)",
            "interpreter_version": f"Python {ver_m.group(1)}" if ver_m else "Python 3.x (from Codex evidence)",
            "evidence_source": "extracted_from_finding_prose",
        })
    if extracted:
        mapped["run_evidence"] = extracted
        return True
    return False


_DEEP_RUN_EVIDENCE_KINDS = {"execution_outcome", "combined"}
_DEEP_RUN_EVIDENCE_FIELDS = (
    "cmd",
    "cwd",
    "exit",
    "passed",
    "failed",
    "skipped",
    "skip_reason",
    "interpreter_version",
    "evidence_source",
)
_WEAK_RUN_EVIDENCE_SOURCES = {"", "extracted_from_finding_prose", "codex_finding_prose"}

_CODE_LINE_REF_RE = re.compile(
    r"([A-Za-z0-9_./\-]+\.(?:py|sh|json|yaml|yml|toml|ts|tsx|js|patch|diff|md)):(\d+)(?:-(\d+))?"
)


def _deep_run_evidence_errors(mapped: dict, kind: str) -> list[str]:
    """Validate deep execution/combined run_evidence without changing generic schema."""
    if kind not in _DEEP_RUN_EVIDENCE_KINDS:
        return []
    run_evidence = mapped.get("run_evidence")
    if not isinstance(run_evidence, list) or not run_evidence:
        return ["DEEP_RUN_EVIDENCE_MISSING: run_evidence must be a non-empty array"]

    errs: list[str] = []
    approved = mapped.get("gd_review_decision") == "APPROVED"
    for i, item in enumerate(run_evidence):
        if not isinstance(item, dict):
            errs.append(f"run_evidence[{i}] must be object")
            continue
        missing = [field for field in _DEEP_RUN_EVIDENCE_FIELDS if field not in item]
        if missing:
            errs.append(f"run_evidence[{i}] missing {', '.join(missing)}")
            continue
        try:
            exit_code = int(item.get("exit"))
            failed = int(item.get("failed"))
            skipped = int(item.get("skipped"))
        except (TypeError, ValueError):
            errs.append(f"run_evidence[{i}] exit/failed/skipped must be integers")
            continue
        source = str(item.get("evidence_source") or "").strip()
        if source in _WEAK_RUN_EVIDENCE_SOURCES:
            errs.append(
                f"run_evidence[{i}] evidence_source={source or '<missing>'} is weak; "
                "deep review requires real command transcript evidence"
            )
        if not str(item.get("cwd") or "").strip():
            errs.append(f"run_evidence[{i}] cwd must be a non-empty execution directory")
        if not any(str(item.get(k) or "").strip() for k in ("stdout_excerpt", "stdout_path", "output", "stderr_excerpt")):
            errs.append(f"run_evidence[{i}] requires stdout_excerpt/stdout_path/output/stderr_excerpt")
        if skipped > 0 and not str(item.get("skip_reason") or "").strip():
            errs.append(f"run_evidence[{i}] skipped>0 requires skip_reason")
        if approved and (exit_code != 0 or failed > 0 or skipped > 0):
            errs.append(
                f"APPROVED cannot include failing/skipped run_evidence[{i}] "
                f"(exit={exit_code}, failed={failed}, skipped={skipped})"
            )
    return errs


def _deep_code_diff_evidence_errors(mapped: dict, kind: str, target_path: "Path") -> list[str]:
    """Validate deep code_diff finding evidence has target-resolving file:line refs."""
    if kind != "code_diff" or mapped.get("gd_review_decision") != "REQUIRES_CHANGES":
        return []

    findings = mapped.get("findings")
    if not isinstance(findings, list) or not findings:
        return []

    target_name = target_path.name
    target_str = str(target_path)
    try:
        target_line_count = len(target_path.read_text(encoding="utf-8").splitlines())
    except Exception:
        return [f"DEEP_CODE_LINE_EVIDENCE_TARGET_UNREADABLE: {target_path}"]

    errs: list[str] = []
    for i, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errs.append(f"DEEP_CODE_LINE_EVIDENCE_MISSING: findings[{i}] is not object")
            continue
        evidence_text = "\n".join(
            str(finding.get(k, "") or "")
            for k in ("title", "evidence", "impact", "required_fix", "verify")
        )
        refs = _CODE_LINE_REF_RE.findall(evidence_text)
        target_refs = [
            ref for ref in refs
            if ref[0] == target_name or target_str.endswith(ref[0])
        ]
        if not target_refs:
            errs.append(
                f"DEEP_CODE_LINE_EVIDENCE_MISSING: findings[{i}] must cite "
                f"{target_name}:<line>"
            )
            continue
        for path_ref, start_s, end_s in target_refs:
            start = int(start_s)
            end = int(end_s) if end_s else start
            if start < 1 or end > target_line_count or start > end:
                errs.append(
                    f"DEEP_CODE_LINE_EVIDENCE_INVALID: {path_ref}:{start_s}"
                    f"{'-' + end_s if end_s else ''} out of range "
                    f"(target has {target_line_count} lines)"
                )
    return errs


def _apply_deep_run_evidence_gate(mapped: dict, kind: str, out_path: "Path") -> bool:
    """Fail-close mapped output when deep execution evidence is absent or invalid."""
    errs = _deep_run_evidence_errors(mapped, kind)
    if not errs:
        return False
    _apply_l3_failure(mapped, "; ".join(errs[:3]), out_path)
    return True


def _apply_deep_code_diff_evidence_gate(
    mapped: dict,
    kind: str,
    target_path: "Path",
    out_path: "Path",
) -> bool:
    """Fail-close deep code_diff findings without machine-checkable target line refs."""
    errs = _deep_code_diff_evidence_errors(mapped, kind, target_path)
    if not errs:
        return False
    _apply_l3_failure(mapped, "; ".join(errs[:3]), out_path)
    return True


def _build_deep_plan_capsule(kind: str, target: Path, plan_file: str | None = None) -> str:
    """SC-3: Deep plan review capsule addendum — architecture/risk/interface dimensions."""
    plan_section = ""
    if plan_file and Path(plan_file).exists():
        plan_hash = _sha256_file(Path(plan_file))
        sc_summary = _extract_plan_sc_verify_summary(plan_file)
        plan_section = (
            f"\nPLAN_FILE_PATH: {plan_file}\n"
            f"PLAN_FILE_HASH: {plan_hash}\n"
            f"\n## SC Verify Commands (from plan)\n\n{sc_summary}\n"
        )
    return (
        f"\n## 深度审查维度（SC-3）\n\n"
        f"本次深度审查须从以下三个维度进行分析：\n\n"
        f"### 1. 架构维度\n"
        f"- 验证设计一致性与模块分离边界\n"
        f"- 评估模块间依赖关系与耦合度\n"
        f"- 识别可扩展性与可维护性风险\n\n"
        f"### 2. 风险维度\n"
        f"- 检测安全边界违规与潜在漏洞\n"
        f"- 验证错误处理与回退路径\n"
        f"- 评估数据一致性与状态管理风险\n\n"
        f"### 3. 接口维度\n"
        f"- 验证 API 合约与公开接口稳定性\n"
        f"- 评估调用方兼容性与向后兼容性\n"
        f"- 检查边界条件与输入验证\n"
        + plan_section
    )


def _build_deep_outcome_capsule(kind: str, target: Path, plan_file: str | None = None) -> str:
    """SC-4: Deep outcome capsule addendum — 真跑 evidence + 五元組."""
    plan_section = ""
    if plan_file and Path(plan_file).exists():
        plan_hash = _sha256_file(Path(plan_file))
        sc_summary = _extract_plan_sc_verify_summary(plan_file)
        plan_section = (
            f"\nPLAN_FILE_PATH: {plan_file}\n"
            f"PLAN_FILE_HASH: {plan_hash}\n"
            f"\n## SC Verify Commands (from plan)\n\n{sc_summary}\n"
        )
    return (
        f"\n## 深度结果审查要求（SC-4）\n\n"
        f"**必须：提供真实运行证据（run_evidence）**\n\n"
        f"须真实执行各 verify 命令，并将运行结果以 run_evidence 数组形式报告：\n\n"
        f"cmd / cwd / exit / passed / failed / skipped / skip_reason / interpreter_version / evidence_source / stdout_excerpt(或 stdout_path/output)\n\n"
        f"evidence_source 必须指向真实执行记录（如 writer_transcript / command_rerun / verifier_artifact）；"
        f"不得使用 extracted_from_finding_prose。\n\n"
        f"**跳过必查因（SC-4 必须）**：skipped > 0 时，须在 skip_reason 中说明具体跳过原因。\n\n"
        f"**run_evidence 须放入 JSON block 的 run_evidence 数组字段中。**\n"
        + plan_section
    )


def _build_deep_code_capsule(kind: str, target: Path) -> str:
    """SC-4: Deep code capsule addendum — deep-read semantic bug detection."""
    return (
        f"\n## 深度代码审查要求\n\n"
        f"**必须：深读推理 + 语义 bug 检测**\n\n"
        f"1. **深读**：逐行阅读全文件，检测注释与实现的偏差\n"
        f"2. **语义 bug**：检测逻辑上通过但语义上错误的代码\n"
        f"3. **副作用分析**：检测对外部状态的意外写入或读取\n"
        f"4. **并发风险**：检测竞态条件、死锁、非原子操作\n\n"
        f"findings 除 sc_refs 外须包含具体的 文件:行 引用。\n"
    )


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
    # SC-1 (T1): build-capsule 子命令也读 lens env（preflight 路径与 live 一致）。
    _emphasis_env, _lens_env = _lens_params_from_env()
    try:
        capsule, target_hash, capsule_hash, gd_baseline_key, run_id = build_capsule_text(
            args.kind, Path(args.target), Path(args.cwd),
            queue_job_id=getattr(args, "queue_job_id", None),
            target_role=getattr(args, "target_role", None),
            related_context=related,
            compat_v1=compat_v1,
            emphasis=_emphasis_env,
            lens_emphasis=_lens_env,
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
    if (rc := _validate_out_path(out)) is not None:
        return rc
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
# code_diff is intentionally excluded: code reviews don't produce execution verdicts
# that could be exploited as false-APPROVED pass gates, so the dispatch constraint
# is not needed for that kind. run_review_subcommand("code") still sets the env
# for traceability, but the bridge does not enforce it for code_diff.
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


# SC-5 (T5): 双 lens dispatch —— 失败时携带已写盘的 failed-mapped + 退出码。
class _LensDispatchFailed(Exception):
    """单 lens dispatch 失败（writer DEGRADED/MALFORMED/FAILED/timeout/result 缺失）。
    携带 (mapped, transport_path, exit_code)，供 dual-lens 路径统一终止。"""

    def __init__(self, mapped: dict, transport_path: str | None, exit_code: int):
        self.mapped = mapped
        self.transport_path = transport_path
        self.exit_code = exit_code


def _run_lens_dispatch(
    capsule_text: str,
    *,
    run_id: str,
    gd_baseline_key: str,
    kind: str,
    target_str: str,
    run_cwd: "Path",
    compat_v1: bool,
    deep: bool,
) -> tuple[dict, "str | None"]:
    """跑一次 writer（单 lens）→ parse raw → 返回 (mapped, result_path)。

    与 _cmd_run_bridge_inner 单 lens 路径等价（writer 调用 + marker 判定 + result_path 提取
    + parse_raw_to_mapped），但失败时不直接 exit —— 抛 _LensDispatchFailed 让 dual-lens
    合并层决定终止。用于 plan 直连路双 lens 调度（SC-5 part 2）。
    """
    tmpdir = Path(os.environ.get("TMPDIR", "/tmp"))
    capsule_tmp = tmpdir / f"gd-codex-bridge-{run_id}.capsule.txt"
    capsule_tmp.write_text(capsule_text, encoding="utf-8")

    _effective_timeout, _writer_extra_args = _writer_timeout_args(deep, kind)

    try:
        result = subprocess.run(
            [
                "bash", str(WRITER_PATH),
                "--capsule-file", str(capsule_tmp),
                "--baseline-key", gd_baseline_key,
                "--review-kind", kind,
                "--cwd", str(run_cwd),
                "--no-stop-marker",
            ] + _writer_extra_args,
            capture_output=True, text=True, timeout=_effective_timeout,
        )
    except subprocess.TimeoutExpired:
        raise _LensDispatchFailed(
            _failed_mapped("codex", kind, target_str,
                           f"writer subprocess timeout >{_effective_timeout}s"),
            None, 1)

    writer_stdout = result.stdout
    writer_stderr = result.stderr
    writer_exit = result.returncode
    _wstatus = parse_writer_status_line(writer_stdout)
    _wstatus_tag = f"[{_wstatus[0]}/{_wstatus[1]}] " if _wstatus else ""
    result_path = parse_writer_result_path(writer_stdout)

    if "[REVIEW] ⚠️ DEGRADED" in writer_stdout:
        raise _LensDispatchFailed(
            _failed_mapped("codex", kind, target_str,
                           f"{_wstatus_tag}writer DEGRADED: {writer_stdout.strip()[:200]}", "degraded"),
            result_path or None, 1)
    if "[REVIEW] ✗ MALFORMED" in writer_stdout:
        raise _LensDispatchFailed(
            _failed_mapped("codex", kind, target_str,
                           f"{_wstatus_tag}writer MALFORMED: {writer_stdout.strip()[:200]}", "degraded"),
            result_path or None, 1)
    if "[REVIEW] ✗ FAILED" in writer_stdout or writer_exit != 0:
        raise _LensDispatchFailed(
            _failed_mapped("codex", kind, target_str,
                           f"{_wstatus_tag}writer FAILED exit={writer_exit}: "
                           f"{(writer_stdout + writer_stderr).strip()[:200]}"),
            result_path or None, 1)
    if not result_path or not Path(result_path).exists():
        head = "\n".join(writer_stdout.splitlines()[:20])
        reason = (f"WRITER_RESULT_PATH_MISSING: regex 未匹配 'Full result:'。head[20]:\n{head}"
                  if not result_path
                  else f"WRITER_RESULT_PATH_MISSING: path={result_path!r} 不存在。head[20]:\n{head}")
        raise _LensDispatchFailed(
            _failed_mapped("codex", kind, target_str, reason), None, 1)

    raw_text = Path(result_path).read_text(encoding="utf-8")
    mapped, _errs = parse_raw_to_mapped(kind, target_str, raw_text, compat_v1=compat_v1)
    # Layer 4: stamp capsule provenance onto the mapped result so the downstream
    # chain (merge-loop loop_report → router route_report → validator) can refuse
    # to treat a pre_fed APPROVED as a trusted deep-review. Additive.
    _rq = parse_writer_review_quality(writer_stdout)
    if _rq:
        mapped["review_quality"] = _rq
    return mapped, result_path


def _is_plan_direct_dual_lens(args: argparse.Namespace, deep: bool) -> bool:
    """SC-5 part 2 gate：仅 plan 直连路 + --deep + 非 controller 调用 → bridge 做双 lens。

    - kind=="plan"：plan 直连路（code/execution/combined 走 controller，已有双调度）。
    - --deep：深审才双镜头（浅审 single_pass 保留旧行为）。
    - GD_REVIEW_ROUTER_INVOCATION_ID 未设：非 controller 直调（controller 已 dispatch
      codex_A/B，bridge 再双调度会嵌套 2→4 job，触发 G8）。code_diff 经 controller 故天然排除。
    """
    if args.kind != "plan" or not deep:
        return False
    return not os.environ.get(_GD_ROUTER_INVOCATION_ENV)


def _mark_l3_failure(mapped: dict, reason: str) -> None:
    """就地标记 L3 失败（degraded/FAILED + merge_notes.degraded_reason + sotd），不写盘。
    供 dual-lens 逐 lens 标记（最终只写一次 merged 结果）。"""
    mapped["review_run_status"] = "degraded"
    mapped["gd_review_decision"] = "FAILED"
    mapped.setdefault("merge_notes", {})["degraded_reason"] = reason
    sotd = mapped.get("source_of_truth_decision")
    if isinstance(sotd, dict):
        sotd["value"] = "FAILED"


def _run_l3_content_evidence(
    kind: str, target_path: "Path", raw_result_path: "Path",
) -> str | None:
    """跑 L3 content-evidence validator，返回失败 reason（None=通过/跳过）。不 mutate mapped。

    code_diff / execution_outcome / combined 跳过（其 SCOPE_CHECKED 非计划 SC-ID）。
    与 _cmd_run_bridge_inner 单 lens 路径的 L3 逻辑等价；dual-lens 逐 lens 调用以保持等强度。
    """
    if not _kind_requires_l3(kind):
        return None
    l3_script = GD_PROJECT_ROOT / "scripts" / "gd-validate-review-content-evidence.py"
    if not l3_script.exists():
        print("L3_CONTENT_EVIDENCE: script missing — fail-closed", file=sys.stderr)
        return "L3 content-evidence script missing — fail-closed"
    if not target_path.exists():
        print(f"L3_CONTENT_EVIDENCE: target not found ({target_path}) — fail-closed", file=sys.stderr)
        return f"L3 target not found ({target_path}) — fail-closed"
    try:
        r = subprocess.run(
            [sys.executable, str(l3_script),
             "--target", str(target_path), "--review", str(raw_result_path)],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"L3_CONTENT_EVIDENCE: FAILED — {r.stdout.strip()[:200]}", file=sys.stderr)
            return "L3 content-evidence validator rejected review: " + r.stdout.strip()[:200]
        return None
    except subprocess.TimeoutExpired:
        print("L3_CONTENT_EVIDENCE: timeout (30s) — fail-closed", file=sys.stderr)
        return "L3 content-evidence validator timed out (30s) — fail-closed"
    except Exception as e:  # noqa: BLE001
        print(f"L3_CONTENT_EVIDENCE: error — {e}", file=sys.stderr)
        return f"L3 content-evidence validator error — {e}"


def _run_plan_direct_dual_lens(
    args: argparse.Namespace,
    target: "Path",
    cwd: "Path",
    out_path: "Path",
    target_str: str,
    run_id: str,
    compat_v1: bool,
    related: list[dict] | None,
) -> int:
    """SC-5 part 2: plan 直连路双 lens —— codex_A / codex_B 同 target 各跑一次 → merge。

    每镜头：build_capsule_text(lens_emphasis=tag)（L3 分化）+ deep addendum + allowed cmds，
    _run_lens_dispatch 跑 writer→parse→mapped，_run_l3_content_evidence 逐 lens 校验（保持等强度），
    L3 失败则 _mark_l3_failure（degraded）→ merge_dual_codex_mapped 从严仲裁（任一 degraded→FAILED）。
    单 lens dispatch 失败（writer DEGRADED/MALFORMED/FAILED/timeout）→ fail-closed 立即终止。
    """
    mapped_per_lens: list[dict] = []
    last_transport: str | None = None
    for lens_tag, suffix in (("codex_A", "A"), ("codex_B", "B")):
        lens_run_id = f"{run_id}-{suffix}"
        lens_capsule, _th, _ch, lens_baseline_key, _rid = build_capsule_text(
            "plan", target, cwd,
            queue_job_id=getattr(args, "queue_job_id", None),
            target_role=getattr(args, "target_role", None),
            related_context=related,
            compat_v1=compat_v1,
            lens_emphasis=lens_tag,  # L3 分化（A=结构符合 / B=对抗边角）
        )
        lens_capsule += _build_deep_plan_capsule("plan", target, getattr(args, "plan_file", None))
        lens_capsule += _DEEP_ALLOWED_COMMANDS_SECTION
        try:
            mapped, result_path = _run_lens_dispatch(
                lens_capsule,
                run_id=lens_run_id, gd_baseline_key=lens_baseline_key,
                kind="plan", target_str=target_str, run_cwd=cwd,
                compat_v1=compat_v1, deep=True,
            )
        except _LensDispatchFailed as e:
            out_path.write_text(json.dumps(e.mapped, ensure_ascii=False, indent=2), encoding="utf-8")
            print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
            print("GD_REVIEW_DECISION: FAILED")
            print(f"MAPPED_RESULT: {out_path}")
            print(f"TRANSPORT_RESULT: {e.transport_path or 'N/A'}")
            print(f"DUAL_LENS_ABORTED: lens={lens_tag} dispatch failed", file=sys.stderr)
            return e.exit_code
        # 逐 lens L3 content-evidence（保持与单 lens 等强度）
        l3_reason = _run_l3_content_evidence("plan", target, Path(result_path))
        if l3_reason is not None:
            _mark_l3_failure(mapped, l3_reason)
        mapped["raw_result_path"] = result_path
        mapped_per_lens.append(mapped)
        last_transport = result_path

    merged = merge_dual_codex_mapped(mapped_per_lens[0], mapped_per_lens[1])
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    decision = merged["gd_review_decision"]
    status = merged["review_run_status"]
    print(f"GD_CODEX_BRIDGE_STATUS: {status}")
    print(f"GD_REVIEW_DECISION: {decision}")
    print(f"MAPPED_RESULT: {out_path}")
    print(f"TRANSPORT_RESULT: {last_transport}")
    print(
        f"DUAL_LENS_MERGED: A={mapped_per_lens[0].get('gd_review_decision')} "
        f"B={mapped_per_lens[1].get('gd_review_decision')} → {decision}",
        file=sys.stderr,
    )
    return 0 if decision == "APPROVED" else 1


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

    # T6 SC-6.3: execution artifact kinds guard (symmetric with plan guard above).
    # code_diff / execution_outcome / combined must receive a real artifact, not capsule.md.
    if args.kind in _EXECUTION_ARTIFACT_KINDS:
        sys.path.insert(0, str(GD_PROJECT_ROOT / "scripts"))
        from lib.path_classification import is_review2_capsule_path  # noqa: E402
        if is_review2_capsule_path(args.target):
            print(
                f"CAPSULE_TARGET_FORBIDDEN: --kind={args.kind!r} received capsule.md as target "
                f"({args.target!r}). Pass the real diff / execution artifact. "
                "code_diff expects a .patch file; execution_outcome expects a result JSON; "
                "combined expects the diff or bundle descriptor.",
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
    if (rc := _validate_out_path(out_path)) is not None:
        return rc
    compat_v1 = _resolve_compat_v1(args.kind, getattr(args, "compat_v1", None))

    related = _load_related_context(getattr(args, "related_context", None))
    # SC-1 (T1): 从 env 读统一 lens 协议 → A/B capsule 真分化（修 G1 断线 + G2 值不对齐）。
    _emphasis_env, _lens_env = _lens_params_from_env()
    try:
        capsule, target_hash, capsule_hash, gd_baseline_key, run_id = build_capsule_text(
            args.kind, target, cwd,
            queue_job_id=getattr(args, "queue_job_id", None),
            target_role=getattr(args, "target_role", None),
            related_context=related,
            compat_v1=compat_v1,
            emphasis=_emphasis_env,
            lens_emphasis=_lens_env,
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

    # SC-3/SC-4: append deep capsule addendum when --deep is set
    _deep = getattr(args, "deep", False)
    if _deep:
        if args.kind == "plan":
            capsule += _build_deep_plan_capsule(args.kind, target, getattr(args, "plan_file", None))
        elif args.kind in {"execution_outcome", "combined"}:
            capsule += _build_deep_outcome_capsule(args.kind, target, getattr(args, "plan_file", None))
        else:
            capsule += _build_deep_code_capsule(args.kind, target)
        # SC-0 (T0): deep 允许的查证命令清单（不只开 workspace-write）
        capsule += _DEEP_ALLOWED_COMMANDS_SECTION

    # SC-23: deep isolation guard — snapshot git status before running
    _pre_git_status: str | None = None
    if _deep:
        try:
            _gs = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=str(cwd), timeout=10,
            )
            _pre_git_status = _gs.stdout
        except Exception as _e:
            print(
                f"DEEP_ISOLATION_PREREQ_FAILED: cannot snapshot git status before deep run: {_e}",
                file=sys.stderr,
            )
            mapped = _failed_mapped("codex", args.kind, target_str,
                                    "deep isolation prereq failed — git status unavailable")
            out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
            print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
            print("GD_REVIEW_DECISION: FAILED")
            print(f"MAPPED_RESULT: {out_path}")
            return 1

    # SC-2 (T2): code 路 deep 副本隔离 — codex workspace-write 落副本，原工作区 git status 不变。
    # hard_stop: 副本不得写入原工作区 / worktree 不得丢 dirty。worktree+stash 复刻 dirty，
    # codex 在副本跑命令；原工作区前后 git status --porcelain 字节一致（由 SC-23 post-check 兜底）。
    _run_cwd: Path = cwd
    _workcopy_manifest: dict | None = None
    if _deep and args.kind == "code_diff":
        try:
            import importlib.util
            _spec = importlib.util.spec_from_file_location(
                "gd_prepare_workcopy", GD_PROJECT_ROOT / "scripts" / "gd-prepare-workcopy.py")
            _wc_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
            _spec.loader.exec_module(_wc_mod)  # type: ignore[union-attr]
            _wc_scratch = out_path.parent / f"_workcopy_{run_id}"
            _workcopy_manifest = _wc_mod.prepare_workcopy(cwd, run_id, _wc_scratch)
            _run_cwd = Path(_workcopy_manifest["workcopy_cwd"])
            print(f"WORKCOPY_PREPARED: cwd={_run_cwd}", file=sys.stderr)
        except Exception as _e:
            print(f"WORKCOPY_PREPARE_FAILED: {_e}", file=sys.stderr)
            mapped = _failed_mapped("codex", args.kind, target_str,
                                    f"deep workcopy isolation failed: {_e}")
            out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
            print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
            print("GD_REVIEW_DECISION: FAILED")
            print(f"MAPPED_RESULT: {out_path}")
            return 1

    # SC-5 (T5) part 2: plan 直连路 + --deep + 非 controller → bridge 双 lens 调度。
    # 同 target 跑 codex_A / codex_B 两次（各自 GD_REVIEW_LENS_TAG + lens 文案内联），再合并。
    # code_diff / execution / combined 走 controller（已 dispatch codex_A/B），bridge 不双调度
    # （G8 嵌套 2→4 job 由 _is_plan_direct_dual_lens 的 router-env 判别硬排除）。
    if _is_plan_direct_dual_lens(args, _deep):
        return _run_plan_direct_dual_lens(
            args, target, cwd, out_path, target_str, run_id, compat_v1, related,
        )

    tmpdir = Path(os.environ.get("TMPDIR", "/tmp"))
    capsule_tmp = tmpdir / f"gd-codex-bridge-{run_id}.capsule.txt"
    capsule_tmp.write_text(capsule, encoding="utf-8")

    # SC-1b: deep AND non-deep plan reviews use a consistent timeout ladder:
    # 2 x exec_timeout(720) <= send_wait(1500) <= writer(1700) <= controller/router(1800).
    # send-timeout only controls the waiting client; exec-timeout is persisted in
    # job metadata so the already-running codex-watch daemon can enforce it per job.
    # Other non-deep kinds keep the fast 240/540/600 budget. See _writer_timeout_args.
    _effective_timeout, _writer_extra_args = _writer_timeout_args(
        _deep, args.kind, getattr(args, "writer_timeout_sec", 600))

    try:
        result = subprocess.run(
            [
                "bash", str(WRITER_PATH),
                "--capsule-file", str(capsule_tmp),
                "--baseline-key", gd_baseline_key,
                "--review-kind", args.kind,
                "--cwd", str(_run_cwd),
                "--no-stop-marker",
            ] + _writer_extra_args,
            capture_output=True,
            text=True,
            timeout=_effective_timeout,
        )
    except subprocess.TimeoutExpired:
        timeout_sec = _effective_timeout
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"writer subprocess timeout >{timeout_sec}s")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print("TRANSPORT_RESULT: N/A")
        return 1
    finally:
        # SC-2 (T2): worktree 生命周期管理 —— writer 返回（成功/超时/异常）即释放副本，
        # 防止每次 deep code_diff 泄漏一个完整 git worktree（altitude/efficiency 双命中）。
        # worktree 仅 writer 期间需要；后续 L3/post-check 用 original target/cwd，不受影响。
        if _workcopy_manifest is not None:
            try:
                _wc_mod.cleanup_workcopy(_workcopy_manifest)  # type: ignore[union-attr]
            except Exception as _cleanup_err:  # noqa: BLE001
                print(f"WORKCOPY_CLEANUP_FAILED: {_cleanup_err}", file=sys.stderr)

    writer_stdout = result.stdout
    writer_stderr = result.stderr
    writer_exit = result.returncode

    # 解析 writer stdout 找 result path（Review Trust §Step 1：用共享 helper）。
    # Structured writer failure classification (transport_unavailable / codex_exit_N
    # / no_verdict / malformed). None on the approved path. Prefixed onto the
    # mapped degraded_reason so downstream sees the specific mode, not a stdout
    # fragment. Does not change branch order or exit semantics.
    _wstatus = parse_writer_status_line(writer_stdout)
    _wstatus_tag = f"[{_wstatus[0]}/{_wstatus[1]}] " if _wstatus else ""
    # 严格防御：path 存在性下游另查；这里只做正则提取，让 test driver 能纯离线探测。
    result_path = parse_writer_result_path(writer_stdout)

    # writer 任意非 ✓ APPROVED / ✗ REQUIRES_CHANGES → mapped FAILED
    # Plan I §1: 修去除 bare "DEGRADED" 模糊匹配 — 该子串可能出现在 capsule 内容或
    # codex 输出中（误把成功 review 当 transport degraded）。只匹配 writer 自己的 marker。
    if "[REVIEW] ⚠️ DEGRADED" in writer_stdout:
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"{_wstatus_tag}writer DEGRADED: {writer_stdout.strip()[:200]}", "degraded")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: degraded")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print(f"TRANSPORT_RESULT: {result_path or 'N/A'}")
        return 1
    if "[REVIEW] ✗ MALFORMED" in writer_stdout:
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"{_wstatus_tag}writer MALFORMED: {writer_stdout.strip()[:200]}", "degraded")
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GD_CODEX_BRIDGE_STATUS: degraded")
        print("GD_REVIEW_DECISION: FAILED")
        print(f"MAPPED_RESULT: {out_path}")
        print(f"TRANSPORT_RESULT: {result_path or 'N/A'}")
        return 1
    if "[REVIEW] ✗ FAILED" in writer_stdout or writer_exit != 0:
        mapped = _failed_mapped("codex", args.kind, target_str,
                                f"{_wstatus_tag}writer FAILED exit={writer_exit}: "
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
    # code_diff findings review code quality rather than plan SC-IDs; L3 skipped.
    # execution_outcome / combined: Codex reviews execution artifacts (sc_acceptance,
    # exec_status, deliverables) whose SCOPE_CHECKED section lists execution dimensions
    # (not plan SC-IDs). The L3 content-evidence SC-ID requirement is not applicable
    # to execution reviews — skip to avoid false-rejecting valid execution APPROVED.
    if _kind_requires_l3(args.kind):
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

    # SC-23: deep isolation post-check
    if _deep and _pre_git_status is not None:
        try:
            _gs_post = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=str(cwd), timeout=10,
            )
            _post_git_status = _gs_post.stdout
        except Exception:
            # Post-check failure is a hard error: we cannot confirm cleanliness
            print("DEEP_ISOLATION_POSTREQ_FAILED: cannot verify git status after deep run",
                  file=sys.stderr)
            _post_git_status = ""  # force diff detection below
        if _pre_git_status != _post_git_status:
            # Use absolute-path comparison to prevent substring/traversal bypass.
            # Allow any path under plans/gd/ (plan-dir results are regenerable artifacts).
            _allowed_abs = (cwd / "plans" / "gd").resolve()
            _pre_lines = set(_pre_git_status.splitlines())
            _new_changes = []
            for _line in _post_git_status.splitlines():
                if _line in _pre_lines:
                    continue
                # Porcelain format: "XY path" or "XY orig -> path" — path starts at col 3
                _rel = _line[3:].split(" -> ")[-1].strip()
                try:
                    _abs = (cwd / _rel).resolve()
                    if not _abs.is_relative_to(_allowed_abs):
                        _new_changes.append(_line)
                except Exception:
                    _new_changes.append(_line)  # conservative: treat unresolvable as violation
            if _new_changes:
                print(
                    f"DEEP_ISOLATION_VIOLATED: --deep run modified files outside allowed path: "
                    + "; ".join(_new_changes[:5]),
                    file=sys.stderr,
                )
                violated_mapped = _failed_mapped(
                    "codex", args.kind, target_str,
                    "deep isolation violated — Codex modified files outside allowed results path",
                )
                out_path.write_text(json.dumps(violated_mapped, ensure_ascii=False, indent=2), encoding="utf-8")
                print("GD_CODEX_BRIDGE_STATUS: failed_to_run")
                print("GD_REVIEW_DECISION: FAILED")
                print(f"MAPPED_RESULT: {out_path}")
                return 1

    # SC-17/SC-28: extract run_evidence from finding evidence prose when deep mode
    if _deep:
        _extract_run_evidence_into_mapped(mapped)

    # SC-28/SC-33: add plan_file_path and tests_status_source to mapped result when deep
    _plan_file_arg = getattr(args, "plan_file", None)
    if _deep and _plan_file_arg and not mapped.get("plan_file_path"):
        mapped["plan_file_path"] = _plan_file_arg
    if _deep and mapped.get("run_evidence") and not mapped.get("tests_status_source"):
        mapped["tests_status_source"] = "deep_evidence"
    if _deep:
        _apply_deep_run_evidence_gate(mapped, args.kind, out_path)
        _apply_deep_code_diff_evidence_gate(mapped, args.kind, target, out_path)
    # Write once after all deep-mode mutations
    if _deep:
        out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")

    decision = mapped["gd_review_decision"]
    status = mapped["review_run_status"]
    print(f"GD_CODEX_BRIDGE_STATUS: {status}")
    print(f"GD_REVIEW_DECISION: {decision}")
    print(f"MAPPED_RESULT: {out_path}")
    print(f"TRANSPORT_RESULT: {result_path}")
    # SC-1 (bridge N9): fail-closed exit code. Only APPROVED is a pass (0);
    # REQUIRES_CHANGES and FAILED must both surface a non-zero exit so callers
    # cannot mistake "changes required" / "failed" for a green review.
    return 0 if decision == "APPROVED" else 1


def _apply_l3_failure(mapped: dict, reason: str, out_path: "Path") -> None:
    """Apply L3 failure to mapped result and write to disk (F-R6-2 fix).

    更新 review_run_status, gd_review_decision, merge_notes.degraded_reason,
    source_of_truth_decision.value 后写盘。单 lens 路径用（dual-lens 用 _mark_l3_failure 不写盘）。
    """
    _mark_l3_failure(mapped, reason)
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

    # SC-17/SC-28: for execution_outcome/combined, extract run_evidence from finding prose
    # so the router subcommand (which consumes this mapped output) carries run-evidence.
    if args.kind in {"execution_outcome", "combined"}:
        _extract_run_evidence_into_mapped(mapped)

    out_path = Path(args.out)
    if (rc := _validate_out_path(out_path)) is not None:
        return rc
    if getattr(args, "deep", False):
        _apply_deep_run_evidence_gate(mapped, args.kind, out_path)
        _apply_deep_code_diff_evidence_gate(mapped, args.kind, target, out_path)
    out_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")

    # L3: content-evidence validator (SC-W1-1)
    # Failure → aggregate bucket "wrapper_schema_fail" (blocking).
    # review_run_status must stay schema-valid ("degraded"); wrapper_schema_fail
    # is an aggregate-level bucket, not a review_run_status enum value (F1 fix).
    # Timeout, exceptions, missing script/target are all fail-closed (F2+F5 fix).
    # code_diff findings review code quality rather than plan SC-IDs; L3 skipped.
    # execution_outcome / combined: SCOPE_CHECKED lists execution dimensions, not
    # plan SC-IDs; the SC-ID evidence requirement does not apply.
    if _kind_requires_l3(args.kind):
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
    # SC-1 (bridge N9): fail-closed exit code — only APPROVED is a pass (0);
    # REQUIRES_CHANGES and FAILED must both return non-zero.
    return 0 if decision == "APPROVED" else 1


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
    if (rc := _validate_out_path(out_path)) is not None:
        return rc
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MERGED_DECISION: {merged['gd_review_decision']}")
    print(f"MERGED_STATUS: {merged['review_run_status']}")
    print(f"MERGED_REASON: {merged['merge_notes'].get('arbitration_reason', 'N/A')[:120]}")
    print(f"OUT: {out_path}")
    # SC-1 (bridge N9): fail-closed exit code — only APPROVED is a pass (0);
    # REQUIRES_CHANGES and FAILED must both return non-zero.
    return 0 if merged["gd_review_decision"] == "APPROVED" else 1


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
                # Skip pure schema-sample files (no _test_meta — e.g. deep-*.mapped.json)
                if "_test_meta" not in desc:
                    continue
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
    p_b.add_argument("--plan-file", default=None,
                     help="SC-33: path to plan markdown file; included in deep capsule metadata")

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
    p_r.add_argument("--deep", action="store_true", default=False,
                     help="SC-1b: deep review mode; passes workspace-write plus per-job exec/send timeout ladder to writer")
    p_r.add_argument("--plan-file", default=None,
                     help="SC-33: path to plan markdown file; deep capsule includes PLAN_FILE_PATH + plan hash + SC verify commands")

    p_p = sub.add_parser("parse-transport")
    p_p.add_argument("--kind", required=True, choices=_all_kind_choices)
    p_p.add_argument("--target", required=True)
    p_p.add_argument("--raw-result", required=True)
    p_p.add_argument("--out", required=True)
    p_p.add_argument("--compat-v1", action=argparse.BooleanOptionalAction, default=None,
                     help="execution_outcome/combined: default True; plan/code_diff: default False. Explicit flag overrides kind-based inference.")
    p_p.add_argument("--deep", action="store_true", default=False,
                     help="Apply deep execution/combined run_evidence fail-closed checks while parsing.")

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
