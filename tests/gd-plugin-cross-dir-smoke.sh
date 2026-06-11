#!/usr/bin/env bash
# gd-plugin-cross-dir-smoke.sh — Cross-directory portability + write-isolation smoke.
#
# Proves the GD plugin works for an INSTALLER on a non-GD project (constitution
# P1/FR-014), NOT by self-testing the GD repo's own dir. Spins up a temp non-GD
# git repo as ${CLAUDE_PROJECT_DIR}, points ${CLAUDE_PLUGIN_DATA} at a temp data
# dir, and REALLY invokes review-result-writer.sh through a fixture codex-send-wait
# stub — asserting real result/baseline files land under ${CLAUDE_PLUGIN_DATA}
# (test -f real files, NOT path echoes), never the plugin install dir.
#
# Modes:
#   (default)              happy path: fixture codex-send-wait → APPROVED → real product files
#   --no-codex             HANDOFF_BIN points at a missing stub → fail-closed + Chinese hint, no APPROVED
#   --assert-data-isolated assert product prefix ∈ {CLAUDE_PLUGIN_DATA, CLAUDE_PROJECT_DIR}, 0 hits on plugin root
#   --print-outdir         print the resolved product out-dir (for SC verify reuse)
#
# Exit codes: 0 = pass; 1 = fail (assertion or unexpected state).

set -euo pipefail

MODE="happy"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-codex) MODE="no-codex"; shift ;;
    --assert-data-isolated) MODE="assert-data-isolated"; shift ;;
    --print-outdir) MODE="print-outdir"; shift ;;
    -h|--help)
      echo "Usage: gd-plugin-cross-dir-smoke.sh [--no-codex|--assert-data-isolated|--print-outdir]"
      exit 0
      ;;
    *) echo "[smoke] ✗ unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ── Plugin root = this repo (the bundle). tests/ → root is parent. ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WRITER="$PLUGIN_ROOT/vendor/l3-transport/scripts/review-result-writer.sh"

if [[ ! -f "$WRITER" ]]; then
  echo "[smoke] ✗ writer not found: $WRITER" >&2
  exit 1
fi

# ── Temp sandbox: a NON-GD project dir + isolated plugin data + handoff bin ──
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/gd-smoke-XXXXXX")"
cleanup() { rm -rf "$SANDBOX"; }
trap cleanup EXIT

TARGET_PROJECT="$SANDBOX/target-project"   # the installer's OWN project (not GD)
PLUGIN_DATA="$SANDBOX/plugin-data"          # update-safe data dir
HANDOFF_BIN_DIR="$SANDBOX/handoff/bin"      # fixture transport bin
OUT_DIR="$PLUGIN_DATA/gd-review-baselines"  # product target (under CLAUDE_PLUGIN_DATA)

mkdir -p "$TARGET_PROJECT" "$PLUGIN_DATA" "$HANDOFF_BIN_DIR" "$OUT_DIR"

# Make TARGET_PROJECT a real git repo (non-GD) so target resolution is realistic.
git -C "$TARGET_PROJECT" init -q
git -C "$TARGET_PROJECT" config user.email "smoke@example.com"
git -C "$TARGET_PROJECT" config user.name "smoke"
echo "hello" > "$TARGET_PROJECT/README.md"
git -C "$TARGET_PROJECT" add -A
git -C "$TARGET_PROJECT" commit -q -m "init" || true

export CLAUDE_PROJECT_DIR="$TARGET_PROJECT"
export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
export CLAUDE_PLUGIN_DATA="$PLUGIN_DATA"

BASELINE_KEY="smoke$(date +%s)"

# ── Fixture codex-send-wait stub: emits a valid APPROVED raw result. ──
# Matches the writer's invocation: --cwd <dir> --mode review-only --payload-file <f> --timeout N
write_fixture_stub() {
  cat > "$HANDOFF_BIN_DIR/codex-send-wait" <<'STUB'
#!/usr/bin/env bash
# Fixture codex-send-wait — simulates a successful daemon round-trip with APPROVED.
# Emits a structurally-valid Plan Review Result (header / Scope Checked / Findings /
# Residual Risk) so review-result-writer.sh structure validation passes.
cat <<'RESULT'
# Plan Review Result

VERDICT: APPROVED
REVIEW_DOMAIN: ai_infra
REVIEW_MODE: single_pass
REVIEW_DELTA_SCOPE: full_matrix

## Scope Checked

| 检查面 | 结论 | 证据 |
|--------|------|------|
| portability | pass | fixture |

## Findings

(none)

## Residual Risk

none
RESULT
exit 0
STUB
  chmod +x "$HANDOFF_BIN_DIR/codex-send-wait"
}

