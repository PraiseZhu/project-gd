# /review2 Command

> **Source of truth**: `Project GD/commands/review2.md`
> **Installed copy** (authorized only): `/Users/praise/.claude/commands/review2.md`
> **Authority**: L2 profile-aware Codex workbench wrapper. NOT a replacement for `/gd review` (L3 formal review-chain authority).

## Authority Boundary

```text
L3_GD_REVIEW_SEMANTICS: unchanged
RELEASE_VERDICT: NOT_APPLICABLE (default)
```

`/review2` output never grants release approval. Only `tools/gd-codex-chain-release-status.sh` produces `OVERALL_RELEASE_STATUS: READY_FOR_COMMIT`.

## Usage

```
/review2 [--profile code_diff|plan_review|release_closure|runtime_parity] [--target <path>]
```

Defaults:
- `--profile code_diff` (safe default; does not imply release readiness)
- `--target` auto-detected from git diff or current directory
- `--cwd` auto-detected from git root

## Profiles

| Profile | Use when | BRIDGE_TARGET_POLICY | RELEASE_VERDICT |
|---------|---------|---------------------|-----------------|
| `code_diff` | Reviewing code changes (scripts, config, fixtures) | — | NOT_APPLICABLE |
| `plan_review` | Reviewing a Goal-Driven plan for completeness and anti-fill compliance | `original_plan_only` | NOT_APPLICABLE |
| `release_closure` | Verifying full release readiness before committing | — | Full evidence contract required |
| `runtime_parity` | Auditing parity between source and installed runtime | — | NOT_APPLICABLE |

### plan_review routing semantics

When `--profile plan_review`:
- L2 helper generates an audit-context capsule (`BRIDGE_TARGET_POLICY: original_plan_only`).
- The bridge **must** send the **original plan file** to Codex, not the capsule itself.
- The capsule contains `REVIEW_TARGET_HASH` for integrity verification.
- Capsule target guard: bridge rejects any `--target capsule.md` invocation with `PLAN_TARGET_MUST_BE_ORIGINAL_PLAN`.
- Target preflight: `gd-validate-review2-plan-target.py` enforces field-based compliance (SC-IDs, REVIEW_DOMAIN, REVIEW_FOCUS, step fields) without binding to a specific template.

## Execution Flow

```
/review2 --profile <profile> [--target <path>]
  → gd-build-review2-capsule.py        # build capsule with INLINE_FACTS + MANDATORY_READ
  → gd-validate-review2-capsule.py     # validate before send (fail-closed)
  → gd-codex-bridge-review.py run-bridge  # send to Codex via L2 bridge
  → gd-validate-review2-output.py      # validate mandatory_read coverage
  → write results/review-route-split/<run-id>/
  → write results/release-evidence/<run-id>/ (if profile=release_closure)
```

## CAPABILITY_STATUS Mapping

| Profile | CAPABILITY_STATUS |
|---------|-----------------|
| `code_diff` | `active` |
| `plan_review` | `active` (target preflight + capsule policy guard enforced) |
| `release_closure` | `active` (capsule completeness + mandatory_read coverage enforced) |
| `runtime_parity` | `active` |

## Output Contract (every /review2 call)

```text
REVIEW_ROUTE: /review2
ROUTE_LAYER: L2
REVIEW_PROFILE: <profile>
DRIFT_PREFLIGHT_STATUS: pass | fail | degraded
CAPSULE_CONTEXT_STATUS: pass | fail
MANDATORY_READ_STATUS: pass | fail | not_applicable
MANDATORY_READ_COVERAGE_STATUS: pass | fail | not_applicable
GIT_STATE_CONTEXT_STATUS: pass | fail | not_applicable
RELEASE_CLOSURE_CONTEXT_STATUS: pass | fail | not_applicable
RELEASE_VERDICT: READY_FOR_COMMIT | BLOCKED | NOT_APPLICABLE
MACHINE_VERDICT_SOURCE: canonical_final_status | n_a
BLOCKED_REASON: <reason or N/A>
CODEX_EXEC_MODE: direct_arg
CODEX_RUN_STATE: not_started | running | completed | failed | degraded
OUTPUT_LAST_MESSAGE_PATH: <results path or N/A>
L3_GD_REVIEW_SEMANTICS: unchanged
```

## Codex Execution Flags

```bash
python3 scripts/gd-codex-bridge-review.py run-bridge \
  --kind <profile-derived-kind> \
  --target <capsule.md or diff> \
  --cwd <git-root> \
  --out results/review-route-split/<run-id>/ \
  --live-transport \
  [--compat-v1]
```

## Fail-Closed Rules

- Capsule validation failure → stop, print `CAPSULE_VALIDATE_FAIL`, do not send to Codex
- `plan_review` capsule missing `BRIDGE_TARGET_POLICY` → `BRIDGE_TARGET_POLICY_MISSING`, stop
- `plan_review` capsule with wrong policy value → `BRIDGE_TARGET_POLICY_INVALID`, stop
- `plan_review` + capsule file passed as bridge target → `PLAN_TARGET_MUST_BE_ORIGINAL_PLAN`, stop
- `plan_review` plan target fails field preflight → `PLAN_TEMPLATE_STATUS: fail`, `BRIDGE_INVOCATION_STATUS: not_started`
- `release_closure` with missing mandatory_read files → `CAPSULE_BUILD_FAIL`, stop
- Codex output with `missing` coverage on mandatory read → `COVERAGE_VALIDATE_FAIL`
- `release_closure` + `missing` coverage → `RELEASE_VERDICT: BLOCKED`
- No Codex transport → `CODEX_RUN_STATE: failed`, `RELEASE_VERDICT: BLOCKED` (for release_closure)
- v2 template missing + no `--compat-v1` → `V2_TEMPLATE_NOT_READY`, exit 1

## Install / Parity

Install via `scripts/install-review-route-command.sh --route review2 --dry-run` (safe default).
Live install requires explicit user authorization + ledger entry in `baselines/gd-v7-runtime-write-authorizations.jsonl`.
Parity check: `tools/gd-parity-verify.sh --bundle review2_command` (after install).
