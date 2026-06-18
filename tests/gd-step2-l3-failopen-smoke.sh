#!/usr/bin/env bash
# gd-step2-l3-failopen-smoke.sh
#
# Regression smoke for step-2-l3-failopen: close the L3-only fail-open holes in
# the four review-chain components. Each SC has NEGATIVE assertions (the
# fail-open hole is now closed → fail-closed) and POSITIVE assertions (the
# tightening did NOT misfire on a valid input).
#
#   SC-5  gd-review-merge-and-fix-loop.py
#     N1  bridge job failure → NON-EMPTY FAILED sentinel, never []
#     N2  both subprocess returncodes checked (run-bridge + parse-transport)
#     N8  Claude self-review load failure → exit 1, never silent []
#     #3  finding only resolved when its file was ACTUALLY modified
#   SC-6  gd-review-router.py
#     N3  mapped decision=None / FAILED → fail-closed, not completed/APPROVED
#     N4  merge-loop returncode!=0 → must not trust APPROVED from loop_report
#     P2  corrupt router descriptor vs genuine no_artifact → distinct outcome
#     +   `--self-test` still PASS
#   SC-7  gd-review-suite-controller.py + gd-aggregate-codex-cross-review.py
#     N5  bridge_exit!=0 (live) → verdict FAILED
#     N6  aggregate not generated → FAILED (no synthetic APPROVE)
#     +   closure_eligible MISSING defaults False; aggregate mapped parse-fail → FAILED
#
# Exit 0 = all pass. Self-contained; uses mktemp fixtures cleaned on exit; does
# not mutate the repo working tree.

set -euo pipefail

ROOT="/Users/praise/AI-Agent/Claude/projects/Project GD"
cd "$ROOT"

TMPROOT="$(mktemp -d -t gd-step2-failopen.XXXXXX)"
cleanup() { rm -rf "$TMPROOT"; }
trap cleanup EXIT

