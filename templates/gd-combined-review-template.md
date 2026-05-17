# Combined Review Result (v2)

REVIEW_KIND: combined
TEMPLATE_KIND: gd-combined-review
SCHEMA_VERSION: 2.0
GD_STANDARD: <fill from capsule>
GOAL_SOURCE: <fill from capsule>

GD_REVIEW_DECISION: <APPROVED | REQUIRES_CHANGES | FAILED>

---

## 1. 标识与运行状态

```text
REVIEWER: <claude | codex>
REVIEW_TARGET: <combined target reference>
REVIEW_TARGET_KIND: execution_plus_code
TARGET_ROLE: combined_artifact
REVIEW_RUN_STATUS: <completed | failed_to_run | transport_failed>
```

## 2. Scope Checked

combined review 必须覆盖 execution_outcome 检查面 + code_diff 检查面 + cross-validation：

| 类别 | 检查面 |
|------|--------|
| outcome | sc_acceptance_coverage / verify_reruns_executed / deliverable_existence / owned_paths_compliance / anti_fill_check |
| code | code_diff_consistency / unit_test_coverage / api_contract_changes / security_review |
| cross | outcome_vs_code_consistency / stage_order |

`stage_order` 必须为 `["outcome", "code"]`（outcome-first）。

## 3. Findings

逐条列出 P0/P1/P2 finding，区分 finding 来自 outcome 还是 code 还是 cross-validation。

## 4. Cross-validation Findings

combined review 独有：记录 outcome 与 code diff 之间是否一致。例如：

- outcome 声明 files_modified 中的文件是否在 code diff 中真实出现
- code diff 引入的新公开 API 是否在 sc_acceptance 中有对应 SC
- outcome 中 verify_reruns 引用的命令是否在 code diff 后仍可执行

## 5. Merge Notes

如本 review 与其他 reviewer 输出冲突，记录冲突原因和决议。

## 6. Residual Risk

非阻塞但需追踪的风险。

## 7. Machine-readable Result (v2 schema)

必须输出符合 `schema/gd-review-result-v2.schema.json` 的 JSON 块，包裹在 `<!-- gd-review-result-json:start -->` ... `<!-- gd-review-result-json:end -->` 标签内。

字段须含 execution_outcome-review 全部字段 + `cross_validation_findings`（combined 独有）。
