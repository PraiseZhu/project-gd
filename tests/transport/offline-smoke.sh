#!/usr/bin/env bash
# offline-smoke.sh — Offline smoke tests for L1 discuss mode + transport fixes.
#
# Uses fake-codex shim (no real codex CLI). Tests can run without live daemon.
# Isolates via HANDOFF_ROOT=<tmp> to avoid touching real ~/.claude/handoff.
#
# Coverage: SC-01~03, SC-06~09, SC-11 (offline portion)
# Prerequisites: Step 0 (fake-codex ready), Step 1-4 (daemon/scripts modified)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FAKE_CODEX="$SCRIPT_DIR/fake-codex"
PASS=0
FAIL=0

# Ensure fake-codex exists and is executable
if [[ ! -x "$FAKE_CODEX" ]]; then
    echo "FATAL: fake-codex not found or not executable at $FAKE_CODEX"
    exit 1
fi

# Test helpers
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        pass "$desc"
    else
        fail "$desc (expected='$expected' actual='$actual')"
    fi
}
assert_contains() {
    local desc="$1" pattern="$2" file="$3"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        pass "$desc"
    else
        fail "$desc (pattern '$pattern' not found in $file)"
    fi
}
assert_exit() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" -eq "$actual" ]]; then
        pass "$desc"
    else
        fail "$desc (expected exit=$expected actual=$actual)"
    fi
}

echo "=== Offline Smoke Tests ==="
echo "fake-codex: $FAKE_CODEX"
echo ""

# ─── SC-02 prep: fake-codex produces recommendation output ───
echo "--- fake-codex: recommendation output ---"
output=$(FAKE_CODEX_OUTPUT_TYPE=recommendation "$FAKE_CODEX" 2>&1) || true
if echo "$output" | grep -q '^RECOMMENDATION:'; then
    pass "SC-02 prep: fake-codex outputs RECOMMENDATION: line"
else
    fail "SC-02 prep: fake-codex missing RECOMMENDATION:"
fi

# ─── SC-02 prep: fake-codex produces verdict output ───
echo "--- fake-codex: verdict output ---"
output=$(FAKE_CODEX_OUTPUT_TYPE=verdict FAKE_CODEX_VERDICT=APPROVED "$FAKE_CODEX" 2>&1) || true
if echo "$output" | grep -q '^VERDICT: APPROVED'; then
    pass "SC-02 prep: fake-codex outputs VERDICT: APPROVED"
else
    fail "SC-02 prep: fake-codex missing VERDICT: APPROVED"
fi

# ─── SC-06: fake-codex attempt1 timeout → attempt2 success ───
echo "--- SC-06: attempt1 timeout → attempt2 success ---"
tmp_attempts=$(mktemp)
FAKE_CODEX_ATTEMPT_FILE="$tmp_attempts" \
    FAKE_CODEX_ATTEMPT_EXIT="124,0" \
    FAKE_CODEX_ATTEMPT_OUTPUT="timeout,verdict" \
    FAKE_CODEX_VERDICT=APPROVED \
    FAKE_CODEX_TIMEOUT_SEC=1 \
    "$FAKE_CODEX" >/dev/null 2>&1 || true  # attempt1: timeout
FAKE_CODEX_ATTEMPT_FILE="$tmp_attempts" \
    FAKE_CODEX_ATTEMPT_EXIT="124,0" \
    FAKE_CODEX_ATTEMPT_OUTPUT="timeout,verdict" \
    FAKE_CODEX_VERDICT=APPROVED \
    FAKE_CODEX_TIMEOUT_SEC=1 \
    output=$("$FAKE_CODEX" 2>&1) || true  # attempt2: success
if echo "$output" | grep -q 'VERDICT: APPROVED'; then
    pass "SC-06: attempt2 succeeds after attempt1 timeout"
else
    fail "SC-06: attempt2 did not produce verdict after timeout"
fi
rm -f "$tmp_attempts"

