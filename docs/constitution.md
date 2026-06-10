<!--
Sync Impact Report
==================
Version change: (none) → 1.0.0  [initial ratification]
Bump rationale: 首次采纳。为 "L3 链路 review 机制优化"（MR !11 / feature/l3-chain-mechanism）建立前置决策层。

Principles defined (6):
  P1 优化复用，不推倒重来 (Optimize by Reuse, Not Rebuild)
  P2 权威源是代码与已执行 master plan (Code & Executed Plans Are Source of Truth)
  P3 治理产物不可绕过 (Governance Artifacts Are Non-Bypassable)
  P4 Codex 不可用即 fail-closed (Fail-Closed on Codex Unavailability)
  P5 审查收敛有界 (Bounded Review Convergence)
  P6 质量与符合性分离 + anti-fill 穷举 (Separate Quality from Conformance)

Sections added: 变更边界 (Change Boundaries) / 输出契约 (Output Contract) / Governance

Files needing sync:
  ✅ projects/Project GD/CLAUDE.md — 一致（constitution 与其 lab-only/REV_VERDICT/全中文约束互补，无冲突）
  ⚠ projects/Project GD/docs/gd-v7-project-goal.md — 待处理：宜在顶部引用本 constitution 为前置决策层
  ⚠ ~/.claude/commands/gd.md「Review 对齐」段 — 待处理：/gd plan 应在审查 L3 改动时引用本 constitution 的原则编号（触 live，需 deploy-live + ledger 授权）

Deferred TODO: none（RATIFICATION_DATE 已知 = 2026-06-09）
-->

# Project GD Constitution

> 适用范围：本 constitution 治理 **L3 链路（`/gd` 四阶段中的 `/gd review plan` 与 `/gd review` execution/code）review 机制的优化工作**。它是 `/spec2`（spec 编写）→ `/spec3`（澄清）→ `/gd plan` 链路的最前置决策层，与 `CLAUDE.md`、`PROJECT_GOAL.md` 互补而非替代。

## Core Principles

### P1 · 优化复用，不推倒重来 (Optimize by Reuse, Not Rebuild)

本次工作是对**现有 L3 机制的优化**，不是重建。

- 改动 **MUST** 以扩展现有 L3 组件为主：`gd-review-suite-controller.py`（bounded-parallel + dual-gate）、`gd-codex-bridge-review.py`（共享 bridge）、`gd-review-merge-and-fix-loop.py`（≤3 轮 auto-fix）、stage-dispatch-ledger、controller-report。
- **MUST NOT** 整体替换 L3 的编排层或新建一套平行的 review 子系统。
- L2 已实现并测试的 `gd-review-controller.py`（Round 1 dual-codex + 三方并集 baseline + Round 2+ 收窄 + D7 fanout）**MUST** 以"审查引擎"身份被移植/adapt 进 L3，**MUST NOT** 取代 L3 的治理外层。
- 任何 PR 若删除或停用某个现存 L3 治理脚本 / gate，**MUST** 在 spec 中显式声明并取得用户批准，否则视为越界（review [P1] 阻断）。

*Rationale*：用户明确"优化而非推倒重来"；L3 已有可用的并发与闭环治理，重建会丢弃已验证的 gate 并放大回归风险。

### P2 · 权威源是代码与已执行 master plan (Code & Executed Plans Are the Source of Truth)

- 任何关于 L2/L3 现状的断言 **MUST** 引用实际实现（`scripts/*.py` 的 `file:line`）+ 对应的已执行 master plan（如 `plans/gd/2026-06-08-l2-review2-redesign/`）。
- **MUST NOT** 把设计稿当权威：`docs/2026-06-07-l2-review-workflow-redesign-spec.md` 是 **stale** 的——其 T1（单 reviewer 穷举）与决策集（仅 D1/D2/D3）已被 2026-06-08 master plan 的 dual-codex（D4）、D7 fanout、H5 neutral-lens 取代，实现以 `gd-review-controller.py` 为准。
- review 时 **MUST** 校验 finding / 断言是否带可点击的 `file:line` 证据；无证据的"现状描述"判 `degraded`。

*Rationale*：本会话曾因只读 redesign-spec、未读 master plan + controller 代码，误判"双 Codex 不存在"。该错误直接来自把 stale 设计稿当权威，本原则将其制度化封堵。

### P3 · 治理产物不可绕过 (Governance Artifacts Are Non-Bypassable)

优化后，以下 L3 闭环 gate **MUST** 继续强制存在并通过：

- stage-dispatch-ledger（stage=plan / stage=execute）；
- controller-report（run_mode / jobs / final_decision）；
- dual-gate：primary（聚合 error buckets）+ secondary（独立重读），disagree → `PARENT_GATE_MISMATCH`；
- bounded-parallel 派发的 owned_paths 越界检查。

任何"为了省事跳过 ledger / report / gate"的改动 **MUST** 被拒绝。

*Rationale*：这些产物是 L3 区别于裸 review 的可审计闭环；P1（复用）的具体落地就是不破坏它们。

### P4 · Codex 不可用即 fail-closed (Fail-Closed on Codex Unavailability)

