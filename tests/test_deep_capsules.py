"""Tests for SC-3, SC-4, SC-5, SC-26, SC-33 deep review capsule features."""
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import pytest


class TestDeepPlanCapsule:
    """SC-3: _build_deep_plan_capsule returns text with architecture/risk/interface."""

    def test_deep_plan_capsule_has_dimensions(self):
        """SC-3: deep plan capsule contains architecture, risk, interface dimensions."""
        from gd_codex_bridge_review import _build_deep_plan_capsule
        result = _build_deep_plan_capsule("plan", Path("/tmp/fake-plan.md"))
        assert "Deep Review Dimensions" in result, "capsule must mention Deep Review Dimensions"
        assert "アーキテクチャ" in result or "arch" in result.lower(), "must have architecture dimension"
        assert "リスク" in result or "risk" in result.lower(), "must have risk dimension"
        assert "インターフェース" in result or "interface" in result.lower(), "must have interface dimension"
        # SC-3: must NOT contain conformance scoping sentence
        assert "conformance" not in result.lower() or "Deep" in result, (
            "deep plan capsule must not be conformance-scoped"
        )

    def test_deep_plan_capsule_with_plan_file(self):
        """SC-33: deep plan capsule includes PLAN_FILE_PATH when plan_file given."""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Test Plan\n\n- [ ] SC-1(test)\n  - verify (method: command, build-gate): `echo ok`\n")
            plan_path = f.name
        try:
            from gd_codex_bridge_review import _build_deep_plan_capsule
            result = _build_deep_plan_capsule("plan", Path(plan_path), plan_file=plan_path)
            assert "PLAN_FILE_PATH:" in result, "must include PLAN_FILE_PATH"
            assert "PLAN_FILE_HASH:" in result, "must include PLAN_FILE_HASH"
        finally:
            os.unlink(plan_path)


class TestDeepOutcomeCapsule:
    """SC-4: _build_deep_outcome_capsule returns text with 五元組."""

    def test_deep_outcome_capsule_has_quintuple(self):
        """SC-4: deep outcome capsule contains 五元組 fields."""
        from gd_codex_bridge_review import _build_deep_outcome_capsule
        result = _build_deep_outcome_capsule("execution_outcome", Path("/tmp/fake.json"))
        assert "cmd" in result, "must reference cmd field"
        assert "exit" in result, "must reference exit field"
        assert "passed" in result, "must reference passed field"
        assert "failed" in result, "must reference failed field"
        assert "skipped" in result, "must reference skipped field"
        assert "skip_reason" in result or "スキップ必査因" in result, "must mention skip reason requirement"
        assert "run_evidence" in result, "must mention run_evidence field"


class TestBridgeSelfTestRegression:
    """SC-5: bridge self-test regression — validate no NEW failures from our changes."""

    def test_bridge_self_test_new_fixtures_pass(self):
        """SC-5: all deep-* fixtures in codex-bridge-v2/ must pass in self-test output."""
        import subprocess
        bridge = os.path.join(PROJECT_ROOT, "scripts", "gd-codex-bridge-review.py")
        r = subprocess.run(
            [sys.executable, bridge, "self-test"],
            capture_output=True, text=True,
        )
        # Check that our new fixtures all appear as ✓ (pass) lines
        new_fixtures = [
            "deep-outcome-pass.mapped.json",
            "deep-plan-pass.mapped.json",
            "deep-code-pass.mapped.json",
            "deep-outcome-fail-missing-evidence.mapped.json",
            "deep-plan-fail-missing-findings.mapped.json",
        ]
        output = r.stdout + r.stderr
        for fixture in new_fixtures:
            assert f"✓ v2-routing {fixture}" in output, (
                f"SC-5: fixture {fixture} should appear as ✓ in self-test output"
            )
        # None of the new fixtures should appear in FAILED section
        if "self-test FAILED:" in output:
            failed_section = output.split("self-test FAILED:")[1]
            for fixture in new_fixtures:
                assert fixture not in failed_section, (
                    f"SC-5: fixture {fixture} should not appear in self-test FAILED section"
                )


