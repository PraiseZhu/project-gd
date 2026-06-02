#!/usr/bin/env python3
"""
gd-build-dispatch-map.py — DEPRECATED

SUPERSEDED (commands/gd.md L191): dispatch_map 现按 templates/gd-dispatch-map-template.md
手写，仍用 gd-validate-dispatch.py 校验。本脚本不得再调用。

Usage:
    python3 gd-build-dispatch-map.py  # prints deprecation notice and exits 1
"""
import sys

print(
    "DEPRECATED: gd-build-dispatch-map.py has been superseded.\n"
    "  dispatch_map is now authored manually per templates/gd-dispatch-map-template.md\n"
    "  and validated by scripts/gd-validate-dispatch.py.\n"
    "  See commands/gd.md L191 for the migration contract.",
    file=sys.stderr,
)
sys.exit(1)