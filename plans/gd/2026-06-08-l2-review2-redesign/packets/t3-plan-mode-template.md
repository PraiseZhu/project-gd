# Task Packet: t3-plan-mode-template

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t3-plan-mode-template
agent_role: implementer
parent_step: T3
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T15:18:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表（ref GOAL_SOURCE）
CHAIN_GOAL:   让 L2(/review2) 成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交（ref master plan §1）
PHASE_GOAL:   实现并部署 L2 spec T1-T9，使 /review2 plan 与 /review2 code 两入口端到端可用（ref master plan §1）
TASK_GOAL:    在 Project GD 仓内新建 plan mode 模板 source 文件 `templates/plan-mode-template.md`——
              其"成功标准"段从"无 ID 勾选框"改为每条 `SC-N` + `verify (method: command|path|assertion|test): <命令>` + `expect: <字面输出串/exit code>`；
              "实施步骤"段每步补 `WHERE / WHAT / WHY / VERIFY` 四要素 + `SC-N` 映射；
              结构对齐 `templates/plan-template.md`（GD 版 plan 模板）。
              本 task 只写 Project GD source，**绝不直接改 live `~/.claude/templates/plan-template.md`**——回灌由 T9 经 .deploy-manifest.jsonl 完成（D6）。
```

---

## 3. 依赖与并发

```yaml
blocked_by: []                        # plan 模板独立无实现依赖；source 是新建文件，不依赖任何前置 task 产物
can_parallel_with:
  - t1                                # T1（改 gd-review-standard.md + gd-codex-bridge-review.py）与本任务无文件交集——T1 owned: gd-review-standard.md + bridge.py；T3 owned: templates/plan-mode-template.md（新建），对称关系：t1 packet 亦声明 can_parallel_with:[t3]
  - t4                                # T4（anti-fill 硬门脚本 + plan mode Stop hook）与本任务无文件交集：
                                      #   本任务 owned = templates/plan-mode-template.md（新建模板正文）
                                      #   T4   owned = scripts/gd-validate-review2-plan-target.py + plan-mode-antifill-stop-hook.js（校验逻辑）
                                      # 模板（被动结构）与硬门（主动校验）是同一 F5 缺口的两面，可并行；语义上互补但无写冲突
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md   # 读 §3 T3 段（source 归属 / WHAT 结构改动 / VERIFY）、§6 决策表 D2（已授权改全局模板）与 D6（存 Project GD source 再 deploy，不直接改 live）、§1 F5（plan 模板与 goal 提取错配）
  - templates/plan-template.md                            # 结构基准：T3 要求新模板"结构对齐"此 GD 版 plan 模板（成功标准 SC-N+verify+expect 写法、实施步骤 WHERE/WHAT/WHY/VERIFY 写法、目标链/边界/交付物清单段落骨架）
```

> **依赖说明**：本任务 `blocked_by` 为空——`templates/plan-mode-template.md` 是从零新建的 source 文件，不消费任何其他 task 的 deliverable。`required_context` 中的 `templates/plan-template.md` 是仓内既有的公共只读结构基准（非 task 产物），用作"对齐目标态"，禁止修改它。

---

## 4. 路径权限

```yaml
owned_paths:
  - templates/plan-mode-template.md      # 新建 plan mode 模板 source（D6：本 task 唯一允许写入；不直接写 live ~/.claude/templates/plan-template.md，由 T9 deploy 回灌）
forbidden_paths:
  - "/Users/praise/.claude/**"                            # D6 关键红线：本 task 只写 Project GD source，绝不碰 live；尤其禁写 ~/.claude/templates/plan-template.md（回灌是 T9 的事）
  - 旧 /rev artifacts
  - templates/plan-template.md                            # 结构基准，只读不改（required_context 公共只读资源）
  - prompts/gd-review-standard.md                         # T1 owned
  - scripts/gd-codex-bridge-review.py                     # T1/T6 owned
  - scripts/gd-validate-review2-plan-target.py            # T4 owned
  - scripts/plan-mode-antifill-stop-hook.js               # T4 owned（plan mode Stop hook）
  - commands/review2.md                                   # T2/T5 owned
  - scripts/gd-review2-preflight.sh                       # T2 owned
  - scripts/gd-detect-review2-code-target.py              # T5 owned
  - scripts/gd-review-router.py                           # T6/T7 owned
  - scripts/gd-review-controller.py                       # T7 owned
  - schema/gd-baseline-findings.schema.json               # T7 owned
  - scripts/gd-review2-package-deliverable.sh             # T8 owned
  - .deploy-manifest.jsonl                                # T9 owned（T3 source 的 deploy 条目由 T9 补入，本 task 不动 manifest）
