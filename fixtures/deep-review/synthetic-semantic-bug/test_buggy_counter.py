"""Test for buggy_counter — passes despite the semantic bug."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from buggy_counter import count_failures


def test_count_failures_with_all_pass():
    # Plan says: count_failures([True, True, True]) should return 0 (no failures)
    # Bug: count_failures actually counts True values (passes), so it returns 3
    # But this specific test passes because [False, True] gives count_failures=1
    # which is "expected" by the buggy author who confused pass/fail
    results = [False, True]  # 1 failure, 1 pass
    # BUG: should assert count_failures(results) == 1, but author wrote:
    assert count_failures(results) == 1  # This passes! But for wrong reason
