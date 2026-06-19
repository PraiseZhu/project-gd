#!/usr/bin/env python3
"""gd-validate-execution-outcome.py — Execution outcome artifact validator (H4b).

Phase 1 (original): JSON schema validation only.
Phase 2 (option-A, --plan-file): also extracts SC verify commands from the plan,
    reruns build-gate / non-integration commands via subprocess, and compares
    real exit codes against sc_acceptance declarations.
    Integration / true-API items are explicitly labelled not_run, never skipped silently.

Validates that a /gd execute outcome JSON meets the minimum contract:
  - Required top-level fields: outcome_version, outcome_id, task_outcomes
  - Each task_outcome must have: task_id, exec_status, sc_acceptance
  - sc_acceptance entries must have: sc_ref, status (pass|fail|not_run|n_a)
  - deliverables with must_exist=true must exist on disk
  - No writes outside owned_paths_post_audit (if declared)
  - [Phase 2] build-gate verify commands rerun; declared pass but exit≠0 → FAIL
  - [Phase 2] integration items must be declared not_run (not pass)

Exit codes:
  0  — outcome valid (OUTCOME_VALIDATOR_PASS)
  1  — validation failed (OUTCOME_VALIDATOR_FAIL)
  2  — missing input / unreadable file / interpreter missing

Usage:
  # Phase 1 (schema only, backward-compatible):
  python3 scripts/gd-validate-execution-outcome.py <outcome.json>

  # Phase 2 (schema + verify rerun):
  python3 scripts/gd-validate-execution-outcome.py <outcome.json> \\
      --plan-file <master-plan.md> [--plan-file <step-N.md> ...] \\
      [--timeout 60]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Shell injection patterns that are dangerous in verify commands.
# Note: && and ; are allowed (plan verify commands legitimately use cd && cmd patterns).
# We block: subshell $() / backtick substitution / pipe-to-exec / redirection to /dev/
_SHELL_INJECT_RE = re.compile(r"\$\(|\`[^`]*\`|>\s*/dev/\w|<\s*\(|\|\s*(bash|sh|python3?|exec)\b")

# ── Phase 1 constants ───────────────────────────────────────────────────────

REQUIRED_TOP = {"outcome_version", "outcome_id", "task_outcomes"}
REQUIRED_TASK = {"task_id", "exec_status", "sc_acceptance"}
VALID_EXEC_STATUS = {"completed", "failed", "skipped", "partial"}
VALID_SC_STATUS = {"pass", "fail", "not_run", "n_a"}

# ── Phase 2 constants ───────────────────────────────────────────────────────

GATE_BUILD = "build_gate"          # safe to rerun in CI/validator
GATE_INTEGRATION = "integration"   # needs real API / env; mark not_run, never skip silently
GATE_EXECUTION = "execution_gate"  # needs full pipeline execution context

# Patterns for plan markdown parsing
# Matches: - [ ] SC-1(...)  or  - [x] SC-1(...)
_SC_HDR = re.compile(r"^\s*-\s*\[[ xX]\]\s*(SC-[\d]+(?:[.\-][\w]+)*)", re.MULTILINE)
# Matches: - verify (method: command, build-gate): `cmd here`
_VERIFY = re.compile(
    r"-\s+verify\s*\(method:\s*([^)]+)\)\s*:\s*`([^`]+)`",
    re.MULTILINE | re.DOTALL,
)
# F7 fix: also match §8a SC verification matrix YAML entries:
#   {sc: SC-1, cmd: "...", expect: "..."}  or  - {sc: SC-1, cmd: "..."}
# These appear in the verify[] arrays inside task-packet YAML blocks and in
# the §8a table inline YAML.  We capture the sc ref and the cmd value.
_VERIFY_YAML = re.compile(
    r"\{[^}]*\bsc:\s*(SC-[\d]+(?:[.\-][\w]+)*)\b[^}]*\bcmd:\s*[\"']([^\"']+)[\"'][^}]*\}",
    re.MULTILINE | re.DOTALL,
)
# Matches the §8a matrix table row:  | SC-N | cmd text | expect |
# We extract sc ref and the cmd column (column 2).
_VERIFY_TABLE = re.compile(
    r"^\|[^|]*\|\s*(SC-[\d]+(?:[.\-][\w]+)*)\s*\|[^|]*\|([^|]+)\|",
    re.MULTILINE,
)
# Backtick-quoted command inside a table cell: `cmd`
_BACKTICK_CMD = re.compile(r"`([^`]+)`")
# Markers that indicate a command requires real external resources
_INTEGRATION_MARKERS = (
    "-m integration",
    '-m "integration',
    "--live-sample",
    "--live-transport",
    "akb2.quality.calibration",  # true API calibration run
    "live-sample",
)

DEFAULT_TIMEOUT = 60  # seconds per verify command

def _normalize_sc_ref(ref: str) -> str:
    """Return canonical form: 'SC-N' (uppercase, no 'master ' prefix)."""
    ref = ref.strip()
    # Remove leading "master " (case-insensitive)
    ref = re.sub(r"^master\s+", "", ref, flags=re.IGNORECASE)
    # Ensure uppercase SC-
    ref = re.sub(r"^sc-", "SC-", ref, flags=re.IGNORECASE)
    return ref


# ── Phase 2 helpers ──────────────────────────────────────────────────────────


def _classify_gate(method_str: str, cmd: str) -> str:
    """Return GATE_BUILD, GATE_INTEGRATION, or GATE_EXECUTION for a verify entry."""
    m = method_str.lower()
    # Explicit gate tag in method string
    if "execution-gate" in m:
        return GATE_INTEGRATION  # requires real env / amendment state
    if "integration" in m:
        return GATE_INTEGRATION
    # Command content markers
    for marker in _INTEGRATION_MARKERS:
        if marker in cmd:
            return GATE_INTEGRATION
    # Natural-language descriptions (Chinese characters) are not shell-executable.
    # Format 3 (table) now only emits backtick-quoted commands, so this guard mainly
    # catches Format 2 (YAML) entries whose cmd field is a prose description.
    # Phase 2 skips GATE_EXECUTION entries without requiring not_run status.
    if any(
        "㐀" <= ch <= "䶿"   # CJK Extension A
        or "一" <= ch <= "鿿"  # CJK Unified Ideographs
        or "豈" <= ch <= "﫿"  # CJK Compatibility Ideographs
        for ch in cmd
    ):
        return GATE_EXECUTION
    return GATE_BUILD


def extract_sc_verify_cmds(plan_path: Path) -> list[dict]:
    """SC-1 / F7 fix: extract {sc_ref, cmd, method, gate_type} from a plan markdown.

    Supports three formats found in GD master plans:
    1. Inline verify blocks:  - verify (method: command): `cmd`
    2. §5c task-packet YAML:  {sc: SC-N, cmd: "...", ...}
    3. §8a matrix table row:  | SC-N | cmd text | expect |
    """
    text = plan_path.read_text(encoding="utf-8")
    results: list[dict] = []
    seen_cmds: set[tuple[str, str]] = set()  # (sc_ref, cmd) dedup

    def _add(sc_ref: str, cmd: str, method: str = "command") -> None:
        cmd = cmd.strip()
        if not cmd or len(cmd) < 3:
            return
        if _SHELL_INJECT_RE.search(cmd):
            print(
                f"  WARN: {sc_ref} verify command contains injection-risk pattern "
                f"($() / backtick / pipe-to-shell) — omitting from rerun; "
                f"cmd={cmd[:80]}",
                file=sys.stderr,
            )
            return
        key = (sc_ref, cmd)
        if key in seen_cmds:
            return
        seen_cmds.add(key)
        results.append({
            "sc_ref": sc_ref,
            "cmd": cmd,
            "method": method,
            "gate_type": _classify_gate(method, cmd),
        })

    # Format 1: inline verify blocks inside SC list items
    sc_positions = list(_SC_HDR.finditer(text))
    for idx, sc_match in enumerate(sc_positions):
        sc_ref = sc_match.group(1)
        block_start = sc_match.end()
        block_end = sc_positions[idx + 1].start() if idx + 1 < len(sc_positions) else len(text)
        block = text[block_start:block_end]
        for v_match in _VERIFY.finditer(block):
            _add(sc_ref, v_match.group(2), v_match.group(1).strip())

    # Format 2: §5c task-packet YAML  {sc: SC-N, cmd: "..."}
    for m in _VERIFY_YAML.finditer(text):
        _add(m.group(1), m.group(2))

    # Format 3: §8a matrix table  | SC-N | cmd_col | expect_col |
    # Only extract backtick-quoted content (`cmd`) as executable commands.
    # Bare prose descriptions are not executable and are deliberately excluded —
    # they are verified by child executor smoke tests, not Phase 2 direct re-execution.
    for m in _VERIFY_TABLE.finditer(text):
        sc_ref = m.group(1).strip()
        cmd_col = m.group(2)
        for bt in _BACKTICK_CMD.finditer(cmd_col):
            _add(sc_ref, bt.group(1))

    return results


def _find_python311() -> str | None:
    """SC-4: locate a Python ≥3.11 interpreter; return None if absent."""
    for candidate in ("python3.13", "python3.12", "python3.11"):
        path = shutil.which(candidate)
        if path:
            return path
    # Last resort: check if python3 itself is ≥3.11
    py3 = shutil.which("python3")
    if py3:
        try:
            r = subprocess.run(
                [py3, "-c", "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"],
                capture_output=True,
                timeout=5,
            )
            if r.returncode == 0:
                return py3
        except Exception:
            pass
    return None


def _substitute_python(cmd: str, python_exe: str) -> str:
    """Replace bare 'python3' invocations with the locked interpreter.

    SC-13: Guards against producing '/usr/bin/env /path/to/python3.13' by only
    substituting when python_exe is a clean absolute path (no spaces, no 'env').
    Also strips the /usr/bin/env prefix when replacing so the result is a valid
    executable command.
    """
    # Safety: only substitute if python_exe looks like a clean absolute executable path.
    # Block /usr/bin/env (the indirection binary) but not paths that contain 'env' as a
    # substring (e.g. .pyenv, .venv, virtual_env) — use basename check.
    import os as _os
    if " " in python_exe or _os.path.basename(python_exe) == "env":
        return cmd  # unsafe or indirection binary — skip substitution
    # Strip /usr/bin/env python3 prefix first (SC-13 key fix: avoids /usr/bin/env /path/to/python3)
    cmd = re.sub(r"/usr/bin/env\s+python3(?!\.\d)(\s+-[mc])", rf"{python_exe}\1", cmd)
    # Replace bare python3 -m or python3 -c
    cmd = re.sub(r"\bpython3(?!\.\d)(\s+-[mc])", rf"{python_exe}\1", cmd)
    return cmd


def validate_verify_rerun(
    plan_cmds: list[dict],
    sc_acceptance_by_ref: dict[str, str],
    python_exe: str | None,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[str]:
    """SC-2 + SC-3: classify integration items, rerun build-gate items, compare.
    SC-3: sc_ref values are normalised on both sides before matching.
          Unmatched plan SC-IDs are reported explicitly (not silently skipped).
    """
    errors: list[str] = []

    # SC-3: build normalised lookup from outcome sc_acceptance
    normalised_declared: dict[str, str] = {
        _normalize_sc_ref(k): v for k, v in sc_acceptance_by_ref.items()
    }

    for entry in plan_cmds:
        sc_ref_raw = entry["sc_ref"]
        sc_ref = _normalize_sc_ref(sc_ref_raw)
        cmd = entry["cmd"]
        gate_type = entry["gate_type"]
        declared = normalised_declared.get(sc_ref)

        if declared is None:
            # HIGH-1/2 fix: multi-task executions legitimately have plan SCs absent from
            # a given task's sc_acceptance. Emit a warning (not a hard error) so callers
            # can detect unintentional mismatches without blocking partial-task outcomes.
            print(
                f"  WARN UNMATCHED_SC_REF: plan has '{sc_ref_raw}' (normalised: '{sc_ref}') "
                f"not in sc_acceptance — skipping rerun (may be in another task outcome)",
                file=sys.stderr,
            )
            continue

        # SC-2: integration items must be declared not_run (not pass/fail)
        if gate_type == GATE_INTEGRATION:
            if declared == "pass":
                errors.append(
                    f"{sc_ref}: classified as integration/execution-gate "
                    f"but declared 'pass' — must be 'not_run' with reason; "
                    f"method={entry['method']!r}"
                )
            # If declared not_run / n_a, that's correct — no further check
            continue

        # GATE_EXECUTION: needs full pipeline context (e.g. Chinese prose descriptions
        # from §5c YAML that aren't shell-executable). Skip silently — these are
        # verified by child executor smoke tests, not Phase 2 direct re-execution.
        if gate_type == GATE_EXECUTION:
            continue

        # SC-4 (V3): build-gate command declared not_run/n_a must NOT be silently
        # accepted. build_gate commands are by definition safe to rerun (that is the
        # whole reason for the classification), so a not_run declaration here is a
        # fail-open hole — the executor skipped a gate it should have run. Rerun it
        # and report what the declaration should have been (pass/fail) per real exit.
        rerun_for_not_run = declared in ("not_run", "n_a")

        # Injection check was moved to extract_sc_verify_cmds (parse time); entries
        # reaching here are pre-vetted. Run the command directly.
        effective_cmd = _substitute_python(cmd, python_exe) if python_exe else cmd
        try:
            result = subprocess.run(
                effective_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            actual_exit = result.returncode
        except subprocess.TimeoutExpired:
            errors.append(
                f"{sc_ref}: verify command timed out (>{timeout}s) — "
                f"declared {declared!r}; cmd={cmd[:80]}"
            )
            continue
        except Exception as exc:
            errors.append(f"{sc_ref}: verify command error: {exc}")
            continue

        expected_pass = actual_exit == 0
        if rerun_for_not_run:
            # SC-4 (V3): build_gate was declared not_run/n_a but is rerunnable. We
            # reran it; the declaration should reflect the real result, not not_run.
            should_be = "pass" if expected_pass else "fail"
            snippet_err = result.stderr[:200].strip()
            errors.append(
                f"{sc_ref}: build_gate declared {declared!r} but is rerunnable and "
                f"actually exited {actual_exit} — should be declared {should_be!r} "
                f"(build_gate verify must not be left not_run)\n"
                f"  cmd:    {cmd[:100]}\n"
                f"  stderr: {snippet_err}"
            )
        elif declared == "pass" and not expected_pass:
            snippet_out = result.stdout[:200].strip()
            snippet_err = result.stderr[:200].strip()
            errors.append(
                f"{sc_ref}: DECLARED pass BUT verify exited {actual_exit}\n"
                f"  cmd:    {cmd[:100]}\n"
                f"  stdout: {snippet_out}\n"
                f"  stderr: {snippet_err}"
            )
        elif declared == "fail" and expected_pass:
            errors.append(
                f"{sc_ref}: declared fail but verify exited 0 "
                f"(unexpected pass; possible stale declaration)"
            )

        # SC-14: warn if pytest reported skipped tests under a declared-pass result
        if declared == "pass" and "pytest" in cmd.lower():
            _stdout_clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout or "")
            _skipped_match = re.search(r"\b(\d+)\s+skipped\b", _stdout_clean)
            if _skipped_match:
                _n_skipped = int(_skipped_match.group(1))
                if _n_skipped > 0:
                    print(
                        f"  WARN SKIP_UNDER_PASS: {sc_ref}: verify declared 'pass' "
                        f"but {_n_skipped} test(s) were skipped — review skip reasons; "
                        f"cmd={cmd[:80]}",
                        file=sys.stderr,
                    )

    return errors


# ── Phase 1 validation ───────────────────────────────────────────────────────


def _normalize_to_outcome(data: dict) -> dict:
    """Accept two producer shapes; normalise to the wrapped outcome envelope.

    - **Wrapped envelope** (has ``task_outcomes``): an aggregated ``/gd execute``
      outcome — returned unchanged.
    - **Flat single-result** (``gd-execution-result`` per
      ``gd-child-execute-prompt-template.md`` / ``gd-execution-status.schema.json``:
      top-level ``exec_status`` + ``sc_acceptance``): this is what the execute child
      actually emits. Wrap it into a 1-element ``task_outcomes`` so downstream
      validation runs identically — the gate is NOT weakened, the same per-task
      checks (exec_status / sc_acceptance / deliverables / verify-rerun) still apply.

    Anything else is returned unchanged so the REQUIRED_TOP check fails with a clear
    error (no silent pass).
    """
    if not isinstance(data, dict) or "task_outcomes" in data:
        return data
    if "exec_status" in data and "sc_acceptance" in data:
        task = dict(data)
        task.setdefault("task_id", data.get("result_id", "single"))
        return {
            "outcome_version": data.get("outcome_version", "flat-result-1"),
            "outcome_id": data.get("outcome_id", data.get("result_id", "single")),
            "task_outcomes": [task],
        }
    return data


def validate_schema(path: Path) -> tuple[list[str], dict]:
    """Phase 1: schema-only validation. Returns (errors, data)."""
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"cannot read outcome JSON: {e}"], {}

    if not isinstance(data, dict):
        return ["top-level must be a JSON object"], {}

    # Accept both the wrapped outcome envelope AND the flat gd-execution-result the
    # execute child actually emits (schema drift fix — see _normalize_to_outcome).
    data = _normalize_to_outcome(data)

    missing_top = REQUIRED_TOP - set(data.keys())
    if missing_top:
        return [f"missing required fields: {sorted(missing_top)}"], data

    task_outcomes = data["task_outcomes"]
    if not isinstance(task_outcomes, list):
        errors.append("task_outcomes must be an array")
        return errors, data

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
                    errors.append(
                        f"{prefix}.sc_acceptance[{j}].status invalid: {sc.get('status')!r}"
                    )

        for k, deliv in enumerate(task.get("deliverables", [])):
            if not isinstance(deliv, dict):
                continue
            if deliv.get("must_exist"):
                path_str = deliv.get("path", "")
                if not path_str:
                    errors.append(
                        f"{prefix}.deliverables[{k}]: must_exist=true but path missing"
                    )
                elif not Path(path_str).exists():
                    errors.append(
                        f"{prefix}.deliverables[{k}]: must_exist=true but not found: {path_str!r}"
                    )

    return errors, data


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate /gd execute outcome JSON (H4b).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("outcome", help="Path to outcome JSON file")
    parser.add_argument(
        "--plan-file",
        dest="plan_files",
        metavar="PLAN_MD",
        action="append",
        default=[],
        help="Plan markdown file(s) to extract SC verify commands from "
        "(enables Phase 2 verify-rerun; may be repeated for multiple step files)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Seconds per verify command (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args()

    outcome_path = Path(args.outcome)
    if not outcome_path.exists():
        print(f"OUTCOME_VALIDATOR_FAIL: file not found: {outcome_path}", file=sys.stderr)
        return 2

    # Phase 1: schema validation
    errors, data = validate_schema(outcome_path)

    # SC-4 (V4): if Phase 2 was requested (--plan-file) but a schema flaw blocks it,
    # surface PHASE2_SKIPPED loudly instead of silently dropping the verify-rerun.
    # Otherwise a single schema blemish would quietly disable the strongest gate
    # (actual command rerun) while still printing a PASS-shaped phase1 result.
    if args.plan_files and errors:
        print(
            "PHASE2_SKIPPED: schema validation failed; verify-rerun not executed "
            f"({len(errors)} schema error(s)) — fix schema then re-run with --plan-file",
            file=sys.stderr,
        )

    # Phase 2: verify-rerun (only when --plan-file supplied)
    if args.plan_files and not errors:
        # SC-4: locate Python ≥3.11
        python_exe = _find_python311()
        if python_exe is None:
            print(
                "OUTCOME_VALIDATOR_FAIL: no Python ≥3.11 interpreter found; "
                "cannot safely rerun verify commands (python3=3.9.6 may give false negatives). "
                "Install python3.11+ or set PATH.",
                file=sys.stderr,
            )
            return 2
        print(f"VERIFY_RERUN: using interpreter {python_exe}")

        # SC-1: extract verify commands from all supplied plan files;
        # accumulate by_gate counts in the same pass (no second iteration needed).
        all_plan_cmds: list[dict] = []
        by_gate: dict[str, int] = {}
        for pf in args.plan_files:
            plan_path = Path(pf)
            if not plan_path.exists():
                # HIGH-3 fix: plan-file not found is a missing-input error (exit 2),
                # not a validation failure (exit 1).
                print(
                    f"OUTCOME_VALIDATOR_FAIL: plan-file not found: {pf}",
                    file=sys.stderr,
                )
                return 2
            cmds = extract_sc_verify_cmds(plan_path)
            print(
                f"VERIFY_RERUN: extracted {len(cmds)} verify entries from {plan_path.name}"
            )
            for c in cmds:
                by_gate[c["gate_type"]] = by_gate.get(c["gate_type"], 0) + 1
            all_plan_cmds.extend(cmds)

        for gate, count in sorted(by_gate.items()):
            status = "WILL_RUN" if gate == GATE_BUILD else "NOT_RUN (integration/execution-gate)"
            print(f"VERIFY_RERUN:   {gate}: {count} commands → {status}")

        # Build sc_acceptance lookup (norm-keyed) across all tasks.
        # Storing by normalised key means validate_verify_rerun's own normalisation is
        # a no-op, and duplicate detection needs only one dict (norm → first_raw).
        sc_declared: dict[str, str] = {}        # norm → status
        sc_first_raw: dict[str, str] = {}       # norm → first raw key seen (for dup warn)
        for task in data.get("task_outcomes", []):
            for sc in task.get("sc_acceptance", []):
                if isinstance(sc, dict) and "sc_ref" in sc:
                    raw = sc["sc_ref"]
                    norm = _normalize_sc_ref(raw)
                    if norm in sc_declared:
                        # SC-4 (P2-dup): a duplicate sc_ref must NOT silently
                        # overwrite the first declaration (last-wins could mask a
                        # failing first entry behind a later pass). Keep the FIRST
                        # value and warn loudly so the conflict is visible.
                        if sc.get("status", "") != sc_declared[norm]:
                            print(
                                f"  WARN DUPLICATE_SC_REF: sc_ref '{raw}' normalises to "
                                f"'{norm}' which is already declared "
                                f"'{sc_declared[norm]}' (from '{sc_first_raw.get(norm)}') "
                                f"with conflicting status '{sc.get('status', '')}' "
                                "— keeping FIRST declaration, ignoring later",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"  WARN DUPLICATE_SC_REF: sc_ref '{raw}' normalises to "
                                f"'{norm}' which is already declared "
                                f"(from '{sc_first_raw.get(norm)}') — keeping first",
                                file=sys.stderr,
                            )
                        continue
                    sc_declared[norm] = sc.get("status", "")
                    sc_first_raw[norm] = raw

        # SC-2 + SC-3: classify and rerun
        rerun_errors = validate_verify_rerun(
            all_plan_cmds, sc_declared, python_exe, timeout=args.timeout
        )
        errors.extend(rerun_errors)

    if errors:
        print("OUTCOME_VALIDATOR_FAIL")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    phase = "phase1+phase2" if args.plan_files else "phase1"
    print(f"OUTCOME_VALIDATOR_PASS ({phase})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
