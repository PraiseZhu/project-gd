# /gd v7 执行调度规则（Plan 5）

> **Plan**：Plan 5 Claude Execution Dispatch + Result Closure
> **Stage**：主 agent 执行 batch + 结果写入 + 批次收口（不启动 child agent / 不接 Codex auto-executor）
> **依赖**：Plan 4 dispatch map + validator（必须 dispatch map valid 才能建 batch）

---

## 1. 核心概念

### 1.1 Execution Batch（执行批次）

```
dispatch_map.json
       │
       ▼  (按 wave 顺序取出 tracks)
execution_batch.json   ← Plan 5 核心数据结构
       │
       ▼
一个 batch 含多个 task_result，每个 task_result 对应一个 track
       │
       ▼
closure_report.json    ← 批次收口，CLOSURE_STATUS + 聚合统计
```

### 1.2 执行模式

| 模式 | 含义 | Plan 5 支持 |
|------|------|------------|
| `dry_run` | 生成 batch 结构，不写交付物 | ✓ |
| `human_exec` | 人工执行，主 agent 写结果 | ✓（Plan 5 scope） |
| `agent_exec` | 启动 child agent 自动执行 | `pending_future_plan`（Plan 5 不实现） |

### 1.3 执行阶段状态

| `EXEC_STATUS` | 含义 |
|---------------|------|
| `not_started` | 任务尚未执行 |
| `in_progress` | 执行中 |
| `completed` | 执行完成 + verify 全部通过 |
| `completed_with_skips` | 执行完成，部分 verify 跳过（非阻断） |
| `failed` | 执行失败 / verify 不通过 |
| `blocked` | 上游 track 未完成，阻断当前 track |
| `skipped` | 主动跳过（附 `not_run_reason`） |

### 1.4 批次收口状态（CLOSURE_STATUS）

| `CLOSURE_STATUS` | 含义 |
|-----------------|------|
| `closed` | 批次全部 track 完成，所有 verify 通过 |
| `closed_with_constraints` | 批次完成，部分 verify 跳过或降级（可接受） |
| `blocked` | 批次存在阻断依赖，无法继续 |
| `failed` | 批次内 track 失败，需人工干预 |

---

## 2. Execution Batch 结构

### 2.1 顶层字段（必填）

```json
{
  "batch_id": "batch-<dispatch_id>-wave<N>",
  "dispatch_id": "<source dispatch_id>",
  "wave_ref": "w1",
  "batch_created_at": "2026-05-11T00:00:00Z",
  "execution_mode": "human_exec",
  "task_results": [...]
}
```

### 2.2 task_result 字段（每个 track 对应一项）

```json
{
  "task_id": "<track_id>",
  "track_ref": "<track_id>",
  "exec_status": "completed",
  "not_run_reason": null,
  "deliverables_produced": [
    {"path": "...", "kind": "file", "verified": true}
  ],
  "verify_results": [
    {
      "sc_ref": "SC-1",
      "method": "command",
      "cmd": "python3 -m json.tool manifest.gd-v7.json > /dev/null && echo PASS",
      "result": "PASS",
      "exit_code": 0
    }
  ],
  "gd_execution_status_json": {
    "task_id": "<track_id>",
    "exec_status": "completed",
    "sc_results": {"SC-1": "pass"}
  }
}
```

### 2.3 machine-readable 块约定

每个 `task_result` 的执行结果文件（`gd-execution-result-template.md`）必须包含机器可读 JSON 块：

```
<!-- gd-execution-status-json:start -->
{"task_id": "...", "exec_status": "...", "sc_results": {...}}
<!-- gd-execution-status-json:end -->
```

批次收口器（`gd-validate-execution-batch.py`）解析此块读取执行状态，不依赖 Markdown 表格 regex。

---

## 3. Closure Report 结构（Patch #1）

