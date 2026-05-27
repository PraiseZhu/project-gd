# Review Chain Fix — Codex Handoff Report

**Date:** 2026-05-27  
**Plan:** `.planning/2026-05-27-gd-review-chain-fix/task_plan.md` (approved v3)  
**Branch:** `worktree-parallel-mixing-riddle` → merge target `feature/fix-routing-noise`  
**Worktree:** `.claude/worktrees/parallel-mixing-riddle`

---

## Phase 验收表

| Phase | Description | Status | Evidence |
|-------|-------------|--------|----------|
| Phase 1 | L3 evidence validator + fixtures | **PASS** | See §Phase 1 evidence |
| Phase 2 | Bridge prompt 硬化 + fail-fast | **PASS** | See §Phase 2 evidence |
| Phase 3 | Stage ledger batch_id + selftest | **PASS** | See §Phase 3 evidence |
| Phase 4 | Controller v1.1 batch ledger splitting | **PASS** | See §Phase 4 evidence |
| Phase 5 | Controller report validator + parent gate Rule 2b/3b | **PASS** | See §Phase 5 evidence |
| Phase 6 | commands/gd.md minimal cherry-pick rev16→rev21 | **PASS** | See §Phase 6 evidence |
| Phase 7 | Full regression + smoke (8/9 green) | **PASS_WITH_KNOWN_EXCEPTION** | See §Phase 7 evidence |
| Phase 8 | Codex handoff report | **PASS** | This document |

Phase 7 status: 8 of 9 Test Plan items are PASS; the 9th item (`gd-check-review-route-preflight.sh --route review2`) returns FAIL due to a **pre-existing** mismatch between worktree `commands/gd.md` and installed `~/.claude/commands/gd.md`. This mismatch existed at the worktree base (pre-Phase-6) and cannot be resolved within the plan's hard boundary (`/Users/praise/.claude/** 绝不写`). The original plan's "全绿" criterion is therefore amended to `PASS_WITH_KNOWN_EXCEPTION` and documented as residual risk for post-merge install action.

---

## Phase 1 — L3 Evidence Validator + Fixtures

**Positive case:**
```
$ python3 scripts/gd-validate-review-content-evidence.py \
    --target fixtures/review-chain/l3-evidence/target-with-sc-ids.md \
    --review fixtures/review-chain/l3-evidence/approved-scope-checked.md
L3_RESULT: EVIDENCE_VALID (verdict=APPROVED, target_sc_ids=3, review_sc_ids=3)
exit=0
```

**Negative case (APPROVED without scope SC-IDs):**
```
$ python3 scripts/gd-validate-review-content-evidence.py \
    --target fixtures/review-chain/l3-evidence/target-with-sc-ids.md \
    --review fixtures/review-chain/l3-evidence/approved-missing-scope-sc.md \
    --json-report /tmp/out.json
ERROR: FAKE_EVIDENCE_DETECTED: APPROVED verdict — SCOPE_CHECKED section has no SC-IDs
L3_RESULT: FAKE_EVIDENCE_DETECTED (1 error(s), verdict=APPROVED)
exit=1
JSON .error_codes = ["missing_scope_sc_ids"]
JSON .missing_scope_sc_ids = ["SC-R1","SC-R2","SC-R3"]
```

---

## Phase 2 — Bridge Fail-Fast

**Inline JSON rejected (no live transport):**
```
$ python3 scripts/gd-codex-bridge-review.py build-capsule \
    --kind plan --compat-v1 \
    --target fixtures/review-chain/l3-evidence/target-with-sc-ids.md \
    --cwd . --out /tmp/capsule.json \
    --related-context '[{"bad":true}]'
ERROR: --related-context value looks like inline JSON, not a file path. Write the JSON to a file and pass the path instead.
exit=2
```

---

## Phase 3 — Stage Ledger batch_id Selftest

```
$ python3 scripts/gd-validate-stage-dispatch-ledger.py --selftest
PASS: single → valid (expected valid)
PASS: batch-001 → valid (expected valid)
PASS: missing batch_id → invalid (expected invalid)
LEDGER_VALID (single + batch-001), invalid (missing batch_id)
exit=0
```

---

## Phase 4 — Suite Controller v1.1

```
$ python3 scripts/gd-review-suite-controller.py \
    --fixture fixtures/review-chain/suite-controller/eight-target-approved-suite.json \
    --out-dir /tmp/ctrl-out/
...
CONTROLLER_REPORT_PATH: .../controller-report.json
STAGE_DISPATCH_LEDGER_PATH: .../stage-dispatch-ledger-batch-001.json
STAGE_DISPATCH_LEDGER_PATH: .../stage-dispatch-ledger-batch-002.json
STAGE_DISPATCH_LEDGER_PATH: .../stage-dispatch-ledger-batch-003.json
STAGE_DISPATCH_LEDGER_PATH: .../stage-dispatch-ledger-batch-004.json
exit=1  (fixture mode: transport_failed expected)

schema_version = "1.1"
run_mode       = "fixture"
batch ledgers  = 4
child_agent_count per ledger = 2 (≤ max_parallel=2 ✓)
```

