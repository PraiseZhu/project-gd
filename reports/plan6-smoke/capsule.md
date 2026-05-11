# /gd Codex Sidecar Review Capsule

REVIEW_KIND: plan
REVIEW_TARGET: fixtures/plans/phase2-good-plan.md
GENERATED_AT: 2026-05-11T09:03:59Z

## Goal Chain

```
# /gd v7 目标源（权威）

> **Authority status**：本文件是 `/gd` v7 的唯一目标权威源。
> **Supersedes**：旧 `Project GD/PROJECT_GOAL.md`（已在 Plan 1 baseline 标 `legacy_rev_goal_not_v7_authority`，仅作为旧 `/rev` 实验的历史 artifact 保留）。
> **Locked at**：Plan 2 v2 Step 2，Stage 由 master plan v7 锁定。
> **Consumers**：所有 `/gd` master plan / step plan / task packet / execution result / plan review / execution review / Codex cross-review capsule 必须以本文件为目标源；模板头部以 `GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md` 引用。

---

## 1. 权威目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，提升复杂任务的计划、审查、执行、验收效率，并通过 Codex 作为 cross-review sidecar 降低填表式计划与执行遗漏风险。
CHAIN_GOAL: 用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准，保证后续 /gd command、multi-agent dispatch、execution review、Codex cross-review 都引用同一套契约。
PHASE_GOAL: Project GD 内存在独立的 /gd shared core 文件组，且不覆盖旧 /rev 产物、不写 ~/.claude。
TASK_GOAL: `test -f prompts/gd-review-standard.md && test -f templates/gd-task-packet-template.md && python3 -m json.tool schema/gd-review-result.schema.json >/dev/null` 成功。
```

---

## 2. 目标层级语义

| 层级 | 角色 | 改动频率 | 改动协议 |
|------|------|---------|---------|
| `PROJECT_GOAL` | v7 项目终极目标 | 几乎不变 | 修改需用户在对话中显式授权 + Plan N 中说明 |
| `CHAIN_GOAL` | shared core 链路目标 | 几乎不变 | 同上 |
| `PHASE_GOAL` | 当前阶段目标（Plan 边界） | 每个 Plan 一次 | 各 Plan 自定，引用本文件 |
| `TASK_GOAL` | 当前 step / task packet 目标 | 每个 step 一次 | step plan 自定，引用本文件 |

`PHASE_GOAL` / `TASK_GOAL` 在各 Plan 中可覆盖；`PROJECT_GOAL` / `CHAIN_GOAL` 不可覆盖。

---

## 3. 与旧 `/rev` 的关系

- 旧 `Project GD/PROJECT_GOAL.md`：`/rev` v6 实验的目标文件，Plan 1 baseline 已标 `legacy_rev_goal_not_v7_authority`。
- 旧 `bin/rev` 仍读取旧 `PROJECT_GOAL.md`，与本文件**不冲突**：旧 `/rev` 作为 lab artifact 保留，不被 `/gd` 链路引用。
- 旧 `prompts/rev-review-standard.md`：`/rev` review 标准，Plan 1 baseline 标 `legacy_rev_standard`。`/gd` 不复用，另立 `prompts/gd-review-standard.md`。

---

## 4. 边界声明

- 本文件**不**实现 `/gd` runner、不注册 slash command、不修改任何旧 `/rev` artifact。
- 本文件**不**写 `/Users/praise/.claude/**`。
- 本文件可以被未来 `/gd` master plan 引用为 `GOAL_SOURCE`，但不可以被旧 `/rev` 模板引用。

---

## 5. 修改协议

- 任何对本文件 `PROJECT_GOAL` / `CHAIN_GOAL` 的修改，必须：
  1. 用户在对话中显式授权
  2. 对应 Plan 在 `不修改` 列表中移除本文件
  3. 修改后在 Plan 1 baseline 类似机制中重新固化 hash
- `PHASE_GOAL` / `TASK_GOAL` 在本文件中只示意当前 Plan 2 的结束态；各 Plan 内自定 PHASE/TASK GOAL 不需要回写本文件。

