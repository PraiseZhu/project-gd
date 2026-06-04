#!/usr/bin/env bash
# gd-run-akb-plan3-fresh-rerun.sh
# AKB Plan 3 fresh rerun wrapper for Project GD.
#
# Required env vars:
#   GD_AKB2_WORKTREE  — path to AKB2 worktree
#   GD_FRESH_REPORT_DIR — path for fresh reports (created by this script)
#
# Usage:
#   --preflight  Check prerequisites without invoking live daemon. Default if no flag.
#   --live       Run full end-to-end including Codex daemon (requires explicit flag).
#
# Exit codes:
#   0 = preflight_ready
#   1 = preflight_blocked
#   2 = live_mode_not_authorized
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GD_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Argument parsing ──────────────────────────────────────────────────────────
MODE="preflight"
if [[ "${1:-}" == "--live" ]]; then
    MODE="live"
elif [[ "${1:-}" == "--preflight" ]] || [[ -z "${1:-}" ]]; then
    MODE="preflight"
else
    echo "GD_FRESH_RERUN_STATUS: unknown_flag — expected --preflight or --live, got: ${1}" >&2
    exit 2
fi

# ── Live mode: intentionally not implemented ──────────────────────────────────
if [[ "$MODE" == "live" ]]; then
    echo "GD_FRESH_RERUN_STATUS: live_mode_not_authorized"
    echo "To run live, user must explicitly pass --live and authorize daemon access"
    exit 2
fi

# ── Preflight mode ────────────────────────────────────────────────────────────
BLOCKED=0
MISSING_ITEMS=()
STATUS_ITEMS=()

# Check GD_AKB2_WORKTREE
if [[ -z "${GD_AKB2_WORKTREE:-}" ]]; then
    BLOCKED=1
    MISSING_ITEMS+=("GD_AKB2_WORKTREE env var not set")
elif [[ ! -d "${GD_AKB2_WORKTREE}" ]]; then
    BLOCKED=1
    MISSING_ITEMS+=("GD_AKB2_WORKTREE directory not found: ${GD_AKB2_WORKTREE}")
else
    STATUS_ITEMS+=("GD_AKB2_WORKTREE: ok (${GD_AKB2_WORKTREE})")
fi

# Check GD_FRESH_REPORT_DIR
if [[ -z "${GD_FRESH_REPORT_DIR:-}" ]]; then
    BLOCKED=1
    MISSING_ITEMS+=("GD_FRESH_REPORT_DIR env var not set")
else
    mkdir -p "${GD_FRESH_REPORT_DIR}" 2>/dev/null || {
        BLOCKED=1
        MISSING_ITEMS+=("GD_FRESH_REPORT_DIR could not be created: ${GD_FRESH_REPORT_DIR}")
    }
    if [[ -d "${GD_FRESH_REPORT_DIR}" ]]; then
        STATUS_ITEMS+=("GD_FRESH_REPORT_DIR: created/exists (${GD_FRESH_REPORT_DIR})")
    fi
fi

# Check required validator scripts
REQUIRED_VALIDATORS=(
    "gd-validate-stage-dispatch-ledger.py"
    "gd-validate-controller-report.py"
    "gd-validate-codex-cross-review-aggregate.py"
    "gd-validate-parent-close-gate.py"
)

for validator in "${REQUIRED_VALIDATORS[@]}"; do
    validator_path="${SCRIPT_DIR}/${validator}"
    if [[ -f "${validator_path}" ]]; then
        STATUS_ITEMS+=("validator ${validator}: ok")
    else
        BLOCKED=1
        MISSING_ITEMS+=("validator missing: ${validator_path}")
    fi
done

# ── Write preflight report ────────────────────────────────────────────────────
if [[ -n "${GD_FRESH_REPORT_DIR:-}" ]] && [[ -d "${GD_FRESH_REPORT_DIR}" ]]; then
    PREFLIGHT_REPORT="${GD_FRESH_REPORT_DIR}/preflight-report.json"

    # Build JSON arrays for status and missing items
    STATUS_JSON="["
    first=1
    for item in "${STATUS_ITEMS[@]+"${STATUS_ITEMS[@]}"}"; do
        if [[ $first -eq 0 ]]; then STATUS_JSON+=","; fi
        STATUS_JSON+="\"$(echo "$item" | sed 's/"/\\"/g')\""
        first=0
    done
    STATUS_JSON+="]"

    MISSING_JSON="["
    first=1
    for item in "${MISSING_ITEMS[@]+"${MISSING_ITEMS[@]}"}"; do
        if [[ $first -eq 0 ]]; then MISSING_JSON+=","; fi
        MISSING_JSON+="\"$(echo "$item" | sed 's/"/\\"/g')\""
        first=0
    done
    MISSING_JSON+="]"

    if [[ $BLOCKED -eq 0 ]]; then
        PREFLIGHT_STATUS="preflight_ready"
    else
        PREFLIGHT_STATUS="preflight_blocked"
    fi

    cat > "${PREFLIGHT_REPORT}" <<JSON
{
  "status": "${PREFLIGHT_STATUS}",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "gd_akb2_worktree": "${GD_AKB2_WORKTREE:-null}",
  "gd_fresh_report_dir": "${GD_FRESH_REPORT_DIR:-null}",
  "checks_passed": ${STATUS_JSON},
  "checks_blocked": ${MISSING_JSON},
  "note": "Preflight only — no daemon/network invocation. Pass --live to authorize real execution (requires explicit user authorization)."
}
JSON
fi

# ── Final status output ───────────────────────────────────────────────────────
if [[ $BLOCKED -eq 0 ]]; then
    echo "GD_FRESH_RERUN_STATUS: preflight_ready"
    exit 0
else
    echo "GD_FRESH_RERUN_STATUS: preflight_blocked"
    for item in "${MISSING_ITEMS[@]}"; do
        echo "  BLOCKED: ${item}"
    done
    exit 1
fi
