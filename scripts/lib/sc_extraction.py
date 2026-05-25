#!/usr/bin/env python3
"""Shared SC-ID extraction helper.

SC-ID grammar: must end with a digit; supports compound forms like
SC-W1-1, H2B-SC-14, SC-GS1. The optional -[0-9]+ suffix preserves
full precision so SC-W1-1 and SC-W1-999 are treated as distinct IDs.

Canonical source of SC_ID_RE for the GD lab — shared between
gd-validate-review-content-evidence.py, gd-validate-review2-plan-target.py,
and any future consumer.
"""

from __future__ import annotations

import re

SC_ID_RE = re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*-)?SC-[A-Za-z]*[0-9]+(?:-[0-9]+)?\b")


def extract_sc_ids(text: str) -> set[str]:
    """Return all SC-IDs that appear in *text*."""
    return set(SC_ID_RE.findall(text))
