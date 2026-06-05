#!/usr/bin/env bash
# install-transport.sh — Deploy daemon-side transport files from GD vendor to live.
#
# Deploys: handoff/bin/* + handoff/lib/* + launchagents/*.plist → live
# Does NOT deploy: scripts/* (codex-consult.sh / review-result-writer.sh
#   run directly from vendor, avoiding dual-copy drift).
#
# Features:
#   - SHA-256 before/after verification
#   - Idempotent (skip if hash matches)
#   - Backup original files with timestamp
#   - Drain active queue before kickstart
#   - --dry-run default (no changes without --yes)
#
# Usage:
#   bash install-transport.sh --dry-run          # preview only (default)
#   bash install-transport.sh --yes              # execute deployment
#   bash install-transport.sh --yes --no-restart # deploy but don't restart daemon

set -euo pipefail

# ─── Paths ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GD_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENDOR_DIR="$GD_ROOT/vendor/l3-transport"

LIVE_HANDOFF="$HOME/.claude/handoff"
LIVE_BIN="$LIVE_HANDOFF/bin"
LIVE_LIB="$LIVE_HANDOFF/lib"
LIVE_LAUNCHAGENTS="$HOME/Library/LaunchAgents"
PLIST_NAME="com.praise.codex-watch.plist"

SRC_BIN="$VENDOR_DIR/handoff/bin"
SRC_LIB="$VENDOR_DIR/handoff/lib"
SRC_PLIST="$VENDOR_DIR/launchagents/$PLIST_NAME"

DRY_RUN=true
RESTART_DAEMON=true

# ─── Args ───
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --yes) DRY_RUN=false; shift ;;
    --no-restart) RESTART_DAEMON=false; shift ;;
    *) echo "Usage: install-transport.sh [--dry-run|--yes] [--no-restart]" >&2; exit 1 ;;
  esac
done

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$LIVE_HANDOFF/.backup-${TIMESTAMP}"

# ─── Helpers ───
sha256_file() {
  if [[ -f "$1" ]]; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    echo "MISSING"
  fi
}

log() { echo "[install-transport] $*"; }

# ─── Preflight ───
log "=== Preflight ==="
log "GD root:     $GD_ROOT"
log "Vendor dir:  $VENDOR_DIR"
log "Live bin:    $LIVE_BIN"
log "Live lib:    $LIVE_LIB"
log "Live plist:  $LIVE_LAUNCHAGENTS/$PLIST_NAME"
log "Mode:        $(if $DRY_RUN; then echo 'DRY-RUN (no changes)'; else echo 'LIVE'; fi)"
log ""

# Verify source exists
for src in "$SRC_BIN" "$SRC_LIB" "$SRC_PLIST"; do
  if [[ ! -e "$src" ]]; then
    log "ERROR: source not found: $src" >&2
    exit 1
  fi
done

# ─── Deploy plan ───
log "=== Deploy Plan ==="
log "Files to deploy (daemon-side only, NO scripts/):"

deploy_count=0
declare -a DEPLOY_SOURCES=()
declare -a DEPLOY_TARGETS=()

