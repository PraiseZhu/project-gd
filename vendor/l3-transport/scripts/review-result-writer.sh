#!/usr/bin/env bash
# review-result-writer.sh — Atomic review result handler.
#
# Claude calls this ONE Bash command instead of multiple Write tool calls.
# Handles: codex-send-wait → save result → validate structure → update baseline → output short verdict.
# No Write tool needed — eliminates terminal diff preview bloat.
#
# Usage:
#   bash ~/.claude/scripts/review-result-writer.sh \
#     --capsule-file /path/to/capsule.txt \
#     --baseline-key <md5-12> \
#     --review-kind <plan|code> \
#     [--cwd /project/dir]
#
# Outputs to stdout (only these lines — kept minimal for terminal):
#   [REVIEW] ✓ APPROVED — <one-line summary>
#   [REVIEW] ✗ REQUIRES_CHANGES — <count> items
#   [REVIEW] ⚠️ DEGRADED — watch unavailable
#   [REVIEW] ✗ FAILED — <reason>
#   [REVIEW] ✗ MALFORMED — <missing fields>

set -euo pipefail

# Resolve transport paths from the SAME state-paths.sh the daemon installer uses,
# so CODEX_BIN (${HANDOFF_BIN}/codex-send-wait) and HANDOFF_ROOT stay in sync.
_WRITER_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../handoff/lib/state-paths.sh
. "$_WRITER_SCRIPT_DIR/../handoff/lib/state-paths.sh"

CAPSULE_FILE=""
BASELINE_KEY=""
REVIEW_KIND=""
REVIEW_CWD="${PWD}"
NO_STOP_MARKER=0
OUT_DIR=""
MODE="review-only"
SEND_TIMEOUT="540"
EXEC_TIMEOUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --capsule-file) CAPSULE_FILE="$2"; shift 2 ;;
    --baseline-key) BASELINE_KEY="$2"; shift 2 ;;
    --review-kind) REVIEW_KIND="$2"; shift 2 ;;
    --cwd) REVIEW_CWD="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --no-stop-marker) NO_STOP_MARKER=1; shift ;;
    --mode) MODE="$2"; shift 2 ;;
    --send-timeout) SEND_TIMEOUT="$2"; shift 2 ;;
    --exec-timeout) EXEC_TIMEOUT="$2"; shift 2 ;;
    *) echo "[REVIEW] ✗ FAILED — unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$CAPSULE_FILE" || -z "$BASELINE_KEY" || -z "$REVIEW_KIND" ]]; then
  echo "[REVIEW] ✗ FAILED — missing required args (--capsule-file, --baseline-key, --review-kind)"
  exit 1
fi

if [[ ! -f "$CAPSULE_FILE" ]]; then
  echo "[REVIEW] ✗ FAILED — capsule file not found: $CAPSULE_FILE"
  exit 1
fi

# Write isolation: baselines default to the update-safe plugin data dir
# (${CLAUDE_PLUGIN_DATA}), falling back to ${HOME}/.claude — never the plugin
# install dir. --out-dir lets the caller override the baselines root entirely.
BASELINE_ROOT="${OUT_DIR:-${CLAUDE_PLUGIN_DATA:-$HOME/.claude}/gd-review-baselines}"
BASELINE_DIR="${BASELINE_ROOT}/${BASELINE_KEY}"
mkdir -p "$BASELINE_DIR" || { echo "[REVIEW] ✗ FAILED — 无法创建产物目录: $BASELINE_DIR" >&2; exit 1; }

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
LAST_ERROR_PATH=""

# Writer-required gate: locate intent marker so we can mark it writer_called at end
_SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
_SESSION_ID_SAFE="$(printf '%s' "$_SESSION_ID" | tr -cd 'A-Za-z0-9_-' | cut -c1-64)"
WRITER_MARKER_FILE="${CLAUDE_PLUGIN_DATA:-$HOME/.claude}/gd-state/review-writer-required/${_SESSION_ID_SAFE}.json"

