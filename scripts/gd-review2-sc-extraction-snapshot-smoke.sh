#!/usr/bin/env bash
# gd-review2-sc-extraction-snapshot-smoke.sh — Phase 2 smoke test (SC-4)
# Verifies:
#   1. scripts/lib/sc_extraction.py extract_sc_ids works correctly
#   2. gd-validate-review-content-evidence.py after shared-import produces
#      byte-identical output vs. fixtures/review2-plan/expected/l3-validator-snapshot.txt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
PASS=0; FAIL=0

pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

echo "=== SC Extraction + L3 Snapshot Smoke ==="

# --- Test 1: extract_sc_ids basic unit ---
echo
echo "--- T1: extract_sc_ids unit ---"
result=$(python3 - <<'EOF'
import sys
sys.path.insert(0, "scripts")
from lib.sc_extraction import extract_sc_ids
ids = extract_sc_ids("SC-1 and SC-W2 and H2B-SC-14 and not-SC and SC-GS1")
# Sort for deterministic output
print(sorted(ids))
EOF
)
if echo "$result" | grep -q "SC-1" && echo "$result" | grep -q "SC-W2" && echo "$result" | grep -q "H2B-SC-14" && echo "$result" | grep -q "SC-GS1"; then
    pass "extract_sc_ids extracts SC-1, SC-W2, H2B-SC-14, SC-GS1"
else
    fail "extract_sc_ids returned unexpected: $result"
fi

# --- Test 2: case-sensitive — lowercase 'sc-1' must NOT be extracted ---
echo
echo "--- T2: lowercase sc-1 not extracted (case sensitive) ---"
result2=$(python3 - <<'EOF'
import sys
sys.path.insert(0, "scripts")
from lib.sc_extraction import extract_sc_ids
ids = extract_sc_ids("lowercase sc-1 ignored, but SC-1 is found")
print(sorted(ids))
EOF
)
if echo "$result2" | grep -q "SC-1" && ! echo "$result2" | grep -qE "^.*'sc-1'"; then
    pass "Lowercase sc-1 ignored; uppercase SC-1 extracted"
else
    fail "Unexpected extraction result: $result2"
fi

# --- Test 3: SC_ID_RE accessible from module ---
echo
echo "--- T3: SC_ID_RE importable ---"
if python3 -c "
import sys; sys.path.insert(0, 'scripts')
from lib.sc_extraction import SC_ID_RE, extract_sc_ids
assert SC_ID_RE.pattern, 'SC_ID_RE has no pattern'
print('OK')
" 2>/dev/null | grep -q "OK"; then
    pass "SC_ID_RE importable from lib.sc_extraction"
else
    fail "SC_ID_RE import failed"
fi

# --- Test 4: L3 validator byte-identical snapshot ---
echo
echo "--- T4: L3 validator byte-identical after shared import ---"
SNAPSHOT="$ROOT/fixtures/review2-plan/expected/l3-validator-snapshot.txt"
if [[ ! -f "$SNAPSHOT" ]]; then
    fail "Snapshot not found: $SNAPSHOT"
else
    {
        _ex=0
        echo "=== approved-plan ==="
        python3 scripts/gd-validate-review-content-evidence.py \
            --target fixtures/review-bridge/raw-approved-plan.md \
            --review fixtures/review-bridge/raw-approved-plan.md \
            2>/dev/null || _ex=$?; echo "EXIT:$_ex"; _ex=0
        echo "=== approved-code ==="
        python3 scripts/gd-validate-review-content-evidence.py \
            --target fixtures/review-bridge/raw-approved-code.md \
            --review fixtures/review-bridge/raw-approved-code.md \
            2>/dev/null || _ex=$?; echo "EXIT:$_ex"; _ex=0
        echo "=== requires-changes-missing-sc ==="
        python3 scripts/gd-validate-review-content-evidence.py \
            --target fixtures/review-bridge/raw-requires-changes-missing-sc.md \
            --review fixtures/review-bridge/raw-requires-changes-missing-sc.md \
            2>/dev/null || _ex=$?; echo "EXIT:$_ex"; _ex=0
        echo "=== requires-changes-plan ==="
        python3 scripts/gd-validate-review-content-evidence.py \
            --target fixtures/review-bridge/raw-requires-changes-plan.md \
            --review fixtures/review-bridge/raw-requires-changes-plan.md \
            2>/dev/null || _ex=$?; echo "EXIT:$_ex"; _ex=0
    } > /tmp/gd-l3-smoke-current.txt

    if diff -q "$SNAPSHOT" /tmp/gd-l3-smoke-current.txt >/dev/null 2>&1; then
        pass "L3 validator output byte-identical with snapshot"
    else
        fail "L3 validator output differs from snapshot:"
        diff "$SNAPSHOT" /tmp/gd-l3-smoke-current.txt || true
    fi
fi

# --- Test 5: is_review2_capsule_path ---
echo
echo "--- T5: is_review2_capsule_path ---"
result3=$(python3 - <<'EOF'
import sys
sys.path.insert(0, "scripts")
from lib.path_classification import is_review2_capsule_path
cases = [
    ("results/review-route-split/case/capsule.md", True),
    ("plans/gd/master-plan.md", False),
    ("fixtures/review2-plan/good-policy-capsule.md", False),
    ("/abs/path/to/capsule.md", True),
    ("capsule.md", True),
    ("not-capsule.md", False),
]
ok = True
for path, expected in cases:
    got = is_review2_capsule_path(path)
    if got != expected:
        print(f"FAIL: {path!r} → {got} (expected {expected})")
        ok = False
print("OK" if ok else "FAIL")
EOF
)
if echo "$result3" | tail -1 | grep -q "^OK$"; then
    pass "is_review2_capsule_path all cases correct"
else
    fail "is_review2_capsule_path failures: $result3"
fi

# --- Summary ---
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "SC-4: PASS"
    exit 0
else
    echo "SC-4: FAIL"
    exit 1
fi
