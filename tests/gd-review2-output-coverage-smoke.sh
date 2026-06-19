#!/usr/bin/env bash
# gd-review2-output-coverage-smoke.sh — Phase 4 smoke test (SC-6)
# Verifies gd-validate-review2-output.py coverage validator behaviour:
#   SC-6a: empty mandatory list → exit 1 (fail-closed), COVERAGE_VALIDATE_FAIL, MANDATORY_READ_COUNT: 0
#   SC-6b: all paths covered → COVERAGE_VALIDATE_PASS
#   SC-6c: missing path → COVERAGE_VALIDATE_FAIL with missing entry
#   SC-6d: invalid status → COVERAGE_VALIDATE_FAIL
#   SC-6e: duplicate path → COVERAGE_VALIDATE_FAIL
#   SC-6f: out_of_scope without reason → COVERAGE_VALIDATE_FAIL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

PASS=0; FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

VALIDATOR="python3 scripts/gd-validate-review2-output.py"

echo "=== Output Coverage Smoke ==="

# --- Build shared test capsules ---

# Capsule A: empty MANDATORY_READ (plan_review profile)
cat > "$TMPDIR/capsule-empty.md" << 'EOF'
REVIEW_PROFILE: plan_review
REVIEW_GOAL: test
REVIEW_TARGET:
  test-plan.md
REVIEW_TARGET_HASH: abc123
BRIDGE_TARGET_POLICY: original_plan_only
MANDATORY_READ:

OUTPUT_CONTRACT:
  MANDATORY_READ_COVERAGE:
  L3_GD_REVIEW_SEMANTICS: unchanged
  RELEASE_VERDICT: NOT_APPLICABLE
EOF

# Capsule B: two required mandatory reads
cat > "$TMPDIR/capsule-two-reads.md" << 'EOF'
REVIEW_PROFILE: plan_review
REVIEW_GOAL: test
REVIEW_TARGET:
  test-plan.md
REVIEW_TARGET_HASH: abc123
BRIDGE_TARGET_POLICY: original_plan_only
MANDATORY_READ:
  - path: scripts/alpha.py
  - path: scripts/beta.py

OUTPUT_CONTRACT:
  MANDATORY_READ_COVERAGE:
  L3_GD_REVIEW_SEMANTICS: unchanged
  RELEASE_VERDICT: NOT_APPLICABLE
EOF

# Capsule C: release_closure with mandatory reads
cat > "$TMPDIR/capsule-release.md" << 'EOF'
REVIEW_PROFILE: release_closure
REVIEW_GOAL: release check
MANDATORY_READ:
  - path: scripts/alpha.py
REVIEW_TARGET:
  test-plan.md
OUTPUT_CONTRACT:
  MANDATORY_READ_COVERAGE:
  L3_GD_REVIEW_SEMANTICS: unchanged
  RELEASE_VERDICT: NOT_APPLICABLE
EOF

# --- SC-6a: empty mandatory list → exit 1 (fail-closed, aligned with SC-11a) ---
echo
echo "--- SC-6a: empty mandatory list → COVERAGE_VALIDATE_FAIL (fail-closed) ---"

cat > "$TMPDIR/output-empty.md" << 'EOF'
Some review findings here.
No MANDATORY_READ_COVERAGE section needed.
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-empty.md" --output "$TMPDIR/output-empty.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_FAIL"; then
    pass "empty mandatory list → exit 1 + COVERAGE_VALIDATE_FAIL (fail-closed)"
else
    fail "empty mandatory list → expected exit 1 + FAIL, got exit=$_ex: $(echo "$out" | head -3)"
fi

if echo "$out" | grep -q "MANDATORY_READ_COUNT: 0"; then
    pass "MANDATORY_READ_COUNT: 0 present"
else
    fail "MANDATORY_READ_COUNT: 0 missing in: $(echo "$out" | head -5)"
fi

# --- SC-6b: all paths covered → PASS ---
echo
echo "--- SC-6b: all paths covered → COVERAGE_VALIDATE_PASS ---"

cat > "$TMPDIR/output-good.md" << 'EOF'
Some findings.

MANDATORY_READ_COVERAGE:
  - scripts/alpha.py: read
  - scripts/beta.py: read
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-two-reads.md" --output "$TMPDIR/output-good.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 0 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_PASS"; then
    pass "all covered → exit 0 + COVERAGE_VALIDATE_PASS"
else
    fail "all covered → expected PASS, got exit=$_ex: $(echo "$out" | head -3)"
fi

# --- SC-6c: missing path → COVERAGE_VALIDATE_FAIL ---
echo
echo "--- SC-6c: missing path → COVERAGE_VALIDATE_FAIL ---"

