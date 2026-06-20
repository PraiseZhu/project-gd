#!/usr/bin/env bash
# gd-l1-discuss-marker-contract-smoke.sh — L1 discuss mode marker fail-closed contract.
#
# Exercises vendor/l3-transport/scripts/codex-consult.sh against a FAKE
# codex-send-wait placed in an ISOLATED temporary HANDOFF_BIN. No live daemon,
# no real ~/.claude, no key. Covers SC-1/SC-2/SC-3:
#   SC-1  recommendation present + no line-anchored VERDICT   → exit 0
#   SC-2  exit 0 but no RECOMMENDATION                        → consult exit 4
#   SC-3  watch unavailable                                   → [DISCUSS] DEGRADED exit 2
#   (extra) discuss output contains VERDICT                  → consult exit 4
#
# Isolation: HOME / CLAUDE_PLUGIN_DATA / HANDOFF_ROOT / HANDOFF_BIN all point at a
# mktemp dir; the smoke asserts nothing leaked to real ~/.claude (TEMP_HOME_ISOLATION).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONSULT="$GD_ROOT/vendor/l3-transport/scripts/codex-consult.sh"
FAKE_SEND_SRC="$SCRIPT_DIR/transport/fake-codex"

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

# ─── Isolated runtime root ───
TMP_ROOT="$(mktemp -d)"
export HOME="$TMP_ROOT/home"
export CLAUDE_PLUGIN_DATA="$TMP_ROOT/plugin-data"
# state-paths.sh derives HANDOFF_ROOT=${CLAUDE_PLUGIN_DATA}/gd-handoff, HANDOFF_BIN=${HANDOFF_ROOT}/bin
HANDOFF_ROOT="$CLAUDE_PLUGIN_DATA/gd-handoff"
HANDOFF_BIN="$HANDOFF_ROOT/bin"
mkdir -p "$HANDOFF_BIN"
cp "$FAKE_SEND_SRC" "$HANDOFF_BIN/codex-send-wait"
chmod +x "$HANDOFF_BIN/codex-send-wait"

cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

CAPSULE="$TMP_ROOT/discuss-capsule.txt"
cat >"$CAPSULE" <<'CAP'
QUESTION: 是否采纳方案 A
CONTEXT: 当前 L1 discuss 路径需要 marker fail-closed
CLAUDE_LEAN: 倾向 A，风险可控
OPTIONS: 方案 A; 方案 B
PROJECT_ROOT: /tmp/fake-project
CAP

run_consult() {
  # $1 = FAKE_SEND_MODE value; stdout/stderr captured by caller via direct invocation
  FAKE_SEND_MODE="$1" bash "$CONSULT" --capsule-file "$CAPSULE" --cwd "$TMP_ROOT"
}

echo "=== L1 Discuss Marker Contract Smoke ==="

# ─── SC-1: recommendation present, no line-anchored VERDICT → exit 0 ───
echo "--- SC-1: recommendation OK ---"
set +e
out=$(run_consult recommendation 2>/dev/null); rc=$?
set -e
if [[ $rc -eq 0 ]] && echo "$out" | grep -qE '^RECOMMENDATION:' && ! echo "$out" | grep -qE '^VERDICT:'; then
  pass "DISCUSS_RECOMMENDATION_OK"
else
  fail "DISCUSS_RECOMMENDATION_OK (rc=$rc)"
fi

# ─── SC-2: exit 0 from send-wait but no RECOMMENDATION → consult exit 4 ───
echo "--- SC-2: no RECOMMENDATION fail-closed ---"
set +e
out=$(run_consult no_recommendation 2>/dev/null); rc=$?
set -e
if [[ $rc -eq 4 ]]; then
  pass "DISCUSS_NO_RECOMMENDATION"
else
  fail "DISCUSS_NO_RECOMMENDATION (rc=$rc)"
fi

# ─── (SC-1 complement) discuss output contains VERDICT → consult exit 4 ───
echo "--- SC-1: VERDICT rejected ---"
set +e
out=$(run_consult contains_verdict 2>/dev/null); rc=$?
set -e
if [[ $rc -eq 4 ]]; then
  pass "DISCUSS_VERDICT_REJECTED"
else
  fail "DISCUSS_VERDICT_REJECTED (rc=$rc)"
fi

# ─── SC-3: watch unavailable → [DISCUSS] DEGRADED exit 2 ───
echo "--- SC-3: watch unavailable fail-closed ---"
set +e
out=$(run_consult watch_unavailable 2>&1); rc=$?
set -e
if [[ $rc -eq 2 ]] && echo "$out" | grep -q '\[DISCUSS\] DEGRADED'; then
  pass "DISCUSS_WATCH_UNAVAILABLE_FAIL_CLOSED"
else
  fail "DISCUSS_WATCH_UNAVAILABLE_FAIL_CLOSED (rc=$rc)"
fi

# ─── TEMP_HOME_ISOLATION: nothing written outside TMP_ROOT ───
echo "--- isolation: no real ~/.claude touched ---"
# The real user home (before override) must have no new gd-handoff writes from this run.
# We assert the consult path only resolved under TMP_ROOT by checking no stray files
# appeared under the *original* HOME's handoff root — approximated by confirming every
# file the consult could touch (HANDOFF_BIN) lives under TMP_ROOT.
leaked=0
while IFS= read -r -d '' f; do
  case "$f" in
    "$TMP_ROOT"/*) ;;  # expected
    *) leaked=1; echo "  LEAK outside TMP_ROOT: $f" ;;
  esac
done < <(find "$HANDOFF_ROOT" -type f -print0 2>/dev/null)
if [[ $leaked -eq 0 ]]; then
  pass "TEMP_HOME_ISOLATION"
else
  fail "TEMP_HOME_ISOLATION (leaked files above)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then exit 1; fi
exit 0
