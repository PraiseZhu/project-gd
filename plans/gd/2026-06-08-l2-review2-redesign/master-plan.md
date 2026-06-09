# L2 (/review2) 审查工作流重设计 Master Plan v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-master-plan

日期：2026-06-08
状态：draft
负责人：Claude 执行；Codex 可选 cross-review
SPEC_SOURCE: docs/2026-06-07-l2-review-workflow-redesign-spec.md（v6.1，D1-D7 + 10 漏洞修复）

---

## 1. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表（ref GOAL_SOURCE）
CHAIN_GOAL:   让 L2(/review2) 成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交（ref SPEC_SOURCE §0）
PHASE_GOAL:   实现并部署 L2 spec T1-T9，使 /review2 plan 与 /review2 code 两入口端到端可用，且部署到 live 后 source==installed
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：`/review2 plan/code 两入口拆分正确性; bridge target 修复（真 diff 非 capsule）; baseline 收敛 + 双 codex 并集机制; plan 模板 + anti-fill 硬门; source==installed parity`
- Domain-specific notes：涉及 review prompt runner、capsule 分容、controller 状态机、live 模板/hook 部署；不启用第二 watch daemon；动 live 项（T3/T4-hook/T9）须 ledger 授权。

---

## 3. 成功标准（SC）

> SC-N 与 spec 任务 T-N 一一对应。

- [ ] SC-1：`grep -nE "穷举|一次列全|exhaustive" prompts/gd-review-standard.md` 命中，且 capsule 含 `REVIEW_LENS_EMPHASIS` 字段（T1 穷举强制 + 双 codex lens）
- [ ] SC-2：无 dry-run 证据时 `/review2 code` preflight 脚本 exit≠0 并打印 `DRYRUN_EVIDENCE_MISSING`（T2）
- [ ] SC-3：`templates/plan-mode-template.md` source 存在且每条成功标准含 `SC-N` + `verify (method:...)` + `expect:`（T3）
- [ ] SC-4：含泛词 expect 的 fixture 喂 `gd-validate-review2-plan-target.py` → exit≠0 + `PLAN_ANTIFILL_FAIL`；合规 fixture → exit 0（T4）
- [ ] SC-5：`/review2 plan` 走计划路；`/review2 code` 自动判 code-only/execution-only/combined 三档并输出确认（T5）
- [ ] SC-6：`/review2 code` 触发后 capsule `PRIMARY_TARGET` 指向真实 diff/执行产物，非 capsule.md（T6）
- [ ] SC-7：controller Round 1 双 codex 并集建 `baseline_findings.json`；Round 2+ 单 codex 中性 lens；连续 2 轮 baseline_unresolved 不减 → `CONVERGENCE_TIMEOUT`（T7）
- [ ] SC-8：全 gate 绿产出"草稿+SC 证据表+已 stage"三件套；任一 gate 红 → `DELIVERABLE_BLOCKED` 无成品（T8）
- [ ] SC-9：deploy 后 `diff` source==installed 全一致，`tools/gd-parity-verify.sh --bundle review2_command` 通过（T9）

---

## 4. 非目标（NON_GOALS）

- 不改 L3 `/gd review` 语义；不动旧 `/review`、`/rev`、`codex-watch` daemon
- 不自动 commit / push（终点只产出可提交态）
- `/review2` 不输出裸 `VERDICT:`（用 `GD_REVIEW_DECISION` / `REV_VERDICT`）
- 除 T3/T9/T4-hook 外，所有改动只落 `Project GD/**`

---

## 5. Step 拆分（实现视角；依赖见各 task packet 内部 blocked_by）

| Step | 名称 | 实现 owned_paths（写进各自 task packet） | 实现 blocked_by | 主要 SC |
|------|------|------------------------------------------|-----------------|---------|
| T1 | 穷举强制 + 双 codex lens | prompts/gd-review-standard.md, scripts/gd-codex-bridge-review.py | — | SC-1 |
| T2 | 送审前 dry-run 门 | commands/review2.md, scripts/gd-review2-preflight.sh | T5 | SC-2 |
| T3 | plan 模板 source | templates/plan-mode-template.md | — | SC-3 |
| T4 | anti-fill 硬门 + Stop hook | scripts/gd-validate-review2-plan-target.py, scripts/plan-mode-antifill-stop-hook.js | T5 | SC-4 |
| T5 | 拆 plan/code + 三档判定 | commands/review2.md, scripts/gd-detect-review2-code-target.py | — | SC-5 |
| T6 | 修 bridge 真 target | scripts/gd-codex-bridge-review.py, scripts/gd-review-router.py | T1 | SC-6 |
| T7 | controller + baseline 收敛 | commands/review2.md, scripts/gd-review-router.py, scripts/gd-review-controller.py, schema/gd-baseline-findings.schema.json | T5, T6 | SC-7 |
| T8 | 终点交付物打包 | commands/review2.md, scripts/gd-review2-package-deliverable.sh | T7 | SC-8 |
| T9 | 部署 live + parity（source→target 路径见 t9 packet §5 SC-9.3 + §7；deploy 后 `tools/gd-parity-verify.sh --bundle review2_command` 验 source==installed） | .deploy-manifest.jsonl | T1-T8 | SC-9 |

