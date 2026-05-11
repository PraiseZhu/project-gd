# Phase 2 Smoke Test Plan

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

> 作者：Claude
> 日期：2026-05-10
> 状态：draft

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果没有 smoke 测试计划，bin/rev 的端到端行为无法被机器验证，Phase 2 验收缺乏可执行基准。
PHASE_GOAL:   bin/rev plan 在 smoke 输入上完成一次同步 review，并在 results/ 下生成 prompt.md/raw-output.txt/result.md/result.json。
TASK_GOAL:    运行 bin/rev plan fixtures/plans/phase2-good-plan.md --dry-run 后 results/<run-id>/prompt.md 存在，且含 5 个 Markdown section 标题。
```

---

## 非目标（Non-Goals）

- 不测试模型输出质量（model verdict 不可控）
- 不测试 code mode（Phase 3 reserved）
- 不修改 `~/.claude/**` 任何路径

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | bin/rev plan 接受 fixtures/plans/phase2-good-plan.md | `"$GD_ROOT/bin/rev" plan "$GD_ROOT/fixtures/plans/phase2-good-plan.md" --dry-run` → exit 0 |
| SC-2 | dry-run 生成 prompt.md 含 5 个 section | `grep -cE '^## (Review Standard|Candidate Baseline|Review Context|Artifact|Output Contract)$' <prompt.md>` → 5 |
| SC-3 | rev-baseline extract 成功产出 candidate-baseline.json | `python3 scripts/rev-baseline.py extract fixtures/plans/phase2-good-plan.md --project-goal-file PROJECT_GOAL.md --out /tmp/t.json` → exit 0 |

---

## 实施步骤

### Step 1：dry-run 验证 `[SC-1, SC-2]`

**目标**：prompt.md 正常生成，5 section 齐全

**操作**：

```bash
"$GD_ROOT/bin/rev" plan "$GD_ROOT/fixtures/plans/phase2-good-plan.md" --dry-run
```

**验收**：`grep -cE '^## ...' <prompt.md>` → `5`

**Hard-stop**：extract 失败（exit non-zero） → 停止，报告 SC 编号问题

---

### Step 2：extract baseline `[SC-3]`

**目标**：candidate-baseline.json 包含目标链和 SC 列表

**操作**：

```bash
python3 "$GD_ROOT/scripts/rev-baseline.py" extract \
  "$GD_ROOT/fixtures/plans/phase2-good-plan.md" \
  --project-goal-file "$GD_ROOT/PROJECT_GOAL.md" \
  --out /tmp/phase2-smoke-baseline.json
```

**验收**：`python3 -m json.tool /tmp/phase2-smoke-baseline.json` → exit 0

**Hard-stop**：任一 SC verify 为空 → 停止

---

## 边界约束

**允许写入**：`Project GD/results/**`、`Project GD/baselines/**`

**绝对禁止写入**：`/Users/praise/.claude/**`

---

## 依赖与前置条件

- `PROJECT_GOAL.md` 含 `^PROJECT_GOAL:` 字段
- `bin/rev` 已 chmod +x
- `scripts/rev-baseline.py` 存在且通过 py_compile

---

## 风险与防护

| 风险 | 防护 |
|------|------|
| SC numbering gap | extract 验证连续性，exit non-zero |
| PROJECT_GOAL 不匹配 | extract 字段比对，exit non-zero |
| 误写 ~/.claude/ | Hard-stop + 路径检查 |

---

## 交付物清单

| 文件 | 类型 | SC映射 | 验收状态 |
|------|------|--------|---------|
| results/<run-id>/prompt.md | new | SC-1, SC-2 | [ ] |
| results/<run-id>/candidate-baseline.json | new | SC-3 | [ ] |
