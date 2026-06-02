#!/usr/bin/env python3
"""
gd-validate-planning-dispatch-log.py — DEPRECATED

SUPERSEDED (commands/gd.md L193): 由 gd-validate-stage-dispatch-ledger.py 取代。
本脚本不得再调用。

Usage:
    python3 gd-validate-planning-dispatch-log.py  # prints deprecation notice and exits 1
"""
import sys

print(
    "DEPRECATED: gd-validate-planning-dispatch-log.py has been superseded.\n"
    "  planning dispatch log validation is now handled by scripts/gd-validate-stage-dispatch-ledger.py\n"
    "  See commands/gd.md L193 for the migration contract.",
    file=sys.stderr,
)
sys.exit(1)