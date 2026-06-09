#!/usr/bin/env python3
"""gd-detect-review2-code-target — /review2 code 三档判定脚本.

判定逻辑（无覆盖 flag 时）：
  has_code   = git 工作树有未提交 diff（git diff / git diff --cached / untracked）
  has_result = 目录内发现执行产物 JSON（含 outcome_id / execution_status 等签名字段）

  has_code=True,  has_result=False → REVIEW2_CODE_TARGET: code-only       exit 0
  has_code=False, has_result=True  → REVIEW2_CODE_TARGET: execution-only  exit 0
  has_code=True,  has_result=True  → REVIEW2_CODE_TARGET: combined        exit 0
  否（两者皆 False 或探测失败）    → REVIEW2_CODE_TARGET: INDETERMINATE   exit 2

覆盖 flag（--code / --result / --combined）互斥：
  传一个 → 跳过自动判定，直接输出对应档位，exit 0
  传 >=2 个 → 报错 exit 1（互斥，不静默取任一个）

输出格式（stdout）：
  REVIEW2_CODE_TARGET: code-only|execution-only|combined|INDETERMINATE
  REVIEW2_TRIAGE_BASIS: <依据>

用途：/review2 code 入口调用，三档判定后告知用户确认再分支执行（守 D1：判不准问用户不猜）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 执行产物探测（复用 gd_review_detection 共享模块）
# ---------------------------------------------------------------------------

def _try_import_shared_detection():
    """尝试 import 仓库共享模块 gd_review_detection；返回 has_execution_artifacts_in_dir 函数或 None。"""
    try:
        # 本脚本在 scripts/ 目录，gd_review_detection.py 同目录
        script_dir = Path(__file__).resolve().parent
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gd_review_detection",
            script_dir / "gd_review_detection.py",
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return getattr(mod, "has_execution_artifacts_in_dir", None)
    except Exception:
        return None


def _builtin_is_execution_json(path: Path) -> bool:
    """内置执行产物探测（共享模块不可用时的 fallback）。"""
    import json
    if not path.is_file() or path.suffix != ".json":
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    _EXEC_SIGNATURE_FIELDS = frozenset({
        "outcome_id", "task_outcomes", "outcome_version",
        "execution_status", "exec_status",
    })
    return bool(_EXEC_SIGNATURE_FIELDS & set(data.keys()))


_EXECUTION_SCAN_EXCLUDE_DIRS: frozenset[str] = frozenset({
    "fixtures", "plans", "docs", "archive", "_tmp", "tests", "test",
    "node_modules", ".git",
})


def _builtin_has_execution_artifacts_in_dir(directory: Path) -> bool:
    """内置目录扫描（共享模块不可用时的 fallback）。

    只扫 directory 的直接子目录和 results/ 等已知产物位置，排除 fixtures/、
    plans/、docs/ 等噪声目录，避免把历史 fixture JSON 误判为本次执行产物。
    """
    if not directory.is_dir():
        return False
    for candidate in directory.rglob("*.json"):
        # 排除 _ 前缀临时文件
        if candidate.name.startswith("_"):
            continue
        # 排除已知噪声目录（检查路径任意一段是否命中排除集合）
        if any(part in _EXECUTION_SCAN_EXCLUDE_DIRS for part in candidate.parts):
            continue
        if _builtin_is_execution_json(candidate):
            return True
    return False


# ---------------------------------------------------------------------------
# git 工作树变化探测
# ---------------------------------------------------------------------------

def _detect_has_code(cwd: Path) -> tuple[bool, str]:
    """探测 cwd 的 git 工作树是否有未提交改动（unstaged / staged / untracked）。

    返回 (has_code: bool, basis_detail: str)。
    basis_detail 说明来源（哪种 git 探测命中或均未命中）。
    """
    def _run(args: list[str]) -> tuple[int, str]:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout.strip()

    # 1. unstaged diff（已追踪文件的工作树变化）
    rc, out = _run(["git", "diff"])
    if rc == 0 and out:
        return True, "git_diff_unstaged=non-empty"

    # 2. staged diff（已 add 但未 commit 的变化）
    rc, out = _run(["git", "diff", "--cached"])
    if rc == 0 and out:
        return True, "git_diff_cached=non-empty"

    # 3. untracked 文件（git ls-files --others --exclude-standard）
    # 排除 _tmp/、dispatch/、plans/ 等非代码产物目录，避免临时文件被误判为代码改动
    _UNTRACKED_EXCLUDE_PREFIXES = ("_tmp/", "dispatch/", "plans/", "docs/", "archive/")
    rc, out = _run(["git", "ls-files", "--others", "--exclude-standard"])
    if rc == 0 and out:
        code_files = [
            f for f in out.splitlines()
            if f and not any(f.startswith(p) for p in _UNTRACKED_EXCLUDE_PREFIXES)
        ]
        if code_files:
            return True, "git_untracked=non-empty"

    # 4. git 命令均失败（非 git 目录）→ 探测失败，has_code 视为 False
    rc_check, _ = _run(["git", "rev-parse", "--git-dir"])
    if rc_check != 0:
        return False, "git_not_a_repo"

    return False, "git_diff=empty,git_diff_cached=empty,git_untracked=empty"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gd-detect-review2-code-target",
        description=(
            "/review2 code 三档判定脚本。\n"
            "自动探测 git 工作树改动（has_code）与执行产物文件（has_result），\n"
            "输出 REVIEW2_CODE_TARGET: code-only|execution-only|combined|INDETERMINATE\n"
            "与 REVIEW2_TRIAGE_BASIS: <依据>。\n"
            "\n"
            "覆盖 flag（--code / --result / --combined）互斥：传一个则跳过自动判定直接输出对应档位；\n"
            "传 >=2 个互斥 flag 则报错 exit 1。\n"
            "\n"
            "INDETERMINATE 时 exit 2（交上层问用户，守 D1：判不准不擅自猜）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--cwd",
        metavar="DIR",
        default=".",
        help="git 工作目录（默认：当前目录）",
    )
    override_group = parser.add_mutually_exclusive_group()
    override_group.add_argument(
        "--code",
        action="store_true",
        default=False,
        help="覆盖：强制 REVIEW2_CODE_TARGET=code-only，跳过自动判定",
    )
    override_group.add_argument(
        "--result",
        action="store_true",
        default=False,
        help="覆盖：强制 REVIEW2_CODE_TARGET=execution-only，跳过自动判定",
    )
    override_group.add_argument(
        "--combined",
        action="store_true",
        default=False,
        help="覆盖：强制 REVIEW2_CODE_TARGET=combined，跳过自动判定",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    cwd = Path(args.cwd).resolve()

    # ------------------------------------------------------------------
    # 覆盖 flag 路径（argparse add_mutually_exclusive_group 已保证互斥）
    # ------------------------------------------------------------------
    if args.code:
        print("REVIEW2_CODE_TARGET: code-only")
        print("REVIEW2_TRIAGE_BASIS: user_override(--code)")
        return 0
    if args.result:
        print("REVIEW2_CODE_TARGET: execution-only")
        print("REVIEW2_TRIAGE_BASIS: user_override(--result)")
        return 0
    if args.combined:
        print("REVIEW2_CODE_TARGET: combined")
        print("REVIEW2_TRIAGE_BASIS: user_override(--combined)")
        return 0

    # ------------------------------------------------------------------
    # 自动判定路径
    # ------------------------------------------------------------------
    has_code, code_basis = _detect_has_code(cwd)

    # 执行产物探测：只扫已知产物子目录，不扫全仓（避免 fixtures/plans 误判）
    # 已知产物目录：results/、output/、reports/ — 不含 fixtures/、plans/、_tmp/
    _RESULT_SCAN_DIRS = ["results", "output", "reports"]
    shared_fn = _try_import_shared_detection()
    has_result = False
    result_basis = "no_execution_artifact_found"
    for _scan_subdir in _RESULT_SCAN_DIRS:
        _scan_path = cwd / _scan_subdir
        if not _scan_path.is_dir():
            continue
        if shared_fn is not None:
            _found = shared_fn(_scan_path)
            _basis = f"gd_review_detection({_scan_subdir}/)"
        else:
            _found = _builtin_has_execution_artifacts_in_dir(_scan_path)
            _basis = f"builtin({_scan_subdir}/)"
        if _found:
            has_result = True
            result_basis = _basis
            break

    triage_basis = f"has_code={has_code}({code_basis}),has_result={has_result}({result_basis})"

    _TARGET_MAP = {
        (True, False): "code-only",
        (False, True): "execution-only",
        (True, True):  "combined",
    }
    target = _TARGET_MAP.get((has_code, has_result))
    if target is not None:
        print(f"REVIEW2_CODE_TARGET: {target}")
        print(f"REVIEW2_TRIAGE_BASIS: {triage_basis}")
        return 0

    # (False, False) → INDETERMINATE，exit 2（交上层问用户，守 D1）
    print("REVIEW2_CODE_TARGET: INDETERMINATE")
    print(f"REVIEW2_TRIAGE_BASIS: {triage_basis}")
    print(
        "ERROR: 无法自动判定审查档位（未发现 git 工作树改动，也未发现执行产物文件）。"
        " 请使用 --code / --result / --combined 明确指定后重试。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
