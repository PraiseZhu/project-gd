---
name: gd-review
description: GD protocol review — generate plan review, validate artifacts, Codex cross-review with 2-retry fallback, max-2-parallel-agents rule.
---

# /gd-review — GD Protocol Plan Review

Dual-reviewer plan review following the GD protocol. Produces Claude self-review, dispatches Codex cross-review, merges verdicts, and runs bounded auto-fix.

## Prerequisites

Verify these artifacts exist before proceeding. **Fail-closed** if any are missing — output `REVIEW_TARGET_MISSING` and stop.

```
GD_PROJECT_ROOT = ~/AI-Agent/Claude/projects/Project GD

Required files:
  ${GD_PROJECT_ROOT}/prompts/gd-review-standard.md
  ${GD_PROJECT_ROOT}/templates/gd-plan-review-template.md
  ${GD_PROJECT_ROOT}/templates/gd-plan-review-loop-report-template.md
  <user-specified plan file>
```

Scripts (must exist at these paths):
- `${GD_PROJECT_ROOT}/scripts/gd-codex-bridge-review.py`
- `${GD_PROJECT_ROOT}/scripts/gd-review-merge-and-fix-loop.py`
- `${GD_PROJECT_ROOT}/scripts/gd-review-router.py`
- `${GD_PROJECT_ROOT}/scripts/gd_review_contract.py`
- `~/.claude/scripts/review-result-writer.sh`

## Step 1 — Generate Claude Self-Review

1. Read the plan file and `gd-review-standard.md`
2. Read `gd-plan-review-template.md` for output format
3. Produce review JSON inline (`claude_review_origin: skill_orchestrated`)
4. Output must follow the plan review result template:

```markdown
# Plan Review Result
VERDICT: APPROVED | REQUIRES_CHANGES
REVIEW_DOMAIN: <from plan context>
REVIEW_MODE: single_pass
REVIEW_DELTA_SCOPE: full_matrix

## Scope Checked
| 检查面 | 结论 | 证据（≤30字） |
| <3-5 items from REVIEW_FOCUS> | pass/fail/n_a | <phrase> |

## Findings
### Finding N [P1|P2] <title>
问题: <gap that would cause goal failure>
证据: <plan section or path>
影响: <what goes wrong>
最小修复: <minimal fix>
验收: <how to confirm>

## Residual Risk
<P3 items or "none">
```

## Step 2 — Validate Artifacts (File Count & Format)

Before dispatching cross-review, validate:

| Check | Rule | On Fail |
|-------|------|---------|
| Plan file exists and is non-empty | `[ -s "$PLAN_FILE" ]` | `REVIEW_TARGET_MISSING` (exit 2) |
| Plan has markdown structure | Contains at least one `#` heading | `FAILED: malformed plan` |
| Review standard loaded | gd-review-standard.md parsed | `blocked_missing_artifact` |
| Template loaded | gd-plan-review-template.md parsed | `blocked_missing_artifact` |
| Claude review produced | Self-review has VERDICT line | `FAILED: self-review incomplete` |
| Claude review format | Has `## Scope Checked` + `## Findings` sections | `FAILED: malformed self-review` |

All checks must pass before Step 3. Any failure is **fail-closed** — never proceed with partial validation.

## Step 3 — Codex Cross-Review (Max 2 Concurrent Agents)

### Concurrency Rule (MANDATORY)

**Maximum 2 parallel agents per wave.** This is enforced at the dispatch level:
- Agent 1: Claude self-review (already complete from Step 1, runs inline)
- Agent 2: Codex cross-review (dispatched below)
- **Never spawn a 3rd concurrent agent.** If additional review dimensions are needed, queue them sequentially after the current wave completes.

When dispatching ANY sub-agents during this skill, count active agents before spawning. If count ≥ 2, wait for one to complete first.

### Dispatch Codex

Invoke the bridge script to send the capsule and collect Codex's raw review:

```bash
python3 "${GD_PROJECT_ROOT}/scripts/gd-codex-bridge-review.py" \
  run-bridge \
  --live-transport \
  --compat-v1 \
  --plan-file "$PLAN_FILE" \
  --review-kind plan \
  --cwd "$PWD"
```

The bridge internally:
1. Builds capsule text (review standard + goal + plan + reviewer instructions)
2. Writes capsule to `$TMPDIR/gd-codex-bridge-<run_id>.capsule.txt`
3. Calls `review-result-writer.sh --capsule-file ... --no-stop-marker`
4. Writer invokes `codex-send-wait` for Codex transport
5. Parses result from `~/.claude/review-baselines/<key>/result-<ts>.md`

### Timeout & Retry (2 Retries, Then Fallback)

