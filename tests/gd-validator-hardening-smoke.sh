#!/usr/bin/env bash
# gd-validator-hardening-smoke.sh
# SC-8 regression: prove the L3 validator hardening turns bypass samples into
# fail (exit != 0) while legitimate inputs still pass (exit 0). Each hardened
# validator gets at least one positive (legit -> pass) and one negative
# (bypass -> fail) fixture. Ends by running each validator's built-in self-test
# to confirm the hardening did not break existing self-checks.
#
# Exit 0 = every assertion held. Exit 1 = at least one assertion failed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SCRIPTS="$ROOT/scripts"
PY="${PYTHON:-python3}"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/gd-vhs.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

FAILS=0
PASSES=0

# assert_exit <expected_code> <label> <cmd...>
assert_exit() {
  local expected="$1"; shift
  local label="$1"; shift
  local got=0
  "$@" >/dev/null 2>&1 || got=$?
  if [ "$got" -eq "$expected" ]; then
    echo "  PASS: $label (exit=$got)"
    PASSES=$((PASSES + 1))
  else
    echo "  FAIL: $label (expected exit=$expected, got=$got)"
    FAILS=$((FAILS + 1))
  fi
}

# assert_exit_in <label> <cmd...> -- <code1> <code2> ...
# Passes if the command's exit code is in the accepted set (used for the
# jsonschema-missing path where exit may be 1 or 2 depending on the validator).
assert_nonzero() {
  local label="$1"; shift
  local got=0
  "$@" >/dev/null 2>&1 || got=$?
  if [ "$got" -ne 0 ]; then
    echo "  PASS: $label (nonzero exit=$got)"
    PASSES=$((PASSES + 1))
  else
    echo "  FAIL: $label (expected nonzero, got=0)"
    FAILS=$((FAILS + 1))
  fi
}

