#!/usr/bin/env bash
# Quick final-gate readiness check: run all key validators in self-test mode,
# verify parity, confirm product scripts are present and functional.
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
cd "$MAIN"

echo "=== GD Final Closure Status ==="
PASS=0; FAIL=0

check() {
  local label="$1"; shift
  if "$@" 2>/dev/null; then
    echo "  PASS: $label"
    PASS=$((PASS+1))
  else
    echo "  FAIL: $label"
    FAIL=$((FAIL+1))
  fi
}

# 1. Stage dispatch ledger self-test
check "validate-stage-dispatch-ledger --self-test-minimal" \
  python3 scripts/gd-validate-stage-dispatch-ledger.py --self-test-minimal

# 2. Bridge self-test
check "bridge self-test" \
  python3 scripts/gd-codex-bridge-review.py self-test

# 3. Final gate rejects 3 representative negative fixtures
check "final gate rejects final-fixture-mode-tagged" \
  bash -c '! python3 scripts/gd-validate-parent-close-gate.py fixtures/negative/final-fixture-mode-tagged.json 2>/dev/null'
check "final gate rejects final-transport-failed-approved" \
  bash -c '! python3 scripts/gd-validate-parent-close-gate.py fixtures/negative/final-transport-failed-approved.json 2>/dev/null'
check "final gate rejects final-zero-child-approved" \
  bash -c '! python3 scripts/gd-validate-parent-close-gate.py fixtures/negative/final-zero-child-approved.json 2>/dev/null'

# 4. Installed parity (SHA256 — plugin marketplace runtime; FR-007 retired the legacy ~/.claude/commands/ copy)
main_hash=$(shasum -a 256 commands/gd.md 2>/dev/null | awk '{print $1}' || echo "MISSING")
inst_hash=$(shasum -a 256 "$HOME/.claude/plugins/marketplaces/project-gd-marketplace/commands/gd.md" 2>/dev/null | awk '{print $1}' || echo "MISSING")
if [ "$main_hash" = "$inst_hash" ]; then
  echo "  PASS: installed parity (sha256=$main_hash)"
  PASS=$((PASS+1))
else
  echo "  FAIL: installed parity DRIFT (main=$main_hash installed=$inst_hash)"
  FAIL=$((FAIL+1))
fi

# 5. Bridge compat smoke (actually execute, not just check existence)
check "bridge compat smoke" \
  bash tests/gd-bridge-compat-smoke.sh

# 6. Backup manifest valid JSON
MANIFEST="reports/project-gd-flow-closure-rev21/20260517T154346Z/backup-manifest.json"
check "backup manifest valid JSON" \
  bash -c "python3 -m json.tool '$MANIFEST' >/dev/null"

# 7. Product scripts present and executable
# Note: gd-install-rev21-for-handtest.sh moved to archive/ (one-time task complete)
#       gd-bridge-compat-smoke.sh moved to tests/ (smoke/regression isolation)
for s in \
  tools/gd-root-parity-status.sh \
  tools/gd-parity-verify.sh \
  tools/gd-final-closure-status.sh \
  tests/gd-bridge-compat-smoke.sh; do
  check "script executable: $s" test -x "$s"
done

# 8. G1 sentinel: direct run-bridge execution_outcome --live-transport (no env) must be forbidden
check "G1 sentinel: direct run-bridge execution_outcome forbidden without router env" \
  bash -c 'python3 scripts/gd-codex-bridge-review.py run-bridge \
    --kind execution_outcome --target /tmp/fake --cwd . --out /tmp/x \
    --live-transport 2>&1 | grep -q DIRECT_BRIDGE_FORBIDDEN_FOR_EXECUTION_KIND'

# 9. G4 file-exists: final gate rejects path-not-found and invalid-json controller reports
check "G4 gate rejects controller-report path-not-found" \
  bash -c 'python3 scripts/gd-validate-parent-close-gate.py \
    fixtures/negative/final-controller-report-path-not-found.json 2>&1 | grep -q controller_report_file_not_found'
check "G4 gate rejects controller-report invalid-json" \
  bash -c 'python3 scripts/gd-validate-parent-close-gate.py \
    fixtures/negative/final-controller-report-invalid-json.json 2>&1 | grep -q controller_report_invalid'

# 10 (F2/C4). Deterministic capsule-build checks for execution_outcome and combined.
F2_EO_OUT="${TMPDIR:-/var/tmp}/gd-f2-eo-$$.txt"
F2_EO_STDOUT=$(python3 scripts/gd-codex-bridge-review.py build-capsule \
  --kind execution_outcome \
  --target fixtures/execution-outcome/valid-outcome-d1-test.json \
  --cwd . --out "$F2_EO_OUT" 2>/dev/null) || true
