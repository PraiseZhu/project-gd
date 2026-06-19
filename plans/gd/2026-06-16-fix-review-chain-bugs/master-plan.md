# 修复 GD 审查链路 fail-open/放水 bug v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-master-plan

日期：2026-06-16
状态：draft
负责人：Claude 执行；Codex 可选 cross-review

> 本 master plan 由 `/gd plan` 多 agent dispatch 生成：dispatch-map.json → 2 个 child planner（t1 共享+传输 / t2 L3+L2，wave w1，max_parallel=2）→ 主 agent 合并。
> 派发证据：`ledger/stage-dispatch-ledger.json` + `ledger/controller-report.json`；child 草稿：`proposals/{shared-infra,l3-internal}/proposal.md`。

---

## 1. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，提升复杂任务的计划、审查、执行、验收效率，并通过 Codex 作为 cross-review sidecar 降低填表式计划与执行遗漏风险。
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准，保证后续 /gd command、multi-agent dispatch、execution review、Codex cross-review 都引用同一套契约。
PHASE_GOAL:   消除 GD 三档审查链路（L1/L2/L3）的 fail-open/放水缺陷，使"失败/没审/未知态"不再被当成"通过"，APPROVED 只在有真实证据时产生。
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：fail-closed 收口完整性; returncode 与 decision 一致性; 未知态/缺字段/类型错判 fail; 跨链回归覆盖（L2+L3 共享组件）; 验证器真比对（hash/命令/类型）
- Domain-specific notes：审查链路是元工具——它的 bug 会让被审项目的坏代码静默通过。共享组件改动必须双链回归；child planner 已逐源核对，剔除了已被重构修好的旧 bug，避免"修已修好的代码"。

---

## 3. 成功标准（SC）

> 三类系统病统一收口：① 失败≠空列表/无问题 ② returncode 是真相源 ③ 未知态/缺字段/类型错 → fail-closed。

- [ ] SC-1（Step1·bridge N9）：`gd-codex-bridge-review.py` REQUIRES_CHANGES 返回 exit 1（不再 `else 0`）；verify：`grep -nE "return 0 if .*APPROVED.*else.*0" scripts/gd-codex-bridge-review.py` 无三元 0 命中
- [ ] SC-2（Step1·content-evidence V1）：verdict=UNKNOWN/识别不出时判 `FAKE_EVIDENCE_DETECTED` exit 1，不再早退免检
- [ ] SC-3（Step1·content-evidence V16）：REQUIRES_CHANGES 无 `### Finding` 块判 fail；`--skip-line-ref-check` 对 .json/REQUIRES_CHANGES target 拒绝
- [ ] SC-4（Step1·execution-outcome V3/V4/P2-dup）：build_gate+not_run 主动复跑或报"应改 pass"；schema 瑕疵时仍打印 `PHASE2_SKIPPED` 不静默跳过；重复 sc_ref 不静默覆盖
- [ ] SC-5（Step2·merge-loop #3/N1/N2/N8）：`_run_bridge_job` 异常/超时/解析失败产出 FAILED 不返空；两处 subprocess 查 returncode；没改的 finding 不判 resolved；Claude self-review 加载失败不静默 `[]`
- [ ] SC-6（Step2·router N3/N4/P2）：decision=None/FAILED → fail-closed（不映射 completed/APPROVED）；returncode≠0 不从 loop_report 取 APPROVED；损坏 descriptor 与真无 artifact 用不同 failure_code
- [ ] SC-7（Step2·suite-controller+aggregate N5/N6/P2）：bridge_exit≠0 强制 verdict=FAILED；aggregate 生成失败 → blocking 不 APPROVED；`closure_eligible` 缺失默认 False；aggregate mapped 解析失败 decision→FAILED
- [ ] SC-8（Step3·L3 验证器硬化 V2/V5/V6/V7/V8/V9/V11/V12/V13/V14+6P2）：空壳 anchor 判 fail；jsonschema 缺失不静默降级（exit 2 或显式告警）；hash 读文件真比对；布尔字段 isinstance 类型校验；空块/空 jobs/空 plan 判 fail；.json 入口不跳过强校验链
- [ ] SC-9（Step4·controller N7/N10）：`fut.result()` 包 try/except 写 CONVERGENCE_TIMEOUT 不 crash；git-delta 失败 fail-closed 或注入 `diff_unavailable:true`，不注假增量
- [ ] SC-10（Step4·transport #13/T1/T-watch）：launchctl 用 `launchctl list "$label"` 精确查；review-result-writer 关键写失败输出 `[REVIEW] ✗ FAILED` 不静默 abort；watch-state 用 glob 不用 `ls -r` 解析。**active 覆盖**：L2/L3 active writer 经本会话 bridge WRITER_PATH 修复（commit a12d384）已从旧 `~/.claude/scripts/` 改指 vendor writer，故 vendor 修复即覆盖 L2/L3 active 路径（无需写 `~/.claude/**`）；verify 须确认 active 解析==vendor，非仅 vendor/L1 通过。**部署说明（P2 deployment gap）**：verify 覆盖"本地直接运行"路径（WRITER_PATH 指 project/vendor）；已安装插件（~/.claude/plugins/cache/.../vendor）的 writer 与 project vendor 在执行阶段结束时不一致——plugin cache 需 `claude plugin update`（合并到 main 后）才覆盖。此 gap 属 deploy-after-merge 范畴，不影响源码修复的正确性。
- [ ] SC-11（Step5·L2+收尾）：review2-output MANDATORY_READ 空 → coverage gate 判 fail 不失效；audit-legacy-trust 兼容 JSON 格式 raw path 解析
- [ ] SC-12（Step1·content-evidence 误拒收口 / fail-closed 的另一面）：单条 finding 引用不完整（缺文件名前缀 / 缺 SC-ID）时**不得**把整份有效审查坍缩为 degraded/FAKE_EVIDENCE；只精确标记或降级该条，保留其余有效结论与整体 verdict。正例 fixture：引用风格各异但实质合法的审查仍 pass（防 V1/V16 收紧后误杀好审查）
- [ ] SC-13（Step1·bridge RC 误映射收口）：bridge **不得**把有效 `REQUIRES_CHANGES`（writer/codex 真审结果）映射为 `failed_to_run` / transport 失败；RC 是有效双审结果（review-standard §8.1），须保留为 REQUIRES_CHANGES，不与传输失败混淆

