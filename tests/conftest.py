"""Pytest configuration for Project GD tests."""
import importlib.util
import os
import sys
import pytest

# Add project root to path so scripts can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))


def _load_hyphenated_module(module_name: str, file_name: str) -> None:
    """Register a script with hyphens in its filename as an importable module."""
    if module_name not in sys.modules:
        script_path = os.path.join(PROJECT_ROOT, "scripts", file_name)
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)


# Pre-register hyphenated script modules for test imports
_load_hyphenated_module("gd_codex_bridge_review", "gd-codex-bridge-review.py")
_load_hyphenated_module("gd_review_router", "gd-review-router.py")
_load_hyphenated_module("gd_review_controller", "gd-review-controller.py")
_load_hyphenated_module("gd_prepare_workcopy", "gd-prepare-workcopy.py")
