"""
gd_review_contract.py — Plan 8 v4.1 Review Contract SSOT (Single Source of Truth)

This module is the only authoritative source for all /gd review enums and mappings.
All consumers (detector, router, validators, parser, bridge) MUST import from here.

Local enum definitions in any consumer script are forbidden and will be flagged
by gd-validate-review-contract-drift.py.

CLI:
  python3 scripts/gd_review_contract.py --dump-json   # for docs/fixtures only;
                                                       # not the authoritative source.
"""
from __future__ import annotations

# ----- Enums (frozensets so consumers cannot mutate) -----

REVIEW_KIND_ENUM = frozenset({"plan", "execution_outcome", "code_diff", "combined"})

TEMPLATE_KIND_ENUM = frozenset({
    "gd-plan-review",
    "gd-execution-outcome-review",
    "gd-code-diff-review",
    "gd-combined-review",
})

REVIEW_TARGET_KIND_ENUM = frozenset({
    "plan_only",
    "execution_only_no_code",
    "code_only",
    "execution_plus_code",
    "no_artifact",
    "ambiguous_mixed_artifacts",
})

MODE_ENUM = frozenset({"fixture", "detect_only", "live_dry_run", "live"})

DECISION_ENUM = frozenset({"APPROVED", "REQUIRES_CHANGES", "FAILED", "REVIEW_TARGET_MISSING"})

# Legacy v1 enums for compatibility mode (--compat-v1)
# revision=20: execution_outcome and combined added so that bridge parse-transport
# --compat-v1 can parse real Codex execution review raw that still uses
# v1-style header ("# Code Review Result") instead of the v2 header.
REVIEW_KIND_V1_ENUM = frozenset({"plan", "code", "execution_outcome", "combined"})
TEMPLATE_KIND_V1_ENUM = frozenset({
    "gd-plan-review", "gd-execution-review",
    # revision=20: added for compat-v1 execution kinds
    "gd-execution-outcome-review", "gd-combined-review",
})

# ----- Mappings -----

# review_target_kind → review_kind (1:1 except no_artifact/ambiguous which fail-closed)
TARGET_KIND_TO_REVIEW_KIND = {
    "plan_only": "plan",
    "execution_only_no_code": "execution_outcome",
    "code_only": "code_diff",
    "execution_plus_code": "combined",
    # no_artifact / ambiguous_mixed_artifacts: no review_kind (fail-closed)
}

# review_kind → template_kind (1:1)
REVIEW_KIND_TO_TEMPLATE_KIND = {
    "plan": "gd-plan-review",
    "execution_outcome": "gd-execution-outcome-review",
    "code_diff": "gd-code-diff-review",
    "combined": "gd-combined-review",
}

# mode → whether Codex live transport is allowed
MODE_TO_CODEX_ALLOWED = {
    "fixture": False,
    "detect_only": False,
    "live_dry_run": False,
    "live": True,
}

# review_target_kind → set of legal decisions
TARGET_KIND_TO_LEGAL_DECISIONS = {
    "plan_only": frozenset({"APPROVED", "REQUIRES_CHANGES", "FAILED"}),
    "execution_only_no_code": frozenset({"APPROVED", "REQUIRES_CHANGES", "FAILED"}),
    "code_only": frozenset({"APPROVED", "REQUIRES_CHANGES", "FAILED"}),
    "execution_plus_code": frozenset({"APPROVED", "REQUIRES_CHANGES", "FAILED"}),
    "no_artifact": frozenset({"REVIEW_TARGET_MISSING", "FAILED"}),
    "ambiguous_mixed_artifacts": frozenset({"REVIEW_TARGET_MISSING", "FAILED", "REQUIRES_CHANGES"}),
    # ambiguous explicitly NOT permitted to return APPROVED
}


# review_kind → target_role (v2 schema cross-field allOf; 1:1)
TARGET_ROLE_ENUM = frozenset({"plan_artifact", "execution_artifact", "code_diff", "combined_bundle"})

NEXT_ACTION_ENUM = frozenset({
    "rerun_codex",
    "mark_approved",
    "block_on_p1",
    "require_human_arbitration",
    "no_op",
})

REVIEW_KIND_TO_TARGET_ROLE = {
    "plan": "plan_artifact",
    "execution_outcome": "execution_artifact",
    "code_diff": "code_diff",
    "combined": "combined_bundle",
}

def codex_review_status_from_evidence(
    evidence_present: bool,
    codex_verdict: str,
    run_status: str | None,
) -> str:
    """Map a codex evidence triple → route_report.codex_review_status (SSOT).

    Shared by the plan path (gd-review-merge-and-fix-loop.py convergence +
    consumption) and the execution/combined paths (gd-review-router.py Path A/B)
    so both derive codex_review_status identically — prevents the P1 mislabel
    where a readable mapped file carrying a FAILED verdict or a degraded run
    was silently reported as 'completed'.

    transport_ok (file readable) does NOT mean the codex review succeeded.
    fail-closed matrix:
      ① no evidence file          → transport_failed
      ② file present, FAILED       → wrapper_schema_fail
         verdict, missing/unknown   (codex produced an unusable result)
         run state, or degraded/
         failed_to_run/failed run
      ③ file + APPROVED + clean    → completed
      ④ file + REQUIRES_CHANGES    → requires_changes
         + clean run
    """
    if not evidence_present:
        return "transport_failed"
    if run_status == "completed_with_constraint":
        return "requires_changes"
    if run_status != "completed":
        return "wrapper_schema_fail"
    if codex_verdict == "APPROVED":
        return "completed"
    if codex_verdict == "REQUIRES_CHANGES":
        return "requires_changes"
    # FAILED / unknown verdict on a readable file = unusable codex result.
    return "wrapper_schema_fail"


def dump_json() -> str:
    """Return contract as JSON string for docs/fixture generation only."""
    import json
    return json.dumps({
        "review_kind_enum": sorted(REVIEW_KIND_ENUM),
        "template_kind_enum": sorted(TEMPLATE_KIND_ENUM),
        "review_target_kind_enum": sorted(REVIEW_TARGET_KIND_ENUM),
        "mode_enum": sorted(MODE_ENUM),
        "decision_enum": sorted(DECISION_ENUM),
        "review_kind_v1_enum": sorted(REVIEW_KIND_V1_ENUM),
        "template_kind_v1_enum": sorted(TEMPLATE_KIND_V1_ENUM),
        "target_kind_to_review_kind": TARGET_KIND_TO_REVIEW_KIND,
        "review_kind_to_template_kind": REVIEW_KIND_TO_TEMPLATE_KIND,
        "mode_to_codex_allowed": MODE_TO_CODEX_ALLOWED,
        "target_kind_to_legal_decisions": {
            k: sorted(v) for k, v in TARGET_KIND_TO_LEGAL_DECISIONS.items()
        },
    }, indent=2, ensure_ascii=False)


def main() -> int:
    import sys
    if "--dump-json" in sys.argv:
        print(dump_json())
        return 0
    print("gd_review_contract — SSOT module. Use --dump-json to inspect.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
