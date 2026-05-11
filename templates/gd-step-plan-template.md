# Step <N>: <名称> v<n>

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-step-plan

日期：YYYY-MM-DD
状态：draft | reviewed | approved | executing | done | blocked
负责人：Claude 执行；Codex 可选 cross-review

---

## 1. 目标链（继承 + 当前 task goal）

```text
PROJECT_GOAL: <ref GOAL_SOURCE>
CHAIN_GOAL:   <ref GOAL_SOURCE>
PHASE_GOAL:   <ref master plan>
TASK_GOAL:    <本 step 的具体目标，必须可被 SC 验证>
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra | app_code | docs_content | other`
- REVIEW_FOCUS（3-5 项分号分隔）：`<focus 1>; <focus 2>; <focus 3>`
- Domain-specific notes：<本 step 特有的 review 注意点>

---

## 3. 前置条件

- blocked_by：`<step id>` 或 `—`
- 必须的 baseline / artifact：<列出依赖文件路径>
- Hard-stop 条件：<未满足时停止>

---

## 4. 成功标准（SC，本 step 内的）

> **Anti-fill 规则 A**（来自 `prompts/gd-review-standard.md` §2）：每条 SC 必须绑定**命令 / 路径 / 输出断言 / 测试用例之一**；禁止仅写"目视确认 / 检查一下 / 自检即可"作为唯一内容。
> 写不出可执行 verify 的条件不得作为 SC。

- [ ] SC-1：<具体可验证条件>
  - verify (method: command|path|assertion|test): `<示例：test -f path && echo PASS>`
  - expect: `<示例：PASS>`
- [ ] SC-2：<...>
  - verify (method: command|path|assertion|test): `<...>`
  - expect: `<...>`

---

## 5. 非目标

- <明确不做的事>

---

## 6. 实现步骤

每个步骤必须写齐 4 字段：

```text
Step.N
  WHERE: <文件 / 目录 / 命令的精确位置>
  WHAT:  <做什么具体动作>
  WHY:   <为什么这一步必须存在>
  VERIFY: <做完后如何验证（命令 / 路径 / 断言之一）>
```

禁止用 "完善 / 优化 / 系统性 / 全面 / 增强" 作为唯一动作描述。

---

## 7. Task Packet 拆分

每个并行子任务用 `gd-task-packet-template.md` 单独写一个 task packet 文件，列在此处：

| task_id | agent_role | owned_paths | blocked_by | can_parallel_with |
|---------|-----------|------------|-----------|-------------------|
| t1 | <role> | <paths> | — | t2 |

---

## 8. 边界（修改 / 不修改）

修改：
- <相对路径>

不修改：
- 旧 `/rev` 任何 artifact
- `/Users/praise/.claude/**`
- 其他 step 的 owned_paths

---

## 9. 风险与防护

| 风险 | 防护 |
|------|------|

---

## 10. 测试计划

```bash
# 每条命令必须可执行
```

---

## 11. Assumptions

- <已确认前提>