PASS=0
FAIL=0
note_pass() { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$1"; }
note_fail() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$1" >&2; }

run_case() {
  # run_case <label> <python-file>
  local label="$1" pyf="$2"
  if python3 "$pyf" >/dev/null 2>"$TMPROOT/err.log"; then
    note_pass "$label"
  else
    note_fail "$label"
    sed 's/^/        /' "$TMPROOT/err.log" >&2 || true
  fi
}

echo "=== gd-step2-l3-failopen-smoke ==="

# ---------------------------------------------------------------------------
# SC-5 — merge-and-fix-loop fail-closed
# ---------------------------------------------------------------------------
cat > "$TMPROOT/sc5.py" <<'PY'
import sys, importlib.util, tempfile
from pathlib import Path
ROOT = "/Users/praise/AI-Agent/Claude/projects/Project GD"
sys.path.insert(0, ROOT + "/scripts")
spec = importlib.util.spec_from_file_location("ml", ROOT + "/scripts/gd-review-merge-and-fix-loop.py")
ml = importlib.util.module_from_spec(spec); spec.loader.exec_module(ml)

class Fake:
    def __init__(self, rc, out="", err=""): self.returncode=rc; self.stdout=out; self.stderr=err

orig = ml.subprocess.run

# N2: non-zero run-bridge returncode -> non-empty FAILED sentinel (not [])
ml.subprocess.run = lambda *a, **k: Fake(2, "", "boom")
with tempfile.TemporaryDirectory() as d:
    res = ml._run_bridge_job(Path("plan.md"), Path("."), Path(d), 1, "codex_A", {})
assert res, "N2: bridge failure returned empty list (fail-open)"
assert res[0].get("category") == ml.BRIDGE_FAILURE_CATEGORY, "N2: not a BRIDGE_FAILURE sentinel"
assert res[0].get("bridge_failure") is True

# N1: arbitrary exception inside bridge job -> sentinel, never []
def _raise(*a, **k): raise RuntimeError("kaboom")
ml.subprocess.run = _raise
with tempfile.TemporaryDirectory() as d:
    res2 = ml._run_bridge_job(Path("plan.md"), Path("."), Path(d), 1, "codex_A", {})
assert res2 and res2[0].get("category") == ml.BRIDGE_FAILURE_CATEGORY, "N1: exception not fail-closed"
ml.subprocess.run = orig

# #3 NEGATIVE: finding NOT reported this round but file unmodified -> stays unresolved
bf = [{"id":"F001","file":"a.py","line":10,"category":"bug","status":"unresolved","round_history":[]}]
u, _ = ml.update_baseline_statuses(bf, [], 2, modified_files=set())
assert u == 1 and bf[0]["status"] == "unresolved", "#3: resolved without a real file modification"

# #3 POSITIVE: file modified AND not reported -> resolved
bf2 = [{"id":"F001","file":"a.py","line":10,"category":"bug","status":"unresolved","round_history":[]}]
u2, _ = ml.update_baseline_statuses(bf2, [], 2, modified_files={"a.py"})
assert u2 == 0 and bf2[0]["status"] == "resolved", "#3: valid fix not recognized as resolved"

# #3: bridge_failure sentinel never auto-resolved
sent = [{"id":"BR","file":"<bridge:codex_A>","category":ml.BRIDGE_FAILURE_CATEGORY,
         "status":"unresolved","bridge_failure":True,"round_history":[]}]
u3, _ = ml.update_baseline_statuses(sent, [], 2, modified_files={"<bridge:codex_a>"})
assert u3 == 1 and sent[0]["status"] == "unresolved", "#3: bridge sentinel was resolved"

# N8: missing/corrupt --claude-review aborts (exit 1), never silent []
ml._run_bridge_job = lambda *a, **k: []   # clean bridge so we reach the N8 branch
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    plan = d/"plan.md"; plan.write_text("# plan\n")
    try:
        ml.run_production_plan(str(plan), str(d), str(d/"missing.json"), None, None, "auto", None)
        raise AssertionError("N8: missing claude-review did not abort")
    except SystemExit as e:
        assert e.code == 1, "N8: missing claude-review wrong exit code"
    bad = d/"bad.json"; bad.write_text("{ not json")
    try:
        ml.run_production_plan(str(plan), str(d), str(bad), None, None, "auto", None)
        raise AssertionError("N8: corrupt claude-review did not abort")
    except SystemExit as e:
        assert e.code == 1, "N8: corrupt claude-review wrong exit code"

print("SC-5 OK")
PY
run_case "SC-5  merge-loop N1/N2/N8/#3 (fail-closed + positive)" "$TMPROOT/sc5.py"

# ---------------------------------------------------------------------------
# SC-6 — router fail-closed
# ---------------------------------------------------------------------------
cat > "$TMPROOT/sc6.py" <<'PY'
import sys, importlib.util, tempfile, json
from pathlib import Path
ROOT = "/Users/praise/AI-Agent/Claude/projects/Project GD"
sys.path.insert(0, ROOT + "/scripts")
spec = importlib.util.spec_from_file_location("rt", ROOT + "/scripts/gd-review-router.py")
rt = importlib.util.module_from_spec(spec); spec.loader.exec_module(rt)

class Fake:
    def __init__(self, rc, out="", err=""): self.returncode=rc; self.stdout=out; self.stderr=err

# N3: decision=None and FAILED must NOT become completed/APPROVED; APPROVED still passes
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    target = d/"exec.json"; target.write_text(json.dumps({"x":1}))
    transport = d/"raw.result"; transport.write_text("raw")

    def make_run(decision):
        def _run(cmd, *a, **k):
            if "run-bridge" in cmd:
                return Fake(0, f"TRANSPORT_RESULT: {transport}\n")
            if "parse-transport" in cmd:
                Path(cmd[cmd.index("--out")+1]).write_text(
                    json.dumps({"gd_review_decision": decision, "findings": []}))
                return Fake(0, "")
            return Fake(0, "")
        return _run

    rt.subprocess.run = make_run(None)
    r = rt._run_live_codex_bridge("execution_outcome", target, d, "iid12345678", 60)
    assert r["status"] != "completed" and r["decision"] == "FAILED", "N3: None mapped became completed/APPROVED"

    rt.subprocess.run = make_run("FAILED")
    r = rt._run_live_codex_bridge("execution_outcome", target, d, "iid12345678", 60)
    assert r["status"] != "completed" and r["decision"] == "FAILED", "N3: FAILED mapped became completed"

    rt.subprocess.run = make_run("APPROVED")  # POSITIVE
    r = rt._run_live_codex_bridge("execution_outcome", target, d, "iid12345678", 60)
    assert r["status"] == "completed" and r["decision"] == "APPROVED", "N3: valid APPROVED misfired"

# N4: merge-loop returncode!=0 must not yield APPROVED from a stale loop_report
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    target = d/"plan.md"; target.write_text("# plan\n")
    claude = d/"cr.json"; claude.write_text(json.dumps({"findings":[]}))
    def fake_run(cmd, *a, **k):
        (d/"loop_report_stale.json").write_text(json.dumps({"gd_review_decision":"APPROVED"}))
        return Fake(1)
    rt.subprocess.run = fake_run
    rt._validate_route_report_file = lambda rp: 0
    rc = rt._run_live_plan_review(target, d, "iid12345678", str(claude), None, None, "auto", None)
    assert rc == 1, "N4: returned APPROVED despite merge-loop rc!=0"
    rep = json.loads(sorted(d.glob("route_report_*.json"))[-1].read_text())
    assert rep["decision"] == "FAILED", "N4: route report shows APPROVED despite rc!=0"

# P2: corrupt descriptor sentinel distinct from genuine no_artifact
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    corrupt = d/"desc.json"
    corrupt.write_text(json.dumps({"router_version":"1","artifacts":"NOT_A_DICT"}))
    assert rt.detect_review_target_kind(corrupt) == rt.CORRUPT_DESCRIPTOR_SENTINEL, "P2: corrupt not distinguished"
    empty = d/"emptydir"; empty.mkdir()
    assert rt.detect_review_target_kind(empty) == "no_artifact", "P2: genuine no_artifact misclassified"

print("SC-6 OK")
PY
run_case "SC-6  router N3/N4/P2 (fail-closed + positive)" "$TMPROOT/sc6.py"

# SC-6 router --self-test must still PASS
if python3 scripts/gd-review-router.py --self-test >/dev/null 2>"$TMPROOT/st.log"; then
  note_pass "SC-6  router --self-test"
else
  note_fail "SC-6  router --self-test"
  sed 's/^/        /' "$TMPROOT/st.log" >&2 || true
fi

# ---------------------------------------------------------------------------
# SC-7 — suite-controller + aggregate fail-closed
# ---------------------------------------------------------------------------
cat > "$TMPROOT/sc7.py" <<'PY'
import sys, importlib.util, tempfile, json
from pathlib import Path
ROOT = "/Users/praise/AI-Agent/Claude/projects/Project GD"
sys.path.insert(0, ROOT + "/scripts")
spec = importlib.util.spec_from_file_location("ctrl", ROOT + "/scripts/gd-review-suite-controller.py")
ctrl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctrl)
spec2 = importlib.util.spec_from_file_location("agg", ROOT + "/scripts/gd-aggregate-codex-cross-review.py")
agg = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(agg)

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    # closure_eligible MISSING -> default False -> FAILED (N6-adjacent fail-closed)
    m = d/"m.json"; m.write_text(json.dumps({"aggregate_summary": {"transport_failed": 0}}))
    v, b = ctrl._secondary_gate(m)
    assert v == "FAILED", "closure_eligible missing did not default to False"

    # closure_eligible True, no blockers -> APPROVED (POSITIVE)
    ok = d/"ok.json"; ok.write_text(json.dumps({"aggregate_summary": {"closure_eligible": True}}))
    v2, _ = ctrl._secondary_gate(ok)
    assert v2 == "APPROVED", "valid eligible aggregate misfired to FAILED"

    # N6: aggregate file missing -> FAILED AGGREGATE_MISSING
    v3, b3 = ctrl._secondary_gate(d/"nope.json")
    assert v3 == "FAILED" and "AGGREGATE_MISSING" in b3, "N6: missing aggregate not blocked"

    # aggregate mapped parse-fail -> decision FAILED + requires_changes
    bad = d/"bad.json"; bad.write_text("{ not json")
    (d/"t.md").write_text("# t")
    job = {"queue_job_id":"j1","target_role":"master_plan","primary_target":str(d/"t.md"),
           "review_kind":"plan","mapped_result_path":str(bad)}
    entry = agg.build_aggregate_job(job, Path("."))
    assert entry["gd_review_decision"] == "FAILED", "aggregate: corrupt mapped not -> FAILED"
    assert entry["codex_requires_changes"] is True

    # aggregate valid mapped -> decision preserved (POSITIVE)
    good = d/"good.json"; good.write_text(json.dumps({"gd_review_decision":"APPROVED"}))
    job2 = {"queue_job_id":"j2","target_role":"step_1","primary_target":str(d/"t.md"),
            "review_kind":"plan","mapped_result_path":str(good)}
    entry2 = agg.build_aggregate_job(job2, Path("."))
    assert entry2["gd_review_decision"] == "APPROVED", "aggregate: valid mapped not preserved"

