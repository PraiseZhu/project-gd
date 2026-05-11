# Plan Review Result

GD_REVIEW_DECISION: APPROVED

(本 fixture 含 2 个 gd-review-result-json block，应被 parser reject)

<!-- gd-review-result-json:start -->
```json
{
  "template_kind": "gd-plan-review",
  "reviewer": "claude_main",
  "review_target": "x",
  "review_kind": "plan",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "scope_checked": [{"facet": "x", "result": "pass"}],
  "findings": [],
  "merge_notes": {"conflict_with_other_reviewer": false},
  "residual_risk": [],
  "timestamp": "2026-05-11T08:00:00Z"
}
```
<!-- gd-review-result-json:end -->

<!-- gd-review-result-json:start -->
```json
{
  "template_kind": "gd-plan-review",
  "reviewer": "claude_main",
  "review_target": "x",
  "review_kind": "plan",
  "review_run_status": "completed",
  "gd_review_decision": "REQUIRES_CHANGES",
  "scope_checked": [{"facet": "x", "result": "fail"}],
  "findings": [],
  "merge_notes": {"conflict_with_other_reviewer": false},
  "residual_risk": [],
  "timestamp": "2026-05-11T08:01:00Z"
}
```
<!-- gd-review-result-json:end -->