---

## 4. 非目标（NON_GOALS）—— ⚠️ 已被重构修好，**禁止重复改**（child 逐源核实）

- **#1（bridge `_run_bridge_job`）**：函数名已不存在，等价 `cmd_run_bridge` 已把 timeout/MALFORMED/FAILED/path 缺失全映射 FAILED → 已 fail-closed。**Step2 修 N1 时只参照其修法，不再回头改 bridge。**
- **#11（bridge `--out`）**：现按文件写且 required；若仍报目录错是**文档 bug**（改 `review2.md` 文档），非代码 bug。
- **P2-setdefault（execution-outcome `:316`）**：仅补 task_id，不洗白必填字段，无放水。
- **#12（install-transport/state-paths 双 fallback）**：当前两值一致，是**漂移风险非断链**；列为 Step4 可选硬化（单一真源），非阻断项。
- 旧 `/rev` 任何 artifact；`/Users/praise/.claude/**`。

---

## 5. Step 拆分

| Step | 名称 | owned_paths | 影响链路 | blocked_by | can_parallel_with | 主要 SC |
|------|------|------------|---------|-----------|-------------------|---------|
| 1 | 共享 P0 fail-closed（含误拒收口）| gd-codex-bridge-review.py; gd-validate-review-content-evidence.py; gd-validate-execution-outcome.py | **L2+L3 共享**（双链回归）| — | step-3 | SC-1,2,3,4,12,13 |
| 2 | L3 fail-open 收口 | gd-review-merge-and-fix-loop.py; gd-review-router.py; gd-review-suite-controller.py; gd-aggregate-codex-cross-review.py | L3-only | step-1 | step-4 | SC-5,6,7 |
| 3 | L3 验证器硬化 | gd-validate-{runtime-strict-binding,stage-dispatch-ledger,parent-close-gate,codex-cross-review-aggregate,codex-cross-review-manifest,execution-batch,master-plan-consistency,controller-report,dispatch,child-proposal,subplan-codex-binding,runtime-evidence}.py | L3-only | — | step-1 | SC-8 |
| 4 | 共享 controller + 传输层 | gd-review-controller.py; vendor/l3-transport/scripts/{install-transport,review-result-writer}.sh; vendor/l3-transport/handoff/lib/watch-state.sh | controller=L2+L3；传输=全链 | step-1 | step-2 | SC-9,10 |
| 5 | L2 + 收尾 | gd-validate-review2-output.py; gd-audit-legacy-review-trust.py | L2 | — | — | SC-11 |

