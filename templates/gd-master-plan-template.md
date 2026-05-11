# <Master Plan 名称> v<n>

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-master-plan

日期：YYYY-MM-DD
状态：draft | reviewed | approved | superseded
负责人：Claude 执行；Codex 可选 cross-review

---

## 1. 目标链

```text
PROJECT_GOAL: <从 GOAL_SOURCE 引用，不重写>
CHAIN_GOAL:   <从 GOAL_SOURCE 引用，不重写>
PHASE_GOAL:   <本 master plan 的阶段目标，必须可被 SC 验证>
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra | app_code | docs_content | other`
- REVIEW_FOCUS（3-5 项分号分隔）：`<focus 1>; <focus 2>; <focus 3>`
- Domain-specific notes：<本 master plan 特有的 review 注意点>

---

## 3. 成功标准（SC）

> Anti-fill：每条 SC 必须绑定**命令 / 路径 / 输出断言 / 人工验收条件之一**；禁止仅写"完善 / 优化 / 系统性 / 全面 / 增强"。

- [ ] SC-1：<具体可验证条件，含命令或路径>
- [ ] SC-2：<...>
- [ ] SC-N：<...>

---

## 4. 非目标（NON_GOALS）

- <明确不做的事 1>
- <明确不做的事 2>

---

## 5. Step 拆分

| Step | 名称 | owned_paths | blocked_by | can_parallel_with | 主要 SC |
|------|------|------------|-----------|-------------------|---------|
| 1 | <step 名称> | <路径> | — | — | SC-1 |
| 2 | <step 名称> | <路径> | step 1 | — | SC-2, SC-3 |

---

## 6. 边界（修改 / 不修改）

修改：
- <相对路径>

不修改：
- 旧 `/rev` 任何 artifact
- `/Users/praise/.claude/**`
- 其他 step 的 owned_paths

---

## 7. 风险与防护

| 风险 | 防护 |
|------|------|
| <风险 1> | <防护措施> |

---

## 8. 测试计划

```bash
# Anti-fill：每条命令必须可执行，给出明确 PASS/FAIL 信号
test -f <path>
grep -q "<token>" <file>
python3 -m json.tool <schema> >/dev/null
```

---

## 9. Assumptions

- <已确认前提 1>
- <已确认前提 2>
