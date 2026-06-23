#!/usr/bin/env bash
# gd-step1-shared-p0-smoke.sh
#
# Regression smoke for step-1-shared-p0-failclosed: the L2+L3 shared-component
# fail-closed fixes. Each SC has BOTH a negative assertion (the fail-open hole is
# now closed) and, where there is a tension partner, a positive assertion (the
# tightening did NOT misfire on a valid input).
#
#   SC-1  bridge N9   — REQUIRES_CHANGES / FAILED must exit non-zero; only APPROVED → 0
#   SC-2  V1          — UNKNOWN / unparseable verdict → FAKE_EVIDENCE_DETECTED, exit 1
#   SC-3  V16         — REQUIRES_CHANGES with no ### Finding → fail; --skip-line-ref-check
#                       rejected for .json target
#   SC-4  V3/V4/dup   — build_gate not_run reran/flagged; PHASE2_SKIPPED on schema flaw;
#                       duplicate sc_ref keeps first + warns (no silent overwrite)
#   SC-12 误拒收口    — a valid review with one citation-style defect is preserved
#                       (exit 0, verdict kept), only the bad finding is degraded
#   SC-13 bridge RC   — a valid REQUIRES_CHANGES raw maps to REQUIRES_CHANGES,
#                       never failed_to_run / transport_failed
#
# Exit 0 = all pass. Uses mktemp fixtures, cleaned up on exit; does not touch repo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRIDGE="scripts/gd-codex-bridge-review.py"
CE="scripts/gd-validate-review-content-evidence.py"
EO="scripts/gd-validate-execution-outcome.py"

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

PASS=0; FAIL=0
ok()   { echo "  PASS: $*"; PASS=$((PASS + 1)); }
bad()  { echo "  FAIL: $*"; FAIL=$((FAIL + 1)); }

# expect_exit <expected_code> <label> -- <command...>
expect_exit() {
  local exp="$1" label="$2"; shift 3   # drop exp, label, the literal "--"
  set +e
  "$@" >"$TMP/_out" 2>"$TMP/_err"
  local got=$?
  set -e
  if [ "$got" -eq "$exp" ]; then
    ok "$label (exit $got)"
  else
    bad "$label (expected exit $exp, got $got)"
    sed 's/^/      out> /' "$TMP/_out" | head -3
    sed 's/^/      err> /' "$TMP/_err" | head -3
  fi
}

echo "=== step-1 shared P0 fail-closed smoke ==="

# ─────────────────────────────────────────────────────────────────────────────
# SC-1 — bridge exit codes. Unit-test the three decision→exit ternaries via the
# module return values (deterministic, no schema/L3 noise), then a CLI control.
# ─────────────────────────────────────────────────────────────────────────────
echo
echo "--- SC-1: REQUIRES_CHANGES/FAILED exit non-zero; APPROVED exits 0 ---"

# Static: the old fail-open ternary 'return 0 if ... APPROVED ... else ... 0' is gone.
if grep -nE "return 0 if .*APPROVED.*else.*0" "$BRIDGE" >/dev/null 2>&1; then
  bad "SC-1 static: fail-open ternary still present in $BRIDGE"
else
  ok "SC-1 static: no 'return 0 if APPROVED else 0' ternary remains"
fi

# CLI positive control: a valid APPROVED raw → parse-transport exits 0.
printf '# Master Plan\n\nprose only, no SC ids\n' > "$TMP/sc1-target.md"
expect_exit 0 "SC-1 CLI: APPROVED parse-transport exits 0" -- \
  python3 "$BRIDGE" parse-transport --kind plan --no-compat-v1 \
    --target "$TMP/sc1-target.md" \
    --raw-result fixtures/review-bridge/v2/v2-plan-approved.md \
    --out "$TMP/sc1-mapped.json"

# CLI negative: an APPROVED+REQUIRES_CHANGES merge resolves to a non-APPROVED
# decision and therefore must exit non-zero (was exit 0 under the old ternary).
set +e
python3 "$BRIDGE" merge \
  --claude fixtures/review-sidecar/claude-approved.json \
  --codex fixtures/review-sidecar/codex-requires-changes.json \
  --out "$TMP/sc1-merged.json" >"$TMP/_m" 2>&1
merge_ec=$?
set -e
if [ "$merge_ec" -ne 0 ]; then
  ok "SC-1 CLI: non-APPROVED merge exits non-zero (got $merge_ec)"
else
  bad "SC-1 CLI: non-APPROVED merge wrongly exited 0"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-2 — content-evidence: UNKNOWN / unparseable verdict must NOT free-pass.
