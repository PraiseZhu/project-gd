# Step Plan 草稿 + Task Packets：L3-only 链路 + L3 验证器 + L2 修复

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-step-plan
PARENT_DISPATCH: fix-review-chain-bugs-20260616
PARENT_TRACK: t2-l3-internal
AGENT_ROLE: child_planner

日期：2026-06-16
状态：draft
负责人：Claude 执行；Codex 可选 cross-review

> 本 proposal 只规划 **L3-only（/gd 独有）链路 + L3 验证器 + L2 专属** 文件。
> bridge / content-evidence / execution-outcome / controller / 传输层属共享桶（另一 child），本文件不规划。
> **跨桶同步点**：N1（merge-loop `_run_bridge_job` fail-open）与共享桶 #1（bridge）是同胞拷贝，主 agent 合并时必须放进同一 step 同步改，详见 SC-1 / Task fix-l3-failopen 的同步注记。

---

## 1. 目标链（继承 + 当前 task goal）

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，提升计划/审查/执行/验收效率，Codex 作 cross-review sidecar 降低填表式遗漏（ref GOAL_SOURCE）
CHAIN_GOAL:   用 shared core 固定目标链/SC/任务包/review contract/anti-fill 标准，保证 /gd 各阶段引用同一套契约（ref GOAL_SOURCE）
PHASE_GOAL:   为 GD 审查链路 fail-open/放水类 bug 生成可执行修复计划套件（ref master plan）
TASK_GOAL:    为「L3-only 链路 + L3 验证器 + L2」这一桶的全部 fail-open / returncode 忽略 / 未知态放水 bug 产出 step-plan + 候选 task packets，每条修复标清影响链路与可执行验证方式
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：fail-closed 一致性; returncode 真相源; 类型/缺字段硬校验; hash 真比对; 空块/空 jobs 判 fail
- Domain-specific notes：所有修复必须可被 `python3 <validator> --self-test`（验证器自带）或 grep 锚点验证；修改任何 SC verify 命令前先确认 step / job 字段 schema（见全局 memory `feedback_gd_bridge_dispatch_discipline`）。禁止手工构造 mapped JSON 绕过 parser。

---

## 3. 前置条件

- blocked_by：`—`（本桶与共享桶可并行规划；执行阶段 N1 step 需与共享桶 #1 同 step 落地）
- 必须的 baseline / artifact：本桶 A-F 列出的源文件、`schema/*.json`、`prompts/gd-review-standard.md`（只读标准）
- Hard-stop 条件：若共享桶 bridge 修法（#1）未定，N1 不得单独落地（会留同胞漏洞）

---

## 4. 成功标准（SC，本 step 内的）

> Anti-fill 规则 A：每条 SC 绑定可执行 verify（命令 / 路径 / 断言 / 测试用例之一）。

- [ ] SC-1：merge-loop 四处 fail-open（N1 `_run_bridge_job`、N2 两处 subprocess 不查 returncode、N8 Claude self-review 静默空、#3 baseline 误判 resolved）改为 fail-closed —— bridge/parse 任一非零 returncode 或异常都产出携带哨兵 finding 的非空结果（视角缺失计入 degraded），未被复证为已修的 finding 不得被判 resolved。
  - verify (method: assertion): `grep -nE "except Exception" scripts/gd-review-merge-and-fix-loop.py | wc -l` 改后该函数体内不得再有裸 `except Exception: pass; return []`；并 `grep -n "returncode" scripts/gd-review-merge-and-fix-loop.py`
  - expect: `_run_bridge_job 内出现 returncode 检查；run-bridge 与 parse-transport 两处 returncode 均被断言`
- [ ] SC-2：router 三处 returncode/None 放水（N3 decision=None/FAILED→completed→APPROVED、N4 `_run_live_plan_review` 忽略 subprocess returncode、P2 损坏 descriptor 与真无 artifact 同码）改为 returncode 与 None 都 fail-closed，且坏 descriptor 用独立诊断码。
  - verify (method: assertion): `grep -n 'else "completed"' scripts/gd-review-router.py` 改后 N3 行不再对 None 判 completed；`grep -n "r.returncode\|\.returncode" scripts/gd-review-router.py` N4 路径出现 returncode 断言
  - expect: `decision in (None,"FAILED") → status 非 completed；plan-review subprocess returncode 参与判定`
- [ ] SC-3：suite-controller 三处（N5 bridge_exit 不参与 verdict、N6 aggregate 失败时 synthetic summary 可产 APPROVED、P2 `_secondary_gate` closure_eligible 缺失默认 True）改为 bridge_exit!=0 阻断 final_decision、aggregate 失败强制非 APPROVED、closure_eligible 缺失默认 fail-closed。
  - verify (method: command): `python3 scripts/gd-review-suite-controller.py --self-test 2>&1 | tail -5`（若无 --self-test 用 `bash tests/gd-l3-regression-v1-fixtures.sh`）
  - expect: `自测/回归 fixtures 全 PASS，且新增的 bridge_exit!=0 fixture 得 REQUIRES_CHANGES/FAILED`
