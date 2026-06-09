# T7 Controller Baseline Convergence — Execution Result

```yaml
task_id: t7-controller-baseline-convergence
status: completed
completed_at: 2026-06-09T05:50:00Z
agent_role: implementer
```

## Summary

Controller implements Round 1 dual-codex (codex_A + codex_B) three-way union baseline + Round 2+ single-codex neutral-lens recheck with REVIEW_ROUND/BASELINE_FINDINGS/DELTA_SCOPE/SCOPE_CONSTRAINT injection + git stash create delta snapshots (no new commits) + CONVERGENCE_TIMEOUT on 2 consecutive stagnant rounds + D7 large-delta dual-codex fanout + all 6 selftests passing + baseline JSON Schema valid.

## Deliverables

| Path | Status |
|------|--------|
| `scripts/gd-review-controller.py` | Created (1350+ lines) |
| `schema/gd-baseline-findings.schema.json` | Created (valid JSON Schema draft-07) |
| `commands/review2.md` | T7 code-loop orchestration section appended |
| `scripts/gd-review-router.py` | Controller hook-in added for execution_outcome/combined routes |

## Verify Command Outputs

```
=== SC-7.1a: REVIEW_LENS_EMPHASIS|codex_A|codex_B ===
23  (>= 2 ✓)

=== SC-7.1b: line/dedup ===
84  (>= 1 ✓)

=== SC-7.2a: mapped/findings/gd_review_decision ===
34  (>= 1 ✓)

=== SC-7.2b: no raw regex on VERDICT/P1/finding ===
0  (= 0 ✓)

=== SC-7.3a: git stash create/snapshot/blob ===
28  (>= 1 ✓)

=== SC-7.3b: no git commit subprocess ===
0  (= 0 ✓)

=== SC-7.4a: CONVERGENCE_TIMEOUT count ===
18  (>= 1 ✓)

=== SC-7.4c: no DELIVERABLE_BLOCKED ===
0  (= 0 ✓)

=== SC-7.5: round2_fanout_threshold params ===
8  (>= 2 ✓)

=== SC-7.7: four capsule fields ===
29  (>= 4 ✓)

=== SC-7.9a: ephemeral ===
6  (>= 1 ✓)

=== SC-7.9b: schema JSON valid ===
VALID_JSON  ✓

=== SC-7.9c: baseline_unresolved/new_in_delta/APPROVED ===
49  (>= 2 ✓)
```

## Selftest Outputs

### selftest: convergence_timeout

```
=== selftest: convergence_timeout ===
[controller] Branch A: code-only  invocation_id=ctrl-20260609T054746Z-9ec2b772
[controller] Round 1 complete: 2 baseline findings
[controller] Round 2: dispatch=1  baseline_unresolved=2  new_in_delta=0
[controller] Round 3: dispatch=1  baseline_unresolved=2  new_in_delta=0
[controller] Round 4: dispatch=1  baseline_unresolved=2  new_in_delta=0
CONVERGENCE_TIMEOUT: baseline_unresolved did not decrease for 2 consecutive rounds
CONVERGENCE_TIMEOUT confirmed via SystemExit
exit=0
```

Output contains CONVERGENCE_TIMEOUT: PASS. Selftest function returns 0 (test passed = timeout confirmed).

### selftest: d7_large_delta_fanout

```
=== selftest: d7_large_delta_fanout ===
[d7_selftest] large_delta dispatch=2  small_delta dispatch=1
d7_large_delta_fanout: PASS
exit=0
```

### selftest: branch_b_convergence_timeout

```
=== selftest: branch_b_convergence_timeout ===
[controller] Branch B: execution-only  invocation_id=ctrl-20260609T054747Z-b25f8d13
[controller] Round 1 complete: 1 baseline findings
[controller] Round 2: dispatch=1  baseline_unresolved=1  new_in_delta=0
[controller] Round 3: dispatch=1  baseline_unresolved=1  new_in_delta=0
[controller] Round 4: dispatch=1  baseline_unresolved=1  new_in_delta=0
CONVERGENCE_TIMEOUT: branch B baseline_unresolved stagnant for 2 rounds
CONVERGENCE_TIMEOUT confirmed in branch B
exit=0
```

### selftest: round2_capsule_fields

```
=== selftest: round2_capsule_fields ===
round2_capsule_fields: PASS (REVIEW_ROUND=2)
exit=0
```

### selftest: h5_no_silent_resolve

```
=== selftest: h5_no_silent_resolve ===
h5_no_silent_resolve: PASS (symptom-present finding stays unresolved)
exit=0
```

### selftest: branch_c_rerun_after_simplify

```
=== selftest: branch_c_rerun_after_simplify ===
[controller] Branch C: combined  invocation_id=ctrl-20260609T054748Z-4f89c82d
[controller] Branch A: code-only  invocation_id=ctrl-20260609T054748Z-4f89c82d-A
[controller] Round 1 complete: 1 baseline findings
[controller] Round 2: dispatch=1  baseline_unresolved=0  new_in_delta=0
APPROVED
[controller] Branch B: execution-only  invocation_id=ctrl-20260609T054748Z-4f89c82d-B
[controller] Round 1 complete: 1 baseline findings
[controller] Round 2: dispatch=1  baseline_unresolved=0  new_in_delta=0
APPROVED
branch_c_rerun_after_simplify: PASS (exec_mtime=1780984069.574 > simplify_time=1780984068.574)
exit=0
```

## SC Checklist

| SC | Description | Status |
|----|-------------|--------|
| SC-7.1 | Round 1 dual codex (codex_A+codex_B) + Claude 3-way union baseline | PASS |
| SC-7.2 | Round 2+ consumes bridge mapped JSON, no raw codex regex parsing | PASS |
| SC-7.3 | Delta via git stash create, no git commits | PASS |
| SC-7.4 | CONVERGENCE_TIMEOUT on 2 stagnant rounds; no DELIVERABLE_BLOCKED | PASS |
| SC-7.5 | D7 large delta → dispatch=2; small delta → dispatch=1 | PASS |
| SC-7.6 | Branch B also has CONVERGENCE_TIMEOUT | PASS |
| SC-7.7 | Round 2+ capsule contains REVIEW_ROUND/BASELINE_FINDINGS/DELTA_SCOPE/SCOPE_CONSTRAINT | PASS |
| SC-7.8 | H5: symptom-present finding not silently resolved | PASS |
| SC-7.9 | codex exec --ephemeral; baseline_unresolved==0 AND new_in_delta==0 → APPROVED; schema valid; Branch C mtime ordering | PASS |

## Blockers

none — all 6 selftests pass, all 13 SC verifications pass. Real multi-round execution requires codex binary; selftests use stubs (per spec).

## Notes

- `commands/review2.md` T7 code-loop section appended between "分支 C" and "统一终点" sections; T5 入口解析段 and T8 终点段 not modified.
- `scripts/gd-review-router.py` gained `_run_controller_multi_round()` helper + `use_controller` param on `_run_live_execution_only` and `_run_live_execution_plus_code`. T6 target-transmission logic not modified.
- Controller does not self-trigger on import; no daemon/hook/cron registered.
