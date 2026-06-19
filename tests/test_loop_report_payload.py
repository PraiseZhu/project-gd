"""Unit tests for plan-review codex evidence plumbing (handoff #3 fix, rev 2).

Locks the P1/P2 fixes:
  - codex_review_status is derived from the evidence TRIPLE (mapped file present +
    gd_review_decision + review_run_status), NOT just file existence. A readable
    mapped file carrying FAILED/degraded must surface as wrapper_schema_fail,
    never 'completed'.
  - conflict arbitration: an APPROVED convergence exit demotes when codex
    evidence is failed/constrained (transport_failed→FAILED,
    wrapper_schema_fail/requires_changes→REQUIRES_CHANGES).
  - 7-state matrix A-G + validator compatibility.

Run either way:
    python3 tests/test_loop_report_payload.py
    pytest tests/test_loop_report_payload.py
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PROJECT_ROOT, "scripts")
sys.path.insert(0, SCRIPTS)


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_merge = _load_module("gd_review_merge_loop_under_test", "gd-review-merge-and-fix-loop.py")
_router = _load_module("gd_review_router_under_test", "gd-review-router.py")
_validate = _load_module("gd_validate_route_report_under_test", "gd-validate-route-report.py")

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")
        if "PYTEST_CURRENT_TEST" in os.environ:
            raise AssertionError(label)


def _mapped(d, verdict="APPROVED", run_status="completed"):
    """A codex mapped JSON (what _run_bridge_job writes as bridge-r{N}-{lens}-mapped.json)."""
    return json.dumps({"gd_review_decision": verdict, "review_run_status": run_status, **d})


# ---------------------------------------------------------------------------
# _codex_review_status_from_evidence — the 7-state matrix (SC-2/SC-3, pure fn)
# ---------------------------------------------------------------------------
def test_codex_review_status_matrix():
    """SC-5 states A-G for the pure mapping function."""
    print("[_codex_review_status_from_evidence] 7-state matrix")
    f = _merge._codex_review_status_from_evidence
    # A / D / G: no evidence (file absent / unparseable) → transport_failed
    check(f(False, "APPROVED", "completed") == "transport_failed",
          "A: no evidence file → transport_failed")
    # B: APPROVED + completed → completed
    check(f(True, "APPROVED", "completed") == "completed",
          "B: APPROVED+completed → completed")
    # C: REQUIRES_CHANGES + completed → requires_changes
    check(f(True, "REQUIRES_CHANGES", "completed") == "requires_changes",
          "C: REQUIRES_CHANGES+completed → requires_changes")
    # E: mapped + verdict FAILED → wrapper_schema_fail (P1 core!)
    check(f(True, "FAILED", "completed") == "wrapper_schema_fail",
          "E: mapped+verdict FAILED → wrapper_schema_fail (NOT completed)")
    # F: mapped + APPROVED + degraded run → wrapper_schema_fail (P1 core!)
    check(f(True, "APPROVED", "degraded") == "wrapper_schema_fail",
          "F: APPROVED+degraded run → wrapper_schema_fail (NOT completed)")
    # extra: failed_to_run / failed run states
    check(f(True, "APPROVED", "failed_to_run") == "wrapper_schema_fail",
          "mapped+APPROVED+failed_to_run → wrapper_schema_fail")
    check(f(True, "APPROVED", "failed") == "wrapper_schema_fail",
          "mapped+APPROVED+failed → wrapper_schema_fail")
    check(f(True, "APPROVED", None) == "wrapper_schema_fail",
          "mapped+APPROVED+missing run_status → wrapper_schema_fail")
    check(f(True, "APPROVED", "bogus") == "wrapper_schema_fail",
          "mapped+APPROVED+unknown run_status → wrapper_schema_fail")
    check(f(True, "REQUIRES_CHANGES", None) == "wrapper_schema_fail",
          "mapped+REQUIRES_CHANGES+missing run_status → wrapper_schema_fail")
    # extra: completed_with_constraint → requires_changes (constrained, not clean)
    check(f(True, "APPROVED", "completed_with_constraint") == "requires_changes",
          "completed_with_constraint → requires_changes (not completed)")
    # extra: unknown verdict on readable file → wrapper_schema_fail (fail-closed)
    check(f(True, "WEIRD", "completed") == "wrapper_schema_fail",
          "unknown verdict on readable file → wrapper_schema_fail")
    # P1 negative lock: the failure states are NEVER 'completed'
    for verdict, run in [("APPROVED", "degraded"), ("FAILED", "completed"),
                         ("REQUIRES_CHANGES", "failed_to_run")]:
        check(f(True, verdict, run) != "completed",
              f"P1 lock: {verdict}/{run} must NOT be completed")


# ---------------------------------------------------------------------------
# _latest_codex_evidence — 3-tuple
# ---------------------------------------------------------------------------
def test_latest_codex_evidence_3tuple():
    print("[_latest_codex_evidence] 4-tuple (path, verdict, run_status, hash) + malformed")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        p, v, rs, h = _merge._latest_codex_evidence(d, 1)
        check(p is None and v == "FAILED" and rs is None and h is None,
              "no artifacts → (None, FAILED, None, None)")
        (d / "bridge-r1-codex_A-mapped.json").write_text(
            _mapped({"extra": 1}, verdict="REQUIRES_CHANGES", run_status="completed"))
        p, v, rs, h = _merge._latest_codex_evidence(d, 1)
        check(p is not None and v == "REQUIRES_CHANGES" and rs == "completed",
              "codex_A present → reads verdict + run_status")
        check(p.name == "bridge-r1-codex_A-mapped.json", "prefers codex_A")
        check(h is not None and len(h) == 64, "hash pre-computed (sha256 64-hex)")
        # fallback to codex_B, including run_status
        (d / "bridge-r1-codex_A-mapped.json").unlink()
        (d / "bridge-r1-codex_B-mapped.json").write_text(
            _mapped({}, verdict="APPROVED", run_status="degraded"))
        p, v, rs, h = _merge._latest_codex_evidence(d, 1)
        check(v == "APPROVED" and rs == "degraded", "fallback codex_B reads run_status")
        check(h is not None, "fallback returns hash too")
        # malformed → path NON-None (evidence present) + hash, so caller maps to
        # wrapper_schema_fail (NOT transport_failed). This aligns with _consume_and_merge.
        (d / "bridge-r2-codex_A-mapped.json").write_text("{not json")
        p, v, rs, h = _merge._latest_codex_evidence(d, 2)
        check(p is not None and v == "FAILED", "malformed → path present + verdict FAILED")
        check(h is not None, "malformed → hash still computed (no re-read needed)")
        crs = _merge._codex_review_status_from_evidence(p is not None, v, rs)
        check(crs == "wrapper_schema_fail", "malformed → wrapper_schema_fail (aligned with consumption)")
        # robust (MEDIUM-fix): malformed codex_A + valid codex_B → uses codex_B, doesn't discard
        (d / "bridge-r3-codex_A-mapped.json").write_text("{not json")
        (d / "bridge-r3-codex_B-mapped.json").write_text(
            _mapped({}, verdict="APPROVED", run_status="completed"))
        p, v, rs, h = _merge._latest_codex_evidence(d, 3)
        check(v == "APPROVED" and rs == "completed",
              "malformed codex_A + valid codex_B → falls through to codex_B")
        # round mismatch → None
        p, v, rs, h = _merge._latest_codex_evidence(d, 9)
        check(p is None, "wrong round → None")


# ---------------------------------------------------------------------------
# _write_convergence_exit_report — 4 exits + conflict arbitration (SC-1/SC-4)
# ---------------------------------------------------------------------------
def _exit_report(base_decision, mapped_verdict=None, mapped_run=None, last_round=1):
    """Run _write_convergence_exit_report in a FRESH tempdir (per case, so prior
    cases' mapped artifacts don't leak into the 'no evidence' cases). Returns
    the loop_report dict."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        plan = d / "plan.md"
        plan.write_text("# plan\n")
        if mapped_verdict is not None:
            (d / f"bridge-r{last_round}-codex_A-mapped.json").write_text(
                _mapped({}, verdict=mapped_verdict, run_status=mapped_run or "completed"))
        rp = _merge._write_convergence_exit_report(
            d, plan, base_decision, "test reason", last_round, "APPROVED")
        return json.loads(rp.read_text(encoding="utf-8"))