- [ ] SC-4：aggregate（D `:183-191`）mapped 解析失败时 decision 不留 none 静默通过，置 FAILED 并标 blocking。
  - verify (method: assertion): `grep -n "gd_review_decision\|FAILED" scripts/gd-aggregate-codex-cross-review.py` mapped 不可读分支显式 set FAILED
  - expect: `mapped 不可读 → entry["gd_review_decision"]="FAILED" 且 codex_requires_changes=True`
- [ ] SC-5：L3 验证器「降级类」（V5/V8/V9）—— 缺 jsonschema 不静默弱校验，改为告警或 exit；manifest 死代码 SCHEMA_PATH 实际加载并使 additionalProperties 生效；aggregate fallback 验 transport_ok/hash 关联。
  - verify (method: command): `python3 -c "import sys; sys.argv=['x']; ..."` 改用 grep 锚点：`grep -n "additionalProperties\|jsonschema\|SCHEMA_PATH" scripts/gd-validate-codex-cross-review-manifest.py`
  - expect: `manifest validator 实际读取 SCHEMA_PATH 并启用 additionalProperties；stage-ledger/aggregate 缺 jsonschema 时打印告警到 stderr`
- [ ] SC-6：L3 验证器「类型/恒真类」（V11 `is True` 身份比较、V13 缺 inventory 块 SKIPPED 恒 PASS + step_plans=[] 恒空 PASS、V14 必填字段只查 key 不查值）—— 用 isinstance/真值校验替换身份比较，空块/空 step_plans 判 fail，必填字段查非空值。
  - verify (method: assertion): `grep -n "is True" scripts/gd-validate-execution-batch.py` 改后 must_exist/verified 用真值或 `in (True,"true",1)` 容错；`grep -n "SKIPPED_LEGACY_PLAN\|step_plans" scripts/gd-validate-master-plan-consistency.py`
  - expect: `execution-batch 不再以 is True 漏判 "true"/1；master-plan 空 inventory 不再无条件 return 0`
- [ ] SC-7：L3 验证器「空壳/hash 类」（V2 空壳 anchor 块体无 validator 调用照过、V6 传 .json 走 validate_closure_json 跳过强校验链、V7 hash 只验格式不读文件比对、V12 ineligible 被 if is_top_approved 包住 + claude_review_status 非白名单溜过）—— 空壳 anchor 报 error、JSON 模式补强校验链、hash 真读文件比对、ineligible 检查不依赖 top_approved、claude_review_status 白名单收敛。
  - verify (method: assertion): `grep -n "_SHA256_RE.match" scripts/gd-validate-stage-dispatch-ledger.py` 改后 result_hash/merge_report_hash 行附加读 result_path 文件并 sha256 比对；`grep -n "is_top_approved\|INELIGIBLE_STATUSES" scripts/gd-validate-parent-close-gate.py` ineligible 循环移出 `if is_top_approved` 块
  - expect: `stage-ledger hash 真比对（"a"*64 不再过）；parent-close-gate ineligible 检查无条件执行`
- [ ] SC-8：L3 验证器 P2 桶（parent-close-gate `:519` 坏 JSON 当无约束、dispatch `:170` 空 deliverables 无校验、controller-report `:127` schema_version=="1.0" 直接 return 0、child-proposal `:148` verify.cmd 只查长度+黑名单、subplan-codex-binding `:62` jobs=[] 静默通过、runtime-evidence `:83` parent_status 不核对）—— 坏 JSON 判 fail、空 deliverables 判 fail、1.0 走实质校验、verify.cmd 加可执行性最小断言、空 jobs 判 fail、parent_status 强制核对。
  - verify (method: command): `for v in gd-validate-parent-close-gate gd-validate-dispatch gd-validate-controller-report gd-validate-child-proposal gd-validate-subplan-codex-binding gd-validate-runtime-evidence; do python3 -c "import ast; ast.parse(open('scripts/'+'$v'+'.py').read()); print('$v ok')"; done`
  - expect: `六个文件语法均 ok；空 jobs / 坏 JSON / 1.0 各自 fixture 返回非 0`
- [ ] SC-9：L2 专属（review2-output `:80-82` release_closure 的 MANDATORY_READ 为空 → coverage gate 失效；I1 audit-legacy-review-trust `:98-107` JSON raw path 尾逗号解析失败导致可信报告被降级）—— release_closure profile 下 mandatory_paths 为空判为 coverage 缺失（不得直接放行）；raw path 解析对尾逗号/JSON 片段健壮（低优先，方向保守）。
  - verify (method: assertion): `grep -n "mandatory_paths\|release_closure" scripts/gd-validate-review2-output.py` 改后空 mandatory_paths 在 release_closure profile 下追加 error；`grep -n "raw_result_path\|rstrip\|strip" scripts/gd-audit-legacy-review-trust.py`
  - expect: `release_closure + 空 mandatory_paths → 非空 errors；raw path 解析容忍尾逗号`

---

## 5. 非目标

- 不修改共享桶文件（bridge / content-evidence / execution-outcome / controller / 传输层）。N1 修法与共享桶 #1 对齐但落地由主 agent 合并到同一 step。
- 不改 `prompts/gd-review-standard.md`、`schema/*.json`（只消费，shared core 不可改）。
- 不改 `~/.claude/**`、不启动 daemon/hook/cron。
- 不重写验证器架构，只补 fail-closed 与真校验；不引入新依赖（jsonschema 已可用，但「缺失则告警/exit」逻辑须保留以防部署环境差异）。

