#!/usr/bin/env bash
# Smoke test: verify bridge v1 compat works for execution_outcome and combined kinds.
# Requires a valid v1 raw (# Code Review Result + Scope Checked).
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
BRIDGE="$MAIN/scripts/gd-codex-bridge-review.py"

echo "=== GD Bridge v1 Compat Smoke ==="

# Create a minimal valid v1 execution raw
RAW_FILE=$(mktemp /tmp/gd-bridge-smoke-XXXXXX.md)
OUT_FILE=$(mktemp /tmp/gd-bridge-smoke-out-XXXXXX.json)

cat > "$RAW_FILE" << 'RAW'
# Code Review Result

VERDICT: APPROVED
REVIEW_DOMAIN: ai_infra
REVIEW_MODE: single_pass

## Scope Checked

| 检查面 | 结论 | 证据 |
|--------|------|------|
| sc_acceptance_coverage | pass | SC verified |
| deliverable_existence | pass | scripts present |
| owned_paths_compliance | pass | no writes outside owned |

## Findings

none

## Residual Risk

none
RAW

PASS=0; FAIL=0

for kind in execution_outcome combined; do
  python3 "$BRIDGE" parse-transport \
    --kind "$kind" \
    --target "smoke-target" \
    --raw-result "$RAW_FILE" \
    --out "$OUT_FILE" \
    --compat-v1 2>/dev/null

  if [ $? -eq 0 ]; then
    status=$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('review_run_status','?'))")
    decision=$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('gd_review_decision','?'))")
    echo "  PASS: $kind + compat-v1 => status=$status decision=$decision"
    PASS=$((PASS+1))
  else
    echo "  FAIL: $kind + compat-v1 should map v1 raw but failed"
    FAIL=$((FAIL+1))
  fi
done

# Verify default v2 mode correctly rejects v1 raw
python3 "$BRIDGE" parse-transport \
  --kind "execution_outcome" \
  --target "smoke-target" \
  --raw-result "$RAW_FILE" \
  --out "$OUT_FILE" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "  PASS: execution_outcome without --compat-v1 correctly rejects v1 raw"
  PASS=$((PASS+1))
else
  echo "  FAIL: execution_outcome without --compat-v1 should reject v1 raw but passed"
  FAIL=$((FAIL+1))
fi

rm -f "$RAW_FILE" "$OUT_FILE"

echo ""
echo "=== BRIDGE_COMPAT_SMOKE: pass=$PASS fail=$FAIL ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
