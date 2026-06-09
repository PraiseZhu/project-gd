# Task Packet: t2-dryrun-gate

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t2-dryrun-gate
agent_role: implementer
parent_step: T2
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T15:03:29Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表（ref GOAL_SOURCE）
CHAIN_GOAL:   让 L2(/review2) 成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交（ref master plan §1）
PHASE_GOAL:   实现并部署 L2 spec T1-T9，使 /review2 plan 与 /review2 code 两入口端到端可用（ref master plan §1）
TASK_GOAL:    在 /review2 code 送 Codex 之前增设一道"本地跑通(含 fallback / 无 API key)证据"硬门——
              证据文件缺失时 preflight 脚本 exit≠0 并打印 DRYRUN_EVIDENCE_MISSING，阻止把"未本地验证过的代码"送进交叉审查；
              证据齐备时放行。门只挂 code 路，不挂 plan 路（计划阶段无代码可跑）。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t5-split-commands-triage        # T2 挂 code 路；本门写在 /review2 code 送审前编排层，需 T5 先把 `/review2 code` 子命令入口与三档判定建立，否则无 code 路可挂
can_parallel_with:
  - t4                              # T4（anti-fill 硬门 + Stop hook）与本任务无文件交集（T4 owned scripts/gd-validate-review2-plan-target.py + hook；本任务 owned commands/review2.md + scripts/gd-review2-preflight.sh），可并行
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md   # 唯一上下文：读 §3 T2 段（门定义/exit 码/WHY）、§1 F7（token 黑洞是轮数）、§4 依赖图 T2 归位（挂 code 路非 plan 路）
```

> **blocked_by 读取说明**：T5 完成后，本任务可读 T5 deliverable `commands/review2.md` 中已建立的 `/review2 code` 子命令编排段（合法前置依赖产物），把本门接到 code 路送审前。`commands/review2.md` 同时是本任务 owned_paths 之一（追加 preflight 调用编排），属共享编辑文件——本任务只在 code 路送审前新增"调用 preflight + 失败即停"段落，不改 T5 已写的三档判定逻辑。

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-review2-preflight.sh       # 新建：dry-run 证据 preflight 脚本
  # commands/review2.md 由 t5 owned（t5 创建该文件）；本任务在 blocked_by t5 完成后对 code 路送审前段追加内容，
  # deliverables 中说明"追加 preflight gate 段到 T5 owned commands/review2.md"，不重复声明 owned_paths。
forbidden_paths:
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
  - prompts/gd-review-standard.md                          # T1 owned
  - scripts/gd-codex-bridge-review.py                      # T1/T6 owned
  - scripts/gd-validate-review2-plan-target.py             # T4 owned
  - scripts/plan-mode-antifill-stop-hook.js                # T4 owned
  - templates/plan-mode-template.md                        # T3 owned
  - scripts/gd-detect-review2-code-target.py               # T5 owned
  - scripts/gd-review-router.py                            # T6/T7 owned
  - scripts/gd-review-controller.py                        # T7 owned
  - schema/gd-baseline-findings.schema.json                # T7 owned
  - scripts/gd-review2-package-deliverable.sh              # T8 owned
  - .deploy-manifest.jsonl                                 # T9 owned
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（`commands/review2.md` 仅限 code 路送审前 gate 段、`scripts/gd-review2-preflight.sh` 全文）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取以下三类，超出此范围视为越界：
  1. `required_context` 列出的文件（即 `docs/2026-06-07-l2-review-workflow-redesign-spec.md`）
  2. 已完成的 `blocked_by` task（t5-split-commands-triage）的 deliverable `commands/review2.md`（code 路子命令编排段，作为接入锚点）
  3. 公共只读资源（GOAL_SOURCE、`prompts/gd-review-standard.md` 作为标准引用、lock files、schema）

不在以上三类范围的其他 task 的 `owned_paths`（未完成、未列入 required_context）禁止读取。

---

## 5. 成功标准（SC）

> 对应 master plan SC-2 / spec T2。

- [ ] SC-2a：`scripts/gd-review2-preflight.sh` 存在且可执行（`chmod +x`），接受 `--evidence <path>` 指定证据文件路径，默认探测 `results/review-route-split/dryrun-evidence.json`（或同等约定路径，脚本内 header 注释写明）。
- [ ] SC-2b：证据文件**缺失**时，运行 `bash scripts/gd-review2-preflight.sh`（不带证据）→ exit code 非零（约定 exit 3）且 stdout/stderr 含字面串 `DRYRUN_EVIDENCE_MISSING`，不进入送审。
- [ ] SC-2c：证据文件**存在且声明所有生产路径（含 fallback / 无 API key 分支）已本地跑通**（最小判据：文件存在 + 含字段 `paths_exercised` 非空数组 + 含 `fallback_no_api_key: true`/等价标记）时，运行 preflight → exit 0 且打印 `DRYRUN_EVIDENCE_OK`，放行送审。
- [ ] SC-2d：`commands/review2.md` 的 `/review2 code` 送 Codex 前编排明确记录"先跑 `scripts/gd-review2-preflight.sh`，exit≠0(`DRYRUN_EVIDENCE_MISSING`) 则停、不送 Codex"，且文档说明该门**只挂 code 路、不挂 plan 路**。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-review2-preflight.sh
    kind: file
    must_exist: true
    description: dry-run 证据 preflight 门脚本——无证据 exit≠0 + DRYRUN_EVIDENCE_MISSING，有合规证据 exit 0 + DRYRUN_EVIDENCE_OK
  - path: commands/review2.md
    kind: file
    must_exist: true
    description: 在 /review2 code 送 Codex 前编排层新增 preflight gate 段，记录失败即停语义与"只挂 code 路"边界
```

