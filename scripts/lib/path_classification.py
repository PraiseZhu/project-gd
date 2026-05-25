#!/usr/bin/env python3
"""Shared path classification helpers for the GD review chain."""

from __future__ import annotations

from pathlib import Path


def is_review2_capsule_path(path: str) -> bool:
    """Return True if *path* looks like a /review2 capsule output.

    A capsule is the L2 helper output (gd-build-review2-capsule.py).
    Its canonical filename is 'capsule.md'.  The bridge must never
    accept a capsule as the plan target for --kind plan.
    """
    return Path(path).name.lower() == "capsule.md"
