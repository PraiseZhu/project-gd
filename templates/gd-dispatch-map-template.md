# Dispatch Map: <dispatch_id>

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-dispatch-map

> 本模板按 `docs/gd-v7-multi-agent-dispatch.md` §8-§9 字段写。
> 写完后用 `python3 scripts/gd-validate-dispatch.py <本文件对应 .json>` 校验。
> 校验通过后由主 agent（Claude Code）按 wave 顺序调度 child agent。

---

## 1. 标识与目标链

```yaml
dispatch_id: <kebab-case>
source_master_plan: <相对路径，如 plans/gd/2026-05-11-foo/master-plan.md>
goal_chain:
  PROJECT_GOAL: <从 GOAL_SOURCE 引用，不重写>
  CHAIN_GOAL: <从 GOAL_SOURCE 引用，不重写>
  PHASE_GOAL: <本 dispatch 的阶段目标，可被 SC 验证>
```

---

## 2. 并发上限（默认 2/2/2/2；合法范围 [1,2]；Plan 6.5-C 锁定）

```yaml
max_parallel_planning: 2
max_parallel_execution: 2
max_parallel_review: 2
max_parallel_validation: 2
# 上限只能降到 1，不能升到 2 以上：
# 任何 max_parallel_* 取值 > 2 → validator exit 1
# 取 1 时必须写 rationale：
overrides_rationale: <一句话说明降到 1 的理由，例：'serial 因为共享同一个 sqlite db'>
```

---

## 3. Tracks（每个 track 必填以下字段）

```yaml
tracks:
  - track_id: t1                                      # kebab-case 唯一
    mode: plan | execute | review | validate
    agent_role: child_planner | child_executor | child_reviewer | child_validator
    owned_paths:
      - <相对路径>                                     # 唯一允许写入的路径
    forbidden_paths:
      - "/Users/praise/.claude/**"
      - <其他 track 的 owned_paths>
    required_context:
      - <相对路径>                                     # 静态文件 OR 某 blocked_by track 的 deliverable
    deliverables:
      - path: <相对路径>
        kind: file | directory | report
        must_exist: true
    blocked_by: []                                    # 必须先完成的 track_id 列表
    can_parallel_with: []                             # 候选并行 track_id；必须对称声明
    sc_refs: [SC-1]                                   # 关联 SC 至少 1 项
    verify:
      - sc_ref: SC-1
        method: command | path | assertion | test
        cmd: "test -f <path> && echo PASS"
        expect: "PASS"
```

---

## 4. Waves（按串行顺序排列）

```yaml
waves:
  - wave_id: w1
    track_ids: [t1, t2]                               # 本 wave 内的 track 必须可并行（满足 §2 硬条件）
    description: <wave 目标>
  - wave_id: w2
    track_ids: [t3]                                   # 单 track 也可独占一 wave
    description: <wave 目标>
```

---

## 5. Merge gates（按 dispatch-rules §4）

```yaml
merge_gates:
  - gate_id: G1
    description: child 输出格式合规
  - gate_id: G2
    description: files_added/modified 全在 owned_paths 内
  - gate_id: G3
    description: execution result 无 REV_VERDICT/GD_REVIEW_DECISION 字段
  - gate_id: G4
    description: SC 有 evidence 或 not_run_reason
  - gate_id: G5
    description: 并行 wave 全完才进串行 wave
  - gate_id: G6
    description: reviewer 冲突时 master 写仲裁理由
```

---

## 6. 校验

```bash
python3 scripts/gd-validate-dispatch.py <本文件对应 .json> ; echo "exit=$?"
# 期望 exit=0
```

校验失败必须修，**不得**带着 violation 进 dispatch 调度。
