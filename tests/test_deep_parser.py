"""Tests for SC-26, SC-7, SC-33 deep parser features."""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import pytest


class TestV2TitleTolerance:
    """SC-26: v2 title tolerance."""

    def test_v2_title_tolerance_with_suffix(self):
        """SC-26: title with (v2) suffix accepted."""
        from gd_codex_bridge_review import parse_raw_to_mapped
        # Minimal v2 plan markdown with (v2) suffix
        raw = """# Plan Review Result (v2)

<!--gd-review-result-json:start-->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-plan-review",
  "review_kind": "plan",
  "review_target_kind": "plan_only",
  "target_role": "plan_artifact",
  "reviewer": "codex",
  "review_target": "test.md",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": {"location": "fenced_json_block", "value": "APPROVED"},
  "scope_checked": [{"area": "test", "result": "pass", "evidence": "ok"}],
  "findings": [],
  "merge_notes": {"conflict_with_other_reviewer": false},
  "residual_risk": "",
  "timestamp": "2026-06-14T10:00:00Z"
}
```
<!--gd-review-result-json:end-->
"""
        mapped, errs = parse_raw_to_mapped("plan", "test.md", raw, compat_v1=False)
        assert mapped.get("gd_review_decision") == "APPROVED", f"errs={errs}"

    def test_v2_title_tolerance_without_suffix(self):
        """SC-26: title without (v2) suffix also accepted."""
        from gd_codex_bridge_review import parse_raw_to_mapped
        raw = """# Plan Review Result

<!--gd-review-result-json:start-->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-plan-review",
  "review_kind": "plan",
  "review_target_kind": "plan_only",
  "target_role": "plan_artifact",
  "reviewer": "codex",
  "review_target": "test.md",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": {"location": "fenced_json_block", "value": "APPROVED"},
  "scope_checked": [{"area": "test", "result": "pass", "evidence": "ok"}],
  "findings": [],
  "merge_notes": {"conflict_with_other_reviewer": false},
  "residual_risk": "",
  "timestamp": "2026-06-14T10:00:00Z"
}
```
<!--gd-review-result-json:end-->
"""
        mapped, errs = parse_raw_to_mapped("plan", "test.md", raw, compat_v1=False)
        assert mapped.get("gd_review_decision") == "APPROVED", (
            f"bare title should be accepted; errs={errs}"
        )


class TestDeepFindingsMissing:
    """SC-7: DEEP_FINDINGS_MISSING."""

    def test_deep_findings_missing_fixture_loadable(self):
        """SC-7: deep-plan-fail-missing-findings.mapped.json is loadable and has expected decision."""
        fixture = os.path.join(
            PROJECT_ROOT, "fixtures", "codex-bridge-v2",
            "deep-plan-fail-missing-findings.mapped.json",
        )
        assert os.path.exists(fixture), f"fixture missing: {fixture}"
        with open(fixture) as f:
            d = json.load(f)
        assert isinstance(d, dict)
        assert d.get("expected_gd_review_decision") == "FAILED", (
            "DEEP_FINDINGS_MISSING fixture should expect FAILED decision"
        )


class TestDeepCapsulePlanFile:
    """SC-33: --plan-file capsule includes PLAN_FILE_PATH."""

    def test_plan_file_in_capsule(self):
        """SC-33: when --plan-file is given, capsule includes PLAN_FILE_PATH."""
        import tempfile
        from pathlib import Path
        from gd_codex_bridge_review import _build_deep_plan_capsule
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Plan\n- [ ] SC-1 test\n")
            plan_path = f.name
        try:
            result = _build_deep_plan_capsule("plan", Path(plan_path), plan_file=plan_path)
            assert "PLAN_FILE_PATH:" in result
            assert plan_path in result
        finally:
            os.unlink(plan_path)


# SC-33: alias with name matching SC verify command
def test_deep_capsule_plan_file():
    """SC-33: --plan-file capsule includes PLAN_FILE_PATH (alias for -k filter)."""
    import os
    import tempfile
    from pathlib import Path
    PROJECT_ROOT_LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from gd_codex_bridge_review import _build_deep_plan_capsule
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Plan\n- [ ] SC-1 test\n  - verify (method: command, build-gate): `echo ok`\n")
        plan_path = f.name
    try:
        result = _build_deep_plan_capsule("plan", Path(plan_path), plan_file=plan_path)
        assert "PLAN_FILE_PATH:" in result, "capsule must include PLAN_FILE_PATH"
        assert plan_path in result, "capsule must include actual plan path"
    finally:
        os.unlink(plan_path)
