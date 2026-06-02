#!/usr/bin/env python3
"""
gd-validate-probe.py — DEPRECATED

SUPERSEDED (commands/gd.md L192): probe schema 现以 stage ledger 的 capability_status
字段承载。本脚本不得再调用。

Usage:
    python3 gd-validate-probe.py  # prints deprecation notice and exits 1
"""
import sys

print(
    "DEPRECATED: gd-validate-probe.py has been superseded.\n"
    "  probe schema is now carried by the stage dispatch ledger's capability_status field.\n"
    "  See commands/gd.md L192 for the migration contract.",
    file=sys.stderr,
)
sys.exit(1)