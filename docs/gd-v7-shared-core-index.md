# /gd v7 Shared Core 索引

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md

> 本索引列出 Plan 2 v2 产出的全部 `/gd` shared core artifact，及它们被后续 step（Plan 3-8）的消费关系。
> 详细字段定义见各 schema；权威 manifest 见 `manifest.gd-v7.json`。

---

## 1. 文件总览（15 个 artifact + 1 个 marker）

| # | 路径 | 类型 | Owner Step | 第一次被消费的 step |
|---|------|------|-----------|---------------------|
| 1 | `docs/gd-v7-project-goal.md` | 目标源 | Plan 2 | 所有后续 plan / template |
| 2 | `prompts/gd-review-standard.md` | review 标准 | Plan 2 | Plan 6（cross-review 接入）；Claude reviewer 一上来就引用 |
| 3 | `templates/gd-master-plan-template.md` | 模板 | Plan 2 | Plan 3（Claude Code adapter 写第一份 master plan） |
| 4 | `templates/gd-step-plan-template.md` | 模板 | Plan 2 | Plan 3 |
| 5 | `templates/gd-task-packet-template.md` | 模板 | Plan 2 | Plan 4（multi-agent planning dispatch） |
| 6 | `templates/gd-execution-result-template.md` | 模板 | Plan 2 | Plan 5（execution dispatch） |
| 7 | `templates/gd-plan-review-template.md` | 模板 | Plan 2 | Plan 6（cross-review） |
| 8 | `templates/gd-execution-review-template.md` | 模板 | Plan 2 | Plan 6 |
| 9 | `schema/gd-plan-suite.schema.json` | schema | Plan 2 | Plan 7（fixtures 校验） |
| 10 | `schema/gd-task-packet.schema.json` | schema | Plan 2 | Plan 4 |
| 11 | `schema/gd-execution-status.schema.json` | schema | Plan 2 | Plan 5 |
| 12 | `schema/gd-review-result.schema.json` | schema | Plan 2 | Plan 6 |
| 13 | `manifest.gd-v7.json` | 清单 | Plan 2 | Plan 3 pre-flight |
| 14 | `docs/gd-v7-shared-core-index.md` | 索引 | Plan 2 | Plan 3 pre-flight |
| 15 | `reports/gd-v7-shared-core.md` | 报告 | Plan 2 | Plan 3 pre-flight |
| — | `reports/gd-v7-shared-core.start.marker` | marker | Plan 2 Step 1 | Plan 2 Step 8 no-write audit |

---

## 2. 引用关系图（文字版）

```
                       docs/gd-v7-project-goal.md  (GOAL_SOURCE)
                                  │
        ┌─────────────────────────┼─────────────────────────────┐
        ▼                         ▼                             ▼
  templates/gd-master-plan  templates/gd-step-plan      templates/gd-task-packet
        │                         │                             │
        │                         │                             │
        ▼                         ▼                             ▼
   future master plan        future step plan          dispatched task packet
        │                         │                             │
        └─────────────┬───────────┴──────────┬──────────────────┘
                      ▼                      ▼
            templates/gd-execution-result    schemas/*.json
                      │
                      ▼
            templates/gd-plan-review  ←──┐
            templates/gd-execution-review  │
                      │                   │
                      ▼                   │
            prompts/gd-review-standard.md  ◄───  Codex cross-review (Plan 6)
                      │
                      ▼
                 GD_REVIEW_DECISION
                  (NEVER bare VERDICT:)
```

---

## 3. 后续 Plan 的消费契约

| Plan | 消费的 shared core artifact | 不得修改的 artifact |
|------|---------------------------|---------------------|
| Plan 3（Claude Code adapter） | master/step plan 模板 + index + manifest | review-standard、schema、task-packet 模板 |
| Plan 4（multi-agent planning） | task-packet 模板 + task-packet schema | review-standard、其他模板 |
| Plan 5（execution dispatch） | execution-result 模板 + execution-status schema | review-standard、plan/review 模板 |
| Plan 6（Codex cross-review） | review-standard + plan/execution-review 模板 + review-result schema | 任何 plan/task/execution artifact 内容 |
| Plan 7（anti-fill fixtures） | 全部 shared core | 不修改任何 shared core 内容（仅生成 fixtures） |
| Plan 8（隔离收口） | manifest + report | 全部 shared core 文件（只读） |

