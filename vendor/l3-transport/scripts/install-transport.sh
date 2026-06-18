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

# HANDOFF root resolved from the SAME state-paths.sh the client (codex-send-wait)
# sources, so daemon deploy target == client lookup path (no silent drift).
# shellcheck source=../handoff/lib/state-paths.sh
. "$VENDOR_DIR/handoff/lib/state-paths.sh"

LIVE_HANDOFF="$HANDOFF_ROOT"
LIVE_BIN="$HANDOFF_BIN"
LIVE_LIB="$HANDOFF_LIB"
LIVE_LAUNCHAGENTS="$HOME/Library/LaunchAgents"
# 两个 plist 都部署：主 daemon + healthcheck。healthcheck 漏部署会留在旧路径,
# 读不到新路径 heartbeat → 每 StartInterval kickstart-kill 健康 daemon(flap 根因)。
PLIST_NAMES=("com.praise.codex-watch.plist" "com.praise.codex-watch-healthcheck.plist")
PLIST_DAEMON="${PLIST_NAMES[0]}"   # 需 kickstart 的主 daemon plist（数组首项，单一真相源）

SRC_BIN="$VENDOR_DIR/handoff/bin"
SRC_LIB="$VENDOR_DIR/handoff/lib"

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
log "Live plists: ${PLIST_NAMES[*]}"
log "Mode:        $(if $DRY_RUN; then echo 'DRY-RUN (no changes)'; else echo 'LIVE'; fi)"
log ""

# Verify source exists (bin/lib dirs + every plist template)
_srcs=("$SRC_BIN" "$SRC_LIB")
for pn in "${PLIST_NAMES[@]}"; do _srcs+=("$VENDOR_DIR/launchagents/$pn"); done
for src in "${_srcs[@]}"; do
  if [[ ! -e "$src" ]]; then
    log "ERROR: source not found: $src" >&2
    exit 1
  fi
done

# ─── Render plist placeholders → resolved runtime values ───
# bundle plists are placeholder-ized (no /Users/<dev> literals). Substitute against
# the SAME state-paths.sh-resolved values so daemon/healthcheck ProgramArguments /
# log paths / CLAUDE_PLUGIN_DATA match the client's lookup. Rendered files become deploy sources.
HANDOFF_STATE_RESOLVED="${HANDOFF_STATE:-$HANDOFF_ROOT/state}"
# CLAUDE_PLUGIN_DATA 用与 state-paths.sh 第 17 行同款 fallback：installer shell 没设该变量时
# 回退 $HOME/.claude(绝不渲染空串,否则 daemon/client 又漂移到不同 gd-handoff 根)。
CLAUDE_PLUGIN_DATA_RESOLVED="${CLAUDE_PLUGIN_DATA:-$HOME/.claude}"
# sed 用 '|' 作分隔符：若任一替换值含 '|' 会破坏 sed 表达式、产生畸形 plist。
# 正常路径不含 '|'；对 CI/自动化注入的异常路径 fail-closed，而非渲染坏文件。
for _v in "$HANDOFF_BIN" "$HANDOFF_STATE_RESOLVED" "$HANDOFF_ROOT" "$HOME" "$CLAUDE_PLUGIN_DATA_RESOLVED"; do
  case "$_v" in
    *"|"*) echo "ERROR: 路径含 '|' 无法安全渲染 plist: $_v" >&2; exit 1 ;;
  esac
done
# 渲染每个 plist 模板到临时文件;RENDERED_PLISTS[i] 对应 PLIST_NAMES[i]
declare -a RENDERED_PLISTS=()
_cleanup_rendered() { for _t in "${RENDERED_PLISTS[@]}"; do rm -f "$_t"; done; }
trap _cleanup_rendered EXIT   # 立即注册 trap；空数组遍历安全
for pn in "${PLIST_NAMES[@]}"; do
  _tmp="$(mktemp "${TMPDIR:-/tmp}/codex-watch-plist-XXXXXX")"
  RENDERED_PLISTS+=("$_tmp")   # mktemp 后立刻登记，sed 中途崩溃也能被 trap 清理
  sed \
    -e "s|__HANDOFF_BIN__|${HANDOFF_BIN}|g" \
    -e "s|__HANDOFF_STATE__|${HANDOFF_STATE_RESOLVED}|g" \
    -e "s|__HANDOFF_ROOT__|${HANDOFF_ROOT}|g" \
    -e "s|__HOME__|${HOME}|g" \
    -e "s|__CLAUDE_PLUGIN_DATA__|${CLAUDE_PLUGIN_DATA_RESOLVED}|g" \
    "$VENDOR_DIR/launchagents/$pn" > "$_tmp"
