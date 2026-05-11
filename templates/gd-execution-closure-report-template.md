# /gd Execution Closure Report（批次收口报告）模板

> **用途**：执行批次全部 task 完成后，主 agent 生成收口报告，汇总 CLOSURE_STATUS 与各 track 结果。
> **消费者**：Plan 6 Codex cross-review（作为 review 输入之一）；Plan 8 isolation 收口审计
> **依赖**：对应的 `execution_batch.json`（必须通过 `gd-validate-execution-batch.py`）

---

```json
{
  "closure_id": "closure-<batch_id>-<YYYYMMDD>",
  "source_batch": "<batch_id>",
  "closure_status": "<closed|closed_with_constraints|blocked|failed>",
  "track_results": [
    {
      "track_id": "<track_id>",
      "exec_status": "<completed|failed|skipped|blocked>",
      "sc_pass_count": 0,
      "sc_fail_count": 0,
      "sc_skip_count": 0
    }
  ],
  "failed_tracks": [],
  "not_run_aggregation": {
    "total": 0,
    "skipped": 0,
    "blocked": 0,
    "in_progress": 0
  },
  "next_action": null,
  "constraint_notes": null,
  "generated_at": "<ISO 8601 时间戳>"
}
```

---

## 字段说明

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `closure_id` | string | 格式：`closure-<batch_id>-<YYYYMMDD>` |
| `source_batch` | string | 来源批次的 `batch_id` |
| `closure_status` | enum | 见 §CLOSURE_STATUS 规则 |
| `track_results` | array | 每个 track 的收口摘要（非空） |
| `failed_tracks` | array | `exec_status ∉ {completed, completed_with_skips}` 的 track_id 列表（可空） |
| `not_run_aggregation` | object | 聚合统计：`{total, skipped, blocked, in_progress}` |
| `generated_at` | string | ISO 8601，UTC |

### 条件必填字段

| 字段 | 必填条件 | 说明 |
|------|---------|------|
| `next_action` | `closure_status ∈ {blocked, failed}` | 人工干预路径，≥10 字符，禁止"继续执行"等占位语 |
| `constraint_notes` | `closure_status = closed_with_constraints` | 描述约束内容，≥10 字符 |

### CLOSURE_STATUS 判定规则

| 条件 | `CLOSURE_STATUS` |
|------|----------------|
| 所有 track `exec_status = completed`，所有 verify `result = PASS` | `closed` |
| 所有 track 完成（含 `completed_with_skips`），无 `failed` | `closed_with_constraints` |
| 存在 `exec_status = blocked`（上游未完成） | `blocked` |
| 存在 `exec_status = failed` | `failed` |

---

## 使用步骤

1. **批次执行完成后**：收集所有 task 的 `gd_execution_status_json` 块
2. **汇总统计**：计算 `sc_pass/fail/skip_count`，识别 `failed_tracks`
3. **判定 CLOSURE_STATUS**：按上方规则选取
4. **填写条件必填字段**：若 `blocked/failed` 必填 `next_action`
5. **输出 closure report JSON**
6. **校验**：通过 `gd-validate-execution-batch.py --closure` 检查（结构合规）

---

## Anti-fill 规则

- `next_action` 禁止值：`"继续执行"`、`"请人工检查"`、`"后续处理"`（≤5 字的通用占位）
- `constraint_notes` 禁止值：`"有一些问题"`、`"需要注意"`（无具体内容的短语）
- `failed_tracks` 为空但 `closure_status = failed`：校验器拒绝
- `track_results` 为空数组：校验器拒绝