- Codex transport unavailable 时，**MUST** 写 `outcome=codex_transport_unavailable` + `capability_status=blocked_missing_artifact` 并 `exit≠0`。
- **MUST NOT** 产出仅 Claude 的 `APPROVED`（禁止伪造通过）。
- 此不变量在优化前后保持一致，dual-codex 引入后任一 codex 失败的降级路径 **MUST** 同样 fail-closed（不得用另一个 codex 的 APPROVED 掩盖）。

*Rationale*：交叉验证的价值前提是"缺验证就不放行"；静默降级会让 anti-fill 防线失效。

### P5 · 审查收敛有界 (Bounded Review Convergence)

- **Round 1 穷举**：dual-codex（`codex_A` / `codex_B` 仅 `REVIEW_LENS_EMPHASIS` 不同）+ Claude self-review → 三方 findings 并集去重（键：文件 + 行号±3 + 类别，严重度取高）→ `baseline_findings.json`。
- **Round 2+ 收窄**：默认单 codex（neutral lens，H5），注入 `REVIEW_ROUND` + `BASELINE_FINDINGS` + `DELTA_SCOPE` + `SCOPE_CONSTRAINT`（只验修复 + 查 delta，**MUST NOT** 重审未改动代码 / 扩大审核边界）。
- **D7 例外**：delta > 150 行 **或** > 5 文件时，本轮才 re-fanout 回 2 codex。
- delta **MUST** 用 `git stash create` 快照获取，**MUST NOT** 为取 delta 写 git 历史。
- 连续 2 轮 unresolved 不减 → `CONVERGENCE_TIMEOUT` `exit≠0`；并发 **MUST** ≤2。
- **MUST NOT** 出现无界 ping-pong（用户实测过 12 轮的反面教材）。

*Rationale*：token 黑洞是轮数 × capsule × reasoning；首轮建基线、后续只对账是已验证的收敛手段，移植进 L3 时其语义不得被稀释。

### P6 · 质量与符合性分离 + anti-fill 穷举 (Separate Quality from Conformance; Exhaustive Anti-Fill)

- code/执行结果审查中，代码质量与 bug **MUST** 由 `/code-review`（找 bug）与 `/simplify`（清理）在上游处理。
- 发给 Codex 的 cross-review 范围 **MUST** 收窄为"只核对是否符合计划 SC（conformance），不重复找 bug"，capsule 须显式声明该 scoping。
- reviewer **MUST** 穷举：一次扫完 target 内全部 SC / 模块 / fallback 并一次列全所有 finding；明知多处只报一条 = 协议违规，判 `degraded`。
- 上述一切 **MUST** 服务项目北极星：减少"格式完整但计划不具体"的 AI 填表（见 `PROJECT_GOAL.md`）。

*Rationale*：质量与 conformance 分离可缩小每轮范围、降轮数；穷举强制直接决定 P5 的收敛速度。

## 变更边界 (Change Boundaries)

**范围内**：L3 `/gd review plan` 与 `/gd review`（execution-only / code-only / combined）的审查机制。

**范围外 / 边界约束**：

- **MUST NOT** 改动 L1（`/gd plan` dispatch）语义，除非优化确有必需且在 spec 显式声明并经批准。
- **MUST NOT** 破坏 L2 独立链路 `/review2`（它是另一套命令，本优化不回灌它）。
- Project GD `**` 内为 lab-local，可直接改；触 `~/.claude/**`（L3 实现锚点 `commands/gd.md`、live scripts/templates/hooks 等）**MUST** 走 `deploy-live` skill + ledger 授权 + parity 验证（source==installed），**MUST NOT** 直接写 live。
- **MUST NOT** 自动 `commit` / `push`；终点只产出可提交态，由 `commit-projects` / `submit-mr` 触发。

## 输出契约 (Output Contract)

- 用户可见结论 **MUST** 全中文（结构标记 / 枚举 key / 路径 / git hash 保留英文）。
- verdict **MUST** 用 `REV_VERDICT` / `GD_REVIEW_DECISION`，**MUST NOT** 输出裸 `VERDICT:`（避免误触 `~/.claude/scripts/hooks/review-stop-marker.js` regex）。`REV_VERDICT` ∈ {`APPROVED`, `REQUIRES_CHANGES`, `FAILED`}。
- 本轮含 Edit/Write/MultiEdit 或产生项目状态变化的 mutation 时，最终回复 **MUST** 套用「执行完成」模板。

## Governance

- **修订程序**：修改任一原则 **MUST** 经 PR + 用户批准，并按版本策略 bump；本 constitution 优先级高于本仓内其他 spec/plan 文档的冲突措辞，但 **不** 凌驾于 `~/.claude/CLAUDE.md` 用户全局规则与 `CLAUDE.md` 项目硬约束之上（三者冲突时以更严格者为准并在 spec 标出）。
- **版本策略**（语义化）：MAJOR = 删除/重定义原则等向后不兼容治理变更；MINOR = 新增原则/章节或实质性扩展；PATCH = 措辞澄清 / typo / 非语义调整。
- **合规审查**：`/gd plan` 的 `Review 对齐` 与后续 spec **MUST** 引用本 constitution 的原则编号（P1–P6）作为质量约束；每份 L3 优化 spec/plan **MUST** 声明它遵循哪些原则、以及（若有）申请豁免哪条及理由。

**Version**: 1.0.0 | **Ratified**: 2026-06-09 | **Last Amended**: 2026-06-09