---

## 6. 实现步骤

### Step.1 — L3 fail-open 收口（merge-loop / router / suite-controller / aggregate）

```text
WHERE: scripts/gd-review-merge-and-fix-loop.py（:471-477 #3, :516-567 N1, :562-564 N2, :959-966 N8）
       scripts/gd-review-router.py（:382-412 N4, :525-526+:1009 N3, :144-173 P2）
       scripts/gd-review-suite-controller.py（:318-324 N5, :1066-1082 N6, :208-218 P2）
       scripts/gd-aggregate-codex-cross-review.py（:183-191 D）
WHAT:  把「失败→空列表/无问题」「returncode 被忽略」「未知态默认通过」三类病灶统一改 fail-closed：
       (1) _run_bridge_job：捕获 run-bridge/parse-transport 的 CompletedProcess，returncode!=0 或异常 → 返回携带哨兵 finding 的非空 list（含 severity=error），不再 except: pass return []；
       (2) N2：两处 subprocess 显式断言 returncode==0 才认 mapped_out 有效；
       (3) N8：claude_review 加载失败时不静默 findings_claude=[]，记 degraded 标志参与 merge；
       (4) #3 update_baseline_statuses：仅当本轮证据足以复证已修才判 resolved（区分「未被复证」与「确认修复」），否则保持 unresolved；
       (5) router N3：decision in (None,"FAILED") → status 非 completed，:1009 APPROVED 条件收紧；
       (6) router N4：_run_live_plan_review 把 subprocess returncode 纳入 downstream_decision；
       (7) router P2：坏 descriptor 用独立诊断码（如 corrupt_descriptor）区分于 no_artifact；
       (8) suite N5：final_decision 计算时 bridge_exit!=0 强制非 APPROVED（不仅写 ledger job_status）；
       (9) suite N6：aggregate 失败重建 synthetic summary 后，rc_agg!=0 / aggregate 不存在一律封顶非 APPROVED；
       (10) suite P2 _secondary_gate：summary.get("closure_eligible", True) 改默认 False（缺失即 fail-closed）；
       (11) aggregate D：mapped 不可读分支显式 set gd_review_decision=FAILED + codex_requires_changes=True。
WHY:   这是 L3 唯一收敛/路由/仲裁层；任一处「失败被当成通过」直接让 /gd review 放水，是本桶最高危。N1 与共享桶 #1 同源，必须同步改否则 L3 仍漏。
VERIFY: SC-1 / SC-2 / SC-3 / SC-4 的 verify 命令；并 `bash tests/gd-l3-regression-v1-fixtures.sh`
```

### Step.2 — L3 验证器硬化（降级 / 类型 / 空壳 / hash 四类）

```text
WHERE: 降级类: gd-validate-stage-dispatch-ledger.py(:156-164 V5), gd-validate-codex-cross-review-aggregate.py(:23-39 V8), gd-validate-codex-cross-review-manifest.py(:11 V9)
       类型/恒真类: gd-validate-execution-batch.py(:438,459,483 V11), gd-validate-master-plan-consistency.py(:342-352 V13), gd-validate-controller-report.py(:64-82 V14)
       空壳/hash类: gd-validate-runtime-strict-binding.py(:188-194 V2), gd-validate-parent-close-gate.py(:923-926 V6 / :894-909 V12), gd-validate-stage-dispatch-ledger.py(:99-101,:133-134 V7)
WHAT:  (V5) 缺 jsonschema 时 _validate_with_jsonschema 返回 None → 调用方打印告警到 stderr（不静默降级到弱校验）；
       (V8) aggregate fallback _structural_check 增加 transport_ok / hash 关联字段校验；
       (V9) manifest validator 实际 json.load(SCHEMA_PATH) 并经 jsonschema(additionalProperties) 校验，移除死代码常量；
       (V11) execution-batch :438/:459/:483 把 `is True` 改为真值或显式集合容错（must_exist/verified ∈ {True}），并对 "true"/1 走显式归一而非身份比较漏过；
       (V13) master-plan 缺 gd-step-plan-inventory 块不再 SKIPPED+return 0，判 FAIL；step_plans==[] 不得恒空 PASS；
       (V14) controller-report find_missing_required_field 对必填字段同时查「存在且值非 null/非空串」；
       (V2) runtime-strict-binding 空壳 anchor（块体内无 validator 调用）由 warning 升为 error；
       (V6) parent-close-gate main 传 .json 时不直接走 validate_closure_json 跳过链，补 parse_parent_status/aggregate/binding 强校验；
       (V12) ineligible 检查移出 `if is_top_approved` 包裹（无条件执行）；claude_review_status 收敛到白名单，非白名单词判 fail（堵 codex-only）；
       (V7) stage-dispatch-ledger result_hash / merge_report_hash 在格式校验后读取对应 result_path/merge_report_path 文件做 sha256 真比对（"a"*64 不再过；文件不存在判 fail）。
WHY:   验证器是闭环最后一道闸；降级/恒真/空壳/假 hash 任一处放水，上游 fail-open 即便修了也会在闭环 gate 被重新放行。
VERIFY: SC-5 / SC-6 / SC-7 的 verify 命令；改 V7 时注意 self-test fixture `_GOOD_JOB.result_hash="a"*64` 需同步给真实文件或调整 fixture（见 Task fix-l3-validators-shell required_context）。
```

