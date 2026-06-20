#!/usr/bin/env python3
"""Shared SC-ID extraction helper.

SC-ID grammar: supports the target project's real uppercase SC identifiers,
including numeric and named compound forms such as SC-1, SC-W1-1,
H2B-SC-14, SC-GS1, SC-L1-1, SC-Rpt-1, and SC-Log-Fmt.

Canonical source of SC_ID_RE for the GD lab — shared between
gd-validate-review-content-evidence.py, gd-validate-review2-plan-target.py,
and any future consumer.
"""

from __future__ import annotations

import re

SC_ID_RE = re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*-)?SC-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b")

# Fix C: codex 常把字段名当值填成 placeholder（SC-ID / SC-N / SC-X 等）。
# 这些是「SC-」+ 通用占位词，不是真 SC-ID，提取时丢弃，避免被 L3 误判为「引用了假 SC-ID」。
_PLACEHOLDER_SC_IDS: frozenset[str] = frozenset(
    {"SC-ID", "SC-N", "SC-X", "SC-NN", "SC-NUM", "SC-FOO", "SC-XXX"}
)

# Fix B/Issue1: 结构化 ID 定义 —— checklist `- [ ] SC-*` + T-N 任务头 `##/### T0`。
# target 的「声明 ID」只认结构化定义，不含正文 mention（如 REVIEW_FOCUS 里的 SC-conformance 散提）。
_CHECKLIST_SC_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*(" + SC_ID_RE.pattern + r")\b", re.MULTILINE)
_TASK_HEADER_RE = re.compile(r"^#{1,6}\s+(T\d+)\b", re.MULTILINE)

# Fix B/Issue3: review 引用 ID 的宽口径 —— codex 在 `| T0 |` 行 / `SC: T0` 引用 T-N，
# 非结构化（不是 `## T0` 头），需全文 `\bT\d+\b` 才能抓到。仅用于 review 侧。
_T_REF_RE = re.compile(r"\bT\d+\b")


def extract_sc_ids(text: str) -> set[str]:
    """全文 SC-ID（placeholder 过滤）。供 extract_referenced_ids（review 侧）用。"""
    return set(SC_ID_RE.findall(text)) - _PLACEHOLDER_SC_IDS


def extract_reviewable_ids(text: str) -> set[str]:
    """target 的**结构化**可审查 ID（checklist SC + T-N 任务头），不含正文 mention。

    用于 target_sc_ids / capsule EXPECTED_SC_IDS / bridge 排他性 count。
    ancient-twirling-peacock.md → {T0-T7}（REVIEW_FOCUS 里的 SC-conformance 散提被排除）。
    """
    ids = set(_CHECKLIST_SC_RE.findall(text))
    ids.update(_TASK_HEADER_RE.findall(text))
    return ids


def extract_referenced_ids(text: str) -> set[str]:
    """review **引用**的 ID（全文 SC + T-N，placeholder 过滤）—— 用于 findings/scope/review_sc_ids。

    宽口径：codex 在 `| T0 | pass |` 行、`SC: T0` 行引用 ID，结构化提取（headers/checklist）
    抓不到，需全文。placeholder（SC-ID/SC-N）被丢，避免误判。
    """
    ids = extract_sc_ids(text)  # 全文 SC，已过滤 placeholder
    ids.update(_T_REF_RE.findall(text))  # 全文 T-N（| T0 | / SC: T0）
    return ids