---

## Phase 5 — Controller Report Validator + Parent Close Gate Rule 2b/3b

**Validator positive (v1.1 eight-target):**
```
$ python3 scripts/gd-validate-controller-report.py \
    fixtures/parent-close-gate/controller-report-v11-eight-target.json
CONTROLLER_REPORT_VALID
exit=0
```

**Validator self-tests (7/7 PASS):**
```
$ python3 scripts/gd-validate-controller-report.py --self-test-minimal
[PASS] pass — v1.0 live report with all required fields
[PASS] pass — v1.1 live report (empty batch_ledgers and jobs)
[PASS] pass — v1.1 fixture report accepted (not rejected)
[PASS] fail — missing required field 'jobs'
[PASS] fail — v1.1 missing batch_ledgers field
[PASS] fail — v1.1 suite_target_closure incomplete
[PASS] fail — unsupported schema_version
exit=0
```

**Parent close gate — positive (eight-target v1.1):**
```
$ python3 scripts/gd-validate-parent-close-gate.py \
    fixtures/parent-close-gate/closure-v11-eight-target.json
PARENT_CLOSE_GATE_VALID: closure-v11-eight-target.json
exit=0
```

**Parent close gate — negative (ineligible mapped_status):**
```
$ python3 scripts/gd-validate-parent-close-gate.py \
    fixtures/parent-close-gate/suite-target-closure-ineligible.json
PARENT_CLOSE_GATE_INVALID: closure_ineligible: transport_failed in suite_target_closure target gd-v11-fixture-step-2
exit=1
```

---

## Phase 6 — commands/gd.md cherry-pick

```
$ git show --stat cc14f98
 commands/gd.md | 86 +++++----
 1 file changed, 35 insertions(+), 51 deletions(-)
```

Changed content (2 hunks only):
1. `/gd plan` CAPABILITY_STATUS table row — updated from lock_revision=2 to lock_revision=21; references stage dispatch ledger + controller report replacing planning_dispatch_log.json
2. Dispatch contract section — replaced "Multi-step dispatch contract v1.1 (lock_revision=12)" with "Mandatory Subagent Dispatch Contract (lock_revision=21)"; Fail-closed section updated; Probe 合約 collapsed to SUPERSEDED tombstone

---

## Phase 7 — Full Regression Smoke (9 items)

| Check | Result |
|-------|--------|
| `bash scripts/gd-l3-regression-v1-fixtures.sh` | `L3_REGRESSION: PASS` ✅ |
| `bash scripts/gd-bridge-compat-smoke.sh` | pass=3 fail=0 ✅ |
| `bash scripts/gd-check-review-route-preflight.sh --route review2` | `PREFLIGHT_STATUS: FAIL` ⚠ (pre-existing — see PASS_WITH_KNOWN_EXCEPTION above) |
| Phase 1 positive re-run | `L3_RESULT: EVIDENCE_VALID, exit=0` ✅ |
| Phase 1 negative re-run | `exit=1, missing_scope_sc_ids` ✅ |
| Phase 2 fail-fast re-run | `exit=2, no live transport` ✅ |
| Phase 3 selftest re-run | `LEDGER_VALID, exit=0` ✅ |
| Phase 4 controller v1.1 re-run | `schema_version=1.1, 4 ledgers, child_agent_count≤2` ✅ |
| Phase 5 gate positive + negative re-run | `VALID + INVALID, exit=0/1` ✅ |

**Preflight explanation:** `gd-check-review-route-preflight.sh` compares worktree's `commands/gd.md` (hash: c15a050c...) vs installed `~/.claude/commands/gd.md` (hash: ee3f4717...). Pre-Phase-6 worktree hash was already `8c163653...` ≠ installed `ee3f4717...`. Phase 6's gd.md cherry-pick changed the source hash but did not cause the underlying mismatch — it was pre-existing. Installation to `~/.claude/commands/` is prohibited by plan hard boundary.

---

## Changed Files (by Phase)

