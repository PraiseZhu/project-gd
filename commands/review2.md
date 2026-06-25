---
description: L2 profile-aware Codex 审查工作台。subcommand-aware 调度 Codex 深度审查，输出不授予发布批准（仅 tools/gd-codex-chain-release-status.sh 产出 READY_FOR_COMMIT）。
---

# /review2 Command

> **Source of truth**: `${CLAUDE_PLUGIN_ROOT}/commands/review2.md`（随插件分发，命令安装由 `/plugin` 机制接管，无开发者机器命令副本）
> **Authority**: L2 subcommand-aware Codex workbench wrapper. NOT a replacement for `/gd review` (L3 formal review-chain authority).

## Authority Boundary

```text
L3_GD_REVIEW_SEMANTICS: unchanged
RELEASE_VERDICT: NOT_APPLICABLE (default)
```

`/review2` output never grants release approval. Only `tools/gd-codex-chain-release-status.sh` produces `OVERALL_RELEASE_STATUS: READY_FOR_COMMIT`.

## Usage

```
/review2 plan <plan-file> [--deep]        # 动手前：审计划（anti-fill 硬门 + Codex 交叉审查）
/review2 code [--code|--result|--combined] [--deep]  # 动手后：审代码/执行结果（三档自动判定）

# [--deep]：开启深度审查（codex workspace-write + 副本隔离 + deep addendum：架构/风险/接口维度
#           + 真跑 verify 命令 + 深读语义 bug 检测）。仅 plan 与 code 三块支持。
#           release_closure / runtime_parity 不支持 --deep（L2 不授予 release approval）。

# 暂留旧式 flag（Q4 不拆子命令）：
/review2 --profile release_closure  # 发布闭环验证
/review2 --profile runtime_parity   # source/installed parity 审计
```

Defaults（code 子命令）:
- `--cwd` auto-detected from git root
- 三档自动判定（无覆盖 flag 时）：调用 `scripts/gd-detect-review2-code-target.py` 探测

## Subcommands

### `/review2 plan <plan-file>`

等价于原 `--profile plan_review` 路。审查动手前的计划，防 AI 填表。

```text
BRIDGE_TARGET_POLICY: original_plan_only
```

**执行流程**：

```
/review2 plan <plan-file>
  Step1  gd-validate-review2-plan-target.py             # anti-fill 硬门（T4 owned）
           缺失 verify 命令/expect 泛词 → PLAN_ANTIFILL_FAIL exit≠0，不送
  Step3  gd-build-review2-capsule.py --kind plan        # 构建 capsule（原始计划为 PRIMARY_TARGET）
  Step4  gd-validate-review2-capsule.py                 # capsule 完整性校验（fail-closed）
  Step5  gd-codex-bridge-review.py run-bridge \         # 送 Codex 审查
           --kind plan \
           --target <plan-file> \                        # 原始计划文件，非 capsule（BRIDGE_TARGET_POLICY 保证）
           --cwd <git-root> \
           --out results/review-route-split/<run-id>/
  Step6  gd-validate-review2-output.py                  # 验证 mandatory_read 覆盖
  → APPROVED  → 输出「确定版计划」+ baseline，接 /review2 code 或 execute
  → REQUIRES_CHANGES → 列 findings，用户改计划后回 Step2
```

**Fail-closed 规则**：
- anti-fill 门不过 → `PLAN_ANTIFILL_FAIL` exit≠0，不送
- capsule 验证失败 → `CAPSULE_VALIDATE_FAIL`，停止
- capsule 缺 `BRIDGE_TARGET_POLICY` → `BRIDGE_TARGET_POLICY_MISSING`，停止
- capsule `BRIDGE_TARGET_POLICY` 值错误 → `BRIDGE_TARGET_POLICY_INVALID`，停止
- 桥接收到 capsule 路径而非原始计划 → `PLAN_TARGET_MUST_BE_ORIGINAL_PLAN`，停止
- 计划目标字段校验失败 → `PLAN_TEMPLATE_STATUS: fail`，`BRIDGE_INVOCATION_STATUS: not_started`

---

### `/review2 code [--code|--result|--combined]`

