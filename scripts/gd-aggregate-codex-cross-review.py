#!/usr/bin/env python3
"""
gd-aggregate-codex-cross-review.py

Aggregates Codex cross-review results from a manifest-driven batch into a v2 aggregate JSON.

Consumed by:
  - /gd review 全链路 cross-review 聚合 (commands/gd.md L508)
  - gd-validate-parent-close-gate.py --aggregate-json (parent close gate signoff)

Input:  manifest JSON (schema/gd-codex-cross-review-manifest.schema.json)
Output: aggregate JSON (schema/gd-codex-cross-review-aggregate.schema.json)

Usage:
    python3 gd-aggregate-codex-cross-review.py --manifest <manifest.json> --out <aggregate.json>
    python3 gd-aggregate-codex-cross-review.py --manifest <manifest.json> --out <aggregate.json> --contract-sources commands/gd.md:prompts/gd-review-standard.md:templates/gd-plan-review-template.md:templates/gd-plan-review-loop-report-template.md

Exit codes:
    0 — aggregate written successfully (closure_eligible may be true or false)
    1 — aggregate written but closure_ineligible
    2 — input error (manifest missing/invalid, job files missing)
    3 — output error (cannot write aggregate)
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Return SHA-256 hex digest of file content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    """Return SHA-256 hex digest of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_review_contract_hash(contract_sources: list[str]) -> str:
    """Compute combined SHA-256 of all review contract source files."""
    combined = ""
    for src in contract_sources:
        p = Path(src)
        if p.exists():
            combined += sha256_file(p) + "\n"
        else:
            combined += f"MISSING:{src}\n"
    return sha256_text(combined)


def detect_stale_contract(contract_hash: str, contract_sources: list[str]) -> bool:
    """Check if the current contract sources differ from contract_hash."""
    current = compute_review_contract_hash(contract_sources)
    return current != contract_hash


def parse_raw_result(raw_path: Path) -> dict:
    """Parse a Codex raw .result file.

    Returns:
        dict with keys: gd_review_decision, findings_count, parse_status, ambiguous
    """
    if not raw_path or not raw_path.exists():
        return {
            "gd_review_decision": "none",
            "findings_count": 0,
            "parse_status": "file_missing",
            "ambiguous": False,
        }

    text = raw_path.read_text(encoding="utf-8", errors="replace")

    # Detect ambiguous: multiple JSON blocks
    json_blocks = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                json_blocks.append(text[start : i + 1])
                start = -1

    ambiguous = len(json_blocks) > 1

    # Detect bare VERDICT (not GD_REVIEW_DECISION)
    has_bare_verdict = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("VERDICT:") and not stripped.startswith("GD_REVIEW_DECISION:"):
            has_bare_verdict = True
            break

    # Extract GD_REVIEW_DECISION
    decision = "none"
    findings_count = 0
    for line in text.splitlines():
        if line.strip().startswith("GD_REVIEW_DECISION:"):
            val = line.split(":", 1)[1].strip()
            if val in ("APPROVED", "REQUIRES_CHANGES", "FAILED"):
                decision = val
        if line.strip().startswith("findings_count:") or line.strip().startswith("total_findings:"):
            try:
                findings_count = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    # Try JSON parse for richer extraction
    for block in json_blocks:
        try:
            data = json.loads(block)
            if "gd_review_decision" in data:
                decision = data["gd_review_decision"]
            if "findings" in data and isinstance(data["findings"], list):
                findings_count = len(data["findings"])
            break
        except json.JSONDecodeError:
            continue

    parse_status = "ok"
    if ambiguous:
        parse_status = "ambiguous_json_blocks"
    if has_bare_verdict:
        parse_status = "bare_verdict_detected" if parse_status == "ok" else f"{parse_status}+bare_verdict"

    return {
        "gd_review_decision": decision,
        "findings_count": findings_count,
        "parse_status": parse_status,
        "ambiguous": ambiguous,
    }


def build_aggregate_job(job: dict, gd_root: Path) -> dict:
    """Build a single aggregate_job entry from a manifest job."""
    entry = {
        "queue_job_id": job["queue_job_id"],
        "target_role": job["target_role"],
        "primary_target": job.get("primary_target", ""),
        "review_kind": job.get("review_kind", "plan"),
        "transport_status": "transport_failed",
        "raw_result_path": None,
        "raw_result_hash": "",
        "mapped_result_path": None,
        "mapped_result_hash": "",
        "codex_review_status": "transport_failed",
        "codex_review_kind": job.get("review_kind", "none"),
        "gd_review_decision": "none",
        "codex_requires_changes": False,
        "missing_primary_target": False,
    }

    # Check primary target existence
    primary = job.get("primary_target", "")
    if primary and not Path(primary).exists():
        entry["missing_primary_target"] = True

    # Process raw result
    raw_path_str = job.get("codex_raw_result_path")
    if raw_path_str:
        raw_path = Path(raw_path_str)
        if raw_path.exists():
            raw_hash = sha256_file(raw_path)
            parsed = parse_raw_result(raw_path)

            entry["transport_status"] = "transport_ok"
            entry["raw_result_path"] = str(raw_path)
            entry["raw_result_hash"] = raw_hash
            entry["codex_review_status"] = "completed"
            entry["gd_review_decision"] = parsed["gd_review_decision"]
            entry["codex_requires_changes"] = parsed["gd_review_decision"] in (
                "REQUIRES_CHANGES",
                "FAILED",
            )

    return entry


