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

GD_PROJECT_ROOT="/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD"
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

# Check ledger for install_claude_command authorization (whitespace-flex JSONL parser)
# Canonical fields per Plan 1 baseline runtime_write_authorization.ledger_format:
#   ts / target_path / granted_by / scope / plan_ref / rationale
# We match by parsing each JSONL line and inspecting the `scope` field exactly.
# This is robust to minified vs spaced JSONL and to optional trailing whitespace.
LEDGER_OK="no"
if [[ -f "$LEDGER" ]]; then
  if python3 - "$LEDGER" <<'PYEOF' 2>/dev/null; then
import json, sys
ledger_path = sys.argv[1]
expected_scope = "install_claude_command"
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
            if obj.get("scope") == expected_scope and obj.get("target_path") == expected_target:
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
      else
        echo "INSTALL_STATUS: install_pending_authorization"
        echo "  Reason: $LEDGER 缺 scope=install_claude_command 记录"
      fi
      ;;
    present_parity_pass)
      echo "INSTALL_STATUS: installed_parity_pass"
      ;;
    present_parity_fail)
      echo "INSTALL_STATUS: install_blocked_hash_mismatch"
      echo "  Source hash: $SOURCE_HASH"
      echo "  Target hash: $TARGET_HASH"
      echo "  Reason: 目标已存在但 hash 不一致；不会自动覆盖。手动卸载或备份后重试。"
      ;;
  esac
  exit 0
fi

# ---------- Install mode ----------
# Lock 1: ledger
if [[ "$LEDGER_OK" != "yes" ]]; then
  echo "INSTALL_STATUS: install_pending_authorization"
  echo "ERROR: --install 但 ledger 无 scope=install_claude_command 授权记录" >&2
  echo "  Ledger: $LEDGER" >&2
  echo "  请用户先在对话中显式授权后追加 ledger 记录。" >&2
  exit 1
fi

# Lock 2: hash collision
if [[ "$TARGET_STATE" == "present_parity_fail" ]]; then
  echo "INSTALL_STATUS: install_blocked_hash_mismatch"
  echo "ERROR: $TARGET 已存在且 hash 与 source 不一致" >&2
  echo "  Source hash: $SOURCE_HASH" >&2
  echo "  Target hash: $TARGET_HASH" >&2
  echo "  请先 uninstall 或确认是否是用户手写文件。" >&2
  exit 1
fi

# Already installed and matching → no-op
if [[ "$TARGET_STATE" == "present_parity_pass" ]]; then
  echo "INSTALL_STATUS: installed_parity_pass"
  echo "  No-op: source 与 target hash 已一致"
  exit 0
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
