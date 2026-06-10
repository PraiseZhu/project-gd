# Task Packet: t1-transport-guard

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t1-transport-guard
agent_role: implementer
parent_step: step-1
parent_track_id: t1-transport
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
TASK_GOAL:    新建 scripts/gd-codex-transport-guard.py 实现 transport prevention 四道防线（派发前 preflight 探活 / 瞬时失败 bounded 重试 / 充足 timeout / healthcheck，全为确定性代码非提示词），并在 gd-review-suite-controller.py 派双 codex 前接入探活点；任一 codex 经四道防线仍不可用 → fail-closed 阻断（不降级、不以「存活视角+Claude」凑数）。
```

---

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with: []
required_context:
  - specs/l3-review-fusion/spec.md
  - docs/constitution.md
  - plans/gd/2026-06-09-l3-review-fusion/master-plan.md

# 依赖说明：t1 无前置依赖（dispatch-map wave w1 首位执行）。SC-5 的 pytest -k fail_closed/retry_recover
# 需要 t5 提供 fixture，但这是 post-t5 集成 gate，不是执行前置条件。t1 完成后该 verify 条处于
# pending 状态，待 t5 就位后方可跑通。原 blocked_by:[t5-regression] 与 dispatch-map 冲突形成
# 执行环，已按 dispatch-map 修正（w1=t1[]→w2=t2[t1]→w3=t3/t4[t2]→w4=t5[t3,t4]→w5=t6[t5]）。
```

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-codex-transport-guard.py
  - scripts/gd-review-suite-controller.py
forbidden_paths:
  - "/Users/praise/.claude/**"
  - scripts/gd-codex-bridge-review.py
  - prompts/gd-review-standard.md
  - scripts/gd-review-merge-and-fix-loop.py
  - scripts/gd-review-router.py
  - tests/review-fusion
  - fixtures/review-fusion
  - .deploy-manifest.jsonl
  - baselines/gd-v7-runtime-write-authorizations.jsonl
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（仅 `gd-codex-transport-guard.py` 新建 + `gd-review-suite-controller.py` 接入探活点）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取 (1) `required_context` 列出的文件；(2) 公共只读资源（PROJECT_GOAL.md、shared core、schema）。`tests/review-fusion` 与 `fixtures/review-fusion` 由 t5 owned，本任务**不写不建**，仅在 §7 verify 中引用其将提供的测试 id。

---

## 5. 成功标准（SC）

- [ ] SC-1：transport prevention 层落成——新建 `scripts/gd-codex-transport-guard.py`，含确定性（非提示词）的重试逻辑（标识符 `retry` 或 `MAX_RETR*` 常量），且 `gd-review-suite-controller.py` 在派双 codex 前调用该 guard 的探活函数。可验证条件：`test -f scripts/gd-codex-transport-guard.py && grep -qE 'retry|MAX_RETR' scripts/gd-codex-transport-guard.py && echo PASS` 输出 `PASS`。
- [ ] SC-5：fail-closed 不降级——单 codex 经 preflight + bounded 重试仍不可用 → guard 返回 fail-closed 信号，controller 据此写阻断态（不以「存活视角 + Claude」凑数、不仅凭 Claude 放行）；注入一次瞬时失败后 bounded 重试使该 codex 恢复、review 正常进行（不误入 fail-closed）。可验证条件：自包含 verify（`python3 -c` 直接 import guard 验证 preflight_probe / probe_with_retry / healthcheck 三函数存在）输出 `PASS`；集成验证 `python3 -m pytest tests/review-fusion -k 'fail_closed or retry_recover'` 由 t5 fixture 提供后跑通（末行 `passed`）。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-codex-transport-guard.py
    kind: file
    must_exist: true
    description: transport prevention 四道防线模块（preflight 探活 / bounded 重试 / timeout 配置 / healthcheck 兜底），暴露供 controller 调用的探活入口函数，返回结构化可用/不可用判定（fail-closed 信号）。
  - path: scripts/gd-review-suite-controller.py
    kind: file
    must_exist: true
    description: 在派双 codex bridge 前接入 guard 探活点的修订版（仅新增前置探活分支，不改既有 dual-gate / ledger / report 语义）。
