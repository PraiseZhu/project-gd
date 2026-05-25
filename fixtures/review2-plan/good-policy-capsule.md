# /review2 Capsule — 20260526T000000Z

REVIEW_PROFILE: plan_review
REVIEW_GOAL: Review the plan for Goal-Driven completeness and anti-fill compliance.

SCOPE:
  - Plan correctness and Goal-Driven completeness
  - Anti-fill compliance

OUT_OF_SCOPE:
  - /gd review core semantics (unchanged)
  - ~/.claude/** runtime (not modified in this scope)

REVIEW_TARGET:
  fixtures/review2-plan/good-plan.md

REVIEW_TARGET_HASH: abc123def456abc123def456abc123def456abc123def456abc123def456abc12

BRIDGE_TARGET_POLICY: original_plan_only

MANDATORY_READ:

CHECKS:
  - Code correctness and error handling
  - No hardcoded paths or credentials
  - Exit codes match documented contract

OUTPUT_CONTRACT:
  Format: Finding -> Evidence -> Root Cause -> Fix
  Severity: P1 (blocker) | P2 (warning) | P3 (minor)

  After findings, output mandatory read coverage as follows (one line per path):
  MANDATORY_READ_COVERAGE:
  Allowed statuses: read | summarized_by_preflight | out_of_scope | missing

RELEASE_VERDICT_NOTE:
  This capsule does NOT grant release approval.
  L3_GD_REVIEW_SEMANTICS: unchanged
  RELEASE_VERDICT: NOT_APPLICABLE (unless profile=release_closure with full evidence contract)
