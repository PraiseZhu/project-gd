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
