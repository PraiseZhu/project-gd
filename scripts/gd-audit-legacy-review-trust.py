#!/usr/bin/env python3
"""
gd-audit-legacy-review-trust.py

Audits historical GD review reports and classifies each into 3 trust tiers.

Tiers (per commands/gd.md L516):
  - trusted_codex_raw       — 有真实 Codex raw .result 文件，可验证
  - local_self_review_only  — 仅 Claude 本地 self-review，无 Codex 双审证据
  - legacy_untrusted        — 含 codex_transport_unavailable / W2 pending 等旧 marker
                              但无真实 raw 文件，是 pre-Plan-I-batch-1 误诊

Output: reports/review-trust/legacy-review-trust-audit.md
  — 不重写旧 review 文件，只在 parent close 中引用

Usage:
    python3 gd-audit-legacy-review-trust.py --scan-dir <reports-dir> [--out <output.md>]
    python3 gd-audit-legacy-review-trust.py --scan-dir <reports-dir> --json-out <output.json>

Exit codes:
    0 — audit completed (may include legacy_untrusted entries)
    1 — scan error (directory not found, unreadable files)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# Markers that indicate a "claimed Codex review" without real evidence
LEGACY_UNTRUSTED_MARKERS = [
    "codex_transport_unavailable",
    "W2 pending",
    "W2_pending",
    "codex bridge pending",
    "codex_bridge_pending",
    "Codex unavailable",
    "Codex unreachable",
    "transport not yet available",
]

# Markers that indicate local-only review
LOCAL_ONLY_MARKERS = [
    "local_self_review",
    "claude_only",
    "CAPABILITY_STATUS: local_only",
    "REVIEWER: claude",
    "reviewer: claude",
]

# Evidence of real Codex raw result
CODEX_RAW_EVIDENCE = [
    "codex_raw_result_path",
    "raw_result_path",
    "raw_result_hash",
    "REVIEWER: codex",
    "reviewer: codex",
    "codex_review_status: completed",
]


def extract_raw_result_path(line: str) -> str:
    """Extract a raw_result_path value from one report line.

    Handles two on-disk shapes seen in real reports:
      - text  :  codex_raw_result_path: /Users/.../result.md
      - JSON  :  "codex_raw_result_path": "/Users/.../result.md",

    The JSON form quotes both key and value and appends a trailing comma as an
    object-member separator. Splitting on the first ':' yields the key portion
    (possibly quoted); everything after the FIRST ':' that follows the key token
    is the value. We then peel surrounding quotes and any trailing comma so the
    path resolves cleanly (tolerating a trailing comma rather than failing).
    """
    # Split off the value: take everything after the first colon that separates
    # the key from the value. For JSON the key is '"..."' so the first ':' still
    # lands right after the closing key-quote.
    if ":" not in line:
        return ""
    value = line.split(":", 1)[1].strip().rstrip(",").strip()
    # Peel one layer of surrounding matched quotes (JSON string value).
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        value = value[1:-1]
    else:
        value = value.strip("\"'")
    return value.strip()


def classify_report(report_path: Path) -> dict:
    """Classify a single review report into a trust tier.

    Returns:
        dict with: path, tier, evidence, markers_found, has_raw_file
    """
    result = {
        "path": str(report_path),
        "tier": "legacy_untrusted",
        "evidence": [],
        "markers_found": [],
        "has_raw_file": False,
        "raw_file_path": None,
        "reason": "",
    }

    if not report_path.exists():
        result["tier"] = "legacy_untrusted"
        result["reason"] = "file_missing"
        return result

    try:
        text = report_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        result["reason"] = "unreadable"
        return result

    # Check for Codex raw evidence
    has_codex_evidence = False
    for marker in CODEX_RAW_EVIDENCE:
        if marker in text:
            has_codex_evidence = True
            result["evidence"].append(marker)

    # Check for raw result file references.
    # Tolerates both plain text form  (raw_result_path: /path/to/file)
    # and JSON form                   ("raw_result_path": "/path/to/file",)
    # — JSON keys/values are quoted and JSON object members carry a trailing comma,
    # which the naive ".strip('\"')" path-extraction failed to peel off, leaving a
    # path like '/path/file",' that never resolved → trusted reports misclassified.
    for line in text.splitlines():
        if "raw_result_path" in line or "codex_raw_result_path" in line:
            try:
                raw_path = extract_raw_result_path(line)
            except (IndexError, ValueError):
                raw_path = ""
            if raw_path:
                candidate = Path(raw_path)
                if candidate.exists():
                    result["has_raw_file"] = True
                    result["raw_file_path"] = str(candidate)

    # Check for legacy untrusted markers
    has_legacy_markers = False
    for marker in LEGACY_UNTRUSTED_MARKERS:
        if marker.lower() in text.lower():
            has_legacy_markers = True
            result["markers_found"].append(marker)

    # Check for local-only markers
    has_local_only = False
    for marker in LOCAL_ONLY_MARKERS:
        if marker in text:
            has_local_only = True
            result["markers_found"].append(marker)

    # Determine tier
    if has_codex_evidence and result["has_raw_file"]:
        result["tier"] = "trusted_codex_raw"
        result["reason"] = "has_codex_raw_evidence_and_raw_file"
    elif has_codex_evidence and not result["has_raw_file"]:
        # Claims Codex evidence but raw file not found — could be path issue
        result["tier"] = "local_self_review_only"
        result["reason"] = "codex_evidence_claimed_but_raw_file_missing"
    elif has_legacy_markers and not has_codex_evidence:
        result["tier"] = "legacy_untrusted"
        result["reason"] = "legacy_markers_without_codex_evidence"
    elif has_local_only and not has_codex_evidence:
        result["tier"] = "local_self_review_only"
        result["reason"] = "local_only_markers_no_codex_evidence"
    else:
        # No clear markers — default to legacy_untrusted if no codex evidence
        if has_codex_evidence:
            result["tier"] = "local_self_review_only"
            result["reason"] = "codex_evidence_present_but_raw_file_unverified"
        else:
            result["tier"] = "legacy_untrusted"
            result["reason"] = "no_codex_evidence_found"

    return result


def scan_directory(scan_dir: Path) -> list[dict]:
    """Recursively scan a directory for review reports and classify each."""
    results = []
    review_extensions = {".md", ".json", ".txt"}

    for root, dirs, files in os.walk(scan_dir):
        # Skip non-review directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "backup"]
        for fname in sorted(files):
            if not any(fname.endswith(ext) for ext in review_extensions):
                continue
            # Only scan files that look like review reports
            if not any(
                keyword in fname.lower()
                for keyword in ["review", "result", "report", "capsule", "verdict", "aggregate"]
            ):
                continue
            fpath = Path(root) / fname
            results.append(classify_report(fpath))

    return results


def render_markdown(results: list[dict], scan_dir: Path) -> str:
    """Render audit results as Markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tiers = {"trusted_codex_raw": [], "local_self_review_only": [], "legacy_untrusted": []}
    for r in results:
        tiers[r["tier"]].append(r)

    lines = [
        "# Legacy Review Trust Audit",
        "",
        f"**Generated**: {now}",
        f"**Scan directory**: `{scan_dir}`",
        f"**Total files scanned**: {len(results)}",
        "",
        "## Summary",
        "",
        f"| Tier | Count |",
        f"|------|-------|",
        f"| trusted_codex_raw | {len(tiers['trusted_codex_raw'])} |",
        f"| local_self_review_only | {len(tiers['local_self_review_only'])} |",
        f"| legacy_untrusted | {len(tiers['legacy_untrusted'])} |",
        "",
        "## Tier: trusted_codex_raw",
        "",
    ]

    if tiers["trusted_codex_raw"]:
        for r in tiers["trusted_codex_raw"]:
            lines.append(f"- `{r['path']}` — raw: `{r.get('raw_file_path', 'N/A')}`")
    else:
        lines.append("_(none)_")

    lines.extend([
        "",
        "## Tier: local_self_review_only",
        "",
    ])
    if tiers["local_self_review_only"]:
        for r in tiers["local_self_review_only"]:
            lines.append(f"- `{r['path']}` — {r['reason']}")
    else:
        lines.append("_(none)_")

    lines.extend([
        "",
        "## Tier: legacy_untrusted",
        "",
        "> **注意**：以下报告含 `codex_transport_unavailable` / `W2 pending` 等旧 marker 但**无**真实 raw 文件——是 pre-Plan-I-batch-1 误诊，**不**作为 Codex 双审证据。",
        "",
    ])
    if tiers["legacy_untrusted"]:
        for r in tiers["legacy_untrusted"]:
            markers = ", ".join(r["markers_found"]) if r["markers_found"] else "none"
            lines.append(f"- `{r['path']}` — markers: {markers} — {r['reason']}")
    else:
        lines.append("_(none)_")

    lines.extend([
        "",
        "---",
        "",
        "**不重写旧 review 文件**。本审计仅在 parent close 中引用。",
    ])

    return "\n".join(lines) + "\n"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Audit legacy GD review reports for trust tier classification"
    )
    parser.add_argument("--scan-dir", required=True, help="Directory to scan for review reports")
    parser.add_argument("--out", default=None, help="Output path for Markdown audit report")
    parser.add_argument("--json-out", default=None, help="Output path for JSON audit data")
    args = parser.parse_args()

    scan_dir = Path(args.scan_dir)
    if not scan_dir.exists() or not scan_dir.is_dir():
        print(f"ERROR: scan directory not found: {scan_dir}", file=sys.stderr)
        sys.exit(1)

    results = scan_directory(scan_dir)

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "scan_directory": str(scan_dir),
                "total_scanned": len(results),
                "tier_counts": {
                    "trusted_codex_raw": sum(1 for r in results if r["tier"] == "trusted_codex_raw"),
                    "local_self_review_only": sum(1 for r in results if r["tier"] == "local_self_review_only"),
                    "legacy_untrusted": sum(1 for r in results if r["tier"] == "legacy_untrusted"),
                },
                "results": results,
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"JSON audit written: {json_path}")

    out_path = Path(args.out) if args.out else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(results, scan_dir), encoding="utf-8")
        print(f"Markdown audit written: {out_path}")
    elif not args.json_out:
        # Default: write to reports/review-trust/
        default_out = Path("reports/review-trust/legacy-review-trust-audit.md")
        default_out.parent.mkdir(parents=True, exist_ok=True)
        default_out.write_text(render_markdown(results, scan_dir), encoding="utf-8")
        print(f"Markdown audit written: {default_out}")

    # Summary to stdout
    tiers = {"trusted_codex_raw": 0, "local_self_review_only": 0, "legacy_untrusted": 0}
    for r in results:
        tiers[r["tier"]] += 1
    print(f"Scanned: {len(results)} files")
    print(f"  trusted_codex_raw: {tiers['trusted_codex_raw']}")
    print(f"  local_self_review_only: {tiers['local_self_review_only']}")
    print(f"  legacy_untrusted: {tiers['legacy_untrusted']}")

    sys.exit(0)


if __name__ == "__main__":
    main()