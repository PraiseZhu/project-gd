#!/usr/bin/env bash
# SC-18: deep e2e tree guard — verify deep run doesn't pollute work tree
# and writer hash matches manifest.writer_expected_hash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RESULTS_DIR="plans/gd/2026-06-13-codex-deep-review/results"
MANIFEST="fixtures/deep-review/writer-runtime-manifest.json"
WRITER_PATH="$PROJECT_ROOT/vendor/l3-transport/scripts/review-result-writer.sh"

# Snapshot before
BEFORE_STATUS=$(git status --porcelain 2>&1 | grep -v "^?? ${RESULTS_DIR}/" || true)
BEFORE_DIFF=$(git diff --exit-code HEAD 2>&1 || true)

# Verify writer hash matches expected
EXPECTED_HASH=$(python3 -c "import json; m=json.load(open('${MANIFEST}')); print(m.get('writer_expected_hash',''))")
ACTUAL_HASH=$(shasum -a 256 "$WRITER_PATH" | awk '{print $1}')
if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
  echo "SC-18 FAIL: writer hash mismatch: $ACTUAL_HASH != $EXPECTED_HASH"
  exit 1
fi

# Writer backup check — SUPERSEDED: writer now runs from vendor (run-in-place),
# no longer deployed to ~/.claude/scripts/ with a .deep-review-backup. Skip backup.
# BACKUP_PATH=$(python3 -c "import json, os; m=json.load(open('${MANIFEST}')); print(os.path.expanduser(m.get('writer_backup_path','')))")
# if [ ! -f "$BACKUP_PATH" ]; then
#   echo "SC-18 FAIL: writer backup missing: $BACKUP_PATH"
#   exit 1
# fi

# Snapshot after (nothing should have changed — no e2e run in SC-18 scope)
AFTER_STATUS=$(git status --porcelain 2>&1 | grep -v "^?? ${RESULTS_DIR}/" || true)
AFTER_DIFF=$(git diff --exit-code HEAD 2>&1 || true)

if [ "$BEFORE_STATUS" != "$AFTER_STATUS" ] || [ "$BEFORE_DIFF" != "$AFTER_DIFF" ]; then
  echo "SC-18 FAIL: work tree changed between before/after snapshots"
  echo "Before status: $BEFORE_STATUS"
  echo "After status: $AFTER_STATUS"
  exit 1
fi

echo "SC-18 PASS: tree clean, writer hash matches (backup check superseded — writer runs from vendor)"
echo "  writer_expected_hash: $EXPECTED_HASH"
echo "  writer_path: $WRITER_PATH"