```

## Review Standard (gd-review-standard.md)

```
# /gd Review Standard

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md

> **本文件是 `/gd` review 的唯一标准源。**
> 所有 reviewer（Claude main / Claude subagent / Codex cross-review sidecar）必须只引用本文件，不得另立标准。
> 不复用旧 `prompts/rev-review-standard.md`（lab-only `/rev` 标准，Plan 1 baseline 已标 `legacy_rev_standard`）。

---

## 1. Output Contract

reviewer 必须按以下契约输出，**禁止裸 `VERDICT:`**（避免触发 `~/.claude/scripts/hooks/review-stop-marker.js` 的 regex）：

```text
REVIEWER:           claude_main | claude_subagent_<role> | codex
REVIEW_TARGET:      <被审 artifact 的相对路径>
REVIEW_KIND:        plan | code
REVIEW_RUN_STATUS:  completed | completed_with_constraint | degraded | failed_to_run
GD_REVIEW_DECISION:        APPROVED | REQUIRES_CHANGES | FAILED
FINDINGS:           <见第 3 节 Finding Schema>
MERGE_NOTES:        <见第 5 节 Merge Matrix>
```

`GD_REVIEW_DECISION` 必须出现且仅出现一次；任何形式的裸 `VERDICT:` 在 review artifact / template 中都被 [P1] 阻断。

---

## 2. Anti-Fill 阻断规则（最小规则集）

reviewer 见到以下任一情形 → **必须** 给 P1 或 P2，不得放过：

### 规则 A：SC verify 不可执行

`verify` 字段仅写"目视确认 / 检查一下 / 看看是否正确 / 自检即可"等无可执行手段的描述 → P1。
合规：`verify` 含**命令 / 路径 / 输出断言 / 测试用例之一**。

### 规则 B：步骤动作泛化

实现步骤的 WHAT 仅用 `完善 / 优化 / 系统性 / 全面 / 增强` 作为唯一动词 → P2。
合规：动词指向具体动作（创建 X 文件 / 修改 Y 函数 / 删除 Z 字段）。

### 规则 C：SC 未绑定可验证物

SC 既无对应命令，也无路径，也无输出断言 → P1。
合规：每条 SC 至少绑定一个可验证物。

### 规则 D：task packet 依赖对话上下文

task packet 出现"见上文 / 按之前讨论 / 参考 session 内容 / 接续刚才的任务" → P1。
合规：task packet 必须自包含；外部依赖只能通过 `required_context` 列文件路径。

### 规则 E：路径越界

execution result 的 `files_added/modified` 含 task packet `owned_paths` 之外的路径 → P1（除非 task packet 显式 `forbidden_paths` 不冲突且属于明确豁免）。

### 规则 F：裸 VERDICT 残留

review artifact / template 出现 `^VERDICT:` 行 → P1。

---

## 3. Finding Schema（统一格式）

每条 finding 必须填齐以下字段：

```yaml
severity: P1 | P2                    # 仅 P1 / P2 阻断；P3 进入 Residual Risk
title: <短标题，不含路径>
sc_refs:
  - SC-<N>                           # 关联的 SC，至少一项
evidence: <file:line — 命令 / 输出>   # 必须给出可复现锚点
impact: <按当前状态会失败的具体场景>
required_fix: <最小修复，禁止扩大范围>
verify: <补完后如何确认（命令 / 路径 / 断言）>
```

P3 不进 Findings；只能写在 Residual Risk。

---

## 4. Blocker 门槛

`GD_REVIEW_DECISION: REQUIRES_CHANGES` 仅允许用于：

- active path 会失败
- 用户目标未完成
- baseline / state / mirror 会影响后续运行
- 生成链路会继续产出错误结果
- 安全 / 数据 / 不可恢复风险
- 核心验证缺失到无法判断成功
- 触发本文件第 2 节 anti-fill 规则任一项

不得阻塞：

- 风格偏好、架构洁癖
- dormant code
- 不影响运行的 stale docs
- 没有失败证据的潜在优化

---

## 5. Merge Matrix（多 reviewer 仲裁）

