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

# Resolve transport paths from the SAME state-paths.sh as the writer/daemon, so
# the L1 discuss path and L3 review path share one HANDOFF_BIN (no drift).
_CONSULT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../handoff/lib/state-paths.sh
. "$_CONSULT_SCRIPT_DIR/../handoff/lib/state-paths.sh"

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

# Use live codex-send-wait (same daemon as review, different mode).
# CODEX_BIN resolved via state-paths.sh ${HANDOFF_BIN} — same coordination root as
# the writer/daemon, no $HOME/.claude/handoff hardcode.
# CODEX_SEND_WAIT_TIMEOUT is read by codex-send-wait; no hardcoded --timeout here
# so the single env var controls both discuss and review paths (SC-06).
CODEX_BIN="${HANDOFF_BIN}/codex-send-wait"

if [[ ! -x "$CODEX_BIN" ]]; then
  echo "[DISCUSS] DEGRADED — watch unavailable, cannot get second opinion"
  echo "[讨论] ⚠️ 缺 codex 传输栈：未找到可执行 codex-send-wait（路径 ${CODEX_BIN}）。fail-closed，不产出第二意见；请先按 README 部署传输栈后重试。" >&2
  exit 2
fi

CODEX_OUTPUT=$("$CODEX_BIN" --cwd "$DISCUSS_CWD" --mode discuss \
  --payload-file "$CAPSULE_FILE" 2>&1) || {
  exit_code=$?
  if [[ $exit_code -eq 2 ]]; then
    echo "[DISCUSS] DEGRADED — watch unavailable, cannot get second opinion"
    exit 2
  fi
  echo "[DISCUSS] FAILED — codex-send-wait exit $exit_code" >&2
  echo "$CODEX_OUTPUT" >&2
  exit 4
}

# SC-1/SC-2: fail-closed marker check on a successful codex-send-wait return.
# codex-send-wait exit 0 is not by itself proof of a valid second opinion — the
# discuss output must carry a line-anchored RECOMMENDATION: marker, and must NOT
# carry a line-anchored VERDICT: (that is the review path's gate, never discuss).
# Without this check a malformed/empty Codex output is echoed as a valid opinion.
if ! printf '%s\n' "$CODEX_OUTPUT" | grep -qE '^RECOMMENDATION:'; then
  echo "[DISCUSS] FAILED — no RECOMMENDATION in Codex output" >&2
  printf '%s\n' "$CODEX_OUTPUT" >&2
  exit 4
fi
if printf '%s\n' "$CODEX_OUTPUT" | grep -qE '^VERDICT:'; then
  echo "[DISCUSS] FAILED — discuss output contains VERDICT" >&2
  printf '%s\n' "$CODEX_OUTPUT" >&2
  exit 4
fi

echo "$CODEX_OUTPUT"