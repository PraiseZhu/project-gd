import pytest, importlib.util, pathlib, inspect
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent

def load_router():
    spec = importlib.util.spec_from_file_location("router", PROJECT_ROOT / "scripts/gd-review-router.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_code_path_quality_conformance_separation():
    """code_path_quality_conformance_separation: source contains upstream_quality_gate and conformance fields."""
    router = load_router()
    src = inspect.getsource(router)
    assert "upstream_quality_gate" in src, "upstream_quality_gate field missing"
    assert "conformance" in src, "conformance field missing"
    assert "codex_review_scope" in src, "codex_review_scope field missing"
    # fail_closed path must exist
    assert "fail_closed" in src, "fail_closed field missing"
    # Two observable artifacts
    assert "code-review" in src or "code_review" in src, "code-review reference missing"
    assert "simplify" in src, "simplify reference missing"

def test_bridge_contract():
    """bridge_contract: router source contains failure_code enum values."""
    router = load_router()
    src = inspect.getsource(router)
    for code in ["UPSTREAM_QUALITY_GATE_FAIL", "CODE_REVIEW_UNAVAILABLE", "SIMPLIFY_UNAVAILABLE"]:
        assert code in src, f"failure_code enum '{code}' missing from router"
