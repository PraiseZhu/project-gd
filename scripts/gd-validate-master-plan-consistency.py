#!/usr/bin/env python3
"""gd-validate-master-plan-consistency.py

Pre-Codex preflight for master-plan consistency.  Reads machine-readable
fenced JSON blocks from a master-plan Markdown file and checks six rules:

  MASTER_PLAN_DISPATCH_DRIFT   — inventory step-ids drift from dispatch_map
  OWNED_FORBIDDEN_OVERLAP      — a step owns and forbids overlapping paths
  DELIVERABLE_NOT_OWNED        — deliverable path not covered by owned_paths
  SC_VERIFY_MISSING            — sc_refs entry has no same-step verify entry
  VERIFY_FUTURE_REFERENCE      — verify.cmd references a later-step deliverable
  PROTECTED_RUNTIME_OWNED      — owned/deliverable path under .claude/scripts|commands|handoff

METRIC_ASSERTION_WEAK is emitted as WARN only (does not fail).

Exit codes
  0  — PREFLIGHT_PASSED or PREFLIGHT_SKIPPED_LEGACY_PLAN (no fenced blocks)
  1  — PREFLIGHT_FAILED (one or more rules triggered)
  2  — usage / parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Optional

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# Paths under these prefixes are protected runtime — ordinary steps must not own them.
_PROTECTED_PREFIXES = [
    PurePosixPath("/Users/praise/.claude/scripts"),
    PurePosixPath("/Users/praise/.claude/commands"),
    PurePosixPath("/Users/praise/.claude/handoff"),
    PurePosixPath("/Users/praise/.claude/history"),
]


def _normalize(p: str) -> PurePosixPath:
    s = p[2:] if p.startswith("./") else p
    return PurePosixPath(s)


def _overlaps(a: str, b: str) -> bool:
    """True iff paths a and b are equal or one is an ancestor of the other."""
    pa, pb = _normalize(a), _normalize(b)
    if pa == pb:
        return True
    try:
        pa.relative_to(pb)
        return True
    except ValueError:
        pass
    try:
        pb.relative_to(pa)
        return True
    except ValueError:
        pass
    return False


def _path_covered_by(p: str, owned: list[str]) -> bool:
    """True if p is covered by any path in owned (same or parent prefix)."""
    return any(_overlaps(p, o) for o in owned)


def _is_protected_runtime(p: str) -> bool:
    """True if p falls under a protected .claude runtime prefix."""
    pn = _normalize(p)
    return any(
        pn == prefix or str(pn).startswith(str(prefix) + "/")
        for prefix in _PROTECTED_PREFIXES
    )


# ---------------------------------------------------------------------------
# Fenced block parser
# ---------------------------------------------------------------------------

_FENCED_BLOCK_RE = re.compile(
    r"^```json\s+([\w-]+)\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)


def _extract_fenced_blocks(text: str) -> dict[str, str]:
    """Return {block_name: raw_json_text} for all ```json <name> fenced blocks."""
    return {m.group(1): m.group(2) for m in _FENCED_BLOCK_RE.finditer(text)}


# ---------------------------------------------------------------------------
# Preflight rules
# ---------------------------------------------------------------------------

def _check_dispatch_drift(
    inventory: dict,
    dispatch_map_path: Optional[str],
    errors: list[str],
) -> None:
    """MASTER_PLAN_DISPATCH_DRIFT (simplified): every step_id in inventory must
    appear in dispatch_map.json.

    Full round-trip generation via gd-build-dispatch-map.py is a follow-up.
    """
    if not dispatch_map_path:
        return

    dm_path = Path(dispatch_map_path)
    if not dm_path.is_file():
        errors.append(
            f"MASTER_PLAN_DISPATCH_DRIFT: dispatch_map_path={dispatch_map_path!r} "
            "does not exist"
        )
        return

    try:
        dm_text = dm_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"MASTER_PLAN_DISPATCH_DRIFT: cannot read dispatch_map — {exc}")
        return

    try:
        json.loads(dm_text)
    except json.JSONDecodeError as exc:
        errors.append(
            f"MASTER_PLAN_DISPATCH_DRIFT: dispatch_map is not valid JSON — {exc}"
        )
        return

    inv_step_ids = [sp["step_id"] for sp in inventory.get("step_plans", [])]
    for sid in inv_step_ids:
        if sid not in dm_text:
            errors.append(
                f"MASTER_PLAN_DISPATCH_DRIFT: step_id={sid!r} in inventory "
                "not found in dispatch_map.json"
            )


def _check_owned_forbidden_overlap(inventory: dict, errors: list[str]) -> None:
    """OWNED_FORBIDDEN_OVERLAP: same step owns and forbids overlapping paths."""
    for sp in inventory.get("step_plans", []):
        sid = sp.get("step_id", "?")
        owned = sp.get("owned_paths", [])
        forbidden = sp.get("forbidden_paths", [])
        for o in owned:
            for f in forbidden:
                if _overlaps(o, f):
                    errors.append(
                        f"OWNED_FORBIDDEN_OVERLAP: step={sid} "
                        f"owns={o!r} conflicts with forbidden={f!r}"
                    )


def _check_deliverable_not_owned(inventory: dict, errors: list[str]) -> None:
    """DELIVERABLE_NOT_OWNED: deliverable path not covered by same-step owned_paths."""
    for sp in inventory.get("step_plans", []):
        sid = sp.get("step_id", "?")
        owned = sp.get("owned_paths", [])
        for d in sp.get("deliverables", []):
            dpath = d.get("path", "")
            if dpath and not _path_covered_by(dpath, owned):
                errors.append(
                    f"DELIVERABLE_NOT_OWNED: step={sid} "
                    f"deliverable={dpath!r} not covered by any owned_path"
                )


def _check_sc_verify_missing(inventory: dict, errors: list[str]) -> None:
    """SC_VERIFY_MISSING: every sc_refs entry must have ≥1 verify entry with same sc_ref."""
    for sp in inventory.get("step_plans", []):
        sid = sp.get("step_id", "?")
        sc_refs = set(sp.get("sc_refs", []))
        verified = {v.get("sc_ref") for v in sp.get("verify", [])}
        for sc in sc_refs:
            if sc not in verified:
                errors.append(
                    f"SC_VERIFY_MISSING: step={sid} sc_ref={sc!r} "
                    "has no verify entry"
                )


def _check_verify_future_reference(
    inventory: dict,
    waves: Optional[dict],
    errors: list[str],
) -> None:
    """VERIFY_FUTURE_REFERENCE: verify.cmd references a deliverable produced by a
    step that runs LATER in wave order and is NOT in blocked_by.

    Uses string search of deliverable paths in verify cmd strings.
    Requires gd-wave-matrix block for ordering; skips if absent.
    """
    if not waves:
        return

    step_plans = inventory.get("step_plans", [])

    # Build step_id → wave_index
    wave_order: dict[str, int] = {}
    for wi, wave in enumerate(waves.get("waves", [])):
        for track in wave.get("tracks", []):
            for sid in track.get("step_ids", []):
                wave_order[sid] = wi

    # Build step_id → set(deliverable_paths)
    step_deliverables: dict[str, set[str]] = {}
    for sp in step_plans:
        step_deliverables[sp["step_id"]] = {
            d["path"] for d in sp.get("deliverables", []) if d.get("path")
        }

    for sp in step_plans:
        sid = sp.get("step_id", "?")
        my_wave = wave_order.get(sid, 0)
        my_owned = set(sp.get("owned_paths", []))
        my_blocked_by = set(sp.get("blocked_by", []))

        all_cmds = " ".join(v.get("cmd", "") for v in sp.get("verify", []))
        if not all_cmds:
            continue

        for other_sid, other_deliv in step_deliverables.items():
            if other_sid == sid:
                continue
            other_wave = wave_order.get(other_sid, 0)
            if other_wave <= my_wave:
                continue  # other step runs before or at same wave — OK
            if other_sid in my_blocked_by:
                continue  # explicit dependency declared — allowed
            for dp in other_deliv:
                if dp and dp in all_cmds and not _path_covered_by(dp, list(my_owned)):
                    errors.append(
                        f"VERIFY_FUTURE_REFERENCE: step={sid} (wave {my_wave}) "
                        f"verify references {dp!r} produced by later "
                        f"step={other_sid} (wave {other_wave}), "
                        "not in blocked_by"
                    )


def _check_protected_runtime_owned(inventory: dict, errors: list[str]) -> None:
    """PROTECTED_RUNTIME_OWNED: owned_paths/deliverables must not include
    protected .claude runtime directories (scripts/commands/handoff/history).
    settings.json is allowed (hook registration).
    """
    for sp in inventory.get("step_plans", []):
        sid = sp.get("step_id", "?")
        for p in sp.get("owned_paths", []):
            if _is_protected_runtime(p):
                errors.append(
                    f"PROTECTED_RUNTIME_OWNED: step={sid} "
                    f"owns protected runtime path {p!r}"
                )
        for d in sp.get("deliverables", []):
            dp = d.get("path", "")
            if dp and _is_protected_runtime(dp):
                errors.append(
                    f"PROTECTED_RUNTIME_OWNED: step={sid} "
                    f"deliverable {dp!r} is under protected runtime"
                )


def _check_metric_assertion_weak(inventory: dict, warnings: list[str]) -> None:
    """METRIC_ASSERTION_WEAK (WARN only): all verify entries for a sc_ref use only
    file-existence checks (method=path) with no numeric assertions.
    """
    _assertion_re = re.compile(
        r"(assert|expect|\-eq|\-lt|\-gt|\-le|\-ge|==|!=|>=|<=|wc\s+-l|grep.*-c)",
        re.IGNORECASE,
    )
    for sp in inventory.get("step_plans", []):
        sid = sp.get("step_id", "?")
        for sc_ref in sp.get("sc_refs", []):
            matches = [v for v in sp.get("verify", []) if v.get("sc_ref") == sc_ref]
            if not matches:
                continue
            all_path_only = all(v.get("method") == "path" for v in matches)
            has_assertion = any(
                _assertion_re.search(v.get("cmd", "") + v.get("expect", ""))
                for v in matches
            )
            if all_path_only and not has_assertion:
                warnings.append(
                    f"METRIC_ASSERTION_WEAK: step={sid} sc_ref={sc_ref!r} "
                    "verify only checks file existence; consider numeric assertions"
                )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(report_path: Optional[str], result: dict) -> None:
    if not report_path:
        return
    try:
        Path(report_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        print(f"WARN: could not write JSON report to {report_path}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Pre-Codex preflight: master-plan consistency check."
    )
    parser.add_argument("master_plan", help="Path to master-plan markdown file")
    parser.add_argument(
        "--dispatch-map",
        help="Path to dispatch_map.json for MASTER_PLAN_DISPATCH_DRIFT check",
    )
    parser.add_argument(
        "--command-cwd",
        help="COMMAND_CWD declared in master-plan (informational, not validated)",
    )
    parser.add_argument(
        "--json-report",
        help="Write JSON result report to this path",
    )
    args = parser.parse_args(argv[1:])

    mp_path = Path(args.master_plan)
    if not mp_path.is_file():
        print(f"ERROR: master_plan not found: {mp_path}", file=sys.stderr)
        return 2

    text = mp_path.read_text(encoding="utf-8")
    blocks = _extract_fenced_blocks(text)

    if "gd-step-plan-inventory" not in blocks:
        status = "SKIPPED_LEGACY_PLAN"
        result: dict = {
            "status": status,
            "errors": [],
            "warnings": [],
            "rules_checked": [],
        }
        print(f"PREFLIGHT_RESULT: {status} (no gd-step-plan-inventory block found)")
        _write_report(args.json_report, result)
        return 0

    try:
        inventory = json.loads(blocks["gd-step-plan-inventory"])
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: gd-step-plan-inventory block is not valid JSON: {exc}",
            file=sys.stderr,
        )
        return 2

    waves: Optional[dict] = None
    if "gd-wave-matrix" in blocks:
        try:
            waves = json.loads(blocks["gd-wave-matrix"])
        except json.JSONDecodeError:
            pass  # VERIFY_FUTURE_REFERENCE will skip ordering checks

    errors: list[str] = []
    warnings: list[str] = []

    _check_dispatch_drift(inventory, args.dispatch_map, errors)
    _check_owned_forbidden_overlap(inventory, errors)
    _check_deliverable_not_owned(inventory, errors)
    _check_sc_verify_missing(inventory, errors)
    _check_verify_future_reference(inventory, waves, errors)
    _check_protected_runtime_owned(inventory, errors)
    _check_metric_assertion_weak(inventory, warnings)

    rules_checked = [
        "MASTER_PLAN_DISPATCH_DRIFT",
        "OWNED_FORBIDDEN_OVERLAP",
        "DELIVERABLE_NOT_OWNED",
        "SC_VERIFY_MISSING",
        "VERIFY_FUTURE_REFERENCE",
        "PROTECTED_RUNTIME_OWNED",
        "METRIC_ASSERTION_WEAK(WARN)",
    ]

    if errors:
        status = "PREFLIGHT_FAILED"
        for e in errors:
            print(f"ERROR: {e}")
        for w in warnings:
            print(f"WARN: {w}")
        print(
            f"PREFLIGHT_RESULT: {status} "
            f"({len(errors)} error(s), {len(warnings)} warning(s))"
        )
        result = {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "rules_checked": rules_checked,
        }
        _write_report(args.json_report, result)
        return 1

    status = "PREFLIGHT_PASSED"
    for w in warnings:
        print(f"WARN: {w}")
    print(
        f"PREFLIGHT_RESULT: {status} "
        f"(0 errors, {len(warnings)} warning(s))"
    )
    result = {
        "status": status,
        "errors": [],
        "warnings": warnings,
        "rules_checked": rules_checked,
    }
    _write_report(args.json_report, result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
