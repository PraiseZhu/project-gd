#!/usr/bin/env bash
# Shared runtime state determination for codex-watch.
# Source this file; do NOT execute directly.
#
# Requires (from state-paths.sh):
#   HANDOFF_PID, HANDOFF_STATE, HANDOFF_ACTIVE
#
# Exports:
#   watch_state()         -> echoes one of:
#                              RUNNING pid=<N>
#                              RUNNING pid=<N> permission_limited=true
#                              DEGRADED_HEARTBEAT_ONLY reason=<text>
#                              STOPPED reason=<text>
#                           exit code: 0=RUNNING, 2=DEGRADED, 1=STOPPED
#   heartbeat_age()       -> seconds since last heartbeat, or "none"
#   queue_counts()        -> "queued=N running=N done=N failed=N"
#   recent_failed_jobs(N) -> job IDs, one per line (newest first)

HEARTBEAT_MAX_AGE="${HEARTBEAT_MAX_AGE:-120}"

heartbeat_age() {
  local hb="${HANDOFF_STATE}/heartbeat"
  if [[ ! -f "$hb" ]]; then
    echo "none"
    return
  fi
  local last_beat now
  last_beat=$(cat "$hb" 2>/dev/null || echo "0")
  now=$(date +%s)
  echo $((now - last_beat))
}

# _pid_probe <pid>
# Returns one of: alive | dead | permission_denied
# Distinguishes sandbox permission errors from truly absent processes.
_pid_probe() {
  local pid="$1"
  [[ -z "$pid" ]] && echo "dead" && return

  if kill -0 "$pid" 2>/dev/null; then
    echo "alive"
    return
  fi

  # Capture stderr to tell permission error from "no such process"
  local probe_err
  probe_err=$(kill -0 "$pid" 2>&1 || true)
  if echo "$probe_err" | grep -qiE 'operation not permitted|permission denied'; then
    echo "permission_denied"
  else
    echo "dead"
  fi
}

watch_state() {
  local pid="" pid_status hb_age reason

  if [[ -f "$HANDOFF_PID" ]]; then
    pid=$(cat "$HANDOFF_PID" 2>/dev/null || true)
  fi

  pid_status=$(_pid_probe "$pid")
  hb_age=$(heartbeat_age)

  # Case 1: process confirmed alive
  if [[ "$pid_status" == "alive" ]]; then
    echo "RUNNING pid=${pid}"
    return 0
  fi

  # Case 2: permission denied (sandbox) — fall back to heartbeat
  if [[ "$pid_status" == "permission_denied" ]]; then
    if [[ "$hb_age" != "none" && "$hb_age" -le "$HEARTBEAT_MAX_AGE" ]]; then
      echo "RUNNING pid=${pid} permission_limited=true"
      return 0
    fi
    # permission_denied but heartbeat stale/absent → treat as STOPPED
    reason="pid ${pid} permission_denied, heartbeat ${hb_age}s ago"
    echo "STOPPED reason=${reason}"
    return 1
  fi

  # Case 3: pid dead — check heartbeat for DEGRADED state
  if [[ "$hb_age" != "none" && "$hb_age" -le "$HEARTBEAT_MAX_AGE" ]]; then
    if [[ -n "$pid" ]]; then
      reason="pid ${pid} dead but heartbeat fresh (${hb_age}s ago)"
    else
      reason="no pidfile but heartbeat fresh (${hb_age}s ago)"
    fi
    echo "DEGRADED_HEARTBEAT_ONLY reason=${reason}"
    return 2
  fi

  # Case 4: both pid dead and heartbeat stale/absent
  if [[ -n "$pid" ]]; then
    reason="pid ${pid} dead, heartbeat ${hb_age}s ago"
  else
    reason="no pidfile, no fresh heartbeat"
  fi
  echo "STOPPED reason=${reason}"
  return 1
}

queue_counts() {
  local q=0 r=0 d=0 f=0
  for sf in "${HANDOFF_ACTIVE}"/*.status; do
    [[ -f "$sf" ]] || continue
    local st
    st=$(cat "$sf" 2>/dev/null || true)
    case "$st" in
      queued)  q=$((q+1)) ;;
      running) r=$((r+1)) ;;
      done)    d=$((d+1)) ;;
      failed)  f=$((f+1)) ;;
    esac
  done
  echo "queued=${q} running=${r} done=${d} failed=${f}"
}

recent_failed_jobs() {
  local limit="${1:-3}"
  local count=0
  for sf in $(ls -r "${HANDOFF_ACTIVE}"/*.status 2>/dev/null); do
    [[ -f "$sf" ]] || continue
    local st
    st=$(cat "$sf" 2>/dev/null || true)
    if [[ "$st" == "failed" ]]; then
      basename "${sf%.status}"
      count=$((count+1))
      [[ $count -ge $limit ]] && break
    fi
  done
}
