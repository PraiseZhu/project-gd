# Feature Specification: L3 链路 review 机制优化（融合 L2 收敛机制）

**Created**: 2026-06-09
**Status**: Draft
**Input**: 用户描述："根据我提的目标和功能 如何融合进l3链路 制定spec"
**Constitution**: `docs/constitution.md` v1.0.0 — 本 spec 遵循 P1（优化复用不推倒重来）、P2（权威源=代码+master plan）、P3（治理产物不可绕过）、P4（fail-closed）、P5（收敛有界）、P6（质量/符合性分离）。

## 背景与问题 *(WHY)*

L3（`/gd review plan` 与 `/gd review` execution/code）当前可用，但有两处可观测的痛点：

- **计划审查每轮全量重审**：`/gd review plan` 的 ≤3 轮 auto-fix 循环里，每一轮都把整份计划重新发审，单 Codex 视角。后果：(a) token 随轮数线性膨胀；(b) 单视角可能漏检；(c) 无状态 Codex 每轮挑不同的刺（"挑刺漂移"），难收敛。用户实测过 12 轮 ping-pong。
- **代码审查职责不分离**：`/gd review`（执行/代码）让 Codex 重复找 bug，而"代码质量/bug"本应由专门工具承担；且 Codex 未被收窄到"只核对是否符合计划"，也无清理步骤，浪费轮数。

L2（`/review2`）已实现并测试通过一套收敛机制（首轮多视角穷举建基线 + 后续只对账 + 大改动才扩covering）。**目标是把这套已验证机制融合进 L3，而非推倒重来**——保留 L3 现有的并发上限、闭环 gate（ledger/report/dual-gate）与 fail-closed 不变量。

## Clarifications

### Session 2026-06-09
- Q: 收敛机制(dual-codex 首轮 + r2 收窄)的覆盖范围? → A: 两条路都装——`/gd review plan` 与 `/gd review` 的 conformance 循环都套用。
- Q: Codex 在 code/执行审查中的定位? → A: 代码质量/bug 由 `/code-review` + `/simplify` 在上游降错率;Codex 主审“执行结果 / 已实现功能是否符合计划预期”,代码顺带扫一眼(可指出明显问题),但不以地毯式找 bug 为职责。

- Q: 双 Codex 首轮若一个视角 provider 失败? → A: 先靠 prevention 四道防线（派发前 preflight 探活 + 瞬时失败 bounded 重试 + 充足 timeout + healthcheck，均为确定性代码）保活；重试/探活耗尽后任一 Codex 仍起不来 → **fail-closed 阻断**（不降级、不以「存活视角+Claude」凑数、不仅凭 Claude 放行），逼先修 L3 transport。**无降级路径**。
- Q: 硬上限轮数? → A: 放宽到 5 轮（连续 2 轮无进展仍提前 convergence-timeout）。
- Q: 是否沿用 L2 的「r2 单 Codex + D7 大改动才升双 Codex」? → A: 不沿用。L3 链路任务皆为长任务，**每一轮都 dual-codex**，不分大小改动、去掉 D7 条件；scope 收窄（只验修复+delta）保留。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 计划审查有界收敛且首轮覆盖全 (Priority: P1)

作为运行 `/gd review plan` 的开发者，我希望计划审查在**有限轮内收敛**，且**首轮就尽量把问题一次列全**（多视角 + 穷举），这样我不再为 12 轮 ping-pong 烧 token，也不会因单视角漏检而后期返工。

**Why this priority**: 这是用户两个诉求的第一条，直接命中最大痛点（轮数 token 黑洞 + 漏检）。
**Independent Test**: 喂一份已知含多处问题的计划 fixture，跑 `/gd review plan`，验证首轮一次性报全、第 2 轮起只对账、最终在硬上限内收敛或超时——可独立交付价值，无需 US2。
**Acceptance Scenarios**:
1. **Given** 一份含 ≥3 处问题的计划，**When** 首轮 review，**Then** 首轮一次性报出全部 ≥3 处（多视角并集，非分散到多轮）。
2. **Given** 首轮已建立 finding 基线，**When** 用户修完进入第 2 轮，**Then** 第 2 轮审查输入只含"未决 findings + 计划变更部分"，不重审未改动内容、不引入超出首轮边界的新问题面。
3. **Given** 连续 2 轮未决问题数不下降，**When** 触发收敛判定，**Then** 输出 convergence-timeout 非通过态（不必跑满 5 轮硬上限）。
4. **Given** 首轮双视角中一个 Codex 经 preflight+重试 仍失败，**When** 该轮判定，**Then** fail-closed 阻断（不降级、不凑数），提示先修 L3 transport。

