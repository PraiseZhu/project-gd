#!/usr/bin/env bash
# gd-l1-review-writer-marker-contract-smoke.sh — L1 --review writer baseline-preservation contract.
#
# Exercises vendor/l3-transport/scripts/review-result-writer.sh against a FAKE
# codex-send-wait in an ISOLATED temporary HANDOFF_BIN + --out-dir. Covers SC-4:
# a previously APPROVED baseline (last_code_review_status=approved) must survive
# no-verdict / send-failed / malformed / degraded attempts without being clobbered.
#
# Isolation: HOME / CLAUDE_PLUGIN_DATA / HANDOFF_ROOT / HANDOFF_BIN all temporary;
# baselines land under TMP_ROOT via --out-dir. TEMP_HOME_ISOLATION asserted at end.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WRITER="$GD_ROOT/vendor/l3-transport/scripts/review-result-writer.sh"
FAKE_SEND_SRC="$SCRIPT_DIR/transport/fake-codex"

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

TMP_ROOT="$(mktemp -d)"
export HOME="$TMP_ROOT/home"
export CLAUDE_PLUGIN_DATA="$TMP_ROOT/plugin-data"
HANDOFF_ROOT="$CLAUDE_PLUGIN_DATA/gd-handoff"
HANDOFF_BIN_FULL="$HANDOFF_ROOT/bin"
EMPTY_BIN="$TMP_ROOT/empty-bin"
BASELINES="$TMP_ROOT/baselines"
mkdir -p "$HANDOFF_BIN_FULL" "$EMPTY_BIN" "$BASELINES"
cp "$FAKE_SEND_SRC" "$HANDOFF_BIN_FULL/codex-send-wait"
chmod +x "$HANDOFF_BIN_FULL/codex-send-wait"

cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

CAPSULE="$TMP_ROOT/review-capsule.txt"
cat >"$CAPSULE" <<'CAP'
REVIEW_KIND: code
REVIEW_DOMAIN: app_code
REVIEW_ROUND: initial
REVIEW_DELTA_SCOPE: full_matrix
REVIEW_FOCUS: trigger surface; state/baseline
REVIEW_FOCUS_SOURCE: domain_matrix
PLAN_ALIGNMENT_PRESENT: false
PLAN_REVIEW_ALIGNMENT: N/A
DOMAIN_OVERRIDE_REASON: N/A
PROJECT_ROOT: /tmp/fake-project
REPO_ROOT: N/A
BRANCH: N/A
IN_SCOPE: test
OUT_OF_SCOPE: none
USER_ACCEPTED_DECISIONS: none
SUCCESS_CRITERIA: pass
KNOWN_LIMITATIONS: none
BASELINE: test
BASELINE_CONFIDENCE: low
REVIEW_RULES: test
CAP

BASELINE_KEY="abc123def456"
BASELINE_FILE="$BASELINES/$BASELINE_KEY/latest-plan-baseline.json"

# run_writer <handoff_bin> <fake_send_mode> → captures stdout+stderr, sets WRITER_RC
run_writer() {
  local bin="$1" mode="$2"
  export HANDOFF_BIN="$bin"
  set +e
  FAKE_SEND_MODE="$mode" bash "$WRITER" \
    --capsule-file "$CAPSULE" \
    --baseline-key "$BASELINE_KEY" \
    --review-kind code \
    --cwd "$TMP_ROOT" \
    --out-dir "$BASELINES" \
    --no-stop-marker >"$TMP_ROOT/writer-out.txt" 2>&1
  WRITER_RC=$?
  set -e
}

code_status() { jq -r '.last_code_review_status // "MISSING"' "$BASELINE_FILE" 2>/dev/null || echo "MISSING"; }
code_verdict() { jq -r '.last_code_verdict // "MISSING"' "$BASELINE_FILE" 2>/dev/null || echo "MISSING"; }
review_focus() { jq -r '.last_review_focus | length' "$BASELINE_FILE" 2>/dev/null || echo "0"; }

echo "=== L1 Review Writer Marker Contract Smoke ==="

# ─── Setup: seed an APPROVED baseline ───
echo "--- setup: seed approved baseline ---"
run_writer "$HANDOFF_BIN_FULL" review_approved_full
if [[ $WRITER_RC -eq 0 && "$(code_status)" == "approved" && "$(code_verdict)" == "APPROVED" ]]; then
  pass "seed approved baseline (exit=0, status=approved)"