动手后审查。自动判定三档（code-only / execution-only / combined），告知用户确认后分支执行。

#### Step0 三档自动判定

调用 `scripts/gd-detect-review2-code-target.py` 执行判定：

```bash
python3 scripts/gd-detect-review2-code-target.py --cwd <git-root> [--code|--result|--combined]
```

**判定逻辑**（无覆盖 flag 时）：
- `git diff` / `git diff --cached` / untracked 有改动 → `has_code = true`
- 发现执行产物文件（含 `outcome_id`/`execution_status` 等签名字段的 JSON）→ `has_result = true`

| has_code | has_result | REVIEW2_CODE_TARGET |
|----------|------------|---------------------|
| true     | false      | `code-only`         |
| false    | true       | `execution-only`    |
| true     | true       | `combined`          |
| false    | false      | `INDETERMINATE`（exit≠0） |

**用户确认步骤**：脚本输出判定结果 + 依据后，**必须等用户确认**再进入对应分支。用户可用覆盖 flag 推翻自动判定：
- `--code` → 强制 `code-only`
- `--result` → 强制 `execution-only`
- `--combined` → 强制 `combined`
- `INDETERMINATE` → 不擅自猜测，提示用户明确指定覆盖 flag 后再执行（守 D1）

#### Step0.5 Preflight Gate（仅 code 路，送 Codex 前必须通过）

> **GATE_BOUNDARY**: 本门 **只挂 `/review2 code` 路**，不挂 `/review2 plan` 路。
> 计划阶段无代码可跑，plan 路不调用 preflight；plan 路有自己独立的 `gd-validate-review2-plan-target.py` 硬门（T4 owned）。

在进入任意分支（A/B/C）之前，必须先通过 dry-run 证据门：

```bash
bash scripts/gd-review2-preflight.sh [--evidence <path>]
# 默认探测: results/review-route-split/dryrun-evidence.json
```

**失败处理（fail-closed）**：

| preflight exit code | 输出信号 | 动作 |
|---------------------|----------|------|
| 3 | `DRYRUN_EVIDENCE_MISSING` | **立即停止，不进入任何分支，不送 Codex** |
| 1 | `DRYRUN_EVIDENCE_INVALID` | **立即停止，报告证据文件不合规** |
| 0 | `DRYRUN_EVIDENCE_OK` | 放行，继续进入分支 A/B/C |

**为什么只挂 code 路**（spec T2 WHY）：用户复盘 R1b/R4/R6 发现校验器与 fallback 自相矛盾——本地跑一次即可拦，不该让 Codex 替跑。计划阶段无代码可跑，挂 plan 路会拦截正常计划审查（spec §4 依赖图明确 T2 归位于 code 路）。

**证据文件最小合规格式**：

```json
{
  "paths_exercised": ["main", "fallback"],
  "fallback_no_api_key": true
}
```

preflight exit≠0 时，`DRYRUN_EVIDENCE_MISSING` / `DRYRUN_EVIDENCE_INVALID` 是唯一输出信号，不产出任何 capsule 或审查产物。

---

#### 分支 A · code-only

```
LOOP {
  (a) /code-review 找 bug（质量+安全）
  (b) 修复 findings
  (c) gd-codex-bridge-review.py --kind code_diff  （只验 conformance，不重复找 bug）
      capsule 注入：SCOPE_CONSTRAINT: "质量已由 /code-review 上游处理，本轮只验是否符合计划 SC"
  → (c) REQUIRES_CHANGES → 回 (a)
  → (c) APPROVED → 退出 LOOP
}
→ /simplify 清理（LOOP 通过后、最终重测前）
→ 重跑 tests/verify（必须绿，红则回 LOOP）
→ 打包交付物（T8 owned）
```

#### 分支 B · execution-only

```
LOOP {
  gd-codex-bridge-review.py --kind execution_outcome
    （重跑 deliverable/verify 命令，验执行结果是否符合计划 SC）
  → REQUIRES_CHANGES → 修，回 LOOP
  → APPROVED → 退出 LOOP
}
→ （不跑 /simplify）
→ 打包交付物（T8 owned）
```