| 组合 | Final 结果 |
|------|-----------|
| 全部 reviewer `APPROVED` 且全部 `REVIEW_RUN_STATUS=completed` | `final: approved` |
| 任一 reviewer `REQUIRES_CHANGES`（任一 `REVIEW_RUN_STATUS`） | `final: requires_changes` |
| 任一 reviewer `FAILED` | `final: failed` |
| 任一 reviewer `REVIEW_RUN_STATUS=degraded` 或 `failed_to_run`（其他 `APPROVED`） | `final: completed_with_constraint`（**不得 approved**） |
| reviewer verdict 冲突（一个 APPROVED 一个 REQUIRES_CHANGES） | master agent 必须在 `MERGE_NOTES.arbitration_reason` 写仲裁理由；按更严格 verdict 取值 |
| 全部 reviewer `REVIEW_RUN_STATUS != completed` | `final: failed`（无可信 verdict） |

degraded / timeout 不得自动通过。

---

## 6. Task Packet 与 Parallel/Dependency 规则

reviewer 在 plan review 中必须检查：

- 每个 task packet 含 `owned_paths` / `forbidden_paths` / `blocked_by` / `can_parallel_with` / `required_context` / `deliverables` / `verify`
- `verify` 字段满足规则 A
- task packet 之间 `owned_paths` 无重叠
- `can_parallel_with` 中的 task 必须互不在对方的 `blocked_by`
- `required_context` 列出的所有路径都在 task 自己的 owned_paths 之外（避免循环依赖）

---

## 7. Degraded / Timeout 处理

- reviewer 未在窗口内返回（超时）→ `REVIEW_RUN_STATUS: failed_to_run`，`GD_REVIEW_DECISION: FAILED`
- reviewer 返回但缺少必填字段 → `REVIEW_RUN_STATUS: degraded`，`GD_REVIEW_DECISION: FAILED`
- reviewer 显式声明降级运行（如 sandbox 阻断）→ `REVIEW_RUN_STATUS: degraded`，`GD_REVIEW_DECISION: REQUIRES_CHANGES`（不得 APPROVED）
- 任一 degraded → 进入 Merge Matrix 第 4 / 6 行

---

## 8. Codex Cross-Review Sidecar 接入约定（Plan 6 v3 active）

- Codex 仅作为 cross-review sidecar，不参与 plan / execution
- Codex 必须引用本文件作为 review standard，不得另写
- Codex sidecar 运行入口：`Project GD/scripts/gd-codex-review.py`（stdlib-only Python）
- Codex 调用方式：`codex exec --ephemeral --sandbox read-only --skip-git-repo-check --cd <GD_PROJECT_ROOT> -`（stdin = build-capsule 输出）
- 默认 timeout：240 秒（可由 `GD_CODEX_TIMEOUT` 覆盖）
- **禁止**调用旧 `~/.claude/handoff/bin/codex-send-wait`、`~/.claude/scripts/review-result-writer.sh`、`Project GD/scripts/rev-result-writer.sh`、`~/.claude/commands/review.md`、`codex-watch` daemon
- **禁止**写入 `~/.claude/**`；sidecar 所有产物路径都在 `Project GD/**` 内
- Codex 输出 review 结果必须满足：
  - 含且只含一个 `<!-- gd-review-result-json:start --> ... <!-- gd-review-result-json:end -->` block
  - JSON 必须通过 `Project GD/schema/gd-review-result.schema.json`
  - 不得出现裸 `VERDICT:` / `REV_VERDICT:`（行首 / 行内单独成 token 都拒绝）
- Codex review capsule 必须含本文件第 1 节全部字段
- Codex degraded / timeout / non-zero exit / parse fail → 按本文件第 7 节 + Merge Matrix 第 5 行处理（不得 merged APPROVED）

### 8.1 Merge Matrix（Claude + Codex 双 reviewer 合并规则）