else
  fail "seed approved baseline (rc=$WRITER_RC status=$(code_status))"
fi
SEED_FOCUS_LEN="$(review_focus)"

# ─── SC-4a: no VERDICT → fail-closed, baseline preserved ───
echo "--- SC-4: no VERDICT fail-closed ---"
run_writer "$HANDOFF_BIN_FULL" review_no_verdict
if [[ $WRITER_RC -ne 0 && "$(code_status)" == "approved" && "$(code_verdict)" == "APPROVED" ]]; then
  pass "REVIEW_NO_VERDICT_FAIL_CLOSED"
else
  fail "REVIEW_NO_VERDICT_FAIL_CLOSED (rc=$WRITER_RC status=$(code_status))"
fi

# ─── SC-4b: send-wait exit 4 (failed) → baseline preserved ───
echo "--- SC-4: send failed, baseline preserved ---"
run_writer "$HANDOFF_BIN_FULL" send_exit_4
if [[ $WRITER_RC -ne 0 && "$(code_status)" == "approved" && "$(code_verdict)" == "APPROVED" ]]; then
  pass "REVIEW_FAILED_BASELINE_PRESERVED"
else
  fail "REVIEW_FAILED_BASELINE_PRESERVED (rc=$WRITER_RC status=$(code_status))"
fi

# ─── SC-4c: degraded (binary missing → 127) → baseline preserved ───
echo "--- SC-4: degraded, baseline preserved ---"
run_writer "$EMPTY_BIN" recommendation  # mode irrelevant; binary absent → 127
if [[ $WRITER_RC -ne 0 && "$(code_status)" == "approved" && "$(code_verdict)" == "APPROVED" ]]; then
  pass "REVIEW_DEGRADED_BASELINE_PRESERVED"
else
  fail "REVIEW_DEGRADED_BASELINE_PRESERVED (rc=$WRITER_RC status=$(code_status))"
fi

# ─── SC-3: watch unavailable exit 2 → [REVIEW] DEGRADED, baseline preserved ───
echo "--- SC-3: watch unavailable exit 2 → DEGRADED ---"
run_writer "$HANDOFF_BIN_FULL" watch_unavailable  # fake-codex exits 2
if [[ $WRITER_RC -ne 0 && "$(code_status)" == "approved" && "$(code_verdict)" == "APPROVED" ]] \
   && grep -q '\[REVIEW\] ⚠️ DEGRADED' "$TMP_ROOT/writer-out.txt"; then
  pass "REVIEW_WATCH_UNAVAILABLE_DEGRADED"
else
  fail "REVIEW_WATCH_UNAVAILABLE_DEGRADED (rc=$WRITER_RC status=$(code_status))"
fi

# ─── SC-4d: malformed (VERDICT but missing sections) → baseline preserved ───
echo "--- SC-4: malformed, approved baseline unchanged ---"
run_writer "$HANDOFF_BIN_FULL" review_malformed
if [[ $WRITER_RC -ne 0 && "$(code_status)" == "approved" && "$(code_verdict)" == "APPROVED" ]]; then
  pass "REVIEW_APPROVED_BASELINE_UNCHANGED_ON_MALFORMED"
else
  fail "REVIEW_APPROVED_BASELINE_UNCHANGED_ON_MALFORMED (rc=$WRITER_RC status=$(code_status))"
fi

# ─── last_review_focus also preserved (not clobbered by failed attempts) ───
NOW_FOCUS_LEN="$(review_focus)"
if [[ "$NOW_FOCUS_LEN" == "$SEED_FOCUS_LEN" ]]; then
  pass "REVIEW_FOCUS_PRESERVED"
else
  fail "REVIEW_FOCUS_PRESERVED (seed=$SEED_FOCUS_LEN now=$NOW_FOCUS_LEN)"
fi

# ─── TEMP_HOME_ISOLATION ───
leaked=0
while IFS= read -r -d '' f; do
  case "$f" in
    "$TMP_ROOT"/*) ;;
    *) leaked=1; echo "  LEAK: $f" ;;
  esac
done < <(find "$BASELINES" "$HANDOFF_ROOT" -type f -print0 2>/dev/null)
if [[ $leaked -eq 0 ]]; then
  pass "TEMP_HOME_ISOLATION"
else
  fail "TEMP_HOME_ISOLATION (leaked)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then exit 1; fi
exit 0
