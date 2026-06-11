# GD 三链路插件封装 Master Plan v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-master-plan

日期：2026-06-11
状态：draft
负责人：Claude 执行；Codex cross-review（/gd review plan）

> **Governing Constitution**：`docs/constitution-plugin.md` v1.1.0（P1–P6）。
> **Governing Spec**：`specs/gd-plugin-packaging/spec.md`（FR-001~018，SC-001~010，含 Clarifications）。
> 本 master plan 只定"怎么实现封装"，不重开范围讨论；范围决策以上述两文件为权威。

---

## 1. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，提升复杂任务的计划、审查、执行、验收效率，并通过 Codex 作为 cross-review sidecar 降低填表式计划与执行遗漏风险。（ref GOAL_SOURCE §1）
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准，保证后续 /gd command、multi-agent dispatch、execution review、Codex cross-review 都引用同一套契约。（ref GOAL_SOURCE §1）
PHASE_GOAL:   把 /review1（L1）/ /review2（L2）/ /gd（L3）三个独立命令及其全部运行时依赖封装为可分发的 macOS Claude Code 插件——零开发者绝对路径、bundle 完整（含 vendor/l3-transport）、codex 传输栈前置分两段声明、setup 命令收 4 选项制预设、跨目录冒烟证明可用，满足 constitution-plugin.md P1–P6 与 spec SC-001~010。
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS（分号分隔）：插件分发完整性（bundle 缺漏=安装即断）; 路径可移植性（开发者绝对路径清零）; 写入隔离（更新不丢运行时数据）; 外部依赖 fail-closed（缺 codex 不伪 APPROVED）; setup 预设选项制（不自由填、不内置 key）
- Domain-specific notes：本期是**封装与分发**，不改任一链路的 review 判定语义（那归 docs/constitution.md v1.0.0）。一切运行时写入必须可在安装者机器解析；任何引用 `vendor/l3-transport` 的缺漏都是 blocking。

---

## 3. 成功标准（SC，对齐 spec SC-001~010）

> Anti-fill：每条 SC 绑定命令 / 路径 / 输出断言之一；禁止仅写"完善 / 优化 / 系统性 / 全面 / 增强"。
>
> **SC 编号归一说明**（对齐 L3 content-evidence 校验器的零填充归一）：本计划主用零填充形式 SC-001 … SC-010；其去零等价别名为 SC-1, SC-2, SC-3, SC-4, SC-5, SC-6, SC-7, SC-8, SC-9, SC-10（reviewer 若用去零或区间简写如 "SC-001~010"，与本表逐条等价）。下列十条即 SC-1 … SC-10 的零填充写法。

- [ ] SC-001：新安装者从零到三链路命令出现 ≤ 1 行安装命令 + 1 次 reload。verify：`.claude-plugin/marketplace.json` 与 `plugin.json` 存在且 README 含单行 `claude plugin marketplace add ... && claude plugin install ...`。
- [ ] SC-002：安装后链路 runtime 引用文件（含 `vendor/l3-transport`）可解析率 100%（"file not found" = 0）。verify：bundle 完整性清单脚本对 commands/scripts/prompts/templates/schema/docs/fixtures/vendor/l3-transport 全绿。
- [ ] SC-003：在非 Project-GD 项目目录跑链路 happy path 端到端通（跨目录冒烟）。verify：冒烟脚本在临时非 GD git repo 触发命令、产物落隔离区、退出 0。
- [ ] SC-004：缺 codex 环境下依赖 codex 阶段伪 APPROVED = 0，中文缺失提示出现率 100%。verify：模拟缺 codex，断言 fail-closed + 中文提示，无裸 APPROVED。
- [ ] SC-005：维护者更新到安装者生效 ≤ 3 条手动命令。verify：README 明列 marketplace update → plugin update → reload 三命令。
- [ ] SC-006：插件更新后安装者既有运行时数据保留率 100%。verify：运行时产物路径解析到 `${CLAUDE_PLUGIN_DATA}` 或目标项目，非插件安装目录。
- [ ] SC-007：分发产物中开发者机器专属绝对路径出现次数 = 0。verify：`grep -rn "/Users/praise"` 对 bundle 内命令/脚本 = 0 命中（docs/fixtures 历史引用除外，按 spec 边界）。
- [ ] SC-008：安装要求 `pip install` 第三方包数 = 0；内置 API key/密钥数 = 0。verify：脚本仅 import 标准库 + 本地 lib；`grep` 密钥模式 = 0。
- [ ] SC-009：备齐 codex 传输栈环境三链路 cross-review happy path 真实跑通率 100%；README 传输栈三件套前置声明完整。verify：README 含 CLI / 自备 key / daemon 三件套分段；备齐环境冒烟得真实 codex 结论。
- [ ] SC-010：setup 命令预设四项（输出位置/codex key/codex 模型/模型强度）完整度 4/4，每项选项制（自由填 = 0），key 类型覆盖 官方+第三方 = 2/2，可重跑，update 后保留 100%，内置默认 key = 0。verify：setup 命令文件含四字段选项枚举 + 持久化到 `${CLAUDE_PLUGIN_DATA}` + 无内置 key。

---

## 4. 非目标（NON_GOALS）

- 不支持 Windows / Linux（传输层基于 macOS LaunchAgent；spec Assumptions 已锁）
- 不代装 codex CLI 等外部二进制、不分享/内置任何 API key
- 不改任一链路 review 判定语义（归 docs/constitution.md v1.0.0）
- 不引入 auto-update 机制（仅手动更新命令）
- 不 `git commit` / `push`（终点为可提交态，由 commit-projects / submit-mr 触发）

