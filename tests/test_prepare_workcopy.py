"""Tests for deep code_diff workcopy preparation."""
import pathlib
import subprocess

from gd_prepare_workcopy import cleanup_workcopy, prepare_workcopy


def test_prepare_workcopy_manifest_uses_absolute_paths(tmp_path, monkeypatch):
    """Deep workcopy metadata must be stable across child process cwd changes."""
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-m", "seed"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    scratch_rel = pathlib.Path("scratch")
    manifest = prepare_workcopy(repo, "unit", scratch_rel)
    try:
        assert pathlib.Path(manifest["scratch_dir"]).is_absolute()
        assert pathlib.Path(manifest["workcopy_cwd"]).is_absolute()
    finally:
        cleanup_workcopy(manifest)
