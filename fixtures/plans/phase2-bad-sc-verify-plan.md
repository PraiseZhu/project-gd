# Phase 2 Bad SC Numbering Plan (extract should fail)

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

> 作者：Claude
> 日期：2026-05-10
> 状态：draft

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果没有同步 runner，Phase 1 的标准只能停留在文档层。
PHASE_GOAL:   bin/rev plan 可以完成一次同步 plan review。
TASK_GOAL:    运行 bin/rev plan 后 results/<run-id>/result.json 存在且 verdict=APPROVED。
```

---

## 非目标（Non-Goals）

- 不修改 ~/.claude/**

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | bin/rev 存在且可执行 | `test -x "$GD_ROOT/bin/rev"` → exit 0 |
| SC-3 | rev-result-writer.sh --help 输出含所有 flags | `"$GD_ROOT/scripts/rev-result-writer.sh" --help` → 含 `--kind` |

---

## 实施步骤

### Step 1：验证 bin/rev `[SC-1]`

**目标**：bin/rev 存在

**操作**：

```bash
test -x "$GD_ROOT/bin/rev"
```

**验收**：`test -x "$GD_ROOT/bin/rev"` → exit 0

**Hard-stop**：文件不存在 → 停止

---

## 边界约束

**允许写入**：`Project GD/**`

**绝对禁止写入**：`/Users/praise/.claude/**`
