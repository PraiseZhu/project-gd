#!/usr/bin/env bash
# Install Project GD rev21 command to ~/.claude/commands/gd.md.
# Verifies source parity before install; outputs INSTALLED_PARITY_PASS when done.
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$MAIN/commands/gd.md"
DST="$HOME/.claude/commands/gd.md"

echo "=== GD Install rev21 for handtest ==="
echo "source: $SRC"
echo "target: $DST"

if [ ! -f "$SRC" ]; then
  echo "ERROR: source not found: $SRC"
  exit 1
fi

src_hash=$(md5 -q "$SRC")
dst_hash=$(md5 -q "$DST" 2>/dev/null || echo "NONE")

if [ "$src_hash" = "$dst_hash" ]; then
  echo "INSTALLED_PARITY_PASS (already at $src_hash, no-op)"
  exit 0
fi

cp "$SRC" "$DST"
new_hash=$(md5 -q "$DST")

if [ "$src_hash" = "$new_hash" ]; then
  echo "INSTALLED_PARITY_PASS (installed $src_hash)"
else
  echo "ERROR: install succeeded but hash mismatch: src=$src_hash dst=$new_hash"
  exit 1
fi