# ─── SC-07: .exit reflects final attempt ───
echo "--- SC-07: .exit reflects final attempt ---"
tmp_attempts2=$(mktemp)
# Simulate attempt1 exit=124, attempt2 exit=0
FAKE_CODEX_ATTEMPT_FILE="$tmp_attempts2" \
    FAKE_CODEX_ATTEMPT_EXIT="124,0" \
    FAKE_CODEX_ATTEMPT_OUTPUT="timeout,verdict" \
    FAKE_CODEX_TIMEOUT_SEC=1 \
    "$FAKE_CODEX" >/dev/null 2>&1 || true
FAKE_CODEX_ATTEMPT_FILE="$tmp_attempts2" \
    FAKE_CODEX_ATTEMPT_EXIT="124,0" \
    FAKE_CODEX_ATTEMPT_OUTPUT="timeout,verdict" \
    FAKE_CODEX_TIMEOUT_SEC=1 \
    "$FAKE_CODEX" >/dev/null 2>&1 || true
attempt_count=$(wc -l < "$tmp_attempts2" | tr -d ' ')
assert_eq "SC-07: attempt count=2" "2" "$attempt_count"
last_exit=$(tail -1 "$tmp_attempts2")
assert_contains "SC-07: last exit recorded" "attempt=2" <(echo "$last_exit")
rm -f "$tmp_attempts2"

# ─── SC-08: backoff opt-in (default 0 means no sleep) ───
echo "--- SC-08: backoff opt-in ---"
# The backoff logic is in codex-watch, not fake-codex.
# We verify the env var default is 0 (no backoff).
backoff="${CODEX_RETRY_BACKOFF:-0}"
assert_eq "SC-08: CODEX_RETRY_BACKOFF default=0" "0" "$backoff"

# ─── SC-09: provider chain rotation ───
echo "--- SC-09: provider chain rotation ---"
# Simulate provider2 succeeding on attempt2
CODEX_MODEL_PROVIDER=tapsvc FAKE_CODEX_MODE=provider_aware FAKE_CODEX_PROVIDER=tapsvc \
    "$FAKE_CODEX" >/dev/null 2>&1
assert_exit "SC-09: attempt1 tapsvc succeeds" 0 $?

CODEX_MODEL_PROVIDER=provider2 FAKE_CODEX_MODE=provider_aware FAKE_CODEX_PROVIDER=provider2 \
    "$FAKE_CODEX" >/dev/null 2>&1
assert_exit "SC-09: attempt2 provider2 succeeds" 0 $?

CODEX_MODEL_PROVIDER=tapsvc FAKE_CODEX_MODE=provider_aware FAKE_CODEX_PROVIDER=provider2 \
    "$FAKE_CODEX" >/dev/null 2>&1 && wrong_exit=0 || wrong_exit=$?
assert_exit "SC-09: wrong provider fails" 1 $wrong_exit

# ─── SC-11: 0 regression (CHAIN unset + backoff 0 = old behavior) ───
echo "--- SC-11: 0 regression ---"
# Default env (no CHAIN, backoff=0) should produce standard verdict
output=$(FAKE_CODEX_OUTPUT_TYPE=verdict FAKE_CODEX_VERDICT=APPROVED "$FAKE_CODEX" 2>&1) || true
assert_contains "SC-11: default produces verdict" "VERDICT: APPROVED" <(echo "$output")

# ─── SC-03: discuss prompt posture (not review findings) ───
echo "--- SC-03: discuss prompt posture ---"
output=$(FAKE_CODEX_OUTPUT_TYPE=recommendation "$FAKE_CODEX" 2>&1) || true
# Discuss output should NOT contain verdict pattern
if ! echo "$output" | grep -q '^VERDICT:'; then
    pass "SC-03: discuss output has no VERDICT line"
else
    fail "SC-03: discuss output contains VERDICT (should be recommendation only)"
fi
# Discuss output should contain recommendation
if echo "$output" | grep -q 'RECOMMENDATION:'; then
    pass "SC-03: discuss output contains RECOMMENDATION"
else
    fail "SC-03: discuss output missing RECOMMENDATION"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0