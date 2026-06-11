# Task Packet: isolate-transport-and-writes

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> 自包含合约：本 packet 必须能被子 agent 单独执行；禁止「见上文 / 按之前讨论 / 参考会话上下文」。

## 1. 标识

```yaml
task_id: isolate-transport-and-writes
agent_role: implementer
parent_step: step-b-portability-isolation
parent_plan: plans/gd/2026-06-11-plugin-packaging/track-b/step-plan.md
created_at: 2026-06-11T00:00:00Z
```

## 2. 目标链

```text
PROJECT_GOAL: <ref docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref docs/gd-v7-project-goal.md — shared core 固定目标链/review contract>
PHASE_GOAL:   传输栈前置分两段 + 运行时写入隔离的可分发 macOS 插件
TASK_GOAL:    把 HANDOFF_ROOT 解耦为插件管理/env 可覆盖/daemon↔client 一致（state-paths.sh = 唯一真源，install-transport.sh 改为 source 它）；把 writer 的 review-baselines/state 写产物与 codex-send-wait 解析迁到 ${CLAUDE_PLUGIN_DATA}/${HANDOFF_BIN}，缺 codex 时 fail-closed 给中文提示，保留 --out-dir/--baseline-key 覆写
```

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with:
  - zero-out-command-paths
required_context:
  # 应对 Codex round-3 P2 自循环：owned 的 state-paths.sh / review-result-writer.sh / install-transport.sh 不列入 required_context
  - vendor/l3-transport/README.md
  - .deploy-manifest.jsonl
  - docs/constitution-plugin.md
```

## 4. 路径权限

```yaml
owned_paths:
  - vendor/l3-transport/handoff/lib/state-paths.sh
  - vendor/l3-transport/scripts/review-result-writer.sh
  - vendor/l3-transport/scripts/install-transport.sh   # round-3：仅改 HANDOFF 解析 source state-paths.sh
  - vendor/l3-transport/scripts/codex-consult.sh        # round-5：L1 /review1 discuss HANDOFF 解耦
  - vendor/l3-transport/launchagents/com.praise.codex-watch.plist            # round-5：占位符化，由 install-transport 渲染
  - vendor/l3-transport/launchagents/com.praise.codex-watch-healthcheck.plist
forbidden_paths:
  - commands/gd.md
  - commands/review1.md
  - commands/review2.md
  - ".claude-plugin/**"
  - "scripts/gd-validate-*.py"
  - scripts/gd-bundle-completeness.sh
  - tests/gd-plugin-cross-dir-smoke.sh
  - "/Users/praise/.claude/**"
```

读写权限分层：写入仅限 owned_paths；读取限 required_context + 公共只读资源。

## 5. 成功标准（SC）

- [ ] SC-006：writer 写产物（baselines/state）默认解析到 `${CLAUDE_PLUGIN_DATA}`（fallback `${HOME}/.claude`），0 处直写插件安装目录；`--out-dir`/`--baseline-key` 覆写保留。
- [ ] SC-007 支撑（FR-016）：`HANDOFF_ROOT` 默认值脱开发者用户名、env `HANDOFF_ROOT` 可覆盖；`install-transport.sh` 改为 source 同一 `state-paths.sh` 取 HANDOFF，使 daemon↔client 两端恒等（round-3 按 Codex finding 写死，不再 defer）。
- [ ] SC-004 支撑：`review-result-writer.sh`（L3）与 `codex-consult.sh`（L1 /review1 discuss）均经 `${HANDOFF_BIN}/codex-send-wait` 解析；不可执行分支输出中文缺失提示。
- [ ] SC-007 支撑（plist）：2 个 launchagents plist 内 `/Users/praise` 字面 = 0（占位符化，由 install-transport.sh 按 state-paths.sh 解析值渲染；TAPTAP_API_KEY 仍 redact）。

## 6. 交付物

```yaml
deliverables:
  - path: vendor/l3-transport/handoff/lib/state-paths.sh
    kind: file
    must_exist: true
    description: HANDOFF_ROOT 默认改插件管理目录、保留 := env 覆盖、注释写明 daemon↔client 协调约定
  - path: vendor/l3-transport/scripts/review-result-writer.sh
    kind: file
    must_exist: true
    description: BASELINE_DIR/WRITER_MARKER_FILE 迁 ${CLAUDE_PLUGIN_DATA}；CODEX_BIN 经 ${HANDOFF_BIN}；缺 codex 中文 fail-closed 提示
  - path: vendor/l3-transport/scripts/install-transport.sh
    kind: file
    must_exist: true
    description: HANDOFF 解析改为 source 同一 state-paths.sh（仅改解析来源，不改部署动作语义）
```

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-006
    method: command
    cmd: "grep -nE '\\$HOME/\\.claude/(review-baselines|state)' vendor/l3-transport/scripts/review-result-writer.sh; test $? -ne 0 && echo PASS"
    expect: "PASS"
  - sc_ref: SC-007
    method: command
    cmd: "HANDOFF_ROOT=/tmp/h bash -c 'source vendor/l3-transport/handoff/lib/state-paths.sh; test \"$HANDOFF_ROOT\" = /tmp/h' && grep -q 'state-paths.sh' vendor/l3-transport/scripts/install-transport.sh && echo PASS"
    expect: "PASS"
  - sc_ref: SC-004
    method: assertion
    cmd: "grep -c 'HANDOFF_BIN' vendor/l3-transport/scripts/review-result-writer.sh"
    expect: ">=1"
  - sc_ref: SC-004
    method: command
    cmd: "grep -q 'HANDOFF_BIN' vendor/l3-transport/scripts/codex-consult.sh && ! grep -nE '\\$HOME/.claude/handoff/bin' vendor/l3-transport/scripts/codex-consult.sh && echo PASS"
    expect: "PASS（L1 codex-consult.sh 经 HANDOFF_BIN，无 $HOME/.claude/handoff 硬编码）"
  - sc_ref: SC-007
    method: command
    cmd: "! grep -rn '/Users/praise' vendor/l3-transport/launchagents/ && echo PASS"
    expect: "PASS（plist 已脱用户名/占位符化）"
```

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-track-b-isolate-transport-and-writes-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: HANDOFF_ROOT 插件管理可覆盖、writer 写产物隔离到 ${CLAUDE_PLUGIN_DATA}、codex-send-wait 经 HANDOFF_BIN
  blockers: <无则 none；若 install-transport.sh HANDOFF 解析不一致需移交 track-a>
```

## 9. 范围禁令

- 对 install-transport.sh **仅改 HANDOFF 解析来源**（source state-paths.sh），禁止改其装 daemon/plist 的部署动作语义、禁止运行它。
- 禁止写入三命令文件与两个 verifier 脚本（属其他 task）。
- 禁止删除 writer 的 `--out-dir`/`--baseline-key` 调用方覆写能力。
- 禁止启动 daemon、注册 LaunchAgent、跑 launchctl。
- 禁止访问 `/Users/praise/.claude/**`（写入）。
- 禁止用对话上下文替代 required_context。
