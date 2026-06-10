# L3 链路 review 机制优化（融合 L2 收敛机制）Master Plan v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-master-plan

日期：2026-06-09
状态：draft
负责人：Claude 执行；Codex 可选 cross-review
SPEC_SOURCE: specs/l3-review-fusion/spec.md（spec2/3）
CONSTITUTION: docs/constitution.md v1.0.0（P1–P6）

---

## 1. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，提升复杂任务的计划、审查、执行、验收效率，并通过 Codex 作为 cross-review sidecar 降低填表式计划与执行遗漏风险。（引用 GOAL_SOURCE，不重写）
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准，保证后续 /gd command、multi-agent dispatch、execution review、Codex cross-review 都引用同一套契约。（引用 GOAL_SOURCE，不重写）
PHASE_GOAL:   把 L2 已验证的收敛机制（首轮 dual-codex+Claude 三方并集 baseline、r2 起 scope 收窄、每轮双 codex、5 轮硬上限、transport prevention fail-closed）融合进 L3 `/gd review plan` 与 `/gd review` code/执行路；代码审查做到质量(/code-review+/simplify)与符合性(Codex conformance-only)分离；且零破坏现有 L3 治理 gate。优化复用，不推倒重来。
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：`transport prevention/fail-closed 正确性; baseline-convergence 收窄语义; 治理产物零破坏回归; 质量/符合性 scoping 分离`
- Domain-specific notes：本 plan 改动 L3 review 链路核心脚本（全程 lab-local，不写 `~/.claude/**`）；`gd.md` 的 runtime 回灌属独立 Plan E。审查须重点核对宪法 P3（治理产物不可绕过）、P4（fail-closed）、P1（复用非重建）。

---

## 3. 成功标准（SC）

> Anti-fill：每条 SC 绑定命令/路径/断言/测试。

- [ ] SC-1：transport prevention 层落成——`/gd review` 派双 codex 前 preflight 探活 + 单 job 瞬时失败 bounded 重试 + 充足 timeout + healthcheck，且为确定性代码（非提示词）。验证：`test -f scripts/gd-codex-transport-guard.py && grep -qE 'retry|MAX_RETR' scripts/gd-codex-transport-guard.py && python3 -m pytest tests/review-fusion -k 'preflight_unavailable_fail_closed or retry_recover or timeout_configured or healthcheck_invocation' -q 2>&1 | tail -1`（覆盖四道防线：preflight 不可用 fail-closed / 瞬时失败 retry 恢复 / timeout 配置 / healthcheck 调用）
- [ ] SC-2：首轮三方并集 baseline——dual-codex（codex_A/codex_B 仅 REVIEW_LENS_EMPHASIS 不同）+ Claude self-review，findings 并集去重（键：文件+行号±3+类别，严重度取高）。验证：`python3 -m pytest tests/review-fusion -k 'union_baseline' -q 2>&1 | tail -1`（期望全绿；fixture 须含 codex_A 漏报/codex_B 命中对，baseline 并集必含该 finding）。
- [ ] SC-3：r2+ 收窄——第 2 轮起 capsule 注入 REVIEW_ROUND/BASELINE_FINDINGS/DELTA_SCOPE/SCOPE_CONSTRAINT，只验修复+查 delta，不重审未改动；且每轮仍 dual-codex（不分大小改动，无 D7）。验证：`python3 -m pytest tests/review-fusion -k 'r2_scope_constrained_dual_codex' -q 2>&1 | tail -1`（断言 r2 capsule 含 REVIEW_ROUND≥2 + BASELINE_FINDINGS + DELTA_SCOPE + SCOPE_CONSTRAINT + dual codex jobs 存在 + 未改动内容不在审查范围）。
- [ ] SC-4：有界收敛——5 轮硬上限；连续 2 轮 unresolved 不减 → CONVERGENCE_TIMEOUT exit≠0。验证：构造停滞 fixture，脚本 exit≠0 + 打印 CONVERGENCE_TIMEOUT（test）。
- [ ] SC-5：fail-closed 不降级——单 codex 经 preflight+重试 仍不可用 → fail-closed（不以「存活+Claude」凑数、不仅凭 Claude 放行）；瞬时失败一次经重试恢复、review 正常。验证：`python3 -m pytest tests/review-fusion -k 'fail_closed or retry_recover' -q 2>&1 | tail -1`（fail_closed fixture → blocked 非通过；retry_recover fixture → 正常完成）。
- [ ] SC-6：质量/符合性分离——code/执行路**必须先**经 /code-review + /simplify 上游门（任一不可用或非成功 → fail-closed，记录可验证输出），再进 Codex conformance；Codex cross-review capsule 显式声明「只验符合计划 SC，代码顺带扫一眼，不地毯式找 bug」。验证：`grep -qE 'conformance|不重复找 bug|顺带' scripts/gd-codex-bridge-review.py prompts/gd-review-standard.md && python3 -m pytest tests/review-fusion -k 'code_path_quality_conformance_separation or bridge_contract' -q 2>&1 | tail -1`（bridge_contract 覆盖：valid raw→mapped+schema pass；缺 SC: SC-N→FAILED；malformed raw→FAILED；writer 非成功 stdout→FAILED）
- [ ] SC-7：治理零破坏——优化后既有 L3 gate（stage-dispatch-ledger / controller-report / dual-gate / owned_paths）回归 100% 通过。验证：`python3 scripts/gd-validate-controller-report.py fixtures/review-fusion/regression-controller-report.json && python3 scripts/gd-validate-stage-dispatch-ledger.py fixtures/review-fusion/regression-ledger.json && python3 scripts/gd-validate-execution-batch.py fixtures/review-fusion/regression-batch.json fixtures/review-fusion/dispatch-map.json && echo PASS`（覆盖：controller-report 双 gate 一致性 + dispatch ledger + owned_paths containment audit）。
- [ ] SC-8：部署物准备（dispatch-only）——本 plan 仅产出 `.deploy-manifest.jsonl`（含 gd.md + 改动 scripts 条目）+ `baselines/gd-v7-runtime-write-authorizations.jsonl` 授权记录；**runtime 回灌与 source==installed parity 验收属独立 Plan E / deploy-live，不在本 plan SC 范围**。验证（dispatch 范围）：`python3 -c "import json; [json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.lstrip().startswith('#')]" && grep -q 'gd.md' .deploy-manifest.jsonl && grep -q 'gd.md' baselines/gd-v7-runtime-write-authorizations.jsonl && echo MANIFEST_LEDGER_READY`（JSONL 逐行解析 + manifest 含 gd.md 条目 + ledger 有对应授权）。runtime 写入与 parity 验收属 Plan E / deploy-live 后置步骤，不在本 plan SC 范围内。

