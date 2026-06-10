# Task Packet: t3-review-plan-convergence

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t3-review-plan-convergence
agent_role: implementer
parent_step: step-3
parent_track_id: t3-review-plan
parent_dispatch_id: l3-review-fusion
parent_plan: plans/gd/2026-06-09-l3-review-fusion/master-plan.md
created_at: 2026-06-09T00:00:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，降低填表式计划与执行遗漏风险（引用 GOAL_SOURCE，不重写）
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准（引用 GOAL_SOURCE，不重写）
PHASE_GOAL:   把 L2 已验证收敛机制融合进 L3 review，质量/符合性分离，零破坏治理 gate（引用 master plan）
TASK_GOAL:    在 scripts/gd-review-merge-and-fix-loop.py 把现有 ≤3 轮 auto-fix 循环（MAX_AUTO_FIX_ROUNDS=3）升级为 L2 收敛机制：首轮 dual-codex（codex_A/codex_B 仅 lens 不同）+ Claude self-review 三方并集去重建 baseline_findings.json → r2 起注入 REVIEW_ROUND/BASELINE_FINDINGS/DELTA_SCOPE/SCOPE_CONSTRAINT 只验修复+查 delta、每轮仍 dual-codex（无 D7）→ 5 轮硬上限、连续 2 轮 unresolved 不减 → CONVERGENCE_TIMEOUT exit≠0。复用 t2 已暴露的 bridge lens 入参，不改 bridge。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t2-bridge   # bridge lens_emphasis 入参必须先由 t2 落地，t3 复用该接口
can_parallel_with:
  - t4-code-path                    # t4 owned_paths=scripts/gd-review-router.py，与本任务 owned_paths 不重叠，可并行（master-plan §5a wave w3）
# 依赖说明：原 blocked_by 含 t5-regression，但 t5 又 blocked_by t3/t4，形成执行环。
# SC-2/SC-4 的 pytest fixture 由 t5 提供，但这是 post-t5 集成 gate，不是 t3 的执行前置。
# t3 实装收敛逻辑，t5 实装 pytest fixture，两者按 dispatch-map w3/w4 序顺序执行（t5 在 t3 之后），
# 无循环依赖。已按 dispatch-map 修正：t3 blocked_by=[t2]，与 t4 并行于 wave w3。
required_context:
  - specs/l3-review-fusion/spec.md                                 # FR-001 三方并集 / FR-002 r2 收窄 / FR-003 有界 5 轮 / FR-004 每轮 dual-codex 无 D7
  - docs/constitution.md                                           # P5 收敛有界；P4 fail-closed
  - plans/gd/2026-06-09-l3-review-fusion/master-plan.md            # §3 SC-2/SC-3/SC-4；§5 Step 3；§9 Assumptions（L2 移植基准 + 刻意去 D7）
  - scripts/gd-codex-bridge-review.py                              # 只读：t2 暴露的 capsule 入参契约（run-bridge / parse-transport / build_capsule_text 签名中的 lens_emphasis + round/baseline/delta/scope-constraint 参数）；本任务禁止写入此文件
```

> L2 移植基准说明：本任务算法权威源是已实现并测试通过的 L2 `scripts/gd-review-controller.py`（主 checkout 或 `.claude/worktrees/gd-l2-parity/scripts/gd-review-controller.py`）。其 `merge_findings_union` / `run_round1` / `run_round_n` / `_run_convergence_loop` / `update_baseline_statuses` 是移植参照。**读不到该文件**时以 master-plan §9 Assumptions + constitution P5 描述的 L2 机制为准。

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-review-merge-and-fix-loop.py   # 本任务唯一允许写入的路径
forbidden_paths:
  - "/Users/praise/.claude/**"（例外：经 bridge --live-transport 间接写入 ~/.claude/review-baselines/<gd_baseline_key>/ 为 bridge transport 契约，本任务不直接操作该路径）
  - scripts/gd-review-router.py               # t4-code-path owned
  - scripts/gd-codex-transport-guard.py       # t1 owned
  - scripts/gd-review-suite-controller.py     # t1 owned 接入点
  - scripts/gd-codex-bridge-review.py         # t2 owned；只读消费 capsule 入参契约，禁止写
  - prompts/gd-review-standard.md             # t2 owned
  - tests/review-fusion                       # t5 owned
  - fixtures/review-fusion                    # t5 owned
  - .deploy-manifest.jsonl                    # t6 owned
  - baselines/gd-v7-runtime-write-authorizations.jsonl  # t6 owned
  - 旧 /rev artifacts
```

