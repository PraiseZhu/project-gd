# Task Packet: t5-regression-fixtures

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t5-regression-fixtures
agent_role: implementer
parent_step: step-5
parent_track_id: t5-regression
parent_dispatch_id: l3-review-fusion
parent_plan: plans/gd/2026-06-09-l3-review-fusion/master-plan.md
created_at: 2026-06-09T00:00:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，降低填表式计划与执行遗漏风险（引用 GOAL_SOURCE，不重写）
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准（引用 GOAL_SOURCE，不重写）
PHASE_GOAL:   把 L2 已验证收敛机制融合进 L3 review，质量/符合性分离，零破坏治理 gate（引用 master plan §1 PHASE_GOAL）
TASK_GOAL:    在 tests/review-fusion 建覆盖 t1-t4 SC 的 pytest 回归套件（transport 四道防线 / union_baseline / r2 收窄 / convergence + convergence_timeout / fail_closed / 质量符合性分离 + bridge_contract），并在 fixtures/review-fusion 造 controller-report / stage-dispatch-ledger / execution-batch 三个治理 validator 的 regression fixtures，使 SC-4 / SC-5 / SC-7 命令全绿。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t3-review-plan        # 提供 scripts/gd-review-merge-and-fix-loop.py（convergence/convergence_timeout/union_baseline/r2 收窄 被测对象）
  - t4-code-path          # 提供 scripts/gd-review-router.py（fail_closed / 质量符合性分离 被测对象）
can_parallel_with: []
required_context:
  - specs/l3-review-fusion/spec.md
  - plans/gd/2026-06-09-l3-review-fusion/master-plan.md
  - docs/constitution.md
  - templates/gd-task-packet-template.md
  - scripts/gd-validate-controller-report.py
  - scripts/gd-validate-stage-dispatch-ledger.py
  - scripts/gd-validate-execution-batch.py
  - scripts/gd-validate-dispatch.py
```

> 被测脚本（`gd-codex-transport-guard.py` / `gd-codex-bridge-review.py` / `gd-review-merge-and-fix-loop.py` / `gd-review-router.py` / `gd-review-suite-controller.py`）由 t1-t4 owned，**本 task 只通过 subprocess / import 调用，绝不修改、绝不写入**。就位由 blocked_by 保证；读其源码用于编写断言属 §4 读取权限分层第 2 类。

---

## 4. 路径权限

```yaml
owned_paths:
  - tests/review-fusion
  - fixtures/review-fusion
forbidden_paths:
  - "/Users/praise/.claude/**"
  - scripts/gd-codex-transport-guard.py
  - scripts/gd-review-suite-controller.py
  - scripts/gd-codex-bridge-review.py
  - prompts/gd-review-standard.md
  - scripts/gd-review-merge-and-fix-loop.py
  - scripts/gd-review-router.py
  - .deploy-manifest.jsonl
  - baselines/gd-v7-runtime-write-authorizations.jsonl
  - 旧 /rev artifacts
  - 任何 scripts/ 下的文件（本 task 只写 tests/ 与 fixtures/）