---

## 4. 修改协议

任何 shared core artifact 的修改必须：

1. 由对应 Plan 在 `boundaries.modify` 中显式列出
2. 通过该 Plan 的 plan review APPROVED
3. 在该 Plan 的 execution review 中通过路径权限自检
4. 同步更新 `manifest.gd-v7.json` 的 `version` 与 `created_at`

否则 Step 8（隔离收口）将通过 hash 比对发现并 FAIL。

---

## 5. 与旧 `/rev` artifact 的隔离

| 类别 | 旧 `/rev` 文件 | 新 `/gd` 替代 | 是否共存 |
|------|--------------|--------------|---------|
| 目标源 | `PROJECT_GOAL.md` | `docs/gd-v7-project-goal.md` | 共存（旧标 legacy） |
| review 标准 | `prompts/rev-review-standard.md` | `prompts/gd-review-standard.md` | 共存（旧标 legacy） |
| plan 模板 | `templates/plan-template.md` | `templates/gd-master-plan-template.md` + `gd-step-plan-template.md` | 共存（不互引） |
| execution 模板 | `templates/execution-result-template.md` | `templates/gd-execution-result-template.md` | 共存（不互引） |
| schema | `schema/rev-baseline.schema.json` 等 | `schema/gd-*.schema.json` | 共存（不互引） |
| manifest | `manifest.json` (terminal) | `manifest.gd-v7.json` | 共存（不互引） |
| runner | `bin/rev` | （未实现，Plan 3 起规划） | 旧不动 |

---

## 6. Plan 4 dispatch extension（v1.1.0 受控追加）

> 本节由 Plan 4 v2 在 manifest `revisions[1.1.0]` 中受控追加；前后 hash 见 `manifest.gd-v7.json` `revisions[].before_hash` / `after_hash`。

### 6.1 新增 artifact（14 个，全部由 Plan 4 owned）

| # | 路径 | 类型 | 第一次被消费的 step |
|---|------|------|---------------------|
| 1 | `docs/gd-v7-multi-agent-dispatch.md` | 规则文档 | Plan 5（execution dispatch 实现） |
| 2 | `templates/gd-dispatch-map-template.md` | 模板 | 主 agent 编排 dispatch |
| 3 | `templates/gd-child-plan-prompt-template.md` | 模板 | 主 agent 调度 child planner |
| 4 | `templates/gd-child-execute-prompt-template.md` | 模板 | 主 agent 调度 child executor |
| 5 | `schema/gd-dispatch-map.schema.json` | schema | 文档参考 / 未来 Codex review |
| 6 | `scripts/gd-validate-dispatch.py` | validator (stdlib-only) | 主 agent dispatch 前必跑 |
| 7 | `fixtures/dispatch/valid-dispatch.json` | positive fixture | validator 自检 |
| 8 | `fixtures/dispatch/parallel-overlap-invalid.json` | negative: path overlap | validator 自检 |
| 9 | `fixtures/dispatch/missing-context-invalid.json` | negative: 静态文件不存在 | validator 自检 |
| 10 | `fixtures/dispatch/dependency-parallel-conflict-invalid.json` | negative: blocked_by ∩ can_parallel_with | validator 自检 |
| 11 | `fixtures/dispatch/wave-unknown-track-invalid.json` | negative: wave 引用不存在 track (P1.1) | validator 自检 |
| 12 | `fixtures/dispatch/wave-nonparallel-invalid.json` | negative: 同 wave 未声明可并行 (P1.1) | validator 自检 |
| 13 | `fixtures/dispatch/wave-dependency-order-invalid.json` | negative: blocked_by 在更晚 wave (P1.1) | validator 自检 |
| 14 | `fixtures/dispatch/sc-verify-mismatch-invalid.json` | negative: sc_refs vs verify mismatch (P1.2) | validator 自检 |

### 6.2 受控修改的 Plan 2 文件（hash drift 已记录）