---

## 5a. Dispatch Map / Wave Contract（MANDATORY）

> 本节是**执行阶段**（`/gd execute`）的 wave 契约；§开头的 dispatch-map.json 是**计划阶段**的 planning 派发，二者不同。
> 执行阶段需另写一份 execution dispatch_map（owned_paths 已在 §5 标注互斥），本表为其 wave 蓝本。

```
DISPATCH_MAP_PATH: plans/gd/2026-06-16-fix-review-chain-bugs/dispatch-map.json   (planning 阶段已用)
EXECUTION_DISPATCH_MAP: plans/gd/2026-06-16-fix-review-chain-bugs/execution-dispatch-map.json
VALIDATE_CMD: python3 scripts/gd-validate-dispatch.py plans/gd/2026-06-16-fix-review-chain-bugs/execution-dispatch-map.json
EXECUTION_DISPATCH_MAP_DELIVERABLE: {path: plans/gd/2026-06-16-fix-review-chain-bugs/execution-dispatch-map.json, kind: file, must_exist: true, produced_at: execute_stage, gate: "VALIDATE_CMD exit 0 → 否则 fail-closed 不 dispatch"}   # 消化 r5 P1：execution dispatch_map 是可验证交付物
```

### Wave Matrix（执行阶段，max_parallel=2 硬上限）

| Wave | Steps（同 wave 可并行） | 并行前提 |
|------|------------------------|---------|
| 1 | step-1（共享 P0）, step-3（L3 验证器）| owned_paths 不重叠（bridge/两验证器 vs 12 个 validator）；建立 fail-closed pattern |
| 2 | step-2（L3 fail-open）, step-4（controller+传输）| step-2 blocked_by step-1（复用 pattern）；owned 不重叠 |
| 3 | step-5（L2+收尾）| 单 step 独占 wave |

> 规则：同 wave ≤2 step；串行 step 单独成 wave；`/gd execute` 前必须 `VALIDATE_CMD` exit 0 再 dispatch。

---

## 5b. Step 执行字段（WHERE / WHAT / WHY / VERIFY）

> 从 §5 step 表 + §3 SC + child proposal 提取实质，供 /review2 plan anti-fill 门消费；非凑词。

### Step 1 · 共享 P0 fail-closed（含误拒收口 / fail-closed 的两面）
WHERE: scripts/gd-codex-bridge-review.py; scripts/gd-validate-review-content-evidence.py; scripts/gd-validate-execution-outcome.py
WHAT: bridge N9（:1979/:2085 REQUIRES_CHANGES 误返 exit 0 → 改返 exit 1）；content-evidence V1（verdict=UNKNOWN 时 scope+finding 反造假检查早退 → 判 FAKE_EVIDENCE exit 1）、V16（无 ### Finding 块早退 + --skip-line-ref-check 对 REQUIRES_CHANGES/.json 拒绝）；execution-outcome V3（build_gate+not_run 主动复跑或报应改 pass）、V4（schema 瑕疵仍打印 PHASE2_SKIPPED 不静默跳过）、P2-dup（重复 sc_ref 不静默覆盖）。【误拒收口】content-evidence 不因单条 finding 引用缺文件名/SC-ID 就坍缩整份有效审查为 degraded（SC-12，只精确标记/降级该条）；bridge 不把有效 REQUIRES_CHANGES 映射成 failed_to_run（SC-13）
WHY: 三个共享组件 L2+L3 共用。一面：当前"识别不出/未知态/失败"被当通过，坏代码静默放行（fail-open）。另一面：content-evidence/bridge 又会因 Codex 输出格式小瑕疵误拒/误判整份**有效**审查为 degraded/failed（实测 r2/r4/r6 卡点），让审查链无法确定性产出 verdict。两面都要收口才算修对。
VERIFY: grep -nE "return 0 if .*APPROVED.*else.*0" scripts/gd-codex-bridge-review.py 无命中；构造 UNKNOWN verdict 输入跑 gd-validate-review-content-evidence.py 断言 exit 1
VERIFY: 构造"引用缺文件名/SC-ID 但实质合法"的审查跑 content-evidence，断言不坍缩整审（该条降级、整体 verdict 保留）；构造 writer 输出 REQUIRES_CHANGES 跑 bridge parse，断言映射为 REQUIRES_CHANGES 而非 failed_to_run

