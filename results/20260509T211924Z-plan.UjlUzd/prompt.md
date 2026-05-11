## Review Standard

# /rev Review 标准

> **唯一真源（Single Source of Truth）**
> 本文件是 `/rev` CLI runner 与 Codex 桌面端的共同 review 标准。
> 所有阶段计划、执行结果的 review 必须引用本文件：
> `REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md`
>
> 修改本文件前必须同步更新引用方的 review 依据。

---

## 一、输出契约（MANDATORY）

### 1.1 Verdict 字段

每次 review 响应**必须**包含且仅包含以下三种 verdict 之一：

```
REV_VERDICT: APPROVED
REV_VERDICT: REQUIRES_CHANGES
REV_VERDICT: FAILED
```

**禁止**：
- 输出裸 `VERDICT:` — 会触发 live review hook 的 regex
- 输出 `REV_VERDICT: PASS` / `REV_VERDICT: OK` 等非标准值
- 遗漏 `REV_VERDICT:` 行（reviewer 必须最终输出一行）

### 1.2 输出语言

所有面向用户的结论、摘要、证据说明必须使用**中文**。

**保持英文**（机器可读）：命令、路径、变量名、枚举 key。

### 1.3 输出结构

```
# [Plan/Code] Review 结果

REV_VERDICT: [APPROVED|REQUIRES_CHANGES|FAILED]
REVIEW_KIND: [plan|code]
REVIEW_DOMAIN: ai_infra

## 审查范围

| 检查面 | 结论 | 证据（≤30字） |
|--------|------|--------------|
| [检查面] | [通过/阻塞/跳过] | [简短证据] |

## 发现（Findings）— 仅 P1/P2 阻断项

### Finding N [P1|P2] <标题>

问题：<具体描述，指向计划/代码的哪个部分>
证据：<文件:行/命令输出/路径>
影响：<如果不修复，什么会失败>
最小修复：<具体要改什么，不是建议，是指令>
验收：<可执行的验收命令>

## 残余风险

[P3/非阻断项，或 "none"]
```

---

## 二、Goal-Driven 检查（PLAN review 专用）

### 2.1 目标链完整性（必查）

计划必须包含以下字段，且内容不可为占位符：

| 字段 | 合格标准 | 不合格示例 |
|------|----------|-----------|
| `PROJECT_GOAL` | 与 `PROJECT_GOAL.md` 中的同名字段完全一致 | 改写、缩略、翻译 |
| `CHAIN_GOAL` | 回答"本阶段不做，PROJECT_GOAL 缺什么" | "实现 X 功能" |
| `PHASE_GOAL` | 状态描述，不是动作 | "开发 X 模块" |
| `TASK_GOAL` | 可执行断言（路径/命令/输出） | "完成 X 的实现" |

**阻断触发**：任一字段缺失、为空、为模板占位符（`[...]` 未填写）→ P1 阻断。

### 2.2 SC-* 编号化标准（必查）

每条成功标准必须满足：

1. 有唯一 ID（`SC-N`，N 从 1 开始连续）
2. 有可执行 Verify（命令/路径/输出断言）
3. 至少一个实施步骤中有对应 `[SC-N]` 标注

**阻断触发**：SC 存在但 Verify 为空/为"手工确认"/为"目测正确" → P1 阻断。

### 2.3 实施步骤步骤映射（必查）

每个实施步骤必须：

1. 标注映射的 SC-* IDs（`[SC-N]`）
2. 包含具体操作（命令/路径/写入内容），不能只有意图描述
3. 包含 Hard-stop 触发条件

**阻断触发**：步骤描述为纯意图（"分析 X"/"研究 Y"/"考虑 Z"）且无具体绑定操作 → P2 阻断。

---

## 三、Anti-Fill 检查（PLAN + CODE review 均适用）

### 3.1 泛化动作判定规则（MANDATORY）

以下判定规则按优先级顺序执行。

