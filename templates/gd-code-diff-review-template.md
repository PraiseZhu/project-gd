# Code Diff Review Result (v2)

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-code-diff-review
SCHEMA_VERSION: 2.0

---

## 1. 标识与运行状态

```text
SCHEMA_VERSION: 2.0
REVIEWER: <claude_main | claude_subagent_<role> | codex>
REVIEW_TARGET: <diff 文件或 git range>
REVIEW_KIND: code_diff
REVIEW_TARGET_KIND: code_only
TARGET_ROLE: code_diff
REVIEW_RUN_STATUS: completed | completed_with_constraint | degraded | failed_to_run
GD_REVIEW_DECISION: APPROVED | REQUIRES_CHANGES | FAILED
```

`GD_REVIEW_DECISION` 取值见 `prompts/gd-review-standard.md` "Output Contract"；禁止裸 `VERDICT:`。

---

## 2. Scope Checked

| 检查面 | 结论 | 证据（≤30 字） |
|--------|------|---------------|
| owned_paths 合规 | pass / fail | <变更文件对比 task packet owned_paths> |
| forbidden_paths 触碰 | pass / fail | <无 ~/.claude / ~/.codex 写入> |
| 新增/修改逻辑正确性 | pass / fail | <关键 diff 行说明> |
| 测试覆盖 | pass / fail / n_a | <fixture / smoke 覆盖情况> |

---

## 3. Findings（严重度仅 P1 / P2 阻断）

### Finding 1 [P1|P2] <短标题>

```yaml
severity: P1 | P2
title: <短标题>
sc_refs:
  - SC-<N>
evidence: <file:line — diff 内容>
impact: <执行后会产生的明显问题>
required_fix: <最小修复>
verify: <补完后如何确认>
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
  "template_kind": "gd-code-diff-review",
  "review_kind": "code_diff",
  "review_target_kind": "code_only",
  "target_role": "code_diff",
  "reviewer": "<claude_main | claude_subagent_<role> | codex>",
  "review_target": "<diff 文件或 git range>",
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