读写权限分层：

- **写入**：仅限 `scripts/gd-review-merge-and-fix-loop.py`；越界 [P1] 阻断。
- **读取**：允许 (1) `required_context` 列出的文件；(2) 已完成 `blocked_by`（t2-bridge）的 deliverable —— `gd-codex-bridge-review.py` 的 capsule 入参契约（只读消费）；(3) 公共只读资源（GOAL_SOURCE、L2 `gd-review-controller.py` 移植参照、`gd_review_contract.py` 的 REVIEW_KIND_ENUM）。
- 其他 track 未完成的 owned_paths（如 `gd-review-router.py`）禁止读取。

---

## 5. 成功标准（SC）

> sc_refs：SC-2 / SC-3 / SC-4（master-plan §3）。SC-2 与 SC-4 的 pytest fixture 由 **t5** 提供（`tests/review-fusion` + `fixtures/review-fusion`），本任务只产出被这些用例驱动的脚本逻辑，不写 fixture/test。

- [ ] **SC-2（首轮三方并集 baseline）**：实装 `merge_findings_union(codex_a, codex_b, claude)` 三方并集去重——去重键 = `(file 归一化小写, category 归一化小写, line±3)`，severity 取高（`P1>P2>其他`），首报方记 `source`，其余记 `also_reported_by`；round1 路径 dual-codex（codex_A 用 lens_A、codex_B 用 lens_B，仅侧重不同）+ Claude self-review 为第三源 → 输出 `baseline_findings.json`。fixture 含 codex_A 漏报 / codex_B 命中的一对 finding 时，baseline 并集必含该 finding。验证：`python3 -m pytest tests/review-fusion -k 'union_baseline' -q 2>&1 | tail -1` == PASS。
- [ ] **SC-3（r2+ 收窄 + 每轮 dual-codex，无 D7）**：第 2 轮起每轮 capsule 注入四字段 `REVIEW_ROUND`(≥2) / `BASELINE_FINDINGS`(整份 baseline JSON) / `DELTA_SCOPE`(本轮 delta diff 摘要) / `SCOPE_CONSTRAINT`（"只验修复 + 查 delta，不重审未改动、不扩边界"），只验 baseline 未决项是否修复 + 查 delta 新问题，不重审未改动；且每一轮恒为 dual-codex（两个 codex job，均传四字段，**删除 D7 大改动升级条件**）。验证：四个独立 `grep -q` 串联检查 REVIEW_ROUND / BASELINE_FINDINGS / DELTA_SCOPE / SCOPE_CONSTRAINT 全部存在 → `echo PASS`。任一缺失则 grep 非零，verify 失败。
- [ ] **SC-4（有界收敛）**：硬上限 = 5 轮（`MAX_REVIEW_ROUNDS = 5`，替换旧 `MAX_AUTO_FIX_ROUNDS = 3`）；维护 `stagnant_rounds` + `prev_unresolved`：每轮算 `baseline_unresolved`，`>= prev_unresolved` 则 `stagnant_rounds += 1` 否则归 0；`stagnant_rounds >= 2` → 打印 `CONVERGENCE_TIMEOUT` 并 `sys.exit(1)`；跑满 5 轮仍未收敛 → 同样 `CONVERGENCE_TIMEOUT` exit≠0。构造连续 2 轮 unresolved 不减的停滞 fixture，脚本 exit≠0 且 stdout 含 `CONVERGENCE_TIMEOUT`。验证：`python3 -m pytest tests/review-fusion -k 'convergence_timeout' -q 2>&1 | tail -1` == PASS。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-review-merge-and-fix-loop.py
    kind: file
    must_exist: true
    description: 升级后的 plan-review 收敛循环——三方并集 baseline + r2 起四字段收窄 + 每轮 dual-codex（无 D7）+ 5 轮硬上限 + 连续 2 轮停滞 CONVERGENCE_TIMEOUT exit≠0
  - path: <output-dir>/baseline_findings.json
    kind: file
    must_exist: true
    description: 首轮三方并集去重后的 finding 基线（运行期产物；findings[] 含 id/file/line/category/severity/status/source/also_reported_by/round_history，顶层含 baseline_unresolved_count）
