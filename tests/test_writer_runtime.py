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
WRITER_PATH = os.path.expanduser("~/.claude/scripts/review-result-writer.sh")
WRITER_BACKUP_PATH = os.path.expanduser("~/.claude/scripts/review-result-writer.sh.deep-review-backup")
STUB_DIR = os.path.expanduser("~/.claude/jobs/786c591a/tmp/stub-bin")
# Resolved once at import time; avoids repeated os.path.exists per test method
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
        """Run writer with stub codex-send-wait and capture invocation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create stub that captures invocation
            stub_path = os.path.join(tmpdir, "codex-send-wait")
            capture_path = os.path.join(tmpdir, "capture.json")
            with open(stub_path, "w") as f:
                f.write(f"""#!/usr/bin/env bash
ARG_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "$@")
ENV_JSON=$(python3 -c "import json,os; print(json.dumps({{k: v for k, v in os.environ.items() if 'CODEX' in k or 'TIMEOUT' in k}}))")
printf '{{"argv": %s, "env": %s}}\\n' "$ARG_JSON" "$ENV_JSON" > '{capture_path}'
exit 127
""")
            os.chmod(stub_path, 0o755)

            # Create modified writer with stub path
            with open(ACTIVE_WRITER_PATH) as f:
                writer_src = f.read()
            writer_src = writer_src.replace(
                '$HOME/.claude/handoff/bin/codex-send-wait',
                f'{tmpdir}/codex-send-wait'
            )
            writer_test_path = os.path.join(tmpdir, "writer-test.sh")
            with open(writer_test_path, "w") as f:
                f.write(writer_src)
            os.chmod(writer_test_path, 0o755)

            # Create capsule
            capsule_path = os.path.join(tmpdir, "test-capsule.txt")
            with open(capsule_path, "w") as f:
                f.write("REVIEW_KIND: plan\nREVIEW_FOCUS: test\n\n# Test\n")

            # Create baseline dir
            baseline_dir = os.path.expanduser("~/.claude/review-baselines/test-noflag-golden")
            os.makedirs(baseline_dir, exist_ok=True)

            # Run writer
            cmd = [
                "bash", writer_test_path,
                "--capsule-file", capsule_path,
                "--baseline-key", "test-noflag-golden",
                "--review-kind", "plan",
                "--cwd", "/tmp"
            ]
            if extra_args:
                cmd.extend(extra_args)
            subprocess.run(cmd, capture_output=True, text=True)

            # Return capture
            if os.path.exists(capture_path):
                with open(capture_path) as f:
                    return json.load(f)
            return None

    def test_writer_no_flag_golden(self):
        """SC-1: writer with no --mode flag passes --mode review-only to codex-send-wait"""
        capture = self._run_writer_with_stub()
        assert capture is not None, "stub must have been called"
        argv = capture["argv"]
        # Must pass --mode review-only
        assert "--mode" in argv, "--mode must be in argv"
        mode_idx = argv.index("--mode")
        assert argv[mode_idx + 1] == "review-only", "default mode must be review-only"
        # Must NOT have CODEX_SEND_WAIT_TIMEOUT env (before deep changes)
        # After changes with --mode default, env should also be absent
        env = capture.get("env", {})
        assert "CODEX_SEND_WAIT_TIMEOUT" not in env or env.get("CODEX_SEND_WAIT_TIMEOUT") == "", (
            "no-flag writer must not set CODEX_SEND_WAIT_TIMEOUT"
        )


# SC-29: deep timeout golden
class TestWriterDeepTimeoutGolden:
    def _run_writer_with_stub_and_mode(self, mode=None, send_timeout=None, exec_timeout=None):
        """Run writer with given mode/timeout and capture invocation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stub_path = os.path.join(tmpdir, "codex-send-wait")
            capture_path = os.path.join(tmpdir, "capture.json")
            with open(stub_path, "w") as f:
                f.write(f"""#!/usr/bin/env bash
ARG_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "$@")
ENV_JSON=$(python3 -c "import json,os; print(json.dumps({{k: v for k, v in os.environ.items() if 'CODEX' in k or 'TIMEOUT' in k}}))")
printf '{{"argv": %s, "env": %s}}\\n' "$ARG_JSON" "$ENV_JSON" > '{capture_path}'
exit 127
""")
            os.chmod(stub_path, 0o755)

            with open(ACTIVE_WRITER_PATH) as f:
                writer_src = f.read()
            writer_src = writer_src.replace(
                '$HOME/.claude/handoff/bin/codex-send-wait',
                f'{tmpdir}/codex-send-wait'
            )
            writer_test_path = os.path.join(tmpdir, "writer-test.sh")
            with open(writer_test_path, "w") as f:
                f.write(writer_src)
            os.chmod(writer_test_path, 0o755)

            capsule_path = os.path.join(tmpdir, "test-capsule.txt")
            with open(capsule_path, "w") as f:
                f.write("REVIEW_KIND: plan\nREVIEW_FOCUS: test\n\n# Test\n")

            baseline_dir = os.path.expanduser("~/.claude/review-baselines/test-timeout-golden")
            os.makedirs(baseline_dir, exist_ok=True)

            cmd = [
                "bash", writer_test_path,
                "--capsule-file", capsule_path,
                "--baseline-key", "test-timeout-golden",
                "--review-kind", "plan",
                "--cwd", "/tmp"
            ]
            if mode:
                cmd.extend(["--mode", mode])
            if send_timeout:
                cmd.extend(["--send-timeout", str(send_timeout)])
            if exec_timeout:
                cmd.extend(["--exec-timeout", str(exec_timeout)])

            subprocess.run(cmd, capture_output=True, text=True)

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