### Step 2 · L3 fail-open 收口
WHERE: scripts/gd-review-merge-and-fix-loop.py; scripts/gd-review-router.py; scripts/gd-review-suite-controller.py; scripts/gd-aggregate-codex-cross-review.py
WHAT: merge-loop #3（没改不判 resolved）/N1（_run_bridge_job 失败产 FAILED 不返空）/N2（两处 subprocess 查 returncode）/N8（claude self-review 加载失败不静默空）；router N3（decision None/FAILED 不映射 completed/APPROVED）/N4（returncode≠0 不从 loop_report 取 APPROVED）；suite-controller N5（bridge_exit≠0 强制 verdict FAILED）/N6（aggregate 生成失败 → blocking 不 APPROVED）；aggregate mapped 解析失败 decision→FAILED
WHY: L3 链路任一腿失败/超时坍缩成空列表、或 decision 字段被信任过 returncode → 空 baseline 直接 APPROVED，放行未审代码
VERIFY: 喂失败/超时桩给 merge-loop 断言非空 FAILED；python3 scripts/gd-review-router.py --self-test PASS；构造 bridge_exit≠0 跑 suite-controller 断言 verdict=FAILED

### Step 3 · L3 验证器硬化
WHERE: scripts/gd-validate-{runtime-strict-binding,stage-dispatch-ledger,parent-close-gate,codex-cross-review-aggregate,codex-cross-review-manifest,execution-batch,master-plan-consistency,controller-report,dispatch,child-proposal,subplan-codex-binding,runtime-evidence}.py
WHAT: V2 空壳 anchor 判 fail；V5 jsonschema 缺失不静默降级（exit 2 或告警）；V6 .json 入口不跳过强校验链；V7 hash 读文件真比对；V8 fallback 验 transport_ok/hash 关联；V9 加载真 schema（additionalProperties 生效）；V11 布尔字段 isinstance 校验；V12 ineligible 无条件检查；V13 空 plan/空 jobs 判 fail；V14 必填字段查值非仅查 key
WHY: 验证器是闸门，但"识别不出/缺字段/类型写错/缺 jsonschema"普遍倒向通过 → 闸门纸糊，填表式坏数据端到端溜过
VERIFY: 每个 validator 配正负 fixture——合法输入仍 exit 0、绕过样本（空壳/类型错/假 hash/空 jobs）翻 exit 1
VERIFY: 改 V7 真比对后同步更新 stage-ledger self-test 的假 hash fixture（child 已标注）

### Step 4 · 共享 controller + 传输层
WHERE: scripts/gd-review-controller.py; vendor/l3-transport/scripts/{install-transport,review-result-writer}.sh; vendor/l3-transport/handoff/lib/watch-state.sh
WHAT: controller N7（fut.result() 包 try/except 写 CONVERGENCE_TIMEOUT 不 crash）、N10（git-delta 失败 fail-closed 或注 diff_unavailable，不注假增量）；transport #13（launchctl list 精确查）、T1（writer 关键写失败输出 [REVIEW] ✗ FAILED 不静默 abort）、T-watch（watch-state 用 glob 不用 ls -r 解析）
WHY: controller 是 L2+L3 共享收敛器，崩溃/假增量污染审查；传输层全链共用，静默中断让审查既非通过也非明确失败
VERIFY: 构造 bridge 超时跑 controller 断言输出 CONVERGENCE_TIMEOUT 而非堆栈崩溃；只读盘模拟 writer 写失败断言输出 [REVIEW] ✗ FAILED
VERIFY: 路径含空格跑 watch-state recent_failed_jobs 断言不错乱

### Step 5 · L2 + 收尾
WHERE: scripts/gd-validate-review2-output.py; scripts/gd-audit-legacy-review-trust.py
WHAT: review2-output（MANDATORY_READ 为空时 coverage gate 判 fail 不失效）；audit-legacy-trust I1（兼容 JSON 格式 raw_result_path 解析，尾逗号不致解析失败）
WHY: L2 coverage gate 空读清单时整门失效；audit 把 JSON 格式可信报告误降级，统计失真
VERIFY: 构造空 MANDATORY_READ 跑 review2-output 断言 coverage gate fail；构造 JSON 格式 raw path 跑 audit-legacy-trust 断言归类 trusted_codex_raw

## 5c. Step Task Packets（机器可校验字段）

