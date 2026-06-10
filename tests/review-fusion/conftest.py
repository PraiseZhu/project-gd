import subprocess, sys, pathlib, os, tempfile, pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent  # /Users/praise/AI-Agent/Claude/projects/Project GD
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def _ensure_writable_tmpdir() -> None:
    """Guarantee pytest has a writable temp dir even under a locked-down sandbox.

    pytest's built-in tmp_path/tmpdir fixtures resolve their basetemp from the
    system temp dir ($TMPDIR → /tmp → cwd) at startup. In a restricted sandbox
    (e.g. Codex cross-review) all of those can be non-writable, which makes
    pytest abort with "No usable temporary directory found" before any test
    runs. This conftest is imported before pytest resolves basetemp, so setting
    TMPDIR here to a project-local dir makes the suite self-contained: it no
    longer depends on the host's /tmp being writable.

    Only redirects when the current temp dir is genuinely unusable, so normal
    local/CI runs keep using the system temp dir.
    """
    current = tempfile.gettempdir()
    try:
        probe = os.path.join(current, ".gd_tmp_write_probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return  # system temp dir is writable; leave it alone
    except OSError:
        pass
    fallback = PROJECT_ROOT / ".pytest-tmp"
    fallback.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(fallback)
    # tempfile caches the resolved dir; clear it so the new TMPDIR takes effect.
    tempfile.tempdir = None


_ensure_writable_tmpdir()

def run_script(rel_path, args, env=None, input=None, timeout=30):
    """Run a script under PROJECT_ROOT and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(PROJECT_ROOT / rel_path)] + args
    r = subprocess.run(cmd, capture_output=True, text=True, env=env or os.environ.copy(),
                       input=input, timeout=timeout, cwd=str(PROJECT_ROOT))
    return r.returncode, r.stdout, r.stderr

@pytest.fixture
def project_root():
    return PROJECT_ROOT

@pytest.fixture
def fake_codex_always_fail(tmp_path):
    """Stub: always exits 1 (codex unavailable)."""
    stub = tmp_path / "codex"
    stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + ":" + env.get("PATH", "")
    return env, str(tmp_path)

@pytest.fixture
def fake_codex_transient(tmp_path):
    """Stub: fails first call, succeeds from second call onwards."""
    counter = tmp_path / ".call_count"
    stub = tmp_path / "codex"
    stub.write_text(f"""#!/bin/sh
COUNT_FILE="{counter}"
if [ -f "$COUNT_FILE" ]; then
  COUNT=$(cat "$COUNT_FILE")
else
  COUNT=0
fi
COUNT=$((COUNT + 1))
echo $COUNT > "$COUNT_FILE"
if [ "$COUNT" -le 1 ]; then
  exit 1
fi
echo "codex-cli 0.0.0-test"
exit 0
""")
    stub.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + ":" + env.get("PATH", "")
    return env, str(tmp_path)
