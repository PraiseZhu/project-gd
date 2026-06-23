"""Layer 3 fail-visible guard: review-result-writer detects pre-fed capsules.

Standard deep capsules (build_capsule_text via gd-codex-bridge-review.py
run-bridge) never emit VALIDATION_EVIDENCE; only review1's manual template
does (commands/review1.md). When a capsule carries VALIDATION_EVIDENCE the
writer warns on stderr + stamps baseline ``last_review_quality=pre_fed`` so
downstream gates do not treat a shallow APPROVED as a trusted deep-review.

These tests run the live vendor writer (NOT the preimage golden fixture in
test_writer_runtime.py) with ``HANDOFF_ROOT`` overridden to a temp dir, so
codex-send-wait is absent and the writer takes the degraded_unreviewed path.
Detection + baseline update run unconditionally, so the guard is exercised
without a real codex — no transport, no timeout.
"""
import json
import os
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITER_PATH = os.path.join(
    PROJECT_ROOT, "vendor", "l3-transport", "scripts", "review-result-writer.sh"
)


def _minimal_env(handoff_root, plugin_data):
    """Clean env so user CLAUDE_PLUGIN_DATA / CODEX_* vars cannot leak in."""
    return {
        "HOME": os.environ["HOME"],
        "PATH": os.environ["PATH"],
        "HANDOFF_ROOT": handoff_root,
        "CLAUDE_PLUGIN_DATA": plugin_data,
    }


_STUB_APPROVED = """#!/usr/bin/env bash
cat <<'EOF'
# Code Review Result
Scope Checked: src/foo.py
VERDICT: APPROVED
## Findings
No blocking findings.
## Residual Risk
None.
EOF
exit 0
"""


def _run_writer(capsule_text, tmp_path, baseline_key):
    capsule = tmp_path / "capsule.txt"
    capsule.write_text(capsule_text)
    out_dir = tmp_path / "baselines"
    env = _minimal_env(str(tmp_path / "handoff"), str(tmp_path / "pd"))
    result = subprocess.run(
        ["bash", WRITER_PATH,
         "--capsule-file", str(capsule),
         "--baseline-key", baseline_key,
         "--review-kind", "code",
         "--cwd", str(tmp_path),
         "--out-dir", str(out_dir)],
        capture_output=True, text=True, env=env,
    )
    baseline = out_dir / baseline_key / "latest-plan-baseline.json"
    return result, baseline


def _install_stub_codex(tmp_path, stub_script=_STUB_APPROVED):
    """Place a stub codex-send-wait under tmp_path/handoff/bin so the writer
    finds it via HANDOFF_ROOT and runs the codex happy path instead of degraded."""
    bin_dir = tmp_path / "handoff" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "codex-send-wait"
    stub.write_text(stub_script)
    stub.chmod(0o755)
    return stub


def _writer_has_guard():
    """True iff the live vendor writer carries the Layer-3 pre-fed guard."""
    if not os.path.isfile(WRITER_PATH):
        return False
    with open(WRITER_PATH) as f:
        return "REVIEW_QUALITY" in f.read()


@pytest.mark.skipif(not _writer_has_guard(),
                    reason="vendor writer missing Layer-3 pre-fed guard")
class TestWriterPrefedDetection:
    def test_prefed_capsule_marked_pre_fed(self, tmp_path):
        """Capsule with VALIDATION_EVIDENCE → last_review_quality=pre_fed + stderr warns."""
        capsule = (
            "REVIEW_DOMAIN: code\n"
            "REVIEW_ROUND: initial\n"
            f"PROJECT_ROOT: {tmp_path}\n"
            "VALIDATION_EVIDENCE: pass=10 fail=0 SC-7 hash stable\n"
        )
        result, baseline = _run_writer(capsule, tmp_path, "prefed-test")
        assert baseline.exists(), (
            f"baseline 未生成 (rc={result.returncode}); stderr={result.stderr}"
        )
        data = json.loads(baseline.read_text())
        assert data["last_review_quality"] == "pre_fed", (
            f"pre-fed capsule 应标 pre_fed, got {data.get('last_review_quality')!r}; "
            f"stderr={result.stderr}"
        )
        assert "VALIDATION_EVIDENCE" in result.stderr or "pre_fed" in result.stderr, (
            f"stderr 应含 pre-fed 警告: {result.stderr}"
        )

    def test_standard_capsule_marked_standard(self, tmp_path):
        """Standard capsule (no VALIDATION_EVIDENCE) → standard, no pre-fed warning."""
        capsule = (
            "REVIEW_DOMAIN: code\n"
            "REVIEW_ROUND: initial\n"
            f"PROJECT_ROOT: {tmp_path}\n"
            "PRIMARY_TARGET_PATH: src/foo.py\n"
        )
        result, baseline = _run_writer(capsule, tmp_path, "std-test")
        assert baseline.exists(), (
            f"baseline 未生成 (rc={result.returncode}); stderr={result.stderr}"
        )
        data = json.loads(baseline.read_text())
        assert data["last_review_quality"] == "standard", (
            f"standard capsule 应标 standard, got {data.get('last_review_quality')!r}; "
            f"stderr={result.stderr}"
        )
        # stderr carries the degraded (transport-absent) notice but must NOT
        # carry the pre-fed conclusion warning for a standard capsule.
        assert "pre_fed" not in result.stderr, (
            f"standard capsule 不应触发 pre-fed 警告: {result.stderr}"
        )

    def test_prefed_capsule_marked_pre_fed_when_codex_approves(self, tmp_path):
        """Happy path: even when codex returns APPROVED, a pre-fed capsule stays
        marked pre_fed. This is the core Layer-3 guarantee — a shallow APPROVED
        (conclusions were fed, codex may have echoed) must not silently pass as a
        trusted deep-review APPROVED. Downstream gates read review_quality to tell
        them apart. Uses a stub codex-send-wait returning a well-formed APPROVED raw."""
        _install_stub_codex(tmp_path)
        capsule = (
            "REVIEW_DOMAIN: code\n"
            "REVIEW_ROUND: initial\n"
            f"PROJECT_ROOT: {tmp_path}\n"
            "VALIDATION_EVIDENCE: pass=10 fail=0 SC-7 hash stable\n"
        )
        result, baseline = _run_writer(capsule, tmp_path, "prefed-approved")
        assert baseline.exists(), (
            f"baseline 未生成 (rc={result.returncode}); stderr={result.stderr}"
        )
        data = json.loads(baseline.read_text())
        # Codex said APPROVED — verdict/status reflect that...
        status = data.get("last_code_review_status") or data.get("review_status")
        assert status == "approved", (
            f"happy path 应 verdict APPROVED, got status={status!r}; stderr={result.stderr}"
        )
        # ...BUT the pre-fed provenance is still stamped — the APPROVED is shallow.
        assert data["last_review_quality"] == "pre_fed", (
            f"pre-fed capsule 即使 codex APPROVED 也应标 pre_fed, "
            f"got {data.get('last_review_quality')!r}; stderr={result.stderr}"
        )
