"""
Tests for SC-1, SC-20, SC-21, SC-22, SC-29: writer runtime manifest and golden behavior.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "fixtures/deep-review/writer-runtime-manifest.json")
PREIMAGE_PATH = os.path.join(PROJECT_ROOT, "fixtures/deep-review/writer-preimage.sh")
GOLDEN_PATH = os.path.join(PROJECT_ROOT, "fixtures/deep-review/writer-no-flag-golden.json")
WRITER_PATH = os.path.join(PROJECT_ROOT, "vendor/l3-transport/scripts/review-result-writer.sh")
WRITER_BACKUP_PATH = os.path.expanduser("~/.claude/scripts/review-result-writer.sh.deep-review-backup")
STUB_DIR = os.path.expanduser("~/.claude/jobs/786c591a/tmp/stub-bin")
# Resolved once at import time; writer now runs from vendor (run-in-place), not ~/.claude/scripts/
ACTIVE_WRITER_PATH = WRITER_PATH if os.path.exists(WRITER_PATH) else PREIMAGE_PATH


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load_manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


# SC-20: manifest writer_pre_hash verified against preimage
class TestWriterRuntimeManifest:
    def test_writer_runtime_manifest(self):
        """SC-20: manifest.writer_pre_hash == sha256(preimage)"""
        assert os.path.exists(MANIFEST_PATH), "manifest must exist"
        assert os.path.exists(PREIMAGE_PATH), "preimage must exist"
        m = _load_manifest()
        pre_hash = m["writer_pre_hash"]
        preimage_hash = _sha256(PREIMAGE_PATH)
        assert preimage_hash == pre_hash, (
            f"sha256(preimage) {preimage_hash} != manifest.writer_pre_hash {pre_hash}"
        )
        # golden must also reference same pre_hash
        with open(GOLDEN_PATH) as f:
            golden = json.load(f)
        assert golden["writer_pre_hash"] == pre_hash, "golden.writer_pre_hash must match manifest"


# SC-21: backup path valid and hash matches
class TestWriterBackup:
    def test_writer_backup_valid(self):
        """SC-21: writer preimage (改前 writer snapshot) exists and hash matches pre_hash.
        Live backup under ~/.claude/scripts/ retired when writer moved to plugin
        distribution; the preimage fixture carries the same pre-change snapshot."""
        m = _load_manifest()
        assert os.path.exists(PREIMAGE_PATH), f"preimage (改前 writer) 须存在: {PREIMAGE_PATH}"
        backup_hash = _sha256(PREIMAGE_PATH)
        assert backup_hash == m["writer_pre_hash"], (
            f"preimage hash {backup_hash} != pre_hash {m['writer_pre_hash']}"
        )


# SC-1: writer no-flag golden - default behavior unchanged
class TestWriterNoFlagGolden:
    def _run_writer_with_stub(self, extra_args=None):
        """Run vendor writer in-place with a stub codex-send-wait and capture argv.

        Isolation model (mirrors test_writer_prefed_detection): do NOT copy the
        writer — run ACTIVE_WRITER_PATH in place so its `source ../handoff/lib/
        state-paths.sh` resolves (the relative source path breaks when the writer
        is copied to tmpdir, which is why the previous copy-and-replace approach
        failed to invoke the stub). Override HANDOFF_ROOT via env so state-paths.sh
        points HANDOFF_BIN at a tmpdir stub that captures the codex-send-wait argv.
        --out-dir + CLAUDE_PLUGIN_DATA keep all writes inside tmpdir.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_root = os.path.join(tmpdir, "handoff")
            bin_dir = os.path.join(handoff_root, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            stub_path = os.path.join(bin_dir, "codex-send-wait")
            capture_path = os.path.join(tmpdir, "capture.json")
            with open(stub_path, "w") as f:
                f.write(f"""#!/usr/bin/env bash
ARG_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "$@")
ENV_JSON=$(python3 -c "import json,os; print(json.dumps({{k: v for k, v in os.environ.items() if 'CODEX' in k or 'TIMEOUT' in k}}))")
printf '{{"argv": %s, "env": %s}}\\n' "$ARG_JSON" "$ENV_JSON" > '{capture_path}'
exit 127
""")
            os.chmod(stub_path, 0o755)

            capsule_path = os.path.join(tmpdir, "test-capsule.txt")
            with open(capsule_path, "w") as f:
                f.write("REVIEW_KIND: plan\nREVIEW_FOCUS: test\n\n# Test\n")

            out_dir = os.path.join(tmpdir, "baselines")
            env = {
                "HOME": os.environ["HOME"],
                "PATH": os.environ["PATH"],
                "HANDOFF_ROOT": handoff_root,
                "CLAUDE_PLUGIN_DATA": tmpdir,
            }
            cmd = [
                "bash", ACTIVE_WRITER_PATH,
                "--capsule-file", capsule_path,
                "--baseline-key", "test-noflag-golden",
                "--review-kind", "plan",
                "--cwd", "/tmp",
                "--out-dir", out_dir,
            ]
            if extra_args:
                cmd.extend(extra_args)
            subprocess.run(cmd, capture_output=True, text=True, env=env)

            if os.path.exists(capture_path):
                with open(capture_path) as f:
                    return json.load(f)
            return None

    def test_writer_no_flag_golden(self):
        """SC-1: writer with no --mode flag passes --mode review-only + default
        --timeout 1500 to codex-send-wait, and does NOT forward per-job --exec-timeout."""
        capture = self._run_writer_with_stub()
        assert capture is not None, "stub must have been called"
        argv = capture["argv"]
        # Must pass --mode review-only
        assert "--mode" in argv, "--mode must be in argv"
        mode_idx = argv.index("--mode")
        assert argv[mode_idx + 1] == "review-only", "default mode must be review-only"
        # T-P0: no-flag path now forwards the default send_wait as --timeout (1500),
        # so daemon_worst(1440) < send_wait(1500) holds even when the caller passes no flags.
        assert "--timeout" in argv, "no-flag writer must forward default send_wait as --timeout"
        timeout_idx = argv.index("--timeout")
        assert argv[timeout_idx + 1] == "1500", "default send_wait must be 1500 (> daemon worst-case 1440)"
        # No-flag path must not attach per-job --exec-timeout (only deep/bridge does)
        assert "--exec-timeout" not in argv, "no-flag path must not pass per-job exec timeout"
        # Writer consumes CODEX_SEND_WAIT_TIMEOUT env into the --timeout argv; it must
        # not leak the env var through to the codex-send-wait child process.
        env = capture.get("env", {})
        assert "CODEX_SEND_WAIT_TIMEOUT" not in env or env.get("CODEX_SEND_WAIT_TIMEOUT") == "", (
            "no-flag writer must not pass CODEX_SEND_WAIT_TIMEOUT env through to codex-send-wait"
        )


# SC-29: deep timeout golden
class TestWriterDeepTimeoutGolden:
    def _run_writer_with_stub_and_mode(self, mode=None, send_timeout=None, exec_timeout=None):
        """Run vendor writer in-place with stub codex-send-wait and capture argv,
        for the deep timeout golden path. See _run_writer_with_stub for isolation model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_root = os.path.join(tmpdir, "handoff")
            bin_dir = os.path.join(handoff_root, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            stub_path = os.path.join(bin_dir, "codex-send-wait")
            capture_path = os.path.join(tmpdir, "capture.json")
            with open(stub_path, "w") as f:
                f.write(f"""#!/usr/bin/env bash
ARG_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "$@")
ENV_JSON=$(python3 -c "import json,os; print(json.dumps({{k: v for k, v in os.environ.items() if 'CODEX' in k or 'TIMEOUT' in k}}))")
printf '{{"argv": %s, "env": %s}}\\n' "$ARG_JSON" "$ENV_JSON" > '{capture_path}'
exit 127
""")
            os.chmod(stub_path, 0o755)

            capsule_path = os.path.join(tmpdir, "test-capsule.txt")
            with open(capsule_path, "w") as f:
                f.write("REVIEW_KIND: plan\nREVIEW_FOCUS: test\n\n# Test\n")

            out_dir = os.path.join(tmpdir, "baselines")
            env = {
                "HOME": os.environ["HOME"],
                "PATH": os.environ["PATH"],
                "HANDOFF_ROOT": handoff_root,
                "CLAUDE_PLUGIN_DATA": tmpdir,
            }
            cmd = [
                "bash", ACTIVE_WRITER_PATH,
                "--capsule-file", capsule_path,
                "--baseline-key", "test-timeout-golden",
                "--review-kind", "plan",
                "--cwd", "/tmp",
                "--out-dir", out_dir,
            ]
            if mode:
                cmd.extend(["--mode", mode])
            if send_timeout:
                cmd.extend(["--send-timeout", str(send_timeout)])
            if exec_timeout:
                cmd.extend(["--exec-timeout", str(exec_timeout)])

            subprocess.run(cmd, capture_output=True, text=True, env=env)

            if os.path.exists(capture_path):
                with open(capture_path) as f:
                    return json.load(f)
            return None

    def test_writer_deep_timeout_golden(self):
        """SC-29: deep mode passes wait timeout and per-job exec timeout to codex-send-wait"""
        # Only run after Step 1 writer changes are in place
        if not os.path.exists(WRITER_PATH):
            pytest.skip("writer not found")
        with open(WRITER_PATH) as f:
            writer_content = f.read()
        if "--mode" not in writer_content or "send-timeout" not in writer_content or "exec-timeout" not in writer_content:
            pytest.skip("writer not yet updated with --mode/--send-timeout/--exec-timeout")

        # Test deep path: --mode workspace-write + --send-timeout + --exec-timeout
        capture_deep = self._run_writer_with_stub_and_mode("workspace-write", 1500, 720)
        assert capture_deep is not None, "stub must be called for deep path"
        argv = capture_deep["argv"]
        assert "--mode" in argv
        mode_idx = argv.index("--mode")
        assert argv[mode_idx + 1] == "workspace-write", "deep mode must be workspace-write"
        assert "--timeout" in argv
        wait_idx = argv.index("--timeout")
        assert argv[wait_idx + 1] == "1500", "deep send-timeout must be forwarded as --timeout 1500"
        assert "--exec-timeout" in argv
        exec_idx = argv.index("--exec-timeout")
        assert argv[exec_idx + 1] == "720", "deep exec timeout must be forwarded as per-job metadata"

        # Test default path: no flags
        capture_default = self._run_writer_with_stub_and_mode()
        assert capture_default is not None
        argv_def = capture_default["argv"]
        assert "--mode" in argv_def
        mode_idx_def = argv_def.index("--mode")
        assert argv_def[mode_idx_def + 1] == "review-only", "default mode unchanged"
        env_def = capture_default.get("env", {})
        assert "CODEX_SEND_WAIT_TIMEOUT" not in env_def or env_def.get("CODEX_SEND_WAIT_TIMEOUT", "") == "", (
            "default path must not set CODEX_SEND_WAIT_TIMEOUT"
        )
        assert "--exec-timeout" not in argv_def, "default path must not pass per-job exec timeout"