> 供 `/gd execute` 生成任务包：每 step 给 owned_paths / forbidden_paths / blocked_by / can_parallel_with / required_context / precheck_paths / deliverables / verify。
> 约束（消化 r2 Codex findings）：① `verify[]` 每项内联 cmd + expect（非仅 SC-N）；`/gd execute` 须校验展开后含 cmd/expect，仅 SC-N = closure_ineligible。② `required_context ∩ owned_paths == ∅`（要执行前读现状用 `precheck_paths`，不放 required_context）。owned_paths 互斥已由 G3 校验（§9）。

```yaml
- task_id: step-1-shared-p0-failclosed
  owned_paths:
    - scripts/gd-codex-bridge-review.py
    - scripts/gd-validate-review-content-evidence.py
    - scripts/gd-validate-execution-outcome.py
  forbidden_paths: ["/Users/praise/.claude/**", "schema/**", "prompts/gd-review-standard.md", "其他 step 的 owned_paths"]
  blocked_by: []
  can_parallel_with: [step-3-l3-validators]
  required_context: [prompts/gd-review-standard.md]              # 仅外部依赖，无自身 owned
  precheck_paths: [scripts/gd-codex-bridge-review.py, scripts/gd-validate-review-content-evidence.py, scripts/gd-validate-execution-outcome.py]
  deliverables:
    - {path: scripts/gd-codex-bridge-review.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-review-content-evidence.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-execution-outcome.py, kind: file, must_exist: true}
  verify:
    - {sc: SC-1, cmd: "造 REQUIRES_CHANGES mapped 跑 parse-transport 断言进程 exit 1(行为级)；辅 grep 旧三元 return 无命中", expect: "parse-transport(REQUIRES_CHANGES)→exit 1；grep 无命中"}
    - {sc: SC-2, cmd: "造 verdict=UNKNOWN 文本跑 gd-validate-review-content-evidence.py --target", expect: "exit 1 + FAKE_EVIDENCE_DETECTED"}
    - {sc: SC-3, cmd: "造无 ### Finding 的 REQUIRES_CHANGES 文本 + --skip-line-ref-check 跑同验证器", expect: "exit≠0(拒绝)"}
    - {sc: SC-4, cmd: "造 build_gate+not_run outcome 跑 gd-validate-execution-outcome.py --plan-file", expect: "复跑或报应改pass；schema瑕疵含 PHASE2_SKIPPED"}
    - {sc: SC-12, cmd: "造引用缺文件名/SC-ID 但实质合法的审查跑 gd-validate-review-content-evidence.py", expect: "不坍缩整审；该 finding 降级/精确标记，整体 verdict 保留(正例 fixture pass)"}
    - {sc: SC-13, cmd: "造 writer 输出 REQUIRES_CHANGES 跑 gd-codex-bridge-review.py parse-transport", expect: "映射为 REQUIRES_CHANGES，非 failed_to_run/transport 失败"}

- task_id: step-2-l3-failopen
  owned_paths:
    - scripts/gd-review-merge-and-fix-loop.py
    - scripts/gd-review-router.py
    - scripts/gd-review-suite-controller.py
    - scripts/gd-aggregate-codex-cross-review.py
  forbidden_paths: ["/Users/praise/.claude/**", "schema/**", "prompts/gd-review-standard.md", "其他 step 的 owned_paths"]
  blocked_by: [step-1-shared-p0-failclosed]   # 复用 Step1 建立的 fail-closed 模式
  can_parallel_with: [step-4-shared-controller-transport]
  required_context: [prompts/gd-review-standard.md, scripts/gd-codex-bridge-review.py]   # bridge 属 step-1 owned，对 step-2 是外部参考(N1 镜像 bridge 修法)
  precheck_paths: [scripts/gd-review-merge-and-fix-loop.py, scripts/gd-review-router.py, scripts/gd-review-suite-controller.py, scripts/gd-aggregate-codex-cross-review.py]
  deliverables:
    - {path: scripts/gd-review-merge-and-fix-loop.py, kind: file, must_exist: true}
    - {path: scripts/gd-review-router.py, kind: file, must_exist: true}
    - {path: scripts/gd-review-suite-controller.py, kind: file, must_exist: true}
    - {path: scripts/gd-aggregate-codex-cross-review.py, kind: file, must_exist: true}
  verify:
    - {sc: SC-5, cmd: "喂 timeout/解析失败桩调 merge-loop _run_bridge_job", expect: "返回非空 FAILED(非[])；两 subprocess returncode 被检查"}
    - {sc: SC-6, cmd: "python3 scripts/gd-review-router.py --self-test；造 decision=None mapped 喂 _run_live_codex_bridge", expect: "self-test PASS；None/FAILED 不映射 completed/APPROVED"}
    - {sc: SC-7, cmd: "造 bridge_exit≠0 + 缺 aggregate 跑 gd-review-suite-controller.py(fixture)", expect: "final_decision=FAILED；closure_eligible 缺失默认 False"}

- task_id: step-3-l3-validators
  owned_paths:
    - scripts/gd-validate-runtime-strict-binding.py
    - scripts/gd-validate-stage-dispatch-ledger.py
    - scripts/gd-validate-parent-close-gate.py
    - scripts/gd-validate-codex-cross-review-aggregate.py
    - scripts/gd-validate-codex-cross-review-manifest.py
    - scripts/gd-validate-execution-batch.py
    - scripts/gd-validate-master-plan-consistency.py
    - scripts/gd-validate-controller-report.py
    - scripts/gd-validate-dispatch.py
    - scripts/gd-validate-child-proposal.py
    - scripts/gd-validate-subplan-codex-binding.py
    - scripts/gd-validate-runtime-evidence.py
  forbidden_paths: ["/Users/praise/.claude/**", "schema/**", "prompts/gd-review-standard.md", "其他 step 的 owned_paths"]
  blocked_by: []
  can_parallel_with: [step-1-shared-p0-failclosed]
  required_context: [prompts/gd-review-standard.md, schema/gd-stage-dispatch-ledger.schema.json, schema/gd-controller-report.schema.json]   # 外部 schema，非自身 owned
  precheck_paths: []
  deliverables:   # 覆盖全部 12 个 owned validator + 回归测试（消化 r5 P2：deliverables 须覆盖所有修改文件）
    - {path: scripts/gd-validate-runtime-strict-binding.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-stage-dispatch-ledger.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-parent-close-gate.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-codex-cross-review-aggregate.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-codex-cross-review-manifest.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-execution-batch.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-master-plan-consistency.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-controller-report.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-dispatch.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-child-proposal.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-subplan-codex-binding.py, kind: file, must_exist: true}
    - {path: scripts/gd-validate-runtime-evidence.py, kind: file, must_exist: true}
    - {path: tests/gd-validator-hardening-smoke.sh, kind: file, must_exist: true}   # 正负 fixture 回归
  verify:
    - {sc: SC-8, cmd: "每个 V 验证器跑正负 fixture(空壳anchor/假hash/字符串true/空jobs/缺jsonschema)", expect: "合法 exit 0、绕过样本 exit 1；缺 jsonschema exit 2 或告警"}

- task_id: step-4-shared-controller-transport
  owned_paths:
    - scripts/gd-review-controller.py
    - vendor/l3-transport/scripts/install-transport.sh
    - vendor/l3-transport/scripts/review-result-writer.sh
    - vendor/l3-transport/handoff/lib/watch-state.sh
  forbidden_paths: ["/Users/praise/.claude/**", "schema/**", "prompts/gd-review-standard.md", "其他 step 的 owned_paths"]
  blocked_by: [step-1-shared-p0-failclosed]
  can_parallel_with: [step-2-l3-failopen]
  required_context: [prompts/gd-review-standard.md]   # 仅外部依赖，无自身 owned
  precheck_paths: [scripts/gd-review-controller.py, vendor/l3-transport/scripts/install-transport.sh, vendor/l3-transport/scripts/review-result-writer.sh, vendor/l3-transport/handoff/lib/watch-state.sh]
  active_writer_coverage: "SC-10 修 vendor writer；本会话 bridge WRITER_PATH 修复(commit a12d384)已把 L2/L3 active 路径从旧 ~/.claude/scripts/ 改指 vendor writer → vendor 修复即覆盖 active。verify 须双链确认 active==vendor。"
  deliverables:   # 覆盖全部 4 个 owned 文件（消化 r5 P2）
    - {path: scripts/gd-review-controller.py, kind: file, must_exist: true}
    - {path: vendor/l3-transport/scripts/install-transport.sh, kind: file, must_exist: true}
    - {path: vendor/l3-transport/scripts/review-result-writer.sh, kind: file, must_exist: true}
    - {path: vendor/l3-transport/handoff/lib/watch-state.sh, kind: file, must_exist: true}
  verify:
    - {sc: SC-9, cmd: "造 bridge 超时跑 gd-review-controller.py；造 git 失败", expect: "输出 CONVERGENCE_TIMEOUT 不崩；git fail 注 diff_unavailable:true"}
    - {sc: SC-10, cmd: "bash tests/gd-transport-sweep-smoke.sh；只读盘模拟 writer 写失败；含空格路径跑 watch-state；grep WRITER_PATH scripts/gd-codex-bridge-review.py 确认 active 解析到 vendor", expect: "sweep PASS；writer 输出 [REVIEW] ✗ FAILED；watch-state 不错切；WRITER_PATH 指 vendor(a12d384)"}

- task_id: step-5-l2-cleanup
  owned_paths:
    - scripts/gd-validate-review2-output.py
    - scripts/gd-audit-legacy-review-trust.py
  forbidden_paths: ["/Users/praise/.claude/**", "schema/**", "prompts/gd-review-standard.md", "其他 step 的 owned_paths"]
  blocked_by: []
  can_parallel_with: []
  required_context: [prompts/gd-review-standard.md]   # 仅外部依赖，无自身 owned
  precheck_paths: [scripts/gd-validate-review2-output.py, scripts/gd-audit-legacy-review-trust.py]
  deliverables:
    - {path: scripts/gd-validate-review2-output.py, kind: file, must_exist: true}
    - {path: scripts/gd-audit-legacy-review-trust.py, kind: file, must_exist: true}
  verify:
    - {sc: SC-11, cmd: "造空 MANDATORY_READ 跑 gd-validate-review2-output.py；造 JSON raw path 跑 gd-audit-legacy-review-trust.py", expect: "coverage gate fail；audit 归类 trusted_codex_raw"}
```

