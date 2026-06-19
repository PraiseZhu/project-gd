#!/usr/bin/env bash
# gd-step5-l2-cleanup-smoke.sh — step-5 L2 cleanup regression (SC-11)
#
# Covers two fail-open / false-degrade defects:
#   SC-11a (review2-output): empty MANDATORY_READ must FAIL the coverage gate
#                            (fail-closed), not "no-op pass".
#   SC-11b (audit-legacy-trust): a report whose raw_result_path is in JSON form
#                            (quoted value + trailing comma) pointing at a real
#                            file must classify as trusted_codex_raw, not be
#                            downgraded by a parse failure.
#
# Positive + negative assertions for each. Exit 0 = all pass.

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
AUDIT="python3 scripts/gd-audit-legacy-review-trust.py"

echo "=== step-5 L2 cleanup smoke (SC-11) ==="

# ---------------------------------------------------------------------------
# SC-11a: empty MANDATORY_READ → coverage gate FAIL (fail-closed)
# ---------------------------------------------------------------------------
echo
echo "--- SC-11a: empty MANDATORY_READ → COVERAGE_VALIDATE_FAIL ---"

cat > "$TMPDIR/capsule-empty.md" << 'EOF'
REVIEW_PROFILE: plan_review
REVIEW_GOAL: test empty mandatory read
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

cat > "$TMPDIR/output-empty.md" << 'EOF'
Some review findings here.
No MANDATORY_READ_COVERAGE section needed.
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-empty.md" --output "$TMPDIR/output-empty.md" 2>/dev/null) || _ex=$?
if [[ $_ex -ne 0 ]]; then
    pass "empty MANDATORY_READ → non-zero exit ($_ex), gate did not no-op pass"
else
    fail "empty MANDATORY_READ → expected non-zero exit, got 0 (fail-open!): $(echo "$out" | head -3)"
fi

if echo "$out" | grep -q "COVERAGE_VALIDATE_FAIL"; then
    pass "empty MANDATORY_READ → COVERAGE_VALIDATE_FAIL emitted"
else
    fail "empty MANDATORY_READ → expected COVERAGE_VALIDATE_FAIL, got: $(echo "$out" | head -5)"
fi

if echo "$out" | grep -qi "MANDATORY_READ list is empty"; then
    pass "FAIL message explains empty MANDATORY_READ cause"
else
    fail "FAIL message does not explain empty cause: $(echo "$out" | head -5)"
fi

# Negative control: a NON-empty capsule with full coverage still PASSES,
# proving the fix is scoped to the empty case and did not break the happy path.
echo
echo "--- SC-11a (neg control): non-empty + covered → COVERAGE_VALIDATE_PASS ---"

cat > "$TMPDIR/capsule-nonempty.md" << 'EOF'
REVIEW_PROFILE: plan_review
REVIEW_GOAL: test non-empty
REVIEW_TARGET:
  test-plan.md
REVIEW_TARGET_HASH: abc123
BRIDGE_TARGET_POLICY: original_plan_only
MANDATORY_READ:
  - path: scripts/alpha.py

OUTPUT_CONTRACT:
  MANDATORY_READ_COVERAGE:
EOF

cat > "$TMPDIR/output-covered.md" << 'EOF'
Findings.

MANDATORY_READ_COVERAGE:
  - scripts/alpha.py: read
EOF

_ex=0
out=$($VALIDATOR --capsule "$TMPDIR/capsule-nonempty.md" --output "$TMPDIR/output-covered.md" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 0 ]] && echo "$out" | grep -q "COVERAGE_VALIDATE_PASS"; then
    pass "non-empty + covered → exit 0 + PASS (happy path intact)"
else
    fail "non-empty + covered → expected exit 0 + PASS, got exit=$_ex: $(echo "$out" | head -3)"
fi

# ---------------------------------------------------------------------------
# SC-11b: JSON-form raw_result_path → trusted_codex_raw (not downgraded)
# ---------------------------------------------------------------------------
echo
echo "--- SC-11b: JSON-form raw_result_path → trusted_codex_raw ---"

SCAN_DIR="$TMPDIR/reports"
mkdir -p "$SCAN_DIR"

# A real raw result file the report points at.
RAW_FILE="$SCAN_DIR/result-20260616.md"
cat > "$RAW_FILE" << 'EOF'
GD_REVIEW_DECISION: APPROVED
codex raw result body
EOF

# JSON-format report: quoted value + trailing comma (the shape real reports use).
cat > "$SCAN_DIR/route_report_review.json" << EOF
{
  "reviewer": "codex",
  "codex_review_status": "completed",
  "codex_raw_result_path": "$RAW_FILE",
  "verdict": "APPROVED"
}
EOF

_ex=0
out=$($AUDIT --scan-dir "$SCAN_DIR" --json-out "$TMPDIR/audit.json" 2>/dev/null) || _ex=$?
if [[ $_ex -eq 0 ]]; then
    pass "audit completed (exit 0) on JSON-form report"
else
    fail "audit failed unexpectedly, exit=$_ex: $(echo "$out" | head -3)"
fi

tier=$(python3 -c "
import json
d = json.load(open('$TMPDIR/audit.json'))
for r in d['results']:
    if r['path'].endswith('route_report_review.json'):
        print(r['tier'])
        break
")
if [[ "$tier" == "trusted_codex_raw" ]]; then
    pass "JSON-form raw_result_path → classified trusted_codex_raw"
else
    fail "JSON-form raw_result_path → expected trusted_codex_raw, got '$tier'"
fi

raw_resolved=$(python3 -c "
import json
d = json.load(open('$TMPDIR/audit.json'))
for r in d['results']:
    if r['path'].endswith('route_report_review.json'):
        print(r.get('raw_file_path') or '')
        break
")
if [[ "$raw_resolved" == "$RAW_FILE" ]]; then
    pass "raw_file_path resolved cleanly (no trailing comma/quote corruption)"
else
    fail "raw_file_path mis-resolved: got '$raw_resolved' expected '$RAW_FILE'"
fi

# Negative control: JSON-form raw_result_path pointing at a NON-existent file
# must NOT be trusted (downgraded) — proves we still require the file to exist.
echo
echo "--- SC-11b (neg control): JSON raw path to missing file → not trusted ---"

cat > "$SCAN_DIR/route_report_missing.json" << EOF
{
  "reviewer": "codex",
  "codex_raw_result_path": "$SCAN_DIR/does-not-exist.md",
  "verdict": "APPROVED"
}
EOF

_ex=0
$AUDIT --scan-dir "$SCAN_DIR" --json-out "$TMPDIR/audit2.json" >/dev/null 2>&1 || _ex=$?
tier_missing=$(python3 -c "
import json
d = json.load(open('$TMPDIR/audit2.json'))
for r in d['results']:
    if r['path'].endswith('route_report_missing.json'):
        print(r['tier'])
        break
")
if [[ "$tier_missing" != "trusted_codex_raw" ]]; then
    pass "JSON raw path to missing file → NOT trusted (got '$tier_missing')"
else
    fail "JSON raw path to missing file → wrongly trusted_codex_raw"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "SC-11 (step-5 L2 cleanup): PASS"
    exit 0
else
    echo "SC-11 (step-5 L2 cleanup): FAIL"
    exit 1
fi