---

## 5. Step 拆分

| Step | 名称 | owned_paths | blocked_by | can_parallel_with | 主要 SC |
|------|------|------------|-----------|-------------------|---------|
| A | 插件面：`.claude-plugin/` + 安装 README + setup 命令 | `.claude-plugin/`, 安装 README, `commands/setup.md`(+脚本) | — | B | SC-001, SC-005, SC-008, SC-009, SC-010 |
| B | 可移植+隔离：命令清硬编码 + HANDOFF_ROOT + 写入隔离 + 跨目录冒烟 | `commands/*.md`, `vendor/l3-transport/handoff/lib/state-paths.sh`, 写产物脚本, 冒烟脚本 | — | A | SC-002, SC-003, SC-004, SC-006, SC-007 |

> Step A 与 B 在**计划阶段**互不依赖（各自起草自己簇的 step plan + task packets，写入独立 plan 子目录）。**执行阶段**的实际代码改动 owned_paths 不重叠（A 建新文件；B 改既有命令/transport/脚本），由各 task packet 的 owned_paths 精确界定，执行期再按 `/gd execute` 合约校验。

---

## 5a. Dispatch Map / Wave Contract（MANDATORY）

### Dispatch Map 引用

```
DISPATCH_MAP_PATH: plans/gd/2026-06-11-plugin-packaging/dispatch-map.json
VALIDATE_CMD: python3 scripts/gd-validate-dispatch.py plans/gd/2026-06-11-plugin-packaging/dispatch-map.json
```

### Wave Matrix

| Wave | Tracks（同 wave 可并行） | 并行前提验证 |
|------|------------------------|-------------|
| 1 | track-a-plugin-surface, track-b-portability-isolation（并行，child_agent_count=2） | can_parallel_with 双向声明；owned_paths（track-a/ vs track-b/）不重叠；互不在对方 blocked_by；required_context 不依赖对方 deliverable |

> 规则：同 wave ≤2 track（max_parallel=2 硬上限）；主 agent 先跑 VALIDATE_CMD（exit 0）再按 wave dispatch child planner；VALIDATE_CMD 失败 → 禁止 dispatch。

---

## 6. 边界（修改 / 不修改）

修改（计划阶段产物）：
- `plans/gd/2026-06-11-plugin-packaging/**`（master plan / dispatch map / track-a / track-b / dispatch ledger+report）

不修改：
- 旧 `/rev` 任何 artifact
- `/Users/praise/.claude/**`
- 任一链路的 review 判定语义
- 任何源码（计划阶段只产计划；代码改动留给 `/gd execute`）

---

## 7. 风险与防护

| 风险 | 防护 |
|------|------|
| bundle 漏 `vendor/l3-transport` → 安装者 cross-review 全 fail-closed | SC-002 完整性清单把 vendor/l3-transport 列 blocking（constitution P3）|
| 清硬编码时把 `${CLAUDE_PLUGIN_ROOT}`（框架根）与 `${CLAUDE_PROJECT_DIR}`（目标项目）混用 → 误写回插件目录 | track-b task packet 显式区分二者（constitution P2）；SC-006 验证写入隔离 |
| HANDOFF_ROOT daemon↔client 两端不一致 → 断链 | HANDOFF_ROOT 设插件管理目录、不进安装者预设、不让自由填（spec FR-016）|
| setup 预设自由填路径破坏传输协同 | 四字段全选项制（spec FR-018 / SC-010）|
| 冒烟靠本仓自测断言 → 假"可移植" | SC-003 要求非 GD 临时 repo 跨目录冒烟（constitution P1 / spec FR-014）|

---

## 8. 测试计划

```bash
# 计划阶段 gate（本 master plan + dispatch map 自身）
python3 scripts/gd-validate-dispatch.py plans/gd/2026-06-11-plugin-packaging/dispatch-map.json ; echo "exit=$?"
test -f plans/gd/2026-06-11-plugin-packaging/track-a/step-plan.md && echo PASS-A
test -f plans/gd/2026-06-11-plugin-packaging/track-b/step-plan.md && echo PASS-B
# child proposal 校验
python3 scripts/gd-validate-child-proposal.py plans/gd/2026-06-11-plugin-packaging/dispatch/child-a-proposal.json ; echo "exit=$?"
python3 scripts/gd-validate-child-proposal.py plans/gd/2026-06-11-plugin-packaging/dispatch/child-b-proposal.json ; echo "exit=$?"
# Rev21 final-gate 证据
python3 scripts/gd-validate-stage-dispatch-ledger.py plans/gd/2026-06-11-plugin-packaging/dispatch/stage-dispatch-ledger.json ; echo "exit=$?"
python3 scripts/gd-validate-controller-report.py plans/gd/2026-06-11-plugin-packaging/dispatch/controller-report.json ; echo "exit=$?"
```

---

## 9. Assumptions

- 平台仅 macOS；安装者具备私有 GitLab repo 访问权（spec Assumptions）
- codex 传输栈由安装者自备（CLI + 自备 key + daemon），插件只声明前置
- 分发用 git-subdir 同仓布局，`plugin.json` 省略 version（SHA 即版本）
- "三条链路" = `/review1` + `/review2` + `/gd` 三个独立命令；`/gd` 四阶段是其内部阶段
- 计划阶段 child planner 只起草、不写源码；代码改动留给后续 `/gd execute`