### User Story 2 - 代码/执行审查中质量与符合性分离 (Priority: P1)

作为执行完代码后运行 `/gd review` 的开发者，我希望**代码质量与 bug 由专门的代码审查与清理步骤承担**，而发给交叉验证的任务**只核对"是否符合计划预期"**，这样每个环节各司其职、审查更快、不重复劳动。

**Why this priority**: 用户第二条诉求；与 US1 同等重要，构成 L3 优化的另一半。
**Independent Test**: 喂一份"代码能跑但不符合计划 SC"的 fixture，验证质量审查与符合性审查是两个可分别观测的步骤、且交叉验证只判 conformance——可独立测试。
**Acceptance Scenarios**:
1. **Given** 一份待审代码改动，**When** 运行 `/gd review`（code/combined），**Then** 先经"找 bug"的代码审查步骤与"清理"步骤，再由交叉验证判定符合性，三者产物可分别观测。
2. **Given** 代码质量已在上游处理，**When** 交叉验证执行，**Then** 其任务被显式声明为“主审功能是否符合计划 SC，代码顺带扫一眼，不做地毯式找 bug”。
3. **Given** 代码不符合计划 SC，**When** 符合性判定，**Then** 返回需修复并进入有界修复循环，直到符合或超时。

### User Story 3 - 优化零破坏现有治理 (Priority: P2)

作为对审计负责的开发者，我希望这次优化**不破坏任何现有 L3 治理产物**（dispatch ledger、controller report、dual-gate、fail-closed、并发上限），这样可审计闭环与安全底线在优化后依然成立。

**Why this priority**: 这是"优化非推倒重来"的安全网；价值在于防回归，但不阻塞 US1/US2 的核心价值交付，列 P2。
**Independent Test**: 优化前后各跑一遍既有治理 gate 回归套件，对比全绿。
**Acceptance Scenarios**:
1. **Given** 优化前通过的全部治理 gate，**When** 优化落地后重跑，**Then** 全部仍通过（零破坏）。
2. **Given** 任一交叉验证 Codex 经 prevention 仍不可用，**When** review 执行，**Then** 结果为 blocked/非通过，绝不输出降级态或仅 Claude 的通过态。

### Edge Cases
- 双视角中一个 provider 失败 → 先 preflight+重试 抢救；仍失败则 fail-closed 阻断（不降级），先修 transport（per P4）。
- 计划审查的"变更"如何界定（计划是文档而非代码，delta = 计划文件版本差异）？
- `/code-review` 报出的问题落在计划范围外 / 是既存问题 → 是否计入符合性判定边界？
- 每轮 dual-codex 占满 ≤2 并发槽；Claude 自审为本地步骤、不占 Codex 并发槽。
- 收敛超时后的终态归属（由终点 gate 处置 blocked，本机制只负责给出 timeout 信号）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 多轮 review 链路(`/gd review plan` 与 `/gd review` 的 conformance 循环)首轮 MUST 综合**多个独立审查视角 + Claude 自审**，将三方 findings 去重合并为单一基线（finding baseline）。
- **FR-002**: 自第 2 轮起，上述多轮 review 链路 MUST 将审查范围限定为 (a) 核对既有 findings 是否已解决、(b) 只查变更内容；MUST NOT 重审未改动内容或扩大 finding 边界。
- **FR-003**: review MUST 以有界结果终结——收敛到通过，或在连续 2 轮无进展时给出 convergence-timeout；硬上限 = 5 轮，MUST NOT 无界循环。
- **FR-004**: 每一轮 review（含第 2 轮及以后）MUST 采用 dual-codex 双视角覆盖；不区分改动大小——L3 链路任务皆为长任务，一律双视角，不设 D7 式条件升级。第 2 轮起的双视角作用在收窄后的 scope（FR-002）之上。
- **FR-005**: `/gd review`（执行/代码）MUST 将"代码质量/bug 审查"与"清理"作为独立于符合性交叉验证的步骤执行。
- **FR-006**: 符合性交叉验证的**主目标 MUST 是**核对“执行结果 / 已实现功能是否符合已批准计划的 SC”；代码本身**顺带审视**(可指出明显问题)，但 MUST NOT 把地毯式找 bug 当作其职责(那由上游 `/code-review` 承担)。该定位须在审查任务中显式声明。
- **FR-007**: 优化后，全部既有 L3 治理产物（dispatch ledger、controller report、dual-gate 一致性检查、owned_paths 越界检查）MUST 继续被产出并强制。
- **FR-008**: 交叉验证 Codex 调用 MUST 具备 prevention 层——派发前 preflight 探活、瞬时失败 bounded 重试、充足 timeout、healthcheck 兜底，且 MUST 为确定性代码（非提示词，per 规则5）。重试/探活耗尽后**任一** Codex 仍不可用时，系统 MUST fail-closed（阻断、非通过），MUST NOT 降级以「存活视角+Claude」凑数，MUST NOT 仅凭 Claude 放行。
- **FR-009**: 并发 MUST 保持 ≤2 个并行审查 job 的上限。
- **FR-010**: 本优化 MUST NOT 改动 L1（`/gd plan` dispatch）语义，也 MUST NOT 改动独立的 L2 `/review2` 命令。
- **FR-011**: reviewer MUST 穷举——一次扫完 target 内全部 SC/模块/fallback 并一次列全可发现 finding；明知多处只报一条须被判为降级（degraded）。

