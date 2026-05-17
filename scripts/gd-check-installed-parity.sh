#!/usr/bin/env bash
# Check that installed ~/.claude/commands/gd.md matches Project GD main root.
set -euo pipefail

MAIN="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$MAIN/commands/gd.md"
DST="$HOME/.claude/commands/gd.md"

src_hash=$(md5 -q "$SRC" 2>/dev/null || echo "MISSING")
dst_hash=$(md5 -q "$DST" 2>/dev/null || echo "MISSING")

echo "main_hash:      $src_hash"
echo "installed_hash: $dst_hash"

if [ "$src_hash" = "$dst_hash" ]; then
  echo "INSTALLED_PARITY_PASS"
  exit 0
else
  echo "INSTALLED_PARITY_DRIFT — run scripts/gd-install-rev21-for-handtest.sh to fix"
  exit 1
fi
