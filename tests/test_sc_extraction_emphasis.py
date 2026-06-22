"""Regression: checklist SC-ID extraction must tolerate markdown emphasis.

Root cause of the 2026-06-22 AKB2 CQL plan-review L3 FAKE_EVIDENCE rejection:
the plan declares its success criteria as bold checklist items
``- [ ] **SC-1（...）**：...``. `extract_reviewable_ids` (the structured TARGET
extractor) used a regex that required the SC-ID to follow ``]`` directly, so the
leading ``**`` made it extract NOTHING (`target has []`). Meanwhile the review-side
broad extractor found SC-1, so the two disagreed and L3 flagged a real SC-ID as fake.

Fix: tolerate optional ``*``/``**``/``***`` (asterisk) emphasis (and surrounding
space) between the checkbox and the SC-ID — while still being structured (checklist /
T-header only, NOT prose mentions). Underscore emphasis (``__``) is intentionally not
supported: it does not occur in these plans and ``_`` is a word char that collides
with SC_ID_RE's leading ``\\b``.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import pytest

from lib.sc_extraction import extract_reviewable_ids, extract_referenced_ids


class TestBoldChecklistExtraction:
    """SC-ID wrapped in markdown emphasis inside a checklist must still be extracted."""

    def test_bold_sc_id_extracted(self):
        # Exact shape from the AKB2 how-reliability plan that triggered the bug.
        line = "- [ ] **SC-1（P0-1 scanner 捞全，golden 覆盖三类）**：source_ops"
        assert extract_reviewable_ids(line) == {"SC-1"}

    def test_bold_project_style_sc_id_extracted(self):
        assert extract_reviewable_ids("- [ ] **SC-L1-1** first") == {"SC-L1-1"}

    def test_single_asterisk_italic_extracted(self):
        assert extract_reviewable_ids("- [x] *SC-3* done") == {"SC-3"}

    def test_multiline_bold_plan_all_extracted(self):
        plan = "\n".join([
            "## 成功标准（SC）",
            "- [ ] **SC-1（a）**：x",
            "- [ ] **SC-2（b）**：y",
            "- [ ] **SC-8（h）**：z",
        ])
        assert extract_reviewable_ids(plan) == {"SC-1", "SC-2", "SC-8"}


class TestNoRegression:
    """Plain checklists, T-headers and prose-exclusion must keep working."""

    def test_plain_checklist_still_works(self):
        assert extract_reviewable_ids("- [ ] SC-2 普通格式") == {"SC-2"}

    def test_task_header_still_works(self):
        assert extract_reviewable_ids("## T0 任务\n### T1 子任务") == {"T0", "T1"}

    def test_prose_mention_still_excluded(self):
        # NOT a checklist item / header → structured extractor must ignore it.
        assert extract_reviewable_ids("本 plan 引用 SC-99 作为参考，见上文") == set()

    def test_bold_prose_mention_still_excluded(self):
        # Emphasis tolerance must stay scoped to checklist lines, not prose.
        assert extract_reviewable_ids("说明：**SC-99** 不是 checklist 项") == set()

    def test_review_side_unaffected_broad(self):
        # Review-side broad extractor already found bold SC-IDs; keep it that way.
        assert extract_referenced_ids("| **SC-1** | pass | ok |") == {"SC-1"}
