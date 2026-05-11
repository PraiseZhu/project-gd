# /gd Execution Batch（执行批次）模板

> **用途**：记录一个 wave 的执行批次，由主 agent 在执行前创建，执行后填写结果。
> **消费者**：`gd-validate-execution-batch.py`（结构 + 语义校验）
> **依赖**：对应的 `dispatch_map.json`（必须通过 `gd-validate-dispatch.py`）

---

```json
{
  "batch_id": "batch-<dispatch_id>-wave<N>",
  "dispatch_id": "<对应 dispatch map 的 dispatch_id>",
  "wave_ref": "w<N>",
  "batch_created_at": "<ISO 8601 时间戳>",
  "execution_mode": "human_exec",
  "task_results": [
    {
      "task_id": "<track_id>",
      "track_ref": "<track_id>",
      "exec_status": "not_started",
      "not_run_reason": null,
      "deliverables_produced": [
        {
          "path": "<deliverable path>",
          "kind": "<file|directory|report>",
          "verified": false
        }
      ],
      "verify_results": [
        {
          "sc_ref": "<SC-N>",
          "method": "<command|path|assertion|test>",
          "cmd": "<可执行命令/路径/断言，≥3 字符>",
          "result": "<PASS|FAIL|SKIP>",
          "exit_code": null
        }
      ],
      "gd_execution_status_json": {
        "task_id": "<track_id>",
        "exec_status": "not_started",
        "sc_results": {}
      }
    }
  ]
}
```

---

## 字段说明

### 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `batch_id` | ✓ | 格式：`batch-<dispatch_id>-wave<N>` |
| `dispatch_id` | ✓ | 来源 dispatch map 的 `dispatch_id` |
| `wave_ref` | ✓ | 对应 dispatch map 的 `wave_id` |
| `batch_created_at` | ✓ | ISO 8601，UTC |
| `execution_mode` | ✓ | `human_exec`（Plan 5）/ `agent_exec`（未来） |
| `task_results` | ✓ | 非空数组，每个元素对应 wave 内一个 track |

### task_result 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `task_id` | ✓ | 唯一，通常等于 `track_ref` |
| `track_ref` | ✓ | 必须在 dispatch map 的 tracks 中存在 |
| `exec_status` | ✓ | 枚举：`not_started\|in_progress\|completed\|completed_with_skips\|failed\|blocked\|skipped` |
| `not_run_reason` | 条件 | `exec_status = skipped\|blocked` 时必填 |
| `deliverables_produced` | ✓ | 数组（可为空 `[]`） |
| `verify_results` | ✓ | 非空数组 |
| `gd_execution_status_json` | ✓ | 机器可读状态块，必须与 `exec_status` 一致 |

### verify_result 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `sc_ref` | ✓ | 必须在 `track.sc_refs` 中 |
| `method` | ✓ | 枚举：`command\|path\|assertion\|test` |
| `cmd` | ✓ | ≥3 字符；禁止"目视确认"等 anti-fill 关键词 |
| `result` | ✓ | `PASS\|FAIL\|SKIP` |
| `exit_code` | 条件 | `method = command` 时必填，整数 |

---

## 使用步骤

1. **执行前**：复制本模板，填写 `batch_id / dispatch_id / wave_ref / batch_created_at`
2. **每个 track 执行前**：设置 `exec_status = "in_progress"`
3. **执行后**：
   - 更新 `exec_status`
   - 填写 `deliverables_produced`（含 `verified` 状态）
   - 填写 `verify_results`（逐条 SC run）
   - 同步更新 `gd_execution_status_json`
4. **校验**：`python3 scripts/gd-validate-execution-batch.py batch-<id>.json dispatch-map.json`
5. **收口**：通过后生成 closure report

---

## Anti-fill 规则

- `cmd` 禁止含：目视确认、目视检查、看看是否正确、自检即可
- `not_run_reason` 若为 `null` 但 `exec_status = skipped`：校验器拒绝
- `verify_results` 为空数组：校验器拒绝
- `sc_refs`（来自 dispatch map）与 `verify_results[].sc_ref` 集合必须严格相等