rm -f "$F2_EO_OUT"
if echo "$F2_EO_STDOUT" | grep -q "^QUEUE_JOB_ID:"; then
  echo "  PASS: F2/C4 build-capsule execution_outcome produces QUEUE_JOB_ID (no writer call)"
  PASS=$((PASS+1))
else
  echo "  FAIL: F2/C4 build-capsule execution_outcome did not produce QUEUE_JOB_ID — F1 regression?"
  FAIL=$((FAIL+1))
fi

F2_CB_OUT="${TMPDIR:-/var/tmp}/gd-f2-cb-$$.txt"
F2_CB_STDOUT=$(python3 scripts/gd-codex-bridge-review.py build-capsule \
  --kind combined \
  --target fixtures/execution-outcome/valid-outcome-d1-test.json \
  --cwd . --out "$F2_CB_OUT" 2>/dev/null) || true
rm -f "$F2_CB_OUT"
if echo "$F2_CB_STDOUT" | grep -q "^QUEUE_JOB_ID:"; then
  echo "  PASS: F2/C4 build-capsule combined produces QUEUE_JOB_ID (no writer call)"
  PASS=$((PASS+1))
else
  echo "  FAIL: F2/C4 build-capsule combined did not produce QUEUE_JOB_ID — F1/C3 regression?"
  FAIL=$((FAIL+1))
fi

# D4 positive: APPROVED route report with valid ledger must pass validator
check "D4 positive route-with-ledger-approved passes validator" \
  python3 scripts/gd-validate-route-report.py fixtures/positive/route-with-ledger-approved.json

# D4 negative: APPROVED route report missing ledger must fail validator
check "D4 negative route-missing-child-review-ledger rejected by validator" \
  bash -c '! python3 scripts/gd-validate-route-report.py \
    fixtures/negative/route-missing-child-review-ledger.json 2>/dev/null'

# Preflight bridge route (informational — does not block if not yet run)
PREFLIGHT_DIR="reports/bridge-preflight"
PREFLIGHT_PASS_ROUTES="no_fix_needed_or_intermittent config_isolation bypass_daemon shard"
if [ -d "$PREFLIGHT_DIR" ]; then
  LATEST_REPORT=$(find "$PREFLIGHT_DIR" -name "preflight-report.json" | sort -r | head -1)
  if [ -n "$LATEST_REPORT" ]; then
    ROUTE=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); print(d.get('route_decision') or '')" 2>/dev/null)
    if [ -z "$ROUTE" ] || [ "$ROUTE" = "null" ]; then
      echo "  FAIL: preflight-report.json exists but route_decision is null/empty"
      FAIL=$((FAIL+1))
    elif echo "$PREFLIGHT_PASS_ROUTES" | grep -qw "$ROUTE"; then
      echo "  PASS: preflight route=$ROUTE"
      PASS=$((PASS+1))
    elif [ "$ROUTE" = "escalate_outside_scope" ]; then
      echo "  FAIL: preflight route=escalate_outside_scope"
      FAIL=$((FAIL+1))
    elif [ "$ROUTE" = "inconclusive" ]; then
      echo "  FAIL: preflight route=inconclusive"
      FAIL=$((FAIL+1))
    else
      echo "  FAIL: preflight route=$ROUTE (unknown)"
      FAIL=$((FAIL+1))
    fi
  else
    echo "  FAIL: preflight dir exists but no preflight-report.json found"
    FAIL=$((FAIL+1))
  fi
else
  echo "  INFO: bridge preflight not yet run"
fi

# 11. Plan preflight (master-plan consistency) checks
check "plan-preflight: script exists" \
  test -f scripts/gd-validate-master-plan-consistency.py

check "plan-preflight: positive clean-plan fixture passes" \
  python3 scripts/gd-validate-master-plan-consistency.py \
    fixtures/preflight/positive-clean-plan.md

check "plan-preflight: negative owned-forbidden-overlap fires (exit=1)" \
  bash -c '! python3 scripts/gd-validate-master-plan-consistency.py \
    fixtures/preflight/negative-owned-forbidden-overlap.md 2>/dev/null'

check "plan-preflight: negative sc-verify-missing fires (exit=1)" \
  bash -c '! python3 scripts/gd-validate-master-plan-consistency.py \
    fixtures/preflight/negative-sc-verify-missing.md 2>/dev/null'

check "plan-preflight: negative protected-runtime-owned fires (exit=1)" \
  bash -c '! python3 scripts/gd-validate-master-plan-consistency.py \
    fixtures/preflight/negative-protected-runtime-owned.md 2>/dev/null'

check "plan-preflight: semantic-regression fixture passes" \
  python3 scripts/gd-validate-master-plan-consistency.py \
    fixtures/preflight/semantic-regression-passes-preflight.md

