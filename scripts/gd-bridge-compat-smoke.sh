#!/usr/bin/env bash
# Smoke test: verify bridge v1 compat works for execution_outcome and combined kinds.
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
BRIDGE="$MAIN/scripts/gd-codex-bridge-review.py"
TMPDIR_BASE="${TMPDIR:-/var/folders/$(id -u)}"
RAW_FILE=$(mktemp "${TMPDIR:-/var/tmp}/gd-bridge-smoke-XXXXXX.md")
OUT_FILE=$(mktemp "${TMPDIR:-/var/tmp}/gd-bridge-smoke-out-XXXXXX.json")
trap 'rm -f "$RAW_FILE" "$OUT_FILE"' EXIT

echo "=== GD Bridge v1 Compat Smoke ==="

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

# Test 1 & 2: compat-v1 kinds
for kind in execution_outcome combined; do
  if python3 "$BRIDGE" parse-transport \
      --kind "$kind" --target "smoke-target" \
      --raw-result "$RAW_FILE" --out "$OUT_FILE" \
      --compat-v1 2>/dev/null; then
    status=$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('review_run_status','?'))")
    decision=$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('gd_review_decision','?'))")
    echo "  PASS: $kind + compat-v1 => status=$status decision=$decision"
    PASS=$((PASS+1))
  else
    echo "  FAIL: $kind + compat-v1 should map v1 raw but failed"
    FAIL=$((FAIL+1))
  fi
done

# Test 3: G2 — execution_outcome WITHOUT any flag auto-infers --compat-v1 (must PASS)
if python3 "$BRIDGE" parse-transport \
    --kind "execution_outcome" --target "smoke-target" \
    --raw-result "$RAW_FILE" --out "$OUT_FILE" 2>/dev/null; then
  echo "  PASS: execution_outcome without explicit flag auto-infers compat-v1 (G2)"
  PASS=$((PASS+1))
else
  echo "  FAIL: execution_outcome should auto-infer compat-v1 and pass v1 raw"
  FAIL=$((FAIL+1))
fi

# Test 4: explicit --no-compat-v1 MUST reject v1 raw for execution_outcome
if python3 "$BRIDGE" parse-transport \
    --kind "execution_outcome" --target "smoke-target" \
    --raw-result "$RAW_FILE" --out "$OUT_FILE" \
    --no-compat-v1 2>/dev/null; then
  echo "  FAIL: execution_outcome --no-compat-v1 should reject v1 raw but passed"
  FAIL=$((FAIL+1))
else
  echo "  PASS: execution_outcome --no-compat-v1 correctly rejects v1 raw"
  PASS=$((PASS+1))
fi

echo ""
echo "=== BRIDGE_COMPAT_SMOKE: pass=$PASS fail=$FAIL ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
