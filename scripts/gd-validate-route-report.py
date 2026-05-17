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
import json
import re
import subprocess
import sys
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
        if not data.get("child_review_ledger_path"):
            violations.append(
                f"{rtk_str}/live/APPROVED: 'child_review_ledger_path' required — "
                "APPROVED closure requires a mandatory child code/execution review; "
                "missing ledger means the child review was never recorded "
                "(CLOSURE_INELIGIBLE: missing_child_review_ledger)"
            )

    # Step 5 — code_only LOCAL_STATIC_ONLY cannot claim APPROVED.
    # LOCAL_STATIC_ONLY is a placeholder status meaning skill_orchestrated review has
    # not completed; only a completed cross-review may produce APPROVED.
    if (mode_str == "live" and decision_str == "APPROVED" and rtk_str == "code_only"):
        if data.get("failure_code") == "LOCAL_STATIC_ONLY":
            violations.append(
                "code_only/live/APPROVED: failure_code='LOCAL_STATIC_ONLY' is incompatible "
                "with decision=APPROVED — LOCAL_STATIC_ONLY is a placeholder status "
                "indicating the skill_orchestrated review has not completed; "
                "re-run with completed cross-review before claiming APPROVED"
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
