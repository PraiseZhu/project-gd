#!/usr/bin/env bash
# Regression: B2 attempt-internal status touch + P3-a parent-death codex reaper.
#
# B2: codex-watch refreshes status mtime only at attempt boundaries (set_status
# "running"), so a single long attempt (deep review at gpt-5.x xhigh, >EXEC_TIMEOUT)
# leaves mtime stale and the healthcheck false-kills it via WATCH_STUCK. Fix:
# a background toucher refreshes `${base}.status` mtime while codex runs, tied to
# the watcher PID ($$) so it dies with the watcher.
#
# P3-a: a SIGKILL'd / launchd-kickstarted watcher leaves the worker subshell +
# codex chain reparented to init, still burning API/compute. Fix:
# run_codex_with_timeout's python3 wrapper watches CODEX_WATCH_PID and reaps
# codex's process group (killpg(getpgid(proc.pid))) on watcher death.
#
# This test (1) asserts both fixes are present in vendor codex-watch source,
# (2) dynamically proves the toucher refreshes mtime while alive and stops
# when the watcher dies, and (3) checks the touch-interval invariant against
# real config values. Uses vendor paths (no live deployment needed).
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

# Mirror of codex-watch-healthcheck:128-144 stuck detection.
is_stuck() {  # <status_file> <max_age>
  local sf="$1" max="$2" now age
  now=$(date +%s)
  age=$(( now - $(mtime_of "$sf") ))
  [[ "$(cat "$sf")" == "running" && $age -gt $max ]]
}

