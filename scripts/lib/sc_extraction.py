#!/usr/bin/env python3
"""Shared SC-ID extraction helper.

SC-ID grammar: supports the target project's real uppercase SC identifiers,
including numeric and named compound forms such as SC-1, SC-W1-1,
H2B-SC-14, SC-GS1, SC-L1-1, SC-Rpt-1, and SC-Log-Fmt.

Canonical source of SC_ID_RE for the GD lab — shared between
gd-validate-review-content-evidence.py, gd-validate-review2-plan-target.py,
and any future consumer.
"""

from __future__ import annotations

import re

SC_ID_RE = re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*-)?SC-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b")


def extract_sc_ids(text: str) -> set[str]:
    """Return all SC-IDs that appear in *text*."""
    return set(SC_ID_RE.findall(text))