## 6. 边界（修改 / 不修改）

修改：见 §5 各 step owned_paths（共 25 个源文件：3 共享 Python + 4 L3 Python + 12 L3 验证器 + 1 controller + 3 传输 bash + 2 L2）。

不修改：
- §4 NON_GOALS 全部（已修的 #1/#11/P2-setdefault；#12 仅可选）
- 旧 `/rev` artifact；`/Users/praise/.claude/**`
- 其他 step 的 owned_paths（跨 step 互斥，见 G3 校验）
- `schema/*.json` 与 `prompts/gd-review-standard.md`（review 标准 SSOT，只消费不改）

---

## 7. 风险与防护

| 风险 | 防护 |
|------|------|
| 改共享 bridge/content-evidence/execution-outcome 破坏 L2 | Step1 完成后 `/review2` + `/gd` 双链各跑一遍回归 |
| N1（merge-loop）只修一半，L3 仍漏 | Step2 SC-5 显式含 N1；修法参照已修的 bridge cmd_run_bridge（G6 仲裁） |
| V7 改 hash 真比对触发 self-test fixture 假 hash 失败 | Step3 同步更新 stage-ledger self-test fixture（child 已标注豁免要求） |
| 验证器硬化误伤合法输入（过严） | 每个 V 修复带正负 fixture：合法输入仍 pass，绕过样本翻 fail |
| dispatch 旧行号偏差 | child 已逐源核实，§4 列出已修项；执行前每个 task 再核对 live 行号 |

