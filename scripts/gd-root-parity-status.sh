#!/usr/bin/env bash
# Show parity status between Project GD main root allowlist files and their installed/worktree counterparts.
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLED_GD="$HOME/.claude/commands/gd.md"

echo "=== GD Root Parity Status ==="
echo "main_root: $MAIN"
echo ""

# Check installed parity
main_hash=$(md5 -q "$MAIN/commands/gd.md" 2>/dev/null || echo "MISSING")
inst_hash=$(md5 -q "$INSTALLED_GD" 2>/dev/null || echo "MISSING")
if [ "$main_hash" = "$inst_hash" ]; then
  echo "INSTALLED_PARITY: PASS (hash=$main_hash)"
else
  echo "INSTALLED_PARITY: DRIFT"
  echo "  main:      $main_hash"
  echo "  installed: $inst_hash"
fi

echo ""
echo "=== Key allowlist files ==="
ALLOWLIST=(
  "commands/gd.md"
  "scripts/gd-codex-bridge-review.py"
  "scripts/gd-review-router.py"
  "scripts/gd-review-suite-controller.py"
  "scripts/gd-validate-stage-dispatch-ledger.py"
  "scripts/gd-validate-controller-report.py"
  "scripts/gd-validate-route-report.py"
  "scripts/gd-validate-parent-close-gate.py"
  "scripts/gd-validate-execution-batch.py"
  "schema/gd-stage-dispatch-ledger.schema.json"
  "schema/gd-controller-report.schema.json"
  "schema/gd-route-report.schema.json"
  "schema/gd-execution-batch.schema.json"
)

MISSING=0; PRESENT=0
for f in "${ALLOWLIST[@]}"; do
  if [ -f "$MAIN/$f" ]; then
    hash=$(md5 -q "$MAIN/$f")
    echo "  OK  $f ($hash)"
    PRESENT=$((PRESENT+1))
  else
    echo "  MISSING  $f"
    MISSING=$((MISSING+1))
  fi
done

echo ""
echo "=== Summary: present=$PRESENT missing=$MISSING ==="
[ $MISSING -eq 0 ] && echo "ROOT_PARITY_STATUS: READY" || echo "ROOT_PARITY_STATUS: INCOMPLETE"
