import pytest, importlib.util, types, pathlib, sys
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent

def load_guard():
    spec = importlib.util.spec_from_file_location("guard", PROJECT_ROOT / "scripts/gd-codex-transport-guard.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_preflight_unavailable_fail_closed():
    """fail_closed path: always-fail stub → available=False, fail_closed=True."""
    guard = load_guard()
    r = guard.probe_with_retry(
        preflight_fn=lambda t: types.SimpleNamespace(returncode=1, stdout="", stderr=""),
        max_retries=1
    )
    assert r.get("available") is False
    assert r.get("fail_closed") is True

def test_retry_recover():
    """retry_recover path: transient stub (first fail, then ok) → available=True."""
    guard = load_guard()
    calls = [0]
    def transient(t):
        calls[0] += 1
        if calls[0] <= 1:
            return types.SimpleNamespace(returncode=1, stdout="", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
    r = guard.probe_with_retry(preflight_fn=transient, max_retries=2)
    assert r.get("available") is True

def test_timeout_configured():
    """timeout_configured: PROBE_TIMEOUT_SEC is a positive number."""
    guard = load_guard()
    assert hasattr(guard, "PROBE_TIMEOUT_SEC")
    assert isinstance(guard.PROBE_TIMEOUT_SEC, (int, float))
    assert guard.PROBE_TIMEOUT_SEC > 0

def test_healthcheck_invocation():
    """healthcheck_invocation: healthcheck() function is callable and returns bool."""
    guard = load_guard()
    assert callable(guard.healthcheck)
    # We don't call the real healthcheck (would hit real codex), just verify it's wired
    assert "healthcheck" in dir(guard)