done
log "Rendered ${#PLIST_NAMES[@]} plist(s) → HANDOFF_BIN=$HANDOFF_BIN CLAUDE_PLUGIN_DATA=$CLAUDE_PLUGIN_DATA_RESOLVED"
log ""

# ─── Deploy plan ───
log "=== Deploy Plan ==="
log "Files to deploy (daemon-side only, NO scripts/):"

deploy_count=0
declare -a DEPLOY_SOURCES=()
declare -a DEPLOY_TARGETS=()

# Single loop over (src_dir, tgt_dir, label) tuples for bin and lib
for pair in "$SRC_BIN:$LIVE_BIN:bin" "$SRC_LIB:$LIVE_LIB:lib"; do
  IFS=':' read -r src_dir tgt_dir label <<< "$pair"
  for f in "$src_dir"/*; do
    fname=$(basename "$f")
    target="$tgt_dir/$fname"
    DEPLOY_SOURCES+=("$f")
    DEPLOY_TARGETS+=("$target")
    src_hash=$(sha256_file "$f")
    tgt_hash=$(sha256_file "$target")
    if [[ "$src_hash" == "$tgt_hash" ]]; then
      log "  SKIP ${label}/${fname} (hash match)"
    else
      log "  DEPLOY ${label}/${fname} ($src_hash → $tgt_hash)"
      deploy_count=$((deploy_count + 1))
    fi
  done
done

# Plists (both daemon + healthcheck; in DEPLOY arrays for unified post-copy verification)
for pi in "${!PLIST_NAMES[@]}"; do
  pn="${PLIST_NAMES[$pi]}"
  rendered="${RENDERED_PLISTS[$pi]}"
  target_pl="$LIVE_LAUNCHAGENTS/$pn"
  DEPLOY_SOURCES+=("$rendered")
  DEPLOY_TARGETS+=("$target_pl")
  src_hash=$(sha256_file "$rendered")
  tgt_hash=$(sha256_file "$target_pl")
  if [[ "$src_hash" == "$tgt_hash" ]]; then
    log "  SKIP $pn (hash match)"
  else
    log "  DEPLOY $pn ($src_hash → $tgt_hash)"
    deploy_count=$((deploy_count + 1))
  fi
done

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
for pn in "${PLIST_NAMES[@]}"; do
  _tp="$LIVE_LAUNCHAGENTS/$pn"
  if [[ -f "$_tp" ]]; then
    cp "$_tp" "$BACKUP_DIR/"
    log "  Backup: $pn"
  fi
done
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
	      active_count=$(find "$LIVE_HANDOFF/active" -maxdepth 1 -name '*.capsule' -type f 2>/dev/null | wc -l | tr -d ' ')
	      running_count=$(find "$LIVE_HANDOFF/active" -maxdepth 1 -name '*.worker.running' -type f 2>/dev/null | wc -l | tr -d ' ')
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

  # Unload + reload both plists via launchctl (daemon + healthcheck must use new paths together;
  # reloading daemon without healthcheck leaves the stale healthcheck kickstart-killing it).
  for pn in "${PLIST_NAMES[@]}"; do
    _label="${pn%.plist}"
    _tp="$LIVE_LAUNCHAGENTS/$pn"
    # Exact per-label lookup: `launchctl list "$label"` exits 0 iff that label
    # is loaded. The old `launchctl list | grep -q "$_label"` matched any line
    # CONTAINING the label as a substring (e.g. a longer label, or the label
    # appearing in another job's program path), so it could mis-decide a job was
    # loaded when it was not — leaving a stale daemon never reloaded.
    if launchctl list "$_label" >/dev/null 2>&1; then
      log "Unloading $_label..."
      launchctl unload "$_tp" 2>/dev/null || true
      sleep 1
    fi
    log "Loading $_label..."
    launchctl load "$_tp"
  done

  log "Kickstarting $PLIST_DAEMON..."
  _daemon_label="${PLIST_DAEMON%.plist}"
  launchctl kickstart -k "gui/$(id -u)/${_daemon_label}" 2>/dev/null || \
    launchctl kickstart "system/${_daemon_label}" 2>/dev/null || \
    log "NOTE: kickstart may have failed; daemon will start on next load"

  sleep 3

  # Verify
  if pgrep -f "codex-watch run" >/dev/null 2>&1; then
    log "Daemon restarted successfully (pid: $(pgrep -f 'codex-watch run' | head -1))"
  else
    log "WARNING: daemon process not found after restart"
  fi
fi

log ""
log "=== INSTALL COMPLETE ==="
log "Backup: $BACKUP_DIR"
log "Run 'codex-status' to verify health."