# Task Packet: t6-fix-bridge-target

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t6-fix-bridge-target
agent_role: implementer
parent_step: T6
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T00:00:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表
CHAIN_GOAL:   让 L2(/review2)成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交
PHASE_GOAL:   为 L2 spec T1-T9 各产出一份自包含、可被 /gd execute 消费的 task packet（本 packet 对应 T6）
TASK_GOAL:    修 bridge build_capsule_text + cmd_run_bridge，使 code/执行结果路与 plan 路对称——
              真实 diff / 执行结果产物当 PRIMARY_TARGET、L2 capsule 降为 RELATED_CONTEXT，
              REVIEW_FOCUS 按 kind 动态生成（去掉写死的 "bridge candidate review of"）；
              并 trace router 对 combined/execution_outcome 的 target 传递、把结果写进 reports/，
              若同病（target 指向 capsule 而非真 artifact）一并修，不推迟（堵 H9）。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t1-exhaustive-and-dual-codex      # T1 也改 gd-codex-bridge-review.py:build_capsule_text（新增 REVIEW_LENS_EMPHASIS 字段 + 穷举强制指令）；T6 须在其后落地，避免对同一函数的并发编辑冲突
can_parallel_with:
  - t5                                # T5 改 commands/review2.md 入口解析 + 判定脚本，与 T6 的 scripts/ 文件不重叠
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md   # §1 F2/F3（现状缺陷证据）、§2.3 按 kind 分容表（目标态）、§3 T6 段、§5 边界
```

> 读取前置依赖产物的合法性（§4）：`t1-exhaustive-and-dual-codex` 完成后，其对 `scripts/gd-codex-bridge-review.py` 的改动已落在同一文件中，本 packet 在该基础上继续编辑同一文件，属合法续写（同一 owned_path 由依赖顺序串行化，非越界）。

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-codex-bridge-review.py   # build_capsule_text(922-1072) + cmd_run_bridge(1177-1215) + 必要的 helper（如 _get_title_by_kind / 新增 focus/primary-target 派生函数）
  - scripts/gd-review-router.py         # 仅限 execution_outcome/combined 的 target 传递 trace + 写 reports/（_run_live_bridge 区域：438/468/628/886 行附近的 --target 传参链路）
forbidden_paths:
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
  - commands/review2.md                 # 属 T5/T7 owned
  - prompts/gd-review-standard.md        # 属 T1 owned
  - scripts/gd-review-controller.py      # T7 新建，未完成
  - schema/gd-baseline-findings.schema.json  # T7 新建，未完成
  - <任何其他 task 的 owned_paths>
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（上述两个 `.py`）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取 `required_context` 列出的 spec 文件、`blocked_by`（T1）已落在 `gd-codex-bridge-review.py` 的改动、以及公共只读资源（`prompts/gd-review-standard.md`、`templates/`、`schema/`、goal 文件）。

---

## 5. 成功标准（SC）

对应 master plan SC-6。每条 SC 绑可执行 verify（见 §7）。

- [ ] SC-6.1：`build_capsule_text` 中写死的 `REVIEW_FOCUS: bridge candidate review of {target.name}`（现 999 行）消失或被按 kind 动态生成的 focus 取代。新 focus 须按 §2.3 分容表对 4 个 kind 给出不同语义：`plan`=审计划完整性+anti-fill；`code_diff`=质量已由 /code-review 处理，只验 conformance；`execution_outcome`=只验执行结果 vs 计划 SC；`combined`=conformance（质量上游已处理）。`grep -n 'bridge candidate' scripts/gd-codex-bridge-review.py` 不再命中含 `REVIEW_FOCUS` 的写死行（写死的 USER_ACCEPTED_DECISIONS / KNOWN_LIMITATIONS / PLAN_REVIEW_ALIGNMENT 等 "bridge candidate" 残留同步清理或动态化，至少 REVIEW_FOCUS 行必须动态化）。
- [ ] SC-6.2：`PRIMARY_TARGET` 按 kind 与 target_role 分容——`code_diff` 与 `combined` 的 capsule `PRIMARY_TARGET` 指向真实 diff 产物，`execution_outcome` 指向执行结果产物，`plan` 指向原始计划文件；三档的 `PRIMARY_TARGET` 行均**不**指向 `capsule.md`（信封）。L2 capsule 上下文降为 `RELATED_CONTEXT` 的 path/hash 摘要，不再被当作 PRIMARY_TARGET 全文审。
- [ ] SC-6.3：code/执行结果路与 plan 路对称——存在与 plan 路 `cmd_run_bridge`(1199-1209) 等价的守卫或断言，使 `code_diff`/`execution_outcome`/`combined` 的 target 在 capsule 信封（filename==`capsule.md`）时被拒或被纠正为真 artifact，而非沉默写入坏 PRIMARY_TARGET。
- [ ] SC-6.4（堵 H9，同病一并修）：trace `gd-review-router.py` 对 `combined`/`execution_outcome` 的 target 传递链路（`--target str(target)` 传给 bridge 的 `_run_live_bridge` / 438·468·628·886 行附近），确认 router 解析出的 `target` 是真实执行产物/diff 而非 capsule；trace 结果（含每条 `--target` 传参点、解析来源、是否指向真 artifact 的判定）写入 `reports/t6-router-target-trace.md`（明确产出，不留"再决定"）。若 trace 发现 router 自身把 capsule 当 target 传下去，在本 T6 内一并修 router 传参，不推迟到 T7。
- [ ] SC-6.5（回归不破）：现有 bridge 单测/校验链对 `plan` kind 行为不变——`plan` 路仍把原始计划当 PRIMARY_TARGET，`cmd_run_bridge` 的 `PLAN_TARGET_MUST_BE_ORIGINAL_PLAN` 守卫仍生效；bridge 模块可正常 import、build_capsule_text 对 4 个 kind 均能产出 capsule（不抛 ValueError）。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-codex-bridge-review.py
    kind: file
    must_exist: true
    description: build_capsule_text 的 REVIEW_FOCUS 与 PRIMARY_TARGET 按 kind/role 分容；新增 code/执行结果路对称守卫
  - path: scripts/gd-review-router.py
    kind: file
    must_exist: true
    description: execution_outcome/combined 的 target 传递经 trace 确认指向真 artifact；如有同病则修传参
  - path: reports/t6-router-target-trace.md
    kind: report
    must_exist: true
    description: router target 传递 trace 结论（每条 --target 传参点 + 解析来源 + 是否真 artifact 判定 + 是否需修）
```