---

## 4. 非目标（NON_GOALS）

- 不改 L1（`/gd plan` dispatch）语义。
- 不破坏 / 不回灌 L2 独立链路 `/review2`（另一套命令）。
- 不重建 L3 编排层、不新建平行 review 子系统（宪法 P1）。
- 不引入 D7 式「大改动才升级」条件（已定每轮 dual-codex）。
- 不自动 commit/push；终点只产出可提交态。

---

## 5. Step 拆分

| Step | 名称 | owned_paths | blocked_by | can_parallel_with | 主要 SC |
|------|------|------------|-----------|-------------------|---------|
| 1 | transport 加固（prevention 四道防线） | scripts/gd-codex-transport-guard.py（新）+ scripts/gd-review-suite-controller.py 的派发前探活点 | — | — | SC-1, SC-5 |
| 2 | bridge lens emphasis + conformance scoping + 穷举强制 | scripts/gd-codex-bridge-review.py, prompts/gd-review-standard.md | 1 | — | SC-2, SC-6 |
| 3 | review-plan 收敛融合（三方并集+r2收窄+5轮+每轮双codex） | scripts/gd-review-merge-and-fix-loop.py | 2 | 4 | SC-2, SC-3, SC-4 |
| 4 | code/执行路融合（/code-review+/simplify 上游 + Codex conformance loop） | scripts/gd-review-router.py | 2 | 3 | SC-5, SC-6 |
| 5 | 治理零破坏回归 + 故障注入 fixtures | tests/, fixtures/review-fusion/ | 3, 4 | — | SC-4, SC-5, SC-7 |
| 6 | deploy manifest/ledger 准备 | .deploy-manifest.jsonl, baselines/gd-v7-runtime-write-authorizations.jsonl（dispatch 范围；runtime 写入 `~/.claude/commands/gd.md` 由 Plan E / deploy-live 独立后置完成） | 5 | — | SC-8 |

---

## 5a. Dispatch Map / Wave Contract（MANDATORY）

### Dispatch Map 引用

```
DISPATCH_MAP_PATH: plans/gd/2026-06-09-l3-review-fusion/dispatch-map.json
VALIDATE_CMD: python3 scripts/gd-validate-dispatch.py plans/gd/2026-06-09-l3-review-fusion/dispatch-map.json
```

### Wave Matrix

| Wave | Steps（同 wave 可并行） | 并行前提验证 |
|------|------------------------|-------------|
| w1 | step-1（串行，child_agent_count=1） | — |
| w2 | step-2（串行，child_agent_count=1；bridge 是共享 chokepoint，单独成 wave） | — |
| w3 | step-3, step-4（并行，child_agent_count=2） | 双向 can_parallel_with；owned_paths 不重叠（merge-and-fix-loop.py vs review-router.py）；均 blocked_by step-2 |
| w4 | step-5（串行，child_agent_count=1） | — |
| w5 | step-6（串行，child_agent_count=1） | — |

> 规则：同 wave ≤2 step；串行 step 单独成 wave；先 VALIDATE_CMD exit 0 再 dispatch。

