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

## 8. Codex Cross-Review Bridge（Plan 6.5-B candidate；Plan 6 v3 direct sidecar deprecated）

### 8.0 状态变更说明

Plan 6 v3 direct `codex exec` sidecar 已 deprecated（保留 `scripts/gd-codex-review.py` 作为 audit/recovery，不删除；revisions[1.3.0] = completed_with_constraint）。Plan 6.5-B 改用 bridge wrapper 通过旧 `/review` transport 投递给 Codex。本节描述 bridge candidate；`/gd review plan/code` active 状态升级由 Plan E 一次性完成。

### 8.1 三层 Verdict 隔离（必须遵守）

| 层 | 字段 | 允许出现位置 |
|---|------|-----------|
| External transport raw | 行首 `VERDICT: APPROVED` / `VERDICT: REQUIRES_CHANGES` | 旧 writer 的 raw result `~/.claude/review-baselines/<key>/result-*.md`；bridge raw fixtures；fenced 示例 |
| Bridge mapped | `gd_review_decision: APPROVED|REQUIRES_CHANGES|FAILED`（JSON 字段）| `schema/gd-review-result.schema.json` 通过的 mapped JSON |
| `/gd` final artifact | `GD_REVIEW_DECISION:`（中文报告字段）| `/gd` 任意 final artifact（含 segment report、final review 输出、Plan E 之后 commands/gd.md 输出契约）|

`/gd` final artifact **绝对禁止**裸行首 `VERDICT:` 或 `REV_VERDICT:`。

### 8.2 旧 transport 与 bridge wrapper 职责分层

旧 transport / writer 负责（Plan B 不修改）：

- 通过 `~/.claude/handoff/bin/codex-send-wait` 把 capsule 投递给 Codex watch
- 保存 raw result 到 `~/.claude/review-baselines/<gd_baseline_key>/result-*.md`
- 解析旧 raw `VERDICT: APPROVED | REQUIRES_CHANGES`
- 校验旧 raw markdown 基础结构：`# Plan|Code Review Result` 标题 / `Scope Checked` / `## Findings` / `## Residual Risk` / 每 finding 含 5 中文字段（问题/证据/影响/最小修复/验收）/ REQUIRES_CHANGES 必含 ≥1 `### Finding`

`/gd` bridge wrapper 额外负责（不与 writer 重复）：

- 生成带 `/gd` 标准与目标链的 capsule
- 生成并传入 `gd_baseline_key`（公式见 §8.5）
- 找到 writer 保存的 raw result path
- **额外**校验 raw finding 中的 `SC: SC-<N>` 引用（writer 不查；schema `findings[].sc_refs` minItems=1 强制）
- 把 raw result 映射为 `schema/gd-review-result.schema.json` 通过的 JSON
- 校验 mapped JSON schema
- 执行 Claude/Codex merge matrix
- 把 unavailable / degraded / malformed / writer 任意非成功 stdout 全部 fail-closed 到 `gd_review_decision: FAILED`

### 8.3 Capsule 字段分层（Plan 6.5-B v3 收紧）

writer 实际 grep 并写入 `latest-plan-baseline.json` 的字段（**只 3 个**）：

- `REVIEW_DOMAIN`
- `REVIEW_FOCUS`
- `REVIEW_FOCUS_SOURCE`

writer 会保存到 `capsule-<ts>.txt` 审计轨但不解析进 baseline JSON 的字段（建议 capsule 含全；缺失不会让 writer fail）：

- `REVIEW_KIND`、`REVIEW_ROUND`、`REVIEW_DELTA_SCOPE`
- `PLAN_REVIEW_ALIGNMENT`、`PLAN_ALIGNMENT_PRESENT`
- `DOMAIN_OVERRIDE_REASON`
- `PROJECT_ROOT`、`REPO_ROOT`、`BRANCH`
- `IN_SCOPE`、`OUT_OF_SCOPE`、`USER_ACCEPTED_DECISIONS`
- `SUCCESS_CRITERIA`、`KNOWN_LIMITATIONS`
- `BASELINE_CONFIDENCE`、`REVIEW_RULES`

`/gd` wrapper 自用、writer 完全不读取的字段（仅给 Codex reviewer 看）：

- `GD_STANDARD`、`GOAL_SOURCE`
- `REVIEW_TARGET`、`TARGET_HASH`、`CAPSULE_HASH`
- `GD_BASELINE_KEY`、`GD_REVIEW_SCHEMA`
- `EXPECTED_SC_IDS`

### 8.4 允许 / 禁止 调用清单

允许（仅由 `scripts/gd-codex-bridge-review.py` 在 `--live-transport` 模式下调用）：

- `~/.claude/scripts/review-result-writer.sh`
- `~/.claude/handoff/bin/codex-send-wait`（间接，由 writer 调用）

禁止（`/gd` 所有路径下都不允许）：

- `~/.claude/commands/review.md` slash command（直接调用）
- `Project GD/scripts/rev-result-writer.sh`（旧 /rev 链路）
- 修改 `~/.claude/scripts/review-result-writer.sh`、`~/.claude/handoff/bin/codex-send-wait`、`codex-watch` daemon、任何旧 `/review` / `/rev` 文件
- 写 `~/.claude/**` 的非 `review-baselines/<gd_baseline_key>/` 路径