---

## 8. 测试计划

### 8a. SC 验证矩阵（自包含）

> 每条 SC 内联 verify 命令 + 期望 exit/输出断言，不再委托外部 child proposal。命令在 `GD_PROJECT_ROOT` 下执行；行为级断言（喂受控失败输入断言退出码），非纯 grep 形状。

| SC | verify 命令 / fixture | 期望 |
|----|----------------------|------|
| SC-1 | **行为级**：造 REQUIRES_CHANGES 的 raw/mapped → `python3 scripts/gd-codex-bridge-review.py parse-transport ...` 断言进程 exit 1；辅以 `grep -nE "return 0 if .*APPROVED.*else.*0" scripts/gd-codex-bridge-review.py` | parse-transport(REQUIRES_CHANGES) → exit 1（证明修对，非仅形状）；grep 无命中 |
| SC-2 | 写 verdict=UNKNOWN 的 review 文本 → `python3 scripts/gd-validate-review-content-evidence.py --target <f>` | exit 1 + stdout 含 `FAKE_EVIDENCE_DETECTED` |
| SC-3 | 写 REQUIRES_CHANGES 无 `### Finding` 的文本 → 同上验证器；再带 `--skip-line-ref-check` + `.json` target | 无 Finding → exit≠0；skip 开关对 REQUIRES_CHANGES/.json → 拒绝 exit≠0 |
| SC-4 | 造 build_gate+not_run 的 outcome.json → `python3 scripts/gd-validate-execution-outcome.py --plan-file <p> <o>` | 复跑命令或报"应改 pass"；任一 schema 瑕疵时 stdout 含 `PHASE2_SKIPPED` |
| SC-5 | 喂 timeout/解析失败桩调 merge-loop `_run_bridge_job` | 返回非空 FAILED（非 `[]`）；两处 subprocess returncode 被检查；没改 finding 不判 resolved |
| SC-6 | `python3 scripts/gd-review-router.py --self-test`；造 decision=None mapped 喂 `_run_live_codex_bridge` | self-test PASS；None/FAILED 不映射 completed/APPROVED；坏 descriptor 独立 failure_code |
| SC-7 | 造 bridge_exit≠0 的 job + 缺 aggregate → 跑 `gd-review-suite-controller.py`（fixture 模式） | final_decision=FAILED；aggregate 生成失败 → blocking；`closure_eligible` 缺失默认 False |
| SC-8 | 每个 V 验证器跑正负 fixture（空壳 anchor / 假 hash / 字符串 "true" / 空 jobs / 缺 jsonschema env） | 合法输入 exit 0、绕过样本 exit 1；缺 jsonschema → exit 2 或 stderr 告警 |
| SC-9 | 造 bridge 超时跑 `gd-review-controller.py`；造 git 失败 | 输出 `CONVERGENCE_TIMEOUT` 不堆栈崩溃；git fail → 注 `diff_unavailable:true` 不注假增量 |
| SC-10 | `bash tests/gd-transport-sweep-smoke.sh`；只读盘模拟 writer 写失败；含空格路径跑 watch-state `recent_failed_jobs` | sweep smoke PASS；writer stdout 含 `[REVIEW] ✗ FAILED`；watch-state 不按空白错切 |
| SC-11 | 造空 MANDATORY_READ 跑 `gd-validate-review2-output.py`；造 JSON 格式 raw_result_path 跑 `gd-audit-legacy-review-trust.py` | coverage gate 判 fail（不失效）；audit 归类 `trusted_codex_raw` |
| SC-12 | 造"单 finding 引用缺文件名/SC-ID 但实质合法"的审查 → `gd-validate-review-content-evidence.py`；并跑正例 fixture（风格各异的合法审查）| 不坍缩整审为 degraded；该条降级/精确标记，整体 verdict 保留；正例 fixture exit 0 |
| SC-13 | 造 writer/codex 输出 `REQUIRES_CHANGES` → `gd-codex-bridge-review.py parse-transport` | 映射为 REQUIRES_CHANGES（非 failed_to_run / transport 失败）|

