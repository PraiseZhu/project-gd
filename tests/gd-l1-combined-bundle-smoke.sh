#!/usr/bin/env bash
# gd-l1-combined-bundle-smoke.sh
# SC-W2-1: Verify combined kind capsule is ≤ 30720 bytes (L1 externalization active).
set -euo pipefail
MAIN="$(cd "$(dirname "$0")/.." && pwd)"
cd "$MAIN"

TARGET="plans/gd/2026-05-19-review-chain-hardening/master-plan.md"
if [ ! -f "$TARGET" ]; then
  echo "TARGET_MISSING: $TARGET" >&2
  exit 1
fi

OUT=$(mktemp "${TMPDIR:-/var/tmp}/gd-combined-smoke-XXXXXX.json")
trap 'rm -f "$OUT"' EXIT

python3 scripts/gd-codex-bridge-review.py build-capsule \
  --kind combined --target "$TARGET" --cwd . --out "$OUT" > /dev/null 2>&1

SIZE=$(wc -c < "$OUT")
echo "capsule_size=$SIZE"
if [ "$SIZE" -le 30720 ]; then
  echo "SMOKE_RESULT: PASS (capsule=${SIZE}B ≤ 30720B)"
  exit 0
else
  echo "SMOKE_RESULT: FAIL (capsule=${SIZE}B > 30720B)" >&2
  exit 1
fi