sha256_of() {
  # portable sha256 -> stdout hex
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

# ===========================================================================
echo "== V13/V5: gd-validate-codex-cross-review-aggregate.py =="
# Negative (jsonschema present): empty jobs[] must fail via minItems.
cat > "$TMP/agg-empty.json" <<'JSON'
{
  "aggregate_version": "2.0",
  "target_set_id": "plan-h",
  "generated_at": "2026-06-16T10:00:00Z",
  "manifest_path": "manifest.json",
  "manifest_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "review_contract_hash": "1111111111111111111111111111111111111111111111111111111111111111",
  "jobs": [],
  "aggregate_summary": {}
}
JSON
assert_nonzero "aggregate: empty jobs[] rejected (jsonschema path)" \
  "$PY" "$SCRIPTS/gd-validate-codex-cross-review-aggregate.py" "$TMP/agg-empty.json"

# Negative (jsonschema MISSING): the structural fallback must also reject empty
# jobs[] (V13) instead of vacuously passing. We shadow jsonschema to force the
# ImportError branch.
agg_fallback_empty() {
  "$PY" - "$1" <<'PYEOF'
import sys, builtins, importlib.util
real_import = builtins.__import__
def fake_import(name, *a, **k):
    if name == "jsonschema":
        raise ImportError("simulated-missing")
    return real_import(name, *a, **k)
builtins.__import__ = fake_import
spec = importlib.util.spec_from_file_location(
    "agg", "scripts/gd-validate-codex-cross-review-aggregate.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
sys.exit(m.main(["x", sys.argv[1]]))
PYEOF
}
assert_nonzero "aggregate: empty jobs[] rejected (jsonschema-missing fallback)" \
  agg_fallback_empty "$TMP/agg-empty.json"

# Positive: a fully schema-valid aggregate with one job must pass (no false reject).
GOODHASH="$(printf 'placeholder' | { command -v shasum >/dev/null 2>&1 && shasum -a 256 || sha256sum; } | awk '{print $1}')"
cat > "$TMP/agg-ok.json" <<JSON
{
  "aggregate_version": "2.0",
  "target_set_id": "plan-h",
  "generated_at": "2026-06-16T10:00:00Z",
  "manifest_path": "manifest.json",
  "manifest_hash": "$GOODHASH",
  "review_contract_hash": "$GOODHASH",
  "jobs": [
    {
      "queue_job_id": "job-001",
      "target_role": "master_plan",
      "transport_status": "transport_ok",
      "raw_result_path": "raws/job-001.md",
      "raw_result_hash": "$GOODHASH"
    }
  ],
  "aggregate_summary": {
    "total_jobs": 1,
    "transport_ok": 1,
    "transport_failed": 0,
    "wrapper_schema_fail": 0,
    "approved": 1,
    "requires_changes": 0,
    "failed": 0,
    "missing_primary_target_count": 0,
    "codex_requires_changes_count": 0,
    "closure_eligible": true,
    "closure_blockers": []
  }
}
JSON
assert_exit 0 "aggregate: legit 1-job aggregate still passes" \
  "$PY" "$SCRIPTS/gd-validate-codex-cross-review-aggregate.py" "$TMP/agg-ok.json"

# ===========================================================================
echo "== V13: gd-validate-subplan-codex-binding.py =="
mkdir -p "$TMP/reports"
# Negative: aggregate with empty jobs[] -> binding has nothing to bind -> fail.
cat > "$TMP/bind-empty.json" <<'JSON'
{ "jobs": [] }
JSON
assert_exit 1 "subplan-binding: empty jobs[] rejected" \
  "$PY" "$SCRIPTS/gd-validate-subplan-codex-binding.py" \
  --reports-dir "$TMP/reports" --aggregate-json "$TMP/bind-empty.json"

# Negative: a job missing target_role/primary_target/review_kind -> fail.
# (Schema delegate may also fire; either way it must be nonzero.)
cat > "$TMP/bind-badjob.json" <<'JSON'
{
  "aggregate_version": "2.0",
  "jobs": [ { "queue_job_id": "j1" } ]
}
JSON
assert_nonzero "subplan-binding: job missing bindings rejected" \
  "$PY" "$SCRIPTS/gd-validate-subplan-codex-binding.py" \
  --reports-dir "$TMP/reports" --aggregate-json "$TMP/bind-badjob.json"

# Positive: the schema-valid aggregate (agg-ok) has a job carrying its bindings;
# but subplan-binding requires target_role/primary_target/review_kind. Build a
# minimal-but-complete binding-positive aggregate that also passes the delegated
# schema validator.
cat > "$TMP/bind-ok.json" <<JSON
{
  "aggregate_version": "2.0",
  "target_set_id": "plan-h",
  "generated_at": "2026-06-16T10:00:00Z",
  "manifest_path": "manifest.json",
  "manifest_hash": "$GOODHASH",
  "review_contract_hash": "$GOODHASH",
  "jobs": [
    {
      "queue_job_id": "job-001",
      "target_role": "master_plan",
      "primary_target": "plans/master.md",
      "review_kind": "plan",
      "transport_status": "transport_ok",
      "raw_result_path": "raws/job-001.md",
      "raw_result_hash": "$GOODHASH"
    }
  ],
  "aggregate_summary": {
    "total_jobs": 1,
    "transport_ok": 1,
    "transport_failed": 0,
    "wrapper_schema_fail": 0,
    "approved": 1,
    "requires_changes": 0,
    "failed": 0,
    "missing_primary_target_count": 0,
    "codex_requires_changes_count": 0,
    "closure_eligible": true,
    "closure_blockers": []
  }
}
JSON
assert_exit 0 "subplan-binding: legit bound job passes" \
  "$PY" "$SCRIPTS/gd-validate-subplan-codex-binding.py" \
  --reports-dir "$TMP/reports" --aggregate-json "$TMP/bind-ok.json"

# ===========================================================================
echo "== V2: gd-validate-runtime-strict-binding.py (empty-shell anchor) =="
# Build a synthetic source file. Positive source: every required-stage anchor
# contains its validator call with the required flag.
cat > "$TMP/gd-ok.md" <<'MD'
# synthetic gd.md (positive)

<!-- gd-runtime-strict-required:start stage=plan -->
run `python3 scripts/gd-validate-planning-dispatch-log.py log.json --strict-live-proof`
<!-- gd-runtime-strict-required:end stage=plan -->

<!-- gd-runtime-strict-required:start stage=probe -->
run `python3 scripts/gd-validate-planning-dispatch-log.py log.json --strict-live-proof`
also `python3 scripts/gd-validate-probe.py probe.json --strict-live-proof`
<!-- gd-runtime-strict-required:end stage=probe -->

<!-- gd-runtime-strict-required:start stage=execute-agent-exec -->
run `python3 scripts/gd-validate-planning-dispatch-log.py log.json --strict-live-proof`
<!-- gd-runtime-strict-required:end stage=execute-agent-exec -->

<!-- gd-runtime-strict-required:start stage=review-router -->
run `python3 scripts/gd-validate-route-report.py route.json --schema-version 1.0`
<!-- gd-runtime-strict-required:end stage=review-router -->
MD
assert_exit 0 "runtime-strict-binding: full validator-bound anchors pass" \
  "$PY" "$SCRIPTS/gd-validate-runtime-strict-binding.py" --source "$TMP/gd-ok.md"

# Negative: the plan anchor is an EMPTY SHELL (no validator call). Pre-hardening
# this was a soft warning (exit 0); now it must fail.
cat > "$TMP/gd-empty-anchor.md" <<'MD'
# synthetic gd.md (empty-shell plan anchor)

<!-- gd-runtime-strict-required:start stage=plan -->
this anchor claims a runtime check but binds no validator at all
<!-- gd-runtime-strict-required:end stage=plan -->

<!-- gd-runtime-strict-required:start stage=probe -->
run `python3 scripts/gd-validate-planning-dispatch-log.py log.json --strict-live-proof`
also `python3 scripts/gd-validate-probe.py probe.json --strict-live-proof`
<!-- gd-runtime-strict-required:end stage=probe -->

<!-- gd-runtime-strict-required:start stage=execute-agent-exec -->
run `python3 scripts/gd-validate-planning-dispatch-log.py log.json --strict-live-proof`
<!-- gd-runtime-strict-required:end stage=execute-agent-exec -->

<!-- gd-runtime-strict-required:start stage=review-router -->
run `python3 scripts/gd-validate-route-report.py route.json --schema-version 1.0`
<!-- gd-runtime-strict-required:end stage=review-router -->
MD
assert_exit 1 "runtime-strict-binding: empty-shell anchor rejected" \
  "$PY" "$SCRIPTS/gd-validate-runtime-strict-binding.py" --source "$TMP/gd-empty-anchor.md"

# ===========================================================================
echo "== V9: gd-validate-controller-report.py (additionalProperties) =="
# Positive: a valid v1.0 controller report passes.
cat > "$TMP/ctrl-ok.json" <<'JSON'
{
  "schema_version": "1.0",
  "run_mode": "live",
  "started_at": "2026-06-16T10:00:00Z",
  "finished_at": "2026-06-16T10:05:00Z",
  "aggregate_path": "agg.json",
  "manifest_path": "manifest.json",
  "primary_gate": { "verdict": "APPROVED", "blocking": [] },
  "secondary_gate": { "verdict": "APPROVED", "blocking": [] },
  "gate_consistent": true,
  "dirty_detected": false,
  "jobs": [
    {
      "queue_job_id": "job-001",
      "target_role": "plan",
      "primary_target": "plans/step.md",
      "bridge_exit": 0,
      "bridge_stderr_path": null,
      "bridge_stderr_summary": "none",
      "raw_verdict": "APPROVED",
      "mapped_status": "approved",
      "aggregate_bucket": "primary"
    }
  ]
}
JSON
assert_exit 0 "controller-report: clean v1.0 report passes" \
  "$PY" "$SCRIPTS/gd-validate-controller-report.py" "$TMP/ctrl-ok.json"

# Negative: an extra/unknown top-level field must be rejected (additionalProperties:false).
"$PY" - "$TMP/ctrl-ok.json" "$TMP/ctrl-extra.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
d["sneaky_backdoor_field"] = "approve me"
json.dump(d, open(sys.argv[2], "w"))
PYEOF
assert_exit 2 "controller-report: unknown extra field rejected" \
  "$PY" "$SCRIPTS/gd-validate-controller-report.py" "$TMP/ctrl-extra.json"

# Negative: boolean field carrying a string "true" must be rejected (V11 via schema).
"$PY" - "$TMP/ctrl-ok.json" "$TMP/ctrl-strbool.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
d["gate_consistent"] = "true"   # string, not bool
json.dump(d, open(sys.argv[2], "w"))
PYEOF
assert_exit 2 "controller-report: string \"true\" boolean rejected" \
  "$PY" "$SCRIPTS/gd-validate-controller-report.py" "$TMP/ctrl-strbool.json"

# ===========================================================================
echo "== V12: gd-validate-parent-close-gate.py (unconditional ineligible) =="
# Positive: a closure JSON with verdict=APPROVED + all jobs approved + the
# required evidence paths present must pass.
echo '{"schema_version":"1.0"}' > "$TMP/ctrl-ref.json"   # placeholder controller ref content
echo '{}' > "$TMP/ledger-ref.json"
# Build a closure JSON. Use a schema-valid controller report on disk so Rule 2b passes.
cp "$TMP/ctrl-ok.json" "$TMP/ctrl-for-closure.json"
cat > "$TMP/closure-ok.json" <<JSON
{
  "verdict": "APPROVED",
  "aggregate_source": "aggregate-final.json",
  "closure_evidence": {
    "controller_report_path": "$TMP/ctrl-for-closure.json",
    "stage_dispatch_ledger_path": "$TMP/ledger-ref.json"
  },
  "jobs": [
    { "queue_job_id": "job-001", "mapped_status": "approved" }
  ]
}
JSON
assert_exit 0 "parent-close-gate: legit APPROVED closure passes" \
  "$PY" "$SCRIPTS/gd-validate-parent-close-gate.py" "$TMP/closure-ok.json"

# Negative (V12 core): verdict MISSING but a job carries an ineligible
# mapped_status (human_exec). Pre-hardening this slipped through because the
# ineligible check only ran when verdict==APPROVED. Now it must fail.
cat > "$TMP/closure-ineligible.json" <<JSON
{
  "aggregate_source": "aggregate-final.json",
  "closure_evidence": {
    "controller_report_path": "$TMP/ctrl-for-closure.json",
    "stage_dispatch_ledger_path": "$TMP/ledger-ref.json"
  },
  "jobs": [
    { "queue_job_id": "job-x", "mapped_status": "human_exec" }
  ]
}
JSON
assert_exit 1 "parent-close-gate: ineligible job rejected even w/ no verdict" \
  "$PY" "$SCRIPTS/gd-validate-parent-close-gate.py" "$TMP/closure-ineligible.json"

# ===========================================================================
echo "== V5: gd-validate-stage-dispatch-ledger.py (no silent jsonschema downgrade) =="
# Negative: missing required field must fail in BOTH the jsonschema path and the
# manual fallback (force ImportError to exercise the fallback).
cat > "$TMP/ledger-bad.json" <<'JSON'
{
  "schema_version": "1.0",
  "stage": "plan",
  "parent_run_id": "run-1",
  "recorded_at": "2026-06-16T10:00:00Z",
  "child_agent_count": 1,
  "max_parallel": 1,
  "child_jobs": [
    { "job_id": "j1", "result_path": "r.json", "result_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "status": "completed" }
  ],
  "main_agent_merge": {
    "merge_report_path": "m.md",
    "merge_report_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "final_decision": "APPROVED",
    "blocking_buckets": []
  }
}
JSON
# (missing batch_id)
assert_nonzero "stage-ledger: missing batch_id rejected (jsonschema path)" \
  "$PY" "$SCRIPTS/gd-validate-stage-dispatch-ledger.py" "$TMP/ledger-bad.json"

ledger_fallback() {
  "$PY" - "$1" <<'PYEOF'
import sys, builtins, importlib.util
real_import = builtins.__import__
def fake_import(name, *a, **k):
    if name == "jsonschema":
        raise ImportError("simulated-missing")
    return real_import(name, *a, **k)
builtins.__import__ = fake_import
spec = importlib.util.spec_from_file_location(
    "ledger", "scripts/gd-validate-stage-dispatch-ledger.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
data = __import__("json").load(open(sys.argv[1]))
errs = m.validate(data)
sys.exit(1 if errs else 0)
PYEOF
}
assert_nonzero "stage-ledger: missing batch_id rejected (jsonschema-missing fallback)" \
  ledger_fallback "$TMP/ledger-bad.json"

# Positive: a valid ledger passes (jsonschema path).
cat > "$TMP/ledger-ok.json" <<'JSON'
{
  "schema_version": "1.0",
  "stage": "plan",
  "parent_run_id": "run-1",
  "batch_id": "batch-single",
  "recorded_at": "2026-06-16T10:00:00Z",
  "child_agent_count": 1,
  "max_parallel": 1,
  "child_jobs": [
    { "job_id": "j1", "result_path": "r.json", "result_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "status": "completed" }
  ],
  "main_agent_merge": {
    "merge_report_path": "m.md",
    "merge_report_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "final_decision": "APPROVED",
    "blocking_buckets": []
  }
}
JSON
assert_exit 0 "stage-ledger: valid ledger passes" \
  "$PY" "$SCRIPTS/gd-validate-stage-dispatch-ledger.py" "$TMP/ledger-ok.json"

# ===========================================================================
echo "== built-in self-tests (regression: hardening must not break them) =="
assert_exit 0 "self-test: stage-dispatch-ledger --self-test-minimal" \
  "$PY" "$SCRIPTS/gd-validate-stage-dispatch-ledger.py" --self-test-minimal
assert_exit 0 "self-test: stage-dispatch-ledger --selftest" \
  "$PY" "$SCRIPTS/gd-validate-stage-dispatch-ledger.py" --selftest
assert_exit 0 "self-test: controller-report --self-test-minimal" \
  "$PY" "$SCRIPTS/gd-validate-controller-report.py" --self-test-minimal
assert_exit 0 "self-test: runtime-strict-binding --check-singleton" \
  "$PY" "$SCRIPTS/gd-validate-runtime-strict-binding.py" --check-singleton

# ===========================================================================
echo "==========================================================="
echo "RESULT: PASSES=$PASSES FAILS=$FAILS"
if [ "$FAILS" -eq 0 ]; then
  echo "GD_VALIDATOR_HARDENING_SMOKE: PASS"
  exit 0
else
  echo "GD_VALIDATOR_HARDENING_SMOKE: FAIL"
  exit 1
fi
