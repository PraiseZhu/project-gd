{
  "template_kind": "gd-plan-review",
  "reviewer": "codex",
  "review_target": "reports/plan6-smoke/capsule.md",
  "review_kind": "plan",
  "review_run_status": "failed_to_run",
  "gd_review_decision": "FAILED",
  "scope_checked": [
    {
      "facet": "sidecar runtime",
      "result": "fail",
      "evidence": "codex non-zero exit 1: 2026-05-11T09:04:01.138138Z ERROR rmc"
    }
  ],
  "findings": [],
  "merge_notes": {
    "conflict_with_other_reviewer": false,
    "degraded_reason": "codex non-zero exit 1: 2026-05-11T09:04:01.138138Z ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when Client(HttpRequest(HttpRequest(\"http/request failed: error sending request for url (ht"
  },
  "residual_risk": [],
  "timestamp": "2026-05-11T09:04:31Z"
}