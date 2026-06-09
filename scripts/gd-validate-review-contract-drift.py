#!/usr/bin/env python3
"""gd-validate-review-contract-drift.py — AST-based review contract drift scanner.

Scans consumer scripts for local enum/frozenset definitions that duplicate
the SSOT enums in gd_review_contract.py. Local definitions are forbidden
because they diverge silently when the SSOT changes.

SSOT protected names (from gd_review_contract.py):
  REVIEW_KIND_ENUM, TEMPLATE_KIND_ENUM, REVIEW_TARGET_KIND_ENUM,
  DECISION_ENUM, TARGET_ROLE_ENUM, REVIEW_KIND_V1_ENUM, TEMPLATE_KIND_V1_ENUM

Usage:
  # Scan all main-chain scripts
  python3 scripts/gd-validate-review-contract-drift.py

  # Scan specific files
  python3 scripts/gd-validate-review-contract-drift.py scripts/gd-codex-bridge-review.py

  # Allow list mode (check allowlist path)
  python3 scripts/gd-validate-review-contract-drift.py --allowlist fixtures/review-contract-drift/allowlist.json

Exit codes:
  0 = no local enum violations found
  1 = violations found (printed to stdout)
  2 = usage error
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

GD_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = GD_ROOT / "scripts"
SSOT_MODULE = "gd_review_contract"

# Names in SSOT that must not be locally redefined in consumer scripts
PROTECTED_NAMES = frozenset({
    "REVIEW_KIND_ENUM",
    "TEMPLATE_KIND_ENUM",
    "REVIEW_TARGET_KIND_ENUM",
    "DECISION_ENUM",
    "TARGET_ROLE_ENUM",
    "REVIEW_KIND_V1_ENUM",
    "TEMPLATE_KIND_V1_ENUM",
    "MODE_ENUM",
    "NEXT_ACTION_ENUM",
    "TARGET_ROLE_ENUM",
})

# Default scan targets: all .py in scripts/ except SSOT itself
DEFAULT_SCAN = [
    p for p in SCRIPTS.glob("*.py")
    if p.stem != SSOT_MODULE and p.stem != "gd-validate-review-contract-drift"
] + list((SCRIPTS / "lib").glob("*.py"))


def _is_frozenset_or_set_literal(node: ast.expr) -> bool:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "frozenset":
            return True
    if isinstance(node, ast.Set):
        return True
    return False


def scan_file(path: Path, allowlist: set[str]) -> list[tuple[str, int, str]]:
    """Return list of (path_str, lineno, message) for violations."""
    violations = []
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src, str(path))
    except (SyntaxError, OSError):
        return []

    for node in ast.walk(tree):
        # Top-level or class-level assignments: NAME = frozenset(...) or NAME = {...}
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                name = target.id
                if name not in PROTECTED_NAMES:
                    continue
                allow_key = f"{path.name}:{name}"
                if allow_key in allowlist:
                    continue
                if not _is_frozenset_or_set_literal(node.value):
                    continue
                # Skip imports / re-exports (from gd_review_contract import X; X = X is fine)
                violations.append((
                    str(path.relative_to(GD_ROOT)),
                    node.lineno,
                    f"LOCAL_ENUM_DEFINITION: {name!r} — must import from {SSOT_MODULE}, "
                    f"not define locally. Add '{allow_key}' to allowlist if intentional."
                ))

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for review contract enum drift.")
    parser.add_argument(
        "files", nargs="*", help="Files to scan (default: all main-chain scripts/)"
    )
    parser.add_argument(
        "--allowlist",
        default=str(GD_ROOT / "fixtures" / "review-contract-drift" / "allowlist.json"),
        help="JSON file with allowed local definitions (array of 'filename:NAME' strings)",
    )
    args = parser.parse_args()

    # Load allowlist
    allowlist: set[str] = set()
    allow_path = Path(args.allowlist)
    if allow_path.exists():
        try:
            entries = json.loads(allow_path.read_text())
            allowlist = set(entries) if isinstance(entries, list) else set()
        except (json.JSONDecodeError, OSError):
            pass

    # Determine scan targets
    if args.files:
        targets = [Path(f) for f in args.files]
    else:
        targets = DEFAULT_SCAN

    all_violations: list[tuple[str, int, str]] = []
    for t in targets:
        if not t.exists():
            print(f"WARNING: file not found, skipping: {t}", file=sys.stderr)
            continue
        all_violations.extend(scan_file(t, allowlist))

    if all_violations:
        print(f"CONTRACT_DRIFT: {len(all_violations)} violation(s) found:\n")
        for path_str, lineno, msg in sorted(all_violations):
            print(f"  {path_str}:{lineno}: {msg}")
        return 1

    scanned = len(targets)
    print(f"OK: no contract drift — {scanned} file(s) scanned, 0 violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