#### 规则 A：泛化动词禁用集

以下动词**单独作为步骤的唯一动作**时触发检查：

```
系统性 / 全面 / 优化 / 完善 / 增强 / 提升 / 梳理 / 对齐 /
优先考虑 / 确保 / 加强 / 改善 / 规范 / 统一
```

**判定逻辑**（AND 条件，全部成立才阻断）**：
- 条件 1：步骤核心动词属于上方禁用词集
- 条件 2：步骤中无具体绑定对象（无路径/无命令/无 SC-* ID/无输出断言）
- 条件 3：步骤中无 Verify 行

三个条件同时成立 → P2 阻断。

**例外（不阻断）**：
- "全面测试 SC-1 至 SC-5 的验收" — 有 SC 绑定 ✓
- "优化 `bin/rev` 的 timeout 参数从 240s 改为 120s" — 有路径+具体变更 ✓
- "梳理 `fixtures/plans/*.md` 并输出候选清单" — 有路径+输出 ✓

#### 规则 B：泛化词作为"成功"的唯一证明

SC 的 Verify 如果只包含泛化描述而无可执行验证：

```
# 阻断示例
SC-3 verify: 确认代码质量符合标准      ← 无命令，无路径，无输出断言

# 合格示例
SC-3 verify: rg 'REV_VERDICT' Project GD/prompts/ → 至少1条命中
```

**阻断触发**：Verify 内容无法被机器执行（无命令/无路径/无 `→ 期望输出`）→ P1 阻断。

#### 规则 C：证据链断裂

执行结果（code review）中，某 SC 声称"完成"但：
- 没有对应的实际输出文件路径
- 没有命令执行结果的引用
- 没有 diff 片段

**阻断触发**：声称完成但无具体证据 → P1 阻断。

### 3.2 Anti-Fill 误判防护（不得误伤）

以下情况**不得**触发 anti-fill 阻断：

- 步骤中的泛化词是**修饰性描述**而非**核心动作**（"全面地检查以下命令的返回值：`diff ...`"）
- 步骤有多个操作，其中一个用了泛化词但其他操作有具体绑定
- Non-Goal 列表中的泛化词（描述不做什么是允许的）
- 注释或说明段落中的泛化词（区分操作步骤和说明文字）

---

## 四、阻断阈值（Blocker Threshold）

`REV_VERDICT: REQUIRES_CHANGES` 仅在以下情况触发：

| 阻断类别 | 说明 |
|----------|------|
| 活动路径会失败 | 执行计划步骤会报错或产生错误输出 |
| 用户目标未达成 | TASK_GOAL 不可验证 / SC-* 无 verify |
| Baseline/State 影响后续运行 | 写入错误的 baseline 会影响后续 Phase |
| 生成管线持续输出错误 | 模板错误导致 AI 持续填出泛化内容 |
| 安全/数据/不可逆风险 | 误写 ~/.claude/、误删数据、密钥暴露 |
| 核心验证缺失 | 无法判断计划是否成功完成 |
| Anti-Fill P1 阻断 | SC verify 无法执行 / 证据链断裂 |

**不得阻断**：

- 风格偏好、架构美学意见
- 休眠代码（不在活动路径上）
- 不影响运行时的过时文档
- 非活动路径的清理建议
- `NON_GOALS` 中列出的项目
- `USER_ACCEPTED_DECISIONS` 中的决策
- `KNOWN_LIMITATIONS` 中的已知限制

---

## 五、Plan Review 专属规则

### 5.1 Non-Goals 检查

计划必须有 Non-Goals 段落，且必须列出**真实可能被误做**的事情。

**阻断触发**：Non-Goals 为空或只有废话 → P2 阻断（可能范围蔓延）。

### 5.2 Hard-stop 检查

每个实施步骤必须有 Hard-stop 触发条件。

**阻断触发**：步骤无 Hard-stop 且该步骤会写入外部状态 → P2 阻断。