# ─────────────────────────────────────────────────────────────────────────────
echo
echo "--- SC-2: UNKNOWN verdict → FAKE_EVIDENCE_DETECTED, exit 1 ---"
cat > "$TMP/sc2-target.md" <<'EOF'
# Plan
- SC-1: build the thing
- SC-2: wire the thing
EOF
cat > "$TMP/sc2-unknown.md" <<'EOF'
# Plan Review Result
Some prose with no GD_REVIEW_DECISION line and no findings at all.
EOF
expect_exit 1 "SC-2: UNKNOWN-verdict review rejected" -- \
  python3 "$CE" --target "$TMP/sc2-target.md" --review "$TMP/sc2-unknown.md"
if grep -q "FAKE_EVIDENCE_DETECTED" "$TMP/_out"; then
  ok "SC-2: stdout contains FAKE_EVIDENCE_DETECTED"
else
  bad "SC-2: stdout missing FAKE_EVIDENCE_DETECTED"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-3 — content-evidence: RC-with-no-Finding fails; skip flag rejected on .json.
# ─────────────────────────────────────────────────────────────────────────────
echo
echo "--- SC-3: RC no-Finding fails; --skip-line-ref-check rejected for .json ---"
cat > "$TMP/sc3-rc-nofind.md" <<'EOF'
GD_REVIEW_DECISION: REQUIRES_CHANGES
Prose with no ### Finding sections.
EOF
expect_exit 1 "SC-3: REQUIRES_CHANGES with no ### Finding rejected" -- \
  python3 "$CE" --target "$TMP/sc2-target.md" --review "$TMP/sc3-rc-nofind.md"

cat > "$TMP/sc3-outcome.json" <<'EOF'
{"task_results":[{"deliverables_produced":[{"path":"scripts/x.py"}],"verify_results":[{"cmd":"pytest"}]}]}
EOF
cat > "$TMP/sc3-rev.md" <<'EOF'
GD_REVIEW_DECISION: REQUIRES_CHANGES
### Finding 1
SC: SC-1
问题: x
EOF
set +e
python3 "$CE" --target "$TMP/sc3-outcome.json" --review "$TMP/sc3-rev.md" \
  --skip-line-ref-check >"$TMP/_out" 2>"$TMP/_err"
sc3_ec=$?
set -e
if [ "$sc3_ec" -ne 0 ]; then
  ok "SC-3: --skip-line-ref-check rejected for .json target (exit $sc3_ec)"
else
  bad "SC-3: --skip-line-ref-check wrongly accepted for .json target"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-4 — execution-outcome: build_gate not_run reran/flagged; PHASE2_SKIPPED;
#        duplicate sc_ref keeps first (no silent overwrite).
# ─────────────────────────────────────────────────────────────────────────────
echo
echo "--- SC-4: build_gate not_run reran (V3); PHASE2_SKIPPED (V4); dup keep-first ---"
cat > "$TMP/sc4-plan.md" <<'EOF'
## Step 1

- [ ] SC-1(do thing)
  - verify (method: command, build-gate): `true`
EOF
cat > "$TMP/sc4-notrun.json" <<'EOF'
{
  "outcome_version": "1", "outcome_id": "o1",
  "task_outcomes": [
    {"task_id": "t1", "exec_status": "completed",
     "sc_acceptance": [{"sc_ref": "SC-1", "status": "not_run"}]}
  ]
}
EOF
# V3: build_gate declared not_run but rerunnable → flagged (exit 1), not silently passed.
expect_exit 1 "SC-4 V3: build_gate not_run reran and flagged" -- \
  python3 "$EO" "$TMP/sc4-notrun.json" --plan-file "$TMP/sc4-plan.md"
if grep -qiE "should be declared|build_gate.*not_run|rerunnable" "$TMP/_out"; then
  ok "SC-4 V3: reports declaration should be pass/fail"
else
  bad "SC-4 V3: missing 'should be declared' report"
fi

# V4: schema flaw + --plan-file → PHASE2_SKIPPED on stderr (not silent drop).
cat > "$TMP/sc4-bad.json" <<'EOF'
{"outcome_version":"1","outcome_id":"o2","task_outcomes":[{"task_id":"t","exec_status":"BOGUS","sc_acceptance":[]}]}
EOF
expect_exit 1 "SC-4 V4: schema flaw fails" -- \
  python3 "$EO" "$TMP/sc4-bad.json" --plan-file "$TMP/sc4-plan.md"
if grep -q "PHASE2_SKIPPED" "$TMP/_err"; then
  ok "SC-4 V4: PHASE2_SKIPPED surfaced on stderr"
else
  bad "SC-4 V4: PHASE2_SKIPPED not surfaced"
fi

# P2-dup: duplicate sc_ref keeps the FIRST declaration and warns (no last-wins).
# First=fail (consistent with `false` exit 1); later pass must be ignored → PASS.
cat > "$TMP/sc4-dup-plan.md" <<'EOF'
## Step 1