---

## 7. 验证（Anti-fill 硬约束）

> `verify` 字段是 anti-fill 的核心防线：必须含**命令 / 路径 / 输出断言 / 测试用例之一**。
> 下列 cmd 均为可直接 `bash` 执行的真实命令；exit-code 断言用 `test $? ...` 表达，无证据路径用临时目录隔离。

```yaml
verify:
  - sc_ref: SC-2a
    method: command
    cmd: "test -x scripts/gd-review2-preflight.sh && echo EXECUTABLE"
    expect: "EXECUTABLE"
  - sc_ref: SC-2b
    method: test
    cmd: "rm -f /tmp/gd-t2-nonexistent-evidence.json; bash scripts/gd-review2-preflight.sh --evidence /tmp/gd-t2-nonexistent-evidence.json >/tmp/gd-t2-out.log 2>&1; rc=$?; grep -q DRYRUN_EVIDENCE_MISSING /tmp/gd-t2-out.log && test $rc -ne 0 && echo MISSING_BLOCKED"
    expect: "MISSING_BLOCKED"
  - sc_ref: SC-2c
    method: test
    cmd: "printf '{\"paths_exercised\":[\"main\",\"fallback\"],\"fallback_no_api_key\":true}' > /tmp/gd-t2-evidence.json; bash scripts/gd-review2-preflight.sh --evidence /tmp/gd-t2-evidence.json >/tmp/gd-t2-ok.log 2>&1; rc=$?; grep -q DRYRUN_EVIDENCE_OK /tmp/gd-t2-ok.log && test $rc -eq 0 && echo OK_PASSED"
    expect: "OK_PASSED"
  - sc_ref: SC-2d
    method: assertion
    cmd: "grep -cE 'gd-review2-preflight\\.sh|DRYRUN_EVIDENCE_MISSING' commands/review2.md"
    expect: ">=1"
```

> **master plan SC-2 顶层验收**（无证据时门必须拒审）：
> `cmd: "bash scripts/gd-review2-preflight.sh; test $? -ne 0"` —— 不带证据参数时脚本探测不到默认证据文件，必须返回非零退出码（拒审）。该命令是 master SC-2 的可执行绑定。

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t2-dryrun-gate-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论：preflight 门是否建立、无证据是否拒审、是否接入 code 路送审前>
  blockers: <未完成的依赖或外部阻塞；若 T5 未提供 code 路入口，记录为 blocker>
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 task 的 `owned_paths`（任何场景）；尤其不得改 `scripts/gd-codex-bridge-review.py`、`scripts/gd-validate-review2-plan-target.py`、`scripts/gd-detect-review2-code-target.py`、`scripts/gd-review-controller.py`
- 禁止把门挂到 plan 路（`/review2 plan`）——计划阶段无代码可跑，挂错会拦截正常计划审查（spec §4 已将 T2 修正为 code 路，不在 plan 档）
- 禁止 **读取** 其他 task 的 `owned_paths`，**除非** 该 task 已完成且其 deliverables 列入本 packet 的 `required_context`（本任务仅依赖 t5 的 `commands/review2.md` code 路段）
- 禁止访问 `/Users/praise/.claude/**`
- 禁止启动 daemon、注册 hook、修改 cron、调用真实 Codex/外部网络（preflight 只读本地证据文件，不发送任何审查）
- 禁止在 preflight 内自动生成或伪造证据文件——门只校验证据存在与合规，不代跑（spec T2 WHY：本地跑一次即可拦，不该让 Codex 替跑，也不该让门替跑）
- 禁止用对话上下文替代 `required_context`
```