### Step.3 — L3 验证器 P2 残项 + L2 收尾

```text
WHERE: gd-validate-parent-close-gate.py(:519 坏 JSON 当无约束)
       gd-validate-dispatch.py(:170 空 deliverables 无校验)
       gd-validate-controller-report.py(:127→实为 :169-170 schema_version=="1.0" return 0)
       gd-validate-child-proposal.py(:148 verify.cmd 只查长度+黑名单)
       gd-validate-subplan-codex-binding.py(:62 jobs=[] 静默通过)
       gd-validate-runtime-evidence.py(:83 parent_status 不核对)
       gd-validate-review2-output.py(:80-82 release_closure MANDATORY_READ 空→gate 失效) [L2]
       gd-audit-legacy-review-trust.py(:98-107 JSON raw path 尾逗号解析失败) [L2 / I1 低优先]
WHAT:  (parent-close-gate :519) JSONDecodeError 返回 None 后调用方不得当「无约束通过」，判 fail；
       (dispatch :170) deliverables==[] 对需要交付的 track 判 fail（区分明确「无交付」与「漏填」）；
       (controller-report 1.0) schema_version=="1.0" 不再直接 return 0，走与 1.1 对齐的必填+job 字段实质校验子集；
       (child-proposal :148) verify.cmd 在 ≥3 字符与黑名单之外，增加最小可执行性断言（含命令/路径/断言 token 之一）；
       (subplan-codex-binding :62) jobs==[] 判 fail（绑定为空＝未审）；
       (runtime-evidence :83) for_parent_status 为空时仍核对 parent_status 在 VALID_PARENT_STATUSES 且与上下文一致；
       (review2-output L2) profile==release_closure 且 mandatory_paths 为空 → 追加 coverage 缺失 error（不直接 return errors 放行）；
       (audit-legacy-trust I1) raw_result_path 解析对尾逗号/JSON 片段做 rstrip(',') 与健壮 split，避免可信报告被误降级（方向保守，最低优先）。
WHY:   这些 P2 各自在边缘输入（坏 JSON / 空数组 / 旧版本号 / 空 mandatory）下放水；单独看低危，合在一起构成「构造特定空/坏输入即过闸」的系统性绕过面。
VERIFY: SC-8 / SC-9 的 verify 命令。
```

> 实现步骤动词均为具体动作（捕获 returncode / 改默认值 / 读文件比对 / 移出 if 块 / 追加 error），无「完善/优化/系统性/全面/增强」单独成句。

---

## 7. Task Packet 拆分

| task_id | agent_role | owned_paths | blocked_by | can_parallel_with |
|---------|-----------|------------|-----------|-------------------|
| fix-l3-failopen | implementer | scripts/gd-review-merge-and-fix-loop.py, scripts/gd-review-router.py, scripts/gd-review-suite-controller.py, scripts/gd-aggregate-codex-cross-review.py | shared-bucket#1（仅 N1 行同步） | fix-l3-validators-shell |
| fix-l3-validators-shell | implementer | scripts/gd-validate-stage-dispatch-ledger.py, scripts/gd-validate-codex-cross-review-aggregate.py, scripts/gd-validate-codex-cross-review-manifest.py, scripts/gd-validate-execution-batch.py, scripts/gd-validate-master-plan-consistency.py, scripts/gd-validate-controller-report.py, scripts/gd-validate-runtime-strict-binding.py, scripts/gd-validate-parent-close-gate.py | — | fix-l3-failopen |
| fix-l3-validators-p2 | implementer | scripts/gd-validate-dispatch.py, scripts/gd-validate-child-proposal.py, scripts/gd-validate-subplan-codex-binding.py, scripts/gd-validate-runtime-evidence.py | fix-l3-validators-shell（避免 parent-close-gate / controller-report owned 冲突需先落地） | — |
| fix-l2-coverage | implementer | scripts/gd-validate-review2-output.py, scripts/gd-audit-legacy-review-trust.py | — | fix-l3-failopen, fix-l3-validators-shell |

> 注：controller-report.py（V14 + 1.0 早退）与 parent-close-gate.py（V6/V12 + :519）均出现在 fix-l3-validators-shell 与 P2 两处需求中。为避免 owned_paths 重叠，**两文件整体归 fix-l3-validators-shell**；故 fix-l3-validators-p2 设 blocked_by=fix-l3-validators-shell（其 owned 不含这两文件，但需读 shell task 落地后的成品做一致性确认）。下方 task packets 已据此固定 owned_paths 无重叠。

---

## 8. 候选 Task Packets

### Task Packet: fix-l3-failopen

```yaml
task_id: fix-l3-failopen
agent_role: implementer
parent_step: Step.1
parent_plan: plans/gd/2026-06-16-fix-review-chain-bugs/step-plans/<master>.md
owned_paths:
  - scripts/gd-review-merge-and-fix-loop.py
  - scripts/gd-review-router.py
  - scripts/gd-review-suite-controller.py
  - scripts/gd-aggregate-codex-cross-review.py
required_context:
  - prompts/gd-review-standard.md
  - schema/gd-review-result.schema.json
  - schema/gd-codex-cross-review-aggregate.schema.json
forbidden_paths:
  - "/Users/praise/.claude/**"
  - 共享桶文件（bridge/content-evidence/execution-outcome/controller/transport）
```

