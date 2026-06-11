# Task Packet: gd-plugin-install-readme

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> 自包含合约：本 packet 必须能被子 agent 单独执行；禁止「见上文 / 按之前讨论 / 参考会话上下文」。

## 1. 标识

```yaml
task_id: gd-plugin-install-readme
agent_role: implementer
parent_step: step-a-plugin-surface
parent_plan: plans/gd/2026-06-11-plugin-packaging/track-a/step-plan.md
created_at: 2026-06-11T00:00:00Z
```

## 2. 目标链

```text
PROJECT_GOAL: <ref Project GD/docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref Project GD/docs/gd-v7-project-goal.md §1>
PHASE_GOAL:   把 /review1 /review2 /gd 三命令封装为可分发 macOS 插件（传输栈前置分两段、更新可控、范围诚实）
TASK_GOAL:    写安装 README（.claude-plugin/README.md）——【第 0 步前提】仅 macOS + 私有 GitLab 访问权；【第 1 段】一行装插件命令 + 一次 reload；【第 2 段】codex 传输栈三件套前置；【更新段】手动更新 ≤3 命令 + 传输层改动加 install-transport.sh；显式不宣称「一条命令即得完整功能」
```

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with:
  - gd-plugin-scaffold-manifests
  - gd-plugin-setup-command
required_context:
  - specs/gd-plugin-packaging/spec.md
  - docs/constitution-plugin.md
  - vendor/l3-transport/README.md
```

## 4. 路径权限

```yaml
owned_paths:
  - .claude-plugin/README.md
forbidden_paths:
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json
  - commands/setup.md
  - scripts/gd-plugin-setup.sh
  - commands/gd.md
  - commands/review1.md
  - commands/review2.md
  - "vendor/l3-transport/**"
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
```

读写权限分层：写入仅限 owned_paths；读取限 required_context（spec/constitution/vendor README 提供传输栈三件套事实）+ 公共只读资源。

## 5. 成功标准（SC）

- [ ] SC-009：README 用两个固定 marker `<!-- gd-install-section -->`（安装段）与 `<!-- gd-transport-prereq-section -->`（传输栈前置段）分段且不混淆；三件套（① codex CLI+认证 ② 安装者自备 key 官方/第三方 ③ install-transport.sh）**只出现在前置段**；仅 macOS + 私有 GitLab 访问权列为第 0 步前提；无「一条命令即得完整功能」措辞。
- [ ] SC-001（本 packet 分担：README 侧单行命令文本）：安装段含单行 `claude plugin marketplace add … && claude plugin install …@…` 与一次 reload 步骤。
- [ ] SC-005：README 用 marker `<!-- gd-update-commands:start -->` … `<!-- gd-update-commands:end -->` 包裹手动更新命令块，块内命令数 ≤3（marketplace update → plugin update → reload）+ 块外注明传输层改动加 install-transport.sh。

## 6. 交付物

```yaml
deliverables:
  - path: .claude-plugin/README.md
    kind: file
    must_exist: true
    description: 两段式安装/前置/更新文档，含第 0 步前提与范围诚实声明
```

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-009
    method: command
    cmd: "f=.claude-plugin/README.md; grep -q '<!-- gd-install-section -->' \"$f\" && grep -q '<!-- gd-transport-prereq-section -->' \"$f\" && awk '/<!-- gd-transport-prereq-section -->/{x=1} x' \"$f\" | grep -q 'codex CLI' && awk '/<!-- gd-transport-prereq-section -->/{x=1} x' \"$f\" | grep -q 'install-transport.sh' && ! (awk '/<!-- gd-install-section -->/{x=1} /<!-- gd-transport-prereq-section -->/{x=0} x' \"$f\" | grep -q 'install-transport.sh') && grep -Eq 'macOS' \"$f\" && grep -Eq 'GitLab' \"$f\" && ! grep -Eq '一条命令.*完整功能|一行.*即得.*完整' \"$f\" && echo PASS"
    expect: "PASS"
  - sc_ref: SC-001
    method: command
    cmd: "awk '/<!-- gd-install-section -->/{x=1} /<!-- gd-transport-prereq-section -->/{x=0} x' .claude-plugin/README.md | grep -Eq 'claude plugin marketplace add .+&&.+claude plugin install .+@' && grep -Eq 'reload|重启|restart' .claude-plugin/README.md && echo PASS"
    expect: "PASS"
  - sc_ref: SC-005
    method: command
    cmd: "f=.claude-plugin/README.md; test \"$(awk '/<!-- gd-update-commands:start -->/{x=1;next} /<!-- gd-update-commands:end -->/{x=0} x' \"$f\" | grep -cE '^[[:space:]]*(claude|/)')\" -le 3 && grep -q 'marketplace update' \"$f\" && grep -q 'plugin update' \"$f\" && grep -q 'install-transport.sh' \"$f\" && echo PASS"
    expect: "PASS"
```

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-plugin-install-readme-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论>
  blockers: <未完成的依赖或外部阻塞>
```

## 9. 范围禁令

- 禁止写入其他 task 的 owned_paths（plugin.json / marketplace.json / setup.md / setup 脚本）。
- 禁止改 commands/gd.md / review1.md / review2.md / vendor/l3-transport/**。
- 禁止访问 /Users/praise/.claude/**。
- 禁止启动 daemon、注册 hook、修改 cron / LaunchAgent。
- 禁止在 README 宣称「复制一条命令即得三链路完整功能」。
- 禁止用对话上下文替代 required_context。
