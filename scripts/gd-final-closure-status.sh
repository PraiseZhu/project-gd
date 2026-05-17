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
