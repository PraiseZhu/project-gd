{
  "template_kind": "gd-code-diff-review",
  "reviewer": "codex",
  "review_target": "/Users/praise/AI-Agent/Claude/projects/Project GD/results/review-route-split/review2-20260526T201123Z/capsule.md",
  "review_kind": "code_diff",
  "review_run_status": "degraded",
  "gd_review_decision": "FAILED",
  "scope_checked": [
    {
      "facet": "bridge runtime",
      "result": "fail",
      "evidence": "finding[0] 缺 SC: SC-<N>（wrapper schema 加严）; finding[1] 缺 SC:"
    }
  ],
  "findings": [],
  "merge_notes": {
    "conflict_with_other_reviewer": false,
    "degraded_reason": "L3 content-evidence validator rejected review: ERROR: FAKE_EVIDENCE_DETECTED: Finding #1 has no SC-ID reference\nERROR: FAKE_EVIDENCE_DETECTED: Finding #2 has no SC-ID reference\nL3_RESULT: FAKE_EVIDENCE_DETECTED (2 error(s), verdict=REQUIRES_CHANGE"
  },
  "residual_risk": [],
  "timestamp": "2026-05-26T12:15:36Z"
}