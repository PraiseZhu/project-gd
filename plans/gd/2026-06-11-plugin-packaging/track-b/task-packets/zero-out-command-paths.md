# Task Packet: zero-out-command-paths

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> 自包含合约：本 packet 必须能被子 agent 单独执行；禁止「见上文 / 按之前讨论 / 参考会话上下文」。

## 1. 标识

```yaml
task_id: zero-out-command-paths
agent_role: implementer
parent_step: step-b-portability-isolation
parent_plan: plans/gd/2026-06-11-plugin-packaging/track-b/step-plan.md
created_at: 2026-06-11T00:00:00Z
```

## 2. 目标链

```text
PROJECT_GOAL: <ref docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref docs/gd-v7-project-goal.md — shared core 固定目标链/SC/review contract>
PHASE_GOAL:   把 /review1 /review2 /gd 三命令封装为零硬编码路径的可分发 macOS 插件
TASK_GOAL:    清零 commands/gd.md、review1.md、review2.md 中所有开发者机器专属绝对路径，框架内文件引用改用 ${CLAUDE_PLUGIN_ROOT}，path-traversal 守卫脱用户名为 ${HOME}，删除作废的 ~/.claude/commands 安装模型描述
```

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with:
  - isolate-transport-and-writes
required_context:
  # 应对 Codex round-3 P2 自循环：owned 的三命令文件不列入 required_context（读自己将改的 owned 文件是隐含行为）
  - docs/constitution-plugin.md
  - specs/gd-plugin-packaging/spec.md
```

## 4. 路径权限

```yaml
owned_paths:
  - commands/gd.md
  - commands/review1.md
  - commands/review2.md
forbidden_paths:
  - ".claude-plugin/**"
  - commands/setup.md
  - "vendor/l3-transport/**"
  - scripts/gd-bundle-completeness.sh
  - tests/gd-plugin-cross-dir-smoke.sh
  - "/Users/praise/.claude/**"
```

读写权限分层：写入仅限 owned_paths；读取限 required_context + 公共只读资源。

## 5. 成功标准（SC）

- [ ] SC-007：三命令文件中**不得残留任何 `/Users/praise/` 字面**（含 `/Users/praise/AI-Agent/...` 与 `/Users/praise/.claude`），框架内引用改为 `${CLAUDE_PLUGIN_ROOT}`。
- [ ] 守卫语义保留：gd.md 的 path-traversal 拒绝逻辑改写为 `${HOME}/.claude/**` 模式（脱用户名），拒绝行为不丢失——清零与守卫保留二者兼得。

## 6. 交付物

```yaml
deliverables:
  - path: commands/gd.md
    kind: file
    must_exist: true
    description: GD_PROJECT_ROOT/GD_STANDARD/GOAL_SOURCE 改 ${CLAUDE_PLUGIN_ROOT}；删旧 install/parity 描述；守卫脱用户名
  - path: commands/review1.md
    kind: file
    must_exist: true
    description: GD_ROOT 改 ${CLAUDE_PLUGIN_ROOT}
  - path: commands/review2.md
    kind: file
    must_exist: true
    description: 删除/改写 Installed copy 开发者绝对路径行（旧 installed-copy 模型作废）
```

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-007
    method: command
    cmd: "! grep -rEn '/Users/praise/(AI-Agent|\\.claude)' commands/gd.md commands/review1.md commands/review2.md && grep -q '${HOME}/.claude' commands/gd.md && echo PASS"
    expect: "PASS（应对 Codex round-3 P1：直接 fail on /Users/praise/(AI-Agent|.claude)，含 .claude 字面；不用 grep -v 排除；守卫已脱用户名 ${HOME}/.claude）"
  - sc_ref: SC-007
    method: assertion
    cmd: "grep -c 'CLAUDE_PLUGIN_ROOT' commands/gd.md"
    expect: ">=1"
```

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-track-b-zero-out-command-paths-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: 三命令文件开发者绝对路径清零、框架引用改 ${CLAUDE_PLUGIN_ROOT}、守卫脱用户名
  blockers: <未完成依赖或外部阻塞，无则 none>
```

## 9. 范围禁令

- 禁止写入 vendor/l3-transport/** 与两个 verifier 脚本（属其他 task）。
- 禁止改 `.claude-plugin/**` / commands/setup.md / setup 脚本（track-a）。
- 禁止删除 path-traversal 守卫逻辑（只脱用户名）。
- 禁止访问 `/Users/praise/.claude/**`（写入）。
- 禁止用对话上下文替代 required_context。
