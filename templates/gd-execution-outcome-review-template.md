# Execution Outcome Review Result (v2)

REVIEW_KIND: execution_outcome
TEMPLATE_KIND: gd-execution-outcome-review
SCHEMA_VERSION: 2.0
GD_STANDARD: <fill from capsule>
GOAL_SOURCE: <fill from capsule>

GD_REVIEW_DECISION: <APPROVED | REQUIRES_CHANGES | FAILED>

---

## 1. 标识与运行状态

```text
REVIEWER: <claude | codex>
REVIEW_TARGET: <execution outcome JSON path>
REVIEW_TARGET_KIND: execution_only_no_code
TARGET_ROLE: execution_artifact
REVIEW_RUN_STATUS: <completed | failed_to_run | transport_failed>
```

## 2. Scope Checked

review 执行 outcome artifact 时必须覆盖以下检查面（每个标 pass/fail + 简短证据）：

| 检查面 | 必查内容 |
|--------|---------|
| sc_acceptance_coverage | 每个 SC 是否 status 明确 + evidence 非空（pass 必有 evidence；not_run 必有 not_run_reason） |
| verify_reruns_executed | task_outcomes 中每个 verify_rerun 是否 actual_exit==expected_exit；expected_stdout_substring 是否真在 actual_stdout 中 |
| deliverable_existence | 所有 must_exist=true 的 deliverable 是否 verified=true |
| owned_paths_compliance | owned_paths_post_audit.writes_outside_owned 是否为空 |
| anti_fill_check | sc_acceptance evidence 是否含具体命令、数字、路径，不是宽泛 "通过" / "完成" |

## 3. Findings

逐条列出 P0/P1/P2 finding，每条含 severity / title / sc_refs / evidence / impact / required_fix / verify。

## 4. Merge Notes

如本 review 与其他 reviewer 输出冲突，记录冲突原因和决议。

## 5. Residual Risk

非阻塞但需追踪的风险。

## 6. Machine-readable Result (v2 schema)

必须输出符合 `schema/gd-review-result-v2.schema.json` 的 JSON 块，包裹在 `<!-- gd-review-result-json:start -->` ... `<!-- gd-review-result-json:end -->` 标签内。

字段须含：schema_version / template_kind / review_kind / review_target_kind / target_role / reviewer / review_target / review_run_status / gd_review_decision / source_of_truth_decision / scope_checked / findings / merge_notes / residual_risk / timestamp。
