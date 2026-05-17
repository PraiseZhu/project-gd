# Combined Review Result (v2)

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-combined-review
REVIEW_KIND: combined
SCHEMA_VERSION: 2.0

GD_REVIEW_DECISION: APPROVED | REQUIRES_CHANGES | FAILED

> 顶层 `GD_REVIEW_DECISION:` 行是 source-of-truth（per Plan 8 v4.1 Step 4）。
> Anti-fill 适用范围：**PLAN_SECTION_ONLY** —— substitution drill 仅对
> `<!-- gd-plan-section:start -->` … `<!-- gd-plan-section:end -->` 之间的
> plan-bearing 内容生效。section 之外的执行/代码部分按 NOOP 处理。
> Combined review：当 `scope_checked` 有任一 `result == "fail"` 时，**必须** emit `cross_validation_findings`（非空）；
> 全部 `scope_checked` pass/n_a 时，`cross_validation_findings` 允许为空数组。
> 规则及 validator 见 `prompts/gd-review-standard.md` §14。
> Combined review **不可** 复制源 review 中已有的 finding（no re-raise）。

---

## 1. 标识与运行状态

```text
REVIEWER: <claude_main | claude_subagent_<role> | codex>
REVIEW_TARGET: <combined bundle 路径 或 dir>
REVIEW_TARGET_KIND: execution_plus_code
TARGET_ROLE: combined_bundle
REVIEW_RUN_STATUS: completed | completed_with_constraint | degraded | failed_to_run
```

`GD_REVIEW_DECISION` 取值见 `prompts/gd-review-standard.md` "Output Contract"。
顶层 header 与 §6 fenced JSON block 的 `gd_review_decision` 必须一致。
`source_of_truth_decision.location = "top_level_machine_header"`、`value` 与顶层一致。
禁止裸 `VERDICT:` 或 `REV_VERDICT:`。

---

## 2. Scope Checked

| 检查面 | 结论 | 证据（≤30 字） |
|--------|------|---------------|
| execution_completeness | pass / fail / n_a | <bundle execution 路径> |
| code_matches_execution_claim | pass / fail / n_a | <diff vs execution log> |
| plan_alignment | pass / fail / n_a | <plan vs bundle> |

---

## 3. Findings（**禁止 re-raise**：源 review 已写入的 finding 不再写一遍）

> Combined reviewer 只补充**跨源（execution + code）才能发现的新 finding**。
> 已被独立 execution_outcome / code_diff review 标记的 finding 不重复列出。
> 跨源不一致写入 §6 的 `cross_validation_findings` 数组（不在本节）。

### Finding 1 [P1|P2] <短标题>

```yaml
severity: P1 | P2
title: <短标题>
sc_refs:
  - SC-<N>
evidence: <跨源证据，例如 execution log 与 git diff 对比>
impact: <bundle 级别的影响>
required_fix: <最小修复，不扩大范围>
verify: <可执行命令或隔离用例>
```

---

## 4. Merge Notes

```yaml
MERGE_NOTES:
  conflict_with_other_reviewer: false | true
  arbitration_reason: <如果冲突，写仲裁理由>
  degraded_reason: <如果 REVIEW_RUN_STATUS != completed，写原因>
```

---

## 5. Residual Risk

字符串字段（v2 schema：`residual_risk: string`），无残留风险写 `none`。

---

## 6. Machine-readable Result（v2 schema，含 cross_validation_findings）

reviewer 输出**必须且只能**含一个以下 block；JSON 必须通过
`schema/gd-review-result-v2.schema.json`。缺失 / 重复 / schema fail → `FAILED`。

<!-- gd-review-result-json:start -->
```json
{
  "schema_version": "2.0",
  "template_kind": "gd-combined-review",
  "review_kind": "combined",
  "review_target_kind": "execution_plus_code",
  "target_role": "combined_bundle",
  "reviewer": "claude_main",
  "review_target": "<bundle 相对路径>",
  "review_run_status": "completed",
  "gd_review_decision": "APPROVED",
  "source_of_truth_decision": {
    "location": "top_level_machine_header",
    "value": "APPROVED"
  },
  "scope_checked": [
    {"area": "execution_completeness", "result": "pass", "evidence": "<≤60 字>"}
  ],
  "findings": [],
  "merge_notes": {
    "conflict_with_other_reviewer": false
  },
  "residual_risk": "",
  "timestamp": "2026-05-14T00:00:00Z",
  "cross_validation_findings": []
}
```
<!-- gd-review-result-json:end -->

填写规则：
- `template_kind="gd-combined-review"`、`review_kind="combined"`、
  `review_target_kind="execution_plus_code"`、`target_role="combined_bundle"` 固定
- `cross_validation_findings[*].inconsistency_type` 取值见 v2 schema enum：
  `execution_diverges_from_plan` | `code_does_not_match_execution_claim` |
  `plan_step_skipped_in_code` | `extra_code_outside_plan_scope`
- `cross_validation_findings[*].findings` 至少 1 条，每条含 `severity` / `title` / `evidence`
- §3 中**不得复述**源 review 已 raise 的 finding（no re-raise）
- `timestamp` 必须 ISO 8601 with timezone

---

## 7. Plan Section（可选，仅当 combined bundle 含 plan-bearing 子文档时启用）

> **作用范围**：仅本 section 内的内容触发 substitution drill。
> 调用 `scripts/gd-validate-plan-review-anti-fill.py --review-kind gd-combined-review <file.md>`
> 时 validator 仅扫描 `<!-- gd-plan-section:start -->` … `<!-- gd-plan-section:end -->`
> 之间的 `gd-plan-review-anti-fill` block，section 之外不触发 anti-fill。
>
> 如果 combined bundle 不含 plan 子文档，删除整段 §7（包括 markers），validator 走 NOOP 路径。

<!-- gd-plan-section:start -->

### 7.1 Plan-bearing 内容摘要

<列出 bundle 中 plan-bearing 的文件路径与摘要 — 例如 sub-plan / amendment / decision log>

### 7.2 Anti-Fill block（plan_section_only scope 下必填）

```json gd-plan-review-anti-fill
{
  "substitution_drill": {
    "done": true,
    "sample_field": "<plan-bearing 文档中的字段路径>",
    "would_substitute_into": "<同 plan 内另一字段或另一 sub-plan 的同名字段>",
    "result": "pass"
  },
  "banned_token_scan": {
    "scanned_files": [
      "<plan-bearing 子文档相对路径>"
    ],
    "hits": []
  },
  "anchored_evidence_check": {
    "all_anchors_resolved": true,
    "unresolved": []
  }
}
```

填写规则：
- `result: pass` → plan 内容具体、不可替换 → drill 通过
- `result: fail` → plan 内容泛化 → 整体 `GD_REVIEW_DECISION: REQUIRES_CHANGES`
- `banned_token_scan.scanned_files` 仅包含 plan-bearing 文件路径
- `anchored_evidence_check.unresolved` 非空 → `GD_REVIEW_DECISION: REQUIRES_CHANGES`

<!-- gd-plan-section:end -->
