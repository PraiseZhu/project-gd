# Missing WHERE Plan (preflight fail fixture)

> Purpose: preflight must reject this — steps have WHAT/WHY/VERIFY but no WHERE field

REVIEW_DOMAIN: scripts
REVIEW_FOCUS: test coverage gap

## Success Criteria

| SC | Verify | Expect |
|----|--------|--------|
| SC-1 | check output | pass |

## Steps

### Step 1: Do something

WHAT: run the test suite
WHY: ensure coverage
VERIFY: exit 0 and PASS in output
