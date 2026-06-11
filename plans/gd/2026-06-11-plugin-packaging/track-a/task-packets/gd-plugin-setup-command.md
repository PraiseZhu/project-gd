# Task Packet: gd-plugin-setup-command

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> 自包含合约：本 packet 必须能被子 agent 单独执行；禁止「见上文 / 按之前讨论 / 参考会话上下文」。

## 1. 标识

```yaml
task_id: gd-plugin-setup-command
agent_role: implementer
parent_step: step-a-plugin-surface
parent_plan: plans/gd/2026-06-11-plugin-packaging/track-a/step-plan.md
created_at: 2026-06-11T00:00:00Z
```

## 2. 目标链

```text
PROJECT_GOAL: <ref Project GD/docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref Project GD/docs/gd-v7-project-goal.md §1>
PHASE_GOAL:   把 /review1 /review2 /gd 三命令封装为可分发 macOS 插件（setup 选项制预设、零 pip、零内置 key）
TASK_GOAL:    建与三链路并列的 setup 命令（commands/setup.md）+ 选项制持久化脚本（scripts/gd-plugin-setup.sh，bash/stdlib）——收 4 字段（审查产物输出位置/codex key 官方+第三方两类/codex 模型/模型强度 effort）全选项制、存 ${CLAUDE_PLUGIN_DATA}、可重跑改任一项、零内置默认 key；HANDOFF_ROOT 不进预设
```

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with:
  - gd-plugin-scaffold-manifests
  - gd-plugin-install-readme
required_context:
  - specs/gd-plugin-packaging/spec.md
  - docs/constitution-plugin.md
  - commands/gd.md
```

## 4. 路径权限

```yaml
owned_paths:
  - commands/setup.md
  - scripts/gd-plugin-setup.sh
forbidden_paths:
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json
  - .claude-plugin/README.md
  - commands/gd.md
  - commands/review1.md
  - commands/review2.md
  - "vendor/l3-transport/**"
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
```

读写权限分层：写入仅限 owned_paths；读取限 required_context（commands/gd.md 仅作 frontmatter 形态只读对齐）+ 公共只读资源。

## 5. 成功标准（SC）

- [ ] SC-010：setup 命令与三链路并列（commands/setup.md frontmatter 形态与 gd.md 一致），脚本收 4 字段全选项制（自由填字段=0）、codex key 覆盖官方+第三方两类、持久化到 ${CLAUDE_PLUGIN_DATA}、可重跑改任一项、零内置默认 key；HANDOFF_ROOT 不进预设。
- [ ] SC-008（本 packet 分担：setup 侧）：setup 脚本与命令文件不要求 pip install 任何第三方包，不含明文 key。

## 6. 交付物

```yaml
deliverables:
  - path: commands/setup.md
    kind: file
    must_exist: true
    description: setup 命令，frontmatter 与三链路并列，正文呈现 4 选项制字段并调用持久化脚本
  - path: scripts/gd-plugin-setup.sh
    kind: file
    must_exist: true
    description: bash/stdlib 选项制持久化脚本，含 --self-check 只读自检子命令
```

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-010
    method: command
    cmd: "head -3 commands/setup.md | grep -q '^---' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FIELDS=4' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FREEFORM=0' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'KEY_TYPES=2' && bash scripts/gd-plugin-setup.sh --self-check | grep -Eq 'PERSIST=.*CLAUDE_PLUGIN_DATA' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'BUILTIN_KEY=0' && echo PASS"
    expect: "PASS"
  - sc_ref: SC-008
    method: command
    cmd: "! grep -rEn 'pip install|pip3 install' scripts/gd-plugin-setup.sh commands/setup.md && ! grep -rEn 'sk-[A-Za-z0-9]{16,}' scripts/gd-plugin-setup.sh commands/setup.md && echo PASS"
    expect: "PASS"
```

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-plugin-setup-command-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论>
  blockers: <未完成的依赖或外部阻塞>
```

## 9. 范围禁令

- 禁止写入其他 task 的 owned_paths（plugin.json / marketplace.json / README）。
- 禁止改 commands/gd.md / review1.md / review2.md / vendor/l3-transport/**。
- 禁止把 HANDOFF_ROOT 列入 setup 预设字段。
- 禁止在脚本内置任何默认 codex key 或明文 key。
- 禁止要求安装者 pip install 任何第三方包。
- 禁止访问 /Users/praise/.claude/**；禁止启动 daemon、注册 hook、launchctl setenv。
- 禁止用对话上下文替代 required_context。
