#!/usr/bin/env bash
# Shared path definitions for handoff system.
#
# HANDOFF_ROOT is the SINGLE daemon↔client coordination point: install-transport.sh
# (daemon deploy target) and codex-send-wait (client lookup) MUST both source THIS
# file so they resolve to the identical value — if the two ends disagree, transport
# breaks silently. This is plugin-managed transport infrastructure, NOT an installer
# setup preset (it must never be a free-fill field; a wrong value = broken chain).
#
# All variables use ${VAR:=default} so callers can override by exporting before
# sourcing this file (e.g. `export HANDOFF_ROOT=/tmp/h`). This enables verifier
# isolated tests to inject a temporary HANDOFF_ROOT without polluting real runtime.
#
# Default precedence: ${CLAUDE_PLUGIN_DATA} (update-safe plugin data dir) when set,
# else ${HOME}/.claude as fallback; transport state lives under a `gd-handoff` subdir.

if [[ -z "${HANDOFF_ROOT:-}" && -z "${CLAUDE_PLUGIN_DATA:-}" ]]; then
  _GD_DEFAULT_PLUGIN_DATA="${HOME}/.claude/plugins/data/codex-openai-codex"
  if [[ -d "${_GD_DEFAULT_PLUGIN_DATA}/gd-handoff" ]]; then
    CLAUDE_PLUGIN_DATA="${_GD_DEFAULT_PLUGIN_DATA}"
  fi
fi

: "${HANDOFF_ROOT:=${CLAUDE_PLUGIN_DATA:-${HOME}/.claude}/gd-handoff}"
: "${HANDOFF_BIN:=${HANDOFF_ROOT}/bin}"
: "${HANDOFF_LIB:=${HANDOFF_ROOT}/lib}"
: "${HANDOFF_ACTIVE:=${HANDOFF_ROOT}/active}"
: "${HANDOFF_ARCHIVE:=${HANDOFF_ROOT}/archive}"
: "${HANDOFF_STATE:=${HANDOFF_ROOT}/state}"
: "${HANDOFF_PID:=${HANDOFF_STATE}/codex-watch.pid}"
: "${HANDOFF_LOG:=${HANDOFF_STATE}/codex-watch.log}"

export HANDOFF_ROOT HANDOFF_BIN HANDOFF_LIB HANDOFF_ACTIVE HANDOFF_ARCHIVE HANDOFF_STATE HANDOFF_PID HANDOFF_LOG
if [[ -n "${CLAUDE_PLUGIN_DATA:-}" ]]; then
  export CLAUDE_PLUGIN_DATA
fi
