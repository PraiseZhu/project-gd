# Execution Result

> 本模板用于记录计划执行结果，供 `bin/rev code` 本地 conformance gate 验证。
> 每条 SC-* 必须与 baseline 1:1 对应，不可遗漏、不可重复。
>
> REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

## 执行摘要

| 字段 | 值 |
|------|---|
| EXECUTION_STATUS | completed \| partial \| blocked |
| baseline_key | <!-- 填写 baseline key，如 phase3-test --> |
| plan_hash | <!-- 64位 hex，复制自 baseline --> |
| 执行时间 | <!-- YYYY-MM-DDTHH:MM:SSZ --> |

## SC 验收结果

| SC-ID | status | evidence | not_run_reason |
|-------|--------|----------|----------------|
| SC-1 | pass \| fail \| not_run \| n_a | <!-- pass/fail: 必填，含 backtick anchor；not_run/n_a: 留空字符串 --> | <!-- not_run/n_a: 必填原因；pass/fail: 留空字符串 --> |

<!-- 说明：
- status=pass/fail → evidence 必须非空且含 backtick anchor（如 `exit 0`、`/path/to/file` 等）；not_run_reason 留空字符串。
- status=not_run/n_a → not_run_reason 必须非空；evidence 留空字符串。
- 禁止使用泛化证据：`完成`、`OK`、`通过`、`已处理`、`见上`、`done`、`正常`、`符合预期`。
-->

## 执行说明

<!-- 简要描述执行过程、遇到的问题、决策 -->

## 机器可读块

```json rev_execution_status
{
  "baseline_key": "<!-- 填写 baseline key -->",
  "plan_hash": "<!-- 64位 hex -->",
  "execution_status": "completed",
  "sc_results": [
    {
      "id": "SC-1",
      "status": "pass",
      "evidence": "`exit 0` from `python3 rev-baseline.py validate ...`",
      "not_run_reason": ""
    }
  ]
}
```

<!-- 注意：
- 本文件是 execution artifact，不是 code review 结果。
- 本文件禁止包含 REV_VERDICT 行（REV_VERDICT 属于 reviewer/result，不属于执行方）。
- baseline_key 和 plan_hash 必须与 --baseline-file / --baseline-key 参数完全一致。
-->
