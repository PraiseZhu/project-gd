# Missing VERIFY Plan (preflight fail fixture)

> Purpose: preflight must reject this — steps have WHERE/WHAT/WHY but no VERIFY field

REVIEW_DOMAIN: scripts
REVIEW_FOCUS: test coverage gap

## Success Criteria

| SC | Verify | Expect |
|----|--------|--------|
| SC-1 | check output | pass |

## Steps

### Step 1: Do something

WHERE: scripts/gd-validate-review2-plan-target.py
WHAT: read the validator code
WHY: ensure coverage is complete