| # | 输入 | merged 输出 |
|---|------|-------------|
| 1 | 全部 reviewer `APPROVED` 且 `REVIEW_RUN_STATUS: completed` | `APPROVED` |
| 2 | 任一 reviewer `REQUIRES_CHANGES` | `REQUIRES_CHANGES` |
| 3 | 任一 reviewer `FAILED` | `FAILED` |
| 4 | 任一 reviewer `degraded` / `failed_to_run`（无更严重 verdict）| `completed_with_constraint`（不得 APPROVED）|
| 5 | 任一 raw 输出缺/多 JSON block / schema fail / 含裸 VERDICT: 或 REV_VERDICT: | `FAILED` |

优先级：3 > 5 > 2 > 4 > 1。Plan 6 v3 sidecar runner `merge` 子命令固化此 matrix。

---

## 9. 与旧 `/review` / `/rev` 的隔离

- 本标准**不**复用旧 `prompts/rev-review-standard.md`
- 本标准**不**触发旧 `~/.claude/commands/review.md` 链路
- 本标准**不**引入裸 `VERDICT:` 字段
- 本标准产出物路径：`Project GD/reports/gd-*-review.md` 或 `~/.claude/review-baselines/<key>/result-*.md`（Codex 走后者；Claude 内部 review 走前者）

```

## Review Template (gd-plan-review-template.md)

```
# Plan Review Result

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-plan-review

---

## 1. 标识与运行状态

```text
REVIEWER: <claude_main | claude_subagent_<role> | codex>
REVIEW_TARGET: <plan 文件相对路径>
REVIEW_KIND: plan
REVIEW_RUN_STATUS: completed | completed_with_constraint | degraded | failed_to_run
GD_REVIEW_DECISION: APPROVED | REQUIRES_CHANGES | FAILED
```

`GD_REVIEW_DECISION` 取值见 `prompts/gd-review-standard.md` "Output Contract"；禁止裸 `VERDICT:`。

---

## 2. Scope Checked

| 检查面 | 结论 | 证据（≤30 字） |
|--------|------|---------------|
| <REVIEW_FOCUS 项> | pass / fail / n_a | <短语> |

---

## 3. Findings（严重度仅 P1 / P2 阻断）

### Finding 1 [P1|P2] <短标题>

```yaml
severity: P1 | P2
title: <短标题>
sc_refs:
  - SC-<N>
evidence: <plan 文件 + 行号 / 命令 / 输出>
impact: <按当前计划执行会产生的明显问题>
required_fix: <最小修复，不扩大范围>
verify: <补完后如何确认（命令 / 路径 / 断言）>
```

---

## 4. Merge Notes

```yaml
MERGE_NOTES:
  conflict_with_other_reviewer: false | true
  arbitration_reason: <如果冲突，写仲裁理由>
  degraded_reason: <如果 REVIEW_RUN_STATUS != completed，写原因>
```

---

## 5. Residual Risk（P3 或非阻塞项）

- <事项 1，没有则写 none>

---

## 6. Machine-readable Result（Plan 6 v3 sidecar 必读）

reviewer 输出**必须且只能**含一个以下 block；JSON 必须通过 `schema/gd-review-result.schema.json`。`scripts/gd-codex-review.py parse` 据此解析；缺失 / 重复 / schema fail 都会被 reject 为 `FAILED`。

<!-- gd-review-result-json:start -->
```json
{
  "template_kind": "gd-plan-review",
  "reviewer": "claude_main",
  "review_target": "<plan 相对路径>",
  "review_kind": "plan",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "scope_checked": [
    {"facet": "<focus 短语>", "result": "pass", "evidence": "<≤60 字证据>"}
  ],
  "findings": [],
  "merge_notes": {
    "conflict_with_other_reviewer": false
  },
  "residual_risk": [],
  "timestamp": "2026-05-11T00:00:00Z"
}
```
<!-- gd-review-result-json:end -->

填写规则：
- `findings` 与 §3 markdown 表必须一一对应（同顺序、同 severity / sc_refs / evidence / impact / required_fix / verify）。冲突 → parser fail。
- `gd_review_decision` 与 §1 一致。冲突 → parser fail。
- `residual_risk` 与 §5 一致。
- `timestamp` 必须是 ISO 8601 UTC（含 `Z`）。
- 禁止在 markdown 任何地方出现行首裸 `VERDICT:` 或 `REV_VERDICT:`。

