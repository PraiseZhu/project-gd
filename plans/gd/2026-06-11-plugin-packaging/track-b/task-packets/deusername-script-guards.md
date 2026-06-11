# Task Packet: deusername-script-guards

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> 自包含合约：本 packet 必须能被子 agent 单独执行；禁止「见上文 / 按之前讨论 / 参考会话上下文」。
> round-5 新增：SC-007 scan 扩到 scripts 后，照出 validator/bridge 脚本里硬编码的 `/Users/praise/.claude` protected-runtime 守卫需脱用户名（否则在安装者机器上守卫永不命中、保护失效）。

## 1. 标识

```yaml
task_id: deusername-script-guards
agent_role: implementer
parent_step: step-b-portability-isolation
parent_plan: plans/gd/2026-06-11-plugin-packaging/track-b/step-plan.md
created_at: 2026-06-11T00:00:00Z
```

## 2. 目标链

```text
PROJECT_GOAL: <ref docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref docs/gd-v7-project-goal.md — shared core / review contract>
PHASE_GOAL:   把三链路封装为零开发者硬编码路径的可分发 macOS 插件
TASK_GOAL:    把 5 个 validator/bridge 脚本里硬编码的 /Users/praise/.claude protected-runtime 守卫改为运行时解析安装者 HOME（expanduser("~/.claude") / Path.home()），保留拒绝语义，使守卫在安装者机器真正生效
```

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with:
  - zero-out-command-paths
  - isolate-transport-and-writes
required_context:
  - docs/constitution-plugin.md
  - specs/gd-plugin-packaging/spec.md
```

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-validate-dispatch.py
  - scripts/gd-validate-execution-batch.py
  - scripts/gd-validate-master-plan-consistency.py
  - scripts/gd-validate-child-proposal.py
  - scripts/gd-codex-bridge-review.py
forbidden_paths:
  - "commands/**"
  - "vendor/l3-transport/**"
  - ".claude-plugin/**"
  - "tests/**"
  - scripts/gd-bundle-completeness.sh
  - scripts/gd-plugin-setup.sh
  - "/Users/praise/.claude/**"
```

## 5. 成功标准（SC）

- [ ] SC-007：5 个脚本内 `/Users/praise/(AI-Agent|.claude)` 命中 = 0；守卫改用 `os.path.expanduser("~/.claude")` / `Path.home()/".claude"` 解析安装者 HOME，拒绝「写 <安装者HOME>/.claude」的语义不丢失。
- [ ] 守卫语义保留：脚本既有 self-test / 校验行为不被破坏（抽查 self-test 仍跑通）。

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-validate-dispatch.py
    kind: file
    must_exist: true
    description: is_under_protected_runtime 守卫脱用户名为 expanduser("~/.claude")
  - path: scripts/gd-validate-execution-batch.py
    kind: file
    must_exist: true
  - path: scripts/gd-validate-master-plan-consistency.py
    kind: file
    must_exist: true
  - path: scripts/gd-validate-child-proposal.py
    kind: file
    must_exist: true
  - path: scripts/gd-codex-bridge-review.py
    kind: file
    must_exist: true
```

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-007
    method: command
    cmd: "! grep -rEnI '/Users/praise/(AI-Agent|\\.claude)' scripts/gd-validate-dispatch.py scripts/gd-validate-execution-batch.py scripts/gd-validate-master-plan-consistency.py scripts/gd-validate-child-proposal.py scripts/gd-codex-bridge-review.py && echo PASS"
    expect: "PASS（5 脚本零命中）"
  - sc_ref: SC-007
    method: command
    cmd: "python3 scripts/gd-validate-dispatch.py --self-test >/dev/null 2>&1 || python3 scripts/gd-validate-child-proposal.py --self-test >/dev/null 2>&1; echo GUARD_INTACT"
    expect: "GUARD_INTACT（守卫语义未破坏，self-test 可跑）"
```

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-track-b-deusername-script-guards-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: 5 个 validator/bridge 脚本 protected-runtime 守卫脱用户名，拒绝语义保留
  blockers: <无则 none>
```

## 9. 范围禁令

- 仅改守卫的「用户名解析」（`/Users/praise/.claude` → `expanduser("~/.claude")`），禁止改其拒绝逻辑/校验语义。
- 禁止写入 commands / vendor/l3-transport / tests / 其他 task 的 owned_paths。
- P3 作废的 install-gd-command.sh / uninstall-gd-command.sh / install-review-route-command.sh / check-gd-command-parity.sh **不入 bundle、不在本 task 范围**（由 bundle-completeness 断言不被打包）。
- 禁止访问 `/Users/praise/.claude/**`（写入）；禁止用对话上下文替代 required_context。
```
