import pytest, importlib.util, pathlib, inspect
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent

def load_loop():
    spec = importlib.util.spec_from_file_location("loop", PROJECT_ROOT / "scripts/gd-review-merge-and-fix-loop.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_r2_scope_constrained_dual_codex():
    """r2_scope_constrained_dual_codex: source has REVIEW_ROUND, BASELINE_FINDINGS, DELTA_SCOPE, SCOPE_CONSTRAINT injected and dual codex."""
    loop = load_loop()
    src = inspect.getsource(loop)
    for field in ["REVIEW_ROUND", "BASELINE_FINDINGS", "DELTA_SCOPE", "SCOPE_CONSTRAINT"]:
        count = src.count(field)
        assert count >= 2, f"{field} appears {count} times (<2); must appear in both definition and usage"
    # dual codex: ThreadPoolExecutor with max_workers=2 or similar pattern
    assert any(pat in src for pat in ["max_workers=2", "ThreadPoolExecutor(max_workers", "codex_A", "codex_B"])
    # No D7 condition
    for forbidden in ["large_delta", "D7", "threshold_lines", "threshold_files"]:
        assert forbidden not in src, f"Forbidden D7 token '{forbidden}' found in source"
