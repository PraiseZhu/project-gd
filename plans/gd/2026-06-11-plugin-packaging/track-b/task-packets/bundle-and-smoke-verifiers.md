# Task Packet: bundle-and-smoke-verifiers

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> 自包含合约：本 packet 必须能被子 agent 单独执行；禁止「见上文 / 按之前讨论 / 参考会话上下文」。

## 1. 标识

```yaml
task_id: bundle-and-smoke-verifiers
agent_role: implementer
parent_step: step-b-portability-isolation
parent_plan: plans/gd/2026-06-11-plugin-packaging/track-b/step-plan.md
created_at: 2026-06-11T00:00:00Z
```

## 2. 目标链

```text
PROJECT_GOAL: <ref docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref docs/gd-v7-project-goal.md — shared core / review contract>
PHASE_GOAL:   bundle 完整性 + 跨目录冒烟证明的可分发 macOS 插件
TASK_GOAL:    建 scripts/gd-bundle-completeness.sh（八类目标 blocking 校验，含 vendor/l3-transport，拒作废安装脚本）与 tests/gd-plugin-cross-dir-smoke.sh（临时非 GD repo 跑 happy path，产物隔离断言，--no-codex fail-closed 断言）
```

## 3. 依赖与并发

```yaml
blocked_by:
  - zero-out-command-paths
  - isolate-transport-and-writes
  - deusername-script-guards
can_parallel_with: []
required_context:
  - commands/gd.md
  - vendor/l3-transport/handoff/lib/state-paths.sh
  - vendor/l3-transport/scripts/review-result-writer.sh
  - docs/constitution-plugin.md
  - specs/gd-plugin-packaging/spec.md
```

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-bundle-completeness.sh
  - tests/gd-plugin-cross-dir-smoke.sh
forbidden_paths:
  - commands/gd.md
  - commands/review1.md
  - commands/review2.md
  - "vendor/l3-transport/**"
  - ".claude-plugin/**"
  - commands/setup.md
  - "/Users/praise/.claude/**"
```

读写权限分层：写入仅限 owned_paths；读取限 required_context（含前两 task 已完成的 deliverables：三命令文件 + state-paths.sh + writer）+ 公共只读资源。

## 5. 成功标准（SC）

- [ ] SC-002：`gd-bundle-completeness.sh --check` 校验八类目标（commands 三文件 / scripts+lib / prompts / templates / schema / docs / fixtures / vendor/l3-transport 关键文件），健康仓 exit 0，缺漏 exit≠0 列出缺失项。
- [ ] SC-003：`gd-plugin-cross-dir-smoke.sh` 在 mktemp 临时非 GD git repo 跑 happy path，**用临时 ${HANDOFF_BIN} 下的 fixture `codex-send-wait`（可执行 stub，回写 VERDICT: APPROVED raw）真调 `review-result-writer.sh`，断言生成 result/baseline 实文件到 ${CLAUDE_PLUGIN_DATA}（test -f 实文件，禁止纯路径回显）**，exit 0，且不以 `$PWD`/`Project GD` 命中作为通过依据。
- [ ] SC-004：`--no-codex` 子模式断言 cross-review fail-closed、中文提示出现、产物区不含通过结论字样。
- [ ] SC-006：`--assert-data-isolated` 断言产物路径前缀 = `${CLAUDE_PLUGIN_DATA}` 或 `${CLAUDE_PROJECT_DIR}`，0 命中插件安装目录。
- [ ] SC-007（整分发物清单 sweep，t3 blocked_by t1+t2 故可见全部清零结果）：对 `commands/` + `scripts/` + `vendor/l3-transport/`（*.md/*.sh/*.py，按 spec 边界排除 docs/fixtures/mirrors/baselines/plans）整体零命中 `/Users/praise/(AI-Agent|.claude)`，且 gd.md 守卫已脱用户名 `${HOME}/.claude`。

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-bundle-completeness.sh
    kind: file
    must_exist: true
    description: 八类 bundle 目标 blocking 存在性校验 + 拒作废安装脚本（install-gd-command/uninstall/parity）
  - path: tests/gd-plugin-cross-dir-smoke.sh
    kind: file
    must_exist: true
    description: 临时非 GD repo 跨目录冒烟（fixture codex-send-wait 真调 writer 产出 ${CLAUDE_PLUGIN_DATA} 实文件，非回显）+ 产物隔离 + --no-codex fail-closed + --print-outdir/--assert-data-isolated 子开关
```

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-002
    method: command
    cmd: "bash scripts/gd-bundle-completeness.sh --check && echo PASS"
    expect: "PASS"
  - sc_ref: SC-003
    method: command
    cmd: "bash tests/gd-plugin-cross-dir-smoke.sh && echo PASS"
    expect: "PASS"
  - sc_ref: SC-004
    method: command
    cmd: "bash tests/gd-plugin-cross-dir-smoke.sh --no-codex && echo PASS"
    expect: "PASS"
  - sc_ref: SC-006
    method: command
    cmd: "bash tests/gd-plugin-cross-dir-smoke.sh --assert-data-isolated && echo PASS"
    expect: "PASS"
  - sc_ref: SC-007
    method: command
    cmd: "! grep -rEnI '/Users/praise/(AI-Agent|\\.claude)' commands scripts vendor/l3-transport --exclude='install-gd-command.sh' --exclude='uninstall-gd-command.sh' --exclude='install-review-route-command.sh' --exclude='check-gd-command-parity.sh' && grep -q '${HOME}/.claude' commands/gd.md && echo PASS"
    expect: "PASS（整分发物运行时清单全文件类型零命中含 bin/plist，排除 P3 作废脚本 + 守卫脱用户名）"
```

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-track-b-bundle-and-smoke-verifiers-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: bundle 完整性 blocking 校验脚本 + 跨目录冒烟脚本（含 no-codex fail-closed 与数据隔离断言）建成且本机跑通
  blockers: <无则 none>
```

## 9. 范围禁令

- 禁止写入三命令文件与 vendor/l3-transport/**（依赖前两 task 的产物，只读不写）。
- 禁止改 `.claude-plugin/**` / commands/setup.md / setup 脚本（track-a）。
- 冒烟脚本禁止以本仓自身目录自测断言为通过依据（FR-014）。
- 禁止启动 daemon、注册 hook、改 cron / LaunchAgent。
- 禁止访问 `/Users/praise/.claude/**`（写入）；禁止用对话上下文替代 required_context。
