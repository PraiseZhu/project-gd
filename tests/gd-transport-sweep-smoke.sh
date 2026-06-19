#!/bin/bash
# gd-transport-sweep-smoke.sh
# Regression guard for the 2026-06-16 codex-watch transport reliability fixes:
#   (1) sweep_stale_worker_markers() clears leaked *.worker.running markers at
#       daemon startup. BUG B: a worker killed mid-job (healthcheck kickstart /
#       SIGKILL / crash) leaks its marker; count_running_workers then counts it
#       forever and dispatch wedges once >= MAX_PARALLEL markers leak.
#   (2) count_running_workers() plain-counts markers (no per-marker liveness —
#       staleness is handled by the startup sweep, not by counting).
#   (3) codex-watch stays bash 3.2-safe: no bash-4-only constructs ($BASHPID,
#       ${v^^}/${v,,}, declare -A, mapfile/readarray) in executable lines. A
#       $BASHPID under `set -u` crashes the worker subshell and strands the job
#       at status=running (the regression this test exists to prevent).
#
# Pinned to /bin/bash (macOS 3.2) — the daemon's actual runtime, NOT env bash.
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
DAEMON="$MAIN/vendor/l3-transport/handoff/bin/codex-watch"
[ -f "$DAEMON" ] || { echo "DAEMON_MISSING: $DAEMON" >&2; exit 1; }

fail=0

# --- Test 3: static bash 3.2 safety guard (comment lines excluded) -------------
# grep output is "N:content"; the second grep drops lines whose content (after
# "N:") begins with optional whitespace then '#', so the explanatory comments
# that *mention* $BASHPID do not trip a false positive.
if grep -nE '\$\{?BASHPID|\$\{[A-Za-z_][A-Za-z0-9_]*(\^\^|,,)|declare[[:space:]]+-A|mapfile|readarray' "$DAEMON" \
     | grep -vE '^[0-9]+:[[:space:]]*#'; then
  echo "SMOKE_RESULT: FAIL (bash-4-only construct in codex-watch executable line — breaks /bin/bash 3.2 daemon)" >&2
  exit 1
fi
echo "  ok: no bash-4-only constructs in codex-watch executable lines"

# --- Functional setup: isolated HANDOFF_ROOT + source the daemon --------------
export HANDOFF_ROOT="$(mktemp -d "${TMPDIR:-/var/tmp}/gd-sweep-smoke-XXXXXX")"
trap 'rm -rf "$HANDOFF_ROOT"' EXIT
mkdir -p "$HANDOFF_ROOT/active" "$HANDOFF_ROOT/archive" "$HANDOFF_ROOT/state"

# Sourcing defines the functions; the main dispatch is guarded by
# [[ "${BASH_SOURCE[0]}" == "${0}" ]] so nothing runs on source.
# shellcheck disable=SC1090
source "$DAEMON"
A="$HANDOFF_ROOT/active"

# --- Test 1: count_running_workers plain-counts live markers ------------------
: > "$A/job-a.worker.running"
: > "$A/job-b.worker.running"
n=$(count_running_workers)
if [ "$n" = "2" ]; then
  echo "  ok: count_running_workers counts 2 markers"
else
  echo "  FAIL: count_running_workers=$n (expected 2)" >&2; fail=1
fi

# --- Test 2: sweep clears ALL markers (empty + dead-PID content alike) --------
echo "999999" > "$A/job-c.worker.running"   # leaked marker with a dead PID inside
sweep_stale_worker_markers
# find (not `ls glob`) so a zero-match count doesn't trip set -e + pipefail.
remaining=$(find "$A" -maxdepth 1 -name '*.worker.running' | wc -l | tr -d ' ')
post=$(count_running_workers)
if [ "$remaining" = "0" ] && [ "$post" = "0" ]; then
  echo "  ok: sweep cleared all stale markers (remaining=0, count=0)"
else
  echo "  FAIL: after sweep remaining=$remaining count=$post (expected 0/0)" >&2; fail=1
fi

if [ "$fail" = "0" ]; then
  echo "SMOKE_RESULT: PASS (sweep + count + bash-3.2 safety)"
  exit 0
else
  echo "SMOKE_RESULT: FAIL" >&2
  exit 1
fi
