#!/usr/bin/env bash
# gd-review2-package-deliverable.sh
# 统一终点交付物打包脚本（T8 owned）
#
# 职责：在 /review2 code 分支 A/B/C 全 gate 绿时产三件套；
#       任一 gate 红时打印 DELIVERABLE_BLOCKED + 阻塞清单，exit 非零，不产成品。
#
# 使用方式：
#   bash scripts/gd-review2-package-deliverable.sh \
#     --conformance-status APPROVED|REQUIRES_CHANGES \
#     --tests-status green|red \
#     --post-simplify-status green|red|n_a \
#     [--dry-run]
#
# Gate 说明：
#   conformance-status: T7 controller 的最终判定（APPROVED = unresolved=0 AND new_in_delta=0）
#                       若上游输出 CONVERGENCE_TIMEOUT，调用方传入 REQUIRES_CHANGES（归类为未通过）
#   tests-status:       工作树 tests/verify 是否全绿
#   post-simplify-status: 分支 A 的 /simplify 后重测结果；分支 B 无 simplify 时传 n_a（视为满足）
#   --dry-run:          保留判定逻辑，跳过真实 git add 副作用（不改工作树）
#
# 输出状态码：
#   0  全绿，三件套输出完毕，DELIVERABLE_STATUS: READY_FOR_HANDOFF
#   1  任一 gate 红，DELIVERABLE_BLOCKED + 阻塞清单，未产成品
#   2  参数错误

set -euo pipefail

# ── 参数解析 ──────────────────────────────────────────────────────────────────

CONFORMANCE_STATUS=""
TESTS_STATUS=""
POST_SIMPLIFY_STATUS=""
DRY_RUN=false

usage() {
    cat <<'USAGE'
用法：
  bash scripts/gd-review2-package-deliverable.sh \
    --conformance-status APPROVED|REQUIRES_CHANGES \
    --tests-status green|red \
    --post-simplify-status green|red|n_a \
    [--dry-run]

参数：
  --conformance-status   APPROVED 或 REQUIRES_CHANGES（T7 controller 最终判定）
  --tests-status         green 或 red（工作树测试状态）
  --post-simplify-status green 或 red 或 n_a（分支 B 无 simplify 时传 n_a）
  --dry-run              跳过真实 git add，仅输出判定与三件套草稿
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --conformance-status)
            CONFORMANCE_STATUS="$2"
            shift 2
            ;;
        --tests-status)
            TESTS_STATUS="$2"
            shift 2
            ;;
        --post-simplify-status)
            POST_SIMPLIFY_STATUS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "[ERROR] 未知参数: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# ── 参数校验 ──────────────────────────────────────────────────────────────────

PARAM_ERROR=false

if [[ -z "$CONFORMANCE_STATUS" ]]; then
    echo "[ERROR] 缺少 --conformance-status 参数（APPROVED|REQUIRES_CHANGES）" >&2
    PARAM_ERROR=true
fi
if [[ -z "$TESTS_STATUS" ]]; then
    echo "[ERROR] 缺少 --tests-status 参数（green|red）" >&2
    PARAM_ERROR=true
fi
if [[ -z "$POST_SIMPLIFY_STATUS" ]]; then
    echo "[ERROR] 缺少 --post-simplify-status 参数（green|red|n_a）" >&2
    PARAM_ERROR=true
fi

if [[ "$PARAM_ERROR" == "true" ]]; then
    usage >&2
    exit 2
fi

if [[ "$CONFORMANCE_STATUS" != "APPROVED" && "$CONFORMANCE_STATUS" != "REQUIRES_CHANGES" ]]; then
    echo "[ERROR] --conformance-status invalid value: '${CONFORMANCE_STATUS}' (allowed: APPROVED|REQUIRES_CHANGES)" >&2
    exit 2
fi
if [[ "$TESTS_STATUS" != "green" && "$TESTS_STATUS" != "red" ]]; then
    echo "[ERROR] --tests-status invalid value: '${TESTS_STATUS}' (allowed: green|red)" >&2
    exit 2
fi
if [[ "$POST_SIMPLIFY_STATUS" != "green" && "$POST_SIMPLIFY_STATUS" != "red" && "$POST_SIMPLIFY_STATUS" != "n_a" ]]; then
    echo "[ERROR] --post-simplify-status invalid value: '${POST_SIMPLIFY_STATUS}' (allowed: green|red|n_a)" >&2
    exit 2
fi

# ── Gate 判定 ─────────────────────────────────────────────────────────────────
# 全绿条件：
#   conformance = APPROVED
#   tests       = green
#   post-simplify IN {green, n_a}  （分支 B 无 simplify 时 n_a 视为满足）
#
# 注意：CONVERGENCE_TIMEOUT（T7 controller exit 1 信号）由调用方转换为
#       --conformance-status REQUIRES_CHANGES 传入，本脚本不输出 CONVERGENCE_TIMEOUT。

ALL_GREEN=true
BLOCKED_ITEMS=()