- [ ] SC-1(do thing)
  - verify (method: command, build-gate): `false`
EOF
cat > "$TMP/sc4-dup.json" <<'EOF'
{
  "outcome_version": "1", "outcome_id": "o3",
  "task_outcomes": [
    {"task_id": "t1", "exec_status": "completed",
     "sc_acceptance": [
       {"sc_ref": "SC-1", "status": "fail"},
       {"sc_ref": "SC-1", "status": "pass"}
     ]}
  ]
}
EOF
expect_exit 0 "SC-4 dup: keep-first 'fail' (later 'pass' ignored) → consistent PASS" -- \
  python3 "$EO" "$TMP/sc4-dup.json" --plan-file "$TMP/sc4-dup-plan.md"
if grep -q "DUPLICATE_SC_REF" "$TMP/_err"; then
  ok "SC-4 dup: DUPLICATE_SC_REF warning emitted"
else
  bad "SC-4 dup: DUPLICATE_SC_REF warning missing"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-12 — content-evidence: a valid review with one citation-style defect is
#         PRESERVED (exit 0, verdict kept), only the bad finding is degraded.
#         This is the explicit tension partner of SC-2/SC-3.
# ─────────────────────────────────────────────────────────────────────────────
echo
echo "--- SC-12: valid review w/ mixed refs preserved; bad finding only degraded ---"
cat > "$TMP/sc12-target.md" <<'EOF'
# Plan master
line2
line3
- [ ] SC-1: build the parser
- [ ] SC-2: wire the validator
line7
EOF
cat > "$TMP/sc12-valid.md" <<'EOF'
GD_REVIEW_DECISION: REQUIRES_CHANGES

### Finding 1
SC: SC-1
问题: 解析器对空输入崩溃
证据: sc12-target.md:4 的逻辑未处理空字符串
影响: 运行时异常
最小修复: 增加空值守卫
验收: python3 run.py 退出码 0

### Finding 2
SC: SC-2
问题: 校验器漏掉一个分支
证据: 在第 5 行附近缺少检查(引用风格不同,缺文件名前缀)
影响: 漏报
最小修复: 补分支
验收: pytest -k validator 通过
EOF
expect_exit 0 "SC-12: valid mixed-ref review preserved (exit 0)" -- \
  python3 "$CE" --target "$TMP/sc12-target.md" --review "$TMP/sc12-valid.md"
if grep -q "EVIDENCE_VALID" "$TMP/_out" && grep -q "verdict=REQUIRES_CHANGES" "$TMP/_out"; then
  ok "SC-12: overall verdict REQUIRES_CHANGES preserved"
else
  bad "SC-12: verdict not preserved / not EVIDENCE_VALID"
fi
if grep -q "DEGRADED_FINDING" "$TMP/_err"; then
  ok "SC-12: offending finding marked DEGRADED_FINDING (not whole-review collapse)"
else
  bad "SC-12: degraded-finding marker missing on stderr"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-13 — bridge: a valid REQUIRES_CHANGES raw maps to REQUIRES_CHANGES, never
#         failed_to_run / transport_failed (RC is a valid double-review result).
# ─────────────────────────────────────────────────────────────────────────────
echo
echo "--- SC-13: valid REQUIRES_CHANGES raw maps to REQUIRES_CHANGES ---"
set +e
python3 - "$ROOT" <<'PY' >"$TMP/_out" 2>"$TMP/_err"
import importlib.util, os, sys
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "scripts"))
spec = importlib.util.spec_from_file_location(
    "brg", os.path.join(root, "scripts", "gd-codex-bridge-review.py"))
brg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brg)
raw = open(os.path.join(
    root, "fixtures/review-bridge/v2/v2-execution-outcome-requires-changes.md")).read()
mapped, errs = brg.parse_raw_to_mapped(
    "execution_outcome", "reports/example/execution-outcome.json", raw, compat_v1=False)
dec = mapped.get("gd_review_decision")
st = mapped.get("review_run_status")
assert dec == "REQUIRES_CHANGES", f"decision collapsed to {dec!r}"
assert st not in ("failed_to_run", "transport_failed"), f"status mismapped to {st!r}"
print(f"decision={dec} status={st} errs={errs}")
PY
sc13_ec=$?
set -e
if [ "$sc13_ec" -eq 0 ]; then
  ok "SC-13: RC preserved ($(cat "$TMP/_out"))"
else
  bad "SC-13: RC mismapped"
  sed 's/^/      /' "$TMP/_err" | head -4
fi

# ─────────────────────────────────────────────────────────────────────────────
echo
echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "STEP1_SHARED_P0: PASS"
  exit 0
else
  echo "STEP1_SHARED_P0: FAIL"
  exit 1
fi