print("SC-7 OK")
PY
run_case "SC-7  suite-controller + aggregate (fail-closed + positive)" "$TMPROOT/sc7.py"

# SC-7 N5/N6 end-to-end via fixtures: APPROVED fixture passes, FAILED fixture blocked
APPR_OUT="$TMPROOT/appr"
if python3 scripts/gd-review-suite-controller.py \
      --fixture fixtures/review-chain/suite-controller/approved-v1-suite.json \
      --out-dir "$APPR_OUT" >"$TMPROOT/appr.log" 2>&1 \
   && grep -q "SUITE_CONTROLLER_VERDICT: APPROVED" "$TMPROOT/appr.log"; then
  note_pass "SC-7  approved fixture → exit 0 + verdict APPROVED (positive)"
else
  note_fail "SC-7  approved fixture → exit 0 + verdict APPROVED (positive)"
  sed 's/^/        /' "$TMPROOT/appr.log" >&2 || true
fi

cat > "$TMPROOT/failed-suite.json" <<'JSON'
{
  "target_set_id": "sc7-failed-test",
  "kind": "plan",
  "compat_v1": true,
  "jobs": [
    {
      "queue_job_id": "sc7-failed-test-master-plan",
      "target_role": "master_plan",
      "primary_target": "fixtures/review-chain/suite-controller/targets/master-plan.md",
      "simulated_decision": "FAILED",
      "simulated_run_status": "degraded",
      "simulated_target_hash": "e57ec192067c67a75eda4fb17779ac585e473a21675227aaf391877524b090cf"
    }
  ]
}
JSON
if python3 scripts/gd-review-suite-controller.py \
      --fixture "$TMPROOT/failed-suite.json" \
      --out-dir "$TMPROOT/fail" >"$TMPROOT/fail.log" 2>&1; then
  note_fail "SC-7  FAILED-decision fixture → blocked (exit !=0)"
else
  if grep -q "SUITE_CONTROLLER_VERDICT: FAILED" "$TMPROOT/fail.log"; then
    note_pass "SC-7  FAILED-decision fixture → blocked (exit !=0)"
  else
    note_fail "SC-7  FAILED-decision fixture → blocked (verdict not FAILED)"
    sed 's/^/        /' "$TMPROOT/fail.log" >&2 || true
  fi
fi

# ---------------------------------------------------------------------------
echo
echo "=== summary: PASS=$PASS FAIL=$FAIL ==="
if [ "$FAIL" -ne 0 ]; then
  echo "gd-step2-l3-failopen-smoke: FAIL" >&2
  exit 1
fi
echo "gd-step2-l3-failopen-smoke: PASS"
exit 0