### 5.3 文件范围声明

计划必须明确声明：
- 允许写入的文件列表（`Project GD/` 内）
- 绝对禁止写入的路径（`/Users/praise/.claude/**`）

---

## 六、Code Review 专属规则

### 6.1 SC-* 完整性检查（MANDATORY）

执行结果必须逐条列出 baseline 中**全部** SC-* 的状态：

```
| SC-N | [pass|fail|not_run|n_a] | 证据（路径/命令输出片段） | 未执行原因（如适用） |
```

**阻断触发**：任一 SC 状态为空白 / 缺列 / 缺证据 → P1 阻断。

### 6.2 REV_VERDICT 声明位置

code review result 中的 `REV_VERDICT:` 必须在 SC 完整性表格**之后**，不得在开头仅凭意图声明。

### 6.3 路径越界检查

执行结果或 code diff 中出现对 `~/.claude/**` 的任何写操作 → P1 阻断。

### 6.4 Execution Artifact 与 Code Review Result 字段区分

**Execution artifact**（执行结果 `.md`）使用 `EXECUTION_STATUS` 字段与 ` ```json rev_execution_status ` 机器块表达执行状态，**禁止**在执行 artifact 中写 `REV_VERDICT:`（该字段属于 reviewer，不属于被 review 的文件）。

- `EXECUTION_STATUS`：`completed | partial | blocked` — 描述执行完成情况
- ` ```json rev_execution_status `：包含结构化 SC 验收结果的机器可读块
- code review result 中的 `REV_VERDICT:` 是最终 reviewer 判断，只出现在 reviewer 输出里

**阻断触发**：执行 artifact 中出现 `REV_VERDICT:` 行 → P1 阻断（污染 review 结果解析）。

---

## 七、Convergence 规则（多轮 review 专用）

当 `REVIEW_DELTA_SCOPE` = `prior_findings_only` 或 `direct_downstream` 时：

- 默认只检查上轮阻断项及其直接下游
- 新增 finding 必须满足：P1/P2 阻断级别 + 本轮引入（非历史问题）
- 同一根因阻断最多 2 轮；第 3 轮只允许 P1/P2
- 不重复旧 finding；若已解决，写入残余风险 1 行

---

## 八、Plan/Code Template Parity 检查

### 8.1 桌面端 parity 约定

Codex 桌面端出方案时，计划顶部必须有：

```
REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md
```

### 8.2 Parity 验证（Phase 4 执行）

- CLI runner 加载的 prompt = 本文件全文
- 桌面端引用的标准 = 本文件路径
- 一致性验证写入 `reports/parity-check.md`

---

## 九、质量规则

- 每条 Finding 必须有具体证据（文件路径、行号、命令输出）
- 每条 Finding 必须有"最小修复"（指令，不是建议）和"验收"（可执行命令）
- 禁止模糊建议（"考虑..."、"可能应该..."）— 非阻断项进残余风险
- P3 项必须进残余风险，不得作为 Finding

---

*本文件版本：1.0.0 | 创建于：2026-05-09 | 所属项目：Project GD*


## Candidate Baseline

