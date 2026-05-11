#!/usr/bin/env python3
"""
rev-execution.py — validate execution result against baseline, or render template.

Usage:
  python3 rev-execution.py validate <execution.md> --baseline <baseline.json> --out <conformance.json>
  python3 rev-execution.py render-template --baseline <baseline.json> --baseline-key <key> --out <execution.md>
"""

import argparse
import importlib.util
import json
import os
import re
import sys

GD_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
EXEC_SCHEMA_FILE = os.path.join(GD_ROOT, "schema", "rev-execution-status.schema.json")
BASELINE_PY = os.path.join(GD_ROOT, "scripts", "rev-baseline.py")

# Generic evidence strings (trim + strip backticks before comparison)
GENERIC_EVIDENCE = {
    "完成", "通过", "ok", "done", "见上", "已处理", "正常", "符合预期",
}

# Anchor regex: evidence must contain a backtick-wrapped span with a concrete anchor
ANCHOR_RE = re.compile(
    r"`[^`]*(exit|stdout|stderr|diff|→|result\.|/[A-Za-z0-9._-]+\.[A-Za-z0-9]+)[^`]*`"
)


# --------------------------------------------------------------------------- #
# Dynamic load of rev-baseline.py (hyphen in filename prevents direct import)
# --------------------------------------------------------------------------- #