具体 bug 列表 + 修法：
1. **N1 `gd-review-merge-and-fix-loop.py:516-567` `_run_bridge_job`**：`except Exception: pass; return []` fail-open（与共享桶 #1 同胞）。修：捕获两个 subprocess 的 CompletedProcess，`run-bridge`/`parse-transport` returncode!=0 或异常 → 返回 `[{"reviewer":"codex_bridge","severity":"error","description":"<错误>", "fail_closed":True}]` 非空 list；与共享桶 #1 用同一 fail-closed 修法（主 agent 合并同 step）。
2. **N2 `:562-564`**：两处 subprocess 不查 returncode，只看 `mapped_out.exists()`。修：先断言 `r.returncode==0`，否则即便文件存在也按失败处理。
3. **N8 `:959-966`**：claude self-review 加载失败静默 `findings_claude=[]`。修：加载失败记 `claude_degraded=True`，merge 时该视角缺失计入 degraded（不得 APPROVED）。
4. **#3 `:471-477` `update_baseline_statuses`**：本轮 codex 没再报即判 resolved。修：仅在有正向复证（如该 finding 对应文件/行已变更证据）时判 resolved，否则保留 unresolved。
5. **N3 `gd-review-router.py:525-526` + `:1009`**：decision=None/FAILED → completed → APPROVED。修：`decision in (None,"FAILED")` → status 非 completed；:1009 APPROVED 条件去掉 `None` 放行。
6. **N4 `:382-412` `_run_live_plan_review`**：忽略 subprocess returncode，从 loop_report 取 APPROVED。修：`r.returncode!=0` → downstream_decision 封顶 FAILED。
7. **P2 `:144-173`**：坏 descriptor 与真无 artifact 同码 `no_artifact`。修：JSONDecodeError/结构损坏返回独立 `corrupt_descriptor`，调用方区分诊断。
8. **N5 `gd-review-suite-controller.py:318-324`（影响 :1155 final_decision）**：bridge_exit 只进 ledger 不参与 verdict。修：final_decision 计算前若任一 job `bridge_exit!=0` → 强制非 APPROVED。
9. **N6 `:1066-1082` main**：aggregate 失败 synthetic summary 可产 APPROVED。修：`rc_agg!=0` 或 aggregate 不存在 → primary_verdict 封顶 FAILED。
10. **P2 `:208-218` `_secondary_gate`**：`closure_eligible` 缺失默认 True。修：`summary.get("closure_eligible", False)`（缺失即 fail-closed）。
11. **D `gd-aggregate-codex-cross-review.py:183-191`**：mapped 解析失败 decision 留 none。修：except 分支 set `entry["gd_review_decision"]="FAILED"` + `codex_requires_changes=True`。

verify：
```yaml
verify:
  - sc_ref: SC-1
    method: assertion
    cmd: "grep -n 'returncode' scripts/gd-review-merge-and-fix-loop.py"
    expect: ">=2 处 returncode 断言（run-bridge + parse-transport）"
  - sc_ref: SC-2
    method: assertion
    cmd: "grep -n 'else \"completed\"' scripts/gd-review-router.py"
    expect: "N3 行不再对 None 判 completed"
  - sc_ref: SC-3
    method: command
    cmd: "bash tests/gd-l3-regression-v1-fixtures.sh"
    expect: "全 PASS（含 bridge_exit!=0 新 fixture 得 FAILED）"
  - sc_ref: SC-4
    method: assertion
    cmd: "grep -n 'gd_review_decision' scripts/gd-aggregate-codex-cross-review.py"
    expect: "mapped 不可读分支显式 set FAILED"
```

### Task Packet: fix-l3-validators-shell

```yaml
task_id: fix-l3-validators-shell
agent_role: implementer
parent_step: Step.2
parent_plan: plans/gd/2026-06-16-fix-review-chain-bugs/step-plans/<master>.md
owned_paths:
  - scripts/gd-validate-stage-dispatch-ledger.py
  - scripts/gd-validate-codex-cross-review-aggregate.py
  - scripts/gd-validate-codex-cross-review-manifest.py
  - scripts/gd-validate-execution-batch.py
  - scripts/gd-validate-master-plan-consistency.py
  - scripts/gd-validate-controller-report.py
  - scripts/gd-validate-runtime-strict-binding.py
  - scripts/gd-validate-parent-close-gate.py
required_context:
  - schema/gd-codex-cross-review-manifest.schema.json
  - schema/gd-codex-cross-review-aggregate.schema.json
  - prompts/gd-review-standard.md
forbidden_paths:
  - "/Users/praise/.claude/**"
```

