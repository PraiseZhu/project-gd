#!/usr/bin/env bash
# codex-consult.sh — Discuss entry point for L1 /review1 default mode.
#
# Reads a discuss capsule, sends it to codex-watch via codex-send-wait
# in discuss mode, and returns the codex discussion text.
#
# This is the L1 "second opinion" path — NO verdict gate, NO baseline write,
# NO stop hook. Separated from review-result-writer.sh to avoid review baggage.
#
# Usage:
#   bash <GD_ROOT>/vendor/l3-transport/scripts/codex-consult.sh \
#     --capsule-file /path/to/discuss-capsule.txt \
#     [--cwd /project/dir]
#
# Discuss capsule format (Claude produces):
#   QUESTION: <the question being asked>
#   CONTEXT: <relevant context>
#   CLAUDE_LEAN: <optional, Claude's current lean>
#   OPTIONS: <optional, options being considered>
#
# Exit codes:
#   0 — discuss complete, result contains RECOMMENDATION
#   1 — usage error
#   2 — watcher unavailable
#   3 — timeout
#   4 — discuss failed (no RECOMMENDATION or codex error)

set -euo pipefail

CAPSULE_FILE=""
DISCUSS_CWD="${PWD}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --capsule-file) CAPSULE_FILE="$2"; shift 2 ;;
    --cwd) DISCUSS_CWD="$2"; shift 2 ;;
    *) echo "[DISCUSS] FAILED — unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$CAPSULE_FILE" ]]; then
  echo "[DISCUSS] FAILED — missing required arg: --capsule-file" >&2
  exit 1
fi

if [[ ! -f "$CAPSULE_FILE" ]]; then
  echo "[DISCUSS] FAILED — capsule file not found: $CAPSULE_FILE" >&2
  exit 1
fi

# Use live codex-send-wait (same daemon as review, different mode)
CODEX_BIN="$HOME/.claude/handoff/bin/codex-send-wait"
CODEX_OUTPUT=""
CODEX_EXIT=0

if [[ -x "$CODEX_BIN" ]]; then
  CODEX_OUTPUT=$("$CODEX_BIN" --cwd "$DISCUSS_CWD" --mode discuss --payload-file "$CAPSULE_FILE" --timeout 540 2>&1) || CODEX_EXIT=$?
else
  CODEX_EXIT=127
fi

if [[ $CODEX_EXIT -eq 127 ]] || [[ $CODEX_EXIT -eq 2 ]]; then
  echo "[DISCUSS] DEGRADED — watch unavailable, cannot get second opinion"
  exit 2
elif [[ $CODEX_EXIT -ne 0 ]]; then
  echo "[DISCUSS] FAILED — codex-send-wait exit $CODEX_EXIT" >&2
  echo "$CODEX_OUTPUT" >&2
  exit 4
fi

# Output the discussion result (stdout — Claude reads this)
echo "$CODEX_OUTPUT"

# Quick sanity: check for RECOMMENDATION marker
if ! echo "$CODEX_OUTPUT" | grep -q '^RECOMMENDATION:'; then
  echo "[DISCUSS] WARNING — result missing RECOMMENDATION marker" >&2
  # Still exit 0 — result is returned, Claude can decide
fi

exit 0