# Save capsule copy.
# T1 (fail-loud): under `set -e` a failed cp (e.g. read-only / full disk) would
# abort the script with NO stdout, so the client sees silence instead of a
# definite failure. Emit [REVIEW] ✗ FAILED explicitly before exiting.
if ! cp "$CAPSULE_FILE" "${BASELINE_DIR}/capsule-${TIMESTAMP}.txt"; then
  echo "[REVIEW] ✗ FAILED — 无法写入 capsule 副本: ${BASELINE_DIR}/capsule-${TIMESTAMP}.txt"
  exit 1
fi

# Extract capsule metadata for state tracking
CAPSULE_DOMAIN=$(grep -m1 '^REVIEW_DOMAIN:' "$CAPSULE_FILE" | sed 's/^REVIEW_DOMAIN:[[:space:]]*//' || echo "N/A")
CAPSULE_ROUND=$(grep -m1 '^REVIEW_ROUND:' "$CAPSULE_FILE" | sed 's/^REVIEW_ROUND:[[:space:]]*//' || echo "initial")
CAPSULE_DELTA_SCOPE=$(grep -m1 '^REVIEW_DELTA_SCOPE:' "$CAPSULE_FILE" | sed 's/^REVIEW_DELTA_SCOPE:[[:space:]]*//' || echo "full_matrix")
CAPSULE_PLAN_ALIGNMENT=$(grep -m1 '^PLAN_REVIEW_ALIGNMENT:' "$CAPSULE_FILE" | sed 's/^PLAN_REVIEW_ALIGNMENT:[[:space:]]*//' || echo "N/A")
CAPSULE_PLAN_ALIGNMENT_PRESENT=$(grep -m1 '^PLAN_ALIGNMENT_PRESENT:' "$CAPSULE_FILE" | sed 's/^PLAN_ALIGNMENT_PRESENT:[[:space:]]*//' || echo "false")
CAPSULE_REVIEW_FOCUS=$(grep -m1 '^REVIEW_FOCUS:' "$CAPSULE_FILE" | sed 's/^REVIEW_FOCUS:[[:space:]]*//' || echo "N/A")
CAPSULE_REVIEW_FOCUS_SOURCE=$(grep -m1 '^REVIEW_FOCUS_SOURCE:' "$CAPSULE_FILE" | sed 's/^REVIEW_FOCUS_SOURCE:[[:space:]]*//' || echo "domain_matrix")
CAPSULE_DOMAIN_OVERRIDE_REASON=$(grep -m1 '^DOMAIN_OVERRIDE_REASON:' "$CAPSULE_FILE" | sed 's/^DOMAIN_OVERRIDE_REASON:[[:space:]]*//' || echo "N/A")

# Per-finding validation helper (lightweight: 问题/证据/影响/最小修复/验收)
_validate_finding_block() {
  local kind="$1" fnum="$2" block="$3"
  local prefix="Finding #${fnum}"

  echo "$block" | grep -q '问题:' || MISSING_FIELDS="${MISSING_FIELDS}${prefix}: 问题, "
  echo "$block" | grep -q '证据:' || MISSING_FIELDS="${MISSING_FIELDS}${prefix}: 证据, "
  echo "$block" | grep -q '影响:' || MISSING_FIELDS="${MISSING_FIELDS}${prefix}: 影响, "
  echo "$block" | grep -q '最小修复:' || MISSING_FIELDS="${MISSING_FIELDS}${prefix}: 最小修复, "
  echo "$block" | grep -q '验收:' || MISSING_FIELDS="${MISSING_FIELDS}${prefix}: 验收, "
}

# Send to Codex watch — CODEX_BIN resolved via state-paths.sh ${HANDOFF_BIN}
# (same coordination root as the daemon), no $HOME/.claude/handoff hardcode.
CODEX_BIN="${HANDOFF_BIN}/codex-send-wait"
CODEX_OUTPUT=""
CODEX_EXIT=0

if [[ -x "$CODEX_BIN" ]]; then
  CODEX_ARGS=(--cwd "$REVIEW_CWD" --mode "$MODE" --payload-file "$CAPSULE_FILE" --timeout "$SEND_TIMEOUT")
  if [[ -n "$EXEC_TIMEOUT" ]]; then
    CODEX_ARGS+=(--exec-timeout "$EXEC_TIMEOUT")
  fi
  CODEX_OUTPUT=$("$CODEX_BIN" "${CODEX_ARGS[@]}" 2>&1) || CODEX_EXIT=$?
