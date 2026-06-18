#!/usr/bin/env bash
# Regression: codex-watch / healthcheck false-kill (WATCH_STUCK) flap.
#
# Root cause (2026-06-16): the healthcheck stuck detector measures
# (now - status-file mtime), but codex-watch set the status mtime once at
# try_claim and refreshed only the HEARTBEAT per attempt — not the status mtime.
# A legitimate retry chain (CODEX_EXEC_TIMEOUT x max_attempts, up to ~480s)
# accumulated past STUCK_TASK_MAX_AGE=300, so the healthcheck false-killed jobs
# that were still progressing (one even completed on attempt 2 after being reset
# to failed at 300s).
#
# Fix: codex-watch re-writes "running" (set_status) per attempt, resetting the
# stuck-clock to per-attempt. Invariant: STUCK_TASK_MAX_AGE > CODEX_EXEC_TIMEOUT
# so a single attempt never trips the stuck detector.
#
# This test (1) reproduces the false-kill condition, (2) proves a per-attempt
# refresh prevents it, (3) asserts the invariant against the REAL config values,
# and (4) confirms the fix is present in codex-watch's attempt loop.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CW="$REPO_ROOT/vendor/l3-transport/handoff/bin/codex-watch"
HC="$REPO_ROOT/vendor/l3-transport/handoff/bin/codex-watch-healthcheck"

PASS=0
FAIL=0
pass() { echo "  ok: $*"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL + 1)); }

# Portable "set file mtime to N seconds ago".
backdate() {  # <file> <seconds_ago>
  local f="$1" secs="$2" ts
  if ts=$(date -v-"${secs}"S +%Y%m%d%H%M.%S 2>/dev/null); then
    touch -t "$ts" "$f"
  else
    touch -d "${secs} seconds ago" "$f"  # GNU coreutils fallback
  fi
}

mtime_of() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1"; }

# Mirror of codex-watch-healthcheck:96-104 stuck detection.
is_stuck() {  # <status_file> <max_age>
  local sf="$1" max="$2" now age
  now=$(date +%s)
  age=$(( now - $(mtime_of "$sf") ))
  [[ "$(cat "$sf")" == "running" && $age -gt $max ]]
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
STATUS="$TMP/job.status"

# Read REAL config values from source (not hardcoded copies).
STUCK_MAX=$(grep -E '^STUCK_TASK_MAX_AGE=' "$HC" | head -1 | cut -d= -f2 | tr -dc '0-9')
CODEX_TO=$(grep -E 'CODEX_EXEC_TIMEOUT="\$\{CODEX_EXEC_TIMEOUT:-' "$CW" | head -1 | grep -oE ':-[0-9]+' | tr -dc '0-9')
[[ -n "$STUCK_MAX" ]] || { echo "cannot read STUCK_TASK_MAX_AGE from $HC"; exit 2; }
[[ -n "$CODEX_TO" ]] || { echo "cannot read CODEX_EXEC_TIMEOUT from $CW"; exit 2; }
echo "config: STUCK_TASK_MAX_AGE=$STUCK_MAX  CODEX_EXEC_TIMEOUT=$CODEX_TO"

# --- Case 1: reproduce the false-kill condition (stale status mtime) ---
echo "running" > "$STATUS"
backdate "$STATUS" $((STUCK_MAX + 27))   # e.g. 327s — observed in the incident
if is_stuck "$STATUS" "$STUCK_MAX"; then
  pass "Case 1: stale status mtime (>${STUCK_MAX}s) reproduces stuck/false-kill condition"
else
  fail "Case 1: could not reproduce stuck condition"
fi

# --- Case 2: per-attempt refresh (the fix) prevents the false-kill ---
echo "running" > "$STATUS"   # simulates codex-watch set_status "$base" "running" at attempt start
if is_stuck "$STATUS" "$STUCK_MAX"; then
  fail "Case 2: status still stuck after per-attempt refresh"
else
  pass "Case 2: per-attempt status refresh resets stuck-clock (no false-kill)"
fi

# --- Case 3: invariant — single attempt cannot trip the stuck detector ---
if [[ "$STUCK_MAX" -gt "$CODEX_TO" ]]; then
  pass "Case 3: invariant STUCK_TASK_MAX_AGE($STUCK_MAX) > CODEX_EXEC_TIMEOUT($CODEX_TO)"
else
  fail "Case 3: invariant broken — a single attempt could exceed the stuck threshold"
fi

# --- Case 4: fix is present in codex-watch's attempt loop ---
# The set_status "running" refresh must appear AFTER the per-attempt heartbeat
# refresh and inside the while-attempt loop.
if awk '/while \[\[ \$attempt -lt \$max_attempts \]\]/{inloop=1}
        inloop && /date \+%s > "\$HANDOFF_HEARTBEAT"/{hb=1}
        inloop && hb && /set_status "\$base" "running"/{found=1}
        /run_codex_with_timeout/{if(inloop) exit}
        END{exit !found}' "$CW"; then
  pass "Case 4: codex-watch refreshes status mtime (set_status running) per attempt"
else
  fail "Case 4: per-attempt status refresh missing from codex-watch attempt loop"
fi

# --- Case 5: full timeout-layer ordering (daemon budget < send-wait < controller) ---
# Root cause #2 (found during fix verification): the controller's bridge_timeout
# wraps run-bridge, which polls codex-send-wait. With default single-provider
# chain, max_attempts=2 so daemon budget = 2 x CODEX_EXEC_TIMEOUT. The order must
# hold so no upper layer kills a lower layer mid-legitimate-retry:
#   2 x CODEX_EXEC_TIMEOUT  <=  codex-send-wait TIMEOUT  <=  controller bridge_timeout
SW="$REPO_ROOT/vendor/l3-transport/handoff/bin/codex-send-wait"
CTRL="$REPO_ROOT/scripts/gd-review-controller.py"
SEND_WAIT_TO=$(grep -E 'TIMEOUT="\$\{CODEX_SEND_WAIT_TIMEOUT:-' "$SW" | head -1 | grep -oE ':-[0-9]+' | tr -dc '0-9')
CTRL_TO=$(grep -E '^\s*bridge_timeout = [0-9]+' "$CTRL" | head -1 | grep -oE '[0-9]+')
echo "config: codex-send-wait TIMEOUT=$SEND_WAIT_TO  controller bridge_timeout=$CTRL_TO  (max_attempts default=2)"
daemon_budget=$(( CODEX_TO * 2 ))
if [[ -n "$SEND_WAIT_TO" && -n "$CTRL_TO" ]] \
   && [[ "$SEND_WAIT_TO" -ge "$daemon_budget" ]] \
   && [[ "$CTRL_TO" -ge "$SEND_WAIT_TO" ]]; then
  pass "Case 5: timeout-layer order holds — daemon_budget($daemon_budget) <= send-wait($SEND_WAIT_TO) <= controller($CTRL_TO)"
else
  fail "Case 5: timeout-layer order broken — daemon_budget=$daemon_budget send-wait=$SEND_WAIT_TO controller=$CTRL_TO (upper layer may kill legitimate retry)"
fi

echo ""
echo "=== summary: PASS=$PASS FAIL=$FAIL ==="
if [[ $FAIL -eq 0 ]]; then
  echo "GD_TRANSPORT_HEALTHCHECK_FLAP_SMOKE: PASS"
  exit 0
else
  echo "GD_TRANSPORT_HEALTHCHECK_FLAP_SMOKE: FAIL"
  exit 1
fi