具体 bug 列表 + 修法：
- **V5 `gd-validate-stage-dispatch-ledger.py:156-164`**：缺 jsonschema 静默降级。修：`_validate_with_jsonschema` 返回 None 时调用方 `print("WARN: jsonschema unavailable, manual fallback", file=sys.stderr)`。
- **V7 `:99-101`,`:133-134`**：result_hash / merge_report_hash 只验格式不读文件。修：格式校验通过后读取 result_path / merge_report_path 文件做 `hashlib.sha256(...).hexdigest()` 真比对，不匹配或文件缺失判 error。**同步**：self-test fixture `_GOOD_JOB.result_hash="a"*64`、`_GOOD_MERGE.merge_report_hash="b"*64` 需改为对真实临时文件计算的 hash，或在 fixture 模式跳过物理比对（须显式标注 fixture 豁免，不得默认跳过 live）。
- **V8 `gd-validate-codex-cross-review-aggregate.py:23-39`**：fallback 不验 transport_ok/hash 关联。修：`_structural_check` 增加 jobs[].transport_ok 与 mapped_result_hash 存在性/关联校验。
- **V9 `gd-validate-codex-cross-review-manifest.py:11`**：SCHEMA_PATH 死代码，additionalProperties 没生效。修：实际 `json.load(SCHEMA_PATH)` 并用 jsonschema Draft7 校验（含 additionalProperties=false）；缺 jsonschema 时告警+保留手工必填校验。
- **V11 `gd-validate-execution-batch.py:438,459,483`**：`is True` 身份比较被 "true"/1 绕过。修：`dlv.get("must_exist") is True` → 显式归一 `dlv.get("must_exist") in (True,)`（拒绝字符串/数字伪真）并对非布尔类型报 error（堵 "true"/1 既不静默通过也不静默漏判）。
- **V13 `gd-validate-master-plan-consistency.py:342-352`**：缺 inventory 块 SKIPPED return 0；step_plans=[] 恒空 PASS。修：缺块判 FAIL（或显式 require 标志），step_plans==[] 判 FAIL。
- **V14 `gd-validate-controller-report.py:64-82`**：必填字段只查 key。修：`find_missing_required_field` 对必填字段同时校验值非 None / 非空串。
- **V2 `gd-validate-runtime-strict-binding.py:188-194`**：空壳 anchor 照过（warning）。修：块体内无 validator 调用由 `warnings.append` 升为 `errors.append`。
- **V6 `gd-validate-parent-close-gate.py:923-926`**：传 .json 走 validate_closure_json 跳过强校验链。修：JSON 模式补 parse_parent_status / aggregate / binding 强校验（不直接短路）。
- **V12 `:894-909`**：ineligible 被 `if is_top_approved` 包住；claude_review_status 非白名单溜过。修：ineligible 循环移出 `if is_top_approved`（无条件执行）；claude_review_status 收敛白名单 `{approved, requires_changes, failed}`，非白名单判 fail。

verify：
```yaml
verify:
  - sc_ref: SC-5
    method: assertion
    cmd: "grep -n 'additionalProperties\\|SCHEMA_PATH' scripts/gd-validate-codex-cross-review-manifest.py"
    expect: "实际加载 SCHEMA_PATH 且 additionalProperties 生效"
  - sc_ref: SC-6
    method: assertion
    cmd: "grep -n 'is True' scripts/gd-validate-execution-batch.py"
    expect: "must_exist/verified 不再用裸 is True 漏判 'true'/1"
  - sc_ref: SC-7
    method: assertion
    cmd: "grep -n '_SHA256_RE.match' scripts/gd-validate-stage-dispatch-ledger.py"
    expect: "hash 行附加读 result_path 文件 sha256 真比对"
  - sc_ref: SC-7
    method: command
    cmd: "python3 scripts/gd-validate-stage-dispatch-ledger.py --self-test"
    expect: "self-test PASS（fixture hash 已同步真实文件或显式 fixture 豁免）"
```

### Task Packet: fix-l3-validators-p2

```yaml
task_id: fix-l3-validators-p2
agent_role: implementer
parent_step: Step.3
parent_plan: plans/gd/2026-06-16-fix-review-chain-bugs/step-plans/<master>.md
owned_paths:
  - scripts/gd-validate-dispatch.py
  - scripts/gd-validate-child-proposal.py
  - scripts/gd-validate-subplan-codex-binding.py
  - scripts/gd-validate-runtime-evidence.py
blocked_by:
  - fix-l3-validators-shell
required_context:
  - templates/gd-task-packet-template.md
  - prompts/gd-review-standard.md
forbidden_paths:
  - "/Users/praise/.claude/**"
```

具体 bug 列表 + 修法：
- **dispatch `gd-validate-dispatch.py:170`**：空 deliverables 无校验。修：`deliverables==[]` 对需交付 track 判 error（与 anti-fill 规则一致）。
- **child-proposal `gd-validate-child-proposal.py:148`**：verify.cmd 只查长度+黑名单。修：在 ≥3 字符与 anti-fill 黑名单外，增加最小可执行性断言（cmd 须含命令/路径/断言/测试 token 之一，否则 error）。
- **subplan-codex-binding `gd-validate-subplan-codex-binding.py:62`**：jobs=[] 静默通过。修：`jobs==[]` 判 error（绑定为空＝未审，fail-closed）。
- **runtime-evidence `gd-validate-runtime-evidence.py:83`**：for_parent_status 为空时不核对 parent_status。修：即便 for_parent_status 为空，仍要求 parent_status ∈ VALID_PARENT_STATUSES 且与已知上下文一致。

