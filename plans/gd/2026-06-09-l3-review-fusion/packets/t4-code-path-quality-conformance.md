# Task Packet: t4-code-path-quality-conformance

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t4-code-path-quality-conformance
agent_role: child_executor
parent_step: step-4
parent_track_id: t4-code-path
parent_dispatch_id: l3-review-fusion
parent_plan: plans/gd/2026-06-09-l3-review-fusion/master-plan.md
created_at: 2026-06-09T00:00:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，降低填表式计划与执行遗漏风险（引用 GOAL_SOURCE）
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准（引用 GOAL_SOURCE）
PHASE_GOAL:   把 L2 已验证收敛机制融合进 L3 review，质量/符合性分离，零破坏治理 gate（引用 master plan）
TASK_GOAL:    在 gd-review-router.py 的 code/执行路实现质量/符合性分离两段闭环：(1) 先经 /code-review + /simplify 上游门——任一不可用或非成功 → fail-closed（记录可验证输出，不静默放行）；(2) 再进 Codex conformance loop（复用 t3 经 bridge 的收敛机制，Codex 主审「执行结果/已实现功能是否符合计划 SC」，代码顺带看）。两步产物可分别观测。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t2-bridge                       # bridge 是 step-2/3/4 共享 chokepoint，必须先于本 task 定稿 lens/conformance scoping 接口
can_parallel_with:
  - t3-review-plan                  # owned_paths 不重叠（merge-and-fix-loop.py vs review-router.py），均 blocked_by t2-bridge，可并行
required_context:
  - specs/l3-review-fusion/spec.md
  - docs/constitution.md
  - plans/gd/2026-06-09-l3-review-fusion/master-plan.md
  - scripts/gd-review-router.py     # 唯一要改的文件；现状权威源

# 跨 track 依赖（只调用、不修改，本 task 不拥有这些文件）：
#   - scripts/gd-codex-bridge-review.py        # t2 owned。经 subprocess 调 run-bridge --live-transport / parse-transport（kind=execution_outcome|combined）做 conformance cross-review。lens/conformance scoping/穷举本体由 t2 落实。
#   - scripts/gd-review-merge-and-fix-loop.py  # t3 owned。收敛机制本体由 t3 提供；本 task 在 conformance loop 经 subprocess 复用，不在 router 内重写。
#   - scripts/gd-validate-execution-outcome.py # 已存在不改；router 既有 code/执行路已调它做 Stage-1 outcome 校验，沿用。
```

> 注：`scripts/gd-codex-transport-guard.py`（t1 产出）是 prevention 四道防线本体；本 task 不直接调用它，transport prevention 由 suite-controller / bridge 层承担，本 task 只需在 router 对「bridge 返回 transport_failed」做既有 fail-closed 处置。

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-review-router.py
forbidden_paths:
  - "/Users/praise/.claude/**"
  - scripts/gd-codex-transport-guard.py
  - scripts/gd-review-suite-controller.py
  - scripts/gd-codex-bridge-review.py
  - prompts/gd-review-standard.md
  - scripts/gd-review-merge-and-fix-loop.py
  - tests/review-fusion
  - fixtures/review-fusion
  - .deploy-manifest.jsonl
  - baselines/gd-v7-runtime-write-authorizations.jsonl
  - 旧 /rev artifacts
```

读写权限分层：

- **写入**：仅限 `scripts/gd-review-router.py`。写入其他路径（尤其 bridge / merge-and-fix-loop / prompt / `/Users/praise/.claude/**`）视为越界，[P1] 阻断。
- **读取**：允许 `required_context` 列出文件 + 已完成 `blocked_by`（t2-bridge）的 deliverables（bridge 定稿后 CLI 契约）+ 公共只读资源。`gd-review-merge-and-fix-loop.py` 与 `gd-validate-execution-outcome.py` 作为被调用脚本的 CLI 契约可只读参考。

---

## 5. 成功标准（SC）

> 绑定 master SC-5（fail-closed 不降级）与 SC-6（质量/符合性分离）。下列 SC-1/SC-2 为 task 级可验证条件，分别映射 master SC-5 / SC-6。

