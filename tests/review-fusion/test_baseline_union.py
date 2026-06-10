import pytest, importlib.util, pathlib
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent

def load_loop():
    spec = importlib.util.spec_from_file_location("loop", PROJECT_ROOT / "scripts/gd-review-merge-and-fix-loop.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_union_baseline():
    """union_baseline: codex_A missing a finding that codex_B reports → baseline must contain it."""
    loop = load_loop()
    # codex_A does NOT report this finding
    codex_a = [{"file": "foo.py", "line": 10, "category": "logic", "severity": "P1", "description": "logic error"}]
    # codex_B DOES report the same finding (within ±3 line window)
    codex_b = [
        {"file": "foo.py", "line": 10, "category": "logic", "severity": "P1", "description": "logic error"},
        {"file": "bar.py", "line": 20, "category": "safety", "severity": "P2", "description": "safety issue"},
    ]
    claude = []
    merged = loop.merge_findings_union(codex_a, codex_b, claude)
    files = [f["file"] for f in merged]
    assert "bar.py" in files, "codex_B-only finding (bar.py) must be in baseline union"
    # severity should be max
    foo_findings = [f for f in merged if f["file"] == "foo.py"]
    assert len(foo_findings) == 1, "foo.py should be deduplicated"
    assert foo_findings[0]["severity"] == "P1"
