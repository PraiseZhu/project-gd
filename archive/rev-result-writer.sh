#!/usr/bin/env bash
# scripts/rev-result-writer.sh — parse raw codex output, write result.md + result.json
#
# Usage:
#   rev-result-writer.sh --kind plan|code --artifact <file> \
#     --run-dir <dir> --candidate-baseline <json> --baseline-key <key>
set -euo pipefail

usage() {
    cat <<'EOF'
scripts/rev-result-writer.sh

Flags:
  --kind              plan|code
  --artifact          path to reviewed artifact
  --run-dir           path to results/<run-id>/ directory
  --candidate-baseline path to candidate-baseline.json
  --baseline-key      baseline storage key (e.g. gd-<sha12> or phase2-test)
  --help              show this help
EOF
}

KIND=""
ARTIFACT=""
RUN_DIR=""
CANDIDATE_BASELINE=""
BASELINE_KEY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --kind)              KIND="$2";               shift 2 ;;
        --artifact)          ARTIFACT="$2";            shift 2 ;;
        --run-dir)           RUN_DIR="$2";             shift 2 ;;
        --candidate-baseline) CANDIDATE_BASELINE="$2"; shift 2 ;;
        --baseline-key)      BASELINE_KEY="$2";        shift 2 ;;
        --help|-h)           usage; exit 0 ;;
        *) echo "ERROR: unknown flag: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$KIND" || -z "$ARTIFACT" || -z "$RUN_DIR" || -z "$CANDIDATE_BASELINE" || -z "$BASELINE_KEY" ]]; then
    echo "ERROR: all flags are required" >&2
    usage >&2
    exit 1
fi

if [[ "$KIND" != "plan" && "$KIND" != "code" ]]; then
    echo "ERROR: --kind must be plan or code, got: $KIND" >&2
    exit 1
fi

# --------------------------------------------------------------------------- #
# Locate files
# --------------------------------------------------------------------------- #

RAW="$RUN_DIR/raw-output.txt"
PROMPT="$RUN_DIR/prompt.md"
RESULT_MD="$RUN_DIR/result.md"
RESULT_JSON="$RUN_DIR/result.json"
CONFORMANCE_PATH="$RUN_DIR/conformance.json"

if [[ ! -f "$RAW" ]]; then
    echo "ERROR: raw-output.txt not found: $RAW" >&2
    exit 1
fi

GD_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --------------------------------------------------------------------------- #
# Parse raw output
# --------------------------------------------------------------------------- #

# Count verdict lines
BARE_COUNT="$(grep -cE '^VERDICT:' "$RAW" || true)"
REV_COUNT="$(grep -cE '^REV_VERDICT:' "$RAW" || true)"

RUN_ID="$(basename "$RUN_DIR")"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

FAILURE_REASON="None"  # will be Python None → JSON null unless overridden

# Check for bare VERDICT:
if [[ "$BARE_COUNT" -gt 0 ]]; then
    echo "ERROR: bare VERDICT: found in raw output (triggers live hook) — failure_reason=bare_verdict" >&2
    exit 1
fi

# Check for multiple REV_VERDICT:
if [[ "$REV_COUNT" -gt 1 ]]; then
    echo "ERROR: multiple REV_VERDICT: lines ($REV_COUNT) — failure_reason=multi_verdict" >&2
    exit 1
fi

# Check for missing REV_VERDICT:
if [[ "$REV_COUNT" -eq 0 ]]; then
    # Check for runner failure_reason line
    FR_LINE="$(grep -oE '^failure_reason=.+' "$RAW" | head -1 || true)"
    if [[ -n "$FR_LINE" ]]; then
        echo "ERROR: codex runner failure — $FR_LINE" >&2
    else
        echo "ERROR: no REV_VERDICT: found — failure_reason=missing_verdict" >&2
    fi
    exit 1
fi

# Extract verdict value
VERDICT_LINE="$(grep -oE '^REV_VERDICT: (APPROVED|REQUIRES_CHANGES|FAILED)$' "$RAW" | head -1 || true)"
if [[ -z "$VERDICT_LINE" ]]; then
    echo "ERROR: REV_VERDICT: has non-standard value — failure_reason=missing_verdict" >&2
    exit 1
fi

VERDICT="${VERDICT_LINE#REV_VERDICT: }"

# Extract failure_reason from runner-injected line (for FAILED verdicts)
RAW_FR="$(grep -oE '^failure_reason=.+' "$RAW" | head -1 | cut -d= -f2- || true)"
if [[ -n "$RAW_FR" ]]; then
    FAILURE_REASON="\"$RAW_FR\""
fi

# FAILED only for execution failure, not content issues
# REQUIRES_CHANGES and APPROVED must have failure_reason = None
if [[ "$VERDICT" == "REQUIRES_CHANGES" ]]; then
    FAILURE_REASON="None"
fi
if [[ "$VERDICT" == "APPROVED" ]]; then
    FAILURE_REASON="None"
fi

# --------------------------------------------------------------------------- #
# Write result.md (summary of raw output, not full copy)
# --------------------------------------------------------------------------- #

{
    printf '# %s Review Result\n\n' "$(echo "$KIND" | sed 's/./\u&/')"
    printf 'REV_VERDICT: %s\n' "$VERDICT"
    printf 'REVIEW_KIND: %s\n' "$KIND"
    printf 'REVIEW_DOMAIN: ai_infra\n'
    printf 'run_id: %s\n' "$RUN_ID"
    printf 'timestamp: %s\n\n' "$TIMESTAMP"
    printf '## Raw Output\n\n'
    cat "$RAW"
} > "$RESULT_MD"

# --------------------------------------------------------------------------- #
# Update baseline (APPROVED plan only — code mode never updates baseline)
# --------------------------------------------------------------------------- #

BASELINE_UPDATED="False"

if [[ "$KIND" == "plan" && "$VERDICT" == "APPROVED" ]]; then
    BASELINE_DIR="$GD_ROOT/baselines/$BASELINE_KEY"
    mkdir -p "$BASELINE_DIR"
    cp "$CANDIDATE_BASELINE" "$BASELINE_DIR/latest-rev-baseline.json"
    BASELINE_UPDATED="True"
fi

# --------------------------------------------------------------------------- #
# Write result.json
# --------------------------------------------------------------------------- #

# Conformance path: present for code mode (if file exists), null for plan mode
if [[ "$KIND" == "code" && -f "$CONFORMANCE_PATH" ]]; then
    CONFORMANCE_JSON_VAL="\"$CONFORMANCE_PATH\""
else
    CONFORMANCE_JSON_VAL="None"
fi

python3 - <<PYEOF
import json

failure_reason_raw = $FAILURE_REASON
baseline_updated = $BASELINE_UPDATED
conformance_val = $CONFORMANCE_JSON_VAL

d = {
    "run_id": "$RUN_ID",
    "kind": "$KIND",
    "verdict": "$VERDICT",
    "failure_reason": failure_reason_raw if failure_reason_raw != "null" else None,
    "baseline_updated": baseline_updated,
    "paths": {
        "prompt": "$PROMPT",
        "raw": "$RAW",
        "result_md": "$RESULT_MD",
        "conformance": conformance_val if conformance_val != "null" else None
    },
    "timestamp": "$TIMESTAMP"
}
with open("$RESULT_JSON", "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"OK: result.json written, kind={d['kind']!r}, verdict={d['verdict']}, baseline_updated={d['baseline_updated']}, failure_reason={d['failure_reason']!r}")
PYEOF