- [ ] SC-1（↔ master SC-5，fail-closed 不降级）：code/执行路 handler 中 `/code-review` + `/simplify` 上游门「任一不可用或非成功」时 **MUST** 走 fail-closed 分支——写 route_report（`decision` 非 `APPROVED`，带可验证 `failure_code`，如 `UPSTREAM_QUALITY_GATE_FAIL` / `CODE_REVIEW_UNAVAILABLE` / `SIMPLIFY_UNAVAILABLE`），记录上游门可验证输出（命令/退出码/stdout 摘要 + hash 落盘），且 `exit≠0`；**MUST NOT** 静默放行、**MUST NOT** 仅凭 outcome/Claude 出 `APPROVED`。源码含可静态检索的 `fail_closed` 标识。
- [ ] SC-2（↔ master SC-6，质量/符合性分离）：code/执行路 **MUST 先**经 `/code-review`（找 bug）+ `/simplify`（清理）上游门，**再**进 Codex conformance cross-review；两段产物在 route_report 中可分别观测（上游质量门有独立字段/落盘产物，Codex conformance 判定独立于质量门）；调 bridge 时 Codex 任务 **MUST** 被收窄为 conformance（核对是否符合计划 SC）而非地毯式找 bug。源码含可静态检索的 `conformance` 与 `code-review`/`simplify` 标识。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-review-router.py
    kind: file
    must_exist: true
    description: 在 code/执行路三个 handler（_run_live_execution_only / _run_live_code_only / _run_live_execution_plus_code）插入 /code-review + /simplify 上游质量门 + fail-closed 处置，并把后续 Codex cross-review 收窄为 conformance。