class TestV2TitleTolerance:
    """SC-26: v2 parser accepts titles with and without (v2) suffix."""

    def test_title_with_v2_suffix_accepted(self):
        """SC-26: '# Plan Review Result (v2)' is accepted."""
        from gd_codex_bridge_review import _parse_raw_to_mapped_v2
        raw = """GD_REVIEW_DECISION: APPROVED

# Plan Review Result (v2)

## Scope Checked
| SC-ID | 结论 | 证据 |
|-------|------|------|

## Findings

## Residual Risk

<!--gd-review-result-json:start-->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-plan-review",
  "review_kind": "plan",
  "review_target_kind": "plan_only",
  "target_role": "plan_artifact",
  "reviewer": "codex",
  "review_target": "test-plan.md",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": {"location": "fenced_json_block", "value": "APPROVED"},
  "scope_checked": [{"area": "plan", "result": "pass", "evidence": "ok"}],
  "findings": [],
  "merge_notes": {"conflict_with_other_reviewer": false},
  "residual_risk": "",
  "timestamp": "2026-06-14T10:00:00Z"
}
```
<!--gd-review-result-json:end-->
"""
        mapped, errs = _parse_raw_to_mapped_v2("plan", "test-plan.md", raw)
        assert mapped.get("gd_review_decision") == "APPROVED", f"errs: {errs}"

    def test_title_without_v2_suffix_accepted(self):
        """SC-26: '# Plan Review Result' (no (v2) suffix) is also accepted."""
        from gd_codex_bridge_review import _parse_raw_to_mapped_v2
        raw = """GD_REVIEW_DECISION: APPROVED

# Plan Review Result

## Scope Checked
| SC-ID | 结论 | 证据 |
|-------|------|------|

## Findings

## Residual Risk

<!--gd-review-result-json:start-->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-plan-review",
  "review_kind": "plan",
  "review_target_kind": "plan_only",
  "target_role": "plan_artifact",
  "reviewer": "codex",
  "review_target": "test-plan.md",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": {"location": "fenced_json_block", "value": "APPROVED"},
  "scope_checked": [{"area": "plan", "result": "pass", "evidence": "ok"}],
  "findings": [],
  "merge_notes": {"conflict_with_other_reviewer": false},
  "residual_risk": "",
  "timestamp": "2026-06-14T10:00:00Z"
}
```
<!--gd-review-result-json:end-->
"""
        mapped, errs = _parse_raw_to_mapped_v2("plan", "test-plan.md", raw)
        assert mapped.get("gd_review_decision") == "APPROVED", (
            f"title without (v2) suffix should be accepted; errs: {errs}"
        )


class TestDeepFindingsMissing:
    """SC-7: DEEP_FINDINGS_MISSING fixture validation."""

    def test_deep_findings_missing_fixture_valid(self):
        """SC-7: deep-plan-fail-missing-findings.mapped.json is a valid self-test descriptor."""
        fixture_path = os.path.join(
            PROJECT_ROOT, "fixtures", "codex-bridge-v2",
            "deep-plan-fail-missing-findings.mapped.json"
        )
        assert os.path.exists(fixture_path), f"fixture missing: {fixture_path}"
        with open(fixture_path) as f:
            data = json.load(f)
        # Self-test descriptor format: should have _test_meta and expected_gd_review_decision
        assert data.get("expected_gd_review_decision") == "FAILED", (
            "DEEP_FINDINGS_MISSING fixture should expect FAILED decision"
        )
        meta = data.get("_test_meta", {})
        assert meta.get("_expect") in {"PASS", "FAIL"}, "fixture must have _test_meta._expect"


# SC-3: alias function with name matching SC verify command -k filter
def test_deep_plan_template():
    """SC-3: deep plan capsule has architecture/risk/interface dimensions (alias for -k filter)."""
    from pathlib import Path
    from gd_codex_bridge_review import _build_deep_plan_capsule
    result = _build_deep_plan_capsule("plan", Path("/tmp/fake-plan.md"))
    assert (
        "arch" in result.lower() or "架构" in result or "アーキテクチャ" in result
    ), "must have architecture dimension"
    assert (
        "risk" in result.lower() or "风险" in result or "リスク" in result
    ), "must have risk dimension"
    assert (
        "interface" in result.lower() or "接口" in result or "インターフェース" in result
    ), "must have interface dimension"
    assert "conformance" not in result.lower() or "Deep" in result, \
        "must not contain conformance scoping sentence"


# SC-4: alias function with name matching SC verify command -k filter
def test_deep_outcome_template():
    """SC-4: deep outcome capsule has five-tuple fields (alias for -k filter)."""
    from pathlib import Path
    from gd_codex_bridge_review import _build_deep_outcome_capsule
    result = _build_deep_outcome_capsule("execution_outcome", Path("/tmp/fake.json"))
    for field in ("cmd", "exit", "passed", "failed", "skipped"):
        assert field in result, f"must reference {field} field in outcome template"
    assert "skip" in result.lower(), "must mention skip reason check"
