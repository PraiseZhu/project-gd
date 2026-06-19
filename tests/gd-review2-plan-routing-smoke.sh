#!/usr/bin/env bash
# gd-review2-plan-routing-smoke.sh — Phase 5 smoke test (SC-7, SC-8, SC-10)
# Verifies bridge routing guards:
#   SC-7: capsule target rejection (PLAN_TARGET_MUST_BE_ORIGINAL_PLAN)
#   SC-8: v2 templates present → build-capsule succeeds for plan and code_diff kinds
#         (Updated after v2 template補做: test now verifies positive path, not V2_TEMPLATE_NOT_READY guard)
#   SC-10: positive: plan target → bridge invokes writer, mock returns APPROVED

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

PASS=0; FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

pass() { echo "  PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

BRIDGE="python3 scripts/gd-codex-bridge-review.py"
MOCK_WRITER="$(pwd)/fixtures/mocks/review-result-writer-mock.sh"
GOOD_PLAN="$(pwd)/fixtures/review2-plan/good-plan.md"
CAPSULE_TARGET="$(pwd)/fixtures/review2-plan/results/review-route-split/case/capsule.md"

# --- Plan Routing Smoke ===

# --- SC-loop-report: router-readable loop_report + codex field plumbing ---
# Handoff #3 fix: plan review must carry codex evidence (codex_mapped_result_path /
# codex_review_status) into route_report. Pure-helper coverage (no codex/bridge):
# merge-loop writes loop_report_{ts}.json that router globs, raw_result_path points
# at bridge-mapped JSON, timeout→REQUIRES_CHANGES, and validator accepts the new
# codex_* fields on a plan_only route_report.
echo
echo "--- SC-loop-report: loop_report payload + codex field plumbing (python unit suite) ---"
_ex=0
python3 tests/test_loop_report_payload.py >/tmp/gd-loopreport-unit.log 2>&1 || _ex=$?
if [[ $_ex -eq 0 ]] && grep -q "RESULTS: .* passed, 0 failed" /tmp/gd-loopreport-unit.log; then
    pass "loop_report payload + codex plumbing unit suite PASS ($(grep -o 'RESULTS: [0-9]* passed' /tmp/gd-loopreport-unit.log | head -1))"
else
    fail "loop_report payload + codex plumbing unit suite FAILED (exit=$_ex); tail:"
    tail -8 /tmp/gd-loopreport-unit.log | sed 's/^/      /'
fi

echo
echo "--- SC-bridge-policy: execution_outcome findings require sc_refs ---"
_ex=0
python3 tests/test_bridge_sc_refs_policy.py >/tmp/gd-bridge-sc-refs-policy.log 2>&1 || _ex=$?
if [[ $_ex -eq 0 ]] && grep -q "RESULTS: .* passed, 0 failed" /tmp/gd-bridge-sc-refs-policy.log; then
    pass "bridge sc_refs policy unit suite PASS ($(grep -o 'RESULTS: [0-9]* passed' /tmp/gd-bridge-sc-refs-policy.log | head -1))"
else
    fail "bridge sc_refs policy unit suite FAILED (exit=$_ex); tail:"
    tail -8 /tmp/gd-bridge-sc-refs-policy.log | sed 's/^/      /'
fi

# --- SC-6 GENERATIVE: router/merge-loop PRODUCE the route_report (not hand-written) ---
# The negative case must be GENERATED through the real router→merge-loop→loop_report
# →route_report chain so a router/merge-loop field-passthrough regression fails here
# (a hand-written route_report only proves the validator accepts the final shape).
# We inject an APPROVED+degraded codex mapped fixture via --codex-mapped-result, which
# routes merge-loop to _consume_and_merge (no codex convergence needed): the mapped
# file exists but carries APPROVED+degraded → codex_review_status=wrapper_schema_fail.
echo
echo "--- SC-6 generative: APPROVED/degraded mapped → router-generated wrapper_schema_fail ---"
_ex=0
python3 - "$TMPDIR" <<'SETUP' || _ex=$?
import sys, json
from pathlib import Path
d = Path(sys.argv[1])
# an APPROVED + degraded codex mapped result (the P1 mislabel trap: must NOT be approved)
(d / "gen-approved-degraded-mapped.json").write_text(json.dumps(
    {"gd_review_decision": "APPROVED", "review_run_status": "degraded", "findings": []}))
# minimal APPROVED claude-review so merge-loop has the Claude side
(d / "gen-claude.json").write_text(json.dumps({
    "template_kind": "gd-plan-review", "reviewer": "claude_main", "review_kind": "plan",
    "review_run_status": "completed", "gd_review_decision": "APPROVED", "findings": []}))
SETUP
if [[ $_ex -ne 0 ]]; then
    fail "SC-6 setup failed (exit=$_ex)"
else
    GEN_OUT="$TMPDIR/gen-out-failed"
    router_rc=0
    set +e
    python3 scripts/gd-review-router.py --mode live --target "$GOOD_PLAN" \
        --claude-review "$TMPDIR/gen-claude.json" \
        --codex-mapped-result "$TMPDIR/gen-approved-degraded-mapped.json" \
        --output-dir "$GEN_OUT" >"$TMPDIR/gen-run.log" 2>&1
    router_rc=$?
    set -e
    RR=$(ls -t "$GEN_OUT"/route_report_*.json 2>/dev/null | head -1)
    if [[ -z "$RR" ]]; then
        fail "SC-6 generative: no route_report produced; run log:"; tail -5 "$TMPDIR/gen-run.log" | sed 's/^/      /'
    else
        v=0; python3 scripts/gd-validate-route-report.py "$RR" >/dev/null 2>&1 || v=$?
        # one read of the GENERATED route_report (asserting router's actual output)
        summary=$(python3 - "$RR" <<'READ'
import json, sys
d = json.load(open(sys.argv[1]))
print("|".join([
    d.get("codex_review_status") or "",
    d.get("failure_code") or "",
    "1" if d.get("codex_mapped_result_path") else "0",
    d.get("decision") or "",
]))
READ
        )
        crs=${summary%%|*}; rest=${summary#*|}
        fc=${rest%%|*}; rest2=${rest#*|}
        has_mapped=${rest2%%|*}; dec=${rest2##*|}
        if [[ $router_rc -ne 0 && $v -eq 0 && "$crs" == "wrapper_schema_fail" && "$fc" == "CODEX_WRAPPER_SCHEMA_FAIL" \
              && "$has_mapped" == "1" && "$crs" != "completed" && "$dec" != "APPROVED" ]]; then
            pass "APPROVED/degraded mapped → router-generated route_report: wrapper_schema_fail + CODEX_WRAPPER_SCHEMA_FAIL + nonzero rc + validator OK (decision=$dec)"
        else
            fail "SC-6 generative: expected nonzero rc + wrapper_schema_fail/CODEX_WRAPPER_SCHEMA_FAIL/mapped/non-APPROVED/validatorOK, got rc=$router_rc crs=$crs fc=$fc has_mapped=$has_mapped dec=$dec v=$v"
        fi
    fi
fi

# --- SC-7: capsule target rejection via --run-bridge --live-transport ---
echo
echo "--- SC-7: capsule target → PLAN_TARGET_MUST_BE_ORIGINAL_PLAN ---"
_ex=0
out=$($BRIDGE run-bridge \
    --kind plan \
    --target "$CAPSULE_TARGET" \
    --cwd . \
    --out "$TMPDIR/sc7-out.json" \
    --live-transport \
    2>&1) || _ex=$?

if [[ $_ex -eq 1 ]] && echo "$out" | grep -q "PLAN_TARGET_MUST_BE_ORIGINAL_PLAN"; then
    pass "capsule target → exit 1 + PLAN_TARGET_MUST_BE_ORIGINAL_PLAN"
else
    fail "capsule target → expected exit 1 + PLAN_TARGET_MUST_BE_ORIGINAL_PLAN, got exit=$_ex: $(echo "$out" | head -3)"
fi

# --- SC-8: v2 templates now present → build-capsule succeeds (positive path) ---
echo
echo "--- SC-8: build-capsule --kind plan → capsule produced (v2 template present) ---"

# Verify plan v2 template EXISTS (补做完成后应存在)
V2_PLAN_TEMPLATE="templates/gd-plan-review-v2-template.md"
if [[ -f "$V2_PLAN_TEMPLATE" ]]; then
    pass "SC-8 prerequisite: v2 plan template present ($V2_PLAN_TEMPLATE)"
else
    fail "SC-8 prerequisite: v2 plan template MISSING at $V2_PLAN_TEMPLATE"
fi

_ex=0
out=$($BRIDGE build-capsule \
    --kind plan \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc8-out.json" \
    2>&1) || _ex=$?

if [[ $_ex -eq 0 ]] && echo "$out" | grep -qE "target_hash|capsule.*写入"; then
    pass "plan build-capsule (v2 template present) → exit 0 + capsule produced"
else
    fail "plan build-capsule → expected exit 0 + capsule, got exit=$_ex: $(echo "$out" | head -3)"
fi

# code_diff v2 template now exists — build-capsule should succeed with --no-compat-v1
echo
echo "--- SC-8: build-capsule --kind code_diff --no-compat-v1 → capsule produced (v2 template present) ---"
_ex=0
out=$($BRIDGE build-capsule \
    --kind code_diff \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc8-code-diff-out.json" \
    --no-compat-v1 \
    2>&1) || _ex=$?

if [[ $_ex -eq 0 ]] && echo "$out" | grep -qE "target_hash|capsule.*写入"; then
    pass "code_diff build-capsule --no-compat-v1 (v2 template present) → exit 0 + capsule produced"
else
    fail "code_diff build-capsule --no-compat-v1 → expected exit 0 + capsule, got exit=$_ex: $(echo "$out" | head -3)"
fi

# Verify execution_outcome is NOT blocked (v2 template exists)
echo
echo "--- SC-8: build-capsule --kind execution_outcome → NOT blocked (template exists) ---"
_ex=0
out=$($BRIDGE build-capsule \
    --kind execution_outcome \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc8-eo-out.json" \
    2>&1) || _ex=$?

if [[ $_ex -eq 0 ]] && echo "$out" | grep -qE "capsule.*写入|CAPSULE_BUILD|target_hash"; then
    pass "execution_outcome build-capsule → exit 0 (template exists, not blocked)"
elif echo "$out" | grep -q "V2_TEMPLATE_NOT_READY"; then
    fail "execution_outcome blocked by V2_TEMPLATE_NOT_READY (unexpected — should have template)"
else
    fail "execution_outcome → unexpected exit=$_ex: $(echo "$out" | head -3)"
fi

# --- SC-10: positive — plan target with mock writer → APPROVED ---
echo
echo "--- SC-10: plan target + mock writer → APPROVED via GD_WRITER_PATH_OVERRIDE ---"

# SC-10 uses --compat-v1 to bypass V2_TEMPLATE_NOT_READY and exercise the live path
_ex=0
out=$(GD_WRITER_PATH_OVERRIDE="$MOCK_WRITER" \
    GD_MOCK_RESULT_DIR="$TMPDIR/mock-results" \
    $BRIDGE run-bridge \
    --kind plan \
    --target "$GOOD_PLAN" \
    --cwd . \
    --out "$TMPDIR/sc10-out.json" \
    --live-transport \
    --compat-v1 \
    2>&1) || _ex=$?

if [[ $_ex -eq 0 ]] && echo "$out" | grep -q "GD_CODEX_BRIDGE_STATUS: approved"; then
    pass "plan + mock writer + --compat-v1 → exit 0 + GD_CODEX_BRIDGE_STATUS: approved"
elif echo "$out" | grep -q "APPROVED"; then
    pass "plan + mock writer + --compat-v1 → APPROVED (exit=$_ex)"
else
    fail "plan + mock writer + --compat-v1 → expected APPROVED, got exit=$_ex: $(echo "$out" | head -5)"
fi

# --- Summary ---
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "SC-7/SC-8/SC-10 (plan-routing): PASS"
    exit 0
else
    echo "SC-7/SC-8/SC-10 (plan-routing): FAIL"
    exit 1
fi
