#!/usr/bin/env bash
# Shared path definitions for handoff system.
#
# All variables use ${VAR:=default} so callers can override by exporting before
# sourcing this file. This enables verifier isolated tests to inject a temporary
# HANDOFF_ROOT without polluting the real runtime paths.

: "${HANDOFF_ROOT:=${HOME}/.claude/handoff}"
: "${HANDOFF_BIN:=${HANDOFF_ROOT}/bin}"
: "${HANDOFF_LIB:=${HANDOFF_ROOT}/lib}"
: "${HANDOFF_ACTIVE:=${HANDOFF_ROOT}/active}"
: "${HANDOFF_ARCHIVE:=${HANDOFF_ROOT}/archive}"
: "${HANDOFF_STATE:=${HANDOFF_ROOT}/state}"
: "${HANDOFF_PID:=${HANDOFF_STATE}/codex-watch.pid}"
: "${HANDOFF_LOG:=${HANDOFF_STATE}/codex-watch.log}"
