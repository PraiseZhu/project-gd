# [阶段名称] 计划（Plan Mode）

GD_STANDARD: Project GD/prompts/gd-review-standard.md
TEMPLATE_KIND: gd-plan

> 作者：[Author]
> 日期：[YYYY-MM-DD]
> 状态：draft | reviewed | approved

---

> **D6 自述（必读）**：本文件为 **plan mode 用 source**，存于 Project GD 仓内的 `templates/plan-mode-template.md`。
> 部署到 live `~/.claude/templates/plan-template.md` 由 **T9** 经 `.deploy-manifest.jsonl` 完成，不在此文件内直接改 live。
> **禁止写入 `/Users/praise/.claude/**`（含 `~/.claude/templates/`、`~/.claude/commands/`、`~/.claude/scripts/` 等所有子目录）。**
> 直接修改 live 路径 = D6 红线违反，review 中 [P1] 阻断。

---

## 2. Review 对齐

- REVIEW_DOMAIN: `ai_infra | app_code | docs_content | other`
- REVIEW_FOCUS: `<focus 1>; <focus 2>; <focus 3>`

> REVIEW_FOCUS 填 3-5 项，用分号分隔；说明文字不得插入 `REVIEW_FOCUS` 与冒号之间。

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
- 不修改 `/Users/praise/.claude/**`（D6 红线，lab-only 硬约束）

**填写要求**：非目标必须是**真实可能被误做**的事情，不是废话。

---

## 成功标准（SC）

> **Anti-fill 规则 A**：每条 SC 必须绑定**命令 / 路径 / 输出断言 / 测试用例之一**；禁止仅写"目视确认 / 检查一下 / 自检即可"。写不出可执行 verify 的条件不得作为 SC。
>
> **格式约束**：每条成功标准必须以 `SC-N` 编号开头；禁止使用无 ID 勾选框（`- [ ] <无 SC 编号的描述>`）。
> 每条 SC 必须同时携带以下两个字段：
> - `verify (method: command|path|assertion|test): <验收命令或路径检查>`
> - `expect: <具体字符串/exit code/非空断言>`

- [ ] SC-1：[具体可观测状态]
  - verify (method: command): `[验收命令]`
  - expect: `[具体输出字符串或 exit 0]`
- [ ] SC-2：[具体可观测状态]
  - verify (method: path): `[文件路径存在性检查]`
  - expect: `[文件存在，exit 0]`
- [ ] SC-3：[具体可观测状态]
  - verify (method: assertion): `[grep 或 awk 断言命令]`
  - expect: `[>=N 或具体字符串]`
- [ ] SC-4：[具体可观测状态]
  - verify (method: test): `[测试命令或条件表达式]`
  - expect: `[通过/PASS/exit 0]`

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

### Step 1：[步骤名称] `[SC-1]`

WHERE: [文件/目录/命令的精确位置，例如：`scripts/foo.py:42` 或 `templates/bar.md`]

WHAT: [做什么具体动作，例如：新建文件 / 在第 N 行插入 / 将函数 X 的返回值从 Y 改为 Z]

WHY: [为什么这一步必须存在，例如：缺少此文件时 /review2 plan 无法提取 SC 清单]

VERIFY: `[验收命令]` → `[期望输出]`

**Hard-stop**：[何时必须停下来而不是继续，例如：verify 输出不符合 expect 时] → 停止原因：[不停会出什么问题]

---

### Step 2：[步骤名称] `[SC-2, SC-3]`

WHERE: [文件/目录/命令的精确位置]

WHAT: [做什么具体动作]

WHY: [为什么这一步必须存在]

VERIFY: `[验收命令]` → `[期望输出]`

**Hard-stop**：[何时停止]

---

<!-- 继续按步骤添加；每步必须含 WHERE/WHAT/WHY/VERIFY 四要素 + SC 映射 -->

---

## 边界约束

### 文件写入范围

**允许写入**（仅限）：
- `Project GD/[本阶段目标文件列表]`

**绝对禁止写入**：
- `/Users/praise/.claude/**`（任何子目录，含 `~/.claude/templates/plan-template.md`）
- `~/.claude/commands/`、`~/.claude/templates/`、`~/.claude/scripts/`
- 任何 `Project GD/` 外路径

> D6 红线：本模板为 plan mode source，部署到 live `~/.claude/templates/plan-template.md` 由 T9 完成，
> 不在此文件内直接改 live。上述"禁止写入"是所有填写此模板的计划的执行约束，不论场景。

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
| 误写 `/Users/praise/.claude/` | hard-stop + D6 路径检查；review 中 [P1] 阻断 |

---

## 交付物清单

| 文件 | 类型 | SC 映射 | 验收状态 |
|------|------|---------|---------|
| [文件路径] | new/modified | SC-N | [ ] |
| [文件路径] | new/modified | SC-N | [ ] |

---

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | [YYYY-MM-DD] | 初始版本 |

---

## 附：最小样例计划片段（SC-3e 可提取性验证用）

> 以下是使用本模板填写的最小示例，供 goal skill 结构提取测试与 SC-3e 验证使用。
> 样例展示了 SC-1 + verify (method: ...) + expect: 三件套的完整写法。

---

### 样例：新建 foo.sh 计划（最小）

**目标链**：

```
PROJECT_GOAL: 演示 plan mode 模板 SC-N 结构
CHAIN_GOAL:   让 goal skill 能从本计划中提取非空 SC 清单
PHASE_GOAL:   templates/plan-mode-template.md 存在且 SC 段结构符合提取规则
TASK_GOAL:    grep -Eq 'SC-1' templates/plan-mode-template.md && echo EXTRACTABLE
```

**成功标准**：

- [ ] SC-1：`scripts/foo.sh` 文件存在且可执行（exit 0）
  - verify (method: command): `test -f scripts/foo.sh && test -x scripts/foo.sh && echo FOO_SH_EXECUTABLE`
  - expect: `FOO_SH_EXECUTABLE`

**实施步骤**：

### Step 1：新建 foo.sh `[SC-1]`

WHERE: `scripts/foo.sh`（新建文件）

WHAT: 新建文件 `scripts/foo.sh`，写入 `#!/usr/bin/env bash` 后执行 `chmod +x scripts/foo.sh`

WHY: foo.sh 不存在时 SC-1 verify 命令返回 exit 1，验收失败

VERIFY: `test -f scripts/foo.sh && test -x scripts/foo.sh && echo FOO_SH_EXECUTABLE` → `FOO_SH_EXECUTABLE`

**Hard-stop**：VERIFY 输出非 `FOO_SH_EXECUTABLE` 时停止 → 继续执行会产生错误的交付物声明

---

<!-- END SAMPLE -->
