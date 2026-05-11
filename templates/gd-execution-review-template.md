# Execution Review Result

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-execution-review

---

## 1. 标识与运行状态

```text
REVIEWER: <claude_main | claude_subagent_<role> | codex>
REVIEW_TARGET: <execution result 文件相对路径>
REVIEW_KIND: code
REVIEW_RUN_STATUS: completed | completed_with_constraint | degraded | failed_to_run
GD_REVIEW_DECISION: APPROVED | REQUIRES_CHANGES | FAILED
```

---

## 2. Scope Checked

| 检查面 | 结论 | 证据（≤30 字） |
|--------|------|---------------|
| <REVIEW_FOCUS 项> | pass / fail / n_a | <短语> |
| owned_paths 合规 | pass / fail | <files_added/modified 对比 task packet> |
| forbidden_paths 触碰 | pass / fail | <execution result 第 5 节自检> |

---

## 3. Findings

### Finding 1 [P1|P2] <短标题>

```yaml
severity: P1 | P2
title: <短标题>
sc_refs:
  - SC-<N>
evidence: <file:line — 命令 / 输出>
impact: <会导致什么 active path 失败 / 验收不可信>
required_fix: <只改哪些文件 / 函数 / 配置>
verify: <可执行命令或隔离用例>
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

## 5. Residual Risk

- <事项 1，没有则写 none>

---

## 6. Machine-readable Result（Plan 6 v3 sidecar 必读）

reviewer 输出**必须且只能**含一个以下 block；JSON 必须通过 `schema/gd-review-result.schema.json`。`scripts/gd-codex-review.py parse --kind code` 据此解析；缺失 / 重复 / schema fail 都会被 reject 为 `FAILED`。

<!-- gd-review-result-json:start -->
```json
{
  "template_kind": "gd-execution-review",
  "reviewer": "claude_main",
  "review_target": "<execution result 相对路径>",
  "review_kind": "code",
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

填写规则同 plan-review template §6：findings/decision/residual_risk 须与 markdown 正文一致；冲突 → parser fail；timestamp 必须 ISO 8601 UTC；禁止裸 `VERDICT:` / `REV_VERDICT:`。
