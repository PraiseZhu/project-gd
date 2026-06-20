#!/usr/bin/env python3
"""SC-2 (T2): code 路 deep 副本机制 — 复制 dirty（staged/unstaged/untracked）到独立 workcopy。

codex 在 workspace-write 模式下会改文件；副本保证它只改副本，原工作区 git status --porcelain
前后字节一致（hard_stop: 副本不得写入原工作区 / worktree 丢 dirty 审错对象）。

副本策略（纯 Python 子进程，跨平台；不依赖 bash4 特性）：
  1. `git worktree add --detach <workdir>`  → 链接工作树在 HEAD（tracked 文件全在，无 dirty）
  2. `git -C <orig> stash create -u`         → 造含 staged+unstaged+untracked 的 commit 对象
                                              （**不碰原工作树**，仅返回 commit SHA）
  3. `git -C <workdir> stash apply --index <sha>` → 把 dirty 复刻进副本
副本 `git diff HEAD` == 原 `git diff HEAD`（dirty 等价）；clean tree → stash create 返回空 → 跳过 apply。

清理：`git -C <orig> worktree remove --force <workdir>`（best-effort，由调用方在 finally 触发）。

CLI（自检 / 独立测试）:
  python3 scripts/gd-prepare-workcopy.py --orig <git-root> --run-id <id> --output-dir <dir>
  → stdout 打印 workcopy_manifest.json；--verify-then-clean 做 dirty 等价断言后清理。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


GIT_OP_TIMEOUT_SEC = 30  # 与 gd-review-controller.py 对齐（项目内 git 超时唯一锚点，避免分叉）


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd),
                          timeout=GIT_OP_TIMEOUT_SEC)


def _git_root(path: Path) -> Path | None:
    """返回 git toplevel；非 repo 返回 None（合法信号），其他异常向上抛（fail-visible，不静默吞）。"""
    r = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=GIT_OP_TIMEOUT_SEC,
    )
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    return None


def prepare_workcopy(orig_cwd: Path, run_id: str, scratch_base: Path) -> dict:
    """创建 dirty-等价 workcopy，返回 manifest dict。

    manifest 字段: original_cwd / workcopy_cwd / scratch_dir / stash_commit / created_at。
    Raises RuntimeError on any git step failure (fail-closed — 不给 codex 一个半成品副本)。
    """
    orig = Path(orig_cwd).resolve()
    root = _git_root(orig)
    if root is None:
        raise RuntimeError(f"not a git work tree (no toplevel): {orig}")
    orig = root  # worktree/stash 必须在 repo root 上跑

    scratch = Path(scratch_base).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    workdir = scratch / f"wc-{run_id}"
    if workdir.exists():
        # 残留：先尝试清理再建
        subprocess.run(
            ["git", "-C", str(root), "worktree", "remove", "--force", str(workdir)],
            capture_output=True, text=True, timeout=30,
        )

    # 1. linked worktree at HEAD (tracked 文件全在，干净)
    r = _run(["git", "-C", str(root), "worktree", "add", "--detach", str(workdir)], root)
    if r.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {r.stderr.strip()[:200]}")
    if not workdir.exists():
        raise RuntimeError(f"worktree dir not created: {workdir}")

    # 2. capture dirty as a commit object WITHOUT touching the working tree.
    #    stash create 失败 → 副本停留在 HEAD（审 clean 基线）；不致命，stash_commit 留空跳过 apply。
    stash_commit = ""
    try:
        r = _run(["git", "-C", str(root), "stash", "create", "-u"], root)
        if r.returncode == 0:
            stash_commit = (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        pass

    # 3. replicate dirty into the worktree (staged+unstaged+untracked)
    if stash_commit:
        r = _run(
            ["git", "-C", str(workdir), "stash", "apply", "--index", stash_commit],
            workdir,
        )
        if r.returncode != 0:
            # apply 冲突/失败 → 清理副本并 fail-closed（不给 codex 不一致副本）
            subprocess.run(
                ["git", "-C", str(root), "worktree", "remove", "--force", str(workdir)],
                capture_output=True, text=True, timeout=30,
            )
            raise RuntimeError(
                f"git stash apply --index failed (dirty not replicated): {r.stderr.strip()[:200]}"
            )

    manifest = {
        "original_cwd": str(orig),
        "workcopy_cwd": str(workdir),
        "scratch_dir": str(scratch),
        "stash_commit": stash_commit or "",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (scratch / f"workcopy_manifest-{run_id}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def cleanup_workcopy(manifest: dict) -> None:
    """best-effort 移除 worktree（stash create 未建 ref，无需 drop）。"""
    orig = Path(manifest.get("original_cwd", "."))
    workdir = Path(manifest.get("workcopy_cwd", ""))
    if workdir.exists():
        subprocess.run(
            ["git", "-C", str(orig), "worktree", "remove", "--force", str(workdir)],
            capture_output=True, text=True, timeout=30,
        )


def verify_dirty_equivalence(orig: Path, workdir: Path) -> tuple[bool, str]:
    """断言 副本 git diff HEAD == 原 git diff HEAD（dirty 等价）。返回 (ok, reason)。"""
    def _diff(p: Path) -> str:
        r = subprocess.run(
            ["git", "-C", str(p), "diff", "HEAD"], capture_output=True, text=True, timeout=60,
        )
        return r.stdout
    orig_d = _diff(orig)
    wc_d = _diff(workdir)
    if orig_d == wc_d:
        return True, "dirty-equivalent"
    return False, f"diff mismatch: orig={len(orig_d)}c wc={len(wc_d)}c"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--orig", required=True, help="git root to copy dirty from")
    p.add_argument("--run-id", default="selftest", help="run id for scratch naming")
    p.add_argument("--output-dir", required=True, help="scratch base dir (workcopy + manifest)")
    p.add_argument("--verify-then-clean", action="store_true",
                   help="prepare → assert dirty equivalence → cleanup")
    args = p.parse_args()

    manifest = prepare_workcopy(Path(args.orig), args.run_id, Path(args.output_dir))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if args.verify_then_clean:
        ok, reason = verify_dirty_equivalence(Path(manifest["original_cwd"]),
                                              Path(manifest["workcopy_cwd"]))
        print(f"DIRTY_EQUIVALENCE: {'pass' if ok else 'fail'} ({reason})", file=sys.stderr)
        cleanup_workcopy(manifest)
        print("WORKCOPY_CLEANED", file=sys.stderr)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