cat > "$TMPDIR/output-missing.md" << 'EOF'
Some findings.

MANDATORY_READ_COVERAGE:
  - scripts/alpha.py: read
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-two-reads.md" --output "$TMPDIR/output-missing.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_FAIL"; then
    pass "missing path → exit 1 + COVERAGE_VALIDATE_FAIL"
else
    fail "missing path → expected exit 1 + FAIL, got exit=$_ex: $(echo "$out" | head -3)"
fi

if echo "$out" | grep -q "scripts/beta.py.*MISSING\|mandatory_read not covered.*beta"; then
    pass "FAIL message names missing path (beta.py)"
else
    fail "FAIL message does not identify missing path: $(echo "$out" | head -5)"
fi

# --- SC-6d: invalid status → COVERAGE_VALIDATE_FAIL ---
echo
echo "--- SC-6d: invalid status → COVERAGE_VALIDATE_FAIL ---"

cat > "$TMPDIR/output-badstatus.md" << 'EOF'
Some findings.

MANDATORY_READ_COVERAGE:
  - scripts/alpha.py: skipped
  - scripts/beta.py: read
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-two-reads.md" --output "$TMPDIR/output-badstatus.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_FAIL"; then
    pass "invalid status → exit 1 + COVERAGE_VALIDATE_FAIL"
else
    fail "invalid status → expected exit 1 + FAIL, got exit=$_ex: $(echo "$out" | head -3)"
fi

if echo "$out" | grep -q "invalid status.*skipped"; then
    pass "FAIL message names invalid status 'skipped'"
else
    fail "FAIL message does not identify invalid status: $(echo "$out" | head -5)"
fi

# --- SC-6e: duplicate path → COVERAGE_VALIDATE_FAIL ---
echo
echo "--- SC-6e: duplicate path → COVERAGE_VALIDATE_FAIL ---"

cat > "$TMPDIR/output-dup.md" << 'EOF'
Some findings.

MANDATORY_READ_COVERAGE:
  - scripts/alpha.py: read
  - scripts/alpha.py: summarized_by_preflight
  - scripts/beta.py: read
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-two-reads.md" --output "$TMPDIR/output-dup.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_FAIL"; then
    pass "duplicate path → exit 1 + COVERAGE_VALIDATE_FAIL"
else
    fail "duplicate path → expected exit 1 + FAIL, got exit=$_ex: $(echo "$out" | head -3)"
fi

if echo "$out" | grep -q "more than once\|duplicate\|exactly once"; then
    pass "FAIL message mentions duplicate"
else
    fail "FAIL message does not mention duplicate: $(echo "$out" | head -5)"
fi

# --- SC-6f: out_of_scope without reason → COVERAGE_VALIDATE_FAIL ---
echo
echo "--- SC-6f: out_of_scope without OUT_OF_SCOPE_REASON → COVERAGE_VALIDATE_FAIL ---"

cat > "$TMPDIR/output-noscopereason.md" << 'EOF'
Some findings.

MANDATORY_READ_COVERAGE:
  - scripts/alpha.py: out_of_scope
  - scripts/beta.py: read
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-two-reads.md" --output "$TMPDIR/output-noscopereason.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_FAIL"; then
    pass "out_of_scope without reason → exit 1 + COVERAGE_VALIDATE_FAIL"
else
    fail "out_of_scope without reason → expected exit 1 + FAIL, got exit=$_ex: $(echo "$out" | head -3)"
fi

if echo "$out" | grep -q "OUT_OF_SCOPE_REASON"; then
    pass "FAIL message requires OUT_OF_SCOPE_REASON"
else
    fail "FAIL message does not mention OUT_OF_SCOPE_REASON: $(echo "$out" | head -5)"
fi

# --- SC-6g: out_of_scope WITH reason → PASS ---
echo
echo "--- SC-6g: out_of_scope with OUT_OF_SCOPE_REASON → COVERAGE_VALIDATE_PASS ---"

cat > "$TMPDIR/output-withscopereason.md" << 'EOF'
Some findings.

OUT_OF_SCOPE_REASON: scripts/alpha.py: file unchanged since last review
MANDATORY_READ_COVERAGE:
  - scripts/alpha.py: out_of_scope
  - scripts/beta.py: read
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-two-reads.md" --output "$TMPDIR/output-withscopereason.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 0 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_PASS"; then
    pass "out_of_scope with reason → exit 0 + COVERAGE_VALIDATE_PASS"
else
    fail "out_of_scope with reason → expected exit 0 + PASS, got exit=$_ex: $(echo "$out" | head -3)"
fi

# --- Summary ---
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "SC-6 (output-coverage): PASS"
    exit 0
else
    echo "SC-6 (output-coverage): FAIL"
    exit 1
fi