### Phase 5 — commit `dcdb954`
- `scripts/gd-validate-controller-report.py` — fully rewritten: accepts fixture mode, validates v1.1 `batch_ledgers[]` file hashes, `suite_target_closure[]` closure completeness, `evidence_kind` enum; 7 self-tests
- `scripts/gd-validate-parent-close-gate.py` — Rule 2b upgraded: calls controller report validator subprocess, then checks `suite_target_closure[]` for INELIGIBLE_STATUSES; Rule 3b: validates stage ledger file exists and is valid JSON
- `fixtures/parent-close-gate/stage-dispatch-ledger-batch-001.json` (new)
- `fixtures/parent-close-gate/stage-dispatch-ledger-batch-002.json` (new)
- `fixtures/parent-close-gate/stage-dispatch-ledger-batch-003.json` (new)
- `fixtures/parent-close-gate/stage-dispatch-ledger-batch-004.json` (new)
- `fixtures/parent-close-gate/controller-report-v11-eight-target.json` (new)
- `fixtures/parent-close-gate/controller-report-v11-ineligible.json` (new)
- `fixtures/parent-close-gate/closure-v11-eight-target.json` (new)
- `fixtures/parent-close-gate/suite-target-closure-ineligible.json` (new)

### Phase 6 — commit `cc14f98`
- `commands/gd.md` — 2 hunks: CAPABILITY_STATUS row + dispatch contract section (rev16→rev21)

### Phases 1–4 (base branch, pre-existing in `feature/fix-routing-noise`)
- `scripts/gd-validate-review-content-evidence.py` — `error_codes[]`, `missing_scope_sc_ids` JSON output
- `scripts/gd-codex-bridge-review.py` — `_load_related_context` inline-JSON fail-fast
- `scripts/gd-validate-stage-dispatch-ledger.py` — `batch_id` required, uniqueness check, `--selftest` mode
- `schema/gd-stage-dispatch-ledger.schema.json` — `batch_id` in required array
- `scripts/gd-review-suite-controller.py` — schema_version 1.0→1.1, batch ledger splitting (max_parallel≤2), `evidence_kind` enum, `batch_ledgers[]` + `suite_target_closure[]` in report
- `fixtures/review-chain/suite-controller/eight-target-approved-suite.json` (new)

---

## lock_revision 状态

| Item | Status |
|------|--------|
| Worktree `commands/gd.md` | rev21 ✅ (cc14f98) |
| Installed `~/.claude/commands/gd.md` | rev16 ⚠ (user action required post-merge) |

---

## Codex Cross-Review Round 1 Fixes (2026-05-27, post-handoff)

Codex review of the original handoff returned `REQUIRES_CHANGES` with 3 P1 + 1 P2 findings; all addressed:

| Finding | Severity | Fix |
|---------|----------|-----|
| 1. Worktree diff vs feature/fix-routing-noise deletes 5 `results/review-route-split/*` files | P1 | `git cherry-pick e837cb2` — restored 5 files; diff now has 0 D entries |
| 2. parent close gate accepts fixture-mode controller report | P1 | `gd-validate-parent-close-gate.py` Rule 2b: after loading controller report, reject `run_mode ∈ {fixture, mock_only}` with `fixture_mode_rejected`; new negative fixture `controller-report-v11-fixture-mode.json` + `closure-v11-fixture-mode.json` |
| 3. `schema/gd-controller-report.schema.json` still v1.0-only | P1 | Extended to support v1.0 and v1.1; conditional `allOf` requires `batch_ledgers[]` + `suite_target_closure[]` when `schema_version="1.1"`; SHA-256 `pattern` on hashes; `evidence_kind` enum |
| 4. Phase 7 status was `PASS*` (ambiguous) | P2 | Renamed to `PASS_WITH_KNOWN_EXCEPTION` with explicit explanation |

**Validation evidence:**
- `python3 scripts/gd-validate-parent-close-gate.py fixtures/parent-close-gate/closure-v11-fixture-mode.json` → exit=1, `fixture_mode_rejected`
- `python3 scripts/gd-validate-parent-close-gate.py fixtures/parent-close-gate/closure-v11-eight-target.json` → exit=0 (positive case still PASS)
- `jsonschema.Draft7Validator(schema_v1.1).iter_errors(v1.1_fixture)` → 0 errors; missing `batch_ledgers` → 1 error; missing `suite_target_closure` → 1 error; v1.0 minimal → 0 errors

---

## 残余风险

| Risk | Severity | Resolution |
|------|----------|------------|
| `~/.claude/commands/gd.md` not updated to rev21 | Medium | User must install after MR is merged; preflight will then pass |
| Fixture SHA256 hashes are computed at write-time; moving `fixtures/parent-close-gate/` dir as a unit will break them | Low | Treat `fixtures/parent-close-gate/` as an atomic directory; relative paths in `controller-report-v11-eight-target.json` and `-ineligible.json` must resolve correctly |
| Phase 7 preflight `PREFLIGHT_STATUS: FAIL` | Info | Pre-existing mismatch, not caused by this plan; cannot fix without writing to `~/.claude/` |

---

## 是否可进入 Codex 验收

**Yes** — all functional validators pass, fixtures are self-consistent, batch ledger hash verification works, parent close gate correctly rejects ineligible closure entries. The sole failing check (preflight parity) is pre-existing and cannot be resolved within the plan's hard boundaries. The worktree branch is ready for Codex bridge review.