{
  "goal_chain": {
    "project": "在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少\"格式完整但计划不具体\"的 AI 填表问题。",
    "chain": "如果 SOD 每次全量 Read 33 个 priority 文件，上下文浪费约 26k tokens，且多数文件与当前任务无关。",
    "phase": "改 SOD 加载语义：默认只读 MEMORY.md + USER.md，其他 priority 文件按关键词命中再 Read。",
    "task": "修改 context-guard.md 和 memory-zones.md，添加可执行的命中规则，并通过 3 个 smoke test 验证。"
  },
  "success_criteria": [
    {
      "id": "SC-1",
      "text": "`context-guard.md` 修改后明确：SOD 默认 Read 序列 = MEMORY.md + USER.md，其他按命中规则 Read",
      "verify": "`grep -q 'MEMORY.md.*USER.md' ~/.claude/rules/context-guard.md && echo PASS`"
    },
    {
      "id": "SC-2",
      "text": "`memory-zones.md` 同步更新加载语义描述",
      "verify": "`grep -q '命中规则' ~/.claude/rules/memory-zones.md && echo PASS`"
    },
    {
      "id": "SC-3",
      "text": "命中规则可执行：写在规则文件里，Agent 能按规则判定是否 Read 某文件（关键词匹配 + 优先级）",
      "verify": "`grep -q '关键词来源' ~/.claude/rules/context-guard.md && echo PASS`"
    },
    {
      "id": "SC-4",
      "text": "Smoke test 1：开新会话喊\"做 AKB 翻译\" → Read 列表 ⊇ {USER.md, project_akb_*}，不含无关 feedback",
      "verify": "新会话 transcript 中 SOD 后 Read 列表包含 USER.md + project_akb_*，不含 feedback_eod_*.md"
    },
    {
      "id": "SC-5",
      "text": "Smoke test 2：开新会话喊\"提交代码\" → Read 列表 = {MEMORY.md, USER.md}（最小集）",
      "verify": "新会话 transcript 中 SOD 后 Read 列表 = {MEMORY.md, USER.md}，无其他文件"
    },
    {
      "id": "SC-6",
      "text": "Smoke test 3：开新会话喊\"压缩一下上下文\" → Read 列表 ⊇ {feedback_chinese_after_compaction.md}",
      "verify": "新会话 transcript 中 SOD 后 Read 包含 feedback_chinese_after_compaction.md"
    },
    {
      "id": "SC-7",
      "text": "/context 在 SOD 后的 Messages 区 token 增量 < 8k（基线预估 ~26k 全量 Read）",
      "verify": "SOD 完成后 `/context` 显示 Messages token 增量 < 8000"
    },
    {
      "id": "SC-8",
      "text": "备份快照存在 `<workspace>/_backup/memory-index-first-2026-05-08/`",
      "verify": "`test -d <workspace>/_backup/memory-index-first-2026-05-08 && ls` 显示 context-guard.md + memory-zones.md"
    }
  ],
  "plan_hash": "aa83920cfc00cff2e48d6af3f0d835fa7f09c4cda98eafc75778245ef21f4829",
  "non_goals": [
    "不动 memory 文件本身（位置、内容、三区分层）",
    "不改 Claude Code 的 auto-load 机制（MEMORY.md 仍自动加载）",
    "不改 Phase B 的 lazy rules（B 与 C 互不干扰）",
    "不删除任何 priority 文件",
    "不改 EOD 收割/归档逻辑"
  ],
  "accepted_decisions": []
}


## Review Context

PROJECT_GOAL_SOURCE: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD/PROJECT_GOAL.md
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
REVIEW_DOMAIN: ai_infra
REVIEW_FOCUS: Goal-Driven Anti-Fill plan review
IN_SCOPE: plan goal chain, SC-* completeness, step mapping, anti-fill rules
OUT_OF_SCOPE: execution result conformance (Phase 3), A/B comparison (Phase 4)


## Artifact

---
source_id: phase-c-memory-index-first.md
source_sha256: 54ef1ee3b3c1b3cff18774d7d454a7c822b1ec681e3c49bdb728649455796249
sanitized_by: claude
sanitization_checks:
  - no_secrets
  - no_tokens
  - no_keys
  - no_private_urls
  - no_emails
  - no_personal_paths
sanitization_notes: |
  "负责人：praise + Claude" → "负责人：<USER> + Claude"
  Reformatted SC list (checkbox format) to required table format for bin/rev plan parsing.
  SC smoke tests preserved with executable verify commands.
expected_class: concrete_good
expected_rev_outcome: APPROVED
expected_findings: []
---

# Plan: Phase C — MEMORY.md 索引化加载

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

