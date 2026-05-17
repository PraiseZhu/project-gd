#!/usr/bin/env bash
# check-gd-command-parity.sh — 检查 source 与 installed gd.md hash 一致性
#
# 三态输出：
#   INSTALL_STATUS: not_installed              → exit 0（未安装是合法状态）
#   INSTALL_STATUS: installed_parity_pass      → exit 0（已安装且一致）
#   INSTALL_STATUS: installed_parity_fail      → exit 1（已安装但不一致，需人工介入）
#
# 不修改任何文件（只读）

set -euo pipefail

GD_PROJECT_ROOT="/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD"
SOURCE="${GD_PROJECT_ROOT}/commands/gd.md"
TARGET="/Users/praise/.claude/commands/gd.md"

if [[ ! -f "$SOURCE" ]]; then
  echo "INSTALL_STATUS: source_missing"
  echo "ERROR: source 不存在: $SOURCE" >&2
  exit 1
fi

if [[ ! -f "$TARGET" ]]; then
  echo "INSTALL_STATUS: not_installed"
  exit 0
fi

SOURCE_HASH=$(shasum -a 256 "$SOURCE" | awk '{print $1}')
TARGET_HASH=$(shasum -a 256 "$TARGET" | awk '{print $1}')

if [[ "$SOURCE_HASH" == "$TARGET_HASH" ]]; then
  echo "INSTALL_STATUS: installed_parity_pass"
  echo "  Hash: $SOURCE_HASH"
  exit 0
else
  echo "INSTALL_STATUS: installed_parity_fail"
  echo "  Source hash: $SOURCE_HASH" >&2
  echo "  Target hash: $TARGET_HASH" >&2
  echo "  Source: $SOURCE" >&2
  echo "  Target: $TARGET" >&2
  exit 1
fi