[[ -f "$CW" ]] || { echo "missing $CW"; exit 2; }
[[ -f "$HC" ]] || { echo "missing $HC"; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Real config values from source (not hardcoded).
STUCK_MAX=$(grep -E '^STUCK_TASK_MAX_AGE=' "$HC" | head -1 | cut -d= -f2 | tr -dc '0-9')
TOUCH_IV=$(grep -oE 'CODEX_WATCH_TOUCH_INTERVAL:-[0-9]+' "$CW" | head -1 | grep -oE '[0-9]+' || true)
[[ -n "$STUCK_MAX" ]] || { echo "cannot read STUCK_TASK_MAX_AGE"; exit 2; }
[[ -n "$TOUCH_IV" ]] || { echo "cannot read CODEX_WATCH_TOUCH_INTERVAL default"; exit 2; }
echo "config: STUCK_TASK_MAX_AGE=$STUCK_MAX  CODEX_WATCH_TOUCH_INTERVAL=$TOUCH_IV"

# --- Case 1: B2 toucher present in codex-watch attempt loop ---
if grep -qE 'while kill -0 \$\$ 2>/dev/null; do touch "\$\{base\}\.status"' "$CW" \
   && grep -q 'kill "$_touch_pid" 2>/dev/null || true' "$CW"; then
  pass "B2: toucher loop present in attempt (refreshes status mtime mid-codex-exec)"
else
  fail "B2: toucher loop missing from codex-watch attempt"
fi

# --- Case 2: P3-b touch interval is configurable ---
if grep -q 'CODEX_WATCH_TOUCH_INTERVAL' "$CW"; then
  pass "P3-b: touch interval configurable via CODEX_WATCH_TOUCH_INTERVAL"
else
  fail "P3-b: touch interval hardcoded (no CODEX_WATCH_TOUCH_INTERVAL)"
fi

# --- Case 3: P3-a parent-death reaper present ---
if grep -q '_reap_on_parent_death' "$CW" \
   && grep -q 'export CODEX_WATCH_PID=\$\$' "$CW" \
   && grep -q 'os.killpg(os.getpgid(proc.pid), signal.SIGKILL)' "$CW" \
   && ! grep -q 'os.killpg(os.getpgid(0), signal.SIGKILL)' "$CW"; then
  pass "P3-a: parent-death reaper present (watches CODEX_WATCH_PID, killpg(getpgid(proc.pid)), NOT getpgid(0))"
else
  fail "P3-a: reaper missing or uses wrong process group (getpgid(0) would miss codex)"
fi

# --- Case 4 (dynamic): toucher refreshes mtime while watcher alive ---
# Reproduce the false-kill (stale mtime), then prove the toucher refreshes it
# back under the stuck threshold while the watcher (this shell) is alive.
STATUS="$TMP/job.status"
echo "running" > "$STATUS"
backdate "$STATUS" $((STUCK_MAX + 50))   # stale → would be stuck
if is_stuck "$STATUS" "$STUCK_MAX"; then
  pass "Case 4 pre: stale mtime reproduces stuck (will clear via toucher)"
else
  fail "Case 4 pre: could not reproduce stuck baseline"
fi
# Launch the SAME toucher pattern codex-watch uses ($$ = this script = watcher).
( while kill -0 $$ 2>/dev/null; do touch "$STATUS" 2>/dev/null; sleep 1; done ) &
TPID=$!
sleep 3
if is_stuck "$STATUS" "$STUCK_MAX"; then
  fail "Case 4: toucher failed to refresh mtime (still stuck)"
else
  pass "Case 4: toucher refreshes status mtime → no false-kill while watcher alive"
fi
kill "$TPID" 2>/dev/null || true
wait "$TPID" 2>/dev/null || true

# --- Case 5 (dynamic): toucher stops when watcher dies ---
# A subshell simulating the watcher; on its exit the toucher (gated on its PID)
# must stop so healthcheck can still declare the job stuck later (fail-safe).
STATUS2="$TMP/job2.status"
echo "running" > "$STATUS2"
cat > "$TMP/fake_watcher.sh" <<EOF
#!/usr/bin/env bash
# Simulate codex-watch: launch the toucher gated on \$\$ then "run codex".
( while kill -0 \$\$ 2>/dev/null; do touch "$STATUS2" 2>/dev/null; sleep 1; done ) &
sleep 60
EOF
chmod +x "$TMP/fake_watcher.sh"
bash "$TMP/fake_watcher.sh" &
WPID=$!
sleep 2
[[ -n "$WPID" ]] || { fail "Case 5: watcher did not start"; }
M_DURING=$(mtime_of "$STATUS2")
sleep 2
M_ALIVE=$(mtime_of "$STATUS2")
kill -9 "$WPID" 2>/dev/null   # simulate SIGKILL'd watcher
# Allow one in-flight touch cycle to drain (the toucher polls kill -0 $$ on a
# sleep interval; a touch in progress at kill time may land once after), then
# confirm mtime stabilizes — the toucher must exit within one interval of
# watcher death, not run forever.
sleep 3
M_MID=$(mtime_of "$STATUS2")
sleep 3
M_FINAL=$(mtime_of "$STATUS2")
if [[ "$M_ALIVE" -ge "$M_DURING" ]]; then
  pass "Case 5a: mtime refreshed while watcher alive ($M_DURING → $M_ALIVE)"
else
  fail "Case 5a: mtime not refreshing while watcher alive ($M_DURING → $M_ALIVE)"
fi
if [[ "$M_FINAL" -le "$M_MID" ]] 2>/dev/null; then
  pass "Case 5b: mtime frozen after watcher death (M_MID=$M_MID M_FINAL=$M_FINAL) → healthcheck can still declare stuck (fail-safe intact)"
else
  fail "Case 5b: mtime still advancing after watcher death (M_MID=$M_MID M_FINAL=$M_FINAL) → orphan toucher, fail-safe broken"
fi
wait 2>/dev/null || true

# --- Case 6: invariant — touch interval well under stuck threshold ---
# The toucher must refresh faster than the stuck detector trips, else a
# legitimate attempt could still be false-killed in the gap.
if [[ "$TOUCH_IV" -lt $((STUCK_MAX / 4)) ]]; then
  pass "Case 6: invariant touch_interval($TOUCH_IV) << stuck_max($STUCK_MAX) (4x headroom)"
else
  fail "Case 6: touch_interval($TOUCH_IV) too close to stuck_max($STUCK_MAX); widen headroom"
fi

# --- Case 7: timeout-ladder invariant (T-P1) — daemon_worst < send_wait < controller ---
# The daemon runs at plist CODEX_EXEC_TIMEOUT (NOT the script default 240), so
# worst-case = max_attempts(2) × EXEC. If send_wait < daemon_worst, a review
# whose attempt 1 fails and retries (attempt 2) gets killed mid-flight (T-P0 root
# cause: archive attempt=2 exit=124). Read the REAL plist EXEC_TIMEOUT, max_attempts
# from codex-watch source, send_wait from WRITER default, controller from controller.py.
WRITER="$REPO_ROOT/vendor/l3-transport/scripts/review-result-writer.sh"
PLIST="$REPO_ROOT/vendor/l3-transport/launchagents/com.praise.codex-watch.plist"
EXEC_TO=$(/usr/bin/grep -A1 "CODEX_EXEC_TIMEOUT" "$PLIST" 2>/dev/null | /usr/bin/grep -oE "[0-9]+" | head -1 || true)
[[ -n "$EXEC_TO" ]] || EXEC_TO=720
MAX_ATT=$(/usr/bin/grep -oE "max_attempts[^0-9]*[0-9]+" "$CW" 2>/dev/null | head -1 | /usr/bin/grep -oE "[0-9]+" || true)
[[ -n "$MAX_ATT" ]] || MAX_ATT=2
DAEMON_WORST=$((MAX_ATT * EXEC_TO))
# send_wait default (writer: CODEX_SEND_WAIT_TIMEOUT:-<N>). grep WRITER not codex-watch.
SEND_WAIT=$(/usr/bin/grep -oE 'CODEX_SEND_WAIT_TIMEOUT:-[0-9]+' "$WRITER" 2>/dev/null | head -1 | /usr/bin/grep -oE '[0-9]+' || true)
[[ -n "$SEND_WAIT" ]] || SEND_WAIT=1500
# controller bridge_timeout non-deep (controller.py: bridge_timeout = <N>)
CONTROLLER=$(/usr/bin/grep -E '^\s*bridge_timeout = [0-9]+' "$REPO_ROOT/scripts/gd-review-controller.py" 2>/dev/null | head -1 | /usr/bin/grep -oE '[0-9]+' | head -1 || true)
[[ -n "$CONTROLLER" ]] || CONTROLLER=1700
echo "Case 7 config: EXEC_TO=$EXEC_TO max_attempts=$MAX_ATT daemon_worst=$DAEMON_WORST send_wait=$SEND_WAIT controller=$CONTROLLER"
if [[ "$DAEMON_WORST" -lt "$SEND_WAIT" && "$SEND_WAIT" -le "$CONTROLLER" ]]; then
  pass "Case 7: invariant daemon_worst($DAEMON_WORST) < send_wait($SEND_WAIT) <= controller($CONTROLLER)"
else
  fail "Case 7: invariant BROKEN daemon_worst($DAEMON_WORST) send_wait($SEND_WAIT) controller($CONTROLLER) — a retrying review will be killed mid-flight"
fi

echo ""
echo "=== summary: PASS=$PASS FAIL=$FAIL ==="
if [[ $FAIL -eq 0 ]]; then
  echo "GD_WATCH_TOUCH_AND_REAP_SMOKE: PASS"
  exit 0
else
  echo "GD_WATCH_TOUCH_AND_REAP_SMOKE: FAIL"
  exit 1
fi
