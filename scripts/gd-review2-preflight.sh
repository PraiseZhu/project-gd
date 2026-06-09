#!/bin/bash
# gd-review2-preflight.sh — Dry-run evidence preflight gate for /review2 code
#
# PURPOSE:
#   Before sending code to Codex for cross-review, verify that all production
#   paths (including fallback / no-API-key branch) have been exercised locally.
#   Gate only applies to the /review2 CODE path — NOT the plan path.
#
# USAGE:
#   bash scripts/gd-review2-preflight.sh [--evidence <path>]
#
# ARGUMENTS:
#   --evidence <path>   Path to the dry-run evidence JSON file.
#                       Default: results/review-route-split/dryrun-evidence.json
#
# EXIT CODES:
#   0  — Evidence present and valid → DRYRUN_EVIDENCE_OK
#   1  — Evidence file present but does not meet compliance criteria → DRYRUN_EVIDENCE_INVALID
#   3  — Evidence file missing → DRYRUN_EVIDENCE_MISSING
#
# EVIDENCE FILE FORMAT (minimum required fields):
#   {
#     "paths_exercised": ["main", "fallback"],   // non-empty array
#     "fallback_no_api_key": true                 // or equivalent marker
#   }
#
# GATE BOUNDARY:
#   This gate is ONLY wired into /review2 code.
#   It must NOT be called from /review2 plan (plan phase has no code to run).

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_EVIDENCE_PATH="results/review-route-split/dryrun-evidence.json"
EVIDENCE_PATH=""

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --evidence)
      if [[ -z "${2:-}" ]]; then
        echo "ERROR: --evidence requires a path argument" >&2
        exit 1
      fi
      EVIDENCE_PATH="$2"
      shift 2
      ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Apply default if not specified
if [[ -z "$EVIDENCE_PATH" ]]; then
  EVIDENCE_PATH="$DEFAULT_EVIDENCE_PATH"
fi

# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------

# SC-2b: Evidence file missing → exit 3
if [[ ! -f "$EVIDENCE_PATH" ]]; then
  echo "DRYRUN_EVIDENCE_MISSING: evidence file not found at: $EVIDENCE_PATH" >&2
  echo "DRYRUN_EVIDENCE_MISSING"
  exit 3
fi

# Read evidence file content
evidence_content="$(cat "$EVIDENCE_PATH")"

# Check paths_exercised field: must be a non-empty array
# Use python3 for reliable JSON parsing (available on all target machines)
if ! python3 - <<'PYEOF' "$EVIDENCE_PATH"
import json, sys

path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f"DRYRUN_EVIDENCE_INVALID: JSON parse error: {e}", file=sys.stderr)
    print("DRYRUN_EVIDENCE_INVALID")
    sys.exit(1)

# Validate paths_exercised: must exist and be a non-empty array
paths = data.get("paths_exercised")
if not isinstance(paths, list) or len(paths) == 0:
    print("DRYRUN_EVIDENCE_INVALID: 'paths_exercised' must be a non-empty array", file=sys.stderr)
    print("DRYRUN_EVIDENCE_INVALID")
    sys.exit(1)

# Validate fallback_no_api_key: must be truthy (bool true or equivalent)
fallback = data.get("fallback_no_api_key")
if fallback is not True:
    print("DRYRUN_EVIDENCE_INVALID: 'fallback_no_api_key' must be true", file=sys.stderr)
    print("DRYRUN_EVIDENCE_INVALID")
    sys.exit(1)

# All checks passed
print("DRYRUN_EVIDENCE_OK")
sys.exit(0)
PYEOF
then
  # Python script exited non-zero — already printed the error message
  exit 1
fi

# Python script exited 0 and printed DRYRUN_EVIDENCE_OK
exit 0