### Key Entities *(涉及数据)*

- **Finding Baseline（finding 基线）**：首轮多视角 + 自审并集去重后的问题清单，跨轮携带；含问题定位、描述、严重度、已决/未决状态。
- **Review Round（审查轮次）**：轮号 + scope 标记（首轮全量 / 第 2 轮起收窄）；每一轮均为 dual-codex。
- **Delta Scope（变更范围）**：收窄审查所针对的"本轮改动内容"。
- **Conformance Verdict（符合性判定）**：改动是否符合计划 SC 的结论，独立于质量/bug 结论。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 对一个已知含 N（≥3）处问题的计划 fixture，首轮 review 一次性报出全部 N 处，而非分散到多轮。
- **SC-002**: 第 2 轮及以后的审查输入只含"未决 findings + 变更内容"，可被验证不含未改动全量（输入带轮次≥2 标记且范围受限）。
- **SC-003**: 同一份计划的端到端 review 在 5 轮硬上限内终结；对照旧链路实测的 12 轮，收敛轮数中位数显著下降。
- **SC-004**: 收敛超时场景可复现——构造连续 2 轮无进展的 fixture，系统给出 convergence-timeout 非通过态，且不进入超限轮。
- **SC-005**: 代码审查路径中，"找 bug/清理"与"符合性"是两个可分别观测的步骤与产物（存在质量审查产物 + 独立 conformance 判定）。
- **SC-006**: 优化前已通过的全部 L3 治理 gate（ledger/report/dual-gate）在优化后回归 100% 通过（零破坏）。
- **SC-007**: 任一 Codex 经 prevention（探活+重试+timeout）仍不可用的故障注入下，结果为 blocked/非通过；无「降级继续」、无「仅 Claude 通过」的输出。
- **SC-008**: 注入一次「瞬时失败」后，prevention 的 bounded 重试使该 Codex 恢复、review 正常进行（不误入 fail-closed）——验证防线先于阻断生效。

## Assumptions

- **移植基准**：L2 已实现并测试通过的收敛机制（首轮多视角并集建基线 + 第 2 轮起 scope 收窄 + 收敛超时）是本优化的移植参照；其权威源为实现代码 `scripts/gd-review-controller.py` 与已执行 master plan `plans/gd/2026-06-08-l2-review2-redesign/`（per 宪法 P2，不以 stale 设计稿为准）。**L3 刻意偏离 L2**：不沿用「r2 单 Codex + D7 大改动升级」，改为每一轮都 dual-codex（因 L3 任务皆为长任务）。
- **每轮多视角 = 2 个交叉验证视角 + Claude 自审**：双视角仅审查侧重点不同（两份任务 capsule 唯一差异为视角侧重）；首轮三方并集建 baseline，第 2 轮起在收窄 scope 上仍双视角。
- **计划审查的 delta**：计划为文档，轮间变更由计划文件版本差异界定，可被快照捕获。
- **代码质量与清理步骤**：`/code-review`（找 bug）与 `/simplify`（清理）在 L3 运行环境可用，作为符合性交叉验证的上游步骤。
- **部署边界**：L3 实现锚点 `commands/gd.md` 等位于 live runtime；本 spec 只定义 WHAT/WHY，落地部署走 `deploy-live` + ledger 授权 + parity 验证（不在本 spec 范围内，由 `/gd plan` 之后的部署阶段承担，per 宪法变更边界）。
- **transport 先行**：FR-008 的 prevention 层（探活/重试/timeout/healthcheck）是 dual-codex 覆盖有意义的前提；用户要求「先修 L3 链路」，故 `/gd plan` 中宜把 transport 加固排为**前置任务**，避免 fail-closed 频繁触发。
- **HOW 留给 /gd plan**：编排器关系（L2 controller 当审查引擎 + L3 gate 当闭环外层）、/code-review 与 Python 循环的调用方式等实现决策，不在本 spec，留给 `/gd plan`。
