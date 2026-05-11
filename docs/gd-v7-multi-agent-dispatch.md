# /gd v7 多 Agent Dispatch 规则

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-dispatch-rules

> **Plan 4 v2 产物**。本文件定义 `/gd` 在 multi-agent 编排时的人工编排规则。
> **范围**：规则、判定标准、打回准则、合并门控。
> **不范围**：实现真实 auto-dispatcher / 启动子 agent / 接 Codex / 注册 slash command。
> 本文件供主 agent（Claude Code）人工编排 `/gd plan` / `/gd execute` 流程参考；后续 Plan 5/6 可能由代码实现，但**规则源**始终是本文件。

---

## 1. 角色与职责

### 1.1 主 agent（Claude Code，唯一 master）

**只有主 agent 可以**：

- 拆分 master plan → step plan → task packet
- 决定 dispatch wave 与 track 边界
- 调度 child agent（plan / execute / review / validate 四类）
- 合并 child 输出
- 打回 child（按 §5 规则）
- 仲裁 reviewer 冲突（按 `prompts/gd-review-standard.md` Merge Matrix §5）

主 agent **不允许**：

- 把范围决策交给 child（child 永远只做 task packet 内的事）
- 跳过 task packet 校验直接调度
- 在 child 输出未达通过门时合并

### 1.2 Child agent（4 类）

| 角色 | 输入 | 输出 | 默认并发上限（Plan 6.5-C 收紧）|
|------|------|------|------------|
| `child_planner` | step plan packet | 子计划草稿 + 候选 task packet 列表 | **2** |
| `child_executor` | 1 个 approved task packet | 1 份 execution result（按 `gd-execution-result-template.md`） | **2** |
| `child_reviewer` | plan 或 execution result | 1 份 review result（按 `gd-plan-review-template.md` 或 `gd-execution-review-template.md`） | **2** |
| `child_validator` | dispatch map / fixture | validator 输出（exit code + 摘要） | **2** |

并发上限可在 dispatch map 顶层 `max_parallel_planning` / `max_parallel_execution` / `max_parallel_review` / `max_parallel_validation` 字段覆盖（**合法范围 [1,2]**；只能降到 1，不能升到 2 以上；Plan 6.5-C 锁定决策）。覆盖到 1 必须写 rationale。

### 1.3 Child agent 通用约束

- 只读自己 `task_packet.required_context` 列出的文件
- 只写自己 `task_packet.owned_paths`
- 不访问 `/Users/praise/.claude/**`
- 不启动 daemon / 注册 hook / 修改 cron / `LaunchAgent` / MCP
- 输出结论必须中文（按 global rule）
- 上下文不足 → 返回 `blocked_missing_context`，**禁止猜测**

---

## 2. 可并行硬条件（**全部满足**才允许并行）

两个 track A、B 可候选并行 ⟺ 同时满足：

1. **`owned_paths` 无重叠**（按 §6 路径重叠算法判定，**禁止纯字符串前缀**）
2. **互不在对方 `blocked_by`**
3. **`required_context` 不依赖对方未完成 deliverable**（A 的 required_context 中若含 B 的 deliverable，则 A 必须 `blocked_by: [B]`）
4. **verify 命令不共享可写状态**（如同一个 sqlite db / 同一个 socket / 同一个 lock file）

任一未满足 → **必须串行**，写入 `blocked_by`。

---

## 3. 必须串行硬条件

- 修改同一文件
- 修改同一目录的父子关系（`/foo` 与 `/foo/bar`）
- 需要统一 schema / 接口 / 命名 / 路径约定（约定先行 task 必先完成）
- 后一任务读取前一任务 deliverable
- 同一份 report / manifest / index 由多个任务共同更新

---

## 4. 合并门控（merge gates）

主 agent 合并 child 输出前必须验证：

| 门 | 条件 | 失败处置 |
|----|------|---------|
| G1 | child 输出格式合规（按对应 template） | 打回，按 §5 规则 |
| G2 | execution result 的 `files_added/modified` 全在 task packet `owned_paths` 内 | 打回 + review 标 `[P1] 路径越界` |
| G3 | execution result 中无 `REV_VERDICT:` / `GD_REVIEW_DECISION:` 字段（execution 工件应用 `EXEC_STATUS`） | 打回 |
| G4 | 每条 SC 有 `evidence`（pass/fail）或 `not_run_reason`（not_run/n_a） | 打回 |
| G5 | 并行 wave 内所有 child 完成 → 串行 wave 才能进 | 等待，不强制中断 |
| G6 | reviewer 冲突 → master 写仲裁理由（`MERGE_NOTES.arbitration_reason`） | 仲裁未写不得 final approved |

