# Plan Review Result (v2)

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-plan-review
SCHEMA_VERSION: 2.0

---

## 1. 标识与运行状态

```text
SCHEMA_VERSION: 2.0
REVIEWER: <claude_main | claude_subagent_<role> | codex>
REVIEW_TARGET: <plan 文件相对路径>
REVIEW_KIND: plan
REVIEW_TARGET_KIND: plan_only
TARGET_ROLE: plan_artifact
REVIEW_RUN_STATUS: completed | completed_with_constraint | degraded | failed_to_run
GD_REVIEW_DECISION: APPROVED | REQUIRES_CHANGES | FAILED
```

`GD_REVIEW_DECISION` 取值见 `prompts/gd-review-standard.md` "Output Contract"；禁止裸 `VERDICT:`。

---

## 2. Scope Checked

| 检查面 | 结论 | 证据（≤30 字） |
|--------|------|---------------|
| <REVIEW_FOCUS 项> | pass / fail / n_a | <短语> |

---

## 3. Findings（严重度仅 P1 / P2 阻断）

### Finding 1 [P1|P2] <短标题>

```yaml
severity: P1 | P2
title: <短标题>
sc_refs:
  - SC-<N>
evidence: <plan 文件 + 行号 / 命令 / 输出>
impact: <按当前计划执行会产生的明显问题>
required_fix: <最小修复，不扩大范围>
verify: <补完后如何确认（命令 / 路径 / 断言）>
```

---

## 4. Merge Notes

```yaml
MERGE_NOTES:
  conflict_with_other_reviewer: false | true
  arbitration_reason: <如果冲突，写仲裁理由>
  degraded_reason: <如果 REVIEW_RUN_STATUS != completed，写原因>
```

---

## 5. Residual Risk（P3 或非阻塞项）

---

## 6. Machine-Readable Result（REQUIRED — bridge v2 parser 提取此 block）

> 必须是**唯一**一个 `gd-review-result-json` block，结构符合 `schema/gd-review-result-v2.schema.json`。

<!-- gd-review-result-json:start -->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-plan-review",
  "review_kind": "plan",
  "review_target_kind": "plan_only",
  "target_role": "plan_artifact",
  "reviewer": "<claude_main | claude_subagent_<role> | codex>",
  "review_target": "<plan 文件相对路径>",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": { "location": "top_level_machine_header", "value": "APPROVED" },
  "scope_checked": [
    { "area": "<检查面>", "result": "pass", "evidence": "<≤30字证据>" }
  ],
  "findings": [],
  "merge_notes": { "conflict_with_other_reviewer": false },
  "residual_risk": "",
  "timestamp": "2026-01-01T00:00:00Z"
}
```
<!-- gd-review-result-json:end -->
