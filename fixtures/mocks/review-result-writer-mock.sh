#!/usr/bin/env bash
# review-result-writer-mock.sh — Mock writer for smoke tests (Phase 5)
# Simulates the review-result-writer.sh interface without touching live ~/.claude paths.
# Used via GD_WRITER_PATH_OVERRIDE env var in bridge smoke tests.
#
# Interface matches live writer:
#   bash <writer> --capsule-file <path> --baseline-key <key> --review-kind <kind> \
#                 --cwd <cwd> --no-stop-marker
#
# Output format must satisfy:
#   - parse_writer_result_path(): "Full result: <path>" present
#   - L3 validator: APPROVED verdict requires SCOPE_CHECKED table + valid evidence

set -euo pipefail

MOCK_RESULT_DIR="${GD_MOCK_RESULT_DIR:-/tmp/gd-mock-writer-results}"
mkdir -p "$MOCK_RESULT_DIR"

CAPSULE_FILE=""
BASELINE_KEY=""
REVIEW_KIND=""
CWD="."

while [[ $# -gt 0 ]]; do
    case "$1" in
        --capsule-file)  CAPSULE_FILE="$2"; shift 2 ;;
        --baseline-key)  BASELINE_KEY="$2"; shift 2 ;;
        --review-kind)   REVIEW_KIND="$2"; shift 2 ;;
        --cwd)           CWD="$2"; shift 2 ;;
        --no-stop-marker) shift ;;
        *) shift ;;
    esac
done

RESULT_FILE="$MOCK_RESULT_DIR/mock-result-${REVIEW_KIND:-unknown}-$(date +%s).md"

# Extract PRIMARY_TARGET_PATH from capsule if available (for evidence refs)
PRIMARY_TARGET=""
if [[ -n "$CAPSULE_FILE" && -f "$CAPSULE_FILE" ]]; then
    PRIMARY_TARGET=$(grep -m1 "^PRIMARY_TARGET:" "$CAPSULE_FILE" 2>/dev/null | sed 's/^PRIMARY_TARGET: *//' || true)
fi
PRIMARY_TARGET="${PRIMARY_TARGET:-fixtures/review2-plan/good-plan.md}"

# Build Scope Checked rows covering EVERY SC checklist line in the target plan,
# matching the bridge SHALLOW_REVIEW count (_PLAN_SC_ID_RE = '^- [ ] SC-N' in
# gd-codex-bridge-review.py). A single hardcoded row trips SHALLOW_REVIEW → degraded
# whenever the target declares >1 SC, so derive rows dynamically from the real target.
SC_LIST=$(grep -oE '^- \[[ xX]\] SC-[0-9]+' "$PRIMARY_TARGET" 2>/dev/null | grep -oE 'SC-[0-9]+' | sort -u || true)
SC_ROWS=""
for sc in $SC_LIST; do
    [[ -n "$SC_ROWS" ]] && SC_ROWS="${SC_ROWS}"$'\n'
    SC_ROWS="${SC_ROWS}| ${sc} | PASS | ${PRIMARY_TARGET}:1 — step present |"
done
# Fallback: target unreadable / no SC checklist lines → at least one row (avoids empty table).
[[ -z "$SC_ROWS" ]] && SC_ROWS="| SC-1 | PASS | ${PRIMARY_TARGET}:1 — step present |"

cat > "$RESULT_FILE" << EOF
# Plan Review Result (Mock)

REVIEW_KIND: ${REVIEW_KIND:-unknown}
BASELINE_KEY: ${BASELINE_KEY:-unknown}

## Scope Checked

SCOPE_CHECKED:
| SC-ID | Status | Evidence |
|-------|--------|----------|
${SC_ROWS}

## Findings

No findings (mock writer — automated smoke test).

## Residual Risk

None (mock).

## Verdict

VERDICT: APPROVED
EOF

echo "[REVIEW] ✓ APPROVED. Full result: $RESULT_FILE"
exit 0
