# /review2 Capsule — 20260526T121123Z

REVIEW_PROFILE: code_diff
REVIEW_GOAL: Review code changes for correctness and quality.

SCOPE:
  - Changes in staged / working tree relative to HEAD
  - Code correctness and style

OUT_OF_SCOPE:
  - /gd review core semantics (unchanged)
  - ~/.claude/** runtime (not modified in this scope)
  - mirrors/codex-chain as install source (read-only audit mirror)

INLINE_FACTS:
  target:
    /Users/praise/.claude

REVIEW_TARGET:
  /Users/praise/.claude

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
  If out_of_scope, add: OUT_OF_SCOPE_REASON: <path>: <reason>
  For release_closure: 'missing' is not allowed — it causes RELEASE_VERDICT: BLOCKED

RELEASE_VERDICT_NOTE:
  This capsule does NOT grant release approval.
  L3_GD_REVIEW_SEMANTICS: unchanged
  RELEASE_VERDICT: NOT_APPLICABLE (unless profile=release_closure with full evidence contract)