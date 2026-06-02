#!/usr/bin/env python3
"""
gd-validate-live-dispatch-smoke.py — DEPRECATED

SUPERSEDED (commands/gd.md L194): 由 gd-validate-controller-report.py 取代。
本脚本不得再调用。

Usage:
    python3 gd-validate-live-dispatch-smoke.py  # prints deprecation notice and exits 1
"""
import sys

print(
    "DEPRECATED: gd-validate-live-dispatch-smoke.py has been superseded.\n"
    "  live dispatch smoke validation is now handled by scripts/gd-validate-controller-report.py\n"
    "  See commands/gd.md L194 for the migration contract.",
    file=sys.stderr,
)
sys.exit(1)