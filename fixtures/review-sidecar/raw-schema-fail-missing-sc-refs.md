# Plan Review Result

GD_REVIEW_DECISION: REQUIRES_CHANGES

(本 fixture 的 finding 缺 sc_refs 字段，应被 schema 校验 reject)

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
  "findings": [
    {
      "severity": "P1",
      "title": "缺少 SC 验收路径",
      "evidence": "plan §测试计划 SC-3 行只写人工确认",
      "impact": "无法机器化验收会导致漂移",
      "required_fix": "补 verify 命令或断言",
      "verify": "运行命令 exit 0"
    }
  ],
  "merge_notes": {"conflict_with_other_reviewer": false},
  "residual_risk": [],
  "timestamp": "2026-05-11T08:00:00Z"
}
```
<!-- gd-review-result-json:end -->