verify：
```yaml
verify:
  - sc_ref: SC-8
    method: command
    cmd: "for v in gd-validate-dispatch gd-validate-child-proposal gd-validate-subplan-codex-binding gd-validate-runtime-evidence; do python3 -c \"import ast; ast.parse(open('scripts/'+'$v'+'.py').read()); print('$v ok')\"; done"
    expect: "四文件语法 ok"
  - sc_ref: SC-8
    method: assertion
    cmd: "grep -n 'jobs' scripts/gd-validate-subplan-codex-binding.py"
    expect: "jobs==[] 分支显式判 error"
```

### Task Packet: fix-l2-coverage

```yaml
task_id: fix-l2-coverage
agent_role: implementer
parent_step: Step.3
parent_plan: plans/gd/2026-06-16-fix-review-chain-bugs/step-plans/<master>.md
owned_paths:
  - scripts/gd-validate-review2-output.py
  - scripts/gd-audit-legacy-review-trust.py
required_context:
  - prompts/gd-review-standard.md
forbidden_paths:
  - "/Users/praise/.claude/**"
```

具体 bug 列表 + 修法：
- **L2 `gd-validate-review2-output.py:80-82`**：release_closure 的 MANDATORY_READ 为空 → coverage gate 整个失效（`if not mandatory_paths: return errors`）。修：`profile == "release_closure"` 且 `mandatory_paths` 为空 → 追加 error（release_closure 必须有 mandatory_reads，空＝配置缺失，不得放行）；非 release_closure profile 维持原 no-coverage-required 行为。
- **I1 `gd-audit-legacy-review-trust.py:98-107`（低优先，方向保守）**：JSON 格式 raw path（尾逗号）解析不出 → 可信报告被降级。修：`path_part` 解析增加 `rstrip(',').strip()`，并对 JSON 片段做健壮提取，避免误把可信报告判为不可信。仅放宽误降级方向，不放宽真不可信判定。

verify：
```yaml
verify:
  - sc_ref: SC-9
    method: assertion
    cmd: "grep -n 'release_closure\\|mandatory_paths' scripts/gd-validate-review2-output.py"
    expect: "release_closure + 空 mandatory_paths 追加 error"
  - sc_ref: SC-9
    method: command
    cmd: "python3 -c \"import ast; ast.parse(open('scripts/gd-validate-audit-legacy-review-trust.py'.replace('validate-','')).read()); print('ok')\" 2>/dev/null || python3 -c \"import ast; ast.parse(open('scripts/gd-audit-legacy-review-trust.py').read()); print('ok')\""
    expect: "ok（语法合法）"
```

---

## 9. 边界（修改 / 不修改）

修改（本桶 owned，全部 L3-only 或 L2）：
- scripts/gd-review-merge-and-fix-loop.py, scripts/gd-review-router.py, scripts/gd-review-suite-controller.py, scripts/gd-aggregate-codex-cross-review.py
- scripts/gd-validate-stage-dispatch-ledger.py, scripts/gd-validate-codex-cross-review-aggregate.py, scripts/gd-validate-codex-cross-review-manifest.py, scripts/gd-validate-execution-batch.py, scripts/gd-validate-master-plan-consistency.py, scripts/gd-validate-controller-report.py, scripts/gd-validate-runtime-strict-binding.py, scripts/gd-validate-parent-close-gate.py
- scripts/gd-validate-dispatch.py, scripts/gd-validate-child-proposal.py, scripts/gd-validate-subplan-codex-binding.py, scripts/gd-validate-runtime-evidence.py
- scripts/gd-validate-review2-output.py, scripts/gd-audit-legacy-review-trust.py

