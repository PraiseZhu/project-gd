# [阶段名称] 计划

GD_STANDARD: Project GD/prompts/gd-review-standard.md
TEMPLATE_KIND: gd-plan

> 作者：[Author]
> 日期：[YYYY-MM-DD]
> 状态：draft | reviewed | approved

---

## Review 对齐

- REVIEW_DOMAIN：`ai_infra | app_code | docs_content | other`
- REVIEW_FOCUS（3-5 项分号分隔）：`<focus 1>; <focus 2>; <focus 3>`

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: [项目总目标 — 来自 PROJECT_GOAL.md 第一行]
CHAIN_GOAL:   [本阶段所服务的上层目标 — 用一句话说清楚"为什么这个阶段必须存在"]
PHASE_GOAL:   [本阶段要达成的具体状态 — 不是动作，是"完成后世界是什么样的"]
TASK_GOAL:    [本计划中最小可验证单元 — 用一句话说清楚"哪条命令/路径/输出证明完成了"]
```

**填写要求**：
- `PROJECT_GOAL` 必须与 `PROJECT_GOAL.md` 中的 `PROJECT_GOAL:` 字段一致（不改写）
- `CHAIN_GOAL` 必须回答"这个阶段如果不做，PROJECT_GOAL 会缺什么"
- `PHASE_GOAL` 必须是状态描述（"X 文件存在且通过 Y 验证"），不能是动作描述（"实现 X"）
- `TASK_GOAL` 必须是可执行的验收断言（路径/命令/输出），不能是"完成 X"

---

## 非目标（Non-Goals）

明确说明本计划**不做**什么：

- 不做 [X] — 因为 [原因/外部依赖/下一阶段处理]
- 不做 [Y] — 因为 [原因]
- 不修改 `/Users/praise/.claude/**`（lab-only 硬约束）

**填写要求**：非目标必须是**真实可能被误做**的事情，不是废话。

---

## 成功标准（SC）

> **Anti-fill 规则 A**：每条 SC 必须绑定**命令 / 路径 / 输出断言 / 测试用例之一**；禁止仅写"目视确认 / 检查一下 / 自检即可"。写不出可执行 verify 的条件不得作为 SC。

- [ ] SC-1：[具体可观测状态]
  - verify (method: command|path|assertion|test): `[验收命令或路径检查]`
  - expect: `[具体字符串/exit code]`
- [ ] SC-2：[具体可观测状态]
  - verify (method: command|path|assertion|test): `[验收命令或路径检查]`
  - expect: `[具体字符串/exit code]`
- [ ] SC-3：[具体可观测状态]
  - verify (method: command|path|assertion|test): `[验收命令或路径检查]`
  - expect: `[具体字符串/exit code]`

---

## 实施步骤

每个步骤必须写齐 4 字段，且标注映射的 SC-* IDs：

```text
Step.N  [SC-M]
  WHERE:  <文件 / 目录 / 命令的精确位置>
  WHAT:   <做什么具体动作>
  WHY:    <为什么这一步必须存在>
  VERIFY: <做完后如何验证（命令 / 路径 / 断言之一）>
```

禁止用"完善 / 优化 / 系统性 / 全面 / 增强"作为唯一动作描述。

### Step 1：[步骤名称] `[SC-N]`

WHERE: [文件/目录/命令的精确位置]

WHAT: [做什么具体动作]

WHY: [为什么这一步必须存在]

VERIFY: `[验收命令]` → `[期望输出]`

**Hard-stop**：[何时必须停下来而不是继续] → 停止原因：[不停会出什么问题]

---

### Step 2：[步骤名称] `[SC-N, SC-M]`

WHERE: [文件/目录/命令的精确位置]

WHAT: [做什么具体动作]

WHY: [为什么这一步必须存在]

VERIFY: `[验收命令]` → `[期望输出]`

**Hard-stop**：[何时停止]

---

<!-- 继续按步骤添加 -->

---

## 边界约束

### 文件写入范围

**允许写入**（仅限）：
- `Project GD/[本阶段目标文件列表]`

**绝对禁止写入**：
- `/Users/praise/.claude/**`（任何子目录）
- `~/.claude/commands/`、`~/.claude/templates/`、`~/.claude/scripts/`
- 任何 `Project GD/` 外路径

### 复用 vs 绕开

| 复用 | 不复用 |
|------|--------|
| [明确说明复用哪些现有机制] | [明确说明绕开哪些，以及为什么] |

---

## 依赖与前置条件

- `PROJECT_GOAL.md` 已存在且 hash = `[记录 shasum 值]`
- [其他前置条件，例如"Phase N 已完成"、"X 文件已存在"]

---

## 风险与防护

| 风险 | 防护 |
|------|------|
| [具体风险] | [具体防护机制] |
| 误写 `~/.claude/` | hard-stop + 路径检查 |

---

## 交付物清单

| 文件 | 类型 | SC映射 | 验收状态 |
|------|------|--------|---------|
| [文件路径] | [new/modified] | SC-N | [ ] |
| [文件路径] | [new/modified] | SC-N | [ ] |

---

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | [YYYY-MM-DD] | 初始版本 |