> `reports/t6-router-target-trace.md` 的写入归属：reports/ 为本 packet 显式产出目录，写该 trace 报告属本任务交付物，不视为越界。

---

## 7. 验证（Anti-fill 硬约束）

> 每条 verify 含命令 / 路径 / 断言 / 测试之一；断言 PRIMARY_TARGET 非 capsule.md 是核心防线。

```yaml
verify:
  - sc_ref: SC-6.1
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE 'REVIEW_FOCUS:.*bridge candidate' scripts/gd-codex-bridge-review.py | wc -l"
    expect: "0"
  - sc_ref: SC-6.1
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 -c \"import importlib.util,pathlib; s=importlib.util.spec_from_file_location('b','scripts/gd-codex-bridge-review.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); import tempfile,os; d=tempfile.mkdtemp(); t=pathlib.Path(d)/'diff.patch'; t.write_text('SC-1 dummy'); foci={k: m.build_capsule_text(k, t, pathlib.Path(d))[0].split(chr(10))[1] for k in ['plan','code_diff','execution_outcome','combined']}; print(len(set(foci.values())))\""
    expect: ">=3"
  - sc_ref: SC-6.2
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 -c \"import importlib.util,pathlib,tempfile; s=importlib.util.spec_from_file_location('b','scripts/gd-codex-bridge-review.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); d=tempfile.mkdtemp(); t=pathlib.Path(d)/'diff.patch'; t.write_text('SC-1 dummy'); cap=m.build_capsule_text('code_diff', t, pathlib.Path(d))[0]; pt=[l for l in cap.splitlines() if l.startswith('PRIMARY_TARGET:')][0]; assert 'capsule.md' not in pt, pt; print('PASS')\""
    expect: "PASS"
  - sc_ref: SC-6.3
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE 'capsule|CAPSULE_TARGET_FORBIDDEN|capsule\\.md' scripts/gd-codex-bridge-review.py | grep -iE 'code_diff|execution_outcome|combined|EXECUTION_KINDS|forbidden' | wc -l"
    expect: ">=1"
  - sc_ref: SC-6.4
    method: path
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && test -f reports/t6-router-target-trace.md && grep -cE '438|468|628|886|--target' reports/t6-router-target-trace.md"
    expect: ">=1"
  - sc_ref: SC-6.5
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 -c \"import importlib.util,pathlib,tempfile; s=importlib.util.spec_from_file_location('b','scripts/gd-codex-bridge-review.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); d=tempfile.mkdtemp(); p=pathlib.Path(d)/'plan.md'; p.write_text('SC-1 x'); cap=m.build_capsule_text('plan', p, pathlib.Path(d))[0]; pt=[l for l in cap.splitlines() if l.startswith('PRIMARY_TARGET:')][0]; assert str(p.resolve()) in pt, pt; print('PASS')\""
    expect: "PASS"
```

> 注：SC-6.2 / SC-6.5 的断言对 `build_capsule_text` 的调用签名以现状（`kind, target, cwd, ...` 关键字参数）为准；T1 若新增 `REVIEW_LENS_EMPHASIS` 相关入参须为可选（带默认值），否则本断言需相应补默认实参——实现时以 T1 落地后的真实签名调整调用，但**断言核心（PRIMARY_TARGET 非 capsule.md、4 kind focus 各异）不可弱化**。

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t6-fix-bridge-target-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论：bridge 三档 PRIMARY_TARGET 已指真 artifact、focus 按 kind 动态化、router target trace 已写 reports/>
  blockers: <未完成的依赖或外部阻塞，例如 T1 未落地导致 build_capsule_text 签名未定>
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 task 的 `owned_paths`（`commands/review2.md`、`prompts/gd-review-standard.md`、`scripts/gd-review-controller.py`、`schema/gd-baseline-findings.schema.json` 等）
- 禁止 **读取** 未完成 task 的 `owned_paths`，除非该 task 已完成且其 deliverables 列入 `required_context`
- 禁止访问 `/Users/praise/.claude/**`
- 禁止启动 daemon、注册 hook、修改 cron
- 禁止用对话上下文替代 `required_context`
- 不改 L3 `/gd review` 语义、不动旧 `/review`/`/rev`/`codex-watch` daemon（守 spec §5 边界）
- 不在 `/review2` 输出裸 `VERDICT:`（用 `REV_VERDICT`/`GD_REVIEW_DECISION`，避免触发 live hook regex）
- anti-fill：SC 与 verify 禁止用"完善/优化/系统性/全面/增强"占位；每条 SC 必带可执行断言
```