```

---

## 7. 验证（Anti-fill 硬约束）

> SC-5 的 pytest 依赖 `tests/review-fusion`（t5 owned）。本 packet **不创建**该目录；SC-5 的 verify 由 t5 提供 fixture（`fail_closed` / `retry_recover` 测试 id）后方可跑通。在 t5 完成前，本任务以 deliverable 文件结构 + guard 函数契约（preflight/retry/timeout/healthcheck 四道防线签名）自证。

```yaml
verify:
  - sc_ref: SC-1
    method: command
    cmd: "test -f scripts/gd-codex-transport-guard.py && grep -qE 'retry|MAX_RETR' scripts/gd-codex-transport-guard.py && grep -qE 'ensure_codex_available' scripts/gd-codex-transport-guard.py && grep -qE 'ensure_codex_available|transport_guard' scripts/gd-review-suite-controller.py && echo PASS"
    expect: "PASS"
    note: "第一个 grep 验 guard 文件存在且含重试逻辑；第二个 grep 验 guard 文件本身暴露 ensure_codex_available 入口函数；第三个 grep 验 controller 已调用该入口（引用函数名）。三条串联确保接入点与入口函数均落地，不仅是字面量存在。"
  - sc_ref: SC-1-healthcheck-callpath
    method: assertion
    cmd: "grep -c 'healthcheck' scripts/gd-codex-transport-guard.py"
    expect: ">=2"
    note: ">=2 确保 healthcheck 既有定义行又有被 ensure_codex_available 调用行，排除仅定义未调用的空验证。"
  - sc_ref: SC-5
    method: command
    cmd: "python3 -c \"exec('''import importlib.util, sys, types; spec=importlib.util.spec_from_file_location(\\'guard\\',\\'scripts/gd-codex-transport-guard.py\\'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); preflight=getattr(m,\\'preflight_probe\\',None); retry=getattr(m,\\'probe_with_retry\\',None); hc=getattr(m,\\'healthcheck\\',None); to=getattr(m,\\'PROBE_TIMEOUT_SEC\\',None); assert callable(preflight) and callable(retry) and callable(hc), \\'missing functions\\'; assert isinstance(to,(int,float)), \\'missing PROBE_TIMEOUT_SEC\\'; r1=retry(preflight_fn=lambda t: types.SimpleNamespace(returncode=1,stdout=\\'\\',stderr=\\'\\'), max_retries=1); assert r1.get(\\'available\\')==False and r1.get(\\'fail_closed\\')==True, f\\'fail_closed FAILED: {r1}\\'; call_count=[0]; def transient_fn(t): call_count[0]+=1; return types.SimpleNamespace(returncode=0,stdout=\\'ok\\',stderr=\\'\\') if call_count[0]>1 else types.SimpleNamespace(returncode=1,stdout=\\'\\',stderr=\\'\\'); r2=retry(preflight_fn=transient_fn, max_retries=2); assert r2.get(\\'available\\')==True, f\\'retry_recover FAILED: {r2}\\'; print(\\'PASS\\')\\'\'\')\""
    expect: "PASS"
    note: "直接 import guard 模块做行为验证：fail_closed 路径返回 available=False + fail_closed=True；transient stub 首失败后恢复返回 available=True。这是可执行的函数契约验证，非仅字面量检查。"
  - sc_ref: SC-5
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'fail_closed or retry_recover' -q 2>&1 | tail -1"
    expect: "passed"
    note: "pytest 集成验证由 t5 fixture 提供；t5 完成前此条处于 pending 状态（t1 自证依赖上方 python3 -c 行为验证）。"