| 文件 | before-hash | 修改类型 |
|------|-------------|---------|
| `manifest.gd-v7.json` | `a9ce4206d442dc82a0a03c8a7e5822559a8ef9a69ce51b3a1836af0001eff5a1` | 追加 `revisions[1.1.0]` + `dispatch_artifacts` 段 + `boundaries.modify_in_plan_4` |
| `docs/gd-v7-shared-core-index.md` | `02bd4830d83f929ff64ced0b94a838f01d60313851ea5429f0e6482f2066db74` | 追加本 §6 段 |

after-hash 见 `manifest.gd-v7.json revisions[1.1.0].after_hash` 与 `reports/gd-v7-multi-agent-dispatch.md` §"Plan 2 受控修改记录"。Plan 8 isolation 收口时按此 changelog 审计。

### 6.3 与未来 Plan 的关系

| Plan | 关系 |
|------|------|
| Plan 5 execution dispatch | 实现 `docs/gd-v7-multi-agent-dispatch.md` 规则的代码层；消费 `templates/gd-child-execute-prompt-template.md` 与 validator |
| Plan 6 Codex cross-review | 复用 dispatch 规则 §5 打回规则；validator 可作为 Codex review 的 pre-check |
| Plan 7 anti-fill fixtures | 设计 fixture 时复用 §2 / §3 / §6 / §7 的硬条件作为 negative case 蓝图 |
| Plan 8 isolation 收口 | 审计 manifest `revisions[]` 与 dispatch artifacts 完整性 |

---

## 7. Plan 5 v5 execution dispatch（v1.2.1 active）

> **✓ ACTIVE — Plan 5 v5 已通过 final code review（2026-05-11T07:47Z, result-20260511T074706Z.md）**。
> `manifest.gd-v7.json` `revisions[1.2.1]` 为本能力的 active revision；`revisions[1.2.0]` 保持 `status: retracted`（draft 历史保留，不删除）。
> v5 关键收窄：仅支持 `execution_mode = human_exec`；validator 实现 4 类核心语义校验（wave membership / deliverable truth / owned_paths containment / physical existence）；高级语义（verify truth、exec result block、closure recomputation）留待后续 plan。
> 详见：`reports/gd-v7-execution-dispatch-v5.md`。

### 7.1 active artifacts（v5 promotion 后）

主要消费入口：`/gd execute` 在 human_exec batch 完成后调用 `gd-validate-execution-batch.py`。

| # | 路径 | 类型 | 用途 |
|---|------|------|------|
| 1 | `scripts/gd-validate-execution-batch.py` | validator (stdlib-only) | batch + closure 校验；含 v5 4 类语义校验 |
| 2 | `templates/gd-execution-batch-template.md` | 模板 | 主 agent 按 wave 建立 batch |
| 3 | `templates/gd-execution-closure-report-template.md` | 模板 | 所有 wave 完成后生成 closure report |
| 4 | `schema/gd-execution-batch.schema.json` | schema | 文档参考 |
| 5 | `schema/gd-execution-closure-report.schema.json` | schema | 文档参考 |
| 6 | `fixtures/execution-batch/valid-batch.json` | positive fixture | validator 自检（与 valid-dispatch 严格对齐） |
| 7 | `fixtures/dispatch/_workdir/t1/result.json` | 物理 deliverable | physical existence 校验 |
| 8 | `fixtures/dispatch/_workdir/t2/result.json` | 物理 deliverable | physical existence 校验 |
| 9 | `fixtures/execution-batch/wave-membership-missing-invalid.json` | v5 negative #1 | wave membership 校验 |
| 10 | `fixtures/execution-batch/deliverable-path-mismatch-invalid.json` | v5 negative #2 | deliverable truth 校验 |
| 11 | `fixtures/execution-batch/deliverable-missing-file-invalid.json` | v5 negative #4 | physical existence 校验 |
| 12 | `fixtures/execution-batch/deliverable-outside-owned-path-invalid.json` | v5 negative #3 | owned_paths containment 校验 |
| 13 | `fixtures/execution-batch/{json-block-*,missing-verify,skipped-no-reason,status-mismatch,path-traversal,task-id-mismatch}-invalid.json` | v2 既有 negative（7 个） | 结构/语义 cascade 校验 |
| 14 | `fixtures/execution-results/valid-closure.json` | positive fixture | closure 模式自检 |
| 15 | `fixtures/execution-results/failed-no-next-action-invalid.json` | v2 既有 negative | closure 校验 |
| 16 | `reports/gd-v7-execution-dispatch-v5.md` | v5 执行报告 | candidate→promotion 全程审计 |

