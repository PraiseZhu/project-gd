# Execution Outcome Review Result (v2)

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-execution-outcome-review
REVIEW_KIND: execution_outcome
SCHEMA_VERSION: 2.0

GD_REVIEW_DECISION: APPROVED | REQUIRES_CHANGES | FAILED

> 顶层 `GD_REVIEW_DECISION:` 行是 source-of-truth（per Plan 8 v4.1 Step 4）。
> Anti-fill 适用范围：**NOOP**（execution outcome 无 plan-bearing 结构）。
> 禁用 `substitution_drill`，但**强制 evidence anchoring**：
> 每条 finding 的 `evidence` 必须指向 outcome JSON 路径或 `task_outcomes` 数组索引。

---

## 1. 标识与运行状态

```text
REVIEWER: <claude_main | claude_subagent_<role> | codex>
REVIEW_TARGET: <execution outcome 文件相对路径>
REVIEW_TARGET_KIND: execution_only_no_code
TARGET_ROLE: execution_artifact
REVIEW_RUN_STATUS: completed | completed_with_constraint | degraded | failed_to_run
```

`GD_REVIEW_DECISION` 取值见 `prompts/gd-review-standard.md` "Output Contract"。
顶层 header 与 §6 fenced JSON block 的 `gd_review_decision` 必须一致。
`source_of_truth_decision.location = "top_level_machine_header"`、`value` 与顶层一致。
禁止裸 `VERDICT:` 或 `REV_VERDICT:`。

---

## 2. Scope Checked

| 检查面 | 结论 | 证据（≤30 字，必须含 outcome 路径或索引） |
|--------|------|--------------------------------------|
| verify_step_executed | pass / fail / n_a | <task_outcomes[i].verify_output> |
| evidence_completeness | pass / fail / n_a | <outcome 路径 + 行号> |
| owned_paths_compliance | pass / fail / n_a | <files_modified vs task packet> |

---

## 3. Findings（严重度仅 P1 / P2 阻断）

### Finding 1 [P1|P2] <短标题>

```yaml
severity: P1 | P2
title: <短标题>
sc_refs:
  - SC-<N>
evidence: <outcome JSON path:line 或 task_outcomes[<i>].<field>；必填、必锚定>
impact: <影响哪个 active path / 验收不可信原因>
required_fix: <补哪段 outcome / 重跑哪个 verify>
verify: <补完后如何确认（命令 / 路径 / 断言）>
```

> **Evidence anchoring 规则**：
> - `evidence` 字段必须指向具体 outcome 路径（例如 `reports/plan8/h3-execution-result.md:45`）
>   或 outcome JSON 数组索引（例如 `task_outcomes[2].verify_output`）。
> - 不接受抽象描述（"verify 没跑"、"覆盖率不足" 等无锚定语句）。
> - validator 在 NOOP scope 下不跑 substitution drill，但 reviewer 必须人工核对锚点可解析。

---

## 4. Merge Notes

```yaml
MERGE_NOTES:
  conflict_with_other_reviewer: false | true
  arbitration_reason: <如果冲突，写仲裁理由>
  degraded_reason: <如果 REVIEW_RUN_STATUS != completed，写原因>
```

---

## 5. Residual Risk

字符串字段（v2 schema：`residual_risk: string`），无残留风险写 `none`。

---

## 6. Machine-readable Result（v2 schema）

reviewer 输出**必须且只能**含一个以下 block；JSON 必须通过
`schema/gd-review-result-v2.schema.json`。缺失 / 重复 / schema fail → `FAILED`。

<!-- gd-review-result-json:start -->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-execution-outcome-review",
  "review_kind": "execution_outcome",
  "review_target_kind": "execution_only_no_code",
  "target_role": "execution_artifact",
  "reviewer": "claude_main",
  "review_target": "<execution outcome 相对路径>",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": {
    "location": "top_level_machine_header",
    "value": "APPROVED"
  },
  "scope_checked": [
    {"area": "verify_step_executed", "result": "pass", "evidence": "<task_outcomes[i].verify_output 引用>"}
  ],
  "findings": [],
  "merge_notes": {
    "conflict_with_other_reviewer": false
  },
  "residual_risk": "",
  "timestamp": "2026-05-14T00:00:00Z"
}
```
<!-- gd-review-result-json:end -->

填写规则：
- `template_kind="gd-execution-outcome-review"`、`review_kind="execution_outcome"`、
  `review_target_kind="execution_only_no_code"`、`target_role="execution_artifact"` 固定
- 每条 `findings[*].evidence` 必须包含 outcome 路径或 `task_outcomes[<i>]` 锚点
- 禁止 `cross_validation_findings` 字段（v2 schema：仅 combined 允许）
- `timestamp` 必须 ISO 8601 with timezone

---

## 7. Anti-Fill 附加层（NOOP，本模板**禁止**包含 `gd-plan-review-anti-fill` block）

> **作用范围**：execution_outcome review **不适用 substitution drill**。
> 调用 `scripts/gd-validate-plan-review-anti-fill.py --review-kind gd-execution-outcome-review <file.md>`
> 时 validator 直接 exit 0 并打印 `ANTI_FILL_NOT_APPLICABLE: gd-execution-outcome-review`。
>
> **替代要求 (evidence anchoring)**：
> §3 每条 finding 的 `evidence` 必须含可解析锚点（路径:行号 或 `task_outcomes[i].field`）。
> 此项由 reviewer 自核 + sidecar parser 在后续阶段强制（不在本 validator 范围内）。
