# Code Diff Review Result (v2)

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-code-diff-review
REVIEW_KIND: code_diff
SCHEMA_VERSION: 2.0

GD_REVIEW_DECISION: APPROVED

---

## 1. 标识与运行状态

```text
REVIEWER: codex
REVIEW_TARGET: reports/example/code-diff.patch
REVIEW_TARGET_KIND: code_only
TARGET_ROLE: code_diff
REVIEW_RUN_STATUS: completed
```

## 2. Scope Checked

| 检查面 | 结论 | 证据 |
|--------|------|------|
| owned_paths_only | pass | diff 仅触及 dispatch.json |

## 3. Findings

无。

## 4. Merge Notes

```yaml
MERGE_NOTES:
  conflict_with_other_reviewer: false
```

## 5. Residual Risk

none

## 6. Machine-readable Result (v2 schema)

<!-- gd-review-result-json:start -->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-code-diff-review",
  "review_kind": "code_diff",
  "review_target_kind": "code_only",
  "target_role": "code_diff",
  "reviewer": "codex",
  "review_target": "reports/example/code-diff.patch",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": {
    "location": "top_level_machine_header",
    "value": "APPROVED"
  },
  "scope_checked": [
    {"area": "owned_paths_only", "result": "pass", "evidence": "scripts/foo.py:42"}
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