不修改：
- 共享桶文件（bridge/content-evidence/execution-outcome/controller/transport）
- prompts/gd-review-standard.md、schema/*.json
- /Users/praise/.claude/**
- 其他 step / 其他 child 的 owned_paths

---

## 10. 风险与防护

| 风险 | 防护 |
|------|------|
| N1 单独落地，共享桶 #1 仍漏 → L3 仍有同胞 fail-open | 主 agent 合并时把 N1 与共享桶 #1 放进同一 step；本 proposal 在 Step.1 / SC-1 / Task fix-l3-failopen 三处标注同步点 |
| V7 改真比对后 self-test fixture（"a"*64 假 hash）大面积红 | Task fix-l3-validators-shell 明列 fixture 同步要求：改 fixture 用真实临时文件 hash，或 fixture 模式显式豁免（不得默认跳过 live） |
| controller-report.py / parent-close-gate.py 在 shell 与 p2 两 task 都被需求 → owned 重叠 | 两文件整体归 fix-l3-validators-shell；p2 task owned 不含这两文件并 blocked_by shell |
| fail-closed 收紧后真实正常流程被误判 FAILED（过度收紧） | 每条修法保留「有正向证据才判通过」语义，区分「未复证」与「确认通过」；用回归 fixtures 验证既有正常路径仍 PASS |

---

## 11. 测试计划

```bash
# 语法门
for f in gd-review-merge-and-fix-loop gd-review-router gd-review-suite-controller gd-aggregate-codex-cross-review \
         gd-validate-stage-dispatch-ledger gd-validate-codex-cross-review-aggregate gd-validate-codex-cross-review-manifest \
         gd-validate-execution-batch gd-validate-master-plan-consistency gd-validate-controller-report \
         gd-validate-runtime-strict-binding gd-validate-parent-close-gate gd-validate-dispatch \
         gd-validate-child-proposal gd-validate-subplan-codex-binding gd-validate-runtime-evidence \
         gd-validate-review2-output gd-audit-legacy-review-trust; do
  python3 -c "import ast; ast.parse(open('scripts/'+'$f'+'.py').read()); print('$f ok')"
done

# 验证器自测（带 --self-test 的）
python3 scripts/gd-validate-stage-dispatch-ledger.py --self-test
python3 scripts/gd-validate-controller-report.py --self-test 2>/dev/null || true

# L3 回归 + 路由 self-test
bash tests/gd-l3-regression-v1-fixtures.sh
python3 scripts/gd-review-router.py --self-test
```

---

## 12. Assumptions

- jsonschema 当前环境可用（已实测），但「缺失即告警/exit」逻辑须保留——部署到 codex-watch daemon 环境时 site-packages 可能不同。
- N1 与共享桶 #1 是同源拷贝，修法一致由主 agent 在合并阶段保证；本 child 只在本桶内给出 fail-closed 修法草案。
- 各验证器均以「returncode/exit code 为真相、未知态 fail-closed」为统一原则，符合修复总纲三类病灶。

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "frcb-t2-l3-internal",
  "parent_dispatch_id": "fix-review-chain-bugs-20260616",
  "parent_track_id": "t2-l3-internal",
  "agent_role": "child_planner",
  "output_status": "completed",
  "blocked_reason": null,
  "summary_cn": "为 L3-only 链路（merge-loop/router/suite-controller/aggregate）+ 18 个 L3 验证器 + L2（review2-output/audit-legacy-trust）的 fail-open/returncode 忽略/未知态放水 bug 产出 step-plan 与 4 个 task packets，按三类系统病（失败≠空列表、returncode 是真相源、未知态 fail-closed）统一收口，并标注 N1 与共享桶 #1 的同步落地点。",
  "task_packets": [
    {"task_id": "fix-l3-failopen", "owned_paths": ["scripts/gd-review-merge-and-fix-loop.py", "scripts/gd-review-router.py", "scripts/gd-review-suite-controller.py", "scripts/gd-aggregate-codex-cross-review.py"], "required_context": ["prompts/gd-review-standard.md", "schema/gd-review-result.schema.json", "schema/gd-codex-cross-review-aggregate.schema.json"]},
    {"task_id": "fix-l3-validators-shell", "owned_paths": ["scripts/gd-validate-stage-dispatch-ledger.py", "scripts/gd-validate-codex-cross-review-aggregate.py", "scripts/gd-validate-codex-cross-review-manifest.py", "scripts/gd-validate-execution-batch.py", "scripts/gd-validate-master-plan-consistency.py", "scripts/gd-validate-controller-report.py", "scripts/gd-validate-runtime-strict-binding.py", "scripts/gd-validate-parent-close-gate.py"], "required_context": ["schema/gd-codex-cross-review-manifest.schema.json", "schema/gd-codex-cross-review-aggregate.schema.json", "prompts/gd-review-standard.md"]},
    {"task_id": "fix-l3-validators-p2", "owned_paths": ["scripts/gd-validate-dispatch.py", "scripts/gd-validate-child-proposal.py", "scripts/gd-validate-subplan-codex-binding.py", "scripts/gd-validate-runtime-evidence.py"], "required_context": ["templates/gd-task-packet-template.md", "prompts/gd-review-standard.md"]},
    {"task_id": "fix-l2-coverage", "owned_paths": ["scripts/gd-validate-review2-output.py", "scripts/gd-audit-legacy-review-trust.py"], "required_context": ["prompts/gd-review-standard.md"]}
  ],
  "sc_refs": ["SC-1", "SC-2", "SC-3", "SC-4", "SC-5", "SC-6", "SC-7", "SC-8", "SC-9"],
  "verify": [
    {"sc_ref": "SC-1", "method": "command", "cmd": "grep -n returncode scripts/gd-review-merge-and-fix-loop.py"},
    {"sc_ref": "SC-2", "method": "command", "cmd": "grep -n 'else \"completed\"' scripts/gd-review-router.py"},
    {"sc_ref": "SC-3", "method": "command", "cmd": "bash tests/gd-l3-regression-v1-fixtures.sh"},
    {"sc_ref": "SC-4", "method": "command", "cmd": "grep -n gd_review_decision scripts/gd-aggregate-codex-cross-review.py"},
    {"sc_ref": "SC-5", "method": "command", "cmd": "grep -n 'additionalProperties' scripts/gd-validate-codex-cross-review-manifest.py"},
    {"sc_ref": "SC-6", "method": "command", "cmd": "grep -n 'is True' scripts/gd-validate-execution-batch.py"},
    {"sc_ref": "SC-7", "method": "command", "cmd": "python3 scripts/gd-validate-stage-dispatch-ledger.py --self-test"},
    {"sc_ref": "SC-8", "method": "command", "cmd": "python3 -c \"import ast; ast.parse(open('scripts/gd-validate-subplan-codex-binding.py').read()); print('ok')\""},
    {"sc_ref": "SC-9", "method": "command", "cmd": "grep -n 'release_closure' scripts/gd-validate-review2-output.py"}
  ]
}
```
<!-- gd-child-plan-proposal-json:end -->