def _load_rev_baseline():
    spec = importlib.util.spec_from_file_location("rev_baseline", BASELINE_PY)
    if spec is None or spec.loader is None:
        print(f"ERROR: cannot load {BASELINE_PY}", file=sys.stderr)
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_exec_schema():
    path = os.path.realpath(EXEC_SCHEMA_FILE)
    if not os.path.isfile(path):
        print(f"ERROR: exec schema not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Fenced block extraction
# --------------------------------------------------------------------------- #

def _extract_json_block(text):
    """Extract content of ```json rev_execution_status ... ``` block."""
    pattern = r'```json\s+rev_execution_status\s*\n(.*?)```'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None
    return m.group(1).strip()


# --------------------------------------------------------------------------- #
# Evidence / not_run_reason validation (P1 rules — status-branched)
# --------------------------------------------------------------------------- #

def _check_evidence_field(sc_id, evidence):
    """
    For pass/fail rows: evidence must be non-empty, non-generic, and contain anchor.
    Returns list of error strings (empty = OK).
    """
    errors = []
    if not evidence:
        errors.append(f"{sc_id}: evidence is empty (required for pass/fail)")
        return errors

    # Strip backticks and whitespace for generic check
    stripped = evidence.strip().strip("`").strip()
    if stripped.lower() in GENERIC_EVIDENCE:
        errors.append(f"{sc_id}: evidence is generic ({evidence!r}) — must contain concrete output")
        return errors

    if not ANCHOR_RE.search(evidence):
        errors.append(
            f"{sc_id}: evidence lacks backtick anchor — must contain `exit`, `stdout`, `stderr`, "
            f"`diff`, `→`, `result.*` or a file path like `/path/to/file.ext`"
        )
    return errors


def _check_not_run_reason_field(sc_id, not_run_reason):
    """
    For not_run/n_a rows: not_run_reason must be non-empty.
    Returns list of error strings (empty = OK).
    """
    errors = []
    if not not_run_reason:
        errors.append(f"{sc_id}: not_run_reason is empty (required for not_run/n_a)")
    return errors


def _validate_sc_results(sc_results_data, baseline_sc_list):
    """
    Validate sc_results against baseline.
    Returns list of error strings.
    """
    errors = []

    # Build expected set from baseline
    expected_ids = {sc["id"] for sc in baseline_sc_list}

    # Build actual set (check duplicates)
    seen = {}
    for item in sc_results_data:
        sc_id = item.get("id", "?")
        if sc_id in seen:
            errors.append(f"Duplicate SC: {sc_id}")
        seen[sc_id] = item

    actual_ids = set(seen.keys())

    # Check missing / extra
    missing = expected_ids - actual_ids
    if missing:
        errors.append(f"Missing SCs from baseline: {sorted(missing)}")

    extra = actual_ids - expected_ids
    if extra:
        errors.append(f"Extra SCs not in baseline: {sorted(extra)}")

    # Per-SC status-branched evidence check (P1 rules)
    for item in sc_results_data:
        sc_id = item.get("id", "?")
        status = item.get("status", "")
        evidence = item.get("evidence", "")
        not_run_reason = item.get("not_run_reason", "")

        if status in ("pass", "fail"):
            # Check evidence only; do NOT read not_run_reason
            errors.extend(_check_evidence_field(sc_id, evidence))
        elif status in ("not_run", "n_a"):
            # Check not_run_reason only; do NOT read evidence
            errors.extend(_check_not_run_reason_field(sc_id, not_run_reason))
        # Unknown status values are caught by schema validation earlier

    return errors


# --------------------------------------------------------------------------- #
# Validate subcommand
# --------------------------------------------------------------------------- #

def cmd_validate(args):
    exec_path = args.execution
    baseline_path = args.baseline
    out_path = args.out

    if not os.path.isfile(exec_path):
        print(f"ERROR: execution file not found: {exec_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(baseline_path):
        print(f"ERROR: baseline file not found: {baseline_path}", file=sys.stderr)
        sys.exit(1)

    # Load modules
    rev_baseline = _load_rev_baseline()
    exec_schema = _load_exec_schema()

    # Read execution markdown
    exec_text = open(exec_path, "r", encoding="utf-8").read()

    # Extract JSON block
    json_str = _extract_json_block(exec_text)
    if json_str is None:
        _write_conformance(out_path, passed=False, errors=[
            "No ```json rev_execution_status block found in execution file"
        ])
        sys.exit(1)

    # Parse JSON
    try:
        exec_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        _write_conformance(out_path, passed=False, errors=[f"JSON parse error: {e}"])
        sys.exit(1)

    # Schema validation (reuse _validate_against_schema from rev-baseline.py)
    try:
        rev_baseline._validate_against_schema(exec_data, exec_schema)
    except ValueError as e:
        _write_conformance(out_path, passed=False, errors=[f"Schema error: {e}"])
        sys.exit(1)

    # Load baseline
    try:
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _write_conformance(out_path, passed=False, errors=[f"Baseline load error: {e}"])
        sys.exit(1)

    errors = []

    # plan_hash match
    expected_hash = baseline_data.get("plan_hash", "")
    actual_hash = exec_data.get("plan_hash", "")
    if actual_hash != expected_hash:
        errors.append(
            f"plan_hash mismatch: execution has {actual_hash!r}, baseline has {expected_hash!r}"
        )

    # SC set + evidence validation
    sc_errors = _validate_sc_results(exec_data["sc_results"], baseline_data.get("success_criteria", []))
    errors.extend(sc_errors)

    if errors:
        _write_conformance(out_path, passed=False, errors=errors)
        print(f"FAIL: {len(errors)} conformance error(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    else:
        _write_conformance(out_path, passed=True, errors=[])
        print(f"OK: conformance passed ({len(exec_data['sc_results'])} SCs verified)")


def _write_conformance(out_path, passed, errors):
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    data = {"passed": passed, "errors": errors}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# --------------------------------------------------------------------------- #
# Render-template subcommand
# --------------------------------------------------------------------------- #

def cmd_render_template(args):
    baseline_path = args.baseline
    baseline_key = args.baseline_key
    out_path = args.out

    if not os.path.isfile(baseline_path):
        print(f"ERROR: baseline not found: {baseline_path}", file=sys.stderr)
        sys.exit(1)

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    plan_hash = baseline_data.get("plan_hash", "")
    sc_list = baseline_data.get("success_criteria", [])
    goal_chain = baseline_data.get("goal_chain", {})

    # Build markdown table rows
    table_rows = []
    json_sc = []
    for sc in sc_list:
        sc_id = sc["id"]
        table_rows.append(f"| {sc_id} | pass | <!-- evidence here --> | <!-- leave empty --> |")
        json_sc.append({
            "id": sc_id,
            "status": "pass",
            "evidence": "",
            "not_run_reason": ""
        })

    table_md = "\n".join(table_rows)
    json_block = json.dumps({
        "baseline_key": baseline_key,
        "plan_hash": plan_hash,
        "execution_status": "completed",
        "sc_results": json_sc
    }, ensure_ascii=False, indent=2)

    task_goal = goal_chain.get("task", "")
    phase_goal = goal_chain.get("phase", "")

    content = f"""# Execution Result

> REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

## 执行摘要

| 字段 | 值 |
|------|---|
| EXECUTION_STATUS | completed |
| baseline_key | {baseline_key} |
| plan_hash | {plan_hash} |
| 执行时间 | <!-- YYYY-MM-DDTHH:MM:SSZ --> |

TASK_GOAL: {task_goal}
PHASE_GOAL: {phase_goal}

## SC 验收结果

| SC-ID | status | evidence | not_run_reason |
|-------|--------|----------|----------------|
{table_md}

## 执行说明

<!-- 简要描述执行过程、遇到的问题、决策 -->

## 机器可读块

```json rev_execution_status
{json_block}
```
"""

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: template rendered to {out_path} ({len(sc_list)} SCs)")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description="rev-execution: validate or render execution results")
    sub = parser.add_subparsers(dest="cmd")

    p_val = sub.add_parser("validate", help="Validate execution result against baseline")
    p_val.add_argument("execution", help="Path to execution result .md file")
    p_val.add_argument("--baseline", required=True, help="Path to baseline .json")
    p_val.add_argument("--out", required=True, help="Output path for conformance.json")

    p_tmpl = sub.add_parser("render-template", help="Render a filled execution result template")
    p_tmpl.add_argument("--baseline", required=True, help="Path to baseline .json")
    p_tmpl.add_argument("--baseline-key", required=True, help="Baseline key string")
    p_tmpl.add_argument("--out", required=True, help="Output path for rendered .md")

    args = parser.parse_args()
    if args.cmd == "validate":
        cmd_validate(args)
    elif args.cmd == "render-template":
        cmd_render_template(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