def test_convergence_exit_states():
    """SC-1/SC-4: each exit writes a router-globbable loop_report with correct
    decision + codex_review_status per the matrix."""
    print("[_write_convergence_exit_report] exit states + arbitration")
    # A: no evidence, base APPROVED → demote FAILED + transport_failed
    lrep = _exit_report("APPROVED")
    check(lrep["gd_review_decision"] == "FAILED", "A: no evidence+APPROVED → decision FAILED")
    check(lrep["codex_review_status"] == "transport_failed", "A: codex_review_status transport_failed")
    check(lrep["raw_result_path"] is None, "A: raw_result_path None")
    # B: APPROVED+completed evidence, base APPROVED → keep APPROVED + completed
    lrep = _exit_report("APPROVED", "APPROVED", "completed")
    check(lrep["gd_review_decision"] == "APPROVED", "B: APPROVED evidence → decision APPROVED")
    check(lrep["codex_review_status"] == "completed", "B: codex_review_status completed")
    check(lrep["raw_result_path"] is not None, "B: raw_result_path set (mapped exists)")
    # C: REQUIRES_CHANGES+completed, base REQUIRES_CHANGES → requires_changes
    lrep = _exit_report("REQUIRES_CHANGES", "REQUIRES_CHANGES", "completed")
    check(lrep["gd_review_decision"] == "REQUIRES_CHANGES", "C: decision REQUIRES_CHANGES")
    check(lrep["codex_review_status"] == "requires_changes", "C: codex_review_status requires_changes")
    # D: no evidence, base REQUIRES_CHANGES → demote FAILED + transport_failed
    lrep = _exit_report("REQUIRES_CHANGES")
    check(lrep["gd_review_decision"] == "FAILED", "D: no evidence+timeout → decision FAILED")
    check(lrep["codex_review_status"] == "transport_failed", "D: codex_review_status transport_failed")
    # E: mapped FAILED, base APPROVED → arbitrate REQUIRES_CHANGES + wrapper_schema_fail
    lrep = _exit_report("APPROVED", "FAILED", "completed")
    check(lrep["gd_review_decision"] == "REQUIRES_CHANGES", "E: FAILED verdict demotes APPROVED→REQUIRES_CHANGES")
    check(lrep["codex_review_status"] == "wrapper_schema_fail", "E: codex_review_status wrapper_schema_fail")
    check(lrep["codex_review_status"] != "completed", "E: NOT completed (P1)")
    # HIGH-fix lock: classification must be consistent with codex_review_status (was passing transport_status → contradiction)
    check(lrep["classification"] == "wrapper_schema_fail", "E: classification consistent (not transport_ok)")
    # F: mapped APPROVED+degraded, base APPROVED → wrapper_schema_fail + REQUIRES_CHANGES
    lrep = _exit_report("APPROVED", "APPROVED", "degraded")
    check(lrep["codex_review_status"] == "wrapper_schema_fail", "F: degraded run → wrapper_schema_fail")
    check(lrep["gd_review_decision"] == "REQUIRES_CHANGES", "F: demoted to REQUIRES_CHANGES")
    check(lrep["codex_review_status"] != "completed", "F: NOT completed (P1)")
    check(lrep["classification"] == "wrapper_schema_fail", "F: classification consistent (not transport_ok)")