> 每个修复 step 必须把对应行为断言固化为 committed fixture/test（参照 `tests/gd-transport-sweep-smoke.sh` 模式），不只一次性手测——消化 §7「回归守护」风险。

### 8b. 链路 smoke 回归（修后必跑，全绿）

```bash
bash tests/gd-l1-combined-bundle-smoke.sh
bash tests/gd-review2-plan-routing-smoke.sh
bash tests/gd-l3-regression-v1-fixtures.sh
bash tests/gd-transport-sweep-smoke.sh
python3 scripts/gd-review-router.py --self-test
python3 scripts/gd-codex-bridge-review.py self-test
python3 scripts/gd-validate-dispatch.py plans/gd/2026-06-16-fix-review-chain-bugs/dispatch-map.json
```

---

## 9. Assumptions

- 25 个源文件的 owned_paths 互斥已由 G3 校验确认（无重叠）。
- bridge #1 已 fail-closed（child A 核实 `cmd_run_bridge` 映射全失败态为 FAILED）；本计划不回退该修复。
- N1（merge-loop）、N5（suite-controller `:1155`/`:1122`）、V7（stage-ledger `:100/:133`）根因已由 child 逐源确认。
- 修复均不写 `~/.claude`、不动 schema/review-standard、不启 daemon。
- tests/ 假测试问题（fail-open 没被测出的根因）未纳入本计划，列为后续 wave 2 候选。