# Binaries
for f in "$SRC_BIN"/*; do
  fname=$(basename "$f")
  target="$LIVE_BIN/$fname"
  DEPLOY_SOURCES+=("$f")
  DEPLOY_TARGETS+=("$target")
  src_hash=$(sha256_file "$f")
  tgt_hash=$(sha256_file "$target")
  if [[ "$src_hash" == "$tgt_hash" ]]; then
    log "  SKIP bin/$fname (hash match)"
  else
    log "  DEPLOY bin/$fname ($src_hash → $tgt_hash)"
    deploy_count=$((deploy_count + 1))
  fi
done

# Library
for f in "$SRC_LIB"/*; do
  fname=$(basename "$f")
  target="$LIVE_LIB/$fname"
  DEPLOY_SOURCES+=("$f")
  DEPLOY_TARGETS+=("$target")
  src_hash=$(sha256_file "$f")
  tgt_hash=$(sha256_file "$target")
  if [[ "$src_hash" == "$tgt_hash" ]]; then
    log "  SKIP lib/$fname (hash match)"
  else
    log "  DEPLOY lib/$fname ($src_hash → $tgt_hash)"
    deploy_count=$((deploy_count + 1))
  fi
done

# Plist
target_plist="$LIVE_LAUNCHAGENTS/$PLIST_NAME"
src_hash=$(sha256_file "$SRC_PLIST")
tgt_hash=$(sha256_file "$target_plist")
if [[ "$src_hash" == "$tgt_hash" ]]; then
  log "  SKIP $PLIST_NAME (hash match)"
else
  log "  DEPLOY $PLIST_NAME ($src_hash → $tgt_hash)"
  deploy_count=$((deploy_count + 1))
fi

log ""
log "Total files to deploy: $deploy_count"

# Explicitly confirm: no scripts/ in deploy set
log "SCRIPTS/ NOT DEPLOYED: codex-consult.sh, review-result-writer.sh run from vendor"
log ""

if $DRY_RUN; then
  log "=== DRY-RUN COMPLETE ==="
  log "Run with --yes to execute deployment."
  exit 0
fi

if [[ $deploy_count -eq 0 ]]; then
  log "Nothing to deploy (all hashes match)."
  exit 0
fi

# ─── Backup ───
log "=== Backup ==="
mkdir -p "$BACKUP_DIR"
for f in "$LIVE_BIN"/* "$LIVE_LIB"/*; do
  if [[ -f "$f" ]]; then
    cp "$f" "$BACKUP_DIR/"
    log "  Backup: $(basename "$f")"
  fi
done
if [[ -f "$target_plist" ]]; then
  cp "$target_plist" "$BACKUP_DIR/"
  log "  Backup: $PLIST_NAME"
fi
log "Backup stored at: $BACKUP_DIR"

# ─── Deploy ───
log "=== Deploy ==="
mkdir -p "$LIVE_BIN" "$LIVE_LIB"

for i in "${!DEPLOY_SOURCES[@]}"; do
  src="${DEPLOY_SOURCES[$i]}"
  tgt="${DEPLOY_TARGETS[$i]}"
  fname=$(basename "$tgt")
  src_hash_before=$(sha256_file "$src")
  cp "$src" "$tgt"
  # Preserve executable bit
  if [[ -x "$src" ]]; then
    chmod +x "$tgt"
  fi
  tgt_hash_after=$(sha256_file "$tgt")
  if [[ "$src_hash_before" == "$tgt_hash_after" ]]; then
    log "  OK: $fname ($src_hash_before)"
  else
    log "  FAIL: $fname hash mismatch after copy!" >&2
    exit 1
  fi
done

# Plist (separate because it's not in the DEPLOY arrays for bin/lib)
if [[ "$src_hash" != "$tgt_hash" ]]; then
  cp "$SRC_PLIST" "$target_plist"
  plist_hash_after=$(sha256_file "$target_plist")
  if [[ "$src_hash" == "$plist_hash_after" ]]; then
    log "  OK: $PLIST_NAME ($src_hash)"
  else
    log "  FAIL: $PLIST_NAME hash mismatch after copy!" >&2
    exit 1
  fi
fi

log "Deploy complete: $deploy_count files"

# ─── Drain + Restart ───
if $RESTART_DAEMON; then
  log ""
  log "=== Drain + Restart ==="

  # Check active queue
  active_count=$(find "$LIVE_HANDOFF/active" -maxdepth 1 -name '*.capsule' -type f 2>/dev/null | wc -l | tr -d ' ')
  running_count=$(find "$LIVE_HANDOFF/active" -maxdepth 1 -name '*.worker.running' -type f 2>/dev/null | wc -l | tr -d ' ')

  if [[ $active_count -gt 0 ]] || [[ $running_count -gt 0 ]]; then
    log "Active jobs: ${active_count} capsules, ${running_count} running"
    log "Waiting for drain (max 120s)..."
    waited=0
    while [[ $waited -lt 120 ]]; do
      active_count=$(ls "$LIVE_HANDOFF/active"/*.capsule 2>/dev/null | wc -l | tr -d ' ')
      running_count=$(ls "$LIVE_HANDOFF/active"/*.worker.running 2>/dev/null | wc -l | tr -d ' ')
      if [[ $active_count -eq 0 ]] && [[ $running_count -eq 0 ]]; then
        log "Queue drained after ${waited}s"
        break
      fi
      sleep 5
      waited=$((waited + 5))
    done
    if [[ $active_count -gt 0 ]] || [[ $running_count -gt 0 ]]; then
      log "WARNING: queue not fully drained after 120s (${active_count} capsules, ${running_count} running)"
      log "Proceeding with kickstart anyway — in-flight jobs may be interrupted"
    fi
  else
    log "No active jobs — safe to restart"
  fi

  # Unload + reload via launchctl
  if launchctl list | grep -q "com.praise.codex-watch"; then
    log "Unloading com.praise.codex-watch..."
    launchctl unload "$target_plist" 2>/dev/null || true
    sleep 2
  fi

  log "Loading com.praise.codex-watch..."
  launchctl load "$target_plist"

  log "Kickstarting com.praise.codex-watch..."
  launchctl kickstart -k "gui/$(id -u)/com.praise.codex-watch" 2>/dev/null || \
    launchctl kickstart "system/com.praise.codex-watch" 2>/dev/null || \
    log "NOTE: kickstart may have failed; daemon will start on next load"

  sleep 3

  # Verify
  if pgrep -f "codex-watch" >/dev/null 2>&1; then
    log "Daemon restarted successfully (pid: $(pgrep -f 'codex-watch' | head -1))"
  else
    log "WARNING: daemon process not found after restart"
  fi
fi

log ""
log "=== INSTALL COMPLETE ==="
log "Backup: $BACKUP_DIR"
log "Run 'codex-status' to verify health."