```

## Target Artifact (fixtures/plans/phase2-good-plan.md)

```
# Phase 2 Smoke Test Plan

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

> 作者：Claude
> 日期：2026-05-10
> 状态：draft

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果没有 smoke 测试计划，bin/rev 的端到端行为无法被机器验证，Phase 2 验收缺乏可执行基准。
PHASE_GOAL:   bin/rev plan 在 smoke 输入上完成一次同步 review，并在 results/ 下生成 prompt.md/raw-output.txt/result.md/result.json。
TASK_GOAL:    运行 bin/rev plan fixtures/plans/phase2-good-plan.md --dry-run 后 results/<run-id>/prompt.md 存在，且含 5 个 Markdown section 标题。
```

---

## 非目标（Non-Goals）

- 不测试模型输出质量（model verdict 不可控）
- 不测试 code mode（Phase 3 reserved）
- 不修改 `~/.claude/**` 任何路径

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | bin/rev plan 接受 fixtures/plans/phase2-good-plan.md | `"$GD_ROOT/bin/rev" plan "$GD_ROOT/fixtures/plans/phase2-good-plan.md" --dry-run` → exit 0 |
| SC-2 | dry-run 生成 prompt.md 含 5 个 section | `grep -cE '^## (Review Standard|Candidate Baseline|Review Context|Artifact|Output Contract)$' <prompt.md>` → 5 |
| SC-3 | rev-baseline extract 成功产出 candidate-baseline.json | `python3 scripts/rev-baseline.py extract fixtures/plans/phase2-good-plan.md --project-goal-file PROJECT_GOAL.md --out /tmp/t.json` → exit 0 |

---

## 实施步骤

### Step 1：dry-run 验证 `[SC-1, SC-2]`

**目标**：prompt.md 正常生成，5 section 齐全

**操作**：

```bash
"$GD_ROOT/bin/rev" plan "$GD_ROOT/fixtures/plans/phase2-good-plan.md" --dry-run
```

**验收**：`grep -cE '^## ...' <prompt.md>` → `5`

**Hard-stop**：extract 失败（exit non-zero） → 停止，报告 SC 编号问题

---

### Step 2：extract baseline `[SC-3]`

**目标**：candidate-baseline.json 包含目标链和 SC 列表

**操作**：

```bash
python3 "$GD_ROOT/scripts/rev-baseline.py" extract \
  "$GD_ROOT/fixtures/plans/phase2-good-plan.md" \
  --project-goal-file "$GD_ROOT/PROJECT_GOAL.md" \
  --out /tmp/phase2-smoke-baseline.json
```

**验收**：`python3 -m json.tool /tmp/phase2-smoke-baseline.json` → exit 0

**Hard-stop**：任一 SC verify 为空 → 停止

---

## 边界约束

**允许写入**：`Project GD/results/**`、`Project GD/baselines/**`

**绝对禁止写入**：`/Users/praise/.claude/**`

---

## 依赖与前置条件

- `PROJECT_GOAL.md` 含 `^PROJECT_GOAL:` 字段
- `bin/rev` 已 chmod +x
- `scripts/rev-baseline.py` 存在且通过 py_compile

---

## 风险与防护

| 风险 | 防护 |
|------|------|
| SC numbering gap | extract 验证连续性，exit non-zero |
| PROJECT_GOAL 不匹配 | extract 字段比对，exit non-zero |
| 误写 ~/.claude/ | Hard-stop + 路径检查 |

---

## 交付物清单

| 文件 | 类型 | SC映射 | 验收状态 |
|------|------|--------|---------|
| results/<run-id>/prompt.md | new | SC-1, SC-2 | [ ] |
| results/<run-id>/candidate-baseline.json | new | SC-3 | [ ] |

```

## Reviewer Instructions

- 你是 Codex sidecar reviewer
- 仅按 §Review Standard 给出 review 结论
- 输出必须按 §Review Template 第 6 节填充唯一 `gd-review-result-json` block
- reviewer 字段填 `codex`
- 禁止裸 `VERDICT:` 或 `REV_VERDICT:`
