"""Regression tests for Claude plan-mode template alignment with L2 review."""

import importlib.util
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_bridge():
    path = PROJECT_ROOT / "scripts" / "gd-codex-bridge-review.py"
    spec = importlib.util.spec_from_file_location(
        "gd_codex_bridge_review_plan_template_test",
        path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plan_mode_template_passes_review2_plan_target_gate():
    target = PROJECT_ROOT / "templates" / "plan-mode-template.md"
    result = subprocess.run(
        [
            "python3",
            "scripts/gd-validate-review2-plan-target.py",
            "--target",
            str(target),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PLAN_TEMPLATE_STATUS: pass" in result.stdout
    assert "BRIDGE_INVOCATION_STATUS: allowed" in result.stdout


def test_bridge_extracts_plan_review_alignment_from_plan_mode_template():
    bridge = _load_bridge()
    target = PROJECT_ROOT / "templates" / "plan-mode-template.md"
    domain, focus = bridge._extract_plan_review_meta(target)
    assert domain == "ai_infra | app_code | docs_content | other"
    assert focus == "<focus 1>; <focus 2>; <focus 3>"


if __name__ == "__main__":
    os.environ.setdefault("PYTEST_CURRENT_TEST", "manual")
    test_plan_mode_template_passes_review2_plan_target_gate()
    test_bridge_extracts_plan_review_alignment_from_plan_mode_template()
    print("plan-mode template alignment: PASS")
