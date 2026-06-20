#!/usr/bin/env python3
"""gd-validate-review2-plan-target.py — field-based plan preflight for /review2.

Validates that a plan file passed as --target to /review2 plan_review is a
genuine plan (not a capsule, not an old /rev-style file) and contains the
minimum required fields.

Exit codes:
  0  PLAN_TEMPLATE_STATUS: pass
  1  PLAN_TEMPLATE_STATUS: fail  (structural errors or anti-fill violations)
  2  usage error

Output (stdout):
  PLAN_TEMPLATE_STATUS: pass | fail
  PLAN_ERROR: <description>          (only on fail, one line per error)
  PLAN_ANTIFILL_FAIL: <description>  (anti-fill gate violation, independent signal)
  BRIDGE_INVOCATION_STATUS: not_started | allowed
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.sc_extraction import SC_ID_RE, extract_sc_ids  # noqa: E402
from lib.path_classification import is_review2_capsule_path  # noqa: E402

# Patterns required in a compliant plan (either template style)
_REVIEW_DOMAIN_RE = re.compile(r"REVIEW_DOMAIN[：:]", re.IGNORECASE)
_REVIEW_FOCUS_RE = re.compile(r"REVIEW_FOCUS[：:]", re.IGNORECASE)

# At least one of the four step-field keywords must appear
_WHERE_RE = re.compile(r"^\s*WHERE[：:]", re.MULTILINE)
_WHAT_RE = re.compile(r"^\s*WHAT[：:]", re.MULTILINE)
_WHY_RE = re.compile(r"^\s*WHY[：:]", re.MULTILINE)
_VERIFY_RE = re.compile(r"^\s*VERIFY[：:]", re.MULTILINE)

# Old /rev-style markers that must NOT appear
_REV_VERDICT_RE = re.compile(r"^REV_VERDICT[：:]", re.MULTILINE)
_BARE_VERDICT_RE = re.compile(r"^VERDICT[：:]", re.MULTILINE)
_REVIEW_STANDARD_RE = re.compile(r"^REVIEW_STANDARD[：:]", re.MULTILINE)

# ---------------------------------------------------------------------------
# SC definition / anti-fill gate patterns
# ---------------------------------------------------------------------------

# A real SC definition must start a list item or heading. Plain prose such as
# "Plan Without SC-IDs" must not satisfy the structural SC gate.
_SC_DEFINITION_RE = re.compile(
    r"^\s*(?:"
    r"(?:[-*]\s+\[[ xX]\]\s*)"      # checklist item: - [ ] SC-1
    r"|(?:[-*]\s+)"                  # plain bullet: - SC-1
    r"|(?:#{1,6}\s+)"                # heading: ### SC-1
    r")(" + SC_ID_RE.pattern + r")\b",
    re.MULTILINE,
)

# Matches a per-SC verify line:
#   verify (method: command|path|assertion|test): <non-empty content>
# or indented/lowercase bare:  verify: <non-empty content>
#
# Intentionally does NOT match the plan step-level "VERIFY:" field (all-caps,
# line-leading with no parenthetical) — that is a structural field, not a
# per-SC executable verify entry.  We require at least one of:
#   (a) verify followed immediately by a parenthetical  → verify (method: ...): ...
#   (b) verify preceded by whitespace (indented)         → "  verify: ..."
#   (c) lowercase-starting "verify" with colon + content
_SC_VERIFY_LINE_RE = re.compile(
    r"(?:"
    r"verify\s*\([^)]*\)\s*[：:]\s*\S"   # (a) verify (method: ...): <content>
    r"|"
    r"[ \t]+verify\s*(?:\([^)]*\))?\s*[：:]\s*\S"  # (b) indented verify: <content>
    r")",
    re.IGNORECASE,
)

# Matches an expect line (captures the value portion after the colon).
_SC_EXPECT_LINE_RE = re.compile(
    r"expect\s*[：:]\s*(.+)",
    re.IGNORECASE,
)

# Pure generic-word blacklist — values that are ONLY one of these words
# (after stripping punctuation/whitespace) are considered empty/generic.
_GENERIC_WORDS = frozenset([
    "通过", "正确", "完成", "works", "pass", "ok", "成功",
    # common compound forms that add no specificity
    "通过了", "已完成", "已通过", "已正确",
])


def _strip_punctuation_whitespace(s: str) -> str:
    """Remove all whitespace, quotes, punctuation, and markdown emphasis chars."""
    return re.sub(r'[\s\W_]+', '', s, flags=re.UNICODE).lower()


def _is_pure_generic_expect(value: str) -> bool:
    """Return True if the expect value is entirely composed of generic words.

    A value is pure-generic when, after stripping punctuation/whitespace, it
    equals one of the blacklisted words (or a concatenation thereof) and contains
    no concrete output string, exit code, numeric value, path, or literal token.

    Examples that ARE pure-generic (return True):
      "通过"  "pass"  "ok"  "Pass"  "通过。"  " ok "  "成功"

    Examples that are NOT pure-generic (return False):
      '"PLAN_ANTIFILL_FAIL"'   — quoted literal token
      'exit 0'                  — contains exit code
      '>=1'                     — numeric comparison
      'SYNTAX_OK'               — specific literal
      'pass (exit 0)'           — contains exit code alongside generic word
    """
    stripped = _strip_punctuation_whitespace(value)
    if not stripped:
        # Completely empty expect is also a problem, treat as generic.
        return True

    # If the stripped value IS one of the generic words directly → generic.
    if stripped in _GENERIC_WORDS:
        return True

    # Check if the value is a concatenation of only generic words with no extras.
    # Strategy: remove all generic words from stripped value; if nothing remains
    # it was composed purely of generic words.
    remainder = stripped
    for word in _GENERIC_WORDS:
        remainder = remainder.replace(word, "")
    if not remainder:
        return True

    return False


def _extract_sc_blocks(text: str) -> list[tuple[str, str]]:
    """Extract (sc_id, block_text) pairs from the plan text.

    Each block starts at the line containing an SC-ID and ends just before
    the next SC-ID line or a top-level section heading (^#) or step field
    (^WHERE/WHAT/WHY/VERIFY at column 0).

    Returns a list of (sc_id, block_text) in document order.
    """
    lines = text.splitlines(keepends=True)
    blocks: list[tuple[str, str]] = []

    # Find all SC-ID start positions in the original text.
    matches = list(_SC_DEFINITION_RE.finditer(text))
    if not matches:
        return blocks

    for i, m in enumerate(matches):
        sc_id = m.group(1)
        start = m.start()
        # Block ends at the start of the next SC entry (or end of text).
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block_text = text[start:end]
        blocks.append((sc_id, block_text))

    return blocks


def _check_antifill(text: str) -> list[str]:
    """Anti-fill hard gate: per-SC verify existence + expect generic-word blacklist.

    Returns a list of PLAN_ANTIFILL_FAIL message strings (empty = all pass).
    """
    antifill_errors: list[str] = []

    sc_blocks = _extract_sc_blocks(text)
    if not sc_blocks:
        # No SC blocks found — structural gate will catch this; skip anti-fill.
        return antifill_errors

    for sc_id, block in sc_blocks:
        # SC-4.1: each SC block must contain a verify line with non-empty content.
        if not _SC_VERIFY_LINE_RE.search(block):
            antifill_errors.append(
                f"{sc_id} 缺 verify 行 — 每条 SC 必须含可执行 "
                "verify (method: command|path|assertion|test): <内容>"
            )

        # SC-4.2: if an expect line is present, its value must not be pure generic.
        expect_match = _SC_EXPECT_LINE_RE.search(block)
        if expect_match:
            expect_value = expect_match.group(1).strip()
            if _is_pure_generic_expect(expect_value):
                antifill_errors.append(
                    f"{sc_id} expect 为纯泛词 ({expect_value!r}) — "
                    "expect 必须含具体输出串/exit code/数值/路径/字面 token，"
                    "不得只写通过|正确|完成|works|pass|ok|成功"
                )
        # Note: missing expect line is NOT flagged here — SC-4.1 (verify) is
        # the mandatory gate; expect is validated only when present.

    return antifill_errors


def _extract_defined_sc_ids(text: str) -> set[str]:
    """Return SC IDs declared as real criteria, not prose mentions."""
    return set(_SC_DEFINITION_RE.findall(text))


def _validate(target_path: str) -> tuple[list[str], list[str]]:
    """Return (structural_errors, antifill_errors); both empty = pass."""
    errors: list[str] = []
    antifill_errors: list[str] = []

    # --- Guard: capsule target ---
    if is_review2_capsule_path(target_path):
        errors.append(
            f"target is a capsule file ({Path(target_path).name}), "
            "not an original plan — use original plan path for /review2 plan_review"
        )
        return errors, antifill_errors  # no point checking further

    # --- Read file ---
    p = Path(target_path)
    if not p.exists():
        errors.append(f"target file not found: {target_path}")
        return errors, antifill_errors

    text = p.read_text(encoding="utf-8")

    # --- SC-IDs (≥1 required) ---
    sc_ids = _extract_defined_sc_ids(text)
    if not sc_ids:
        errors.append("no SC-IDs found (≥1 required: SC-1, SC-W2, etc.)")

    # --- REVIEW_DOMAIN / REVIEW_FOCUS ---
    if not _REVIEW_DOMAIN_RE.search(text):
        errors.append("missing REVIEW_DOMAIN field")
    if not _REVIEW_FOCUS_RE.search(text):
        errors.append("missing REVIEW_FOCUS field")

    # --- WHERE / WHAT / WHY / VERIFY (all 4 must appear) ---
    for field, pattern in [
        ("WHERE", _WHERE_RE),
        ("WHAT", _WHAT_RE),
        ("WHY", _WHY_RE),
        ("VERIFY", _VERIFY_RE),
    ]:
        if not pattern.search(text):
            errors.append(
                f"missing step field {field}: plan steps must include "
                "WHERE / WHAT / WHY / VERIFY for each step"
            )

    # --- Old /rev-style markers ---
    if _REV_VERDICT_RE.search(text):
        errors.append(
            "contains line-leading REV_VERDICT: — old /rev template style; "
            "update to GD_STANDARD-based plan"
        )
    if _BARE_VERDICT_RE.search(text):
        errors.append(
            "contains line-leading VERDICT: — this looks like a review output, "
            "not a plan file"
        )
    if _REVIEW_STANDARD_RE.search(text):
        errors.append(
            "contains line-leading REVIEW_STANDARD: — old /rev template style; "
            "replace with GD_STANDARD:"
        )

    # --- Anti-fill hard gate (SC-4.1 / SC-4.2) ---
    # Run even when structural errors exist so callers see both failure kinds.
    antifill_errors = _check_antifill(text)

    return errors, antifill_errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Field-based plan preflight for /review2 plan_review."
    )
    parser.add_argument("--target", required=True, help="Path to the plan file.")
    args = parser.parse_args()

    errors, antifill_errors = _validate(args.target)

    all_failed = bool(errors) or bool(antifill_errors)

    if not all_failed:
        print("PLAN_TEMPLATE_STATUS: pass")
        print("BRIDGE_INVOCATION_STATUS: allowed")
        sys.exit(0)
    else:
        print("PLAN_TEMPLATE_STATUS: fail")
        for e in errors:
            print(f"PLAN_ERROR: {e}")
        for af in antifill_errors:
            print(f"PLAN_ANTIFILL_FAIL: {af}")
        print("BRIDGE_INVOCATION_STATUS: not_started")
        sys.exit(1)


if __name__ == "__main__":
    main()
