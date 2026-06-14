"""
Synthetic semantic bug target for deep-review e2e testing.
Bug: count_failures() returns the number of PASSES (not failures).
The test passes because test_count_failures() calls count_failures()
and compares result to 0 when it should compare to 1.
"""


def count_failures(results: list[bool]) -> int:
    """Count the number of failures in results. Returns count of True (wrong: True=pass)."""
    return sum(1 for r in results if r)  # BUG: should be `not r`


def count_passes(results: list[bool]) -> int:
    """Count the number of passes in results."""
    return sum(1 for r in results if r)
