# Execution Result: <task_id 或 step_id>

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-execution-result

> **本文件是执行结果工件**，不是 review 结果。**禁止**出现 `GD_REVIEW_DECISION:` 字段；执行状态用 `EXEC_STATUS:`。

---

## 1. 标识

```yaml
result_id: <kebab-case>
task_id: <对应 task packet>
parent_step: <step id>
parent_plan: <plan 文件相对路径>
executor_role: <claude_main | claude_subagent | codex>   # 必须用 schema 枚举值（snake_case 小写），见 schema/gd-execution-status.schema.json
executed_at: <YYYY-MM-DDTHH:MM:SSZ>
```

---

## 2. 执行状态（用 EXEC_STATUS，不用 VERDICT）

```text
EXEC_STATUS: completed | completed_with_constraint | blocked | failed
```

`EXEC_STATUS` 取值见 `schema/gd-execution-status.schema.json`。

---

## 3. SC 验收逐项

| sc_ref | 状态 | 证据（命令 / 路径 / 输出） | not_run_reason |
|--------|------|--------------------------|----------------|
| SC-1 | pass / fail / not_run / n_a | `<pass/fail 必填：命令输出或文件路径>` | `<not_run / n_a 必填：原因；pass/fail 留空>` |
| SC-2 | ... | ... | ... |

> 列填写规则：
> - `pass` / `fail` → **证据列必填**（可复现命令或文件路径），not_run_reason 留空
> - `not_run` / `n_a` → **not_run_reason 列必填**（说明为何未跑或不适用），证据列可留空
> - 任一行不满足上述规则视为 anti-fill 违规，review 中按规则 A 或 C [P1] / [P2] 阻断
> - schema 对应字段：`schema/gd-execution-status.schema.json` `sc_acceptance.items` 的 `evidence` / `not_run_reason`

---

## 4. 实际改动

```yaml
files_added:
  - <path>
files_modified:
  - <path>
files_unchanged_in_scope:
  - <path>            # owned_paths 内但本次未触及的文件，便于审计
```

---

## 5. 路径权限自检

```yaml
owned_paths_writes_only: true | false
forbidden_paths_touched: []
out_of_scope_writes: []
```

任一 `forbidden_paths_touched` / `out_of_scope_writes` 非空 → 必须降级 EXEC_STATUS。

---

## 6. Handoff Output

按 `gd-task-packet-template.md` 第 8 节合约填写：

```yaml
result_path: <本文件路径>
status_field: <EXEC_STATUS 值>
summary: <一句话结论>
blockers: <未完成依赖 / 外部阻塞 / 无 → none>
```

---

## 7. 已知局限 / 未执行项

- <KNOWN_LIMITATIONS 1>
- <未执行 SC 与原因>

---

## 8. Anti-fill 自查

- [ ] 没有用"完善 / 优化 / 系统性 / 全面 / 增强"作为唯一动作描述
- [ ] 每条 `pass` 都有对应可复现证据
- [ ] 未读取 `forbidden_paths`
- [ ] 未注册 hook / daemon / cron / slash command
