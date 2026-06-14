# Synthetic Semantic Bug Plan Snapshot

## Goal
Implement a counter module that correctly counts failures vs passes in a result list.

## Semantic Contract

`count_failures(results)` MUST count entries where `result == False` (failures).
`count_passes(results)` MUST count entries where `result == True` (passes).

The two functions must be semantic inverses: `count_failures(r) + count_passes(r) == len(r)`.

## Step 1 — implement counter functions

WHERE: fixtures/deep-review/synthetic-semantic-bug/buggy_counter.py
WHAT: Implement count_failures to return sum(1 for r in results if not r)
WHY: count_failures must count False entries (failures), not True entries (passes)

- [ ] SC-1 count_failures counts False entries (failures)
  - verify (method: command, build-gate): `python3 -c "from buggy_counter import count_failures; assert count_failures([True, False, False]) == 2, 'should count 2 failures'; print('PASS')"`
  - fail condition: count_failures([True, False, False]) returns 1 (counts passes) instead of 2 (counts failures)

- [ ] SC-2 count_failures and count_passes are semantic inverses
  - verify (method: command, build-gate): `python3 -c "from buggy_counter import count_failures, count_passes; r=[True,False,True,False]; assert count_failures(r)+count_passes(r)==len(r), 'must sum to total'; print('PASS')"`