```

---

## 7. HOW（基于 gd-review-router.py 真实状态机）

> 定位基于当前结构，落地以源码实际行为为准（行号可能因前序改动微移）。

**状态机入口**：`run_live()`（约 L1007）按 `detect_review_target_kind()` 分发 5 类。code/执行相关三个 handler：
1. `_run_live_execution_only()`（约 L559，kind=`execution_only_no_code`）：现状 Stage-1 `gd-validate-execution-outcome.py`（`returncode!=0`→`REQUIRES_CHANGES`+`OUTCOME_VALIDATOR_FAIL`+exit 1）；Stage-2 bridge（`_run_live_codex_bridge(kind="execution_outcome")`）cross-review；`APPROVED` 当且仅当 outcome 通过且 codex `completed`+`APPROVED`。
2. `_run_live_code_only()`（约 L761，kind=`code_only`）：现状仅 `git diff HEAD` 落盘 + `LOCAL_STATIC_ONLY`，固定 `REQUIRES_CHANGES`。
3. `_run_live_execution_plus_code()`（约 L821，kind=`execution_plus_code`）：现状 outcome-first（失败→`OUTCOME_FIRST_FAIL` exit 1），通过后 Stage-2 bridge（`kind="combined"`）。

**改动 1 — 插入 /code-review + /simplify 上游门**：新增 helper（如 `_run_upstream_quality_gate(target, output_dir, invocation_id)`），在 outcome 校验通过后、bridge cross-review 之前执行。三 handler 接入点：`execution_only_no_code` Stage-1 通过后；`execution_plus_code` outcome-first 通过后、`combined` bridge 之前；`code_only` 现有 diff 落盘后、决策返回前（保留 `LOCAL_STATIC_ONLY` 语义，不伪造 active Codex code sidecar）。helper 经 subprocess 触发 `/code-review`（找 bug）+ `/simplify`（清理）；先探测可用性（dry probe / which / 约定 launcher 退出码），把每步命令行/退出码/stdout 摘要写 route_report 独立字段（如 `upstream_quality_gate.steps[]`：`step`/`status`/`exit_code`/`output_ref`/`output_hash`），产物落盘 `output_dir`（`quality_gate_code_review_<iid>.log` / `quality_gate_simplify_<iid>.log`）以满足「可分别观测」。

**改动 2 — fail-closed 判「非成功」（SC-1/master SC-5）**：上游门「任一不可用或非成功」（探测不可用 / subprocess 非零 / 约定失败标记）→ 短路 fail-closed：写 route_report，`decision` 非 `APPROVED`（`REQUIRES_CHANGES` 或 `FAILED`），`failure_code` 用可静态检索枚举（`UPSTREAM_QUALITY_GATE_FAIL` / `CODE_REVIEW_UNAVAILABLE` / `SIMPLIFY_UNAVAILABLE`），`findings` 含 `reviewer=quality_gate severity=error`+失败描述，保留可验证输出（命令/退出码/output_ref/hash），`exit≠0`。**MUST NOT** 在质量门未成功时进入 Codex cross-review，**MUST NOT** 静默放行。该分支须含字面 `fail_closed`（下划线标识，表达本 task 新增的上游门 fail-closed 语义）。复用现有 `write_and_validate_route_report()` 落盘 + SSOT 校验，保持 Q2 validator_signature 不变。

**改动 3 — Codex 收窄为 conformance（SC-2/master SC-6）**：上游门成功后才进既有 bridge cross-review。router 侧显式标 conformance：report 增 `codex_review_scope="conformance"`，findings 注释 Codex 主审「是否符合计划 SC、代码顺带看、不地毯式找 bug」。**lens emphasis / conformance scoping / 穷举强制的提示词与 capsule 本体由 t2 在 bridge + prompt 落实**；本 task 不改 bridge，只确保 (a) 质量门先行、(b) 进入 bridge 的 cross-review 标注/约束为 conformance、(c) report 字段使 conformance 判定与质量门产物可分别观测。源码须含字面 `conformance` 与对 `code-review`/`simplify` 的可检索引用。

**改动 4 — conformance loop 复用 t3 收敛机制（跨 track 依赖）**：需修复时进有界修复循环（spec US2 AS-3）。收敛本体由 t3 在 `gd-review-merge-and-fix-loop.py` 提供。复用方式 = 与现有 `_run_live_plan_review()`（约 L294）相同的 subprocess 模式：`subprocess.run([sys.executable, str(loop_script), ...], env={**os.environ, INVOCATION_ID_ENV: invocation_id})`，把 loop 写出的 `loop_report_*.json` 的 `gd_review_decision` 回填 route_report。**MUST NOT** 在 router 内重写收敛逻辑、**MUST NOT** 改 `gd-review-merge-and-fix-loop.py`。若 t3 loop 接口在 code/执行 kind 下尚未就绪，本 task 仅保证 router 侧调用点 + conformance 收窄字段就位（接口对齐由 wave 顺序保证）。

**不变量（零破坏，P3/P4）**：保留 `_write_execution_review_ledger()`（stage=`review_execution_code`，child_agent_count=2）、`write_and_validate_route_report()` SSOT 校验与 `validator_signature`、Q3 side-door env 检查、并发 ≤2、bridge `transport_failed`→`CODEX_TRANSPORT_UNAVAILABLE` 既有 fail-closed 处置一律不动。新增上游门字段以增量方式加入 report，不删既有字段。

**上游门 self-test 契约（供 verify SC-1-behavior 使用）**：router 须支持 `--self-test` flag（或检测 `GD_SELF_TEST=1` env）；进入 self-test 时：(1) 注入 stub 上游门（`/code-review` stub 返回 exit≠0 / 不可用），(2) 调 `_run_upstream_quality_gate` 并断言返回 fail-closed 路径（route_report `failure_code` 为 `CODE_REVIEW_UNAVAILABLE` 或 `UPSTREAM_QUALITY_GATE_FAIL`，`decision` 非 `APPROVED`），(3) 全部断言通过则 stdout 打印 `SELF_TEST: PASS`，任一失败则打印 `SELF_TEST: FAILED:<reason>` 并 exit≠0。这是 SC-1 的唯一可执行行为验证，不可仅用 grep 替代。

---

## 8. 验证（Anti-fill 硬约束）

> 权威 verify 来自 dispatch-map，原样使用。**注意**：SC-5 的 grep token `fail.closed|fail_closed` 中 `.` 会匹配现有注释里的 `fail-closed` 连字符（当前文件已命中多行），故该 grep 在改动前即已 PASS——子 agent **MUST NOT** 把「grep PASS」当 SC-1 完成证据；SC-1 实质完成 = 上游质量门非成功时确有 fail-closed 短路分支（含字面 `fail_closed` 下划线 + 非 APPROVED + exit≠0 + 可验证输出落盘）。验证：SC-5 第一条 verify 为 subprocess 可执行场景（模拟 `/code-review` 不可用，断言 router exit≠0 且含 `fail_closed` 分支）。grep 断言为辅助静态检查，不可单独作为完成证据。

```yaml
verify:
  - sc_ref: SC-1
    method: command
    cmd: "grep -qE 'UPSTREAM_QUALITY_GATE_FAIL|CODE_REVIEW_UNAVAILABLE|SIMPLIFY_UNAVAILABLE' scripts/gd-review-router.py && grep -q 'fail_closed' scripts/gd-review-router.py && grep -q 'upstream_quality_gate' scripts/gd-review-router.py && echo PASS"
    expect: "PASS"
    note: "原 expect 为 'exit!=0' 是错误的——grep 串联成功时命令 exit=0 并 echo PASS；上游门非成功 fail-closed 的行为验证由下方 --self-test 覆盖，此条为静态存在性检查。"
  - sc_ref: SC-1-behavior
    method: command
    cmd: "python3 scripts/gd-review-router.py --self-test 2>&1 | grep -E 'SELF_TEST|fail_closed|UPSTREAM_QUALITY_GATE' | head -5"
    expect: "SELF_TEST: PASS"
    note: "--self-test 模式须模拟 /code-review 不可用场景，断言 router exit≠0 且 report 含 fail_closed 分支与 failure_code。self-test 的可调用契约：router 检测 GD_SELF_TEST=1 env 或 --self-test flag，注入 stub 上游门（返回非零），验证 fail-closed 短路路径，最终打印 SELF_TEST: PASS 或 SELF_TEST: FAILED:<reason>。"
  - sc_ref: SC-5
    method: assertion
    cmd: "grep -c 'fail_closed' scripts/gd-review-router.py"
    expect: ">=2"
    note: ">=2 确保 fail_closed 既在 _run_upstream_quality_gate 的判断分支中出现，又在写 route_report 的字段/注释中出现，不仅是单点字面量。"
  - sc_ref: SC-6
    method: command
    cmd: "grep -q 'conformance' scripts/gd-review-router.py && grep -q 'code-review' scripts/gd-review-router.py && grep -q 'simplify' scripts/gd-review-router.py && grep -q 'upstream_quality_gate' scripts/gd-review-router.py && grep -q 'codex_review_scope' scripts/gd-review-router.py && echo PASS"
    expect: "PASS"
  - sc_ref: SC-6
    method: assertion
    cmd: "grep -c 'conformance' scripts/gd-review-router.py"
    expect: ">=1"
  - sc_ref: SC-5
    method: command
    cmd: "python3 scripts/gd-review-router.py --self-test; echo rc=$?"
    expect: "SELF_TEST: PASS"
    note: "完整 self-test 输出须含 SELF_TEST: PASS（stdout 最终行）；rc= 行为辅助信息。若 self-test 未实装，此条判 FAILED，不得视为 pass。"
```

---

## 9. Handoff 输出

```yaml
handoff_output:
  result_path: <子 agent 写入 execution result 的相对路径>
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论>
  blockers: <未完成的依赖或外部阻塞，例如 t2-bridge 的 conformance scoping 接口或 t3-loop 的 code/执行 kind 契约未就绪>
```

---

## 10. 范围禁令

- 禁止 **写入** 除 `scripts/gd-review-router.py` 外任何路径；尤其禁改 bridge / merge-and-fix-loop / prompt / transport-guard / suite-controller / tests / fixtures / manifest / ledger。
- 收敛机制本体由 t3 提供：本 task 只在 router 接入两段门 + conformance 收窄 + 经 subprocess 复用 t3 loop，**不在 router 内重写收敛逻辑**。
- 禁止访问 `/Users/praise/.claude/**`；禁止 daemon/hook/cron；禁止用对话上下文替代 required_context；不自动 commit/push。