#### 分支 C · combined

```
先走分支 A 全流程（含 LOOP + /simplify + 重测，全绿）
→ 再走分支 B（验执行结果 vs 计划 SC）
→ 两路都 APPROVED → 打包交付物（T8 owned）
```

---

<!-- T7: code 路循环编排段 — DO NOT EDIT (owned by T7 task packet) -->
#### Controller 调用（T7 owned — code 路循环编排）

三档判定通过用户确认后，code 路进入 controller 驱动的多轮循环：

```bash
# 通用调用形式（由 /review2 code 编排层注入 branch 参数）
python3 scripts/gd-review-controller.py \
  --branch <code-only|execution-only|combined> \
  --cwd <git-root> \
  --output-dir results/review-route-split/<run-id>/ \
  [--claude-review-json results/review-route-split/<run-id>/claude_self_review.json] \
  [--execution-result <execution-artifact-path>] \
  [--round2-fanout-threshold-lines 150] \
  [--round2-fanout-threshold-files 5] \
  [--max-rounds 10]
```

**三档 → Controller branch 映射**：

| REVIEW2_CODE_TARGET | --branch 参数 |
|---------------------|--------------|
| `code-only`         | `code-only`  |
| `execution-only`    | `execution-only` |
| `combined`          | `combined`   |

**Round 1（全盘建 baseline）**：
- dispatch `codex_A`（REVIEW_LENS_EMPHASIS: SC-conformance → boundary → interface/contract → failure-mode → anti-fill）
- dispatch `codex_B`（REVIEW_LENS_EMPHASIS: failure-mode → security → anti-fill → SC-conformance → boundary）
- + Claude self-review findings（`--claude-review-json`）
- 三方并集去重（file, line±3, category），severity 取最大值
- 写 `baseline_findings.json`

**Round 2+（只对账）**：
- 默认 dispatch 1 个 codex（中性 lens，无 REVIEW_LENS_EMPHASIS 偏置）
- delta > 150 行 **或** > 5 文件 → 升级至 2 个 codex（D7）
- 每轮 capsule 注入四字段：
  - `REVIEW_ROUND: N`（N ≥ 2）
  - `BASELINE_FINDINGS`：上轮清单含已修/未修状态
  - `DELTA_SCOPE`：git stash create 快照 diff（只含改动行）
  - `SCOPE_CONSTRAINT`：只验 baseline 修没修 + 查 delta 新引入，禁止重审未改动代码

**delta 快照**：
```bash
# controller 内部（不产生新 commit）
git stash create   # 取工作树快照 tree-ish；干净时 fallback 到 HEAD blob
```

**退出判定**：
- `baseline_unresolved == 0 AND new_in_delta == 0` → `APPROVED` (exit 0)
- baseline_unresolved 连续 2 轮不减 → `CONVERGENCE_TIMEOUT` (exit 1，防死循环)
- Controller 只输出 `CONVERGENCE_TIMEOUT`，**不输出** `DELIVERABLE_BLOCKED`（后者属 T8 终点 gate）

**分支 A（code-only）详细流程**：

```
LOOP {
  Round N: dispatch codex (1 or 2) via codex exec --ephemeral
           capsule: SCOPE_CONSTRAINT = "质量已由 /code-review 上游处理，本轮只验 conformance"
           消费 bridge mapped JSON findings[]（不正则解析 codex raw）
  → CONVERGENCE_TIMEOUT (连续 2 轮 unresolved 不减) → exit 1
  → baseline_unresolved > 0 → 继续 LOOP（用户修复后触发下一轮）
  → baseline_unresolved == 0 AND new_in_delta == 0 → APPROVED → 退出 LOOP
}
→ /simplify 清理（codex exec --ephemeral）
→ 重跑 tests/verify（必须绿，红则回 LOOP）
→ 交付物打包（T8 owned）
```

**分支 B（execution-only）详细流程**：

```
LOOP {
  Round N: dispatch codex 验执行结果 vs 计划 SC（复用 gd-validate-execution-outcome.py 重跑 verify）
  → CONVERGENCE_TIMEOUT (连续 2 轮不减) → exit 1    # 分支 B 同样有 CONVERGENCE_TIMEOUT 保护
  → APPROVED → 退出 LOOP
}
→（不跑 /simplify）
→ 交付物打包（T8 owned）
```