```

读写权限分层：

- **写入**：仅限 `templates/plan-mode-template.md`（新建全文）；写入任何其他路径——尤其是 `/Users/praise/.claude/**` 下的任何文件——视为越界，review 中 [P1] 阻断（D6 红线）。
- **读取**：允许读取以下三类，超出此范围视为越界：
  1. `required_context` 列出的文件（`docs/2026-06-07-l2-review-workflow-redesign-spec.md`、`templates/plan-template.md`）
  2. 已完成的 `blocked_by` task 的 deliverables——本任务 `blocked_by` 为空，无此类
  3. 公共只读资源（GOAL_SOURCE、`prompts/gd-review-standard.md` 作为标准引用、lock files、schema）

不在以上三类范围的其他 task 的 `owned_paths`（未完成、未列入 required_context）禁止读取。

---

## 5. 成功标准（SC）

> 对应 master plan SC-3 / spec T3。每条 SC 均绑可执行 verify（见 §7）。

- [ ] SC-3a：`templates/plan-mode-template.md` 在 Project GD 仓内**存在**（新建 source，纳入版本管理；非空文件）。
- [ ] SC-3b：模板"成功标准"段**不含**无 ID 勾选框式条目（不允许 `- [ ] <无 SC 编号的描述>` 作为成功标准条目），改为每条以 `SC-N` 编号开头；且每条成功标准必须同时携带 `verify (method: ...)` 与 `expect:` 两个字段。即模板正文须出现 `SC-`、`verify (method:`、`expect:` 三个 token（method 取值约束为 `command|path|assertion|test` 四选一）。
- [ ] SC-3c：模板"实施步骤"段每步均含 `WHERE` / `WHAT` / `WHY` / `VERIFY` 四要素，且每步标注其覆盖的 `SC-N` 映射（步骤标题或步骤内显式写出对应 SC 编号）。
- [ ] SC-3d：模板结构对齐 `templates/plan-template.md`——含目标链（Goal Chain）骨架、成功标准段、实施步骤段、边界约束（含"绝对禁止写入 `/Users/praise/.claude/**`"或等价红线）；模板正文显式写明"本模板为 plan mode 用 source，部署到 live `~/.claude/templates/plan-template.md` 由 T9 deploy 完成，不在此文件内直接改 live"（D6 自述，防使用者误改 live）。
- [ ] SC-3e（goal 可提取性，对齐 spec T3 VERIFY 末句）：用本模板填写一份**最小样例计划**（含 ≥1 条带 `SC-1` + `verify` + `expect` 的成功标准）后，该样例的成功标准段能被结构化提取出**非空 SC 清单**——以"样例文本含 `SC-1` 且其后同段落内含 `verify (method:` 与 `expect:`"作为可提取性的结构判据（本 task 在 packet 内自带该样例片段供验证，不依赖外部 goal skill 运行环境）。

---

## 6. 交付物

```yaml
deliverables:
  - path: templates/plan-mode-template.md
    kind: file
    must_exist: true
    description: >
      plan mode 模板 source（D6 归属 Project GD，T9 回灌 live）。成功标准段改为 SC-N + verify(method:...) + expect: 三件套；
      实施步骤段每步含 WHERE/WHAT/WHY/VERIFY + SC 映射；结构对齐 templates/plan-template.md；
      正文含"本模板部署到 live 由 T9 完成、不在此直接改 live"的 D6 自述与"禁写 ~/.claude/**"边界红线。
      模板末尾附一段最小样例计划片段（含 SC-1 + verify + expect），用于 SC-3e 可提取性验证。
```

---

## 7. 验证（Anti-fill 硬约束）

> `verify` 字段是 anti-fill 的核心防线：必须含**命令 / 路径 / 输出断言 / 测试用例之一**。
> 下列 cmd 均为可直接在工作树根（`Project GD/.claude/worktrees/gd-l2-parity`）`bash` 执行的真实命令。
> 禁止仅写"目视确认 / 看看是否正确"作为验证。

```yaml
verify:
  - sc_ref: SC-3a
    method: command
    cmd: "test -f templates/plan-mode-template.md && test -s templates/plan-mode-template.md && echo SOURCE_EXISTS"
    expect: "SOURCE_EXISTS"
  - sc_ref: SC-3b
    method: assertion
    cmd: "grep -cE 'SC-[0-9]|verify \\(method:|expect:' templates/plan-mode-template.md"
    expect: ">=3"
  - sc_ref: SC-3b
    method: test
    cmd: "awk '/^## *成功标准/{f=1;next} /^## /{f=0} f' templates/plan-mode-template.md | grep -Eq '^[-*] \\[ \\] +[^S]' && echo HAS_UNNUMBERED || echo ALL_NUMBERED"
    expect: "ALL_NUMBERED"
  - sc_ref: SC-3c
    method: assertion
    cmd: "grep -cE '^WHERE:|^WHAT:|^WHY:|^VERIFY:' templates/plan-mode-template.md"
    expect: ">=4"
  - sc_ref: SC-3d
    method: assertion
    cmd: "grep -cE '/Users/praise/\\.claude/\\*\\*|~/\\.claude/templates/plan-template\\.md|T9' templates/plan-mode-template.md"
    expect: ">=2"
  - sc_ref: SC-3e
    method: test
    cmd: "grep -Eq 'SC-1' templates/plan-mode-template.md && grep -Eq 'verify \\(method:' templates/plan-mode-template.md && grep -Eq 'expect:' templates/plan-mode-template.md && echo GOAL_EXTRACTABLE"
    expect: "GOAL_EXTRACTABLE"
```

> **master plan SC-3 顶层验收（source 存在 + 结构合规，可执行绑定）**：
> `cmd: "test -f templates/plan-mode-template.md && grep -E 'SC-[0-9]|verify \\(method|expect:' templates/plan-mode-template.md"`
> —— source 文件必须存在，且正文必须命中 `SC-N` / `verify (method` / `expect:` 三类 token，证明成功标准段已从勾选框升级为可提取结构。
>
> **关于 spec T3 中"deploy 后 source==installed"与"goal skill 提取"两条**：
> 二者依赖 live `~/.claude/**`（deploy 后的 installed 文件、goal skill 运行环境），**本 task 范围内不执行、不验证**——它们属 T9（deploy live + parity）与 deploy 后的集成验收（goal skill 提取）。本 task 只交付并验证 **source 侧**（SC-3a~SC-3e），用 packet 自带的最小样例片段替代 live goal skill 做可提取性结构判据（SC-3e）。这是 D6"存 source 再 deploy"的直接后果：T3 不碰 live，故不在 T3 验 installed。

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t3-plan-mode-template-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论：plan mode 模板 source 是否新建、成功标准是否改为 SC-N+verify+expect、实施步骤是否补 WHERE/WHAT/WHY/VERIFY+SC 映射、是否仅写 source 未碰 live>
  blockers: <未完成的依赖或外部阻塞；T3 无实现依赖，正常应为 none；若涉及 live 部署需求，记录"待 T9 deploy 回灌"为非阻塞 follow-up>
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 task 的 `owned_paths`（任何场景）；尤其不得改 `templates/plan-template.md`（它是只读结构基准，不是本 task 产物）。
- 禁止 **直接修改 live** `~/.claude/templates/plan-template.md` 或 `/Users/praise/.claude/**` 下任何文件——D6 红线：本 task 只产出 Project GD source，live 回灌由 T9 经 `.deploy-manifest.jsonl` 完成。违反即 [P1] 阻断。
- 禁止把 deploy 逻辑、manifest 条目写进本 task——`.deploy-manifest.jsonl` 是 T9 owned，T3 不动它（即便注意到 source 尚未登记 manifest，也只在 handoff blockers 里留 follow-up，不自行补 manifest）。
- 禁止 **读取** 其他 task 的 `owned_paths`，**除非** 该 task 已完成且其 deliverables 列入本 packet 的 `required_context`（本任务 `blocked_by` 为空，无此类合法读取）。
- 禁止访问 `/Users/praise/.claude/**`（读或写均禁）。
- 禁止启动 daemon、注册 hook、修改 cron。
- anti-fill：禁止在模板正文用"完善 / 优化 / 系统性 / 全面 / 增强"作为成功标准或步骤的唯一内容——模板正是为防"格式完整但不具体"而设，其自身示范文本必须具体可验。
- 禁止用对话上下文替代 `required_context`。
```