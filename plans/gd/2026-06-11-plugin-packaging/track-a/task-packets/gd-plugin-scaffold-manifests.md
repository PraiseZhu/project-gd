# Task Packet: gd-plugin-scaffold-manifests

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> 自包含合约：本 packet 必须能被子 agent 单独执行；禁止「见上文 / 按之前讨论 / 参考会话上下文」。

## 1. 标识

```yaml
task_id: gd-plugin-scaffold-manifests
agent_role: implementer
parent_step: step-a-plugin-surface
parent_plan: plans/gd/2026-06-11-plugin-packaging/track-a/step-plan.md
created_at: 2026-06-11T00:00:00Z
```

## 2. 目标链

```text
PROJECT_GOAL: <ref Project GD/docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref Project GD/docs/gd-v7-project-goal.md §1>
PHASE_GOAL:   把 /review1 /review2 /gd 三命令封装为可分发 macOS 插件（零硬编码路径、bundle 完整、setup 选项制预设）
TASK_GOAL:    建出 .claude-plugin/plugin.json（省略 version）与 .claude-plugin/marketplace.json（git-subdir 同仓布局），使 `claude plugin marketplace add <repo> && claude plugin install <plugin>@<mkt>` 单行命令注册并安装插件，三链路命令入口由 /plugin 机制接管
```

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with:
  - gd-plugin-install-readme
  - gd-plugin-setup-command
required_context:
  - specs/gd-plugin-packaging/spec.md
  - docs/constitution-plugin.md
  - commands/gd.md
```

## 4. 路径权限

```yaml
owned_paths:
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json
forbidden_paths:
  - commands/gd.md
  - commands/review1.md
  - commands/review2.md
  - "vendor/l3-transport/**"
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
  - commands/setup.md
  - scripts/gd-plugin-setup.sh
  - .claude-plugin/README.md
```

读写权限分层：写入仅限 owned_paths；读取限 required_context + 公共只读资源（spec/constitution/三链路命令文件作只读引用以对齐命令入口名）。

## 5. 成功标准（SC）

- [ ] SC-001（本 packet 分担：manifest 侧）：`plugin.json` 省略 version 且含 name + **三链路命令入口声明（review1/review2/gd）**；`marketplace.json` 是合法 JSON 且声明 git-subdir 插件条目，二者共同支撑单行 `marketplace add && plugin install` 且 reload 后命令可见。
- [ ] SC-008（本 packet 分担：清单侧）：两个清单文件不含任何 API key/密钥。

## 6. 交付物

```yaml
deliverables:
  - path: .claude-plugin/plugin.json
    kind: file
    must_exist: true
    description: 插件 manifest，省略 version（SHA 即版本），声明三链路 + setup 命令入口
  - path: .claude-plugin/marketplace.json
    kind: file
    must_exist: true
    description: marketplace 清单，git-subdir 同仓布局，列 gd 插件条目
```

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-001
    method: command
    cmd: "python3 -c \"import json;d=json.load(open('.claude-plugin/plugin.json'));assert 'version' not in d;assert 'name' in d;s=json.dumps(d);assert all(c in s for c in ['review1','review2','gd']);print('OK')\" && python3 -m json.tool .claude-plugin/marketplace.json >/dev/null && echo MKT_OK"
    expect: "OK 与 MKT_OK 均输出（退出 0）"
  - sc_ref: SC-008
    method: command
    cmd: "! grep -rEn 'sk-[A-Za-z0-9]{16,}|TAPTAP_API_KEY=[A-Za-z0-9]' .claude-plugin/plugin.json .claude-plugin/marketplace.json && echo NO_KEY"
    expect: "NO_KEY"
```

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-plugin-scaffold-manifests-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论>
  blockers: <未完成的依赖或外部阻塞>
```

## 9. 范围禁令

- 禁止写入其他 task 的 owned_paths（README / setup.md / setup 脚本）。
- 禁止改 commands/gd.md / review1.md / review2.md / vendor/l3-transport/**。
- 禁止访问 /Users/praise/.claude/**。
- 禁止启动 daemon、注册 hook、修改 cron / LaunchAgent。
- 禁止在 plugin.json 写入 version 字段（git SHA 即版本）。
- 禁止用对话上下文替代 required_context。
