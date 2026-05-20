#!/usr/bin/env bash
# Show parity status between Project GD main root allowlist files and their installed/worktree counterparts.
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLED_GD="$HOME/.claude/commands/gd.md"

echo "=== GD Root Parity Status ==="
echo "main_root: $MAIN"
echo ""

# Check installed parity
main_hash=$(shasum -a 256 "$MAIN/commands/gd.md" 2>/dev/null | awk '{print $1}' || echo "MISSING")
inst_hash=$(shasum -a 256 "$INSTALLED_GD" 2>/dev/null | awk '{print $1}' || echo "MISSING")
if [ "$main_hash" = "$inst_hash" ]; then
  echo "INSTALLED_PARITY: PASS (sha256=$main_hash)"
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
    hash=$(shasum -a 256 "$MAIN/$f" | awk '{print $1}')
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