else
  CODEX_EXIT=127
fi

# Parse verdict from output
VERDICT=""
VERDICT_STATUS=""
RESULT_FILE=""

# exit 127 = codex-send-wait binary missing; exit 2 = watch unavailable (SC-3 DEGRADED).
# Both are transport-unavailable, not review failures — must not be bucketed as FAILED.
if [[ $CODEX_EXIT -eq 127 || $CODEX_EXIT -eq 2 ]]; then
  VERDICT_STATUS="degraded_unreviewed"
  echo "[REVIEW] ⚠️ DEGRADED — watch unavailable, capsule saved to ${BASELINE_DIR}/capsule-${TIMESTAMP}.txt"
  echo "[审查] ⚠️ 缺 codex 传输栈：未找到可执行 codex-send-wait（路径 ${CODEX_BIN}）。" >&2
  echo "[审查] 跨审 fail-closed，不产出通过结论；请先按 README 部署传输栈（codex CLI + 自备 key + install-transport.sh 部署 daemon）后重试。" >&2
elif [[ $CODEX_EXIT -ne 0 ]]; then
  VERDICT_STATUS="failed"
  ERROR_LOG="${BASELINE_DIR}/error-${TIMESTAMP}.log"
  echo "$CODEX_OUTPUT" > "$ERROR_LOG" 2>/dev/null || true
  LAST_ERROR_PATH="$ERROR_LOG"
  echo "[REVIEW] ✗ FAILED — codex-send-wait exit $CODEX_EXIT"
  echo "Failure log: ${ERROR_LOG}"
