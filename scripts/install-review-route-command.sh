#!/usr/bin/env bash
# install-review-route-command.sh — Install /review2 command source to runtime.
#
# Defaults to dry-run. Live install requires --apply AND a matching ledger entry
# in baselines/gd-v7-runtime-write-authorizations.jsonl.
#
# Usage:
#   bash scripts/install-review-route-command.sh --route review2 --dry-run
#   bash scripts/install-review-route-command.sh --route review2 --apply --ledger baselines/...
#
# Exit codes:
#   0 — success (dry-run: plan printed; apply: file written and hash verified)
#   1 — failure (ledger missing, hash mismatch, source missing)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROUTE=""
APPLY=0
DRY_RUN_EXPLICIT=0
LEDGER="$ROOT/baselines/gd-v7-runtime-write-authorizations.jsonl"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --route)    ROUTE="$2"; shift 2 ;;
    --apply)    APPLY=1; shift ;;
    --dry-run)  DRY_RUN_EXPLICIT=1; shift ;;  # explicit dry-run flag (default behavior)
    --ledger)   LEDGER="$2"; shift 2 ;;
    --dry-target) DRY_TARGET="$2"; shift 2 ;;  # for testing only
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

[ -z "$ROUTE" ] && { echo "usage: $0 --route <route> [--apply] [--ledger <path>]"; exit 1; }
DRY_TARGET="${DRY_TARGET:-}"

SOURCE_FILE="$ROOT/commands/${ROUTE}.md"
if [ "$ROUTE" = "review2" ]; then
  RUNTIME_PATH="/Users/praise/.claude/commands/review2.md"
  SCOPE="install_claude_command"
elif [ "$ROUTE" = "review1" ]; then
  RUNTIME_PATH="/Users/praise/.claude/commands/review1.md"
  SCOPE="install_claude_command"
else
  echo "unsupported route: $ROUTE" >&2; exit 1
fi

# Use DRY_TARGET for testing (avoids writing to real runtime)
TARGET="$RUNTIME_PATH"
if [ -n "$DRY_TARGET" ]; then
  TARGET="$DRY_TARGET"
fi

echo "=== Install Review Route Command ==="
echo "route:   $ROUTE"
echo "source:  $SOURCE_FILE"
echo "target:  $TARGET"
echo "apply:   $APPLY"
echo ""

# Source must exist
if [ ! -f "$SOURCE_FILE" ]; then
  echo "INSTALL_FAIL: source not found: $SOURCE_FILE"
  exit 1
fi

SOURCE_HASH=$(shasum -a 256 "$SOURCE_FILE" | awk '{print $1}')
echo "source_sha256: $SOURCE_HASH"

if [ "$APPLY" -eq 0 ]; then
  echo ""
  echo "DRY_RUN: would write to $TARGET"
  echo "INSTALL_STATUS: dry_run_only (pass --apply to execute)"
  exit 0
fi

# APPLY mode: verify ledger authorization
if [ ! -f "$LEDGER" ]; then
  echo "INSTALL_FAIL: ledger not found: $LEDGER"
  echo "  Add an authorization entry before running --apply"
  exit 1
fi

LEDGER_ENTRY=$(python3 -c "
import json, sys
REQUIRED_FIELDS = {'target_path', 'scope', 'granted_by', 'plan_ref', 'rationale'}
ledger = '$LEDGER'
target = '$TARGET'
scope = '$SCOPE'
try:
    with open(ledger) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if e.get('target_path') == target and e.get('scope') == scope:
                    # Validate all required fields present and non-empty
                    missing = [k for k in REQUIRED_FIELDS if not e.get(k)]
                    if missing:
                        print(f'incomplete:{{\",\".join(missing)}}')
                    else:
                        print('authorized')
                    sys.exit(0)
            except json.JSONDecodeError:
                pass
    print('not_found')
except Exception as ex:
    print(f'error:{ex}')
" 2>/dev/null)

case "$LEDGER_ENTRY" in
  authorized)
    : # OK, proceed
    ;;
  not_found)
    echo "INSTALL_FAIL: no matching ledger entry"
    echo "  target_path: $TARGET"
    echo "  scope: $SCOPE"
    echo "  Add to $LEDGER before --apply (must include target_path/scope/granted_by/plan_ref/rationale)"
    exit 1
    ;;
  incomplete:*)
    echo "INSTALL_FAIL: ledger entry found but missing required fields: ${LEDGER_ENTRY#incomplete:}"
    echo "  Required: target_path, scope, granted_by, plan_ref, rationale"
    exit 1
    ;;
  *)
    echo "INSTALL_FAIL: ledger check error: $LEDGER_ENTRY"
    exit 1
    ;;
esac

# Record hash before
TARGET_HASH_BEFORE="MISSING"
if [ -f "$TARGET" ]; then
  TARGET_HASH_BEFORE=$(shasum -a 256 "$TARGET" | awk '{print $1}')
fi

# Write
cp "$SOURCE_FILE" "$TARGET"
TARGET_HASH_AFTER=$(shasum -a 256 "$TARGET" | awk '{print $1}')

if [ "$SOURCE_HASH" != "$TARGET_HASH_AFTER" ]; then
  echo "INSTALL_FAIL: hash mismatch after copy"
  exit 1
fi

echo "INSTALL_STATUS: installed"
echo "target_hash_before: $TARGET_HASH_BEFORE"
echo "target_hash_after:  $TARGET_HASH_AFTER"
echo "source_sha256:      $SOURCE_HASH"
