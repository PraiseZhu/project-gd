#!/usr/bin/env python3
"""
rev-baseline.py — extract or validate a rev baseline JSON.

Usage:
  python3 rev-baseline.py extract <plan.md> --project-goal-file <file> --out <candidate.json>
  python3 rev-baseline.py validate <baseline.json>
"""

import argparse
import hashlib
import json
import os
import re
import sys

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "schema", "rev-baseline.schema.json")


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def _load_schema():
    path = os.path.realpath(SCHEMA_FILE)
    if not os.path.isfile(path):
        print(f"ERROR: schema file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_against_schema(data, schema):
    """Minimal Draft-07 validator (no external deps). Raises ValueError on failure."""
    errors = []

    def check(node, subschema, path):
        typ = subschema.get("type")
        if typ == "object":
            if not isinstance(node, dict):
                errors.append(f"{path}: expected object, got {type(node).__name__}")
                return
            # additionalProperties: false
            if subschema.get("additionalProperties") is False:
                allowed = set(subschema.get("properties", {}).keys())
                extra = set(node.keys()) - allowed
                if extra:
                    errors.append(f"{path}: disallowed fields: {sorted(extra)}")
            for req in subschema.get("required", []):
                if req not in node:
                    errors.append(f"{path}: missing required field '{req}'")
            for k, v in subschema.get("properties", {}).items():
                if k in node:
                    check(node[k], v, f"{path}.{k}")
        elif typ == "array":
            if not isinstance(node, list):
                errors.append(f"{path}: expected array, got {type(node).__name__}")
                return
            min_items = subschema.get("minItems", 0)
            if len(node) < min_items:
                errors.append(f"{path}: need >= {min_items} items, got {len(node)}")
            item_schema = subschema.get("items", {})
            for i, item in enumerate(node):
                check(item, item_schema, f"{path}[{i}]")
        elif typ == "string":
            if not isinstance(node, str):
                errors.append(f"{path}: expected string, got {type(node).__name__}")
                return
            min_len = subschema.get("minLength", 0)
            if len(node) < min_len:
                errors.append(f"{path}: string too short (min {min_len})")
            pattern = subschema.get("pattern")
            if pattern and not re.match(pattern, node):
                errors.append(f"{path}: value {node!r} does not match pattern {pattern!r}")

    check(data, schema, "root")
    if errors:
        raise ValueError("\n".join(errors))


def cmd_validate(args):
    path = args.baseline
    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    schema = _load_schema()
    try:
        _validate_against_schema(data, schema)
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {path} is valid")


# --------------------------------------------------------------------------- #
# Extraction helpers
# --------------------------------------------------------------------------- #

def _extract_section(text, heading):
    """Return content between ## heading and next ##, or None."""
    pattern = rf'^## {re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)'
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def _parse_goal_chain(text):
    """Parse ## 目标链 section, return dict with project/chain/phase/task."""
    section = _extract_section(text, "目标链（Goal Chain）") or _extract_section(text, "目标链")
    if not section:
        return None
    result = {}
    mapping = {
        "PROJECT_GOAL": "project",
        "CHAIN_GOAL": "chain",
        "PHASE_GOAL": "phase",
        "TASK_GOAL": "task",
    }
    for key, field in mapping.items():
        m = re.search(rf'^{key}:\s*(.+)$', section, re.MULTILINE)
        if m:
            result[field] = m.group(1).strip()
    return result if len(result) == 4 else None


def _split_table_row(line):
    """Split a Markdown table row on | while ignoring | inside backtick code spans."""
    parts = []
    current = []
    in_code = False
    for ch in line:
        if ch == '`':
            in_code = not in_code
            current.append(ch)
        elif ch == '|' and not in_code:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    # Drop leading/trailing empty segments from outer pipes
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _parse_sc_table(text):
    """Parse ## 成功标准 table, return list of {id, text, verify}."""
    section = _extract_section(text, "成功标准（Success Criteria）") or _extract_section(text, "成功标准")
    if not section:
        return None
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        parts = _split_table_row(line)
        if len(parts) < 3:
            continue
        sc_id = parts[0]
        if not re.match(r'^SC-\d+$', sc_id):
            continue
        rows.append({
            "id": sc_id,
            "text": parts[1],
            "verify": parts[2],
        })
    return rows


def _parse_non_goals(text):
    """Parse ## 非目标 section, return list of strings."""
    section = _extract_section(text, "非目标（Non-Goals）") or _extract_section(text, "非目标")
    if not section:
        return []
    items = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            items.append(line[2:].strip())
    return items


def cmd_extract(args):
    plan_path = args.plan
    goal_file = args.project_goal_file
    out_path = args.out

    if not os.path.isfile(plan_path):
        print(f"ERROR: plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(goal_file):
        print(f"ERROR: project-goal-file not found: {goal_file}", file=sys.stderr)
        sys.exit(1)

    plan_bytes = open(plan_path, "rb").read()
    plan_text = plan_bytes.decode("utf-8", errors="replace")
    plan_hash = hashlib.sha256(plan_bytes).hexdigest()

    # --- goal chain ---
    gc = _parse_goal_chain(plan_text)
    if not gc:
        print("ERROR: could not parse 目标链 section (missing PROJECT_GOAL/CHAIN_GOAL/PHASE_GOAL/TASK_GOAL)", file=sys.stderr)
        sys.exit(1)

    # --- validate PROJECT_GOAL against PROJECT_GOAL.md ---
    goal_text = open(goal_file, "r", encoding="utf-8").read()
    m = re.search(r'^PROJECT_GOAL:\s*(.+)$', goal_text, re.MULTILINE)
    if not m:
        print(f"ERROR: PROJECT_GOAL: field not found in {goal_file}", file=sys.stderr)
        sys.exit(1)
    expected_goal = m.group(1).strip()
    if gc["project"].strip() != expected_goal:
        print(f"ERROR: PROJECT_GOAL mismatch:\n  plan:     {gc['project']!r}\n  expected: {expected_goal!r}", file=sys.stderr)
        sys.exit(1)

    # --- success criteria ---
    sc_list = _parse_sc_table(plan_text)
    if not sc_list:
        print("ERROR: could not parse 成功标准 table", file=sys.stderr)
        sys.exit(1)

    # validate continuity: SC-0 or SC-1 start, no gaps
    ids = [int(sc["id"][3:]) for sc in sc_list]
    if ids[0] not in (0, 1):
        print(f"ERROR: SC numbering must start at SC-0 or SC-1, got SC-{ids[0]}", file=sys.stderr)
        sys.exit(1)
    for i in range(1, len(ids)):
        if ids[i] != ids[i-1] + 1:
            print(f"ERROR: SC numbering gap: SC-{ids[i-1]} followed by SC-{ids[i]}", file=sys.stderr)
            sys.exit(1)

    # validate verify not empty
    for sc in sc_list:
        if not sc["verify"]:
            print(f"ERROR: {sc['id']} has empty Verify column", file=sys.stderr)
            sys.exit(1)

    # --- non-goals ---
    non_goals = _parse_non_goals(plan_text)

    baseline = {
        "goal_chain": gc,
        "success_criteria": sc_list,
        "plan_hash": plan_hash,
        "non_goals": non_goals,
        "accepted_decisions": [],
    }

    # validate before writing
    schema = _load_schema()
    try:
        _validate_against_schema(baseline, schema)
    except ValueError as e:
        print(f"ERROR: generated baseline fails schema validation:\n{e}", file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"OK: baseline written to {out_path} ({len(sc_list)} SCs)")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description="rev-baseline: extract or validate rev baselines")
    sub = parser.add_subparsers(dest="cmd")

    p_extract = sub.add_parser("extract", help="Extract baseline from a plan markdown file")
    p_extract.add_argument("plan", help="Path to plan .md file")
    p_extract.add_argument("--project-goal-file", required=True, help="Path to PROJECT_GOAL.md")
    p_extract.add_argument("--out", required=True, help="Output path for candidate.json")

    p_validate = sub.add_parser("validate", help="Validate an existing baseline JSON against schema")
    p_validate.add_argument("baseline", help="Path to baseline .json file")

    args = parser.parse_args()
    if args.cmd == "extract":
        cmd_extract(args)
    elif args.cmd == "validate":
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
