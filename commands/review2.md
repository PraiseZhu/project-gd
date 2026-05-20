# /review2 Command

> **Source of truth**: `Project GD/commands/review2.md`
> **Installed copy** (authorized only): `/Users/praise/.claude/commands/review2.md`
> **Authority**: L2 profile-aware Codex workbench wrapper. NOT a replacement for `/gd review` (L3 formal review-chain authority).

## Authority Boundary

```text
L3_GD_REVIEW_SEMANTICS: unchanged
RELEASE_VERDICT: NOT_APPLICABLE (default)
```

`/review2` output never grants release approval. Only `scripts/gd-codex-chain-release-status.sh` produces `OVERALL_RELEASE_STATUS: READY_FOR_COMMIT`.

## Usage

```
/review2 [--profile code_diff|release_closure|runtime_parity] [--target <path>]
```

Defaults:
- `--profile code_diff` (safe default; does not imply release readiness)
- `--target` auto-detected from git diff or current directory
- `--cwd` auto-detected from git root

## Profiles

| Profile | Use when | RELEASE_VERDICT |
|---------|---------|-----------------|
| `code_diff` | Reviewing code changes (scripts, config, fixtures) | NOT_APPLICABLE |
| `release_closure` | Verifying full release readiness before committing | Full evidence contract required |
| `runtime_parity` | Auditing parity between source and installed runtime | NOT_APPLICABLE |

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
- `release_closure` with missing mandatory_read files → `CAPSULE_BUILD_FAIL`, stop
- Codex output with `missing` coverage on mandatory read → `COVERAGE_VALIDATE_FAIL`
- `release_closure` + `missing` coverage → `RELEASE_VERDICT: BLOCKED`
- No Codex transport → `CODEX_RUN_STATE: failed`, `RELEASE_VERDICT: BLOCKED` (for release_closure)

## Install / Parity

Install via `scripts/install-review-route-command.sh --route review2 --dry-run` (safe default).
Live install requires explicit user authorization + ledger entry in `baselines/gd-v7-runtime-write-authorizations.jsonl`.
Parity check: `scripts/gd-parity-verify.sh --bundle review2_command` (after install).
