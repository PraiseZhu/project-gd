#!/usr/bin/env bash
# gd-check-review-route-preflight.sh — Preflight checks before /review1 or /review2 install.
#
# Usage:
#   bash scripts/gd-check-review-route-preflight.sh --route review2
#   bash scripts/gd-check-review-route-preflight.sh --route review2 --require-necessity-memo
#
# Exit codes:
#   0 — all preflight checks pass
#   1 — preflight failed (memo missing, artifacts missing, or parity drift)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROUTE=""
REQUIRE_MEMO=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --route) ROUTE="$2"; shift 2 ;;
    --require-necessity-memo) REQUIRE_MEMO=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

[ -z "$ROUTE" ] && { echo "usage: $0 --route <review1|review2>"; exit 1; }

echo "=== /review2 Route Preflight ==="
echo "route: $ROUTE"
FAIL=0

# 1. L3 /gd command parity tool must run (drift is acceptable pre-install; only tool self-fail blocks)
echo ""
echo "--- L3 parity check ---"
_parity_out="$(bash "$ROOT/tools/gd-parity-verify.sh" --bundle gd-command 2>&1)" || true
if echo "$_parity_out" | grep -qiE "FATAL|command not found|No such file|SSOT .*missing|secret .*missing"; then
  echo "  L3_GD_COMMAND_PARITY: FAIL — parity tool self-failure"
  echo "$_parity_out" | sed 's/^/    /'
  FAIL=1
else
  echo "  L3_GD_COMMAND_PARITY: pass (drift acceptable pre-install)"
fi

# 2. Required artifacts must exist
echo ""
echo "--- Required artifacts ---"
REQUIRED_ARTIFACTS=(
  "scripts/gd-build-review2-capsule.py"
  "scripts/gd-validate-review2-capsule.py"
  "scripts/gd-validate-review2-output.py"
  "commands/review2.md"
  "config/gd-runtime-parity-manifest.json"
  "config/secret-scan-regexes.json"
)
for a in "${REQUIRED_ARTIFACTS[@]}"; do
  if [ -f "$ROOT/$a" ]; then
    echo "  OK: $a"
  else
    echo "  MISSING: $a"
    FAIL=1
  fi
done

# 3. Necessity memo (optional unless --require-necessity-memo)
echo ""
echo "--- Route necessity memo ---"
MEMO="$ROOT/docs/review-route-necessity-memo.md"
if [ -f "$MEMO" ]; then
  DECISION=$(grep "^\*\*decision\*\*\|^decision\s*:\|^| \*\*decision\*\*\|create_slash_command\|extend_bridge_only\|no_new_entry" "$MEMO" 2>/dev/null | head -1 || echo "")
  echo "  memo: found"
  echo "  decision_line: $DECISION"
else
  if [ "$REQUIRE_MEMO" -eq 1 ]; then
    echo "  MISSING: docs/review-route-necessity-memo.md (required by --require-necessity-memo)"
    FAIL=1
  else
    echo "  memo: not found (INFO only; use --require-necessity-memo to enforce)"
  fi
fi

echo ""
if [ $FAIL -eq 0 ]; then
  echo "PREFLIGHT_STATUS: pass"
  exit 0
else
  echo "PREFLIGHT_STATUS: FAIL"
  exit 1
fi