### 8.5 baseline key 公式

`gd_baseline_key = gd-<review_kind>-<target_slug>-<sha256(target_abs_path + target_hash + run_id)[:12]>`

由 wrapper 生成并传入 writer 的 `--baseline-key`。Writer 用此 key 创建 `~/.claude/review-baselines/<gd_baseline_key>/` 作为 storage path。bridge 不再设计"双 baseline key"。

### 8.6 Mapped Result 唯一权威

所有 mapped review result 必须通过 `schema/gd-review-result.schema.json`。**不**新增第二套 review result schema。merge result 用 `reviewer: claude_subagent_merge`（仅满足 schema pattern；不代表实际调用 subagent）。

### 8.7 Merge Matrix（Claude + Codex 双 reviewer 合并规则）

| # | 输入 | merged 输出 |
|---|------|-------------|
| 1 | 双方均 `APPROVED` 且 schema pass | `APPROVED` |
| 2 | 任一 reviewer `gd_review_decision == REQUIRES_CHANGES` | `REQUIRES_CHANGES` |
| 3 | 任一 reviewer `gd_review_decision == FAILED` | `FAILED` |
| 4 | 任一 reviewer `review_run_status in {degraded, failed_to_run}` | `FAILED` |
| 5 | 任一 JSON schema fail / 缺字段 / 多余字段 | `FAILED` |

优先级：3 > 5 > 4 > 2 > 1。`scripts/gd-codex-bridge-review.py merge` 子命令固化此 matrix。

注意 Plan 6 v3 sidecar 的 matrix 第 4 行原是 "degraded → completed_with_constraint"。Plan 6.5-B 收紧为 "degraded/failed_to_run → FAILED"，因为 bridge 透过旧 transport 拿不到通过的 verdict 时，没有任何客观依据可以 merged 出"completed_with_constraint" — 只能 FAILED 等用户重跑。

### 8.8 Plan E Integration Contract

Plan B 不修改 `commands/gd.md` active behavior。Plan E 接线时只能：

1. 调 wrapper `run-bridge --live-transport` 取得 mapped Codex JSON
2. 调 wrapper `merge --claude <claude.json> --codex <codex.json>` 获 merged JSON
3. 暴露 merged result 为 `/gd` final decision

Plan E 不得重新设计 bridge raw contract / mapped schema / merge matrix。

### 8.9 旧 Plan 6 v3 sidecar 节（已废弃）

原 §8 Plan 6 v3 direct sidecar 内容（禁止 codex-send-wait / review-result-writer 等）已被本节 §8.0-§8.8 反转。`scripts/gd-codex-review.py` 文件头追加 `DEPRECATED` marker 但保留代码与 fixtures（v3 sidecar 的 4 子命令 build-capsule/run-codex/parse/merge 留作 audit/recovery，不再是 active 入口）。详见 `reports/gd-v7-plan6.5-b-codex-bridge.md`。

---

## 9. 穷举强制（一次列全所有可发现 finding）

> **所有 reviewer（Claude main / Claude subagent / Codex cross-review sidecar）必须严格遵守本节。**

### 9.1 穷举义务

reviewer 在给出任何 verdict 之前，必须完整扫描 PRIMARY_TARGET 内的**全部**以下对象：

- 每一条 `SC-N`（成功标准）
- 每一个实现模块 / 函数 / 脚本段
- 每一条 fallback / 异常 / 降级路径
- 每一个 `deliverables_produced[].path`（如存在）
- 每一个 `verify_results[].cmd`（如存在）

reviewer 必须**一次列全**所有在本次扫描中可发现的 finding，不得分批分轮逐条透露。

### 9.2 协议违规判定（degraded）

以下任一情形即构成**协议违规**，reviewer 输出自动判定为 `REVIEW_RUN_STATUS: degraded`：

1. **明知多处问题、只报一条**：reviewer 可发现 ≥2 处 P1/P2 问题，但 findings 列表仅列出 1 条。
2. **路径截断**：reviewer 明确表示"本轮只审部分 SC / 留待下轮"（多轮拆报等同于协议违规）。
3. **选择性略过**：已扫描某 SC 但未记录发现（无论认为是否通过），且未在 SCOPE_CHECKED 表中给出明确的 pass 判定。

`REVIEW_RUN_STATUS: degraded` 不得产出 `GD_REVIEW_DECISION: APPROVED`（见 §5 Merge Matrix 第 4 行）。

### 9.3 SCOPE_CHECKED 完整性要求

每次 review 输出的 `SCOPE_CHECKED` 表必须覆盖 PRIMARY_TARGET 中**全部** SC-ID；缺少任何一条 SC-ID 视为穷举不完整，进入 §9.2 第 3 条协议违规判定。

---

## 10. 与旧 `/review` / `/rev` 的隔离

- 本标准**不**复用旧 `prompts/rev-review-standard.md`
- 本标准**不**触发旧 `~/.claude/commands/review.md` 链路
- 本标准**不**引入裸 `VERDICT:` 字段
- 本标准产出物路径：`Project GD/reports/gd-*-review.md` 或 `~/.claude/review-baselines/<key>/result-*.md`（Codex 走后者；Claude 内部 review 走前者）