def build_aggregate(
    manifest: dict,
    manifest_path: Path,
    gd_root: Path,
    contract_sources: list[str] | None = None,
) -> dict:
    """Build the full aggregate JSON from a manifest."""
    now = datetime.now(timezone.utc).isoformat()
    manifest_hash = sha256_file(manifest_path)

    jobs = []
    for job in manifest.get("required_jobs", []):
        jobs.append(build_aggregate_job(job, gd_root))

    # Compute contract hash
    if contract_sources is None:
        contract_sources = [
            str(gd_root / "commands" / "gd.md"),
            str(gd_root / "prompts" / "gd-review-standard.md"),
            str(gd_root / "templates" / "gd-plan-review-template.md"),
            str(gd_root / "templates" / "gd-plan-review-loop-report-template.md"),
        ]
    contract_hash = compute_review_contract_hash(contract_sources)
    stale = detect_stale_contract(contract_hash, contract_sources)

    # Detect ambiguous raw results
    ambiguous = False
    for job_entry in jobs:
        raw_path = job_entry.get("raw_result_path")
        if raw_path:
            parsed = parse_raw_result(Path(raw_path))
            if parsed["ambiguous"]:
                ambiguous = True
                break

    # Build summary
    total = len(jobs)
    transport_ok = sum(1 for j in jobs if j["transport_status"] == "transport_ok")
    transport_failed = sum(1 for j in jobs if j["transport_status"] == "transport_failed")
    wrapper_fail = sum(1 for j in jobs if j["transport_status"] == "wrapper_schema_fail")
    approved = sum(1 for j in jobs if j["gd_review_decision"] == "APPROVED")
    requires_changes = sum(1 for j in jobs if j["gd_review_decision"] == "REQUIRES_CHANGES")
    failed = sum(1 for j in jobs if j["gd_review_decision"] == "FAILED")
    missing_target = sum(1 for j in jobs if j.get("missing_primary_target"))
    codex_rc = sum(1 for j in jobs if j.get("codex_requires_changes"))

    blockers = []
    if transport_failed > 0:
        blockers.append(f"transport_failed: {transport_failed} job(s)")
    if wrapper_fail > 0:
        blockers.append(f"wrapper_schema_fail: {wrapper_fail} job(s)")
    if missing_target > 0:
        blockers.append(f"missing_primary_target: {missing_target} job(s)")
    if codex_rc > 0:
        blockers.append(f"codex_requires_changes: {codex_rc} job(s)")
    if stale:
        blockers.append("stale_review_contract")
    if ambiguous:
        blockers.append("ambiguous_raw_result")

    closure_eligible = len(blockers) == 0

    return {
        "aggregate_version": "2.0",
        "target_set_id": manifest["target_set_id"],
        "generated_at": now,
        "manifest_path": str(manifest_path),
        "manifest_hash": manifest_hash,
        "review_contract_hash": contract_hash,
        "stale_review_contract": stale,
        "ambiguous_raw_result": ambiguous,
        "jobs": jobs,
        "aggregate_summary": {
            "total_jobs": total,
            "transport_ok": transport_ok,
            "transport_failed": transport_failed,
            "wrapper_schema_fail": wrapper_fail,
            "approved": approved,
            "requires_changes": requires_changes,
            "failed": failed,
            "missing_primary_target_count": missing_target,
            "codex_requires_changes_count": codex_rc,
            "closure_eligible": closure_eligible,
            "closure_blockers": blockers,
        },
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Aggregate Codex cross-review results into v2 aggregate JSON"
    )
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--out", required=True, help="Output path for aggregate JSON")
    parser.add_argument(
        "--contract-sources",
        default=None,
        help="Colon-separated list of review contract source files for hash computation",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(2)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid manifest JSON: {e}", file=sys.stderr)
        sys.exit(2)

    gd_root = Path(os.environ.get("GD_PROJECT_ROOT", Path(__file__).resolve().parent.parent))

    contract_sources = None
    if args.contract_sources:
        contract_sources = args.contract_sources.split(":")

    aggregate = build_aggregate(manifest, manifest_path, gd_root, contract_sources)

    out_path = Path(args.out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"ERROR: cannot write aggregate: {e}", file=sys.stderr)
        sys.exit(3)

    print(f"Aggregate written: {out_path}")
    print(f"  jobs: {aggregate['aggregate_summary']['total_jobs']}")
    print(f"  transport_ok: {aggregate['aggregate_summary']['transport_ok']}")
    print(f"  transport_failed: {aggregate['aggregate_summary']['transport_failed']}")
    print(f"  closure_eligible: {aggregate['aggregate_summary']['closure_eligible']}")

    if aggregate["aggregate_summary"]["closure_blockers"]:
        print(f"  blockers: {aggregate['aggregate_summary']['closure_blockers']}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()