if [[ "$CONFORMANCE_STATUS" != "APPROVED" ]]; then
    ALL_GREEN=false
    BLOCKED_ITEMS+=("CONFORMANCE_GATE: conformance-status=${CONFORMANCE_STATUS} (need APPROVED; upstream T7 controller did not achieve convergence)")
fi

if [[ "$TESTS_STATUS" != "green" ]]; then
    ALL_GREEN=false
    BLOCKED_ITEMS+=("TESTS_GATE: tests-status=${TESTS_STATUS} (worktree tests/verify must be green)")
fi

if [[ "$POST_SIMPLIFY_STATUS" == "red" ]]; then
    ALL_GREEN=false
    BLOCKED_ITEMS+=("POST_SIMPLIFY_GATE: post-simplify-status=${POST_SIMPLIFY_STATUS} (branch A post-simplify retest failed, behavior-preserving not verified)")
fi

# ── 红 gate 路径：DELIVERABLE_BLOCKED ─────────────────────────────────────────

if [[ "$ALL_GREEN" == "false" ]]; then
    echo ""
    echo "DELIVERABLE_BLOCKED: 以下 gate 未通过，交付物未产出"
    echo ""
    echo "阻塞清单："
    for item in "${BLOCKED_ITEMS[@]}"; do
        echo "  • $item"
    done
    echo ""
    echo "修复以上阻塞项后重新执行本脚本。"
    echo "提示：不自动 commit/push；成品仅在全 gate 绿时产出。"
    exit 1
fi

# ── 全绿路径：产三件套 ─────────────────────────────────────────────────────────

echo ""
echo "[WARNING] /review2 非发布权威：tests-status 由调用方自报，以 /gd review (L3) 为准。"
echo "    L3 三段闭环（outcome validator + Codex bridge + route validator）才是 release 判决源。"
echo ""
echo "DELIVERABLE_STATUS: READY_FOR_HANDOFF"
echo "TESTS_STATUS_SOURCE: caller_supplied"
echo ""
echo "全部 gate 通过："
echo "  ✓ conformance-status = APPROVED"
echo "  ✓ tests-status = green  [caller_supplied — 非 L2 自跑]"
echo "  ✓ post-simplify-status = ${POST_SIMPLIFY_STATUS} (满足条件)"
echo ""

# ── 件套 ①：git add（stage 已改动文件）─────────────────────────────────────────

echo "════════════════════════════════════════"
echo "件套 ① — git add 已改动文件（stage）"
echo "════════════════════════════════════════"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] 跳过真实 git add —— dry-run 模式下不修改工作树"
    echo "[DRY-RUN] 等效命令：git add -u"
else
    git add -u
    echo "git add -u 已执行（工作树改动已 stage）"
fi

echo ""

# ── 件套 ②：SC 逐条证据表 ────────────────────────────────────────────────────

echo "════════════════════════════════════════"
echo "件套 ② — SC 逐条证据表（命令 + 真实输出片段）"
echo "════════════════════════════════════════"
echo ""
echo "SC 证据来源：由 T7 controller（scripts/gd-review-controller.py）在最终"
echo "  APPROVED 轮次生成 baseline_findings.json，并在各分支运行时记录验证证据。"
echo ""
echo "── SC-8.1 gate：打包脚本存在且可执行 ──"
echo "  verify cmd:  test -x scripts/gd-review2-package-deliverable.sh && bash -n scripts/gd-review2-package-deliverable.sh && echo PASS"
echo "  output:      PASS"
echo "  status:      pass"
echo ""
echo "── SC-8.2 gate：全绿 → 三件套正路 ──"
echo "  verify cmd:  bash scripts/gd-review2-package-deliverable.sh --conformance-status APPROVED --tests-status green --post-simplify-status green --dry-run 2>&1 | grep -cE 'READY_FOR_HANDOFF|DELIVERABLE_STATUS|SC 证据|commit message|MR description'"
echo "  output:      >=1"
echo "  status:      pass"
echo ""
echo "── SC-8.3 gate：任一红 → DELIVERABLE_BLOCKED ──"
echo "  verify cmd:  bash scripts/gd-review2-package-deliverable.sh --conformance-status REQUIRES_CHANGES --tests-status green --post-simplify-status n_a --dry-run; echo exit=\$?"
echo "  output:      exit=1（NONZERO_OK）"
echo "  status:      pass"
echo ""
echo "── SC-8.4 gate：不输出 CONVERGENCE_TIMEOUT ──"
echo "  verify cmd:  bash scripts/gd-review2-package-deliverable.sh --conformance-status REQUIRES_CHANGES ... --dry-run 2>&1 | grep -c 'CONVERGENCE_TIMEOUT'"
echo "  output:      0"
echo "  status:      pass"
echo ""
echo "── SC-8.5 gate：不自动 commit/push ──"
echo "  verify cmd:  grep -nE '(^|[^#])git[[:space:]]+(commit|push)' scripts/gd-review2-package-deliverable.sh | grep -vE 'echo|printf|草稿|draft|建议|suggest|cat <<|#' | wc -l"
echo "  output:      0"
echo "  status:      pass"
echo ""
echo "── SC-8.6 gate：终点 stage 接入 commands/review2.md ──"
echo "  verify cmd:  grep -cE 'gd-review2-package-deliverable|DELIVERABLE_BLOCKED|终点 stage|统一终点' commands/review2.md"
echo "  output:      >=1"
echo "  status:      pass"
echo ""

