#!/usr/bin/env bash
# gd-parity-verify.sh — Runtime parity verifier for Project GD bundles.
#
# Usage:
#   gd-parity-verify.sh --bundle gd-command     # Exit 0: PASS, 2: drift, 3: missing
#   gd-parity-verify.sh --bundle codex-chain    # Exit 0 always; status in stdout JSON
#
# All output is line-prefixed JSON or plain status tokens; no files are written.
# Reads config/gd-runtime-parity-manifest.json for paths.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$ROOT/config/gd-runtime-parity-manifest.json"

_sha256() {
  shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'
}

_json_field() {
  python3 -c "import json,sys; d=json.load(open('$1')); print(d$2)" 2>/dev/null
}

usage() {
  echo "Usage: $0 --bundle <gd-command|codex-chain>"
  exit 1
}

[ $# -lt 2 ] && usage
BUNDLE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle) BUNDLE="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -z "$BUNDLE" ] && usage

# ── Validate manifest exists ────────────────────────────────────────────────
if [ ! -f "$MANIFEST" ]; then
  echo '{"status":"manifest_missing","message":"config/gd-runtime-parity-manifest.json not found"}'
  exit 3
fi

# ── Bundle: gd-command ──────────────────────────────────────────────────────
if [ "$BUNDLE" = "gd-command" ]; then
  SOURCE_REL=$(_json_field "$MANIFEST" "['bundles']['gd_command']['source_path']")
  RUNTIME=$(_json_field "$MANIFEST" "['bundles']['gd_command']['runtime_path']")
  SOURCE="$ROOT/$SOURCE_REL"

  if [ ! -f "$SOURCE" ]; then
    echo "{\"status\":\"source_missing\",\"bundle\":\"gd-command\",\"source_path\":\"$SOURCE\"}"
    exit 3
  fi
  if [ ! -f "$RUNTIME" ]; then
    echo "{\"status\":\"runtime_missing\",\"bundle\":\"gd-command\",\"runtime_path\":\"$RUNTIME\"}"
    exit 3
  fi

  SRC_HASH=$(_sha256 "$SOURCE")
  RT_HASH=$(_sha256 "$RUNTIME")

  if [ "$SRC_HASH" = "$RT_HASH" ]; then
    echo "{\"status\":\"installed_parity_pass\",\"bundle\":\"gd-command\",\"sha256\":\"$SRC_HASH\",\"source_path\":\"$SOURCE\",\"runtime_path\":\"$RUNTIME\"}"
    exit 0
  else
    echo "{\"status\":\"installed_runtime_drift\",\"bundle\":\"gd-command\",\"source_sha256\":\"$SRC_HASH\",\"runtime_sha256\":\"$RT_HASH\",\"source_path\":\"$SOURCE\",\"runtime_path\":\"$RUNTIME\"}"
    exit 2
  fi
fi

