# Task Packet: <task_id>

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: <kebab-case 唯一 id>
agent_role: <子 agent 角色，例如 implementer | researcher | validator>
parent_step: <step id>
parent_plan: <plan 文件相对路径>
created_at: <YYYY-MM-DDTHH:MM:SSZ>
```

---

## 2. 目标链

```text
PROJECT_GOAL: <ref GOAL_SOURCE>
CHAIN_GOAL:   <ref GOAL_SOURCE>
PHASE_GOAL:   <ref master plan>
TASK_GOAL:    <本 task packet 的最小可验证目标>
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - <task_id 或 step_id>            # 必须先完成的 task；为空时写空数组
can_parallel_with:
  - <task_id>                       # 可与本任务并行的 task；为空时写空数组
required_context:
  - <相对路径>                       # 本任务执行所需读取的文件清单（限定范围，避免漫读）
```

---

## 4. 路径权限

```yaml
owned_paths:
  - <相对路径>                       # 本任务唯一允许 **写入** 的路径
forbidden_paths:
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
  - <未完成 / 未列入 required_context / 越界的其他 task 的 owned_paths>
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取以下三类，超出此范围视为越界：
  1. `required_context` 列出的文件（依赖 / 上下文输入）
  2. **已完成的 `blocked_by` task 的 deliverables**（合法的前置依赖产物，例如 task A 完成后 task B 可读 A 的 deliverables）
  3. 公共只读资源（PROJECT_GOAL.md、shared core、lock files、schema）

不在以上三类范围的其他 task 的 `owned_paths`（未完成、未列入 required_context）禁止读取。

---

## 5. 成功标准（SC）

- [ ] SC-1：<具体可验证条件，含命令 / 路径 / 输出断言之一>
- [ ] SC-2：<...>

---

## 6. 交付物

```yaml
deliverables:
  - path: <相对路径>
    kind: file | directory | report
    must_exist: true
    description: <一句话说明>
```

---

## 7. 验证（Anti-fill 硬约束）

> `verify` 字段是 anti-fill 的核心防线：必须含**命令 / 路径 / 输出断言 / 测试用例之一**。
> 禁止仅写"目视确认 / 检查一下 / 看看是否正确"作为唯一内容。
> 写不出可执行 verify 的 SC 不得进入本 packet。

```yaml
verify:
  - sc_ref: SC-1
    method: command            # command | path | assertion | test
    cmd: "test -f <path> && echo PASS"
    expect: "PASS"
  - sc_ref: SC-2
    method: assertion
    cmd: "grep -c '<token>' <file>"
    expect: ">=1"
```

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: <子 agent 写入 execution result 的相对路径>
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论>
  blockers: <未完成的依赖或外部阻塞>
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 task 的 `owned_paths`（任何场景）
- 禁止 **读取** 其他 task 的 `owned_paths`，**除非** 该 task 已完成且其 deliverables 列入本 packet 的 `required_context`（详见 §4 读取权限分层）
- 禁止访问 `/Users/praise/.claude/**`
- 禁止启动 daemon、注册 hook、修改 cron
- 禁止用对话上下文替代 `required_context`
