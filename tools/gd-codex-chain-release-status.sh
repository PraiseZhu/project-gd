#!/usr/bin/env bash
# gd-codex-chain-release-status.sh — L1/L2/L3 release gate for Project GD.
#
# Outputs:
#   L1_RELEASE_STATUS: READY|BLOCKED
#   L2_RELEASE_STATUS: READY|BLOCKED
#   L3_RELEASE_STATUS: READY|BLOCKED (strict parity)
#   OVERALL_RELEASE_STATUS: READY_FOR_COMMIT|BLOCKED
#
# Exit codes (see config/gd-runtime-parity-manifest.json release_gate_exit_codes):
#   0  — ready
#   10 — mirror_incomplete
#   11 — manifest_sync_drift
#   12 — secret_found in mirror
#   13 — untracked_release_files
#   14 — l1_must_include_missing or hash mismatch
#   15 — l2_denominator_unclassified
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/config/gd-runtime-parity-manifest.json"
SECRET_SSOT="$ROOT/config/secret-scan-regexes.json"
L1_MR="$ROOT/mirrors/codex-chain/l1-binary"
# Codex migrated from npm (@openai/codex v0.130) to standalone binary (v0.136+).
# Detect the newest standalone release directory.
L1_RT_BASE="$HOME/.codex/packages/standalone/releases"
if [ -d "$L1_RT_BASE" ]; then
  L1_RT=$(ls -1td "$L1_RT_BASE"/*/  2>/dev/null | head -1 | sed 's|/$||')
else
  L1_RT="$HOME/.npm-global/lib/node_modules/@openai/codex"  # legacy fallback
fi
L2_RT="$HOME/.codex"

_sha256() { shasum -a 256 "$1" 2>/dev/null | awk '{print $1}' || true; }
_json()    { python3 -c "import json,sys; d=json.load(open('$1')); print(d$2)" 2>/dev/null; }

FAIL_CODE=0
L1_STATUS="READY"; L2_STATUS="READY"; L3_STATUS="READY"

echo "=== GD Codex Chain Release Status ==="
echo "manifest: $MANIFEST"
echo "secret_ssot: $SECRET_SSOT"
echo ""

# ── Verify manifest exists ────────────────────────────────────────────────
if [ ! -f "$MANIFEST" ]; then
  echo "FATAL: manifest missing — $MANIFEST"
  exit 11
fi
python3 -m json.tool "$MANIFEST" > /dev/null 2>&1 || { echo "FATAL: manifest invalid JSON"; exit 11; }

# ── Build secret scan regex from SSOT ─────────────────────────────────────
if [ ! -f "$SECRET_SSOT" ]; then
  echo "FATAL: secret scan SSOT missing — $SECRET_SSOT"
  exit 11
fi
# Extract all regexes into a single grep pattern
SECRET_PATTERN=$(python3 -c "
import json
d = json.load(open('$SECRET_SSOT'))
patterns = [p['regex'] for p in d.get('patterns', [])]
print('|'.join(patterns))
" 2>/dev/null)
if [ -z "$SECRET_PATTERN" ]; then
  echo "FATAL: SECRET_PATTERN is empty — SSOT parse failed or no patterns defined"
  exit 11
fi

# ── L3: strict parity (/gd command) ───────────────────────────────────────
echo "--- L3: /gd command (strict parity) ---"
if bash "$ROOT/tools/gd-parity-verify.sh" --bundle gd-command 2>/dev/null | grep -q '"status":"installed_parity_pass"'; then
  echo "  [PARITY] L3_RELEASE_STATUS: READY"
else
  echo "  [PARITY] L3_RELEASE_STATUS: BLOCKED (installed_runtime_drift)"
  L3_STATUS="BLOCKED"; FAIL_CODE=14
fi
echo ""

# ── L1: release mirror completeness ───────────────────────────────────────
echo "--- L1: Codex binary release mirror ---"
# Standalone binary layout: codex-package.json is the version lock file.
# bin/codex.js and bin/rg were npm artifacts — not present in standalone form.
L1_MUST=(
  "codex-package.json:codex-package.json"
)
L1_FAIL=0
for pair in "${L1_MUST[@]}"; do
  rt_rel="${pair%%:*}"; mr_rel="${pair##*:}"
  rt_hash=$(_sha256 "$L1_RT/$rt_rel")
  mr_hash=$(_sha256 "$L1_MR/$mr_rel")
  if [ -z "$rt_hash" ] || [ -z "$mr_hash" ]; then
    echo "  [RELEASE_MIRROR] MISSING: $rt_rel (runtime=$rt_hash mirror=$mr_hash)"
    L1_FAIL=1
  elif [ "$rt_hash" != "$mr_hash" ]; then
    echo "  [RELEASE_MIRROR] HASH_DRIFT: $rt_rel runtime≠mirror"
    L1_FAIL=1
  else
    echo "  [RELEASE_MIRROR] OK: $rt_rel (${rt_hash:0:16}...)"
  fi
done

# Secret scan L1 mirror files
if [ -n "$SECRET_PATTERN" ]; then
  L1_SECRETS=$(grep -rE "$SECRET_PATTERN" "$L1_MR/" 2>/dev/null | grep -v "<REDACTED>" || true)
  if [ -n "$L1_SECRETS" ]; then
    echo "  [RELEASE_MIRROR] SECRET_FOUND in L1 mirror — manual review required"
    L1_FAIL=1; FAIL_CODE=12
  else
    echo "  [RELEASE_MIRROR] secret_scan: PASS"
  fi
fi

if [ $L1_FAIL -eq 0 ]; then
  echo "  L1_RELEASE_STATUS: READY"
else
  echo "  L1_RELEASE_STATUS: BLOCKED"
  L1_STATUS="BLOCKED"
  [ $FAIL_CODE -eq 0 ] && FAIL_CODE=14
fi
echo ""

# ── L2: release mirror completeness ───────────────────────────────────────
echo "--- L2: Codex config/memories/skills/automations release mirror ---"
L2_FAIL=0

# Check L2 classified mirror dirs exist
L2_INCLUDE_DIRS=("l2-config" "l2-memories" "l2-system-skills" "l2-automations")
for d in "${L2_INCLUDE_DIRS[@]}"; do
  if [ ! -d "$ROOT/mirrors/codex-chain/$d" ]; then
    echo "  [RELEASE_MIRROR] MISSING_MIRROR_DIR: $d"
    L2_FAIL=1
  else
    count=$(find "$ROOT/mirrors/codex-chain/$d" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "  [RELEASE_MIRROR] OK: $d ($count files)"
  fi
done

# Check L2 runtime top-level entries are ALL classified (no unclassified)
# We know the expected classification from the manifest (18 top-level files + directories)
L2_KNOWN_ENTRIES=(
  ".codex-global-state.json" ".codex-global-state.json.bak" ".personality_migration"
  "AGENTS.md" "auth.json" "cloud-requirements-cache.json" "config.toml"
  "history.jsonl" "installation_id" "logs_2.sqlite" "logs_2.sqlite-shm"
  "logs_2.sqlite-wal" "models_cache.json" "session_index.jsonl"
  "state_5.sqlite" "state_5.sqlite-shm" "state_5.sqlite-wal" "version.json"
  "ambient-suggestions" "archived_sessions" "automations" "cache"
  "computer-use" "log" "memories" "pets" "plugins" "rules"
  "sessions" "shell_snapshots" "skills" "sqlite" "tmp" ".tmp" "vendor_imports"
  ".stignore" "browser" "goals_1.sqlite" "goals_1.sqlite-shm"
  "goals_1.sqlite-wal" "node_repl"
  # Added 2026-06-04: new runtime ephemera (standalone binary migration + codex updates)
  "packages" "process_manager"
  "chrome-native-hosts-v2.json" "chrome-native-hosts.json"
  "memories_1.sqlite" "memories_1.sqlite-shm" "memories_1.sqlite-wal"
)
L2_UNCLASSIFIED=()
while IFS= read -r entry; do
  name=$(basename "$entry")
  found=0
  for known in "${L2_KNOWN_ENTRIES[@]}"; do
    [ "$known" = "$name" ] && { found=1; break; }
  done
  # Also match known prefix patterns for ephemeral files with UUID suffixes
  if [ $found -eq 0 ]; then
    case "$name" in
      .codex-global-state.json.tmp-*)  found=1 ;;  # transient state write (single dot prefix)
      ..codex-global-state.json.tmp-*) found=1 ;;  # transient state write (double dot prefix variant)
    esac
  fi
  [ $found -eq 0 ] && L2_UNCLASSIFIED+=("$name")
done < <(find "$L2_RT" -maxdepth 1 -mindepth 1 2>/dev/null | sort)

if [ ${#L2_UNCLASSIFIED[@]} -gt 0 ]; then
  echo "  [RELEASE_MIRROR] UNCLASSIFIED_TOP_LEVEL: ${L2_UNCLASSIFIED[*]}"
  L2_FAIL=1; FAIL_CODE=15
else
  echo "  [RELEASE_MIRROR] denominator: all top-level entries classified"
fi

# Secret scan L2 mirror files
if [ -n "$SECRET_PATTERN" ]; then
  L2_SECRETS=$(grep -rE "$SECRET_PATTERN" \
    "$ROOT/mirrors/codex-chain/l2-config/" \
    "$ROOT/mirrors/codex-chain/l2-memories/" \
    "$ROOT/mirrors/codex-chain/l2-system-skills/" \
    "$ROOT/mirrors/codex-chain/l2-automations/" 2>/dev/null \
    | grep -v "<REDACTED>" || true)
  if [ -n "$L2_SECRETS" ]; then
    echo "  [RELEASE_MIRROR] SECRET_FOUND in L2 mirror — manual review required"
    L2_FAIL=1; [ $FAIL_CODE -lt 12 ] && FAIL_CODE=12
  else
    echo "  [RELEASE_MIRROR] secret_scan: PASS"
  fi
fi

# Manifest/sync drift check: known-EXCLUDE files must NOT appear in mirror
# If they do, the sync script's actual behavior contradicts the manifest classification.
# Excluded files that must never appear in mirror
EXCLUDE_SENTINEL_FILES=("history.jsonl" "auth.json" "session_index.jsonl")
# Manifest-only files: metadata allowed in sync-manifest.json, but full content must NOT be in l2-config
MANIFEST_ONLY_FILES=(".codex-global-state.json" "models_cache.json" "cloud-requirements-cache.json")
DRIFT_FOUND=()
for sentinel in "${EXCLUDE_SENTINEL_FILES[@]}"; do
  if [ -f "$ROOT/mirrors/codex-chain/l2-config/$sentinel" ]; then
    DRIFT_FOUND+=("$sentinel in l2-config (manifest=EXCLUDE, sync included it)")
  fi
done
for mf in "${MANIFEST_ONLY_FILES[@]}"; do
  if [ -f "$ROOT/mirrors/codex-chain/l2-config/$mf" ]; then
    DRIFT_FOUND+=("$mf in l2-config (manifest=MANIFEST_ONLY, full content must not be committed)")
  fi
done
if [ ${#DRIFT_FOUND[@]} -gt 0 ]; then
  echo "  [RELEASE_MIRROR] MANIFEST_SYNC_DRIFT: ${DRIFT_FOUND[*]}"
  L2_FAIL=1
  FAIL_CODE=11
fi

# Check sync-manifest.json exists (proves --apply was run)
if [ ! -f "$ROOT/mirrors/codex-chain/sync-manifest.json" ]; then
  echo "  [RELEASE_MIRROR] MISSING: sync-manifest.json — run bin/gd-sync-codex-chain.sh --apply first"
  L2_FAIL=1; [ $FAIL_CODE -eq 0 ] && FAIL_CODE=10
fi

if [ $L2_FAIL -eq 0 ]; then
  echo "  L2_RELEASE_STATUS: READY"
else
  echo "  L2_RELEASE_STATUS: BLOCKED"
  L2_STATUS="BLOCKED"
fi
echo ""

# ── Check for untracked release files ──────────────────────────────────────
echo "--- Git untracked release files check ---"
cd "$ROOT"
# Scope includes commands/ docs/ results/release-evidence/ in addition to core dirs
UNTRACKED=$(git ls-files --others --exclude-standard \
  mirrors/codex-chain config scripts fixtures plans commands docs results/release-evidence 2>/dev/null \
  | grep -v "__pycache__" | grep -v "\.pyc$" | grep -v "\.sqlite" | grep -v "\.wal$" | grep -v "\.shm$" \
  || true)
if [ -n "$UNTRACKED" ]; then
  echo "  UNTRACKED_RELEASE_FILES:"
  echo "$UNTRACKED" | while read -r f; do echo "    $f"; done
  [ $FAIL_CODE -eq 0 ] && FAIL_CODE=13
else
  echo "  untracked_release_files: none"
fi

# ── Check for MM/AM state: staged + unstaged changes on same tracked file ────
echo "--- MM state check (staged + unstaged on same file) ---"
MM_FILES=$(git status --short mirrors/codex-chain config scripts fixtures plans commands docs bin results/release-evidence 2>/dev/null \
  | grep -E "^MM|^AM" | awk '{print $2}' || true)
if [ -n "$MM_FILES" ]; then
  echo "  MM_STATE_FILES (staged changes with uncommitted working-tree modifications):"
  echo "$MM_FILES" | while read -r f; do echo "    $f"; done
  echo "  Fix: stage the working-tree changes before release."
  [ $FAIL_CODE -eq 0 ] && FAIL_CODE=13
else
  echo "  mm_state: clean (no staged+unstaged conflicts)"
fi

# ── Check for unstaged tracked release files (' M' or ' D' state) ────────────
echo "--- Unstaged tracked release files check ---"
# git diff --name-only lists tracked files with working-tree changes not in index
UNSTAGED=$(git diff --name-only \
  mirrors/codex-chain config scripts fixtures plans commands docs bin results/release-evidence 2>/dev/null \
  | grep -v "\.pyc$" | grep -v "__pycache__" || true)
if [ -n "$UNSTAGED" ]; then
  echo "  UNSTAGED_TRACKED_RELEASE_FILES (tracked but not staged — will not be committed as-is):"
  echo "$UNSTAGED" | while read -r f; do echo "    $f"; done
  echo "  Fix: stage these files (git add) before release."
  [ $FAIL_CODE -eq 0 ] && FAIL_CODE=13
else
  echo "  unstaged_tracked: clean (all tracked release files are staged or unmodified)"
fi
echo ""

# ── review2_command parity status ──────────────────────────────────────────
R2_OUT=$(bash "$ROOT/tools/gd-parity-verify.sh" --bundle review2_command 2>/dev/null || true)
R2_STATUS=$(echo "$R2_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")
case "$R2_STATUS" in
  installed_parity_pass)
    echo "--- review2_command parity (installed, hash verified) ---"
    R2_SHA=$(echo "$R2_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('sha256','?'))" 2>/dev/null || echo "?")
    echo "  [PARITY] review2_command: INSTALLED_PASS (sha256=${R2_SHA:0:16}...)"
    ;;
  runtime_missing)
    echo "--- review2_command parity (source ready, not yet installed) ---"
    echo "  [PARITY] review2_command: SOURCE_READY_INSTALL_BLOCKED (use install-review-route-command.sh --route review2 --apply when authorized)"
    ;;
  installed_runtime_drift)
    echo "--- review2_command parity (DRIFT DETECTED) ---"
    echo "  [PARITY] review2_command: DRIFT_DETECTED — installed copy differs from source; re-run installer"
    [ $FAIL_CODE -eq 0 ] && FAIL_CODE=14
    ;;
  *)
    echo "--- review2_command parity (unknown state) ---"
    echo "  [PARITY] review2_command: UNKNOWN ($R2_STATUS)"
    ;;
esac
echo ""

# ── Summary ────────────────────────────────────────────────────────────────
echo "=== Release Gate Summary ==="
echo "  L1_RELEASE_STATUS: $L1_STATUS  [RELEASE_MIRROR]"
echo "  L2_RELEASE_STATUS: $L2_STATUS  [RELEASE_MIRROR]"
echo "  L3_RELEASE_STATUS: $L3_STATUS  [PARITY]"
echo ""

if [ "$L1_STATUS" = "READY" ] && [ "$L2_STATUS" = "READY" ] && [ "$L3_STATUS" = "READY" ] && [ $FAIL_CODE -eq 0 ]; then
  echo "OVERALL_RELEASE_STATUS: READY_FOR_COMMIT"
  exit 0
else
  echo "OVERALL_RELEASE_STATUS: BLOCKED (exit_code=$FAIL_CODE)"
  exit $FAIL_CODE
fi
