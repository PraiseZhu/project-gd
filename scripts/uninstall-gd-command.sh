#!/usr/bin/env bash
# uninstall-gd-command.sh — hash-safe 卸载 /gd Claude command
#
# 安全约束：只删除 hash 与 Project GD source 一致的 installed 文件
# 防止误删用户手写的同名 /gd command 文件
#
# Output:
#   UNINSTALL_STATUS: <not_installed | uninstalled | blocked_hash_mismatch | source_missing>
#   exit 0 = 检查或卸载完成
#   exit 1 = hash 冲突拒绝删除 / source 缺失

set -euo pipefail

GD_PROJECT_ROOT="/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD"
SOURCE="${GD_PROJECT_ROOT}/commands/gd.md"
TARGET="/Users/praise/.claude/commands/gd.md"

if [[ ! -f "$TARGET" ]]; then
  echo "UNINSTALL_STATUS: not_installed"
  echo "  Target $TARGET 不存在，无需操作"
  exit 0
fi

if [[ ! -f "$SOURCE" ]]; then
  echo "UNINSTALL_STATUS: source_missing"
  echo "ERROR: 无法确定 source hash 进行 hash 校验：$SOURCE 不存在" >&2
  echo "  拒绝删除 $TARGET（无法验证它确实由 Project GD 安装）" >&2
  exit 1
fi

SOURCE_HASH=$(shasum -a 256 "$SOURCE" | awk '{print $1}')
TARGET_HASH=$(shasum -a 256 "$TARGET" | awk '{print $1}')

if [[ "$SOURCE_HASH" != "$TARGET_HASH" ]]; then
  echo "UNINSTALL_STATUS: blocked_hash_mismatch"
  echo "ERROR: 拒绝删除 — target hash 与 Project GD source 不一致" >&2
  echo "  Source hash: $SOURCE_HASH" >&2
  echo "  Target hash: $TARGET_HASH" >&2
  echo "  这可能是：(a) 用户手写的同名命令 (b) source 改了但 target 未同步 (c) 其他来源" >&2
  echo "  请先确认后手动处理。" >&2
  exit 1
fi

# Hash matches → safe to delete
rm -f "$TARGET"

echo "UNINSTALL_STATUS: uninstalled"
echo "  Removed: $TARGET"
echo "  Verified hash: $TARGET_HASH"
exit 0