# ── Build a minimal review capsule (plan kind). ──
CAPSULE="$SANDBOX/capsule.txt"
cat > "$CAPSULE" <<EOF
REVIEW_KIND: plan
REVIEW_DOMAIN: ai_infra
REVIEW_FOCUS: portability
PROJECT_ROOT: $TARGET_PROJECT
REPO_ROOT: $TARGET_PROJECT
BRANCH: main
SUCCESS_CRITERIA: cross-dir smoke
EOF

run_writer() {
  # HANDOFF_BIN drives where the writer looks for codex-send-wait (via state-paths.sh).
  HANDOFF_BIN="$HANDOFF_BIN_DIR" \
  bash "$WRITER" \
    --capsule-file "$CAPSULE" \
    --baseline-key "$BASELINE_KEY" \
    --review-kind plan \
    --out-dir "$OUT_DIR" \
    --cwd "$TARGET_PROJECT" \
    --no-stop-marker
}

fail() { echo "[smoke] ✗ FAIL — $1" >&2; exit 1; }

# Assert a real product file exists under OUT_DIR (test -f, not an echo).
assert_product_real() {
  local result_file baseline_file
  result_file=$(find "$OUT_DIR/$BASELINE_KEY" -maxdepth 1 -name 'result-*.md' -type f 2>/dev/null | head -1)
  baseline_file="$OUT_DIR/$BASELINE_KEY/latest-plan-baseline.json"
  [[ -n "$result_file" && -f "$result_file" ]] || fail "result-*.md 实文件未生成于 $OUT_DIR/$BASELINE_KEY"
  [[ -f "$baseline_file" ]] || fail "latest-plan-baseline.json 未生成于 $OUT_DIR/$BASELINE_KEY"
  grep -q 'VERDICT: APPROVED' "$result_file" || fail "result 文件不含 APPROVED 结论"
  echo "$result_file"
}

# Assert product paths fall under CLAUDE_PLUGIN_DATA / CLAUDE_PROJECT_DIR, never PLUGIN_ROOT.
assert_isolated() {
  local f
  # Every product file must be prefixed by PLUGIN_DATA (== OUT_DIR root here).
  while IFS= read -r f; do
    case "$f" in
      "$CLAUDE_PLUGIN_DATA"/*|"$CLAUDE_PROJECT_DIR"/*) : ;;
      *) fail "产物落在隔离区外: $f" ;;
    esac
    case "$f" in
      "$CLAUDE_PLUGIN_ROOT"/*) fail "产物命中插件安装目录: $f" ;;
    esac
  done < <(find "$OUT_DIR" -type f 2>/dev/null)
}

case "$MODE" in
  happy|print-outdir|assert-data-isolated)
    write_fixture_stub
    OUTPUT="$(run_writer 2>&1)" || fail "writer 退出非 0 (happy path)"
    # The writer must report APPROVED (real Codex round-trip simulated).
    echo "$OUTPUT" | grep -q 'APPROVED' || fail "writer 未报 APPROVED (happy path)"
    RESULT_FILE="$(assert_product_real)"

    if [[ "$MODE" == "assert-data-isolated" ]]; then
      assert_isolated
      echo "[smoke] ✓ data-isolated — 产物前缀 = CLAUDE_PLUGIN_DATA，0 命中插件安装目录"
      exit 0
    fi
    if [[ "$MODE" == "print-outdir" ]]; then
      echo "$OUT_DIR/$BASELINE_KEY"
      exit 0
    fi
    echo "[smoke] ✓ happy — 跨目录(非 GD repo) 真调 writer，APPROVED + 实产物落 $OUT_DIR/$BASELINE_KEY"
    # Guard: pass must NOT depend on $PWD/Project GD presence — product is in temp sandbox.
    case "$RESULT_FILE" in
      "$CLAUDE_PLUGIN_DATA"/*) : ;;
      *) fail "happy 产物不在 CLAUDE_PLUGIN_DATA 内（自检脱钩失败）" ;;
    esac
    exit 0
    ;;

  no-codex)
    # Point HANDOFF_BIN at a dir with NO codex-send-wait → transport unavailable.
    rm -f "$HANDOFF_BIN_DIR/codex-send-wait"
    OUTPUT="$(run_writer 2>&1)" || true   # writer may exit 0 with degraded status
    # Must NOT produce an APPROVED verdict.
    if echo "$OUTPUT" | grep -q 'APPROVED'; then
      fail "缺 codex 时仍出现 APPROVED（伪通过）"
    fi
    # Must emit a Chinese fail-closed hint.
    echo "$OUTPUT" | grep -q '缺 codex 传输栈' || fail "缺 codex 时未输出中文缺失提示"
    # Product area must contain no APPROVED verdict result file.
    if find "$OUT_DIR" -name 'result-*.md' -type f 2>/dev/null | xargs grep -l 'VERDICT: APPROVED' 2>/dev/null | grep -q .; then
      fail "产物区出现通过结论 result 文件（应 fail-closed）"
    fi
    echo "[smoke] ✓ no-codex — fail-closed + 中文提示，无伪 APPROVED"
    exit 0
    ;;
esac