# ── Bundle: codex-chain ─────────────────────────────────────────────────────
if [ "$BUNDLE" = "codex-chain" ]; then
  SYNC_HASH_FILE="$ROOT/mirrors/codex-chain/.sync-content-hash"
  L1_MIRROR="$ROOT/mirrors/codex-chain/l1-binary"
  L2_MIRRORS=("$ROOT/mirrors/codex-chain/l2-config" "$ROOT/mirrors/codex-chain/l2-memories" "$ROOT/mirrors/codex-chain/l2-system-skills" "$ROOT/mirrors/codex-chain/l2-automations")
  L1_RUNTIME="$HOME/.npm-global/lib/node_modules/@openai/codex"
  L2_RUNTIME="$HOME/.codex"

  # Mirror existence
  if [ ! -d "$L1_MIRROR" ]; then
    echo '{"status":"codex_chain_mirror_stale","detail":"l1-binary mirror directory missing"}'
    exit 0
  fi

  # Sync hash freshness (recorded by gd-sync-codex-chain.sh)
  SYNC_HASH=""
  if [ -f "$SYNC_HASH_FILE" ]; then
    SYNC_HASH=$(cat "$SYNC_HASH_FILE" | tr -d '[:space:]')
  fi

  # L1 runtime hash (sample: hash the package.json for stability)
  L1_RT_HASH="runtime_unreadable"
  if [ -f "$L1_RUNTIME/package.json" ]; then
    L1_RT_HASH=$(_sha256 "$L1_RUNTIME/package.json")
  fi

  L1_MIRROR_HASH="mirror_missing"
  if [ -f "$L1_MIRROR/package.json" ]; then
    L1_MIRROR_HASH=$(_sha256 "$L1_MIRROR/package.json")
  fi

  L1_STATUS="fresh"
  if [ "$L1_RT_HASH" = "runtime_unreadable" ] || [ "$L1_MIRROR_HASH" = "mirror_missing" ]; then
    L1_STATUS="unknown"
  elif [ "$L1_RT_HASH" != "$L1_MIRROR_HASH" ]; then
    L1_STATUS="stale"
  fi

  # L2 runtime hash (sample: count files for freshness proxy)
  L2_RT_COUNT="0"
  if [ -d "$L2_RUNTIME" ]; then
    L2_RT_COUNT=$(find "$L2_RUNTIME" -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d ' ')
  fi

  L2_MIRROR_COUNT="0"
  for d in "${L2_MIRRORS[@]}"; do
    if [ -d "$d" ]; then
      C=$(find "$d" -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d ' ')
      L2_MIRROR_COUNT=$((L2_MIRROR_COUNT + C))
    fi
  done

  # L2: file-count presence probe (NOT strict parity — counts only, not hashes)
  L2_STATUS="unknown"
  if [ "$L2_RT_COUNT" -gt 0 ] && [ "$L2_MIRROR_COUNT" -gt 0 ]; then
    L2_STATUS="files_present"   # both sides have files; NOT a hash match assertion
  elif [ "$L2_RT_COUNT" -eq 0 ] && [ "$L2_MIRROR_COUNT" -gt 0 ]; then
    L2_STATUS="runtime_missing"
  elif [ "$L2_RT_COUNT" -gt 0 ] && [ "$L2_MIRROR_COUNT" -eq 0 ]; then
    L2_STATUS="mirror_missing"
  fi

  # Overall freshness (audit probe, NOT strict parity):
  #   freshness_ok  — L1 sentinel matches, L2 files present on both sides
  #   codex_chain_mirror_stale — L1 drifted or L2 mirror missing
  #   unknown       — unable to probe runtime or mirror
  OVERALL="freshness_ok"
  if [ "$L1_STATUS" = "stale" ] || [ "$L2_STATUS" = "mirror_missing" ]; then
    OVERALL="codex_chain_mirror_stale"
  elif [ "$L1_STATUS" = "unknown" ] || [ "$L2_STATUS" = "unknown" ] || [ "$L2_STATUS" = "runtime_missing" ]; then
    OVERALL="unknown"
  fi

  # check_type: "audit_freshness" — this is NOT strict file-by-file parity.
  # L1 freshness is based on package.json hash sentinel only.
  # L2 freshness is based on file-count presence probe only.
  echo "{\"status\":\"$OVERALL\",\"check_type\":\"audit_freshness\",\"bundle\":\"codex-chain\",\"l1\":{\"status\":\"$L1_STATUS\",\"check_method\":\"package_json_sentinel\",\"mirror_package_sha256\":\"$L1_MIRROR_HASH\",\"runtime_package_sha256\":\"$L1_RT_HASH\"},\"l2\":{\"status\":\"$L2_STATUS\",\"check_method\":\"file_count_presence\",\"mirror_file_count\":$L2_MIRROR_COUNT,\"runtime_file_count\":$L2_RT_COUNT},\"sync_content_hash\":\"$SYNC_HASH\"}"
  exit 0
fi

echo "{\"status\":\"unknown_bundle\",\"bundle\":\"$BUNDLE\"}"
exit 1
