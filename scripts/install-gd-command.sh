#!/usr/bin/env bash
# install-gd-command.sh — 双锁安装 /gd Claude command
#
# 锁 1：默认无参数 = 仅检查模式（exit 0），不写任何文件
# 锁 2：--install + ledger 含 install_claude_command 授权记录 → 才写
#
# 任一锁未通过 → fail-closed，不写 runtime
#
# Output:
#   INSTALL_STATUS: <not_installed | install_pending_authorization | installed_parity_pass | install_blocked_hash_mismatch | installed_now>
#   exit 0 = check 完成（不论 install 是否发生）
#   exit 1 = --install 时缺授权 / hash 冲突 / 写入失败

set -euo pipefail

# Resolve source root from the script's own location so that worktree invocations
# use the worktree's own commands/gd.md, not the main-repo copy.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GD_PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE="${GD_PROJECT_ROOT}/commands/gd.md"
TARGET="/Users/praise/.claude/commands/gd.md"
LEDGER="${GD_PROJECT_ROOT}/baselines/gd-v7-runtime-write-authorizations.jsonl"

MODE="check"
if [[ "${1:-}" == "--install" ]]; then
  MODE="install"
fi

# Source must exist
if [[ ! -f "$SOURCE" ]]; then
  echo "INSTALL_STATUS: source_missing"
  echo "ERROR: source not found: $SOURCE" >&2
  exit 1
fi

SOURCE_HASH=$(shasum -a 256 "$SOURCE" | awk '{print $1}')

# Check ledger for install_claude_command authorization bound to CURRENT source hash.
# Canonical fields: ts / target_path / granted_by / scope / plan_ref / new_source_hash
#
# REVISION BINDING (Plan A P1): Authorization must carry new_source_hash == SOURCE_HASH.
# Entries without new_source_hash (pre-Plan-A legacy) or with a different hash do NOT match.
# This prevents old authorizations from rev<19 from authorizing a rev=19 install.
LEDGER_OK="no"
if [[ -f "$LEDGER" ]]; then
  if python3 - "$LEDGER" "$SOURCE_HASH" <<'PYEOF' 2>/dev/null; then
import json, sys
ledger_path = sys.argv[1]
source_hash  = sys.argv[2]          # current worktree source hash — must match
expected_scope  = "install_claude_command"
expected_target = "/Users/praise/.claude/commands/gd.md"
try:
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (obj.get("scope") == expected_scope
                    and obj.get("target_path") == expected_target
                    and obj.get("new_source_hash") == source_hash):
                sys.exit(0)
    sys.exit(1)
except FileNotFoundError:
    sys.exit(1)
PYEOF
    LEDGER_OK="yes"
  fi
fi

# Inspect target state
TARGET_STATE="absent"
TARGET_HASH=""
if [[ -f "$TARGET" ]]; then
  TARGET_HASH=$(shasum -a 256 "$TARGET" | awk '{print $1}')
  if [[ "$TARGET_HASH" == "$SOURCE_HASH" ]]; then
    TARGET_STATE="present_parity_pass"
  else
    TARGET_STATE="present_parity_fail"
  fi
fi

# ---------- Check mode ----------
if [[ "$MODE" == "check" ]]; then
  case "$TARGET_STATE" in
    absent)
      if [[ "$LEDGER_OK" == "yes" ]]; then
        echo "INSTALL_STATUS: ready_to_install"
        echo "  Rev19-bound authorization found in ledger."
      else
        echo "INSTALL_STATUS: install_pending_authorization"
        echo "  Reason: ledger 无 scope=install_claude_command + new_source_hash=$SOURCE_HASH 条目"
        echo "  Required: 用户在对话中显式授权并追加 ledger 记录，new_source_hash 必须为当前 source hash"
      fi
      ;;
    present_parity_pass)
      echo "INSTALL_STATUS: installed_parity_pass"
      ;;
    present_parity_fail)
      if [[ "$LEDGER_OK" == "yes" ]]; then
        echo "INSTALL_STATUS: INSTALL_BLOCKED_HASH_MISMATCH / BACKUP_AUTHORIZED"
        echo "  Rev19-bound auth found; --install will backup existing target then overwrite."
        echo "  Source hash: $SOURCE_HASH"
        echo "  Target hash: $TARGET_HASH"
      else
        echo "INSTALL_STATUS: INSTALL_BLOCKED_HASH_MISMATCH / NEEDS_EXPLICIT_BACKUP_OVERWRITE_AUTH"
        echo "  Installed gd.md (rev<19) differs from source (rev=19)."
        echo "  Source hash: $SOURCE_HASH"
        echo "  Target hash: $TARGET_HASH"
        echo "  Required: 1) add ledger entry with new_source_hash=$SOURCE_HASH; 2) run --install to backup+overwrite"
      fi
      ;;
  esac
  exit 0
fi

# ---------- Install mode ----------
# Lock 1: rev19-bound ledger authorization (new_source_hash must match current source)
if [[ "$LEDGER_OK" != "yes" ]]; then
  echo "INSTALL_STATUS: install_pending_authorization"
  echo "ERROR: --install 但 ledger 无 rev19-bound 授权记录" >&2
  echo "  Required: scope=install_claude_command + new_source_hash=$SOURCE_HASH" >&2
  echo "  Ledger: $LEDGER" >&2
  exit 1
fi

# Already installed and matching → no-op
if [[ "$TARGET_STATE" == "present_parity_pass" ]]; then
  echo "INSTALL_STATUS: installed_parity_pass"
  echo "  No-op: source 与 target hash 已一致"
  exit 0
fi

# Hash mismatch: backup existing installed file before overwrite (Plan A A3/B5)
# No longer a hard block — backup ensures the old file is preserved.
if [[ "$TARGET_STATE" == "present_parity_fail" ]]; then
  BACKUP_DIR="${GD_PROJECT_ROOT}/reports/_selftest_runtime_evidence/installed-backup"
  mkdir -p "$BACKUP_DIR"
  BACKUP_TS=$(date +%Y%m%dT%H%M%S)
  BACKUP_FILE="${BACKUP_DIR}/gd.md.installed-pre-rev19-${BACKUP_TS}"
  cp "$TARGET" "$BACKUP_FILE"
  echo "BACKUP_CREATED: $BACKUP_FILE"
  echo "  Backed up hash: $TARGET_HASH"
fi

# Atomic write: cp to tempfile in same dir, then mv
TARGET_DIR=$(dirname "$TARGET")
mkdir -p "$TARGET_DIR"
TMPFILE=$(mktemp "${TARGET_DIR}/.gd-install.XXXXXX")
trap 'rm -f "$TMPFILE"' EXIT

cp "$SOURCE" "$TMPFILE"
mv "$TMPFILE" "$TARGET"
trap - EXIT

# Verify post-install
INSTALLED_HASH=$(shasum -a 256 "$TARGET" | awk '{print $1}')
if [[ "$INSTALLED_HASH" != "$SOURCE_HASH" ]]; then
  echo "INSTALL_STATUS: install_failed_hash_mismatch_after_write"
  echo "ERROR: 写入后 hash 不匹配（$INSTALLED_HASH vs $SOURCE_HASH）" >&2
  exit 1
fi

echo "INSTALL_STATUS: installed_now"
echo "  Source: $SOURCE"
echo "  Target: $TARGET"
echo "  Hash: $INSTALLED_HASH"
exit 0
