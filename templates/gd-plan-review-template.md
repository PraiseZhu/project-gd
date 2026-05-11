# Plan Review Result

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-plan-review

---

## 1. 标识与运行状态

```text
REVIEWER: <claude_main | claude_subagent_<role> | codex>
REVIEW_TARGET: <plan 文件相对路径>
REVIEW_KIND: plan
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

- <事项 1，没有则写 none>

---

## 6. Machine-readable Result（Plan 6 v3 sidecar 必读）

reviewer 输出**必须且只能**含一个以下 block；JSON 必须通过 `schema/gd-review-result.schema.json`。`scripts/gd-codex-review.py parse` 据此解析；缺失 / 重复 / schema fail 都会被 reject 为 `FAILED`。

<!-- gd-review-result-json:start -->
```json
{
  "template_kind": "gd-plan-review",
  "reviewer": "claude_main",
  "review_target": "<plan 相对路径>",
  "review_kind": "plan",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "scope_checked": [
    {"facet": "<focus 短语>", "result": "pass", "evidence": "<≤60 字证据>"}
  ],
  "findings": [],
  "merge_notes": {
    "conflict_with_other_reviewer": false
  },
  "residual_risk": [],
  "timestamp": "2026-05-11T00:00:00Z"
}
```
<!-- gd-review-result-json:end -->

填写规则：
- `findings` 与 §3 markdown 表必须一一对应（同顺序、同 severity / sc_refs / evidence / impact / required_fix / verify）。冲突 → parser fail。
- `gd_review_decision` 与 §1 一致。冲突 → parser fail。
- `residual_risk` 与 §5 一致。
- `timestamp` 必须是 ISO 8601 UTC（含 `Z`）。
- 禁止在 markdown 任何地方出现行首裸 `VERDICT:` 或 `REV_VERDICT:`。
