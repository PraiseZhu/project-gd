#!/usr/bin/env bash
# gd-bundle-completeness.sh — Blocking bundle completeness check for the GD plugin.
#
# Verifies that all eight runtime-referenced bundle target categories exist and are
# non-empty, including the vendor/l3-transport transport stack (FR-003/FR-015/P3).
# Also asserts the P3-deprecated ~/.claude/commands install scripts are NOT bundled
# (two command-install models must not coexist — P3).
#
# stdlib-only bash, macOS bash 3.2 compatible (no associative arrays, no ${var^^}).
#
# Usage:
#   bash scripts/gd-bundle-completeness.sh --check   # exit 0 if complete, exit≠0 + list missing
#
# Exit codes:
#   0 — bundle complete (eight categories present); P3-deprecated scripts, if any,
#       reported as a warning only (their removal is track-a packaging's job).
#   1 — usage error
#   2 — one or more required targets missing (blocking)
#   3 — --strict-p3 set AND a P3-deprecated install script is present in the bundle
#
# P3 rationale: the deprecated ~/.claude/commands install scripts live in the repo
# working tree but are excluded from the actual plugin payload by the packaging
# manifest (track-a). Default --check reports their presence (visible, not silent)
# without failing completeness; --strict-p3 turns the report into a hard gate for
# release packaging verification.

set -euo pipefail

# Bundle root = repo/plugin root (this script lives in <root>/scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MODE=""
STRICT_P3=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE="check"; shift ;;
    --strict-p3) STRICT_P3=1; shift ;;
    -h|--help)
      echo "Usage: gd-bundle-completeness.sh --check [--strict-p3]"
      exit 0
      ;;
    *) echo "[bundle] ✗ unknown arg: $1" >&2; echo "Usage: gd-bundle-completeness.sh --check [--strict-p3]" >&2; exit 1 ;;
  esac
done

if [[ "$MODE" != "check" ]]; then
  echo "[bundle] ✗ missing --check" >&2
  echo "Usage: gd-bundle-completeness.sh --check [--strict-p3]" >&2
  exit 1
fi

MISSING=""
add_missing() { MISSING="${MISSING}  - $1"$'\n'; }

# A directory target: must exist AND contain at least one entry.
require_nonempty_dir() {
  local rel="$1"
  local abs="$BUNDLE_ROOT/$rel"
  if [[ ! -d "$abs" ]]; then
    add_missing "dir 缺失: $rel"
  elif [[ -z "$(ls -A "$abs" 2>/dev/null)" ]]; then
    add_missing "dir 为空: $rel"
  fi
}

# A file target: must exist and be a regular file.
require_file() {
  local rel="$1"
  local abs="$BUNDLE_ROOT/$rel"
  if [[ ! -f "$abs" ]]; then
    add_missing "file 缺失: $rel"
  fi
}

# ── 八类 bundle 目标（FR-003）──
require_nonempty_dir "commands"
require_file "commands/gd.md"
require_file "commands/review1.md"
require_file "commands/review2.md"
require_file "commands/setup.md"

# ── 插件清单（plugin.json 丢失 → claude plugin install 完全失败）──
require_file ".claude-plugin/plugin.json"
require_file ".claude-plugin/marketplace.json"

require_nonempty_dir "scripts"
require_nonempty_dir "scripts/lib"

require_nonempty_dir "prompts"
require_nonempty_dir "templates"
require_nonempty_dir "schema"
require_nonempty_dir "docs"
require_nonempty_dir "fixtures"

# ── vendor/l3-transport 传输栈（FR-015；漏掉则三链路 cross-review 全 fail-closed）──
require_nonempty_dir "vendor/l3-transport"
require_file "vendor/l3-transport/scripts/codex-consult.sh"
require_file "vendor/l3-transport/scripts/review-result-writer.sh"
require_file "vendor/l3-transport/scripts/install-transport.sh"
require_file "vendor/l3-transport/handoff/bin/codex-send-wait"
require_file "vendor/l3-transport/handoff/lib/state-paths.sh"

# launchagents 下至少一个 plist
LAUNCHAGENTS_DIR="$BUNDLE_ROOT/vendor/l3-transport/launchagents"
if [[ ! -d "$LAUNCHAGENTS_DIR" ]]; then
  add_missing "dir 缺失: vendor/l3-transport/launchagents"
else
  plist_count=$(find "$LAUNCHAGENTS_DIR" -maxdepth 1 -name '*.plist' -type f 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$plist_count" -eq 0 ]]; then
    add_missing "vendor/l3-transport/launchagents 下无 .plist"
  fi
fi

# ── P3 违规：作废的命令安装脚本不得进 bundle ──
P3_VIOLATION=""
for dep in \
  "scripts/install-gd-command.sh" \
  "scripts/uninstall-gd-command.sh" \
  "scripts/install-review-route-command.sh" \
  "scripts/check-gd-command-parity.sh" \
  "tools/check-gd-command-parity.sh" \
; do
  if [[ -f "$BUNDLE_ROOT/$dep" ]]; then
    P3_VIOLATION="${P3_VIOLATION}  - P3 作废脚本仍在 bundle: $dep"$'\n'
  fi
done

# ── 结果 ──
status=0

if [[ -n "$MISSING" ]]; then
  echo "[bundle] ✗ INCOMPLETE — 缺失 bundle 目标:" >&2
  printf '%s' "$MISSING" >&2
  status=2
fi

if [[ -n "$P3_VIOLATION" ]]; then
  if [[ $STRICT_P3 -eq 1 ]]; then
    echo "[bundle] ✗ P3 — 作废命令安装脚本不得打包（两套命令安装并存禁止）:" >&2
    printf '%s' "$P3_VIOLATION" >&2
    # P3 hard gate only under --strict-p3, and only if completeness already passed.
    if [[ $status -eq 0 ]]; then
      status=3
    fi
  else
    echo "[bundle] ⚠ P3 警告 — 以下作废脚本在工作树中，须由 track-a 打包清单排除，不进插件 payload:" >&2
    printf '%s' "$P3_VIOLATION" >&2
  fi
fi

if [[ $status -eq 0 ]]; then
  echo "[bundle] ✓ COMPLETE — 八类 bundle 目标齐全（含 vendor/l3-transport）"
fi

exit $status