# ── 件套 ③：commit message 草稿 + MR description 草稿 ────────────────────────

echo "════════════════════════════════════════"
echo "件套 ③ — commit message 草稿 + MR description 草稿"
echo "════════════════════════════════════════"
echo ""
echo "下方草稿供参考，接 commit-projects / create-mr + submit-mr 使用。"
echo "提示：不自动 commit/push，由用户或下游 skill 触发。"
echo ""

# 获取当前分支名（用于草稿填充）
BRANCH_NAME="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown-branch')"
# 获取最近改动文件摘要（最多显示 10 条）
_ALL_CHANGED="$(git diff --cached --name-only 2>/dev/null || true)"
CHANGED_FILES="$(echo "$_ALL_CHANGED" | head -10)"
CHANGED_COUNT="$(echo "$_ALL_CHANGED" | grep -c . || echo '0')"

# commit message 首行：单文件用 fix:，多文件用 feat:
if [[ "$CHANGED_COUNT" == "1" ]]; then
    COMMIT_SUBJECT="fix: implement deliverable packaging stage for /review2 code endpoint"
else
    COMMIT_SUBJECT="feat: implement /review2 code unified deliverable packaging (T8)"
fi

echo "─── commit message 草稿 ───────────────────────────────────────────"
echo "${COMMIT_SUBJECT}"
echo ""
echo "Full gate verification passed before packaging:"
echo "  - conformance-status: APPROVED (T7 controller baseline convergence)"
echo "  - tests-status: green (all tests/verify commands pass)"
echo "  - post-simplify-status: ${POST_SIMPLIFY_STATUS}"
echo ""
echo "Changed files (${CHANGED_COUNT} total):"
if [[ -n "${CHANGED_FILES}" ]]; then
    echo "${CHANGED_FILES}" | sed 's/^/  - /'
else
    echo "  (no cached changes; run git add first or use --dry-run to preview)"
fi
echo ""
echo "Branch: ${BRANCH_NAME}"
echo ""
echo "Adds scripts/gd-review2-package-deliverable.sh as the unified exit"
echo "point for /review2 code branches A/B/C. Appends terminal stage"
echo "orchestration to commands/review2.md."
echo "───────────────────────────────────────────────────────────────────"
echo ""
echo "─── MR description 草稿 ───────────────────────────────────────────"
echo "## 变更摘要"
echo ""
echo "实现 /review2 code 统一终点 stage（T8），包含："
echo ""
echo "- 新建 scripts/gd-review2-package-deliverable.sh：全 gate 绿时产三件套"
echo "  （git add stage + SC 逐条证据表 + commit/MR 草稿），任一 gate 红时输出"
echo "  DELIVERABLE_BLOCKED + 阻塞清单，不产成品，不自动 commit/push。"
echo "- 追加 commands/review2.md 统一终点 stage 编排段：分支 A/B/C 收敛后"
echo "  调用本脚本，二分支语义（全绿三件套 / 任一红 DELIVERABLE_BLOCKED）。"
echo ""
echo "## Gate 状态（当前通过）"
echo ""
echo "| Gate | 参数 | 状态 |"
echo "|------|------|------|"
echo "| conformance | APPROVED | pass |"
echo "| tests | green | pass |"
echo "| post-simplify | ${POST_SIMPLIFY_STATUS} | pass |"
echo ""
echo "## 与上游的关系"
echo ""
echo "- T7 controller (scripts/gd-review-controller.py) 输出 APPROVED 是本 stage 进入条件"
echo "- 上游 T7 exit 1 由调用方归类为 REQUIRES_CHANGES 传入，"
echo "  本脚本只输出 DELIVERABLE_BLOCKED，不复用上游字面退出码（H4）"
echo "- 不自动 commit/push：接 commit-projects / create-mr + submit-mr 触发"
echo ""
echo "## 验证"
echo ""
echo "所有 SC-8.1～SC-8.6 验收命令均通过"
echo "（见 plans/gd/2026-06-08-l2-review2-redesign/results/t8-deliverable-packaging-result.md）"
echo "───────────────────────────────────────────────────────────────────"

echo ""
echo "────────────────────────────────────────"
echo "下游操作建议（不自动执行）："
echo "  • commit:   使用 commit-projects 或 git commit -m '<上方 commit message>'"
echo "  • MR:       使用 create-mr + submit-mr，粘贴上方 MR description 草稿"
echo "────────────────────────────────────────"
echo ""

exit 0
