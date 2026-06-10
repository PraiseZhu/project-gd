import pytest, importlib.util, types, pathlib
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent

def load_guard():
    spec = importlib.util.spec_from_file_location("guard", PROJECT_ROOT / "scripts/gd-codex-transport-guard.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_fail_closed():
    """fail_closed: always-fail stub → blocked, not APPROVED, no degraded pass-through."""
    guard = load_guard()
    r = guard.probe_with_retry(
        preflight_fn=lambda t: types.SimpleNamespace(returncode=1, stdout="", stderr="fail"),
        max_retries=2
    )
    assert r.get("available") is False, f"Expected available=False, got {r}"
    assert r.get("fail_closed") is True, f"Expected fail_closed=True, got {r}"
    # ensure_codex_available should also fail_closed
    def always_fail(t): return types.SimpleNamespace(returncode=1, stdout="", stderr="")
    r2 = guard.probe_with_retry(preflight_fn=always_fail, max_retries=1)
    assert r2.get("fail_closed") is True

def test_retry_recover():
    """retry_recover: transient failure then ok → available=True (no false fail_closed)."""
    guard = load_guard()
    calls = [0]
    def transient(t):
        calls[0] += 1
        return (types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
                if calls[0] > 1 else
                types.SimpleNamespace(returncode=1, stdout="", stderr=""))
    r = guard.probe_with_retry(preflight_fn=transient, max_retries=2)
    assert r.get("available") is True, f"Expected available=True after retry, got {r}"