不在 v5 active 集合（保留作为审计轨）：`docs/gd-v7-execution-dispatch.md`（v2 设计文档）、`reports/gd-v7-execution-dispatch.md`（v2 草稿报告）、`reports/gd-v7-execution-dispatch.start.marker`。`pending_drafts.plan_5_execution_dispatch` 在 manifest 中标记 `superseded_by: "1.2.1"`。

### 7.2 受控修改的 Plan 2/3/4 文件（hash drift 已记录）

| 文件 | before-hash（16-char prefix） | 修改类型 |
|------|------------------------------|---------|
| `templates/gd-execution-result-template.md` | `2450c8522918b4a6` | 追加 §8 machine-readable 执行状态块（Plan 5 Patch #3）；§9 Anti-fill 新增 checkbox |
| `commands/gd.md` | `2311411dbc19c124` | CAPABILITY_STATUS 表 `/gd execute` → `local_only`；Stage behavior 替换；Pending table 更新 |
| `docs/gd-v7-claude-command.md` | `6f13f36222ec0f95` | Owner Plan / Status 更新；§6 Plan 实现进度更新 |
| `manifest.gd-v7.json` | `0906469ca6fa3c4f` | 追加 `revisions[1.2.0]` + `execution_dispatch_artifacts` 段 + `boundaries.modify_in_plan_5` |
| `docs/gd-v7-shared-core-index.md` | `e9253d48a19f0f18` | 追加本 §7 段 |

after-hash 见 `manifest.gd-v7.json revisions[1.2.0].after_hash` 与 `reports/gd-v7-execution-dispatch.md` §"Plan 2/3 受控修改记录"。Plan 8 isolation 收口时按此 changelog 审计。

### 7.3 关键设计决策（v5 收窄 + 4 类语义校验）

| 决策 | 内容 | 影响范围 |
|------|------|---------|
| 收窄 1 | v5 仅支持 `execution_mode = human_exec`；agent_exec / dry_run 由 validator 拒绝 | validator + commands/gd.md fail-closed |
| 收窄 2 | v5 不实现 verify truth (PASS↔exit 0)、exec result markdown block 解析、sc_results 一致性、closure recomputation；留待后续 plan | validator scope |
| 校验 1 | wave membership：`set(task_results.track_ref) == set(wave.track_ids)` | validator + wave-membership-missing-invalid.json |
| 校验 2 | deliverable truth：dispatch must_exist=true 必须在 deliverables_produced 中且 verified=true | validator + deliverable-path-mismatch-invalid.json |
| 校验 3 | owned_paths containment：produced path 必须在对应 track owned_paths 内 | validator + deliverable-outside-owned-path-invalid.json |
| 校验 4 | physical existence：verified=true 时 produced path 必须实际存在（cwd-relative） | validator + deliverable-missing-file-invalid.json |
| Promotion gate | active state 写入推迟到 final code review pass 后；review FAILED → 不写 1.2.1 | commands/gd.md、docs、manifest 写入顺序 |

### 7.4 与未来 Plan 的关系

| Plan | 关系 |
|------|------|
| Plan 6 Codex cross-review | 消费 `gd-execution-closure-report-template.md` 进行 execution review；`gd-validate-execution-batch.py --closure` 可作为 pre-check |
| Plan 7 anti-fill fixtures | 复用 §7.1 fixture 结构作为 negative case 蓝图；`json-block-missing/duplicate` 是 anti-fill 违规典型 |
| Plan 8 isolation 收口 | 审计 manifest `revisions[1.2.0]`、execution dispatch artifacts 完整性、§7.2 hash drift |