**分支 C（combined）详细流程**：

```
先走分支 A 全流程（含 LOOP + /simplify + 重测，全绿）
→ /simplify 完成后必须重跑产生新执行结果（旧结果作废）
  新执行结果 mtime 必须 > simplify 时间戳
→ 再走分支 B 验新执行结果（B 收到的文件 mtime 晚于 simplify）
→ 两路都 APPROVED → 交付物打包（T8 owned）
```

**Controller exit code 语义**：

| exit code | 含义 |
|-----------|------|
| 0 | APPROVED（所有 baseline findings resolved，delta 无新 findings） |
| 1 | CONVERGENCE_TIMEOUT 或 REQUIRES_CHANGES（未收敛） |
| 2 | 参数错误 / selftest 未知名 |

<!-- END T7: code 路循环编排段 -->

---

<!-- T8: 统一终点 stage — DO NOT EDIT (owned by T8 task packet) -->
#### 统一终点 stage（T8 owned）

分支 A/B/C 收敛后统一进入本 stage。由 `scripts/gd-review2-package-deliverable.sh` 执行打包判定。

**调用形式**（由 /review2 code 编排层在各分支收敛后注入参数）：

```bash
bash scripts/gd-review2-package-deliverable.sh \
  --conformance-status <APPROVED|REQUIRES_CHANGES> \
  --tests-status <green|red> \
  --post-simplify-status <green|red|n_a> \
  --controller-report <controller-final-report.json> \
  --tests-evidence <tests-evidence.json> \
  [--dry-run]
```

**参数来源**（各分支到本 stage 的 gate 状态传递）：

| 分支 | --conformance-status 来源 | --post-simplify-status |
|------|--------------------------|------------------------|
| A（code-only） | T7 controller exit 0→APPROVED / exit 1→REQUIRES_CHANGES | 分支 A /simplify 后重测结果：green/red |
| B（execution-only） | T7 controller exit 0→APPROVED / exit 1→REQUIRES_CHANGES | n_a（分支 B 无 /simplify）|
| C（combined） | 两路均 APPROVED 时→APPROVED，否则→REQUIRES_CHANGES | 来自分支 A 的重测结果 |

`--controller-report` 必须指向 T7 生成的 `controller-final-report.json`；APPROVED 路径必须含非空 `mapped_results`，且 mapped result 均为 `review_run_status=completed` / `gd_review_decision=APPROVED` / `bridge_failure=false`。execution/combined 路径还必须绑定非空 `run_evidence_count`。

`--tests-status green` 时 `--tests-evidence` 必须指向真实测试证据 JSON，不能只由调用方口头传 green；每条 `commands[]` 至少包含 `cmd`、`cwd`、`exit=0`、`evidence_source`、`stdout_excerpt` 或存在的 `stdout_path`。

**CONVERGENCE_TIMEOUT 处理**：
- T7 controller exit 1 可能是 `CONVERGENCE_TIMEOUT`（连续 2 轮 findings 不减）或 `REQUIRES_CHANGES`（未收敛）
- 两者均传入 `--conformance-status REQUIRES_CHANGES`，本脚本走红 gate 路径
- **本 stage 只输出 `DELIVERABLE_BLOCKED`，不复用 `CONVERGENCE_TIMEOUT` 字面码**（H4，状态码不混用）

**二分支语义**：

```
全 gate 绿（conformance=APPROVED AND tests=green AND post-simplify IN {green, n_a}）：
  exit 0，DELIVERABLE_STATUS: READY_FOR_HANDOFF
  ① git add -u（stage 已改动文件）            ← 仅 stage，不自动 commit/push
  ② SC 逐条证据表（每条 SC 的 verify 命令 + 真实输出片段，非泛词）
  ③ commit message 草稿 + MR description 草稿
  → 接 commit-projects / create-mr + submit-mr（不自动 commit/push）

任一 gate 红（conformance≠APPROVED 或 tests=red 或 post-simplify=red）：
  exit 1，DELIVERABLE_BLOCKED: 阻塞清单（逐项列出哪个 gate 红）
  不执行 git add，不产出成品（fail-visibly，守 spec §2.2）
```

