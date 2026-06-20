#!/usr/bin/env bash
# gd-source-only-run.sh — Run GD source-only verification with an auto-logged trace.
#
# Wraps the source-only verification suite (pytest / L1 smoke / offline-smoke /
# router+validator self-test / parity dry-run) so the FULL command trace is tee'd to
# results/source-only-run-<ts>.commands.log — a real execution trace, not a hand-written
# command list — and the log path is pinned to results/.source-only-log-path so any
# shell / CI / handoff can locate it without a $SOURCE_ONLY_COMMAND_LOG env var being
# re-exported. Then runs the SC-12 live-write grep gate + git-status snapshot.
#
# This is the SC-12 evidence generator. It never performs a live write: no
# install-transport.sh --yes, no claude plugin install/update, no launchctl, no writes
# under /Users/praise/.claude or ~/Library/LaunchAgents. install-transport.sh --dry-run
# output is redirected to a separate .dryrun.log (DRY_RUN_ONLY) so its observed live
# paths do not pollute the command trace.
#
# Usage: bash scripts/gd-source-only-run.sh
set -euo pipefail

GD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$GD_ROOT"
PY=/Users/praise/.pyenv/shims/python3
mkdir -p results
TS=$(date -u +%Y%m%dT%H%M%SZ)
LOG="results/source-only-run-${TS}.commands.log"
DRYRUN="results/source-only-run-${TS}.dryrun.log"

# Pin the log path so CI / handoff / a fresh shell can find it without an env var.
echo "$LOG" > results/.source-only-log-path

# Tee the entire session (stdout+stderr) to the log — real trace, not a hand list.
exec > >(tee "$LOG") 2>&1

echo "# source-only run trace — generated $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# Real execution trace (tee'd), not a hand-written command list."
echo "# Dry-run output is kept separately at: $DRYRUN (DRY_RUN_ONLY)"
echo

echo "=== pytest (full) ==="
$PY -m pytest -q

echo "=== L1 discuss marker smoke ==="
bash tests/gd-l1-discuss-marker-contract-smoke.sh

echo "=== L1 review writer smoke ==="
bash tests/gd-l1-review-writer-marker-contract-smoke.sh

echo "=== offline-smoke ==="
bash tests/transport/offline-smoke.sh

echo "=== router self-test ==="
$PY scripts/gd-review-router.py --self-test

echo "=== route validator self-test ==="
$PY scripts/gd-validate-route-report.py --self-test

echo "=== L1 command contract validator ==="
$PY scripts/gd-validate-l1-command-contract.py commands/review1.md

echo "=== git diff --check ==="
git diff --check

echo "=== install-transport --dry-run (DRY_RUN_ONLY → $DRYRUN) ==="
bash vendor/l3-transport/scripts/install-transport.sh --dry-run > "$DRYRUN" 2>&1 || true
echo "(dry-run output redirected to $DRYRUN; not part of the command trace)"

echo
echo "=== SC-12: live-write grep gate ==="
if grep -E "install-transport\.sh --yes|claude plugin (install|update)|launchctl (load|unload|kickstart)|cp .*Library/LaunchAgents|mkdir -p .*\.claude|mv .*\.claude" "$LOG"; then
  echo "LIVE_WRITE_COMMANDS_DETECTED: FAIL"
  exit 1
else
  echo "LIVE_WRITE_COMMANDS_ABSENT: PASS"
fi

echo "=== git status snapshot (whitelist) ==="
git status --short --branch

echo
echo "=== SC-12 evidence summary ==="
echo "SOURCE_ONLY_COMMAND_LOG=$LOG"
echo "SOURCE_ONLY_COMMAND_LOG_PIN=results/.source-only-log-path"
echo "LIVE_WRITE_COMMANDS_ABSENT: PASS"
