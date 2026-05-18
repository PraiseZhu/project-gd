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

# 4. Installed parity
main_hash=$(md5 -q commands/gd.md 2>/dev/null || echo "MISSING")
inst_hash=$(md5 -q "$HOME/.claude/commands/gd.md" 2>/dev/null || echo "MISSING")
if [ "$main_hash" = "$inst_hash" ]; then
  echo "  PASS: installed parity ($main_hash)"
  PASS=$((PASS+1))
else
  echo "  FAIL: installed parity DRIFT (main=$main_hash installed=$inst_hash)"
  FAIL=$((FAIL+1))
fi

# 5. Bridge compat smoke (actually execute, not just check existence)
check "bridge compat smoke" \
  bash scripts/gd-bridge-compat-smoke.sh

# 6. Backup manifest valid JSON
MANIFEST="reports/project-gd-flow-closure-rev21/20260517T154346Z/backup-manifest.json"
check "backup manifest valid JSON" \
  bash -c "python3 -m json.tool '$MANIFEST' >/dev/null"

# 7. Product scripts present and executable
for s in \
  scripts/gd-root-parity-status.sh \
  scripts/gd-install-rev21-for-handtest.sh \
  scripts/gd-check-installed-parity.sh \
  scripts/gd-bridge-compat-smoke.sh \
  scripts/gd-final-closure-status.sh; do
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
    fixtures/negative/final-controller-report-invalid-json.json 2>&1 | grep -q controller_report_invalid_json'

# 10 (F2/C4). Deterministic capsule-build checks for execution_outcome and combined.
# Replaces previous --live-transport check (which invoked Codex writer; unstable, slow).
# build-capsule does NOT call writer; only validates the capsule construction stage
# where F1 (INVALID_REVIEW_KIND_FOR_MODE) would surface as regression.
F2_EO_OUT="/tmp/gd-f2-eo-$$.txt"
F2_EO_STDOUT=$(python3 scripts/gd-codex-bridge-review.py build-capsule \
  --kind execution_outcome \
  --target fixtures/execution-outcome/valid-agent-exec-outcome.json \
  --cwd . --out "$F2_EO_OUT" 2>/dev/null) || true
rm -f "$F2_EO_OUT"
if echo "$F2_EO_STDOUT" | grep -q "^QUEUE_JOB_ID:"; then
  echo "  PASS: F2/C4 build-capsule execution_outcome produces QUEUE_JOB_ID (no writer call)"
  PASS=$((PASS+1))
else
  echo "  FAIL: F2/C4 build-capsule execution_outcome did not produce QUEUE_JOB_ID — F1 regression?"
  FAIL=$((FAIL+1))
fi

F2_CB_OUT="/tmp/gd-f2-cb-$$.txt"
F2_CB_STDOUT=$(python3 scripts/gd-codex-bridge-review.py build-capsule \
  --kind combined \
  --target fixtures/execution-outcome/valid-agent-exec-outcome.json \
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

# D4 negative: APPROVED route report missing ledger must fail validator (regression guard)
check "D4 negative route-missing-child-review-ledger rejected by validator" \
  bash -c '! python3 scripts/gd-validate-route-report.py \
    fixtures/negative/route-missing-child-review-ledger.json 2>/dev/null'

# V3-F: bridge preflight status check
# Fails only if preflight was started (dir exists) but report/route_decision is missing.
# If preflight has not been run yet: INFO-only, does not affect pass/fail count.
PREFLIGHT_DIR="reports/bridge-preflight"
if [ -d "$PREFLIGHT_DIR" ]; then
  LATEST_REPORT=$(find "$PREFLIGHT_DIR" -name "preflight-report.json" | sort -r | head -1)
  if [ -n "$LATEST_REPORT" ]; then
    ROUTE=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); print(d.get('route_decision') or '')" 2>/dev/null)
    if [ -n "$ROUTE" ] && [ "$ROUTE" != "null" ]; then
      echo "  PASS: preflight-report.json route_decision=$ROUTE"
      PASS=$((PASS+1))
    else
      echo "  FAIL: preflight-report.json exists but route_decision is null/empty"
      FAIL=$((FAIL+1))
    fi
  else
    echo "  FAIL: preflight dir exists but no preflight-report.json found"
    FAIL=$((FAIL+1))
  fi
else
  echo "  INFO: bridge preflight not yet run (run scripts/gd-bridge-preflight.py first)"
fi

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