def test_loop_report_is_router_globbable():
    print("[_write_convergence_exit_report] router glob match")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        plan = d / "plan.md"
        plan.write_text("# plan\n")
        rp = _merge._write_convergence_exit_report(d, plan, "APPROVED", "x", 1, "APPROVED")
        globs = sorted(d.glob("loop_report_*.json"))
        check(len(globs) == 1, f"router glob finds the written file (got {len(globs)})")
        check(rp.name.startswith("loop_report_") and rp.name.endswith(".json"),
               f"filename = loop_report_*.json (got {rp.name})")


# ---------------------------------------------------------------------------
# validator compatibility (SC-7)
# ---------------------------------------------------------------------------
def _route_report(decision, codex_review_status, evidence_path=None, evidence_hash=None):
    plan = evidence_path.parent / "plan.md" if evidence_path else Path("/tmp/plan.md")
    rr = {
        "schema_version": "2.0", "router_invocation_id": "test-001", "mode": "live",
        "review_target_kind": "plan_only", "decision": decision,
        "validator_signature": _router.VALIDATOR_SIGNATURE, "recorded_at": "2026-06-18T00:00:00Z",
        "plan_ref": str(plan), "plan_hash": "a" * 64,
        "raw_result_path": str(evidence_path) if evidence_path else None,
        "raw_result_hash": evidence_hash,
        "claude_review_origin": "supplied", "downstream_loop_report_path": None,
        "downstream_returncode": 0 if decision == "APPROVED" else 1,
        "codex_review_status": codex_review_status, "findings": [],
    }
    if evidence_path:
        rr["codex_mapped_result_path"] = str(evidence_path)
        rr["codex_mapped_result_hash"] = evidence_hash
    return rr