```
Attempt 1: run bridge (600s timeout)
  ├─ Success → parse Codex result, go to Step 4
  └─ Timeout/Fail →
Attempt 2: re-run bridge (600s timeout)
  ├─ Success → parse Codex result, go to Step 4
  └─ Timeout/Fail →
Fallback: Claude-only review (see below)
```

**After 2 failed attempts**, do NOT retry again. Proceed to fallback.

### Fallback: Claude-Only Review

When Codex is unavailable after 2 retries:

1. **Mark the review as DEGRADED** — set `codex_transport: unavailable`, `review_run_status: degraded`
2. **Use Claude self-review as the sole verdict** — but downgrade any `APPROVED` to `APPROVED_DEGRADED`
3. **Log the gap explicitly** in the review output:

```markdown
## Cross-Review Status
codex_transport: unavailable (2 retries exhausted)
review_coverage: claude_only
gap: Codex cross-review not obtained. Findings may lack second-reviewer perspective.
      P1/P2 findings from Claude review are authoritative.
      Recommendation: re-run /gd-review when Codex is available.
```

4. **Never fake dual-review approval.** `APPROVED_DEGRADED` ≠ `APPROVED`. The caller must decide whether to accept single-reviewer approval.

## Step 4 — Merge & Auto-Fix Loop (≤3 Rounds)

When both Claude and Codex reviews are available:

1. Run the merge script:
```bash
python3 "${GD_PROJECT_ROOT}/scripts/gd-review-merge-and-fix-loop.py" \
  --claude-result "$CLAUDE_RESULT" \
  --codex-result "$CODEX_RESULT" \
  --plan-file "$PLAN_FILE" \
  --max-rounds 3
```

2. Merge matrix (from `gd_review_contract.py`):

| Claude | Codex | Merged |
|--------|-------|--------|
| APPROVED | APPROVED | **APPROVED** |
| APPROVED | REQUIRES_CHANGES | **REQUIRES_CHANGES** |
| REQUIRES_CHANGES | APPROVED | **REQUIRES_CHANGES** |
| REQUIRES_CHANGES | REQUIRES_CHANGES | **REQUIRES_CHANGES** |
| Any | FAILED | **FAILED** |
| Any | degraded/failed_to_run | **FAILED** |

3. If merged = `REQUIRES_CHANGES`:
   - Apply minimal fixes to plan (P1 findings only)
   - Re-run both reviews (Claude inline + Codex via bridge)
   - Repeat up to 3 total rounds

4. After round 3 with no resolution:
   - Output `auto_fix_exhausted`
   - Write loop report per `gd-plan-review-loop-report-template.md`
   - **Stop — no round 4**

## Step 5 — Final Output

Write the final review report including:

```markdown
# GD Review Report

## Metadata
review_kind: plan
review_mode: dual | degraded
rounds_executed: <1-3>
claude_verdict: <APPROVED|REQUIRES_CHANGES>
codex_verdict: <APPROVED|REQUIRES_CHANGES|unavailable>
merged_verdict: <APPROVED|REQUIRES_CHANGES|APPROVED_DEGRADED|FAILED>
codex_transport: available | unavailable

## Claude Review
<full Claude review from Step 1>

## Codex Review
<full Codex review or "unavailable — 2 retries exhausted">

## Merged Findings
<deduplicated findings with `reviewer: claude|codex` attribution>

## Auto-Fix Summary
<rounds executed, fixes applied, or "no auto-fix needed">

## Cross-Review Status
<coverage assessment and any gaps>
```

## Decision Enums (from gd_review_contract.py)

Valid values — any output outside these sets is a bug:

```
VERDICT:      APPROVED | REQUIRES_CHANGES | FAILED | REVIEW_TARGET_MISSING
REVIEW_KIND:  plan | execution_outcome | code_diff | combined
TARGET_ROLE:  plan_artifact | execution_artifact | code_diff | combined_bundle
NEXT_ACTION:  rerun_codex | mark_approved | block_on_p1 | require_human_arbitration | no_op
RUN_STATUS:   completed | degraded | failed_to_run
```

## Error Handling Summary

| Scenario | Action | Output |
|----------|--------|--------|
| Plan file missing | Stop immediately | `REVIEW_TARGET_MISSING` |
| Required template missing | Stop immediately | `blocked_missing_artifact` |
| Claude self-review malformed | Re-generate once, then FAILED | `FAILED: self-review incomplete` |
| Codex timeout (attempt 1) | Retry once more | log + retry |
| Codex timeout (attempt 2) | Fallback to Claude-only | `APPROVED_DEGRADED` or single-reviewer verdict |
| Codex returns MALFORMED | Treat as failed_to_run | `FAILED` in merge |
| Auto-fix loop > 3 rounds | Stop, write loop report | `auto_fix_exhausted` |
| >2 agents requested | Queue, never exceed 2 | `wave_concurrency_exceeded` if violated |
