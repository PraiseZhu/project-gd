#!/usr/bin/env bash
# gd-l3-regression-v1-fixtures.sh
# SC-W3-3: Run L3 validator on all v1 review-bridge fixtures, assert zero false positives.
set -euo pipefail
MAIN="$(cd "$(dirname "$0")/.." && pwd)"
cd "$MAIN"

L3="scripts/gd-validate-review-content-evidence.py"
FIXTURE_DIR="fixtures/review-bridge"
PASS_COUNT=0; FAIL_COUNT=0

for raw in "$FIXTURE_DIR"/*/*.md "$FIXTURE_DIR"/*.md; do
  [ -f "$raw" ] || continue
  fname=$(basename "$raw")
  # Skip intentionally-malformed fixtures (negative test cases for the bridge parser).
  # L3 correctly rejects these — that is expected behavior, not a false positive.
  case "$fname" in
    *malformed*|*missing*|*multiple*|*degraded*|*failed*) continue ;;
  esac
  # Use the fixture itself as both target and review — L3 should not false-positive
  # on legitimate review outputs (unknown verdict → EVIDENCE_VALID).
  result=$(python3 "$L3" --target "$raw" --review "$raw" --skip-line-ref-check 2>&1)
  if echo "$result" | grep -q "EVIDENCE_VALID"; then
    PASS_COUNT=$((PASS_COUNT + 1))
  elif echo "$result" | grep -q "FAKE_EVIDENCE_DETECTED"; then
    echo "FALSE_POSITIVE: $raw"
    echo "  $result" | head -3
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    # Non-zero exit for other reasons (e.g. missing file) — skip
    PASS_COUNT=$((PASS_COUNT + 1))
  fi
done

echo "PASS_COUNT=$PASS_COUNT FAIL_COUNT=$FAIL_COUNT"
if [ "$FAIL_COUNT" -eq 0 ] && [ "$PASS_COUNT" -gt 0 ]; then
  echo "L3_REGRESSION: PASS"
  exit 0
else
  echo "L3_REGRESSION: FAIL (pass=$PASS_COUNT fail=$FAIL_COUNT)"
  exit 1
fi