def test_validator_accepts_plan_codex_fields():
    """SC-7: plan_only route_reports carrying codex fields validate clean for
    each reachable (decision, codex_review_status) pair."""
    print("[validator] plan_only route_report codex-field compatibility")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        ev = d / "bridge-r1-codex_A-mapped.json"
        ev.write_text(_mapped({}, verdict="APPROVED"))
        evhash = hashlib.sha256(ev.read_bytes()).hexdigest()
        plan = d / "plan.md"; plan.write_text("# plan\n")
        phash = hashlib.sha256(plan.read_bytes()).hexdigest()
        cases = [
            ("APPROVED", "completed", True, ev, evhash, phash),       # B
            ("REQUIRES_CHANGES", "requires_changes", True, ev, evhash, phash),  # C
            ("REQUIRES_CHANGES", "wrapper_schema_fail", True, ev, evhash, phash),  # E
            ("FAILED", "transport_failed", False, None, None, phash),  # D (no raw_result)
        ]
        for decision, crs, has_ev, evidence, ehash, ph in cases:
            rr = _route_report(decision, crs, evidence, ehash)
            rr["plan_hash"] = ph
            if evidence:
                rr["plan_ref"] = str(plan)
            viol = _validate.validate_route_report(rr)
            bad = [v for v in viol if "codex" in v.lower() or "raw_result" in v.lower()]
            check(not bad,
                  f"({decision}/{crs}) → no codex/raw_result violations (got {bad})")
        # CRITICAL: APPROVED + wrapper_schema_fail MUST be rejected (the P1 mislabel)
        rr = _route_report("APPROVED", "wrapper_schema_fail", ev, evhash)
        rr["plan_hash"] = phash
        rr["plan_ref"] = str(plan)
        viol = _validate.validate_route_report(rr)
        check(any("codex_review_status" in v for v in viol),
              "APPROVED + wrapper_schema_fail correctly rejected by validator")


def test_consumption_approved_degraded_demotes():
    """Consumption path must not approve APPROVED+degraded codex evidence."""
    print("[_consume_and_merge] APPROVED+degraded demotion")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        plan = d / "plan.md"
        plan.write_text("# plan\n\nSC-1: demo\n", encoding="utf-8")
        claude = d / "claude.json"
        claude.write_text(json.dumps({
            "gd_review_decision": "APPROVED",
            "review_run_status": "completed",
            "findings": [],
        }), encoding="utf-8")
        codex = d / "codex-mapped.json"
        codex.write_text(_mapped({"findings": []}, verdict="APPROVED", run_status="degraded"), encoding="utf-8")
        out = d / "out"
        rc = _merge._consume_and_merge(plan, out, str(claude), None, str(codex), "auto", None)
        reports = sorted(out.glob("loop_report_*.json"))
        check(rc != 0, "APPROVED+degraded consumption exits non-zero")
        check(len(reports) == 1, "consumption writes one loop_report")
        lrep = json.loads(reports[-1].read_text(encoding="utf-8"))
        check(lrep["codex_review_status"] == "wrapper_schema_fail",
              "codex_review_status wrapper_schema_fail")
        check(lrep["classification"] == "wrapper_schema_fail",
              "classification wrapper_schema_fail")
        check(lrep["gd_review_decision"] != "APPROVED",
              "gd_review_decision is not APPROVED")


def run():
    for fn in [
        test_codex_review_status_matrix,
        test_latest_codex_evidence_3tuple,
        test_convergence_exit_states,
        test_loop_report_is_router_globbable,
        test_validator_accepts_plan_codex_fields,
        test_consumption_approved_degraded_demotes,
    ]:
        fn()
    print(f"\n{'=' * 50}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
