#!/usr/bin/env bash
# gd-review2-plan-template-preflight-smoke.sh — Phase 3 smoke test (SC-3, SC-5, SC-9)
# Verifies:
#   SC-9: plan-template.md no longer contains REVIEW_STANDARD or REV_VERDICT at line start
#   SC-3/SC-5: preflight accepts compliant plans; rejects capsule/missing-sc/old-rev style

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

PASS=0; FAIL=0

pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

run_preflight() {
    local target="$1"
    local _ex=0
    python3 scripts/gd-validate-review2-plan-target.py --target "$target" || _ex=$?
    echo "EXIT:$_ex"
    return "$_ex"
}

echo "=== Plan Template Preflight Smoke ==="

# --- SC-9: plan-template.md markers ---
echo
echo "--- SC-9: plan-template.md template markers ---"
if grep -qE '^REVIEW_STANDARD[：:]' templates/plan-template.md 2>/dev/null; then
    fail "plan-template.md still has line-leading REVIEW_STANDARD:"
else
    pass "plan-template.md has no line-leading REVIEW_STANDARD:"
fi

if grep -qE '^REV_VERDICT[：:]' templates/plan-template.md 2>/dev/null; then
    fail "plan-template.md still has line-leading REV_VERDICT:"
else
    pass "plan-template.md has no line-leading REV_VERDICT:"
fi

if grep -qE '^GD_STANDARD[：:]' templates/plan-template.md 2>/dev/null; then
    pass "plan-template.md has GD_STANDARD:"
else
    fail "plan-template.md missing GD_STANDARD:"
fi

if grep -qE 'REVIEW_DOMAIN[：:]' templates/plan-template.md 2>/dev/null; then
    pass "plan-template.md has REVIEW_DOMAIN"
else
    fail "plan-template.md missing REVIEW_DOMAIN"
fi

if grep -qE 'WHERE[：:]|WHAT[：:]|WHY[：:]|VERIFY[：:]' templates/plan-template.md 2>/dev/null; then
    pass "plan-template.md has WHERE/WHAT/WHY/VERIFY step fields"
else
    fail "plan-template.md missing step fields"
fi

# --- SC-3/SC-5: preflight accepts good plans ---
echo
echo "--- SC-3/SC-5: preflight accepts compliant plans ---"

out1=$(python3 scripts/gd-validate-review2-plan-target.py \
    --target fixtures/review2-plan/good-plan.md 2>/dev/null)
if echo "$out1" | grep -q "PLAN_TEMPLATE_STATUS: pass"; then
    pass "good-plan.md → PASS"
else
    fail "good-plan.md → unexpected: $(echo "$out1" | head -2)"
fi

out2=$(python3 scripts/gd-validate-review2-plan-target.py \
    --target fixtures/review2-plan/gd-step-style-good-plan.md 2>/dev/null)
if echo "$out2" | grep -q "PLAN_TEMPLATE_STATUS: pass"; then
    pass "gd-step-style-good-plan.md → PASS"
else
    fail "gd-step-style-good-plan.md → unexpected: $(echo "$out2" | head -2)"
fi

# --- SC-5: preflight rejects bad cases ---
echo
echo "--- SC-5: preflight rejects bad targets ---"

_ex=0
out3=$(python3 scripts/gd-validate-review2-plan-target.py \
    --target fixtures/review2-plan/missing-sc-plan.md 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out3" | grep -q "PLAN_TEMPLATE_STATUS: fail"; then
    pass "missing-sc-plan.md → FAIL (exit 1) ✓"
else
    fail "missing-sc-plan.md → expected fail exit 1, got exit $_ex: $(echo "$out3" | head -2)"
fi

_ex=0
out4=$(python3 scripts/gd-validate-review2-plan-target.py \
    --target fixtures/review2-plan/old-rev-style-plan.md 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out4" | grep -q "PLAN_TEMPLATE_STATUS: fail"; then
    pass "old-rev-style-plan.md → FAIL (exit 1) ✓"
else
    fail "old-rev-style-plan.md → expected fail exit 1, got exit $_ex: $(echo "$out4" | head -2)"
fi

_ex=0
out5=$(python3 scripts/gd-validate-review2-plan-target.py \
    --target fixtures/review2-plan/results/review-route-split/case/capsule.md 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out5" | grep -q "PLAN_TEMPLATE_STATUS: fail"; then
    pass "capsule.md as target → FAIL (exit 1) ✓"
else
    fail "capsule.md as target → expected fail exit 1, got exit $_ex: $(echo "$out5" | head -2)"
fi

# --- P2-A fix: missing WHERE/WHAT/WHY/VERIFY each individually ---
echo
echo "--- SC-5: preflight rejects plans missing individual step fields (P2-A) ---"

for missing_field in WHERE WHAT WHY VERIFY; do
    field_lower="$(echo "$missing_field" | tr '[:upper:]' '[:lower:]')"
    fixture="fixtures/review2-plan/missing-${field_lower}-plan.md"
    _ex=0
    out_f=$(python3 scripts/gd-validate-review2-plan-target.py --target "$fixture" 2>/dev/null) || _ex=$?
    if [[ $_ex -eq 1 ]] && echo "$out_f" | grep -q "PLAN_TEMPLATE_STATUS: fail" && \
       echo "$out_f" | grep -q "missing step field ${missing_field}"; then
        pass "missing-${field_lower}-plan.md → FAIL + missing step field ${missing_field} ✓"
    else
        fail "missing-${field_lower}-plan.md → expected fail + 'missing step field ${missing_field}', got exit $_ex: $(echo "$out_f" | head -3)"
    fi
done

# --- Summary ---
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "SC-3/SC-5/SC-9: PASS"
    exit 0
else
    echo "SC-3/SC-5/SC-9: FAIL"
    exit 1
fi
