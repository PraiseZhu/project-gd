#!/usr/bin/env python3
"""
gd-validate-route-report.py — Plan 5 v3 Wave A1

Single source of truth for route report schema validation (v2).

Validates route reports written by gd-review-router.py:
  - required fields (schema_version / router_invocation_id / mode / review_target_kind /
    decision / validator_signature / recorded_at / findings)
  - enum values for mode / review_target_kind / decision
  - validator_signature: validator field must reference this script by name
  - recorded_at: ISO 8601 calendar-valid datetime
  - additionalProperties: open (consumers may add extra fields, subject to enum lock)
  - schema_version must be "2.0"

Q2 (Plan 5 v3): validator_signature field signed by this script — consumers that
read route reports can subprocess this validator to confirm schema integrity without
grep-based fragile checks.

SC-1 (Q1): binding validators must be in KNOWN allowlist and REQUIRED set present; validated in self-test mode.

CLI:
  python3 scripts/gd-validate-route-report.py <route_report.json>
  python3 scripts/gd-validate-route-report.py --self-test   # singleton check + schema

Exit codes:
  0 = valid
  1 = schema violation (stderr lists violations)
  2 = usage error / file not found
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


GD_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = GD_ROOT / "scripts"

# Plan 8 v4.1 Step 2: enums sourced from SSOT (gd_review_contract).
sys.path.insert(0, str(SCRIPTS))
from gd_review_contract import (  # noqa: E402
    MODE_ENUM,
    REVIEW_TARGET_KIND_ENUM,
    DECISION_ENUM,
    TARGET_KIND_TO_LEGAL_DECISIONS,
)

SCHEMA_VERSION = "2.0"
THIS_VALIDATOR_NAME = "gd-validate-route-report.py"

# Plan 8 v4.1 Step 8: enum for code_only.patch_generation_method
PATCH_GENERATION_METHOD_ENUM = frozenset({"git_diff", "manual", "review_tool"})

# 64-char lowercase hex (sha256) — used for plan_hash / diff_hash / raw_result_hash
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

KNOWN_BINDING_VALIDATORS = {
    "gd-validate-runtime-strict-binding.py",
    "gd-validate-subplan-codex-binding.py",
}
REQUIRED_BINDING_VALIDATORS = {
    "gd-validate-runtime-strict-binding.py",
}

REQUIRED_FIELDS = {
    "schema_version",
    "router_invocation_id",
    "mode",
    "review_target_kind",
    "decision",
    "validator_signature",
    "recorded_at",
    "findings",
}

ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)


def _is_valid_iso8601_datetime(value: str) -> tuple[bool, str | None]:
    if not isinstance(value, str):
        return False, f"expected string, got {type(value).__name__}"
    if not ISO8601_RE.fullmatch(value):
        return False, f"shape regex failed for {value!r}"
    normalised = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        _dt.datetime.fromisoformat(normalised)
    except ValueError as exc:
        return False, f"calendar parse failed: {exc} (value={value!r})"
    return True, None


def validate_route_report(data: dict) -> list[str]:
    """Full schema validation. Returns list of violations (empty = pass)."""
    violations: list[str] = []

    # required fields
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        violations.append(f"required: missing {sorted(missing)}")

    # schema_version must be "2.0"
    sv = data.get("schema_version")
    if sv is not None and sv != SCHEMA_VERSION:
        violations.append(
            f"schema_version: expected {SCHEMA_VERSION!r}, got {sv!r}"
        )

    # mode enum
    mode = data.get("mode")
    if mode is not None:
        if not isinstance(mode, str):
            violations.append(f"mode: expected string, got {type(mode).__name__}")
        elif mode not in MODE_ENUM:
            violations.append(f"mode: {mode!r} not in enum {sorted(MODE_ENUM)}")

    # review_target_kind enum
    rtk = data.get("review_target_kind")
    if rtk is not None:
        if not isinstance(rtk, str):
            violations.append(
                f"review_target_kind: expected string, got {type(rtk).__name__}"
            )
        elif rtk not in REVIEW_TARGET_KIND_ENUM:
            violations.append(
                f"review_target_kind: {rtk!r} not in enum {sorted(REVIEW_TARGET_KIND_ENUM)}"
            )

    # decision enum
    decision = data.get("decision")
    if decision is not None:
        if not isinstance(decision, str):
            violations.append(
                f"decision: expected string, got {type(decision).__name__}"
            )
        elif decision not in DECISION_ENUM:
            violations.append(
                f"decision: {decision!r} not in enum {sorted(DECISION_ENUM)}"
            )

    # validator_signature: must reference this script (Q2)
    vs = data.get("validator_signature")
    if vs is not None:
        if not isinstance(vs, dict):
            violations.append(
                f"validator_signature: expected object, got {type(vs).__name__}"
            )
        else:
            vs_name = vs.get("validator")
            vs_schema = vs.get("schema_version")
            if vs_name != THIS_VALIDATOR_NAME:
                violations.append(
                    f"validator_signature.validator: expected {THIS_VALIDATOR_NAME!r}, "
                    f"got {vs_name!r}"
                )
            if vs_schema != SCHEMA_VERSION:
                violations.append(
                    f"validator_signature.schema_version: expected {SCHEMA_VERSION!r}, "
                    f"got {vs_schema!r}"
                )

    # router_invocation_id: non-empty string
    rid = data.get("router_invocation_id")
    if rid is not None:
        if not isinstance(rid, str) or not rid.strip():
            violations.append(
                "router_invocation_id: must be a non-empty string"
            )

    # recorded_at: ISO 8601 calendar-valid
    ra = data.get("recorded_at")
    if ra is not None:
        ok, reason = _is_valid_iso8601_datetime(ra)
        if not ok:
            violations.append(
                f"recorded_at: must be valid ISO 8601 date-time; {reason}"
            )

    # findings: must be array
    findings = data.get("findings")
    if findings is not None and not isinstance(findings, list):
        violations.append(
            f"findings: expected array, got {type(findings).__name__}"
        )

    # Mode-specific contracts
    mode_str = mode if isinstance(mode, str) else ""
    decision_str = decision if isinstance(decision, str) else ""
    findings_list = data.get("findings", []) if isinstance(data.get("findings"), list) else []

    if mode_str == "live_dry_run":
        # Must NOT claim transport was "available" — bridge was mocked.
        transport = data.get("codex_transport_status")
        if transport == "available":
            violations.append(
                "live_dry_run: 'codex_transport_status' must not be 'available' — "
                "Codex bridge was not called; use 'mocked' or 'not_called'"
            )
        # Must declare bridge was mocked: notes contains "mock" OR finding from "router_mock".
        notes = data.get("notes", "")
        has_mock_notes = isinstance(notes, str) and "mock" in notes.lower()
        has_mock_finding = any(
            isinstance(f, dict) and f.get("reviewer") == "router_mock"
            for f in findings_list
        )
        if not has_mock_notes and not has_mock_finding:
            violations.append(
                "live_dry_run: mock indicator required — 'notes' must contain 'mock' "
                "(case-insensitive) or findings must include reviewer='router_mock'"
            )

    if mode_str == "live" and decision_str in ("APPROVED", "REQUIRES_CHANGES"):
        # Execution-Review Cross-Review v2: execution-only/plus-code targets use
        # codex_raw_result_path (layered) instead of legacy raw_result_path.
        # Legacy raw_result_path check applies only to plan_only and code_only.
        _layered_kinds = {"execution_only_no_code", "execution_plus_code"}
        if rtk not in _layered_kinds:
            # Live APPROVED and REQUIRES_CHANGES both must reference raw Codex result for audit.
            # REQUIRES_CHANGES is a valid Codex result, not a transport failure.
            if not data.get("raw_result_path"):
                violations.append(
                    f"live/{decision_str}: 'raw_result_path' required — live review must reference "
                    "a raw Codex result artifact"
                )
            if not data.get("raw_result_hash"):
                violations.append(
                    f"live/{decision_str}: 'raw_result_hash' required — live review must include "
                    "raw result hash for audit traceability"
                )

    # review_target_kind contracts — outcome-first enforcement.
    # Applies for fixture (simulated) and live (production) modes.
    # detect_only only detects (no review). live_dry_run is an acknowledged mock.
    rtk_str = rtk if isinstance(rtk, str) else ""
    _review_attempted = mode_str in ("fixture", "live")

    if rtk_str == "execution_only_no_code" and _review_attempted:
        if not data.get("execution_artifact_ref"):
            violations.append(
                "execution_only_no_code: 'execution_artifact_ref' required — "
                "must reference the execution artifact under review"
            )
        if "outcome_validator_status" not in data:
            violations.append(
                "execution_only_no_code: 'outcome_validator_status' required — "
                "must record whether outcome validation passed or failed"
            )
        # Execution-Review Cross-Review v2: Codex cross-review fields required when live.
        # APPROVED additionally requires codex_review_status=completed.
        if mode_str == "live":
            cs = data.get("codex_review_status")
            valid_cs = {"completed", "requires_changes", "transport_failed",
                        "wrapper_schema_fail", "not_run_blocked"}
            if cs is None:
                violations.append(
                    "execution_only_no_code/live: 'codex_review_status' required — "
                    "must record Codex cross-review outcome"
                )
            elif cs not in valid_cs:
                violations.append(
                    f"execution_only_no_code/live: 'codex_review_status' must be one of "
                    f"{sorted(valid_cs)}; got {cs!r}"
                )
            if decision_str == "APPROVED":
                if cs != "completed":
                    violations.append(
                        f"execution_only_no_code/live/APPROVED: codex_review_status must be "
                        f"'completed' (cross-review pass); got {cs!r}"
                    )
                for f in ("codex_raw_result_path", "codex_raw_result_hash",
                          "codex_mapped_result_path", "codex_mapped_result_hash",
                          "codex_review_kind"):
                    if not data.get(f):
                        violations.append(
                            f"execution_only_no_code/live/APPROVED: {f!r} required — "
                            "Codex raw/mapped artifacts and review kind must be recorded"
                        )
                # Codex raw evidence integrity checks (Execution-Review v2 hardening).
                # These close the gap where router wrote .raw_unknown path + all-zero hash
                # and validator still passed. APPROVED requires genuine Codex raw evidence.
                import hashlib as _hl
                from pathlib import Path as _P
                _raw_path = data.get("codex_raw_result_path", "")
                _raw_hash = data.get("codex_raw_result_hash", "")
                # 1. raw path must not end with .raw_unknown (synthetic placeholder)
                if _raw_path and _raw_path.endswith(".raw_unknown"):
                    violations.append(
                        "execution_only_no_code/live/APPROVED: 'codex_raw_result_path' ends with "
                        "'.raw_unknown' — this is a synthetic placeholder, not a real Codex raw file; "
                        "re-run with real Codex transport"
                    )
                # 2. raw hash must not be all-zeros (unset sentinel)
                if _raw_hash and _raw_hash == "0" * 64:
                    violations.append(
                        "execution_only_no_code/live/APPROVED: 'codex_raw_result_hash' is all-zeros "
                        "(0x000...000) — sentinel value means raw was not actually hashed; "
                        "re-run with real Codex transport to obtain genuine hash"
                    )
                # 3. raw file must exist on disk
                if _raw_path and not _raw_path.endswith(".raw_unknown"):
                    _raw_file = _P(_raw_path)
                    if not _raw_file.exists():
                        violations.append(
                            f"execution_only_no_code/live/APPROVED: 'codex_raw_result_path' does not "
                            f"exist on disk: {_raw_path!r} — raw evidence file is missing"
                        )
                    # 4. raw file hash must match declared hash
                    elif _raw_hash and _raw_hash != "0" * 64:
                        _actual_hash = _hl.sha256(_raw_file.read_bytes()).hexdigest()
                        if _actual_hash != _raw_hash:
                            violations.append(
                                f"execution_only_no_code/live/APPROVED: 'codex_raw_result_hash' "
                                f"({_raw_hash[:16]}...) does not match actual file hash "
                                f"({_actual_hash[:16]}...) for {_raw_path!r} — "
                                "raw evidence has been tampered with or path is stale"
                            )
            # raw_result_path MUST NOT equal execution_artifact_ref (Execution-Review v2).
            # raw_result_path is for legacy fields; Codex evidence goes to codex_raw_result_path.
            raw_p = data.get("raw_result_path")
            exec_p = data.get("execution_artifact_ref")
            if raw_p and exec_p and raw_p == exec_p:
                violations.append(
                    "execution_only_no_code: 'raw_result_path' must NOT equal "
                    "'execution_artifact_ref' — target artifact and review raw result "
                    "must be distinct (see schema/gd-route-report.schema.json)"
                )

    if rtk_str == "execution_plus_code" and _review_attempted:
        if not data.get("execution_artifact_ref"):
            violations.append(
                "execution_plus_code: 'execution_artifact_ref' required"
            )
        ovs = data.get("outcome_validator_status")
        # Fail-closed path (decision=FAILED + blocked_by/failure_code) may use not_run_blocked.
        _is_fail_closed = (
            decision_str == "FAILED"
            and bool(data.get("blocked_by") or data.get("failure_code"))
        )
        if ovs is None:
            violations.append(
                "execution_plus_code: 'outcome_validator_status' required"
            )
        elif ovs == "not_run_blocked":
            if not _is_fail_closed:
                violations.append(
                    "execution_plus_code: 'outcome_validator_status=not_run_blocked' only allowed "
                    "when decision=FAILED with blocked_by or failure_code set"
                )
        elif ovs != "passed":
            violations.append(
                f"execution_plus_code: 'outcome_validator_status' must be 'passed' "
                f"before code review proceeds (or 'not_run_blocked' for fail-closed); got {ovs!r}"
            )
        stage_order = data.get("stage_order")
        if stage_order is None:
            violations.append(
                "execution_plus_code: 'stage_order' required — must be [\"outcome\", \"code\"]"
            )
        elif stage_order != ["outcome", "code"]:
            violations.append(
                f"execution_plus_code: 'stage_order' must be [\"outcome\", \"code\"]; "
                f"got {stage_order!r}"
            )

    # Plan 8 v4.1 Step 8 — plan_only required fields
    if rtk_str == "plan_only" and _review_attempted:
        plan_ref = data.get("plan_ref")
        if not isinstance(plan_ref, str) or not plan_ref.strip():
            violations.append(
                "plan_only: 'plan_ref' required — non-empty string referencing the plan under review"
            )
        plan_hash = data.get("plan_hash")
        if not isinstance(plan_hash, str) or not plan_hash.strip():
            violations.append(
                "plan_only: 'plan_hash' required — sha256 of plan contents (64-char hex)"
            )
        elif not SHA256_HEX_RE.fullmatch(plan_hash):
            violations.append(
                f"plan_only: 'plan_hash' must be 64-char lowercase hex sha256; got {plan_hash!r}"
            )

    # Plan 8 v4.1 Step 8 — code_only required fields
    if rtk_str == "code_only" and _review_attempted:
        diff_source = data.get("diff_source")
        if not isinstance(diff_source, str) or not diff_source.strip():
            violations.append(
                "code_only: 'diff_source' required — non-empty string identifying the diff origin"
            )
        diff_hash = data.get("diff_hash")
        if not isinstance(diff_hash, str) or not diff_hash.strip():
            violations.append(
                "code_only: 'diff_hash' required — sha256 of diff contents (64-char hex)"
            )
        elif not SHA256_HEX_RE.fullmatch(diff_hash):
            violations.append(
                f"code_only: 'diff_hash' must be 64-char lowercase hex sha256; got {diff_hash!r}"
            )
        method = data.get("patch_generation_method")
        if method is None:
            violations.append(
                "code_only: 'patch_generation_method' required — "
                f"one of {sorted(PATCH_GENERATION_METHOD_ENUM)}"
            )
        elif method not in PATCH_GENERATION_METHOD_ENUM:
            violations.append(
                f"code_only: 'patch_generation_method' {method!r} not in enum "
                f"{sorted(PATCH_GENERATION_METHOD_ENUM)}"
            )

    # Plan 8 v4.1 Step 8 — no_artifact required fields.
    # Enforced for fixture/live (review-mode) reports. detect_only and live_dry_run
    # produce detection-only records and are exempt from review-audit fields.
    if rtk_str == "no_artifact" and _review_attempted:
        failure_code = data.get("failure_code")
        if not isinstance(failure_code, str) or not failure_code.strip():
            violations.append(
                "no_artifact: 'failure_code' required — non-empty string explaining "
                "why no reviewable artifact was found"
            )
        if not isinstance(findings_list, list) or len(findings_list) == 0:
            violations.append(
                "no_artifact: 'findings' must be a non-empty array describing why no "
                "artifact is present"
            )

    # Plan 8 v4.1 Step 8 — ambiguous_mixed_artifacts required fields.
    # Same review-mode gating as no_artifact.
    if rtk_str == "ambiguous_mixed_artifacts" and _review_attempted:
        das = data.get("detected_artifact_set")
        if not isinstance(das, dict):
            violations.append(
                "ambiguous_mixed_artifacts: 'detected_artifact_set' required — object with "
                "boolean keys 'has_plan', 'has_execution', 'has_code'"
            )
        else:
            for key in ("has_plan", "has_execution", "has_code"):
                if key not in das:
                    violations.append(
                        f"ambiguous_mixed_artifacts: 'detected_artifact_set.{key}' missing"
                    )
                elif not isinstance(das[key], bool):
                    violations.append(
                        f"ambiguous_mixed_artifacts: 'detected_artifact_set.{key}' must be "
                        f"boolean; got {type(das[key]).__name__}"
                    )
        failure_code = data.get("failure_code")
        if not isinstance(failure_code, str) or not failure_code.strip():
            violations.append(
                "ambiguous_mixed_artifacts: 'failure_code' required — non-empty string "
                "explaining the ambiguity"
            )
        if not isinstance(findings_list, list) or len(findings_list) == 0:
            violations.append(
                "ambiguous_mixed_artifacts: 'findings' must be a non-empty array describing "
                "the mixed-artifact condition"
            )
        if mode_str == "live" and data.get("raw_result_path"):
            violations.append(
                "ambiguous_mixed_artifacts + live: 'raw_result_path' must not be set — "
                "Codex must not be invoked for ambiguous mixed artifacts"
            )

    # Plan 8 v4.1 Step 8 — decision-legality enforcement per target kind (SSOT-driven)
    if rtk_str and decision_str:
        legal = TARGET_KIND_TO_LEGAL_DECISIONS.get(rtk_str)
        if legal is not None and decision_str not in legal:
            violations.append(
                f"{rtk_str}: decision {decision_str!r} not in legal set {sorted(legal)}"
            )

    # Plan 8 v4.1 Step 8 — mode rules
    # detect_only never writes a final approved decision (detection only)
    if mode_str == "detect_only" and decision_str == "APPROVED":
        violations.append(
            "detect_only: decision must not be 'APPROVED' — detect_only is detection-only "
            "and never writes a final approved review decision"
        )

    # live + no_artifact: Codex must not be invoked
    if mode_str == "live" and rtk_str == "no_artifact" and data.get("raw_result_path"):
        violations.append(
            "no_artifact + live: 'raw_result_path' must not be set — "
            "Codex must not be invoked when no reviewable artifact exists"
        )

    # Step 5 — child review ledger mandatory for execution/code targets on APPROVED live.
    # APPROVED on execution_only_no_code, execution_plus_code, code_only requires a
    # child_review_ledger_path so the mandatory code review pass is auditable.
    _child_review_required_kinds = {
        "execution_only_no_code", "execution_plus_code", "code_only"
    }
    if (mode_str == "live" and decision_str == "APPROVED"
            and rtk_str in _child_review_required_kinds):
        ledger_path_str = data.get("child_review_ledger_path")
        if not ledger_path_str:
            violations.append(
                f"{rtk_str}/live/APPROVED: 'child_review_ledger_path' required — "
                "APPROVED closure requires a mandatory child code/execution review; "
                "missing ledger means the child review was never recorded "
                "(CLOSURE_INELIGIBLE: missing_child_review_ledger)"
            )
        else:
            # D3 (G4 symmetry): validate ledger file physically exists and is valid JSON
            _ledger_p = Path(ledger_path_str)
            if not _ledger_p.is_file():
                violations.append(
                    f"{rtk_str}/live/APPROVED: child_review_ledger_path file not found — "
                    f"{ledger_path_str!r} does not exist on disk "
                    "(CLOSURE_INELIGIBLE: ledger_file_not_found)"
                )
            else:
                try:
                    json.loads(_ledger_p.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as _e:
                    violations.append(
                        f"{rtk_str}/live/APPROVED: child_review_ledger_path invalid JSON — "
                        f"{_ledger_p.name}: {_e} "
                        "(CLOSURE_INELIGIBLE: ledger_invalid_json)"
                    )

    # Plan GD-L1L3 SC-5/SC-7 — code_only/live/APPROVED real Codex code_diff sidecar evidence.
    # code-only APPROVED requires a REAL Codex code_diff sidecar: codex raw/mapped artifacts
    # (distinct from the .patch diff artifact), codex_review_status=completed,
    # codex_review_kind=code_diff, mapped JSON body itself code_diff, and the child ledger
    # must pass the stage-dispatch-ledger validator (not just be JSON-readable).
    if (mode_str == "live" and decision_str == "APPROVED" and rtk_str == "code_only"):
        cs = data.get("codex_review_status")
        if cs in {"transport_failed", "wrapper_schema_fail", "not_run_blocked"}:
            violations.append(
                f"code_only/live/APPROVED: codex_review_status={cs!r} indicates Codex did not "
                "complete; cannot claim APPROVED"
            )
        elif cs != "completed":
            violations.append(
                f"code_only/live/APPROVED: codex_review_status must be 'completed' "
                f"(real Codex code_diff sidecar); got {cs!r}"
            )
        ck = data.get("codex_review_kind")
        if ck != "code_diff":
            violations.append(
                f"code_only/live/APPROVED: codex_review_kind must be 'code_diff'; got {ck!r}"
            )
        # Placeholder/static failure codes incompatible with APPROVED
        _bad_fc = {"LOCAL_STATIC_ONLY", "pending_future_plan", "static-only"}
        fc = data.get("failure_code")
        if fc in _bad_fc:
            violations.append(
                f"code_only/live/APPROVED: failure_code={fc!r} is a placeholder/static status "
                "incompatible with APPROVED (real Codex sidecar must replace it)"
            )

        # required codex evidence fields
        for _f in ("codex_raw_result_path", "codex_raw_result_hash",
                   "codex_mapped_result_path", "codex_mapped_result_hash"):
            if not data.get(_f):
                violations.append(
                    f"code_only/live/APPROVED: {_f!r} required — real Codex code_diff "
                    "sidecar raw/mapped artifacts must be recorded"
                )

        _raw_path = data.get("codex_raw_result_path", "")
        _raw_hash = data.get("codex_raw_result_hash", "")
        _mapped_path = data.get("codex_mapped_result_path", "")
        _mapped_hash = data.get("codex_mapped_result_hash", "")
        _diff_path = data.get("raw_result_path", "")

        # raw must not be .raw_unknown / all-zeros
        if _raw_path and _raw_path.endswith(".raw_unknown"):
            violations.append(
                "code_only/live/APPROVED: 'codex_raw_result_path' ends with '.raw_unknown' — "
                "synthetic placeholder, not real Codex raw"
            )
        if _raw_hash and _raw_hash == "0" * 64:
            violations.append(
                "code_only/live/APPROVED: 'codex_raw_result_hash' is all-zeros sentinel — "
                "raw was not actually hashed"
            )
        # three-artifact separation: codex_raw != diff (.patch), mapped != diff, mapped != raw
        # raw_result_path is the .patch diff artifact; its hash must equal diff_hash
        if (_diff_path and data.get("raw_result_hash") and data.get("diff_hash")
                and data.get("raw_result_hash") != data.get("diff_hash")):
            violations.append(
                "code_only/live/APPROVED: raw_result_hash must equal diff_hash "
                "(raw_result_path is the .patch diff artifact)"
            )
        if _raw_path and _diff_path and _raw_path == _diff_path:
            violations.append(
                "code_only/live/APPROVED: 'codex_raw_result_path' must NOT equal "
                "'raw_result_path' — the .patch diff artifact and the Codex raw review "
                "must be distinct (three-artifact separation)"
            )
        if _mapped_path and _diff_path and _mapped_path == _diff_path:
            violations.append(
                "code_only/live/APPROVED: 'codex_mapped_result_path' must NOT equal "
                "'raw_result_path' — mapped Codex JSON is not the .patch diff artifact"
            )
        if _mapped_path and _raw_path and _mapped_path == _raw_path:
            violations.append(
                "code_only/live/APPROVED: 'codex_mapped_result_path' must NOT equal "
                "'codex_raw_result_path' — mapped JSON and raw review are distinct"
            )
        if _mapped_path and (_mapped_path.endswith(".patch") or _mapped_path.endswith(".raw_unknown")):
            violations.append(
                f"code_only/live/APPROVED: 'codex_mapped_result_path' must be the mapped JSON, "
                f"not a .patch / .raw_unknown file; got {_mapped_path!r}"
            )

        # file existence + hash integrity for raw / mapped; cache mapped bytes for the
        # JSON-body check below (avoids reading the mapped file twice).
        _mapped_bytes = None
        for _label, _pval, _hval in (
            ("codex_raw_result_path", _raw_path, _raw_hash),
            ("codex_mapped_result_path", _mapped_path, _mapped_hash),
        ):
            if not _pval or _pval.endswith(".raw_unknown"):
                continue
            _fobj = Path(_pval)
            if not _fobj.exists():
                violations.append(
                    f"code_only/live/APPROVED: {_label!r} does not exist on disk: {_pval!r}"
                )
                continue
            _fb = _fobj.read_bytes()
            if _label == "codex_mapped_result_path":
                _mapped_bytes = _fb
            if _hval and _hval != "0" * 64:
                _actual = hashlib.sha256(_fb).hexdigest()
                if _actual != _hval:
                    violations.append(
                        f"code_only/live/APPROVED: {_label.replace('_path', '_hash')!r} "
                        f"({_hval[:16]}...) does not match actual file hash "
                        f"({_actual[:16]}...) — evidence tampered or path stale"
                    )

        # mapped JSON body must itself be code_diff (review_kind / target_role / template_kind)
        if _mapped_bytes is not None:
            try:
                _mj = json.loads(_mapped_bytes)
            except (OSError, json.JSONDecodeError) as _e:
                violations.append(
                    f"code_only/live/APPROVED: codex_mapped_result_path is not valid JSON: {_e}"
                )
                _mj = None
            if isinstance(_mj, dict):
                if _mj.get("review_kind") != "code_diff":
                    violations.append(
                        f"code_only/live/APPROVED: mapped JSON review_kind must be "
                        f"'code_diff'; got {_mj.get('review_kind')!r}"
                    )
                if _mj.get("target_role") != "code_diff":
                    violations.append(
                        f"code_only/live/APPROVED: mapped JSON target_role must be "
                        f"'code_diff'; got {_mj.get('target_role')!r}"
                    )
                if _mj.get("template_kind") != "gd-code-diff-review":
                    violations.append(
                        f"code_only/live/APPROVED: mapped JSON template_kind must be "
                        f"'gd-code-diff-review'; got {_mj.get('template_kind')!r}"
                    )
                # mapped JSON verdict must agree with route decision=APPROVED — otherwise
                # a Codex REQUIRES_CHANGES result can back a route APPROVED (伪绿).
                _mj_decision = _mj.get("gd_review_decision") or _mj.get("decision")
                if str(_mj_decision).strip().upper() != "APPROVED":
                    violations.append(
                        f"code_only/live/APPROVED: mapped JSON verdict must be 'APPROVED' "
                        f"(route decision=APPROVED); got {_mj_decision!r}"
                    )

        # child ledger hash integrity + stage-dispatch-ledger validator (not just JSON-readable)
        _ledger_path = data.get("child_review_ledger_path")
        _ledger_hash = data.get("child_review_ledger_hash")
        # defense-in-depth: reject path traversal before passing _ledger_path to the
        # stage-dispatch-ledger subprocess (which reads the file). Route reports are
        # router-produced (ledger under output_dir) or operator-supplied, but a crafted
        # path with '..' must not let the subprocess read arbitrary files.
        if _ledger_path and ".." in Path(_ledger_path).parts:
            violations.append(
                f"code_only/live/APPROVED: child_review_ledger_path contains '..' "
                f"— path traversal rejected: {_ledger_path!r}"
            )
        elif _ledger_path and Path(_ledger_path).is_file():
            if _ledger_hash:
                _actual_lh = hashlib.sha256(Path(_ledger_path).read_bytes()).hexdigest()
                if _actual_lh != _ledger_hash:
                    violations.append(
                        f"code_only/live/APPROVED: child_review_ledger_hash "
                        f"({_ledger_hash[:16]}...) does not match actual ledger file hash "
                        f"({_actual_lh[:16]}...) — ledger tampered or stale"
                    )
            _ledger_val = SCRIPTS / "gd-validate-stage-dispatch-ledger.py"
            if _ledger_val.exists():
                try:
                    _r = subprocess.run(
                        [sys.executable, str(_ledger_val), _ledger_path],
                        capture_output=True, text=True, timeout=30,
                    )
                    if _r.returncode != 0:
                        violations.append(
                            f"code_only/live/APPROVED: child ledger failed stage-dispatch-ledger "
                            f"validation (exit {_r.returncode}): "
                            f"{(_r.stderr or _r.stdout).strip()[:200]}"
                        )
                except (OSError, subprocess.TimeoutExpired) as _e:
                    violations.append(
                        f"code_only/live/APPROVED: could not run stage-dispatch-ledger "
                        f"validator: {_e}"
                    )
            # SC-7: ledger-internal evidence binding — child_jobs[].result_path/hash and
            # main_agent_merge.merge_report_path/hash must resolve to real files whose sha256
            # matches, and final_decision must be APPROVED. A schema-valid ledger with forged
            # internal hashes must NOT back an APPROVED (otherwise a fake ledger props up a
            # 伪绿 APPROVED). The merge report is a standalone file (router writes it separate
            # from the route report) so merge_report_hash is cross-checkable without the
            # route↔ledger hash circular dependency.
            try:
                _ledger_obj = json.loads(Path(_ledger_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                _ledger_obj = None  # stage-dispatch-ledger subprocess already flags JSON errors
            if isinstance(_ledger_obj, dict):
                for _cj in (_ledger_obj.get("child_jobs") or []):
                    _crp = _cj.get("result_path")
                    _crh = _cj.get("result_hash")
                    if _crp and ".." in Path(_crp).parts:
                        violations.append(
                            f"code_only/live/APPROVED: ledger child result_path contains '..' "
                            f"— rejected: {_crp!r}"
                        )
                        continue
                    if _crp and _crh and Path(_crp).is_file():
                        _actual_crh = hashlib.sha256(Path(_crp).read_bytes()).hexdigest()
                        if _actual_crh != _crh:
                            violations.append(
                                f"code_only/live/APPROVED: ledger child result_hash "
                                f"({_crh[:16]}...) does not match actual file "
                                f"({_actual_crh[:16]}...) for {_crp!r} — forged ledger"
                            )
                _merge = _ledger_obj.get("main_agent_merge") or {}
                _mfd = _merge.get("final_decision")
                if _mfd != "APPROVED":
                    violations.append(
                        f"code_only/live/APPROVED: ledger main_agent_merge.final_decision "
                        f"must be 'APPROVED'; got {_mfd!r}"
                    )
                _mrp = _merge.get("merge_report_path")
                _mrh = _merge.get("merge_report_hash")
                if _mrp and ".." in Path(_mrp).parts:
                    violations.append(
                        f"code_only/live/APPROVED: ledger merge_report_path contains '..' "
                        f"— rejected: {_mrp!r}"
                    )
                elif _mrp and _mrh and Path(_mrp).is_file():
                    _actual_mrh = hashlib.sha256(Path(_mrp).read_bytes()).hexdigest()
                    if _actual_mrh != _mrh:
                        violations.append(
                            f"code_only/live/APPROVED: ledger merge_report_hash "
                            f"({_mrh[:16]}...) does not match actual file "
                            f"({_actual_mrh[:16]}...) for {_mrp!r} — forged merge report"
                        )


    # Step 5 — review_run_status failure statuses are incompatible with APPROVED.
    # These statuses indicate Codex transport or wrapper did not produce a valid verdict;
    # APPROVED is unsupported when any of these are set.
    _run_failure_statuses = {
        "failed_to_run", "timeout", "degraded", "transport_failed", "wrapper_schema_fail"
    }
    review_run_status = data.get("review_run_status")
    if decision_str == "APPROVED" and review_run_status in _run_failure_statuses:
        violations.append(
            f"APPROVED with review_run_status={review_run_status!r} is not allowed — "
            f"run status indicates review did not complete; decision must be REQUIRES_CHANGES "
            f"or FAILED when review_run_status is in {sorted(_run_failure_statuses)}"
        )
    # Also check codex_review_status for transport_failed / wrapper_schema_fail
    # (these are the primary status fields for Codex transport; reject APPROVED + failure status)
    _codex_failure_statuses = {"transport_failed", "wrapper_schema_fail"}
    cs_check = data.get("codex_review_status")
    if decision_str == "APPROVED" and cs_check in _codex_failure_statuses:
        # Note: execution_only_no_code already enforces cs=='completed' above;
        # this catch-all covers other kinds that may carry codex_review_status.
        if rtk_str not in ("execution_only_no_code",):
            violations.append(
                f"APPROVED with codex_review_status={cs_check!r} is not allowed — "
                "Codex transport failure or schema fail means no valid verdict was produced; "
                "decision must not be APPROVED"
            )

    return violations


def validate_file(path: Path) -> tuple[int, list[str]]:
    if not path.exists():
        return 2, [f"file not found: {path}"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 1, [f"JSON parse error: {exc}"]
    if not isinstance(raw, dict):
        return 1, ["top-level value must be an object"]
    violations = validate_route_report(raw)
    return (1 if violations else 0), violations


def run_self_test() -> int:
    """Q1: assert known binding validators exist and no unknown ones."""
    errors: list[str] = []

    # SC-1 binding validator allowlist check
    binding_validators = list(SCRIPTS.glob("gd-validate-*binding*.py"))
    found_names = {p.name for p in binding_validators}
    missing = REQUIRED_BINDING_VALIDATORS - found_names
    unknown = found_names - KNOWN_BINDING_VALIDATORS
    if missing:
        errors.append(
            f"BINDING_VALIDATOR_MISSING: required validators not found: {sorted(missing)}"
        )
    if unknown:
        errors.append(
            f"BINDING_VALIDATOR_UNKNOWN: unexpected validators not in allowlist: {sorted(unknown)}"
        )
    if not missing and not unknown:
        print(f"  SC-1 binding validators: {sorted(found_names)} (all known, required present) ✓")

    # Self-schema check: validate a minimal valid fixture inline
    # NOTE: plan_only target now requires plan_ref + plan_hash (Step 8); included
    # so the base sample remains a valid passing fixture for re-use across cases.
    _SHA_ZERO = "0" * 64
    sample = {
        "schema_version": "2.0",
        "router_invocation_id": "selftest-001",
        "mode": "fixture",
        "review_target_kind": "plan_only",
        "decision": "APPROVED",
        "validator_signature": {
            "validator": THIS_VALIDATOR_NAME,
            "schema_version": "2.0",
        },
        "recorded_at": "2026-01-01T00:00:00Z",
        "findings": [],
        "plan_ref": "fixtures/plans/sample-plan.md",
        "plan_hash": _SHA_ZERO,
    }
    violations = validate_route_report(sample)
    if violations:
        errors.append(f"self-schema check FAIL: {violations}")
    else:
        print("  self-schema check: PASS ✓")

    # Negative: bad mode must fail
    bad = dict(sample, mode="invalid_mode_xyz")
    v = validate_route_report(bad)
    if not v:
        errors.append("negative test FAIL: bad mode should produce violations but got none")
    else:
        print(f"  negative (bad mode): violation captured ✓")

    # Negative: bad decision must fail
    bad2 = dict(sample, decision="WRONG_DECISION")
    v2 = validate_route_report(bad2)
    if not v2:
        errors.append("negative test FAIL: bad decision should produce violations but got none")
    else:
        print(f"  negative (bad decision): violation captured ✓")

    # Negative: wrong validator_signature must fail
    bad3 = dict(sample, validator_signature={"validator": "some-other-validator.py", "schema_version": "2.0"})
    v3 = validate_route_report(bad3)
    if not v3:
        errors.append("negative test FAIL: wrong validator_signature should produce violations but got none")
    else:
        print(f"  negative (wrong validator_signature): violation captured ✓")

    # Negative: live_dry_run without mock indicator must fail
    bad4 = dict(sample, mode="live_dry_run", notes="live_dry_run: real detection ran")
    v4 = validate_route_report(bad4)
    if not v4:
        errors.append("negative test FAIL: live_dry_run missing mock indicator should produce violations")
    else:
        print(f"  negative (live_dry_run no mock): violation captured ✓")

    # Positive: live_dry_run with mock in notes must pass
    good_ldr = dict(sample, mode="live_dry_run",
                    notes="live_dry_run: Codex bridge was MOCKED — not a real review result")
    v_good = validate_route_report(good_ldr)
    if v_good:
        errors.append(f"positive test FAIL: live_dry_run with mock notes should pass but got {v_good}")
    else:
        print(f"  positive (live_dry_run mock notes): PASS ✓")

    # Positive: live_dry_run with router_mock finding (no notes) must pass
    good_ldr2 = dict(sample, mode="live_dry_run",
                     findings=[{"reviewer": "router_mock", "severity": "info", "description": "mock"}])
    v_good2 = validate_route_report(good_ldr2)
    if v_good2:
        errors.append(f"positive test FAIL: live_dry_run with router_mock finding should pass but got {v_good2}")
    else:
        print(f"  positive (live_dry_run router_mock finding): PASS ✓")

    # Negative: live/APPROVED without raw_result_path and raw_result_hash must fail
    bad5 = dict(sample, mode="live", decision="APPROVED")
    v5 = validate_route_report(bad5)
    if not v5:
        errors.append("negative test FAIL: live/APPROVED missing raw fields should produce violations")
    else:
        print(f"  negative (live/APPROVED no raw): violation captured ({len(v5)} violations) ✓")

    # Negative: live_dry_run with codex_transport_status=available must fail
    bad6 = dict(sample, mode="live_dry_run",
                notes="live_dry_run: Codex bridge was MOCKED",
                codex_transport_status="available")
    v6 = validate_route_report(bad6)
    if not v6:
        errors.append("negative test FAIL: live_dry_run codex_transport_status=available should fail")
    else:
        print(f"  negative (live_dry_run transport=available): violation captured ✓")

    # Negative: execution_only_no_code missing execution_artifact_ref must fail
    bad7 = dict(sample, review_target_kind="execution_only_no_code",
                outcome_validator_status="passed")
    v7 = validate_route_report(bad7)
    if not v7:
        errors.append("negative test FAIL: execution_only_no_code missing execution_artifact_ref should fail")
    else:
        print(f"  negative (execution_only_no_code no artifact ref): violation captured ✓")

    # Negative: execution_plus_code missing stage_order and outcome_validator_status must fail
    bad8 = dict(sample, review_target_kind="execution_plus_code",
                execution_artifact_ref="fixtures/execution-results/valid-closure.json")
    v8 = validate_route_report(bad8)
    if not v8:
        errors.append("negative test FAIL: execution_plus_code missing stage_order/outcome_status should fail")
    else:
        print(f"  negative (execution_plus_code missing order/status): violation captured ({len(v8)} violations) ✓")

    # Negative: execution_plus_code with wrong stage_order must fail
    bad9 = dict(sample, review_target_kind="execution_plus_code",
                execution_artifact_ref="fixtures/execution-results/valid-closure.json",
                outcome_validator_status="passed",
                stage_order=["code", "outcome"])
    v9 = validate_route_report(bad9)
    if not v9:
        errors.append("negative test FAIL: execution_plus_code wrong stage_order should fail")
    else:
        print(f"  negative (execution_plus_code code-before-outcome): violation captured ✓")

    # Negative: execution_plus_code with outcome not passed must fail
    bad10 = dict(sample, review_target_kind="execution_plus_code",
                 execution_artifact_ref="fixtures/execution-results/valid-closure.json",
                 outcome_validator_status="failed",
                 stage_order=["outcome", "code"])
    v10 = validate_route_report(bad10)
    if not v10:
        errors.append("negative test FAIL: execution_plus_code outcome=failed should fail")
    else:
        print(f"  negative (execution_plus_code outcome=failed): violation captured ✓")

    # Positive: execution_plus_code fail-closed (decision=FAILED + blocked_by + not_run_blocked) must pass
    good_fail_closed = dict(
        sample,
        review_target_kind="execution_plus_code",
        decision="FAILED",
        execution_artifact_ref="fixtures/execution-results/valid-closure.json",
        outcome_validator_status="not_run_blocked",
        stage_order=["outcome", "code"],
        blocked_by="FW-H2A-3a",
        failure_code="NOT_IMPLEMENTED",
    )
    v_good_fc = validate_route_report(good_fail_closed)
    if v_good_fc:
        errors.append(
            f"positive test FAIL: execution_plus_code fail-closed should pass but got {v_good_fc}"
        )
    else:
        print(f"  positive (execution_plus_code fail-closed not_run_blocked): PASS ✓")

    # Negative: not_run_blocked on execution_plus_code without decision=FAILED+blocked_by must fail
    bad11 = dict(
        sample,
        review_target_kind="execution_plus_code",
        execution_artifact_ref="fixtures/execution-results/valid-closure.json",
        outcome_validator_status="not_run_blocked",
        stage_order=["outcome", "code"],
    )
    v11 = validate_route_report(bad11)
    if not v11:
        errors.append(
            "negative test FAIL: execution_plus_code not_run_blocked without fail-closed should produce violations"
        )
    else:
        print(f"  negative (execution_plus_code not_run_blocked no fail-closed): violation captured ✓")

    # Positive: execution_only_no_code fail-closed (not_run_blocked) must pass
    good_exec_only_fc = dict(
        sample,
        review_target_kind="execution_only_no_code",
        decision="FAILED",
        execution_artifact_ref="fixtures/execution-results/valid-closure.json",
        outcome_validator_status="not_run_blocked",
        failure_code="NOT_IMPLEMENTED",
    )
    v_good_eofc = validate_route_report(good_exec_only_fc)
    if v_good_eofc:
        errors.append(
            f"positive test FAIL: execution_only_no_code fail-closed should pass but got {v_good_eofc}"
        )
    else:
        print(f"  positive (execution_only_no_code fail-closed not_run_blocked): PASS ✓")

    # --- Plan 8 v4.1 Step 8 — per-kind required field cases ---

    # Positive: plan_only with plan_ref + plan_hash → PASS (sample already has these)
    good_plan = dict(sample)
    v_good_plan = validate_route_report(good_plan)
    if v_good_plan:
        errors.append(
            f"positive test FAIL: plan_only with plan_ref+plan_hash should pass but got {v_good_plan}"
        )
    else:
        print(f"  positive (plan_only with plan_ref+plan_hash): PASS ✓")

    # Negative: plan_only without plan_hash → FAIL
    bad_plan = {k: v for k, v in sample.items() if k != "plan_hash"}
    v_bad_plan = validate_route_report(bad_plan)
    if not v_bad_plan:
        errors.append("negative test FAIL: plan_only missing plan_hash should produce violations")
    else:
        print(f"  negative (plan_only missing plan_hash): violation captured ✓")

    # Negative: plan_only with malformed plan_hash → FAIL
    bad_plan2 = dict(sample, plan_hash="not-a-sha256")
    v_bad_plan2 = validate_route_report(bad_plan2)
    if not v_bad_plan2:
        errors.append("negative test FAIL: plan_only malformed plan_hash should produce violations")
    else:
        print(f"  negative (plan_only malformed plan_hash): violation captured ✓")

    # Positive: code_only with diff fields + patch_generation_method → PASS
    good_code = dict(sample)
    for k in ("plan_ref", "plan_hash"):
        good_code.pop(k, None)
    good_code.update(
        review_target_kind="code_only",
        diff_source="git diff HEAD~1",
        diff_hash=_SHA_ZERO,
        patch_generation_method="git_diff",
    )
    v_good_code = validate_route_report(good_code)
    if v_good_code:
        errors.append(
            f"positive test FAIL: code_only with diff fields should pass but got {v_good_code}"
        )
    else:
        print(f"  positive (code_only with diff_hash+patch_method): PASS ✓")

    # Negative: code_only without diff_hash → FAIL
    bad_code = {k: v for k, v in good_code.items() if k != "diff_hash"}
    v_bad_code = validate_route_report(bad_code)
    if not v_bad_code:
        errors.append("negative test FAIL: code_only missing diff_hash should produce violations")
    else:
        print(f"  negative (code_only missing diff_hash): violation captured ✓")

    # Negative: code_only with bad patch_generation_method enum → FAIL
    bad_code2 = dict(good_code, patch_generation_method="cherry_pick")
    v_bad_code2 = validate_route_report(bad_code2)
    if not v_bad_code2:
        errors.append("negative test FAIL: code_only bad patch_generation_method should produce violations")
    else:
        print(f"  negative (code_only invalid patch_generation_method): violation captured ✓")

    # Negative: no_artifact without failure_code → FAIL
    bad_no = {k: v for k, v in sample.items() if k not in ("plan_ref", "plan_hash")}
    bad_no.update(
        review_target_kind="no_artifact",
        decision="REVIEW_TARGET_MISSING",
        findings=[{"reviewer": "router", "severity": "info", "description": "no artifact"}],
    )
    v_bad_no = validate_route_report(bad_no)
    if not v_bad_no:
        errors.append("negative test FAIL: no_artifact missing failure_code should produce violations")
    else:
        print(f"  negative (no_artifact missing failure_code): violation captured ✓")

    # Negative: no_artifact with empty findings → FAIL
    bad_no2 = dict(bad_no, failure_code="NO_ARTIFACT_DETECTED", findings=[])
    v_bad_no2 = validate_route_report(bad_no2)
    if not v_bad_no2:
        errors.append("negative test FAIL: no_artifact empty findings should produce violations")
    else:
        print(f"  negative (no_artifact empty findings): violation captured ✓")

    # Positive: no_artifact with failure_code + finding → PASS
    good_no = dict(bad_no, failure_code="NO_ARTIFACT_DETECTED")
    v_good_no = validate_route_report(good_no)
    if v_good_no:
        errors.append(
            f"positive test FAIL: no_artifact with failure_code+finding should pass but got {v_good_no}"
        )
    else:
        print(f"  positive (no_artifact with failure_code+finding): PASS ✓")

    # Positive: ambiguous_mixed_artifacts with all required + decision REQUIRES_CHANGES → PASS
    good_ambig = {k: v for k, v in sample.items() if k not in ("plan_ref", "plan_hash")}
    good_ambig.update(
        review_target_kind="ambiguous_mixed_artifacts",
        decision="REQUIRES_CHANGES",
        detected_artifact_set={"has_plan": True, "has_execution": False, "has_code": True},
        failure_code="AMBIGUOUS_MIXED_ARTIFACTS",
        findings=[{"reviewer": "router", "severity": "info", "description": "plan + code without bundle"}],
    )
    v_good_ambig = validate_route_report(good_ambig)
    if v_good_ambig:
        errors.append(
            f"positive test FAIL: ambiguous valid-shape REQUIRES_CHANGES should pass but got {v_good_ambig}"
        )
    else:
        print(f"  positive (ambiguous with required + REQUIRES_CHANGES): PASS ✓")

    # Negative: ambiguous_mixed_artifacts with decision=APPROVED → FAIL
    bad_ambig = dict(good_ambig, decision="APPROVED")
    v_bad_ambig = validate_route_report(bad_ambig)
    if not v_bad_ambig:
        errors.append("negative test FAIL: ambiguous APPROVED should produce violations")
    else:
        print(f"  negative (ambiguous decision=APPROVED): violation captured ✓")

    # Negative: ambiguous_mixed_artifacts mode=live with raw_result_path → FAIL
    bad_ambig2 = dict(good_ambig, mode="live", raw_result_path="/tmp/raw.json", raw_result_hash=_SHA_ZERO)
    v_bad_ambig2 = validate_route_report(bad_ambig2)
    if not v_bad_ambig2:
        errors.append("negative test FAIL: ambiguous live with raw_result_path should produce violations")
    else:
        print(f"  negative (ambiguous live with raw_result_path): violation captured ✓")

    # Negative: ambiguous_mixed_artifacts missing detected_artifact_set → FAIL
    bad_ambig3 = {k: v for k, v in good_ambig.items() if k != "detected_artifact_set"}
    v_bad_ambig3 = validate_route_report(bad_ambig3)
    if not v_bad_ambig3:
        errors.append("negative test FAIL: ambiguous missing detected_artifact_set should produce violations")
    else:
        print(f"  negative (ambiguous missing detected_artifact_set): violation captured ✓")

    # Negative: detect_only with decision=APPROVED → FAIL
    bad_detect = dict(sample, mode="detect_only")
    v_bad_detect = validate_route_report(bad_detect)
    if not v_bad_detect:
        errors.append("negative test FAIL: detect_only + APPROVED should produce violations")
    else:
        print(f"  negative (detect_only + APPROVED): violation captured ✓")

    # Negative: live + no_artifact + raw_result_path set → FAIL
    bad_live_no = dict(
        good_no,
        mode="live",
        raw_result_path="/tmp/raw.json",
        raw_result_hash=_SHA_ZERO,
    )
    v_bad_live_no = validate_route_report(bad_live_no)
    if not v_bad_live_no:
        errors.append("negative test FAIL: live + no_artifact + raw_result_path should produce violations")
    else:
        print(f"  negative (live no_artifact with raw_result_path): violation captured ✓")

    # --- Plan GD-L1L3 SC-8 — code_only live Codex code_diff sidecar self-test ---
    _co_dir = tempfile.mkdtemp(prefix="gd-codeonly-st-")
    try:
        _coP = Path(_co_dir)

        def _wf(name, content):
            p = _coP / name
            p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
            return str(p), hashlib.sha256(p.read_bytes()).hexdigest()

        _raw_path, _raw_hash = _wf("codex-raw.md", "# Code Diff Review Result (v2)\n\nVERDICT: APPROVED\n")
        _mapped_body = json.dumps({
            "review_kind": "code_diff", "target_role": "code_diff",
            "template_kind": "gd-code-diff-review", "gd_review_decision": "APPROVED",
        })
        _mapped_path, _mapped_hash = _wf("codex-mapped.json", _mapped_body)
        _patch_path, _patch_hash = _wf("diff.patch", "diff --git a/x b/x\n")
        _child_path, _child_hash = _wf("child.json", '{"gd_review_decision":"APPROVED"}')
        _merge_path, _merge_hash = _wf("merge.json", '{"merged":"APPROVED"}')
        _ledger = {
            "schema_version": "1.0", "stage": "review_execution_code",
            "parent_run_id": "run-co-001", "batch_id": "batch-co-001",
            "recorded_at": "2026-01-01T00:00:00Z",
            "child_agent_count": 1, "max_parallel": 2,
            "child_jobs": [{"job_id": "job-1", "result_path": _child_path,
                            "result_hash": _child_hash, "status": "completed"}],
            "main_agent_merge": {"merge_report_path": _merge_path,
                                 "merge_report_hash": _merge_hash,
                                 "final_decision": "APPROVED", "blocking_buckets": []},
        }
        _ledger_path, _ledger_hash = _wf("ledger.json", json.dumps(_ledger))

        def _co_report(**over):
            base = {k: v for k, v in sample.items() if k not in ("plan_ref", "plan_hash")}
            base.update(
                mode="live", review_target_kind="code_only", decision="APPROVED",
                diff_source="git diff HEAD~1", diff_hash=_patch_hash,
                patch_generation_method="git_diff",
                raw_result_path=_patch_path, raw_result_hash=_patch_hash,
                codex_raw_result_path=_raw_path, codex_raw_result_hash=_raw_hash,
                codex_mapped_result_path=_mapped_path, codex_mapped_result_hash=_mapped_hash,
                codex_review_status="completed", codex_review_kind="code_diff",
                child_review_ledger_path=_ledger_path, child_review_ledger_hash=_ledger_hash,
            )
            base.update(over)
            return base

        def _has(vlist, needle):
            return any(needle in x for x in vlist)

        # Positive: complete sidecar → PASS
        _v = validate_route_report(_co_report())
        if _v:
            errors.append(f"positive FAIL code_only sidecar approved: {_v}")
        else:
            print("  positive (code_only sidecar approved): PASS ✓")

        # missing codex raw
        _v = validate_route_report(_co_report(codex_raw_result_path=None, codex_raw_result_hash=None))
        if _has(_v, "codex_raw_result_path") and _has(_v, "required"):
            print("  negative (missing codex raw): PASS ✓")
        else:
            errors.append(f"FAIL missing codex raw: {_v}")

        # missing codex mapped
        _v = validate_route_report(_co_report(codex_mapped_result_path=None, codex_mapped_result_hash=None))
        if _has(_v, "codex_mapped_result_path") and _has(_v, "required"):
            print("  negative (missing codex mapped): PASS ✓")
        else:
            errors.append(f"FAIL missing codex mapped: {_v}")

        # mapped path equals raw (diff artifact)
        _v = validate_route_report(_co_report(codex_mapped_result_path=_patch_path, codex_mapped_result_hash=_patch_hash))
        if _has(_v, "codex_mapped_result_path' must NOT equal 'raw_result_path'"):
            print("  negative (mapped path equals raw): PASS ✓")
        else:
            errors.append(f"FAIL mapped path equals raw: {_v}")

        # mapped path is patch
        _mp_path, _mp_hash = _wf("mapped-as-patch.patch", "fake patch\n")
        _v = validate_route_report(_co_report(codex_mapped_result_path=_mp_path, codex_mapped_result_hash=_mp_hash))
        if _has(_v, "must be the mapped JSON") and _has(_v, ".patch"):
            print("  negative (mapped path is patch): PASS ✓")
        else:
            errors.append(f"FAIL mapped path is patch: {_v}")

        # mapped review_kind mismatch
        _mb_path, _mb_hash = _wf("mapped-wrong-kind.json", json.dumps({
            "review_kind": "plan", "target_role": "code_diff", "template_kind": "gd-code-diff-review"}))
        _v = validate_route_report(_co_report(codex_mapped_result_path=_mb_path, codex_mapped_result_hash=_mb_hash))
        if _has(_v, "mapped JSON review_kind must be 'code_diff'"):
            print("  negative (mapped review_kind mismatch): PASS ✓")
        else:
            errors.append(f"FAIL mapped review_kind mismatch: {_v}")

        # wrong codex kind
        _v = validate_route_report(_co_report(codex_review_kind="plan"))
        if _has(_v, "codex_review_kind must be 'code_diff'"):
            print("  negative (wrong codex kind): PASS ✓")
        else:
            errors.append(f"FAIL wrong codex kind: {_v}")

        # invalid child ledger (missing batch_id)
        _bad_ledger = {k: v for k, v in _ledger.items() if k != "batch_id"}
        _bl_path, _bl_hash = _wf("ledger-nobatch.json", json.dumps(_bad_ledger))
        _v = validate_route_report(_co_report(child_review_ledger_path=_bl_path, child_review_ledger_hash=_bl_hash))
        if _has(_v, "stage-dispatch-ledger"):
            print("  negative (invalid child ledger): PASS ✓")
        else:
            errors.append(f"FAIL invalid child ledger: {_v}")

        # hash mismatch (codex_raw_result_hash wrong)
        _v = validate_route_report(_co_report(codex_raw_result_hash="a" * 64))
        if _has(_v, "does not match actual file hash"):
            print("  negative (hash mismatch): PASS ✓")
        else:
            errors.append(f"FAIL hash mismatch: {_v}")

        # LOCAL_STATIC_ONLY rejected
        _v = validate_route_report(_co_report(failure_code="LOCAL_STATIC_ONLY"))
        if _has(_v, "LOCAL_STATIC_ONLY"):
            print("  negative (LOCAL_STATIC_ONLY rejected): PASS ✓")
        else:
            errors.append(f"FAIL LOCAL_STATIC_ONLY rejected: {_v}")

        # mapped decision mismatch (route APPROVED but mapped verdict REQUIRES_CHANGES)
        _rc_mapped, _rc_mh = _wf("mapped-rc.json", json.dumps({
            "review_kind": "code_diff", "target_role": "code_diff",
            "template_kind": "gd-code-diff-review", "gd_review_decision": "REQUIRES_CHANGES"}))
        _v = validate_route_report(_co_report(
            codex_mapped_result_path=_rc_mapped, codex_mapped_result_hash=_rc_mh))
        if _has(_v, "verdict must be 'APPROVED'"):
            print("  negative (mapped decision mismatch): PASS ✓")
        else:
            errors.append(f"FAIL mapped decision mismatch: {_v}")

        # child ledger result_hash mismatch (forged internal hash)
        _forged_ledger, _forged_lh = _wf("ledger-forged.json", json.dumps({
            "schema_version": "1.0", "stage": "review_execution_code",
            "parent_run_id": "run-co-001", "batch_id": "batch-co-001",
            "recorded_at": "2026-01-01T00:00:00Z",
            "child_agent_count": 1, "max_parallel": 2,
            "child_jobs": [{"job_id": "j", "result_path": _child_path,
                            "result_hash": "a" * 64, "status": "completed"}],
            "main_agent_merge": {"merge_report_path": _merge_path,
                                 "merge_report_hash": _merge_hash,
                                 "final_decision": "APPROVED", "blocking_buckets": []}}))
        _v = validate_route_report(_co_report(
            child_review_ledger_path=_forged_ledger, child_review_ledger_hash=_forged_lh))
        if _has(_v, "ledger child result_hash") and _has(_v, "does not match"):
            print("  negative (child ledger result_hash mismatch): PASS ✓")
        else:
            errors.append(f"FAIL child ledger result_hash mismatch: {_v}")

        # merge final_decision mismatch (ledger says REQUIRES_CHANGES but route APPROVED)
        _mfd_ledger, _mfd_lh = _wf("ledger-mfd.json", json.dumps({
            "schema_version": "1.0", "stage": "review_execution_code",
            "parent_run_id": "run-co-001", "batch_id": "batch-co-001",
            "recorded_at": "2026-01-01T00:00:00Z",
            "child_agent_count": 1, "max_parallel": 2,
            "child_jobs": [{"job_id": "j", "result_path": _child_path,
                            "result_hash": _child_hash, "status": "completed"}],
            "main_agent_merge": {"merge_report_path": _merge_path,
                                 "merge_report_hash": _merge_hash,
                                 "final_decision": "REQUIRES_CHANGES", "blocking_buckets": ["x"]}}))
        _v = validate_route_report(_co_report(
            child_review_ledger_path=_mfd_ledger, child_review_ledger_hash=_mfd_lh))
        if _has(_v, "final_decision must be 'APPROVED'"):
            print("  negative (merge final decision mismatch): PASS ✓")
        else:
            errors.append(f"FAIL merge final decision mismatch: {_v}")

        # merge_report_hash mismatch (merge file real, but hash forged)
        _mrhash_ledger, _mrhash_lh = _wf("ledger-mrhash.json", json.dumps({
            "schema_version": "1.0", "stage": "review_execution_code",
            "parent_run_id": "run-co-001", "batch_id": "batch-co-001",
            "recorded_at": "2026-01-01T00:00:00Z",
            "child_agent_count": 1, "max_parallel": 2,
            "child_jobs": [{"job_id": "j", "result_path": _child_path,
                            "result_hash": _child_hash, "status": "completed"}],
            "main_agent_merge": {"merge_report_path": _merge_path,
                                 "merge_report_hash": "b" * 64,
                                 "final_decision": "APPROVED", "blocking_buckets": []}}))
        _v = validate_route_report(_co_report(
            child_review_ledger_path=_mrhash_ledger, child_review_ledger_hash=_mrhash_lh))
        if _has(_v, "merge_report_hash") and _has(_v, "does not match"):
            print("  negative (merge_report_hash mismatch): PASS ✓")
        else:
            errors.append(f"FAIL merge_report_hash mismatch: {_v}")
    finally:
        shutil.rmtree(_co_dir, ignore_errors=True)

    if errors:
        print("SELF_TEST FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("SELF_TEST: PASS")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("route_report", nargs="?", help="Path to route_report.json")
    p.add_argument("--self-test", action="store_true", help="Run singleton + schema self-test")
    p.add_argument("--json-out", help="Optional path to write violations as JSON")
    args = p.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.route_report:
        p.print_help()
        return 2

    rc, violations = validate_file(Path(args.route_report))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"violations": violations, "exit_code": rc}, indent=2))

    if rc == 2:
        for v in violations:
            print(f"ERROR: {v}", file=sys.stderr)
        return 2
    if violations:
        print(f"ROUTE_REPORT_INVALID: {len(violations)} violations", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(f"OK: route report schema valid ({args.route_report})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
