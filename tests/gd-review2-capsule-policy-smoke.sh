#!/usr/bin/env bash
# gd-review2-capsule-policy-smoke.sh — Phase 4 smoke test (SC-2, SC-3)
# Verifies:
#   SC-2: plan_review capsule builder adds BRIDGE_TARGET_POLICY: original_plan_only
#   SC-3: capsule validator accepts good-policy-capsule, rejects bad-policy-capsule

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

PASS=0; FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

echo "=== Capsule Policy Smoke ==="

# --- SC-2: plan_review profile present in PROFILES ---
echo
echo "--- SC-2: plan_review profile registered ---"
if python3 -c "
import sys; sys.path.insert(0, '.')
_ns = {'__name__': 'inspect_mode'}
exec(open('scripts/gd-build-review2-capsule.py').read(), _ns)
assert 'plan_review' in _ns['PROFILES'], f'plan_review not in PROFILES: {_ns[\"PROFILES\"]}'
print('OK')
" 2>/dev/null | grep -q "^OK$"; then
    pass "plan_review in PROFILES"
else
    fail "plan_review NOT in PROFILES"
fi

# --- SC-2: capsule builder produces BRIDGE_TARGET_POLICY ---
echo
echo "--- SC-2: built capsule contains required policy fields ---"
_ex=0
python3 scripts/gd-build-review2-capsule.py \
    --profile plan_review \
    --target fixtures/review2-plan/good-plan.md \
    --cwd . \
    --out-dir "$TMPDIR" \
    2>/dev/null || _ex=$?

if [[ $_ex -eq 0 ]]; then
    if grep -q "^REVIEW_PROFILE: plan_review" "$TMPDIR/capsule.md"; then
        pass "built capsule has REVIEW_PROFILE: plan_review"
    else
        fail "built capsule missing REVIEW_PROFILE: plan_review"
    fi
    if grep -q "^BRIDGE_TARGET_POLICY: original_plan_only" "$TMPDIR/capsule.md"; then
        pass "built capsule has BRIDGE_TARGET_POLICY: original_plan_only"
    else
        fail "built capsule missing BRIDGE_TARGET_POLICY: original_plan_only"
    fi
    if grep -q "^REVIEW_TARGET_HASH:" "$TMPDIR/capsule.md"; then
        pass "built capsule has REVIEW_TARGET_HASH:"
    else
        fail "built capsule missing REVIEW_TARGET_HASH:"
    fi
else
    fail "capsule builder exited $?_ex — build failed"
fi

# --- SC-3: validator accepts good capsule ---
echo
echo "--- SC-3: validator accepts good-policy-capsule ---"
out=$(python3 scripts/gd-validate-review2-capsule.py \
    --capsule fixtures/review2-plan/good-policy-capsule.md 2>/dev/null)
if echo "$out" | grep -q "CAPSULE_VALIDATE_PASS"; then
    pass "good-policy-capsule.md → CAPSULE_VALIDATE_PASS"
else
    fail "good-policy-capsule.md → unexpected: $(echo "$out" | head -2)"
fi

# --- SC-3: validator rejects bad capsule (wrong policy value) ---
echo
echo "--- SC-3: validator rejects bad-policy-capsule ---"
_ex=0
out=$(python3 scripts/gd-validate-review2-capsule.py \
    --capsule fixtures/review2-plan/bad-policy-capsule.md 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "BRIDGE_TARGET_POLICY_INVALID"; then
    pass "bad-policy-capsule.md → FAIL with BRIDGE_TARGET_POLICY_INVALID ✓"
else
    fail "bad-policy-capsule.md → expected BRIDGE_TARGET_POLICY_INVALID, got exit=$_ex: $out"
fi

# --- SC-3: validator flags missing BRIDGE_TARGET_POLICY ---
echo
echo "--- SC-3: validator flags capsule missing BRIDGE_TARGET_POLICY ---"
cat > "$TMPDIR/no-policy-capsule.md" << 'EOF'
REVIEW_PROFILE: plan_review
REVIEW_GOAL: test
REVIEW_TARGET:
  test-plan.md
REVIEW_TARGET_HASH: abc123
OUTPUT_CONTRACT:
  some content
EOF
_ex=0
out=$(python3 scripts/gd-validate-review2-capsule.py \
    --capsule "$TMPDIR/no-policy-capsule.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "BRIDGE_TARGET_POLICY_MISSING"; then
    pass "capsule missing BRIDGE_TARGET_POLICY → FAIL with BRIDGE_TARGET_POLICY_MISSING ✓"
else
    fail "expected BRIDGE_TARGET_POLICY_MISSING, got exit=$_ex: $out"
fi

# --- P2-B fix: plan_review --target required ---
echo
echo "--- P2-B: plan_review missing target → PLAN_REVIEW_TARGET_REQUIRED ---"
_ex=0
out_miss=$(python3 scripts/gd-build-review2-capsule.py \
    --profile plan_review \
    --out-dir "$TMPDIR/missing-target" \
    2>&1) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out_miss" | grep -q "PLAN_REVIEW_TARGET_REQUIRED"; then
    pass "plan_review without --target → exit 1 + PLAN_REVIEW_TARGET_REQUIRED ✓"
else
    fail "plan_review without --target → expected PLAN_REVIEW_TARGET_REQUIRED exit 1, got exit=$_ex: $out_miss"
fi

echo
echo "--- P2-B: plan_review non-existent target → PLAN_REVIEW_TARGET_NOT_FOUND ---"
_ex=0
out_nf=$(python3 scripts/gd-build-review2-capsule.py \
    --profile plan_review \
    --target /no/such/plan.md \
    --out-dir "$TMPDIR/notfound-target" \
    2>&1) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out_nf" | grep -q "PLAN_REVIEW_TARGET_NOT_FOUND"; then
    pass "plan_review with non-existent target → exit 1 + PLAN_REVIEW_TARGET_NOT_FOUND ✓"
else
    fail "plan_review with non-existent target → expected PLAN_REVIEW_TARGET_NOT_FOUND exit 1, got exit=$_ex: $out_nf"
fi

# --- SC-2: other profiles not affected ---
echo
echo "--- SC-2: code_diff profile unaffected ---"
_ex=0
python3 scripts/gd-build-review2-capsule.py \
    --profile code_diff \
    --target fixtures/review2-plan/good-plan.md \
    --cwd . \
    --out-dir "$TMPDIR/code-diff-out" \
    2>/dev/null || _ex=$?
if [[ $_ex -eq 0 ]]; then
    if grep -q "^REVIEW_PROFILE: code_diff" "$TMPDIR/code-diff-out/capsule.md" \
       && ! grep -q "BRIDGE_TARGET_POLICY:" "$TMPDIR/code-diff-out/capsule.md"; then
        pass "code_diff capsule has no BRIDGE_TARGET_POLICY (correct)"
    else
        fail "code_diff capsule unexpectedly has BRIDGE_TARGET_POLICY"
    fi
else
    fail "code_diff capsule builder failed exit=$_ex"
fi

# --- Summary ---
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "SC-2/SC-3 (capsule-policy): PASS"
    exit 0
else
    echo "SC-2/SC-3 (capsule-policy): FAIL"
    exit 1
fi
