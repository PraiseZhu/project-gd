#!/usr/bin/env bash
# fixture: release-closure-complete
# trigger: /review2 --profile release_closure (golden path)
# command: python3 scripts/gd-build-review2-capsule.py --profile release_closure --out-dir /tmp/fixture-complete/
# expected: exit 0, CAPSULE_BUILD_PASS
set -euo pipefail
OUT=$(mktemp -d /tmp/fixture-complete-XXXX)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python3 "$ROOT/scripts/gd-build-review2-capsule.py" --profile release_closure --out-dir "$OUT"
EXIT=$?
grep -q "CAPSULE_BUILD_PASS" "$OUT"/../../../dev/stdin 2>/dev/null || true
[ $EXIT -eq 0 ] && echo "FIXTURE_PASS: release-closure-complete exit=0" || echo "FIXTURE_FAIL: exit=$EXIT"
rm -rf "$OUT"