```

---

## 7. 验证（Anti-fill 硬约束）

> 权威 verify 来自 dispatch-map，原样使用。SC-2 / SC-4 的 pytest fixture 由 t5 提供；本任务在 t5 fixture 落地后才能跑绿这两条，但脚本逻辑须先就位。SC-3 为 grep 断言，本任务交付即可自验。

```yaml
verify:
  - sc_ref: SC-2
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'union_baseline' -q 2>&1 | tail -1"
    expect: "passed"          # fixture 由 t5 提供（codex_A 漏报/codex_B 命中对 → baseline 并集必含）
  - sc_ref: SC-3
    method: command
    cmd: "grep -qE 'REVIEW_ROUND' scripts/gd-review-merge-and-fix-loop.py && grep -qE 'BASELINE_FINDINGS' scripts/gd-review-merge-and-fix-loop.py && grep -qE 'DELTA_SCOPE' scripts/gd-review-merge-and-fix-loop.py && grep -qE 'SCOPE_CONSTRAINT' scripts/gd-review-merge-and-fix-loop.py && echo PASS"
    expect: "PASS"
    note: "四字段字面量 grep 为静态检查，须与下方行为验证串联使用，单独不足以证明四字段被实际注入 bridge 调用。"
  - sc_ref: SC-3-bridge-callsite
    method: command
    cmd: "python3 -c \"import importlib.util, inspect; spec=importlib.util.spec_from_file_location('loop','scripts/gd-review-merge-and-fix-loop.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); src=inspect.getsource(m); fields=['REVIEW_ROUND','BASELINE_FINDINGS','DELTA_SCOPE','SCOPE_CONSTRAINT']; bridge_call=any('run-bridge' in src or 'run_bridge' in src or '_invoke_bridge' in src for _ in [1]); assert bridge_call, 'no bridge invocation found'; for f in fields: assert src.count(f)>=2, f'{f} appears <2 times (likely only defined, not passed to bridge)'; print('PASS')\""
    expect: "PASS"
    note: "验证四字段在 merge-and-fix-loop 中出现次数 >=2（至少一处定义 + 一处传入 bridge 调用），确保不是仅有字面量常量而未传给 bridge。bridge 调用方式由 §8.6 规定（env 变量传参）。"
  - sc_ref: SC-3
    method: assertion
    cmd: "grep -cE 'max_workers.*2|ThreadPoolExecutor.*2|dual.codex|codex_A.*codex_B' scripts/gd-review-merge-and-fix-loop.py"
    expect: ">=1"
  - sc_ref: SC-3
    method: assertion
    cmd: "grep -cE 'large_delta|D7|threshold_lines|threshold_files' scripts/gd-review-merge-and-fix-loop.py"
    expect: "0"
  - sc_ref: SC-4
    method: command
    cmd: "python3 -m pytest tests/review-fusion -k 'convergence_timeout' -q 2>&1 | tail -1"
    expect: "passed"          # fixture 由 t5 提供（停滞 fixture → exit≠0 + CONVERGENCE_TIMEOUT）
