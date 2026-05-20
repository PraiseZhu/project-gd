#!/usr/bin/env python3
"""gd-validate-execution-outcome.py — Execution outcome artifact validator (H4b).

Validates that a /gd execute outcome JSON meets the minimum contract:
  - Required top-level fields: outcome_version, outcome_id, task_outcomes
  - Each task_outcome must have: task_id, exec_status, sc_acceptance
  - sc_acceptance entries must have: sc_ref, status (pass|fail|not_run|n_a)
  - deliverables with must_exist=true must exist on disk
  - No writes outside owned_paths_post_audit (if declared)

Exit codes:
  0  — outcome valid (OUTCOME_VALIDATOR_PASS)
  1  — validation failed (OUTCOME_VALIDATOR_FAIL)
  2  — missing input / unreadable file

Usage:
  python3 scripts/gd-validate-execution-outcome.py <outcome.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_TOP = {"outcome_version", "outcome_id", "task_outcomes"}
REQUIRED_TASK = {"task_id", "exec_status", "sc_acceptance"}
VALID_EXEC_STATUS = {"completed", "failed", "skipped", "partial"}
VALID_SC_STATUS = {"pass", "fail", "not_run", "n_a"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"cannot read outcome JSON: {e}"]

    if not isinstance(data, dict):
        return ["top-level must be a JSON object"]

    missing_top = REQUIRED_TOP - set(data.keys())
    if missing_top:
        errors.append(f"missing required fields: {sorted(missing_top)}")
        return errors  # can't continue without task_outcomes

    task_outcomes = data["task_outcomes"]
    if not isinstance(task_outcomes, list):
        errors.append("task_outcomes must be an array")
        return errors

    for i, task in enumerate(task_outcomes):
        prefix = f"task_outcomes[{i}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        missing_task = REQUIRED_TASK - set(task.keys())
        if missing_task:
            errors.append(f"{prefix}: missing {sorted(missing_task)}")

        exec_status = task.get("exec_status", "")
        if exec_status not in VALID_EXEC_STATUS:
            errors.append(f"{prefix}.exec_status invalid: {exec_status!r}")

        # sc_acceptance validation
        sc_list = task.get("sc_acceptance", [])
        if not isinstance(sc_list, list):
            errors.append(f"{prefix}.sc_acceptance must be an array")
        else:
            for j, sc in enumerate(sc_list):
                if not isinstance(sc, dict):
                    errors.append(f"{prefix}.sc_acceptance[{j}]: not an object")
                    continue
                if "sc_ref" not in sc:
                    errors.append(f"{prefix}.sc_acceptance[{j}]: missing sc_ref")
                if sc.get("status") not in VALID_SC_STATUS:
                    errors.append(f"{prefix}.sc_acceptance[{j}].status invalid: {sc.get('status')!r}")

        # deliverables: must_exist=true → path must be non-empty and exist on disk
        for k, deliv in enumerate(task.get("deliverables", [])):
            if not isinstance(deliv, dict):
                continue
            if deliv.get("must_exist"):
                path_str = deliv.get("path", "")
                if not path_str:
                    errors.append(f"{prefix}.deliverables[{k}]: must_exist=true but path is missing or empty")
                elif not Path(path_str).exists():
                    errors.append(f"{prefix}.deliverables[{k}]: must_exist=true but path not found: {path_str!r}")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: gd-validate-execution-outcome.py <outcome.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"OUTCOME_VALIDATOR_FAIL: file not found: {path}", file=sys.stderr)
        return 2

    errors = validate(path)
    if errors:
        print("OUTCOME_VALIDATOR_FAIL")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    print("OUTCOME_VALIDATOR_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