日期：2026-05-08
状态：draft v1.1（review 补丁后）
负责人：<USER> + Claude

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果 SOD 每次全量 Read 33 个 priority 文件，上下文浪费约 26k tokens，且多数文件与当前任务无关。
PHASE_GOAL:   改 SOD 加载语义：默认只读 MEMORY.md + USER.md，其他 priority 文件按关键词命中再 Read。
TASK_GOAL:    修改 context-guard.md 和 memory-zones.md，添加可执行的命中规则，并通过 3 个 smoke test 验证。
```

---

## Review 对齐

REVIEW_DOMAIN：ai_infra

REVIEW_FOCUS：
- 加载语义改动后，Agent 能否真正按关键词命中需要的 memory（而不是凭印象跳过该读的）
- USER.md 默认必读这条不能被跳过——这是用户画像，丢失会导致沟通风格全错
- feedback 漏读的最坏情况评估：哪些 feedback 漏读会立刻翻车（比如"压缩后保持中文"漏读会输出英文）

Domain-specific notes：
- ai_infra：runtime active = SOD 流程；trigger surface = context-guard.md / memory-zones.md / SOD skill；state baseline = 当前规则文本快照；validation = 新会话 SOD 后看 transcript Read 调用清单；stale cleanup = 无（无文件移动）

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | `context-guard.md` 修改后明确：SOD 默认 Read 序列 = MEMORY.md + USER.md，其他按命中规则 Read | `grep -q 'MEMORY.md.*USER.md' ~/.claude/rules/context-guard.md && echo PASS` |
| SC-2 | `memory-zones.md` 同步更新加载语义描述 | `grep -q '命中规则' ~/.claude/rules/memory-zones.md && echo PASS` |
| SC-3 | 命中规则可执行：写在规则文件里，Agent 能按规则判定是否 Read 某文件（关键词匹配 + 优先级） | `grep -q '关键词来源' ~/.claude/rules/context-guard.md && echo PASS` |
| SC-4 | Smoke test 1：开新会话喊"做 AKB 翻译" → Read 列表 ⊇ {USER.md, project_akb_*}，不含无关 feedback | 新会话 transcript 中 SOD 后 Read 列表包含 USER.md + project_akb_*，不含 feedback_eod_*.md |
| SC-5 | Smoke test 2：开新会话喊"提交代码" → Read 列表 = {MEMORY.md, USER.md}（最小集） | 新会话 transcript 中 SOD 后 Read 列表 = {MEMORY.md, USER.md}，无其他文件 |
| SC-6 | Smoke test 3：开新会话喊"压缩一下上下文" → Read 列表 ⊇ {feedback_chinese_after_compaction.md} | 新会话 transcript 中 SOD 后 Read 包含 feedback_chinese_after_compaction.md |
| SC-7 | /context 在 SOD 后的 Messages 区 token 增量 < 8k（基线预估 ~26k 全量 Read） | SOD 完成后 `/context` 显示 Messages token 增量 < 8000 |
| SC-8 | 备份快照存在 `<workspace>/_backup/memory-index-first-2026-05-08/` | `test -d <workspace>/_backup/memory-index-first-2026-05-08 && ls` 显示 context-guard.md + memory-zones.md |

---

## 非目标（Non-Goals）

- 不动 memory 文件本身（位置、内容、三区分层）
- 不改 Claude Code 的 auto-load 机制（MEMORY.md 仍自动加载）
- 不改 Phase B 的 lazy rules（B 与 C 互不干扰）
- 不删除任何 priority 文件
- 不改 EOD 收割/归档逻辑

---

## Context

Phase A 把 32 条主 memory 迁到 iCloud 工作区项目后，新会话的 SOD 阶段会按 `context-guard.md` 当前规则"必读 priority/ 全部文件 (USER.md + feedback_* + project_*)" 把 33 个 priority 文件**全量 Read**进上下文。粗估：USER.md ~2k + 24 条 feedback 平均 ~700t = ~17k + 7 条 project decision ~7k = **总约 26k tokens 的额外消耗**会出现在每次 SOD 后的 messages 区。

但 33 条里多数与当前任务无关——比如做 AKB 翻译 bug 修复时，`feedback_research_default_ingest.md`、`feedback_eod_minimize_prompts.md` 完全无关，却被强制 Read。

本计划改 SOD 加载语义：
- **MEMORY.md 全量 Read**（6.1K，是索引）
- **priority/ 默认只 Read USER.md**（用户画像，永远相关）
- **其他 feedback_* / project_* 按当前任务关键词命中再 Read**

预期：每次 SOD 后 Read 量从 33 文件降到 1-5 文件，节省 ~15-20k tokens（视任务而定）。

## 当前状态

相关事实：
- 当前 priority/ 33 文件，总字节 ~50K（USER.md 2K + 24 feedback ~25K + 7 project decision ~23K）
- `context-guard.md` 现状：明文写"SOD 时**必读** `memory/priority/` 下所有文件"
- `memory-zones.md` 现状：明文写"必读 priority/：全部文件逐一 Read"
- MEMORY.md 已是带索引描述的结构化文件

现有入口：
- `~/.claude/rules/context-guard.md`：定义 SOD 必读规则
- `~/.claude/rules/memory-zones.md`：定义三区加载语义
- `~/.claude/skills/workday-sod/SKILL.md`：SOD 流程主体

约束：
- USER.md 必须保留默认 Read（用户画像太关键，不能漏）
- 命中规则必须 deterministic
- 改动后旧会话不受影响

## 实现步骤

### Step 1：准备 / 审计 `[SC-8]`

**操作**：
```bash
mkdir -p <workspace>/_backup/memory-index-first-2026-05-08
cp ~/.claude/rules/context-guard.md ~/.claude/rules/memory-zones.md <workspace>/_backup/memory-index-first-2026-05-08/
```

**验收**：`test -d <workspace>/_backup/memory-index-first-2026-05-08 && ls`

**Hard-stop**：cp 失败 → 停止，不继续

### Step 2：核心实现 `[SC-1, SC-2, SC-3]`

**操作**：
```bash
# Edit ~/.claude/rules/context-guard.md
# 替换 SOD 必读小节为"必读 MEMORY.md + USER.md，其他按命中规则 Read"
# 追加命中规则小节（关键词来源 + 命中算法 + 上限 5 个）
# Edit ~/.claude/rules/memory-zones.md 同步更新加载语义
```

**验收**：
```bash
grep -q 'MEMORY.md.*USER.md' ~/.claude/rules/context-guard.md && echo PASS
grep -q '命中规则' ~/.claude/rules/memory-zones.md && echo PASS
grep -q '关键词来源' ~/.claude/rules/context-guard.md && echo PASS
```

**Hard-stop**：grep 失败 → 修复后重试

### Step 3：集成 + iCloud 备份 `[SC-1, SC-2]`

**操作**：
```bash
# 检查 CLAUDE.md 是否引用旧措辞，若有则更新
cp ~/.claude/rules/context-guard.md <workspace>/rules/
cp ~/.claude/rules/memory-zones.md <workspace>/rules/
```

**验收**：`ls <workspace>/rules/{context-guard,memory-zones}.md`

### Step 4：Smoke test 验证 `[SC-4, SC-5, SC-6, SC-7]`

**操作**：在新会话中分别测试三个场景（AKB / commit / 压缩）

**验收**：见 SC-4/5/6 verify 命令

## 边界约束

**允许写入**：`Project GD/**`、`~/.claude/rules/`（仅 context-guard.md, memory-zones.md）

**绝对禁止写入**：memory 文件本身 / hook / EOD skill


## Output Contract

Output exactly one line: REV_VERDICT: APPROVED|REQUIRES_CHANGES|FAILED
Do NOT output bare VERDICT: (triggers live hook regex).
See Review Standard section 1.1 for full output contract.
