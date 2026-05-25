# Missing WHAT Plan (preflight fail fixture)

> Purpose: preflight must reject this — steps have WHERE/WHY/VERIFY but no WHAT field

REVIEW_DOMAIN: scripts
REVIEW_FOCUS: test coverage gap

## Success Criteria

| SC | Verify | Expect |
|----|--------|--------|
| SC-1 | check output | pass |

## Steps

### Step 1: Do something

WHERE: scripts/gd-validate-review2-plan-target.py
WHY: ensure coverage
VERIFY: exit 0 and PASS in output