---

## 6. 边界（修改 / 不修改）

修改：
- scripts/gd-codex-transport-guard.py（新增）
- scripts/gd-codex-bridge-review.py
- scripts/gd-review-merge-and-fix-loop.py
- scripts/gd-review-router.py
- scripts/gd-review-suite-controller.py（仅派发前探活接入点）
- prompts/gd-review-standard.md
- tests/, fixtures/review-fusion/
- .deploy-manifest.jsonl, baselines/gd-v7-runtime-write-authorizations.jsonl（Step 6 仅产出 manifest + 授权 ledger）

不修改：
- L1 dispatch 语义、L2 `/review2` 命令
- 旧 `/rev` 任何 artifact
- `/Users/praise/.claude/**`（**本 plan 全程不写**；`~/.claude/commands/gd.md` 的 runtime 回灌 + parity 验收属独立 Plan E / deploy-live，不在本 plan 范围）
- 其他 step 的 owned_paths

---

## 7. 风险与防护

| 风险 | 防护 |
|------|------|
| bridge 是 step-2/3/4 共享 chokepoint，并发改冲突 | step-2 单独成 wave 先改 bridge 接口；step-3/4 在其后并行，各自不碰 bridge |
| 每轮 dual-codex 成本翻倍 | 由 transport prevention(SC-1) + scope 收窄(SC-3) 摊薄；轮数 5 上限封顶 |
| runtime 回灌破坏现网 /gd | 本 plan 全程 lab-local 不写 live；gd.md 回灌 + parity 归独立 Plan E（自带 deploy-live + ledger + parity gate）|
| 优化破坏既有治理 gate | SC-7 零破坏回归前后对比 |
| fail-closed 频繁误触发 | transport prevention(Step 1) 先行；SC-5 含瞬时失败重试恢复 fixture |

---

## 8. 测试计划

```bash
# SC-1
test -f scripts/gd-codex-transport-guard.py && grep -qE "retry|MAX_RETR" scripts/gd-codex-transport-guard.py && python3 -m pytest tests/review-fusion -k 'preflight_unavailable_fail_closed or retry_recover or timeout_configured or healthcheck_invocation' -q 2>&1 | tail -1
# SC-2
python3 -m pytest tests/review-fusion -k 'union_baseline' -q 2>&1 | tail -1
# SC-3
python3 -m pytest tests/review-fusion -k 'r2_scope_constrained_dual_codex' -q 2>&1 | tail -1
# SC-4
python3 -m pytest tests/ -k "convergence_timeout" -q
# SC-6
grep -qE "conformance|不重复找 bug|顺带" scripts/gd-codex-bridge-review.py prompts/gd-review-standard.md && python3 -m pytest tests/review-fusion -k 'code_path_quality_conformance_separation or bridge_contract' -q 2>&1 | tail -1
# SC-7
python3 scripts/gd-validate-controller-report.py fixtures/review-fusion/regression-controller-report.json && python3 scripts/gd-validate-stage-dispatch-ledger.py fixtures/review-fusion/regression-ledger.json && python3 scripts/gd-validate-execution-batch.py fixtures/review-fusion/regression-batch.json fixtures/review-fusion/dispatch-map.json && echo PASS
# SC-8 (dispatch scope only — runtime write is Plan E)
python3 -c "import json; [json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.lstrip().startswith('#')]" && grep -q 'gd.md' .deploy-manifest.jsonl && grep -q 'gd.md' baselines/gd-v7-runtime-write-authorizations.jsonl && echo MANIFEST_LEDGER_READY
```

---

## 9. Assumptions

- 移植基准为已实现并测试的 L2 `scripts/gd-review-controller.py` + master plan `plans/gd/2026-06-08-l2-review2-redesign/`（宪法 P2，不以 stale redesign-spec.md 为准）。
- L3 刻意偏离 L2：去 D7、每轮 dual-codex（spec Clarifications）。
- `/code-review`、`/simplify` 在 L3 运行环境可用。
- Step 1 transport 加固为前置（用户「先修 L3 链路」）。
- HOW 细节（编排器关系、/code-review 调用方式）在各 task packet 落实。
- **constitution P5 例外仲裁（L3 豁免声明）**：constitution P5  描述的是 L2 的基准机制。本 plan 依据 （spec FR-004）显式申请豁免：L3  **每轮恒为 dual-codex**（无 D7 升级条件）。理由：L3 实验场景 token 成本次要，发现漏报更优先（spec Clarifications 原文）；且去 D7 后收敛速度反而更可预测（不依赖 delta 大小）。保留不变量： 并发、cfa4b9928d12c304775b9a882fc733a7fc4fac52 delta、 5 轮硬上限、fail-closed。**reviewer 遇到 constitution P5 与本 plan SC-3/SC-4 冲突时，以本 plan + spec FR-004 Clarifications 为准**，constitution P5 的单 codex/D7 规则不适用于本 plan。
