# Synthetic Skip Target Plan Snapshot

## Goal
Verify that a golden_replay test actually executes (not just collected).

## Step 1 — golden replay verification

WHERE: fixtures/deep-review/synthetic-skip-target/
WHAT: Run the golden replay test and verify it passes with 0 skipped.
WHY: If the test is skipped, it means replay hasn't been wired up — a pass claim is false.

- [ ] SC-1 golden replay execution passes with 0 skipped
  - verify (method: command, build-gate): `python3 -m pytest fixtures/deep-review/synthetic-skip-target/ -q`
  - expected: 0 skipped, 1 passed
  - fail condition: any test skipped with reason containing "golden_replay placeholder"
