# T6 Execution Result

```yaml
task_id: t6-fix-bridge-target
agent_role: implementer
status: completed
completed_at: 2026-06-09
```

---

## 执行完成

### 变更摘要

**scripts/gd-codex-bridge-review.py** — 新增函数 + 修改 `build_capsule_text` + 修改 `cmd_run_bridge`：

1. 新增 `_EXECUTION_ARTIFACT_KINDS` 常量（`{"code_diff", "execution_outcome", "combined"}`）
2. 新增 `_review_focus_for_kind(kind)` — 按 kind 返回 spec §2.3 focus 声明，替换写死的 `"bridge candidate review of {target.name}"`
3. 新增 `_primary_target_for_kind(kind, target)` — 返回该 kind 的真实 artifact 路径
4. 新增 `_assert_not_capsule_target(kind, target)` — 对 `_EXECUTION_ARTIFACT_KINDS` 中的 kind，若 target.name == `capsule.md` 则 raise ValueError
5. `build_capsule_text`：在 kind 枚举校验后、FileNotFoundError 校验前，调用 `_assert_not_capsule_target`（SC-6.3 早退）
6. `build_capsule_text`：`REVIEW_FOCUS` 改为 `_review_focus_for_kind(kind)`（SC-6.1）
7. `build_capsule_text`：`PRIMARY_TARGET` 改为 `_primary_target_for_kind(kind, target)`（SC-6.2）；非 plan kind 的 capsule 上下文降为 `RELATED_CONTEXT` 摘要行
8. `cmd_run_bridge`：新增对 `_EXECUTION_ARTIFACT_KINDS` 的 capsule 守卫，与 plan 路的 `PLAN_TARGET_MUST_BE_ORIGINAL_PLAN` 守卫对称（SC-6.3）

**reports/t6-router-target-trace.md** — 新建 trace 报告：
- 追踪 router 四个 `--target` 传参点（438/468/628/886 行）
- 结论：router 传的 `target` 全部来自 `args.target`（CLI 输入的真实产物），无 capsule.md 注入
- 无需修改 router 代码

---

### 成功标准验收

| SC | 验收命令 | 期望 | 实际输出 | 状态 |
|----|---------|------|---------|------|
| SC-6.1a | `grep -nE 'REVIEW_FOCUS:.*bridge candidate' scripts/gd-codex-bridge-review.py \| wc -l` | 0 | `0` | pass |
| SC-6.1b | 4 kind 的 REVIEW_FOCUS 行 `len(set(...))` | ≥3 | `4` | pass |
| SC-6.2 | `code_diff` PRIMARY_TARGET 不含 `capsule.md` | `PASS` | `PASS` | pass |
| SC-6.3 | capsule guard 命中行数 | ≥1 | `6` | pass |
| SC-6.4 | trace 报告存在 + 含 `--target`/行号引用 | ≥1 | `20` | pass |
| SC-6.5 | `plan` kind PRIMARY_TARGET 含 plan.md 路径 | `PASS` | `PASS` | pass |

---

### 验证命令真实输出

```
=== SC-6.1a: no hardcoded bridge candidate ===
       0
=== SC-6.1b: 4 distinct focus values ===
4
=== SC-6.2: code_diff PRIMARY_TARGET not capsule.md ===
PASS
=== SC-6.3: capsule guard count ===
       6
=== SC-6.4: trace report exists ===
20
=== SC-6.5: plan kind regression ===
PASS
```

---

### 运行时/持久状态

N/A — 无 daemon 启动，无 hook 注册，无 `~/.claude/` 写入。

---

### 未执行/延期

- router 代码未修改（trace 结论：router `--target` 链路 CLEAN，无需修）
- T7 owned 路径未动（`scripts/gd-review-controller.py`、`commands/review2.md`）

---

### 代码审查移交

```
PLAN_SOURCE: approved_plan
REVIEW_DOMAIN: ai_infra
REVIEW_FOCUS: bridge target fix (SC-6.1/6.2/6.3/6.4/6.5)
Review command/status: not_run
```

---

### 残余风险

- `_primary_target_for_kind` 目前对所有 kind 返回 `str(target.resolve())`（即调用方传入的 target）。正确性依赖调用方传入真实 artifact 而非 capsule——这由 `_assert_not_capsule_target` 守卫保证（capsule.md 被拒）。其他无效路径（如传错误的 .json）不在 T6 范围内，由 L3 content-evidence validator 兜底。
- none blocking

---

## Handoff Output

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t6-fix-bridge-target-result.md
  status_field: completed
  summary: >
    bridge 三档(code_diff/execution_outcome/combined) PRIMARY_TARGET 已指真实 artifact（非 capsule.md），
    REVIEW_FOCUS 按 kind 动态化（4种各异），capsule 守卫对称 plan 路，
    router target trace 已写 reports/t6-router-target-trace.md（4 site 均 CLEAN，无需修 router）。
  blockers: none
```