```

读写权限分层：

- **写入**：仅限 `tests/review-fusion` 与 `fixtures/review-fusion`。写入任何 `scripts/`、`prompts/`、`baselines/`、`.deploy-manifest.jsonl` 或 `/Users/praise/.claude/**` 视为越界，[P1] 阻断。
- **读取**：允许 (1) `required_context`；(2) 已完成 blocked_by（t1-t4）的 deliverable 脚本源码（仅为编写断言，禁止修改）；(3) 公共只读资源。

---

## 5. 成功标准（SC）

> 沿用 master plan §3 的 SC-4 / SC-5 / SC-7（本 track sc_refs）。SC-1/2/3/6 的被测 pytest 用例由本套件提供（与 t1-t4 共用 `-k` 关键词），但权威 verify 归 SC-4/5/7。

- [ ] **SC-4（有界收敛 + 收敛超时）**：`tests/review-fusion` 下存在以 `convergence` 与 `convergence_timeout` 命名的 pytest 用例；subprocess 调 t3 的 `gd-review-merge-and-fix-loop.py`，喂「连续 2 轮 unresolved 数不下降」停滞 fixture，断言 `exit≠0` + 输出含 `CONVERGENCE_TIMEOUT`，且未跑满 5 轮硬上限。验证：`python3 -m pytest tests/review-fusion -k 'convergence' -q 2>&1 | tail -1` 末行含 `passed` 无 `failed`/`error`。
- [ ] **SC-5（fail-closed 不降级 + retry 恢复）**：存在 `fail_closed` 与 `retry_recover` 用例；`fail_closed` 注入「单 codex 经 preflight+重试 仍不可用」（fake-codex stub 持续失败），断言 blocked 非通过（`exit≠0` + 输出含 `codex_transport_unavailable`/`blocked`），**断言输出不含仅 Claude 的 `APPROVED`**；`retry_recover` 注入「瞬时失败一次后恢复」，断言 bounded 重试恢复、review 正常完成（`exit==0`）。验证：`python3 -m pytest tests/review-fusion -k 'fail_closed' -q 2>&1 | tail -1` 末行含 `passed` 无 `failed`/`error`。
- [ ] **SC-7（治理零破坏回归）**：`fixtures/review-fusion/` 下存在 `regression-controller-report.json`、`regression-ledger.json`、`regression-batch.json`、`dispatch-map.json` 四个 fixture，分别被对应 validator 判 VALID。验证：全链校验 controller-report + stage-dispatch-ledger + dispatch-map + execution-batch 四个 validator 全部 exit 0 并输出 `PASS`。

---

## 6. 交付物

```yaml
deliverables:
  - path: tests/review-fusion
    kind: directory
    must_exist: true
    description: 本 track 唯一 pytest 套件目录；含下列测试模块 + conftest + codex stub。
  - path: tests/review-fusion/conftest.py
    kind: file
    must_exist: true
    description: pytest fixtures——解析 PROJECT_ROOT、定位 t1-t4 被测脚本、run_script(subprocess) helper + fake-codex stub 路径注入（PATH/env）。
  - path: tests/review-fusion/test_transport_guard.py
    kind: file
    must_exist: true
    description: 四道防线——用例名含 preflight_unavailable_fail_closed / retry_recover / timeout_configured / healthcheck_invocation；subprocess 调 gd-codex-transport-guard.py。
  - path: tests/review-fusion/test_baseline_union.py
    kind: file
    must_exist: true
    description: 用例名含 union_baseline——喂 codex_A 漏报 / codex_B 命中对，断言并集 baseline 必含该 finding。
  - path: tests/review-fusion/test_round_scope.py
    kind: file
    must_exist: true
    description: 用例名含 r2_scope_constrained_dual_codex——断言 r2 capsule 含 REVIEW_ROUND≥2 + BASELINE_FINDINGS + DELTA_SCOPE + SCOPE_CONSTRAINT + 双 codex job + 未改动内容不在范围。
  - path: tests/review-fusion/test_convergence.py
    kind: file
    must_exist: true
    description: 用例名含 convergence 与 convergence_timeout——停滞 fixture 触发 CONVERGENCE_TIMEOUT exit≠0 且不超 5 轮。
  - path: tests/review-fusion/test_fail_closed.py
    kind: file
    must_exist: true
    description: 用例名含 fail_closed 与 retry_recover——fail_closed→blocked 非通过且无仅 Claude APPROVED；retry_recover→正常完成。
  - path: tests/review-fusion/test_code_path_separation.py
    kind: file
    must_exist: true
    description: 用例名含 code_path_quality_conformance_separation 与 bridge_contract——质量(/code-review+/simplify)与符合性两步可分别观测；bridge 契约四态。
  - path: tests/review-fusion/fixtures
    kind: directory
    must_exist: true
    description: pytest input fixtures（停滞计划、codex_A/B finding 对、瞬时失败 stub 等）；与 fixtures/review-fusion 的治理 validator fixture 分离。
  - path: fixtures/review-fusion/regression-controller-report.json
    kind: file
    must_exist: true
    description: 满足 gd-validate-controller-report.py v1.1；双 gate 一致 + suite_target_closure 覆盖全 jobs + batch_ledgers=[]（自包含）。
  - path: fixtures/review-fusion/regression-ledger.json
    kind: file
    must_exist: true
    description: 满足 gd-validate-stage-dispatch-ledger.py（stage=review_execution_code，1 child，final_decision=APPROVED）。
  - path: fixtures/review-fusion/regression-batch.json
    kind: file
    must_exist: true
    description: 满足 gd-validate-execution-batch.py；与 dispatch-map.json 配对，wave membership / owned_paths containment / sc_refs↔verify 全通过。
  - path: fixtures/review-fusion/dispatch-map.json
    kind: file
    must_exist: true
    description: regression-batch.json 的配套 dispatch map；过链式 gd-validate-dispatch.py。
```

---

## 7. 验证（Anti-fill 硬约束）

> dispatch-map 权威 verify，原样执行。子 agent 须在 project root（`cd Project GD/`）下运行（execution-batch 校验按 cwd 解析相对路径）。

```yaml
verify:
  - sc_ref: SC-4
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'convergence' -q 2>&1; python3 -m pytest tests/review-fusion -k 'convergence' -q 2>&1 | grep -E 'passed|failed|error|no tests ran' | tail -1"
    expect: "passed"
    note: "tail -1 改为 grep 精确匹配 passed/failed/error/no tests ran，避免 conftest 报错时 tail -1 返回错误信息被误判。若输出含 'no tests ran'，说明 conftest/stub 未就位，视为 FAILED（用例未收集到即等于退化）。"
  - sc_ref: SC-4-collection-guard
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'convergence' --collect-only -q 2>&1 | grep -c 'test_convergence' || echo 0"
    expect: ">=2"
    note: "先验证用例能被收集（>=2 个含 convergence 的用例），collect-only 不执行用例，排除「0 tests collected」导致 tail -1 返回空/非 passed 的退化。"
  - sc_ref: SC-5
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'fail_closed or retry_recover' -q 2>&1 | grep -E 'passed|failed|error|no tests ran' | tail -1"
    expect: "passed"
    note: "同 SC-4：grep 精确匹配终态行。stub 路径注入失败（fake-codex-always-fail 不可执行）会导致 ImportError 或 0 collected，均被 grep 捕获为非 passed。"
  - sc_ref: SC-5-collection-guard
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'fail_closed or retry_recover' --collect-only -q 2>&1 | grep -cE 'fail_closed|retry_recover' || echo 0"
    expect: ">=2"
    note: "验证 fail_closed 与 retry_recover 各至少 1 个用例可收集，排除 stub 路径未配置导致 0 collected 的退化情形。"
  - sc_ref: SC-6
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'code_path_quality_conformance_separation or bridge_contract' -q 2>&1 | grep -E 'passed|failed|error|no tests ran' | tail -1"
    expect: "passed"
  - sc_ref: SC-7
    method: command
    cmd: "python3 scripts/gd-validate-controller-report.py fixtures/review-fusion/regression-controller-report.json && python3 scripts/gd-validate-stage-dispatch-ledger.py fixtures/review-fusion/regression-ledger.json && python3 scripts/gd-validate-dispatch.py fixtures/review-fusion/dispatch-map.json && python3 scripts/gd-validate-execution-batch.py fixtures/review-fusion/regression-batch.json fixtures/review-fusion/dispatch-map.json && echo PASS"
    expect: "PASS"
```

补充自检（非权威 verify，完成前 SHOULD 全绿，否则 SC-7 三件套不算齐 + SC-1/2/3/6 未覆盖）：

```yaml
self_check:
  - "python3 scripts/gd-validate-stage-dispatch-ledger.py fixtures/review-fusion/regression-ledger.json"
  - "python3 scripts/gd-validate-execution-batch.py fixtures/review-fusion/regression-batch.json fixtures/review-fusion/dispatch-map.json"
  - "python3 -m pytest tests/review-fusion -k 'preflight_unavailable_fail_closed or retry_recover or timeout_configured or healthcheck_invocation' -q 2>&1 | tail -1"
  - "python3 -m pytest tests/review-fusion -k 'union_baseline' -q 2>&1 | tail -1"
  - "python3 -m pytest tests/review-fusion -k 'r2_scope_constrained_dual_codex' -q 2>&1 | tail -1"
  - "python3 -m pytest tests/review-fusion -k 'code_path_quality_conformance_separation or bridge_contract' -q 2>&1 | tail -1"
```

---

## 8. HOW（实现规格，禁空词）

### A. pytest 套件组织（被测脚本不改，只调用）
- `conftest.py` 提供 `run_script(rel_path, args, env=None, input=None)`：`subprocess.run([sys.executable, PROJECT_ROOT/rel_path, *args], capture_output=True, text=True)` → `(returncode, stdout, stderr)`。
- 纯函数（收敛判定、mapping）用 `importlib.util.spec_from_file_location` 从绝对路径动态 import，不把 scripts/ 加入可写 path。
- codex 不可用/瞬时失败注入：`tests/review-fusion/fixtures/` 放可执行 stub（`fake-codex-always-fail`、`fake-codex-transient-then-ok`，参照既有 `tests/transport/fake-codex`），经 `env["PATH"]` 前置或 transport-guard 约定的 `CODEX_BIN` env 指向 stub。瞬时失败 stub 用计数文件（首调写 marker 退非 0，二调读 marker 退 0）。

### B. 每个 SC 的 pytest 用例名（与 master-plan §3/§8 `-k` 关键词逐一对齐）

| 测试文件 | 用例名片段 | 断言要点 |
|---|---|---|
| test_transport_guard.py | `preflight_unavailable_fail_closed` | stub 持续失败 → preflight 判不可用 → exit≠0 + 输出 `codex_transport_unavailable`；不产 APPROVED |
| test_transport_guard.py | `retry_recover` | transient stub（首失败后恢复）→ bounded 重试后探活成功 → exit==0 |
| test_transport_guard.py | `timeout_configured` | 断言 transport-guard 含显式 timeout 配置（运行时 timeout 生效，非无限等待） |
| test_transport_guard.py | `healthcheck_invocation` | 断言 preflight 之外存在 healthcheck 调用路径（stub 收到 healthcheck 调用记录） |
| test_baseline_union.py | `union_baseline` | codex_A 漏报 / codex_B 命中同一 finding（键 文件+行号±3+类别）→ 并集 baseline **必含**，严重度取高 |
| test_round_scope.py | `r2_scope_constrained_dual_codex` | r2 capsule 含 REVIEW_ROUND≥2 + BASELINE_FINDINGS + DELTA_SCOPE + SCOPE_CONSTRAINT；两 codex job；未改动内容不在范围 |
| test_convergence.py | `convergence_pass`（命中 `convergence`） | 正常收敛 fixture → 5 轮内收敛 exit==0 |
| test_convergence.py | `convergence_timeout` | 停滞 fixture（连续 2 轮 unresolved 不减）→ exit≠0 + `CONVERGENCE_TIMEOUT`，轮数未达 5 |
| test_fail_closed.py | `fail_closed` | always-fail stub → blocked 非通过 exit≠0；输出**不含**仅 Claude `APPROVED`、不含「降级继续」 |
| test_fail_closed.py | `retry_recover` | transient stub → review 正常完成 exit==0（防线先于阻断） |
| test_code_path_separation.py | `code_path_quality_conformance_separation` | code/执行路 → 「找 bug/清理」产物与「符合性」判定为两个可分别观测的 artifact/输出段 |
| test_code_path_separation.py | `bridge_contract` | 四态：valid raw→mapped+schema pass；缺 SC→FAILED；malformed→FAILED；writer 非成功 stdout→FAILED；degraded→FAILED；failed_to_run→FAILED |

> 硬构造条件：`union_baseline` fixture **必须含 codex_A 漏报 / codex_B 命中对**；`convergence_timeout` fixture **必须连续 2 轮 unresolved 不减**（master-plan §3 SC-2/SC-4 明文）。

### C. 三个治理 validator 的 regression fixture（按真实字段）

**(1) regression-controller-report.json** — `gd-validate-controller-report.py`：
- 顶层全 REQUIRED：`schema_version`="1.1" / `run_mode`="fixture"（validator 接受） / `started_at` / `finished_at` / `aggregate_path` / `manifest_path` / `primary_gate` / `secondary_gate` / `gate_consistent`=true / `dirty_detected`=false / `jobs`。
- `primary_gate`/`secondary_gate` 各含 `verdict`="APPROVED" + `blocking`=[]（双 gate 一致）。
- `jobs` 每项全 REQUIRED_JOB_FIELDS（`queue_job_id`/`target_role`/`primary_target`/`bridge_exit`/`bridge_stderr_path`/`bridge_stderr_summary`/`raw_verdict`/`mapped_status`/`aggregate_bucket`）。1 job：`queue_job_id="job-rf-001"`, `target_role="review_execution_code"`。
- v1.1：`batch_ledgers`=**[]**（避免外部 hash 依赖，自包含）；`suite_target_closure`=[{`target_id`:"job-rf-001", `evidence_kind`:"controller_approved"}]（覆盖全 jobs，否则 exit 5）。

**(2) regression-ledger.json** — `gd-validate-stage-dispatch-ledger.py`：
- 全字段；`stage`="review_execution_code"；`child_agent_count`=1，`max_parallel`=1；`child_jobs` 长度=1，job 含 `result_hash`=64-hex、`status`="completed"；`main_agent_merge.final_decision`="APPROVED"（→ 所有 job 须 completed，已满足）+ `blocking_buckets`=[]。

**(3) regression-batch.json + dispatch-map.json** — `gd-validate-execution-batch.py`（链式先跑 `gd-validate-dispatch.py`）：
- `dispatch-map.json` 顶层全字段（参照 fixtures/dispatch/valid-dispatch.json），单 track `track_id="rf-reg"`，`owned_paths=["fixtures/review-fusion/_regwork"]`，`forbidden_paths` 含 `/Users/praise/.claude/**`，`sc_refs=["SC-7"]`，`verify` 每项 `sc_ref`+`method`+`cmd`；`waves`=[{wave_id:"w1", track_ids:["rf-reg"]}]；`merge_gates`≥1。
- `regression-batch.json`：`dispatch_id` 与 dispatch-map 一致；`wave_ref`="w1"；`execution_mode`="agent_exec"（`dry_run` 会 fast-reject exit 1）；`task_results` 单项全 REQUIRED_TASK_FIELDS，`track_ref`="rf-reg"，`exec_status`="completed"，`not_run_reason`=null。
- v5：wave membership `set(track_ref)`=={"rf-reg"}；owned_paths containment：`deliverables_produced[].path` 落在 `fixtures/review-fusion/_regwork` 内；physical existence：verified=true 的 deliverable 指向本 task 一并创建的占位 `fixtures/review-fusion/_regwork/result.json`。
- sc_refs↔verify coupling：`verify_results` 有且只有 `sc_ref="SC-7"`；cmd ≥3 字符且不含 anti-fill 违规词。
- `gd_execution_status_json` 含 `task_id`/`exec_status`=completed/`sc_results`={"SC-7":"pass"}。
- deliverable path 不含 `..`、不以 `/Users/praise/.claude` 开头。

### D. forbidden_paths 兑现
- §4 含 `/Users/praise/.claude/**` + 所有 t1-t4 owned 脚本 + prompt + manifest + 授权 ledger，显式声明不写任何 `scripts/`。所有 stub、计数文件、占位 deliverable 落在 `tests/review-fusion/` 或 `fixtures/review-fusion/` 内。

---

## 9. Handoff 输出

```yaml
handoff_output:
  result_path: <子 agent 写入 execution result 的相对路径，须落在 owned_paths 内>
  status_field: <见 gd-execution-status.schema.json：completed | completed_with_skips | failed | blocked>
  summary: 三件 validator fixture + 7 个 pytest 模块是否全绿
  blockers: 若 t3/t4 被测脚本未就位导致 pytest 无法运行，记此处并 status=blocked
```

---

## 10. 范围禁令

- 禁止 **写入** 任何 `scripts/`、`prompts/`、`baselines/`、`.deploy-manifest.jsonl`、其他 track owned_paths。
- 禁止 **修改** t1-t4 被测脚本；只能 subprocess/import 调用。
- 禁止访问 `/Users/praise/.claude/**`；禁止 daemon/hook/cron；禁止用对话上下文替代 required_context；不自动 commit/push。