---

## 5. 打回（pushback）规则

主 agent 见到以下情形 → **必须打回 child**，不得私自补齐：

| # | 情形 | 打回标签 |
|---|------|---------|
| 5.1 | task packet 不自包含（含"见上文 / 按之前讨论"） | `not_self_contained` |
| 5.2 | SC `verify` 不可执行（仅"目视确认"） | `verify_not_executable` |
| 5.3 | `owned_paths` 越界（write 到 forbidden_paths 或 ~/.claude/**） | `path_out_of_bounds` |
| 5.4 | execution result 缺 `not_run_reason`（status=not_run/n_a 时） | `missing_not_run_reason` |
| 5.5 | execution result 缺 `evidence`（status=pass/fail 时） | `missing_evidence` |
| 5.6 | child 输出不是中文结论 | `language_violation` |
| 5.7 | 步骤动作仅用"完善 / 优化 / 系统性 / 全面 / 增强"作为唯一动词 | `anti_fill_rule_b` |
| 5.8 | child 启动了 daemon / hook / cron / MCP | `runtime_violation` |

打回必须返回到 child 重做，主 agent **不得**用自己上下文补齐再合并。

---

## 6. 路径重叠判定算法（**禁止纯字符串前缀**）

validator 实现必须遵守：

```python
from pathlib import PurePosixPath

def normalize(p: str) -> PurePosixPath:
    # 去 ./ 前缀；规范化分隔符；不解析 symlink（PurePath 即可）
    return PurePosixPath(p.lstrip("./") if p.startswith("./") else p)

def overlaps(a: str, b: str) -> bool:
    """True 当且仅当 A 和 B 是同一路径或父子关系。
    禁止纯 str.startswith：'/foo' 与 '/foobar' 不算 overlap。"""
    pa, pb = normalize(a), normalize(b)
    if pa == pb:
        return True
    # 一方是另一方的祖先
    try:
        pa.relative_to(pb)
        return True
    except ValueError:
        pass
    try:
        pb.relative_to(pa)
        return True
    except ValueError:
        pass
    return False
```

测试用例（必过）：

| A | B | overlap? | 理由 |
|---|---|---------|------|
| `/foo` | `/foo` | yes | 同路径 |
| `/foo` | `/foo/bar` | yes | 父子 |
| `/foo/bar` | `/foo` | yes | 父子 |
| `/foo` | `/foobar` | **no** | 字符串前缀但非父子 |
| `/foo/bar` | `/foo/baz` | **no** | 同父目录但兄弟 |
| `./foo` | `foo` | yes | 规范化后相同 |

---

## 7. `required_context` 双类校验（**关键**）

每条 `required_context` 路径分两类校验：

### 7.1 静态文件类

不出现在任何 track 的 `deliverables` 中 → **validate-time 必须 `os.path.exists()` 为真**。

例：模板文件 `templates/gd-task-packet-template.md`、shared core 文件 `prompts/gd-review-standard.md`。

### 7.2 Deliverable 引用类

出现在某 track 的 `deliverables` 中 → **不要求** validate-time 存在，但要求：

- 该 producer track 必须出现在引用 track 的 `blocked_by` 中（避免循环依赖）
- producer track 不能与引用 track 在同一 wave 并行

validator 算法：

```python
# Phase 1: build deliverables index
deliverables_index = {}  # path -> producer_track_id
for t in dispatch_map["tracks"]:
    for d in t.get("deliverables", []):
        path = d["path"] if isinstance(d, dict) else d
        deliverables_index[normalize(path)] = t["track_id"]

# Phase 2: cross-check required_context per track
for t in dispatch_map["tracks"]:
    for ctx_path in t.get("required_context", []):
        norm = normalize(ctx_path)
        if norm in deliverables_index:
            producer = deliverables_index[norm]
            if producer == t["track_id"]:
                violation: 自引用
            elif producer not in t.get("blocked_by", []):
                violation: deliverable 引用但未声明 blocked_by
        else:
            if not os.path.exists(ctx_path):
                violation: 静态文件不存在
```

---

## 8. dispatch map 必填字段（顶层）

```yaml
dispatch_id: <kebab-case>
source_master_plan: <相对路径>
goal_chain:
  PROJECT_GOAL: ...
  CHAIN_GOAL: ...
  PHASE_GOAL: ...
max_parallel_planning: 2       # 默认值；合法范围 [1,2]（Plan 6.5-C 锁定）
max_parallel_execution: 2      # 合法范围 [1,2]
max_parallel_review: 2         # 合法范围 [1,2]
max_parallel_validation: 2     # 合法范围 [1,2]
tracks:
  - <每个 track 字段见 §9>
waves:
  - wave_id: w1
    track_ids: [t1, t2, t3]
    description: <wave 目标>
merge_gates:
  - <见 §4>
```

---

## 9. track 必填字段（每个 track）

```yaml
track_id: <kebab-case 唯一>
mode: plan | execute | review | validate
agent_role: <child_planner | child_executor | child_reviewer | child_validator>
owned_paths: [<相对路径>...]
forbidden_paths: [<至少含 ~/.claude/** 与其他 track 的 owned_paths>]
required_context: [<相对路径>...]
deliverables:
  - path: <相对路径>
    kind: file | directory | report
    must_exist: true
blocked_by: [<track_id>...]
can_parallel_with: [<track_id>...]
sc_refs: [SC-1, SC-2, ...]
verify:
  - sc_ref: SC-1
    method: command | path | assertion | test
    cmd: <可执行命令>
    expect: <期望输出>
```

`can_parallel_with` 必须**对称声明**（A.can_parallel_with 含 B ⟺ B.can_parallel_with 含 A），validator 强制检查。

---

## 10. Wave 编排示例（参考）

简单 dispatch（3 track，2 wave）：

```text
Wave 1（并行）:
  - t1 (plan track A)
  - t2 (plan track B)
  说明: 互不依赖，owned_paths 不重叠

Wave 2（串行）:
  - t3 (合并 t1+t2 deliverables 输出)
  说明: blocked_by [t1, t2]，必须等 wave 1 全完
```

---

## 11. 与其他 Plan 的关系

| Plan | 关系 |
|------|------|
| Plan 2 shared core | 本文件复用 `prompts/gd-review-standard.md` Merge Matrix；child agent 输出按 Plan 2 templates |
| Plan 3 `/gd` command | `/gd execute` 当前 fail-closed；本文件规则在 Plan 5 实际接入 dispatcher 时被代码消费 |
| Plan 5 execution dispatch | 实现本文件规则的代码层 |
| Plan 6 Codex cross-review | 复用本文件 §5 打回规则；Codex 作为额外 reviewer |
| Plan 7 anti-fill fixtures | 用本文件 §2 / §3 / §6 / §7 设计 negative fixture |
| Plan 8 isolation 收口 | 审计 manifest revisions[] 与本文件未越界 |

---

## 12. Child Agent Capability Probe（Plan 6.5-C candidate）

任何按本文件 §1.2 启动 child agent 的 `/gd` stage（`/gd plan` child_planner / `/gd execute agent_exec` child_executor）在 dispatch 前**必须**运行 capability probe。

### 12.1 Probe 定义

probe = 检查 Claude Code runtime 当前可用工具列表中是否含可由主 agent 发起 prompt 并等待返回结果的子 agent / Task 调度工具。**不做 no-op fake invoke**（不发空 task 试探）；第一条真实 child task 同时作为 runtime proof。

### 12.2 Probe 输出格式

```yaml
CHILD_AGENT_CAPABILITY: available | unavailable | unknown
probe_method: tool_list_inspection | runtime_environment_check
evidence: <短句证据；如 "Task tool 在当前工具列表" 或 "工具列表未含 Task / Agent">
fallback_mode: manual_packet | fail_closed
```

### 12.3 Fallback 规则

- `available` → 按 §1 / §2 正常 dispatch；max_parallel 上限 2
- `unavailable / unknown` + `/gd plan` → `fallback_mode: manual_packet`：主 agent 自己写 task packet，**不得**声称已并行调度
- `unavailable / unknown` + `/gd execute agent_exec` → `fallback_mode: fail_closed`：输出 `CAPABILITY_STATUS: pending_future_plan`，停止；**不得**自动降级为 `human_exec`（避免 mode 偷换）

### 12.4 Probe 不通过时的 manifest 与 commands/gd.md 状态

- `manifest.gd-v7.json` 不写 `agent_exec active`
- `commands/gd.md` `/gd execute` `CAPABILITY_STATUS` 保持 `local_only` + 仅 `human_exec`
- segment / final report 必须明示 probe 结果与 fallback path