else
  # Save result first.
  # T1 (fail-loud): the result file is the canonical landing of the codex
  # verdict — if this redirect fails under `set -e` the script would die
  # silently after a SUCCESSFUL codex run, making the client believe no result
  # came back. Emit an explicit [REVIEW] ✗ FAILED instead of aborting quietly.
  RESULT_FILE="${BASELINE_DIR}/result-${TIMESTAMP}.md"
  if ! echo "$CODEX_OUTPUT" > "$RESULT_FILE"; then
    echo "[REVIEW] ✗ FAILED — codex 返回成功但结果文件落盘失败: $RESULT_FILE"
    exit 1
  fi

  # Parse VERDICT from output
  if echo "$CODEX_OUTPUT" | grep -q 'VERDICT: APPROVED'; then
    VERDICT="APPROVED"
    VERDICT_STATUS="approved"
  elif echo "$CODEX_OUTPUT" | grep -q 'VERDICT: REQUIRES_CHANGES'; then
    VERDICT="REQUIRES_CHANGES"
    VERDICT_STATUS="requires_changes"
  else
    VERDICT_STATUS="failed"
    echo "[REVIEW] ✗ FAILED — no VERDICT in Codex output"
  fi

  # Structure validation (per-finding granularity)
  if [[ -n "$VERDICT" ]]; then
    MISSING_FIELDS=""

    # Top-level structure checks (shared)
    if [[ "$REVIEW_KIND" == "plan" ]]; then
      echo "$CODEX_OUTPUT" | grep -q '# Plan Review Result' || MISSING_FIELDS="${MISSING_FIELDS}Plan Review Result header, "
    else
      echo "$CODEX_OUTPUT" | grep -q '# Code Review Result' || MISSING_FIELDS="${MISSING_FIELDS}Code Review Result header, "
    fi
    echo "$CODEX_OUTPUT" | grep -q 'Scope Checked' || MISSING_FIELDS="${MISSING_FIELDS}Scope Checked, "
    echo "$CODEX_OUTPUT" | grep -q '^## Findings' || MISSING_FIELDS="${MISSING_FIELDS}Findings section, "
    echo "$CODEX_OUTPUT" | grep -q '^## Residual Risk' || MISSING_FIELDS="${MISSING_FIELDS}Residual Risk section, "

    # Per-finding field validation: split by ### Finding, check each block
    if echo "$CODEX_OUTPUT" | grep -q '^### Finding'; then
      local_finding_num=0
      local_finding_block=""
      local_in_finding=false

      while IFS= read -r vline; do
        if [[ "$vline" =~ ^###[[:space:]]Finding ]]; then
          # Validate previous block if any
          if [[ "$local_in_finding" == true && -n "$local_finding_block" ]]; then
            local_finding_num=$((local_finding_num + 1))
            _validate_finding_block "$REVIEW_KIND" "$local_finding_num" "$local_finding_block"
          fi
          local_finding_block="$vline"
          local_in_finding=true
        elif [[ "$local_in_finding" == true ]]; then
          # Stop at next section header (## or ###) that isn't a Finding
          if [[ "$vline" =~ ^##[[:space:]] && ! "$vline" =~ ^###[[:space:]]Finding ]]; then
            local_finding_num=$((local_finding_num + 1))
            _validate_finding_block "$REVIEW_KIND" "$local_finding_num" "$local_finding_block"
            local_in_finding=false
            local_finding_block=""
          else
            local_finding_block="${local_finding_block}
${vline}"
          fi
        fi
      done <<< "$CODEX_OUTPUT"
      # Validate last finding block
      if [[ "$local_in_finding" == true && -n "$local_finding_block" ]]; then
        local_finding_num=$((local_finding_num + 1))
        _validate_finding_block "$REVIEW_KIND" "$local_finding_num" "$local_finding_block"
      fi
    fi

    # REQUIRES_CHANGES must have at least one finding
    if [[ "$VERDICT" == "REQUIRES_CHANGES" ]]; then
      if ! echo "$CODEX_OUTPUT" | grep -q '^### Finding'; then
        MISSING_FIELDS="${MISSING_FIELDS}at least one ### Finding (REQUIRES_CHANGES with 0 findings), "
      fi
    fi

    # Trim trailing comma+space
    MISSING_FIELDS="${MISSING_FIELDS%, }"

    if [[ -n "$MISSING_FIELDS" ]]; then
      VERDICT_STATUS="malformed"
      VERDICT="MALFORMED"
      echo "[REVIEW] ✗ MALFORMED — missing: ${MISSING_FIELDS}. Full result: ${RESULT_FILE}"
    fi
  fi
fi

# Extract findings summary for state tracking
FINDINGS_SUMMARY="N/A"
NEXT_REVIEW_SCOPE="N/A"
DIRECT_DOWNSTREAM="N/A"

if [[ -n "$CODEX_OUTPUT" && -n "$VERDICT" && "$VERDICT_STATUS" != "malformed" ]]; then
  FINDINGS_SUMMARY=$(echo "$CODEX_OUTPUT" | grep -E '^### Finding' | head -5 | tr '\n' '; ' || echo "N/A")
  FINDINGS_SUMMARY="${FINDINGS_SUMMARY:-N/A}"

  NEXT_REVIEW_SCOPE=$(echo "$CODEX_OUTPUT" | grep -m1 'next_review_scope:' | sed 's/.*next_review_scope:[[:space:]]*//' || echo "N/A")
  DIRECT_DOWNSTREAM=$(echo "$CODEX_OUTPUT" | grep -m1 'direct_downstream:' | sed 's/.*direct_downstream:[[:space:]]*//' || echo "N/A")
fi

# Update baseline JSON (create if missing)
BASELINE_FILE="${BASELINE_DIR}/latest-plan-baseline.json"

# Extract capsule fields for baseline initialization
CAPSULE_CWD=$(grep -m1 '^PROJECT_ROOT:' "$CAPSULE_FILE" | sed 's/^PROJECT_ROOT:[[:space:]]*//' || echo "$REVIEW_CWD")
CAPSULE_REPO_ROOT=$(grep -m1 '^REPO_ROOT:' "$CAPSULE_FILE" | sed 's/^REPO_ROOT:[[:space:]]*//' || echo "N/A")
CAPSULE_BRANCH=$(grep -m1 '^BRANCH:' "$CAPSULE_FILE" | sed 's/^BRANCH:[[:space:]]*//' || echo "N/A")
CAPSULE_IN_SCOPE=$(grep -m1 '^IN_SCOPE:' "$CAPSULE_FILE" | sed 's/^IN_SCOPE:[[:space:]]*//' || echo "N/A")
CAPSULE_OUT_OF_SCOPE=$(grep -m1 '^OUT_OF_SCOPE:' "$CAPSULE_FILE" | sed 's/^OUT_OF_SCOPE:[[:space:]]*//' || echo "N/A")
CAPSULE_ACCEPTED=$(grep -m1 '^USER_ACCEPTED_DECISIONS:' "$CAPSULE_FILE" | sed 's/^USER_ACCEPTED_DECISIONS:[[:space:]]*//' || echo "N/A")
CAPSULE_SUCCESS=$(grep -m1 '^SUCCESS_CRITERIA:' "$CAPSULE_FILE" | sed 's/^SUCCESS_CRITERIA:[[:space:]]*//' || echo "N/A")
CAPSULE_LIMITATIONS=$(grep -m1 '^KNOWN_LIMITATIONS:' "$CAPSULE_FILE" | sed 's/^KNOWN_LIMITATIONS:[[:space:]]*//' || echo "N/A")

if [[ ! -f "$BASELINE_FILE" ]]; then
  # Initialize baseline from capsule metadata
  BASELINE_HEAD="N/A"
  BASELINE_KEY_SOURCE="cwd"
  DIRTY_STATUS=""
  if [[ -d "$REVIEW_CWD/.git" ]] || git -C "$REVIEW_CWD" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    BASELINE_HEAD=$(git -C "$REVIEW_CWD" rev-parse HEAD 2>/dev/null || echo "N/A")
    BASELINE_KEY_SOURCE="repo_root"
    DIRTY_STATUS=$(git -C "$REVIEW_CWD" status --short 2>/dev/null || echo "")
  fi

  jq -n \
    --arg baseline_key "$BASELINE_KEY" \
    --arg baseline_key_source "$BASELINE_KEY_SOURCE" \
    --arg trigger_cwd "$CAPSULE_CWD" \
    --arg repo_root "$CAPSULE_REPO_ROOT" \
    --arg branch "$CAPSULE_BRANCH" \
    --arg head "$BASELINE_HEAD" \
    --arg dirty_status "$DIRTY_STATUS" \
    --arg in_scope "$CAPSULE_IN_SCOPE" \
    --arg out_of_scope "$CAPSULE_OUT_OF_SCOPE" \
    --arg user_accepted_decisions "$CAPSULE_ACCEPTED" \
    --arg success_criteria "$CAPSULE_SUCCESS" \
    --arg known_limitations "$CAPSULE_LIMITATIONS" \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg capsule_path "${BASELINE_DIR}/capsule-${TIMESTAMP}.txt" \
    '{
      baseline_key: $baseline_key,
      baseline_key_source: $baseline_key_source,
      trigger_cwd: $trigger_cwd,
      repo_root: $repo_root,
      branch: $branch,
      head: $head,
      dirty_status: $dirty_status,
      in_scope: $in_scope,
      out_of_scope: $out_of_scope,
      user_accepted_decisions: $user_accepted_decisions,
      success_criteria: $success_criteria,
      known_limitations: $known_limitations,
      timestamp: $ts,
      capsule_path: $capsule_path,
      review_status: "pending",
      verdict: "N/A",
      reviewed_at: null,
      result_path: null,
      watch_result_path: null,
      last_review_kind: "N/A",
      last_review_domain: "N/A",
      last_result_path: null,
      last_findings_summary: "N/A",
      last_review_round: "N/A",
      last_review_delta_scope: "N/A",
      last_next_review_scope: "N/A",
      last_direct_downstream: "N/A",
      plan_review_alignment: "N/A",
      plan_review_alignment_present: false,
      last_review_focus: [],
      last_review_focus_source: "N/A",
      last_domain_override_reason: "N/A"
    }' > "$BASELINE_FILE"
fi

# Update baseline with review results
# Use an explicit template so mktemp respects $TMPDIR (macOS mktemp otherwise
# ignores $TMPDIR and uses confstr, which fails inside the Claude Code sandbox).
TMP_BASELINE=$(mktemp "${TMPDIR:-/tmp}/review-baseline-XXXXXX")

# Convert REVIEW_FOCUS from semicolon-separated string to JSON array
REVIEW_FOCUS_JSON="[]"
if [[ "$CAPSULE_REVIEW_FOCUS" != "N/A" && -n "$CAPSULE_REVIEW_FOCUS" ]]; then
  REVIEW_FOCUS_JSON=$(echo "$CAPSULE_REVIEW_FOCUS" | tr ';' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | jq -R . | jq -s . 2>/dev/null || echo "[]")
fi

# Convert PLAN_ALIGNMENT_PRESENT to boolean
PLAN_ALIGNMENT_BOOL="false"
[[ "$CAPSULE_PLAN_ALIGNMENT_PRESENT" == "true" ]] && PLAN_ALIGNMENT_BOOL="true"

# SC-4: a non-success attempt (failed/degraded/malformed) against an ALREADY-approved
# baseline must NOT clobber the prior gate verdict. The attempt still records its
# evidence (error log, result file, last_error_path) but leaves the approved baseline
# intact so a transient codex/watch failure can't downgrade a passed gate.
PRESERVE_APPROVED=0
if [[ "$VERDICT_STATUS" != "approved" && "$VERDICT_STATUS" != "requires_changes" && -f "$BASELINE_FILE" ]]; then
  if [[ "$REVIEW_KIND" == "plan" ]]; then
    _prior_status="$(jq -r '.review_status // ""' "$BASELINE_FILE" 2>/dev/null || true)"
  else
    _prior_status="$(jq -r '.last_code_review_status // ""' "$BASELINE_FILE" 2>/dev/null || true)"
  fi
  if [[ "$_prior_status" == "approved" ]]; then
    PRESERVE_APPROVED=1
  fi
fi

# Build jq filter: plan reviews update .review_status/.verdict; code reviews use separate fields
if [[ "$PRESERVE_APPROVED" -eq 1 ]]; then
  # Preserve path: stamp the failed attempt WITHOUT touching the approved gate fields
  # (review_status / verdict / result_path / last_code_*). last_review_focus is skipped
  # in the common block below via $preserve_approved.
  if [[ "$REVIEW_KIND" == "plan" ]]; then
    JQ_STATE_FILTER='
       .last_failed_attempt_status = $status |
       .last_failed_attempt_at = $reviewed_at |'
  else
    JQ_STATE_FILTER='
       .last_code_failed_attempt_status = $status |
       .last_code_failed_attempt_at = $reviewed_at |'
  fi
elif [[ "$REVIEW_KIND" == "plan" ]]; then
  JQ_STATE_FILTER='
     .review_status = $status |
     .verdict = $verdict |
     .reviewed_at = $reviewed_at |
     .result_path = $result_path |'
else
  JQ_STATE_FILTER='
     .last_code_review_status = $status |
     .last_code_verdict = $verdict |
     .last_code_reviewed_at = $reviewed_at |
     .last_code_result_path = $result_path |'
fi

jq --arg status "$VERDICT_STATUS" \
   --arg verdict "${VERDICT:-N/A}" \
   --arg reviewed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
   --arg result_path "${RESULT_FILE:-null}" \
   --arg last_review_kind "$REVIEW_KIND" \
   --arg last_review_domain "$CAPSULE_DOMAIN" \
   --arg last_result_path "${RESULT_FILE:-null}" \
   --arg last_findings_summary "$FINDINGS_SUMMARY" \
   --arg last_review_round "$CAPSULE_ROUND" \
   --arg last_review_delta_scope "$CAPSULE_DELTA_SCOPE" \
   --arg last_next_review_scope "$NEXT_REVIEW_SCOPE" \
   --arg last_direct_downstream "$DIRECT_DOWNSTREAM" \
   --arg plan_review_alignment "$CAPSULE_PLAN_ALIGNMENT" \
   --argjson plan_review_alignment_present "$PLAN_ALIGNMENT_BOOL" \
   --argjson last_review_focus "$REVIEW_FOCUS_JSON" \
   --arg last_review_focus_source "$CAPSULE_REVIEW_FOCUS_SOURCE" \
   --arg last_domain_override_reason "$CAPSULE_DOMAIN_OVERRIDE_REASON" \
   --arg last_error_path "${LAST_ERROR_PATH:-}" \
   --argjson preserve_approved "$PRESERVE_APPROVED" \
   "${JQ_STATE_FILTER}"'
   .last_review_kind = $last_review_kind |
   .last_review_domain = $last_review_domain |
   .last_result_path = $last_result_path |
   .last_findings_summary = $last_findings_summary |
   .last_review_round = $last_review_round |
   .last_review_delta_scope = $last_review_delta_scope |
   .last_next_review_scope = $last_next_review_scope |
   .last_direct_downstream = $last_direct_downstream |
   .plan_review_alignment = $plan_review_alignment |
   .plan_review_alignment_present = $plan_review_alignment_present |
   (if $preserve_approved == 1 then . else
     (.last_review_focus = $last_review_focus |
      .last_review_focus_source = $last_review_focus_source)
   end) |
   .last_domain_override_reason = $last_domain_override_reason |
   .last_error_path = (if $last_error_path == "" then null else $last_error_path end)
   ' \
   "$BASELINE_FILE" > "$TMP_BASELINE" 2>/dev/null && mv "$TMP_BASELINE" "$BASELINE_FILE" || rm -f "$TMP_BASELINE"

# Output verdict (short — this is the only stdout Claude sees in terminal)
if [[ "$VERDICT_STATUS" == "malformed" ]]; then
  : # Already output above
elif [[ "$VERDICT" == "APPROVED" ]]; then
  SUMMARY=$(echo "$CODEX_OUTPUT" | grep -v '^$' | grep -vi 'VERDICT' | head -1 | cut -c1-120)
  echo "[REVIEW] ✓ APPROVED${SUMMARY:+ — $SUMMARY}"
  echo "Full result: ${RESULT_FILE}"
elif [[ "$VERDICT" == "REQUIRES_CHANGES" ]]; then
  ITEM_COUNT=$(echo "$CODEX_OUTPUT" | grep -cE '^### Finding' 2>/dev/null) || ITEM_COUNT=0
  echo "[REVIEW] ✗ REQUIRES_CHANGES — ${ITEM_COUNT} findings. Full result: ${RESULT_FILE}"
fi

# Output structured feedback (first 3 findings' key fields)
if [[ "$VERDICT" == "REQUIRES_CHANGES" && -n "$CODEX_OUTPUT" && "$VERDICT_STATUS" != "malformed" ]]; then
  echo ""
  echo "--- Top Findings ---"
  FINDING_NUM=0
  while IFS= read -r line; do
    if [[ "$line" =~ ^###[[:space:]]Finding ]]; then
      FINDING_NUM=$((FINDING_NUM + 1))
      [[ $FINDING_NUM -gt 3 ]] && break
      echo "$line"
    elif [[ $FINDING_NUM -ge 1 && $FINDING_NUM -le 3 ]]; then
      if [[ "$line" =~ ^(问题:|证据:|影响:|最小修复:|验收:) ]]; then
        echo "$line"
      fi
    fi
  done <<< "$CODEX_OUTPUT"
  [[ $FINDING_NUM -gt 3 ]] && echo "... and $((FINDING_NUM - 3)) more findings"
  echo "--- End ---"
fi

# Update writer-required gate marker to "writer_called"
# This tells review-writer-required-gate.js (Stop hook) that the writer ran.
if [[ -f "$WRITER_MARKER_FILE" ]] && command -v jq >/dev/null 2>&1; then
  _MARKER_TMP="${WRITER_MARKER_FILE}.tmp"
  jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     '.status = "writer_called" | .writer_called_at = $ts' \
     "$WRITER_MARKER_FILE" > "$_MARKER_TMP" 2>/dev/null \
     && mv "$_MARKER_TMP" "$WRITER_MARKER_FILE" \
     || rm -f "$_MARKER_TMP"
fi

case "$VERDICT_STATUS" in
  approved|requires_changes)
    exit 0
    ;;
  *)
    exit 1
    ;;
esac
