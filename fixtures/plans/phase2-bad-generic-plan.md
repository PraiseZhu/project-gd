# Phase 2 Bad Generic Plan (Anti-Fill Test)

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

> 作者：Claude
> 日期：2026-05-10
> 状态：draft

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果没有同步 runner，Phase 1 的标准只能停留在文档层。
PHASE_GOAL:   bin/rev 可以运行并生成 review 结果。
TASK_GOAL:    全面完善 bin/rev 的实现，确保整体质量符合标准。
```

---

## 非目标（Non-Goals）

- 不修改 ~/.claude/**

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | 系统性优化 bin/rev 的实现质量 | 确认代码质量符合标准 |
| SC-2 | 全面增强 runner 的稳定性 | 目测正确 |

---

## 实施步骤

### Step 1：优化 bin/rev `[SC-1]`

**目标**：全面提升代码质量

**操作**：

```bash
# 系统性优化实现
```

**验收**：确认正确

**Hard-stop**：无

---

## 边界约束

**允许写入**：`Project GD/**`

**绝对禁止写入**：`/Users/praise/.claude/**`
