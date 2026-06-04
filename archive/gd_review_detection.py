"""gd_review_detection — shared artifact classification module.

Provides the canonical decision matrix for /gd review router:
  - classify_artifacts: maps (has_plan, has_exec, has_code_diff, bundle_declared)
    → REVIEW_TARGET_KIND_ENUM value
  - has_execution_artifacts_in_dir: filesystem probe for execution JSON files
  - is_execution_json: content-based heuristic for execution outcome JSON

Imported by gd-review-router.py; also callable from gd-detect-review-target.py.
"""
from __future__ import annotations

import json
from pathlib import Path

# Execution outcome signature fields (any one sufficient to classify)
_EXEC_SIGNATURE_FIELDS = frozenset({
    "outcome_id", "task_outcomes", "outcome_version",
    "execution_status", "exec_status",
})


def classify_artifacts(
    has_plan: bool,
    has_exec: bool,
    has_code_diff: bool,
    bundle_declared: bool = False,
) -> str:
    """Map artifact presence flags to a review target kind.

    Priority (highest first):
      execution_plus_code  – exec + (plan or code)
      plan_only            – plan, no exec
      execution_only_no_code – exec, no plan/code
      code_only            – code diff declared, no exec
      no_artifact          – nothing detected
    """
    if has_exec and (has_plan or has_code_diff or bundle_declared):
        return "execution_plus_code"
    if has_exec:
        return "execution_only_no_code"
    if has_plan:
        return "plan_only"
    if has_code_diff or bundle_declared:
        return "code_only"
    return "no_artifact"


def is_execution_json(path: Path) -> bool:
    """Return True if *path* looks like an execution outcome JSON artifact."""
    if not path.is_file() or path.suffix != ".json":
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    return bool(_EXEC_SIGNATURE_FIELDS & set(data.keys()))


def has_execution_artifacts_in_dir(directory: Path) -> bool:
    """Return True if *directory* contains at least one execution outcome JSON."""
    if not directory.is_dir():
        return False
    for candidate in directory.rglob("*.json"):
        if candidate.name.startswith("_"):
            continue
        if is_execution_json(candidate):
            return True
    return False
