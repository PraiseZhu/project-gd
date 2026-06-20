#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/gd-review2-package-deliverable.sh"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

pass() { echo "  PASS: $*"; }
fail() { echo "  FAIL: $*" >&2; exit 1; }

cat > "$TMPDIR/controller-empty-mapped.json" <<'JSON'
{
  "review_kind": "execution_outcome",
  "final_verdict": "APPROVED",
  "baseline_unresolved_count": 0,
  "bridge_failure_count": 0,
  "mapped_results": []
}
JSON

cat > "$TMPDIR/controller-final-report.json" <<'JSON'
{
  "review_kind": "execution_outcome",
  "final_verdict": "APPROVED",
  "baseline_unresolved_count": 0,
  "bridge_failure_count": 0,
  "mapped_results": [
    {
      "path": "/tmp/codex_mapped_execution_outcome.json",
      "review_kind": "execution_outcome",
      "review_run_status": "completed",
      "gd_review_decision": "APPROVED",
      "findings_count": 0,
      "run_evidence_count": 1,
      "bridge_failure": false
    }
  ]
}
JSON

cat > "$TMPDIR/tests-evidence-weak.json" <<'JSON'
{
  "status": "green",
  "commands": [
    {
      "cmd": "python3 -m pytest tests/test_controller_deep.py -q",
      "exit": 0,
      "stdout_excerpt": "11 passed"
    }
  ]
}
JSON

cat > "$TMPDIR/tests-evidence.json" <<JSON
{
  "status": "green",
  "commands": [
    {
      "cmd": "python3 -m pytest tests/test_controller_deep.py -q",
      "cwd": "$ROOT",
      "exit": 0,
      "evidence_source": "command_rerun",
      "stdout_excerpt": "11 passed in 0.10s"
    }
  ]
}
JSON

echo "== package evidence gate =="

set +e
out="$(bash "$SCRIPT" \
  --conformance-status APPROVED \
  --tests-status green \
  --post-simplify-status green \
  --controller-report "$TMPDIR/controller-empty-mapped.json" \
  --dry-run 2>&1)"
rc=$?
set -e
if [[ "$rc" -ne 0 ]] && echo "$out" | grep -q -- "--tests-evidence"; then
  pass "green without tests evidence is rejected"
else
  fail "green without evidence should fail, rc=$rc output=$out"
fi

set +e
out="$(cd "$ROOT" && bash "$SCRIPT" \
  --conformance-status APPROVED \
  --tests-status green \
  --post-simplify-status green \
  --controller-report "$TMPDIR/controller-empty-mapped.json" \
  --tests-evidence "$TMPDIR/tests-evidence.json" \
  --dry-run 2>&1)"
rc=$?
set -e
if [[ "$rc" -ne 0 ]] && echo "$out" | grep -q "approved_empty_mapped_results"; then
  pass "APPROVED with empty mapped_results is rejected"
else
  fail "empty mapped_results should fail, rc=$rc output=$out"
fi

set +e
out="$(cd "$ROOT" && bash "$SCRIPT" \
  --conformance-status APPROVED \
  --tests-status green \
  --post-simplify-status green \
  --controller-report "$TMPDIR/controller-final-report.json" \
  --tests-evidence "$TMPDIR/tests-evidence-weak.json" \
  --dry-run 2>&1)"
rc=$?
set -e
if [[ "$rc" -ne 0 ]] && echo "$out" | grep -q "command_0_missing_cwd"; then
  pass "weak tests evidence is rejected"
else
  fail "weak tests evidence should fail, rc=$rc output=$out"
fi

set +e
out="$(cd "$ROOT" && bash "$SCRIPT" \
  --conformance-status APPROVED \
  --tests-status green \
  --post-simplify-status green \
  --controller-report "$TMPDIR/controller-final-report.json" \
  --tests-evidence "$TMPDIR/tests-evidence.json" \
  --dry-run 2>&1)"
rc=$?
set -e
if [[ "$rc" -eq 0 ]] && echo "$out" | grep -q "TESTS_STATUS_SOURCE: tests_evidence_json"; then
  pass "green with controller report and tests evidence is accepted"
else
  fail "green with evidence should pass, rc=$rc output=$out"
fi

echo "PACKAGE_EVIDENCE_SMOKE: PASS"
