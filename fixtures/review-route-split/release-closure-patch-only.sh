#!/usr/bin/env bash
# fixture: release-closure-patch-only
# trigger: validate capsule that has no git_status_short inline_fact (patch-only capsule)
# command: python3 scripts/gd-validate-review2-capsule.py --capsule <patch-only-capsule.md>
# expected: exit 1, CAPSULE_VALIDATE_FAIL (missing release_closure required fields)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CAPSULE=$(mktemp /tmp/patch-only-capsule-XXXX.md)
trap "rm -f '$CAPSULE'" EXIT
cat > "$CAPSULE" << 'CAPSULE'
# /review2 Capsule — patch-only-test
REVIEW_PROFILE: release_closure
REVIEW_GOAL: Test patch-only capsule rejected
OUTPUT_CONTRACT:
  MANDATORY_READ_COVERAGE:
  L3_GD_REVIEW_SEMANTICS: unchanged
  RELEASE_VERDICT: NOT_APPLICABLE
CAPSULE
python3 "$ROOT/scripts/gd-validate-review2-capsule.py" --capsule "$CAPSULE" > /dev/null 2>&1; EXIT=$?
# Expected: validator must exit 1 (rejection). Fixture wrapper exits 0 on expected outcome.
if [ $EXIT -eq 1 ]; then
  echo "FIXTURE_PASS: release-closure-patch-only rejected with exit=1 (expected)"
  exit 0
else
  echo "FIXTURE_FAIL: expected exit=1 got=$EXIT (validator did not reject patch-only capsule)"
  exit 1
fi