**不自动 commit/push 边界**（守 spec §5）：
- 脚本全程只执行 `git add -u`（stage），不调用 `git commit` / `git push`
- commit 与 push 由用户手动或通过 `commit-projects` / `create-mr` + `submit-mr` skill 触发
- 草稿中出现的 `git commit` / `git push` 字符串均为展示性建议文本，不在实际执行路径上

<!-- END T8: 统一终点 stage -->

---

## 暂留 Flag（Q4，不拆子命令）

| Flag | 用途 | CAPABILITY_STATUS |
|------|------|------------------|
| `--profile release_closure` | 发布闭环验证（全量证据契约） | `active` |
| `--profile runtime_parity`  | source/installed parity 审计 | `active` |

执行路与原 `--profile` 路相同：

```
/review2 --profile release_closure|runtime_parity [--target <path>]
  → gd-build-review2-capsule.py
  → gd-validate-review2-capsule.py
  → gd-codex-bridge-review.py run-bridge --kind <profile-derived-kind>
  → gd-validate-review2-output.py
  → write results/review-route-split/<run-id>/
  → write results/release-evidence/<run-id>/ (if profile=release_closure)
```

---

## Output Contract（每次 /review2 调用）

```text
REVIEW_ROUTE: /review2
ROUTE_LAYER: L2
REVIEW_SUBCOMMAND: plan|code|release_closure|runtime_parity
REVIEW2_CODE_TARGET: code-only|execution-only|combined|INDETERMINATE|n_a
DRIFT_PREFLIGHT_STATUS: pass|fail|degraded
CAPSULE_CONTEXT_STATUS: pass|fail
MANDATORY_READ_STATUS: pass|fail|not_applicable
MANDATORY_READ_COVERAGE_STATUS: pass|fail|not_applicable
GIT_STATE_CONTEXT_STATUS: pass|fail|not_applicable
RELEASE_CLOSURE_CONTEXT_STATUS: pass|fail|not_applicable
MACHINE_VERDICT_SOURCE: canonical_final_status|n_a
CODEX_EXEC_MODE: direct_arg
CODEX_RUN_STATE: not_started|running|completed|failed|degraded
OUTPUT_LAST_MESSAGE_PATH: <results path or N/A>
L3_GD_REVIEW_SEMANTICS: unchanged
```

注意：输出不使用裸 `VERDICT:`，使用 `REVIEW2_CODE_TARGET` 等专用信号（守 spec §5，避免触发 live hook regex）。

---

## Codex 执行参数

```bash
# plan 路
python3 scripts/gd-codex-bridge-review.py run-bridge \
  --kind plan \
  --target <original-plan-file> \
  --cwd <git-root> \
  --out results/review-route-split/<run-id>/ \
  [--deep]

# code 路（三档，target 由 T6 修正为真实 diff / 执行产物）
python3 scripts/gd-codex-bridge-review.py run-bridge \
  --kind code_diff|execution_outcome|combined \
  --target <true-diff-or-artifact> \
  --cwd <git-root> \
  --out results/review-route-split/<run-id>/ \
  [--live-transport] \
  [--deep]
```

---

## CAPABILITY_STATUS 映射

| 子命令 / flag | CAPABILITY_STATUS |
|--------------|------------------|
| `plan`         | `active`（target preflight + capsule policy guard + anti-fill 门强制） |
| `code`         | `active`（三档判定 `gd-detect-review2-code-target.py` + 用户确认 + 分支 A/B/C） |
| `release_closure` | `active`（capsule completeness + mandatory_read coverage 强制） |
| `runtime_parity`  | `active` |

---

## Install / Update

命令安装与更新由 Claude Code `/plugin` 机制承担；本文件作为框架内文件随插件分发，无 `~/.claude/commands` 写入步骤。旧 `install-review-route-command.sh`（写 `~/.claude/commands` 的模型）已作废，不进 bundle。