> **实现 wave（6）**：w1[T1,T3] → w2[T5,T6] → w3[T4,T2] → w4[T7] → w5[T8] → w6[T9]。
> 瓶颈文件 review2.md（T2/T5/T7/T8）与 bridge（T1/T6）在实现期串行错开，故同 wave 不冲突。
>
> **注意：wave 矩阵区分说明**：`dispatch-map.json` 中的 waves 是 **planning dispatch** 的批次（各 child 只写独立 packet 文件，全部互无冲突），其 wave 顺序不反映 **实现依赖**。实现依赖（如 T4 blocked_by T5）由各 task packet 内部的 `blocked_by` 字段负责，**execution dispatch** 必须从 packet 文件读取这些依赖以确定执行顺序（T4 的实现 wave 必须在 T5 完成后，见上方实现 wave 矩阵 w2[T5]→w3[T4]）。

---

## 5a. Dispatch Map / Wave Contract（MANDATORY — planning dispatch）

> 本 master plan 的 `/gd plan` 阶段 dispatch 是 **planning dispatch**：9 个 child_planner 各写一份**自包含 task packet**，owned_paths 是各自 packet 文件路径（互不重叠），故纯并发，仅受 `max_parallel=2`。实现依赖（如 T7 实现 blocked_by T6）记录在各 task packet *内部* 的 blocked_by 字段，供后续 `/gd execute` 的 execution dispatch 使用，不在本层。

### Dispatch Map 引用

```
DISPATCH_MAP_PATH: plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json
VALIDATE_CMD: python3 scripts/gd-validate-dispatch.py plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json
```

### Wave Matrix（planning：写 9 个 task packet，纯并发分批）

| Wave | Tracks（同 wave 可并行，各写各 packet） | 并行前提验证 |
|------|------------------------------------------|-------------|
| w1 | t1, t2（child_agent_count=2） | can_parallel_with 双向；owned packet 路径不重叠 |
| w2 | t3, t4（child_agent_count=2） | 同上 |
| w3 | t5, t6（child_agent_count=2） | 同上 |
| w4 | t7, t8（child_agent_count=2） | 同上 |
| w5 | t9（child_agent_count=1） | 单 track 独占 |

---

## 6. 边界（修改 / 不修改）

修改（planning 阶段）：
- `plans/gd/2026-06-08-l2-review2-redesign/**`（master plan + dispatch map + 9 task packet + ledger + report）

不修改：
- 旧 `/rev` 任何 artifact、`/Users/praise/.claude/**`、L2 spec 本身、任何实现源码（实现属后续 `/gd execute`）

---

## 7. 风险与防护

| 风险 | 防护 |
|------|------|
| controller-report schema 为 review-bridge 设计，套 plan 阶段字段语义不匹配 | 写 controller report 时实测 `gd-validate-controller-report.py`，不匹配则按 stage ledger 为主证据，report 如实标注 |
| child planner 写出泛化 task packet | 每个 packet 过 `gd-validate-child-proposal.py`；verify 必须可执行 |
| 实现依赖丢失（planning 并发掩盖 T6→T7 顺序） | 实现依赖写进各 packet 内部 blocked_by + master plan §5 表，execution dispatch 时重建 |

---

## 8. 测试计划

```bash
python3 scripts/gd-validate-dispatch.py plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json
python3 -m json.tool plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json >/dev/null
test -f plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
```

---

## 9. Assumptions

- L2 spec v6.1 是实现权威源，本 master plan 不重述 spec 细节，只做 dispatch 编排
- child planner capability = available（主 agent 有 Agent 工具）
- 本次 `/gd plan` 只产出计划套装，不动任何实现源码
