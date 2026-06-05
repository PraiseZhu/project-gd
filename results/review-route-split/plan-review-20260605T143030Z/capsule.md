# /review2 Capsule — 20260605T143030Z

REVIEW_PROFILE: plan_review
REVIEW_GOAL: Review the plan for Goal-Driven completeness and anti-fill compliance.

SCOPE:
  - Changes in staged / working tree relative to HEAD
  - Code correctness and style

OUT_OF_SCOPE:
  - /gd review core semantics (unchanged)
  - ~/.claude/** runtime (not modified in this scope)
  - mirrors/codex-chain as install source (read-only audit mirror)

INLINE_FACTS:
  target:
    /Users/praise/.claude/plans/serialized-inventing-biscuit.md

REVIEW_TARGET:
  /Users/praise/.claude/plans/serialized-inventing-biscuit.md

REVIEW_TARGET_HASH: 09eb47507c7f61c452965b68b75e9cc16af1fdfc187cf102d97c1c28c70b1893

BRIDGE_TARGET_POLICY: original_plan_only

MANDATORY_READ:

CHECKS:
  - Code correctness and error handling
  - No hardcoded paths or credentials
  - Exit codes match documented contract

OUTPUT_CONTRACT:
  Format:
    # Code Review Result
    VERDICT: APPROVED|REQUIRES_CHANGES|FAILED
    REVIEW_DOMAIN: <domain>
    REVIEW_MODE: single_pass
    REVIEW_DELTA_SCOPE: full_matrix

    ## Scope Checked
    | 检查面 | 结论 | 证据（≤30字）|
    |--------|------|---------------|

    ## Findings
    ### Finding N [P1|P2|P3] <title>
    问题: <description>
    证据: <file:line or path>
    影响: <impact>
    最小修复: <fix>
    验收: <verification>

    ## Residual Risk
    <none or P3 items only>

  After findings, output mandatory read coverage as follows (one line per path):
  MANDATORY_READ_COVERAGE:
  Allowed statuses: read | summarized_by_preflight | out_of_scope | missing
  If out_of_scope, add: OUT_OF_SCOPE_REASON: <path>: <reason>
  For release_closure: 'missing' is not allowed — it causes RELEASE_VERDICT: BLOCKED

RELEASE_VERDICT_NOTE:
  This capsule does NOT grant release approval.
  L3_GD_REVIEW_SEMANTICS: unchanged
  RELEASE_VERDICT: NOT_APPLICABLE (unless profile=release_closure with full evidence contract)