```

---

## 8. HOW（基于 gd-review-merge-and-fix-loop.py 真实结构的实现路线）

> 改动落在 `scripts/gd-review-merge-and-fix-loop.py`（owned）；bridge / router / fixtures 不碰。L2 算法移植自 `gd-review-controller.py`，但**去掉 D7**（spec FR-004 / master-plan §4 / constitution P5）。

### 8.1 现状锚点
- `MAX_AUTO_FIX_ROUNDS = 3`（旧上限，SC-4 替换为 5）。
- fixture 模式 `SCENARIO_HANDLERS` = `codex_unavailable / split_findings / fix_then_rereview / four_rounds_required`。`run_split_findings` 已有简陋去重（键=`(reviewer,severity,description)`，仅去精确重复，**非** file+line±3+category 并集）；`run_four_rounds_required` 用 `MAX_AUTO_FIX_ROUNDS` 判 `AUTO_FIX_EXHAUSTED`。
- production `--plan` 路径：`run_production_plan` → `_consume_and_merge`（单 codex + Claude 两方 merge matrix，无轮次循环 / baseline / dual-codex / capsule 收窄）。
- 已 import `hashlib/subprocess/re/json/datetime/Path`；复用 `_sha256_file` 取 plan hash。

### 8.2 并集去重（SC-2）—— 键=文件+行号±3+类别，severity 取高
新增（移植 L2 `merge_findings_union` + helper），不改 `run_split_findings` 既有 fixture 行为：
```
LINE_DEDUP_WINDOW = 3
def _severity_rank(s)            # {"P1":2,"P2":1}.get(s,0)
def _finding_filecat(f)          # (file.strip().lower(), category.strip().lower())
def _lines_within_window(a,b)    # 同 None→True；一 None→False；否则 abs(int(a)-int(b))<=3
def merge_findings_union(codex_a, codex_b, claude)
    # 三源打 tag；线性扫描：(file,category) 相同且 line 在 ±3 窗口 → 并入；severity 取高；首报记 source、其余 also_reported_by；
    # 赋稳定 id F001.. + status="unresolved" + resolved_in_round=None + round_history=[{round:1,status:unresolved}]
```
关键：**不要用 `line // 7` 桶**（L2 已记该 bucket 把相距 3 行的 finding 错分两桶，是 bug）；用 `abs(a-b)<=3` 直接窗口比较。

### 8.3 baseline_findings.json 存哪
写到 `run_production_plan` 的 `output_dir`（已有 `output_dir = Path(output_dir_str) if output_dir_str else plan_path.parent`）下，固定名 `baseline_findings.json`。移植 L2 `write_baseline` 顶层结构：`{schema_version, baseline_round:1, created_at, controller_invocation_id, branch:"plan", delta_snapshot, baseline_unresolved_count, findings:[...]}`。round1 完成即落盘。

### 8.4 round1 三方并集（SC-2）
新增 round1（移植 L2 `run_round1`）：dual-codex（`ThreadPoolExecutor max_workers=2`，对应 FR-009 ≤2 与 P5），两 job 唯一差异是 lens emphasis（codex_A 用 lens_A、codex_B 用 lens_B；侧重不同同源）；Claude self-review findings 从 `--claude-review` mapped JSON 的 `findings[]` 取，作为第三源传 `merge_findings_union`。bridge 走 t2 lens 入参（见 8.6），消费 mapped JSON `findings[]`（复用现有 `parse-transport` mapped 消费）。

### 8.5 r2+ 收窄 + 每轮 dual-codex（SC-3，无 D7）
新增 round_n（移植 L2 `run_round_n`，**删 large_delta/D7 分支**）+ 收敛循环（移植 `_run_convergence_loop`）：
- delta：移植 `take_delta_snapshot`（`git stash create` 取 tree-ish，**不写 git 历史**；clean tree fallback `git rev-parse HEAD`）+ `git diff HEAD`，`GIT_OP_TIMEOUT_SEC=30`。plan 审查 delta = 计划文件版本差异。
- 每轮 capsule 注入四字段：`SCOPE_CONSTRAINT`="Only verify whether baseline findings have been fixed and check delta for newly introduced issues. Do NOT re-judge baseline findings. Do NOT re-audit unchanged content outside the delta."；`DELTA_SCOPE`=`f"{delta_lines} lines changed across {delta_files} files\n--- diff ---\n{diff_text[:4000]}"`；`BASELINE_FINDINGS`=`json.dumps(baseline,ensure_ascii=False,indent=2)`；`REVIEW_ROUND`=`round_num`(≥2)。
- **每轮恒 dual-codex**：r2+ 始终两 codex job（max_workers=2），均带四字段 + lens_A/lens_B（收窄 scope 之上仍双视角，FR-004）。**移除** `large_delta = ...` 判断与单 codex 分支、删 `threshold_lines/threshold_files` 形参与对应 CLI arg。
- baseline 状态更新移植 `update_baseline_statuses`（H5：仅当本轮 codex 不再报该 symptom（±3 窗口不命中）才标 resolved；delta 中不在 baseline 的为 `new_in_delta` 追加为新 unresolved）。