check "plan-preflight: legacy plan returns SKIPPED_LEGACY_PLAN" \
  bash -c 'out=$(python3 scripts/gd-validate-master-plan-consistency.py \
    fixtures/plans/phase2-good-plan.md 2>&1); \
    echo "$out" | grep -q SKIPPED_LEGACY_PLAN'

# 12. L1+L3+L1.5 production wiring sanity
check "L1: capsule externalized for plan kind" \
  bash -c 'out=$(python3 scripts/gd-codex-bridge-review.py build-capsule \
    --kind plan --target plans/gd/2026-05-19-review-chain-hardening/master-plan.md \
    --cwd . --out "${TMPDIR:-/var/tmp}/gd-l1-sanity-$$.json" --compat-v1 2>&1); \
    size=$(wc -c < "${TMPDIR:-/var/tmp}/gd-l1-sanity-$$.json" 2>/dev/null || echo 999999); \
    rm -f "${TMPDIR:-/var/tmp}/gd-l1-sanity-$$.json"; [ "$size" -le 30720 ]'

check "L3: validator wired into parse-transport" \
  grep -q "gd-validate-review-content-evidence" scripts/gd-codex-bridge-review.py

check "L3: fake SC-ID detected" \
  bash -c '! python3 scripts/gd-validate-review-content-evidence.py \
    --target fixtures/preflight/dispatch-map-without-ghost-step.json \
    --review fixtures/preflight/l3-fake-review-sample.md 2>/dev/null'

check "L1.5: execution_outcome capsule has MANDATORY VERIFY STEP" \
  bash -c 'python3 scripts/gd-codex-bridge-review.py build-capsule \
    --kind execution_outcome \
    --target fixtures/execution-results/valid-closure.json \
    --cwd . --out "${TMPDIR:-/var/tmp}/gd-l15-sanity-$$.json" 2>/dev/null && \
    grep -q "MANDATORY VERIFY STEP" "${TMPDIR:-/var/tmp}/gd-l15-sanity-$$.json" && \
    rm -f "${TMPDIR:-/var/tmp}/gd-l15-sanity-$$.json"'

check "L1: combined capsule <= 30KB" \
  bash tests/gd-l1-combined-bundle-smoke.sh

# 13. L3 v1 fixture regression (no false positives)
check "L3 v1 fixture regression" \
  bash tests/gd-l3-regression-v1-fixtures.sh

echo ""
echo "=== L1/L2/L3 Release Gate Summary (consumed from gd-codex-chain-release-status.sh) ==="

RELEASE_GATE_OUT=$(bash "$MAIN/tools/gd-codex-chain-release-status.sh" 2>/dev/null || true)
RELEASE_OVERALL=$(echo "$RELEASE_GATE_OUT" | grep "^OVERALL_RELEASE_STATUS:" | awk '{print $2}' || echo "unknown")
L1_RS=$(echo "$RELEASE_GATE_OUT" | grep "^  L1_RELEASE_STATUS:" | awk '{print $2}' || echo "unknown")
L2_RS=$(echo "$RELEASE_GATE_OUT" | grep "^  L2_RELEASE_STATUS:" | awk '{print $2}' || echo "unknown")
L3_RS=$(echo "$RELEASE_GATE_OUT" | grep "^  L3_RELEASE_STATUS:" | awk '{print $2}' || echo "unknown")

echo "  [PARITY]         L3 /gd command: $L3_RS"
echo "  [RELEASE_MIRROR] L1 codex binary: $L1_RS"
echo "  [RELEASE_MIRROR] L2 codex config/mirrors: $L2_RS"
echo "  OVERALL_RELEASE_STATUS: $RELEASE_OVERALL"

if [ "$RELEASE_OVERALL" = "READY_FOR_COMMIT" ]; then
  PASS=$((PASS+1))
else
  echo "  (run bash tools/gd-codex-chain-release-status.sh for details)"
  FAIL=$((FAIL+1))
fi

echo ""
# Canonical field declarations (v3.1 A1 ambiguity disambiguation)
echo "MACHINE_RELEASE_VERDICT_FIELD: OVERALL_RELEASE_STATUS"
echo "HUMAN_REPAIR_SUMMARY_FIELD: GD_REPAIR_RESULT"
echo "AMBIGUITY_STATUS: pass_with_note"
echo ""
echo "=== GD_REPAIR_RESULT: pass=$PASS fail=$FAIL ==="
if [ $FAIL -eq 0 ]; then
  echo "GD_REPAIR_RESULT: READY_FOR_HANDTEST"
  echo "main_hash: $main_hash"
  echo "installed_hash: $inst_hash"
  echo "parity_status: PASS"
  exit 0
else
  echo "GD_REPAIR_RESULT: BLOCKED (fail=$FAIL)"
  exit 1
fi