```

---

## HOW（实现细节，基于已读真实代码结构）

**四道防线 → 具体函数 / 确定性手段（全在新文件 `scripts/gd-codex-transport-guard.py`，stdlib-only，与现有 controller / bridge 同风格）：**

1. **派发前 preflight 探活** —— 函数 `preflight_probe(timeout_sec) -> ProbeResult`：用 `subprocess.run` 对 codex transport 做一次轻量存活探测（无副作用调用，不投真审查 capsule），`capture_output=True, text=True, timeout=...`，按 returncode + stdout 标志判定 `available / unavailable`。这是确定性代码，不是提示词。
2. **瞬时失败 bounded 重试** —— 模块级常量 `MAX_RETRIES`（建议 2）+ `RETRY_BACKOFF_SEC`，函数 `probe_with_retry(...)`：判定为瞬时失败（returncode≠0 但非永久错误）时循环重试至上限；上限内恢复 → `available`（支撑 SC-5 的 `retry_recover`）；耗尽仍失败 → `unavailable`（支撑 SC-5 的 `fail_closed`，**绝不**返回降级 available）。
3. **充足 timeout** —— guard 暴露 `PROBE_TIMEOUT_SEC` 默认值（探活短超时，与 bridge writer 的 `--writer-timeout-sec` 默认 600 解耦）；timeout 触发 → 计为本次探测失败进入重试逻辑，而非静默放行。
4. **healthcheck 兜底** —— 函数 `healthcheck() -> bool`：在 preflight 通过、重试恢复后做一次最终健康确认，作为派发前最后一道闸；任一 codex healthcheck 不过 → fail-closed。

**guard 对外契约（供 controller 消费）**：暴露单一入口（如 `ensure_codex_available(...) -> dict`），返回 `{"available": bool, "outcome": "...", "fail_closed": bool}`；不可用时 `outcome` 取 `codex_transport_unavailable`，对齐宪法 P4 与现有 controller `BLOCKING_BUCKETS` 中的 `transport_failed` / `preflight_failed` 桶语义。

**在 `gd-review-suite-controller.py` 的接入点**：现有 live 派发链是 `main()` → `_run_live_targets(args, out_dir)` → 对每个 target `executor.submit(_dispatch_one_bridge, ...)`，`_dispatch_one_bridge` 构造 `bridge_cmd` 并 `_run_subprocess(bridge_cmd, ...)` 真正派 codex。接入做法：在 `_run_live_targets` 提交 bridge future **之前**（ThreadPoolExecutor 提交循环前，复用现有 `if not fixture_mode` + `args.live_transport` 分支位置；preflight master-plan 一致性检查之后、dispatch 之前）调用 `transport_guard.ensure_codex_available(...)`：

- 探活通过 → 照常进入现有 `_run_live_targets` 派双 codex（不改 dual-gate / ledger / report 任何逻辑）。
- 探活 fail-closed → **不提交** bridge future，复用现有 `_write_controller_report(...)` 写 `aggregate_bucket=transport_failed`（或新增 `preflight_failed`）阻断 job，`primary_verdict=FAILED`、`exit≠0`，与现有 PREFLIGHT_FAILED 早退分支同构。fixture 模式（`args.fixture`）不触发 guard，保持现有 fixture 测试不破。

**约束**：只在「派发前」加一道前置探活分支 + 失败早退；**不改** `_primary_gate` / `_secondary_gate` / 三遍 batch-ledger 回填 / controller-report schema / `--max-parallel` 上限（仍 ≤2）等既有治理逻辑，确保 SC-7 零破坏（由 t5 回归覆盖）。

---

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/review-fusion/t1-transport-guard-execution-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: guard 四道防线落成 + controller 探活点接入；SC-5 pytest 待 t5 fixture
  blockers: SC-5 的 tests/review-fusion 测试由 t5 提供，本任务完成后该 verify 方可端到端跑通
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 track 的 `owned_paths`（含 `gd-codex-bridge-review.py`、`gd-review-router.py`、`gd-review-merge-and-fix-loop.py`、`tests/review-fusion`、`fixtures/review-fusion`、`.deploy-manifest.jsonl` 等）。
- 禁止 **读取** 其他 track 的 `owned_paths`，本任务 `required_context` 已限定为 spec / constitution / master-plan / controller 四份。
- 禁止访问 `/Users/praise/.claude/**`。
- 禁止启动 daemon、注册 hook、修改 cron。
- transport prevention 四道防线 MUST 为确定性代码，禁止以提示词实现（宪法规则5 / FR-008）。
- 任一 codex 经四道防线仍不可用 → fail-closed，禁止降级为「存活视角 + Claude」或「仅 Claude 放行」（宪法 P4 / FR-008 / SC-007）。
