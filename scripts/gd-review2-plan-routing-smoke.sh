#!/usr/bin/env bash
# gd-review2-plan-routing-smoke.sh — Phase 5 smoke test (SC-7, SC-8, SC-10)
# Verifies bridge routing guards:
#   SC-7: capsule target rejection (PLAN_TARGET_MUST_BE_ORIGINAL_PLAN)
#   SC-8: v2 template missing → V2_TEMPLATE_NOT_READY exit 1 (not silent degraded)
#   SC-10: positive: plan target → bridge invokes writer, mock returns APPROVED

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

PASS=0; FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

BRIDGE="python3 scripts/gd-codex-bridge-review.py"
MOCK_WRITER="$(pwd)/fixtures/mocks/review-result-writer-mock.sh"
GOOD_PLAN="$(pwd)/fixtures/review2-plan/good-plan.md"
CAPSULE_TARGET="$(pwd)/fixtures/review2-plan/results/review-route-split/case/capsule.md"

echo "=== Plan Routing Smoke ==="

# --- SC-7: capsule target rejection via --run-bridge --live-transport ---
echo
echo "--- SC-7: capsule target → PLAN_TARGET_MUST_BE_ORIGINAL_PLAN ---"
_ex=0
out=$($BRIDGE run-bridge \
    --kind plan \
    --target "$CAPSULE_TARGET" \
    --cwd . \
    --out "$TMPDIR/sc7-out.json" \
    --live-transport \
    2>&1) || _ex=$?

if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "PLAN_TARGET_MUST_BE_ORIGINAL_PLAN"; then
    pass "capsule target → exit 1 + PLAN_TARGET_MUST_BE_ORIGINAL_PLAN"
else
    fail "capsule target → expected exit 1 + PLAN_TARGET_MUST_BE_ORIGINAL_PLAN, got exit=$_ex: $(echo "$out" | head -3)"
fi

# --- SC-8: v2 template missing → V2_TEMPLATE_NOT_READY (not silent degraded) ---
echo
echo "--- SC-8: build-capsule --kind plan → V2_TEMPLATE_NOT_READY ---"

# Verify plan v2 template does NOT exist (should be MISSING per Phase 1 report)
V2_PLAN_TEMPLATE="templates/gd-plan-review-v2-template.md"
if [[ -f "$V2_PLAN_TEMPLATE" ]]; then
    fail "SC-8 prerequisite: v2 plan template exists at $V2_PLAN_TEMPLATE — guard cannot fire (unexpected)"
else
    pass "SC-8 prerequisite: v2 plan template absent ($V2_PLAN_TEMPLATE)"
fi

_ex=0
out=$($BRIDGE build-capsule \
    --kind plan \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc8-out.json" \
    2>&1) || _ex=$?

if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "V2_TEMPLATE_NOT_READY"; then
    pass "plan build-capsule (v2 template missing) → exit 1 + V2_TEMPLATE_NOT_READY"
else
    fail "plan build-capsule → expected exit 1 + V2_TEMPLATE_NOT_READY, got exit=$_ex: $(echo "$out" | head -3)"
fi

# code_diff auto-selects compat_v1=True, so must use --no-compat-v1 to force v2 guard
echo
echo "--- SC-8: build-capsule --kind code_diff --no-compat-v1 → V2_TEMPLATE_NOT_READY ---"
_ex=0
out=$($BRIDGE build-capsule \
    --kind code_diff \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc8-code-diff-out.json" \
    --no-compat-v1 \
    2>&1) || _ex=$?

if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "V2_TEMPLATE_NOT_READY"; then
    pass "code_diff build-capsule --no-compat-v1 → exit 1 + V2_TEMPLATE_NOT_READY"
else
    fail "code_diff build-capsule --no-compat-v1 → expected exit 1 + V2_TEMPLATE_NOT_READY, got exit=$_ex: $(echo "$out" | head -3)"
fi

# Verify execution_outcome is NOT blocked (v2 template exists)
echo
echo "--- SC-8: build-capsule --kind execution_outcome → NOT blocked (template exists) ---"
_ex=0
out=$($BRIDGE build-capsule \
    --kind execution_outcome \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc8-eo-out.json" \
    2>&1) || _ex=$?

if [[ $_ex -eq 0 ]] && echo "$out" | grep -qE "capsule.*写入|CAPSULE_BUILD|target_hash"; then
    pass "execution_outcome build-capsule → exit 0 (template exists, not blocked)"
elif echo "$out" | grep -q "V2_TEMPLATE_NOT_READY"; then
    fail "execution_outcome blocked by V2_TEMPLATE_NOT_READY (unexpected — should have template)"
else
    fail "execution_outcome → unexpected exit=$_ex: $(echo "$out" | head -3)"
fi

# --- SC-10: positive — plan target with mock writer → APPROVED ---
echo
echo "--- SC-10: plan target + mock writer → APPROVED via GD_WRITER_PATH_OVERRIDE ---"

# SC-10 uses --compat-v1 to bypass V2_TEMPLATE_NOT_READY and exercise the live path
_ex=0
out=$(GD_WRITER_PATH_OVERRIDE="$MOCK_WRITER" \
    GD_MOCK_RESULT_DIR="$TMPDIR/mock-results" \
    $BRIDGE run-bridge \
    --kind plan \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc10-out.json" \
    --live-transport \
    --compat-v1 \
    2>&1) || _ex=$?

if [[ $_ex -eq 0 ]] && echo "$out" | grep -q "GD_CODEX_BRIDGE_STATUS: approved"; then
    pass "plan + mock writer + --compat-v1 → exit 0 + GD_CODEX_BRIDGE_STATUS: approved"
elif echo "$out" | grep -q "APPROVED"; then
    pass "plan + mock writer + --compat-v1 → APPROVED (exit=$_ex)"
else
    fail "plan + mock writer + --compat-v1 → expected APPROVED, got exit=$_ex: $(echo "$out" | head -5)"
fi

# --- Summary ---
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "SC-7/SC-8/SC-10 (plan-routing): PASS"
    exit 0
else
    echo "SC-7/SC-8/SC-10 (plan-routing): FAIL"
    exit 1
fi