### 8.6 四字段如何传给 bridge（复用 t2 lens 入参，不改 bridge）
t2 已在 bridge 暴露 lens + round/baseline/delta/scope-constraint capsule 入参（blocked_by 依赖）。本任务移植 L2 `_invoke_bridge_mapped`，用**环境变量**传：`GD_REVIEW_ROUND` / `GD_REVIEW_LENS_EMPHASIS`(lens_A/lens_B) / `GD_BASELINE_FINDINGS`(JSON) / `GD_DELTA_SCOPE` / `GD_SCOPE_CONSTRAINT`；并设 `GD_REVIEW_ROUTER_INVOCATION_ID`（脚本已有 `INVOCATION_ID_ENV`，production 路径要求其存在，Q3 side-door 检查）。bridge 调用序列：`run-bridge --kind plan --target <plan> --cwd <root> --out <log> --live-transport` 取 `TRANSPORT_RESULT:` → `parse-transport --kind plan --target <plan> --raw-result <raw> --out <mapped>` → 读 mapped `findings[]`。**bridge 不写**；若运行期发现 t2 入参名/机制与 env 方式不一致，按 t2 实际契约对齐传参，仍不改 bridge。

### 8.7 5 轮上限 + 连续 2 轮无进展 + CONVERGENCE_TIMEOUT（SC-4）
- 新增 `MAX_REVIEW_ROUNDS = 5` 替换 `MAX_AUTO_FIX_ROUNDS = 3`（旧 fixture handler 若引用旧名，改引新名或保留为向后兼容独立常量，但 production 收敛循环用 5）。
- 收敛循环（移植 `_run_convergence_loop`）：`prev_unresolved: int|None=None`、`stagnant_rounds=0`；`for round_num in range(2, MAX_REVIEW_ROUNDS+1):` 每轮跑 round_n → `update_baseline_statuses` 得 `baseline_unresolved`/`new_in_delta`；`if prev_unresolved is not None and baseline_unresolved >= prev_unresolved: stagnant_rounds+=1 else: stagnant_rounds=0`；`prev_unresolved=baseline_unresolved`；`if stagnant_rounds>=2:` → `print("CONVERGENCE_TIMEOUT: ...")` + `sys.exit(1)`；`if baseline_unresolved==0 and new_in_delta==0:` → `print("APPROVED")` return；循环满 5 轮未收敛 → `CONVERGENCE_TIMEOUT` exit≠0。
- 终态归属：脚本只发 `CONVERGENCE_TIMEOUT` 信号 + exit≠0（终点 gate 处置 blocked）。

### 8.8 不变量与禁区
- **fail-closed 保留**（P4）：Codex 不可达绝不产 APPROVED——保留 `run_codex_unavailable` 的 `CODEX_TRANSPORT_UNAVAILABLE` + exit≠0；dual-codex 任一 job transport 失败即 fail-closed，不以"存活视角+Claude"凑数。
- **plan-only 守卫保留**：`MERGE_FIX_LOOP_NOT_APPLICABLE` 对非 plan kind 的 exit 2 拒绝不动。
- **不动 D7**：L3 刻意去 D7。
- 全程不写 `/Users/praise/.claude/**`、不写 router/bridge/fixtures、不自动 commit/push、不起 daemon/hook/cron。

---

## 9. Handoff 输出

```yaml
handoff_output:
  result_path: reports/execution/t3-review-plan-convergence-result.json
  status_field: <见 gd-execution-status.schema.json>
  summary: plan 收敛循环升级落地：三方并集 baseline + r2 四字段收窄 + 每轮 dual-codex 无 D7 + 5 轮上限 CONVERGENCE_TIMEOUT
  blockers: t2 lens 入参未就位 / t5 fixture 未提供时 SC-2/SC-4 pytest 暂无法跑绿
```

---

## 10. 范围禁令

- 禁止 **写入** 其他 track 的 owned_paths（router/bridge/prompt/transport-guard/suite-controller/tests/fixtures/manifest/ledger）。
- 禁止 **读取** 其他 track 未完成的 owned_paths，除非已列入 required_context（仅 bridge 作为 t2 已完成依赖只读消费）。
- 禁止访问 `/Users/praise/.claude/**`；禁止 daemon/hook/cron；禁止自动 commit/push；禁止用对话上下文替代 required_context。