### 3.1 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `closure_id` | string | `closure-<batch_id>-<timestamp>` |
| `source_batch` | string | 对应 `batch_id` |
| `closure_status` | enum | `closed \| closed_with_constraints \| blocked \| failed` |
| `track_results` | array | 每条 track 的收口状态摘要 |
| `failed_tracks` | array | `exec_status != completed*` 的 track_id 列表 |
| `not_run_aggregation` | object | `{total: N, skipped: N, blocked: N, in_progress: N}` |
| `generated_at` | string | ISO 8601 时间戳 |

### 3.2 条件必填字段

| 字段 | 必填条件 |
|------|---------|
| `next_action` | `closure_status` 为 `blocked` 或 `failed` 时**必填**，说明人工干预路径 |
| `constraint_notes` | `closure_status` 为 `closed_with_constraints` 时必填 |

---

## 4. Validator 链式调用（Patch #2）

`gd-validate-execution-batch.py` 在执行 batch 校验前必须先运行 dispatch map validator：

```
python3 scripts/gd-validate-dispatch.py <dispatch_map>
  → exit ≠ 0 → fail-fast: "dispatch map invalid, 无法校验 batch"
  → exit == 0 → 继续 batch 结构 + 语义校验
```

**目的**：保证 batch 引用的 dispatch map 在 validate-time 仍合法，防止 dispatch map 被改坏后 batch 静默通过。

---

## 5. 执行规则

### 5.1 Wave 顺序执行

- 同一 wave 内的 track 才可并行执行（已由 dispatch validator 保证 `can_parallel_with` 声明）
- 下一 wave 必须等前一 wave 所有 track `exec_status ∈ {completed, completed_with_skips}` 后才能开始
- 任一 track `failed | blocked` → 当前 wave 阻断，不进下一 wave

### 5.2 Deliverable 写入约束

- `owned_paths` 范围内：任意写入
- `forbidden_paths` 范围内：禁止写入，违规立即停止
- `~/.claude/**`：绝对禁止写入

### 5.3 SC verify 执行规则

| verify `method` | 执行方式 |
|----------------|---------|
| `command` | 运行 `cmd` 字符串，捕获 exit code |
| `path` | 检查 `cmd` 路径是否存在 |
| `assertion` | 检查 `cmd` 断言表达式是否为真 |
| `test` | 运行测试套件，检查通过率 |

**Anti-fill 规则 C**（继承 Plan 4）：每个 SC 必须绑定可执行 verify，`sc_refs` 与 `verify[].sc_ref` 集合必须严格相等。

---

## 6. 打回规则

以下情况 batch 结果标记 `CLOSURE_STATUS: failed`，主 agent 必须打回重做（不能跳过）：

1. 任意 track 的 `exec_status == failed`（非 skipped）
2. `deliverables_produced` 列表中 `verified: false` 的交付物出现在 `must_exist: true` 的 deliverable
3. `verify_results` 中 exit_code ≠ 0 且 method == `command`
4. 机器可读 JSON 块缺失或 JSON 解析失败

---

## 7. 合并规则

所有 wave batch 完成后，主 agent 汇总：

1. 所有 track 的 `gd_execution_status_json` 块聚合为 master execution status
2. `CLOSURE_STATUS = closed`：所有 SC 通过，可提交 execution review
3. `CLOSURE_STATUS = closed_with_constraints`：记录约束项，降级提交 review

---

## 8. 与其他 Plan 的关系

| Plan | 关系 |
|------|------|
| Plan 4 | dispatch map + validator（Plan 5 入口必须先通过 Plan 4 validator） |
| Plan 6 Codex cross-review | 消费 closure report + execution batch 作为 review 输入 |
| Plan 7 anti-fill fixtures | 复用 batch 结构设计 negative fixtures |
| Plan 8 isolation 收口 | 审计 batch + closure artifacts 完整性 |

---

## 9. 当前限制（Plan 5 scope）

- `execution_mode: agent_exec`（child agent 自动执行）→ `pending_future_plan`（Plan 5 不实现）
- `execution_mode: human_exec`（主 agent + 人工写结果）→ ✓ Plan 5 实现范围
- Batch validator 当前为静态结构 + 语义校验，不运行实际 verify cmd（dry-run 模式）
