---
description: L1 交叉讨论/第二意见（默认）+ 轻量审核（--review）。拿不准时让 Codex 给独立分析。默认讨论模式（RECOMMENDATION），--review 子模式保留原有 verdict 审核。
---

# /review1 命令

> **Source of truth**：`Project GD/commands/review1.md`
> **Installed copy**（仅授权后）：`~/.claude/commands/review1.md`，须 hash 一致
> **GD_ROOT**：`/Users/praise/AI-Agent/Claude/projects/Project GD`（讨论/审核脚本路径基准）
> **链路层级**：L1 — 默认**交叉讨论/第二意见**；`--review` 子模式 = 轻量 ad-hoc 单发 Codex 审查。L2=`/review2`（profile 工作台）；L3=`/gd`（正式全链多 agent）
> **收编自**：`~/.claude/commands/review.md`（原 `/review`），2026-06-05 收编入 GD
> **传输层**：用 `vendor/l3-transport/`（discuss: codex-consult → codex-send-wait --mode discuss；review: review-result-writer → codex-send-wait --mode review-only → codex-watch daemon → codex exec --ephemeral）。运行层完整路径解耦（vendor writer 内部仍含 `~/.claude` 引用）见 `vendor/l3-transport/README.md` 待解耦清单，封装阶段完成。

手动触发 Codex 第二意见或审核。**绝不自动触发** — 只有用户显式输入 `/review1` 或 `/review1 --review` 时才执行。

## 用法

```
/review1               # 默认：交叉讨论/第二意见（无 verdict 闸门）
/review1 --review plan # 审核当前计划（verdict gate）
/review1 --review code # 审核当前代码变更（verdict gate）
```

### 两种模式

| 模式 | 触发 | 完成标记 | 闸门 | 留痕 |
|------|------|---------|------|------|
| **讨论**（默认） | `/review1` | `RECOMMENDATION:` | 无 verdict | 不写 review-baseline |
| **审核** | `/review1 --review` | `VERDICT: APPROVED\|REQUIRES_CHANGES` | 双层 verdict | 写 review-baseline |

讨论模式是「拿不准让 Codex 给第二意见」——Codex 独立推理、可反对、列取舍、给倾向，**不判决**。
审核模式是「让 Codex 出审核判决」——保留原有 verdict 语义，0 回归。

---

## Discuss Capsule 标准（讨论模式）

每次 `/review1`（默认，无 `--review`）必须生成以下 discuss capsule：

```text
QUESTION: <你想问 Codex 的问题，一句话>
CONTEXT: <相关上下文：当前任务、项目状态、已尝试方案>
CLAUDE_LEAN: <可选，Claude 当前的倾向和理由>
OPTIONS: <可选，正在考虑的方案，分号分隔>
PROJECT_ROOT: <项目根目录绝对路径>
```

### 字段说明

- `QUESTION` — 核心问题，Codex 围绕此给出独立分析
- `CONTEXT` — 足够上下文让 Codex 理解场景（当前任务、约束、已做决策）
- `CLAUDE_LEAN` — 可选，Claude 当前倾向 + 理由（Codex 可反对）
- `OPTIONS` — 可选，正在考虑的方案列表
- `PROJECT_ROOT` — 项目根目录，供 CWD 使用

Discuss capsule **不含**：REVIEW_KIND、VERDICT、REVIEW_DOMAIN、SUCCESS_CRITERIA、BASELINE 等审核字段。

### 讨论模式执行流程

#### Step D1: 收集信息

1. 从对话上下文提取用户问题、当前任务、约束
2. 确定 Claude 当前倾向（如有）
3. 列出正在考虑的方案（如有）

#### Step D2: 生成 Discuss Capsule

按上方格式填充。QUESTION 必须明确；CONTEXT 足够让 Codex 独立推理。

#### Step D3: 生成 Capsule 临时文件

将 capsule 写入临时文件（Bash `cat <<'EOF' > /tmp/discuss-capsule-$$.txt`）。

#### Step D4: 发送并获取讨论结果

```bash
bash "<GD_ROOT>/vendor/l3-transport/scripts/codex-consult.sh" \
  --capsule-file /tmp/discuss-capsule-$$.txt \
  --cwd "$PWD"
```

脚本行为：
- 内部调用 `codex-send-wait --mode discuss --timeout 540`
- 返回 Codex 讨论文本（含 `RECOMMENDATION:` 收尾）
- **不写** review-baseline、**不挂** stop hook
- 不可用时输出 `[DISCUSS] DEGRADED`

Codex 返回后 Claude 应：
1. 展示 Codex 的独立分析和建议
2. 结合自己的判断给出最终建议
3. **不自动执行任何操作**，由用户决定

---

## Review Capsule 标准（审核模式，--review）

每次 `/review1` 必须生成以下完整 capsule，所有字段必填：

```text
REVIEW_KIND: plan | code
REVIEW_DOMAIN: ai_infra | app_code | docs_content | other
PLAN_REVIEW_ALIGNMENT: <一行摘要；没有则 N/A>
PLAN_ALIGNMENT_PRESENT: true | false
REVIEW_FOCUS: <3-5 个检查面，分号分隔；没有则 N/A>
REVIEW_FOCUS_SOURCE: plan | baseline | domain_matrix | reviewer_inferred
DOMAIN_OVERRIDE_REASON: <N/A 或为什么没有采用计划声明的 REVIEW_DOMAIN>
REVIEW_MODE: single_pass
REVIEW_ROUND: initial | followup
REVIEW_DELTA_SCOPE: full_matrix | prior_findings_only | direct_downstream | user_expanded
PREVIOUS_FINDINGS: <N/A 或上一轮 finding 摘要>
ONE_REVIEW_ONLY: true
PROJECT_ROOT: <项目根目录绝对路径>
REPO_ROOT: <git repo 根目录，无 git 时填 N/A>
BRANCH: <当前分支，无 git 时填 N/A>
BASELINE: <见下方基线规则>
PROJECT_GOAL: <项目整体目标，按下方来源优先级提取>
PROJECT_GOAL_SOURCE: user_latest | current_plan | project_docs | claude_summary
CURRENT_TASK_GOAL: <本次任务的具体目标>
SUCCESS_CRITERIA: <可验证的成功标准>
IN_SCOPE: <本次审查范围内的内容>
OUT_OF_SCOPE: <明确排除的内容>
USER_ACCEPTED_DECISIONS: <用户已确认的决策，Codex 不得质疑>
CHANGESET_OR_PLAN: <计划全文 或 代码 diff>
VALIDATION_EVIDENCE: <测试结果、lint 输出、运行截图等>
KNOWN_LIMITATIONS: <已知局限，Codex 不得因此阻塞>
BASELINE_CONFIDENCE: high | medium | low
REVIEW_RULES: <引用本文件的审查标准节>
```

### 字段说明

- `REVIEW_DOMAIN` — 选择内部检查面（见 Domain Matrix）
- `REVIEW_MODE` — 始终 `single_pass`：一次抓明显 bug，少 token，不制造多轮
- `REVIEW_ROUND` — `initial` 首次审查；`followup` 修复后复审
- `REVIEW_DELTA_SCOPE` — 收敛控制：初次用 `full_matrix`（内部全量，输出只列 P1/P2）；follow-up 用 `prior_findings_only` 或 `direct_downstream`；`user_expanded` 用户显式扩大
- `PREVIOUS_FINDINGS` — follow-up 时必填上一轮 finding 摘要，initial 时填 `N/A`
- `PLAN_REVIEW_ALIGNMENT` — 计划中 `Review 对齐` 章节的一行摘要（无则 `N/A`）
- `PLAN_ALIGNMENT_PRESENT` — 计划中是否存在 `Review 对齐` 章节
- `REVIEW_FOCUS` — 本次审查的 3-5 个检查面，分号分隔单行（如 `trigger surface; state/baseline`）
- `REVIEW_FOCUS_SOURCE` — focus 来源：`plan`（计划声明）、`baseline`（approved baseline 继承）、`domain_matrix`（Domain Matrix 退回）、`reviewer_inferred`（reviewer 自行推断）
- `DOMAIN_OVERRIDE_REASON` — 未采用计划声明的 `REVIEW_DOMAIN` 时填写原因，否则 `N/A`

---

## Review 对齐读取规则

`/review1 plan` Step 1 **必须**先检查计划中是否存在 `Review 对齐` 章节：

1. 搜索计划全文中的 `## Review 对齐` 或 `# Review 对齐` 标题
2. 存在时提取：
   - `REVIEW_DOMAIN` — 计划声明的审查领域；仅在与 artifact 类型明显不匹配时覆盖，覆盖时填 `DOMAIN_OVERRIDE_REASON`
   - `REVIEW_FOCUS` — 计划声明的检查面列表；压缩到最能发现 P1/P2 的 3-5 项，写成单行分号分隔
   - Domain-specific notes — 作为审查的补充上下文
3. 不存在时：
   - `PLAN_ALIGNMENT_PRESENT=false`
   - `REVIEW_FOCUS_SOURCE=domain_matrix`
   - 按影响程度作为 finding 或 residual risk（executable plan 应包含 Review 对齐）
4. `PLAN_REVIEW_ALIGNMENT` 只写一行摘要，不粘贴整段多行原文

`/review1 code` 优先从 approved plan baseline 的 `last_review_focus` 继承 focus（见下方读取规则）。

---

## Domain Matrix（内部检查面）

`REVIEW_DOMAIN` 决定内部检查覆盖面。输出 `Scope Checked` 只列 3-5 个关键面，不完整展开。

### `ai_infra`

runtime active、mirror backup、trigger surface、generation surface、state/baseline、validation/runtime health、stale/dormant cleanup

### `app_code`

changed files、API/contracts、data/schema、state/concurrency、UI/UX、tests、security/performance、deployment/runtime

### `docs_content`

source material、generated output、links/assets、metadata、publish path、policy/compliance、validation

### `other`

reviewer 必须说明本次选择的 3-5 个检查面。

---

## 输出模板

Codex 按 `REVIEW_KIND` 对应的轻量模板输出。只报 P1/P2 blocker，P3 进 Residual Risk。

### Plan Review 模板

```markdown
# Plan Review Result

VERDICT: APPROVED | REQUIRES_CHANGES
REVIEW_DOMAIN: ai_infra | app_code | docs_content | other
REVIEW_MODE: single_pass
REVIEW_DELTA_SCOPE: full_matrix | prior_findings_only | direct_downstream | user_expanded

## Scope Checked

> 优先使用计划 `Review 对齐` 中声明的 `REVIEW_FOCUS`。无 `Review 对齐` 时退回 Domain Matrix。

| 检查面 | 结论 | 证据（≤30字） |
|--------|------|---------------|
| <REVIEW_FOCUS 的 3-5 项> | pass/fail/n_a | <短语，不放路径> |

## Findings

### Finding 1 [P1|P2] <短标题，不含路径>

问题: <会导致目标失败的计划缺口>
证据: <计划段落/路径/命令>
影响: <按当前计划执行会出现的明显问题>
最小修复: <只补什么，不扩大范围>
验收: <补完后如何确认>

## Residual Risk

<P3 或非阻塞项；没有则写 none>
```

### Code Review 模板

```markdown
# Code Review Result

VERDICT: APPROVED | REQUIRES_CHANGES
REVIEW_DOMAIN: ai_infra | app_code | docs_content | other
REVIEW_MODE: single_pass
REVIEW_DELTA_SCOPE: full_matrix | prior_findings_only | direct_downstream | user_expanded

## Scope Checked

| 检查面 | 结论 | 证据（≤30字） |
|--------|------|---------------|
| <最多 3-5 个关键面> | pass/fail/n_a | <短语，不放路径> |

## Findings

### Finding 1 [P1|P2] <短标题，不含路径>

问题: <当前代码的明显 bug>
证据: <file>:<line> — <命令输出/隔离复现>
影响: <会导致什么 active path 失败或验收不可信>
最小修复: <只改哪些文件/函数/配置>
验收: <可执行命令或隔离用例>

## Residual Risk

<P3 或非阻塞项；没有则写 none>
```

---

## PROJECT_GOAL 来源优先级

按以下顺序提取 PROJECT_GOAL，使用第一个可用的来源：

1. **user_latest** — 用户在当前对话中最新明确的目标描述
2. **current_plan** — 当前 plan 文件或当前任务说明中的目标
3. **project_docs** — CLAUDE.md / README / 项目文档中的项目定位
4. **claude_summary** — Claude 根据上下文生成的目标摘要（最弱来源）

capsule 中必须同时填写 `PROJECT_GOAL_SOURCE` 标明实际使用的来源。

---

## BASELINE 规则

### `/review1 plan`

BASELINE 包含：
- 用户最新目标描述
- 当前计划全文
- 已确认的约束和决策
- 当前 repo HEAD（`git rev-parse HEAD`）
- 当前 dirty 状态摘要（`git status --short`）

### `/review1 code`

BASELINE 优先级：
1. **有前序 plan review 记录** → 使用 plan review 时记录的 HEAD 和 dirty 摘要作为实现基线，标记 `BASELINE_CONFIDENCE: high`
2. **无前序 plan review** → 使用当前 HEAD，标记 `BASELINE_CONFIDENCE: low`

### Dirty Worktree 分类

对 dirty worktree **必须**区分以下四类，在 BASELINE 中分别列出：
- **本轮改动**：本次任务产生的文件变更
- **执行前已有改动**：进入任务前已存在的 unstaged/staged 变更
- **未跟踪文件**：untracked files
- **生成/缓存文件**：`__pycache__`、`node_modules`、`.pyc`、build artifacts 等

### 无 Git 项目

用以下信息构建弱基线，标记 `BASELINE_CONFIDENCE: low`：
- cwd 绝对路径
- 文件清单（`find . -maxdepth 3 -type f`，排除常见缓存目录）
- 关键文件 mtime 摘要
- Claude 描述的改动范围

---

## Plan Review Baseline 记录

`/review1 plan` 成功生成 capsule 时，**必须**同时写入 baseline 记录，供后续 `/review1 code` 引用。

### Baseline Key 计算

baseline key 决定存储路径和读取路径，**`/review1 plan` 和 `/review1 code` 必须使用同一套计算逻辑**：

- **git repo 内**：使用 `git rev-parse --show-toplevel` 获取 repo root 绝对路径，取 MD5 前 12 位
  - `baseline_key_source: repo_root`
  - 无论从 repo root 还是子目录触发，都读写同一份 baseline
- **非 git 项目**：使用 cwd 绝对路径的 MD5 前 12 位
  - `baseline_key_source: cwd`

### 存储路径

```
~/.claude/review-baselines/<baseline_key>/latest-plan-baseline.json
```

### 记录格式

```json
{
  "baseline_key": "<md5-12>",
  "baseline_key_source": "repo_root | cwd",
  "trigger_cwd": "/absolute/path/where/review1/was/triggered",
  "repo_root": "/absolute/path/to/repo",
  "branch": "main",
  "head": "abc1234def5678",
  "dirty_status": "M src/foo.py\n?? new_file.txt",
  "in_scope": "...",
  "out_of_scope": "...",
  "user_accepted_decisions": "...",
  "success_criteria": "...",
  "known_limitations": "...",
  "timestamp": "2026-04-26T12:00:00Z",
  "capsule_path": "~/.claude/review-baselines/<baseline_key>/capsule-<timestamp>.txt",
  "review_status": "pending",
  "verdict": "N/A",
  "reviewed_at": null,
  "result_path": null,
  "watch_result_path": null,
  "last_review_kind": "plan",
  "last_review_domain": "app_code",
  "last_result_path": null,
  "last_findings_summary": "N/A",
  "last_review_round": "initial",
  "last_review_delta_scope": "full_matrix",
  "last_next_review_scope": "N/A",
  "last_direct_downstream": "N/A",
  "plan_review_alignment": "一行摘要或 N/A",
  "plan_review_alignment_present": true,
  "last_review_focus": ["trigger surface", "state/baseline"],
  "last_review_focus_source": "plan",
  "last_domain_override_reason": "N/A"
}
```

`review_status` 取值：
- `pending` — capsule 已生成，Codex 尚未返回结果
- `approved` — Codex 返回 `VERDICT: APPROVED`
- `requires_changes` — Codex 返回 `VERDICT: REQUIRES_CHANGES`
- `degraded_unreviewed` — watch 不可用或 TEMPORARY_DEGRADED_MODE
- `failed` — `codex-send-wait` 执行失败
- `malformed` — Codex 返回结果缺少必需结构字段

### `/review1 code` 读取规则

0. **读取最近 执行完成（新）**：
   - 搜索当前对话上下文中最近一条包含 `## 执行完成` 的 assistant 消息
   - 存在时提取并写入 capsule `VALIDATION_EVIDENCE`：
     - `成功标准验收` 表格（逐项验收状态）
     - `执行命令` 表格（执行的命令和结果）
     - `运行时/持久状态` 表格
     - `未执行/延期` 表格（未执行项）
   - 提取 `REVIEW_DOMAIN` / `REVIEW_FOCUS` 覆盖值（如果更具体则优先使用）
   - 执行完成 存在 → 在 Scope Checked 添加 `execution handoff: present`
   - 执行完成 缺失但本轮有 mutation → `BASELINE_CONFIDENCE` 降为 `low`，Scope Checked 添加 `execution handoff: MISSING`

1. 计算当前 baseline key（git repo 内用 repo_root hash，非 git 用 cwd hash）
2. 读取 `~/.claude/review-baselines/<baseline_key>/latest-plan-baseline.json`
3. 文件不存在 → 跳到步骤 7（无 approved baseline 退路）
4. 检查 `review_status`：
   - `approved` + `verdict` = `APPROVED` → 进入步骤 5
   - `requires_changes` → `BASELINE_CONFIDENCE: medium`，BASELINE 中注明 "plan review 返回 REQUIRES_CHANGES，基线未被审批通过"，跳到步骤 7
   - `pending` / `degraded_unreviewed` / `failed` / `malformed` → `BASELINE_CONFIDENCE: low`，BASELINE 中注明具体状态，跳到步骤 7
5. 比对当前状态（仅 `review_status = approved` 才可能达到 high）：
   - `repo_root` 匹配 + `branch` 匹配 → `BASELINE_CONFIDENCE: high`
   - `repo_root` 匹配但 `branch` 不同 → `BASELINE_CONFIDENCE: medium`，说明 "plan review 在不同分支"
   - `repo_root` 不匹配 → `BASELINE_CONFIDENCE: low`，说明 "repo root 不匹配"
   - 使用 `baseline.head` 作为 diff 基线（见下方 Diff 生成规则）
6. **继承 review focus**：
   - baseline 有 `last_review_focus`（非空数组）→ capsule `REVIEW_FOCUS` 使用继承值，`REVIEW_FOCUS_SOURCE=baseline`
   - baseline 有 `last_review_domain` → capsule `REVIEW_DOMAIN` 使用继承值（明显不匹配时可覆盖，填 `DOMAIN_OVERRIDE_REASON`）
   - baseline 无 `last_review_focus` 或为空数组 → 退回 Domain Matrix，`REVIEW_FOCUS_SOURCE=domain_matrix`
7. **无 approved baseline 退路**：使用当前 HEAD + dirty diff，`BASELINE_CONFIDENCE: low`，BASELINE 中注明 "无 approved plan baseline"，`REVIEW_FOCUS_SOURCE=domain_matrix`

### `/review1 code` Diff 生成规则

**有 approved baseline 时**（步骤 5 匹配成功）：

使用 `baseline.head` 作为 diff 起点，而非当前 HEAD：

```bash
git diff <baseline.head> -- .          # 已提交 + 未提交的全量变更（首选）
git diff <baseline.head>...HEAD       # 仅已提交变更（不含 working tree）
```

BASELINE 中写明：
- `baseline_head`: `<baseline.head>`
- `current_head`: `<git rev-parse HEAD>`
- `head_relation`: `same` | `descendant` | `diverged` | `unknown`

head_relation 判定：
- `same` — `baseline.head == current HEAD`
- `descendant` — `git merge-base --is-ancestor <baseline.head> HEAD` 返回 0
- `diverged` — 非祖先关系（有分叉）
- `unknown` — 无法判定（baseline.head 不在本地历史中）

head_relation 对 confidence 的影响：
- `same` 或 `descendant` → 不降级
- `diverged` → `BASELINE_CONFIDENCE` 降为 `medium`，说明 "HEAD 与 baseline.head 存在分叉"
- `unknown` → `BASELINE_CONFIDENCE` 降为 `low`，说明 "baseline.head 不在本地历史中"

**无 approved baseline 时**（步骤 6）：

退回 dirty diff：
```bash
git diff HEAD
git diff --cached
```

### 写入时机

- `/review1 plan` Step 2 生成 capsule **之后**立即写入（`review_status: pending`）
- 同一 baseline key 的新 plan review 覆盖旧记录（latest 语义）
- capsule 原文同时保存到 `capsule-<timestamp>.txt`（调试用）
- Step 4 收到 Codex 结果后更新 `review_status`/`verdict`/`reviewed_at`/`result_path` 及扩展 state 字段

---

## 审查标准（REVIEW_RULES）

Codex 只能返回以下两种 verdict：

```text
VERDICT: APPROVED
VERDICT: REQUIRES_CHANGES
```

### `REQUIRES_CHANGES` 仅允许用于（Blocker 门槛）

- active path 会失败
- 用户目标未完成
- baseline/state/mirror 会影响后续运行
- 生成链路会继续产出错误结果
- 安全、数据、不可恢复风险
- 核心验证缺失到无法判断成功

### 不得阻塞

- 风格偏好、架构洁癖
- dormant code
- 不影响运行的 stale docs
- 非 active path 清理
- 没有失败证据的潜在优化
- 模板继续细化建议，除非会放过明显 malformed 输出
- 已列入 `OUT_OF_SCOPE`、`USER_ACCEPTED_DECISIONS`、`KNOWN_LIMITATIONS` 的问题
- 需要二次调研但没有明确失败证据的问题

### 禁止行为

- Codex **不得**输出 `REPLACED`
- Codex **不得**重写计划
- Codex **不得**要求自动二审
- 修复后是否再次 `/review1` **只由用户决定**
- Codex 禁止泛泛建议（"建议考虑..."、"可以优化..."）
- 非阻塞建议只能放入 Residual Risk

---

## Follow-up 窄口逃生门

Follow-up 默认不重新 full matrix，只检查：

1. 上一轮 blocker 是否修复
2. 上一轮 blocker 的 direct downstream
3. **逃生门**：本轮 diff 新引入的明显 P1/P2 bug

### 允许新增 finding 仅当

- `new_bug_from_current_diff: true`
- 且属于 Blocker 门槛之一

新增 finding 必须在证据或影响中说明：
- `changed_in_this_round`: <本轮 diff/文件/行号>
- `why_not_scope_creep`: <为什么这是本轮新引入 bug，不是重新全局扫描>

### 禁止新增

- 与本轮 diff 无关的历史问题
- 新的全局矩阵扫描项
- P3 清理项
- 风格、架构洁癖、模板继续细化建议

### 收敛上限

- 同一 root cause 最多阻塞 2 轮
- 第 2 轮后仍存在的问题只有满足 blocker 门槛（active path 失败、数据/安全风险、核心验证失败）的 P1/P2 可继续阻塞
- 旧 finding 不重复贴；被后续 finding 覆盖时只在 Residual Risk 一句话说明

---

## 执行流程

### 模式分发

`/review1` 第一步：判断用户意图。

- **无 `--review` 标志** → 走**讨论模式**（Step D1-D4），见上方「Discuss Capsule 标准」
- **有 `--review plan` 或 `--review code`** → 走**审核模式**（Step 1-4），见下方

### 审核模式 Step 1: 收集信息

根据 `REVIEW_KIND` 收集所需数据：

**plan review:**
1. 读取当前 plan 文件全文
2. **读取计划中的 `Review 对齐`**（见 Review 对齐读取规则），提取 `REVIEW_DOMAIN`、`REVIEW_FOCUS`、domain-specific notes
3. 获取 git HEAD + dirty 状态（无 git 时用弱基线）
4. 从对话上下文提取用户目标、约束、已确认决策
5. 确定 `REVIEW_DOMAIN`（优先使用 Review 对齐声明，其次根据项目类型）
6. 确定 `REVIEW_ROUND`（是否有前序 plan review）
7. 如为 followup，读取上一轮 findings 填入 `PREVIOUS_FINDINGS`

**code review:**
1. 计算 baseline key，按读取规则查找 approved plan baseline
2. **继承 review focus**（见 `/review1 code` 读取规则步骤 6）：baseline 有 `last_review_focus` 时继承，否则退回 Domain Matrix
3. 按 Diff 生成规则生成 diff：
   - 有 approved baseline → `git diff <baseline.head> -- .`
   - 无 approved baseline → `git diff HEAD` + `git diff --cached`
4. 列出 changed files
5. 列出 untracked files（`git ls-files --others --exclude-standard`），对 in-scope 的 untracked 文件生成伪 diff：`git diff --no-index /dev/null <file>`。二进制或 >500 行的文件标记为 `binary_or_large_untracked`，写明未附全文原因，只允许在 `OUT_OF_SCOPE` 或 `GENERATED/CACHE` 中排除
6. 收集测试结果、lint 输出等验证证据
7. 对 dirty worktree 做四分类
8. 确定 `REVIEW_DOMAIN`（优先使用 baseline 继承值，其次根据变更内容）
9. 确定 `REVIEW_ROUND` 和 `REVIEW_DELTA_SCOPE`
10. 如为 followup，读取上一轮 findings 填入 `PREVIOUS_FINDINGS`

### 审核模式 Step 2: 生成 Capsule

按上方标准格式填充所有字段。不可省略任何字段。

### 审核模式 Step 3: 生成 Capsule 临时文件

将 capsule 写入临时文件（Bash `cat <<'EOF' > /tmp/review-capsule-$$.txt`）。
**禁止使用 Write 工具写 capsule 或 result** — 避免触发 terminal diff preview。

### 审核模式 Step 4: 发送 + 保存结果（单次 Bash 调用）

**必须使用 `review-result-writer.sh` 脚本**，一次性完成 send、result 保存、baseline 更新。
**禁止**用 Write 工具写 `~/.claude/review-baselines/` 下的任何文件。

> ⛔ **Writer 强制路由（MANDATORY）**：`/review1` 触发后，结果**只能**由 `review-result-writer.sh` 输出。
> 禁止以任何形式绕过脚本直接输出 verdict，包括但不限于：
> - 自然语言描述："Watch 显示 STOPPED"、"Codex 返回了结果"、"看起来已经通过了"
> - 手动解读 codex-send-wait 输出并直接宣布 APPROVED/REQUIRES_CHANGES
> - 以 Read 工具读取 result 文件后自行总结
>
> 违反此规则由 `review-writer-required-gate.js`（Stop hook）检测并阻断。

```bash
# 收编后传输层位于 GD vendor。<GD_ROOT> = Project GD 根（封装后为插件安装根）。
# 运行层完整解耦（vendor writer 内部对 ~/.claude/handoff、~/.claude/review-baselines 的引用）
# 见 vendor/l3-transport/README.md 待解耦清单，封装阶段完成。
bash "<GD_ROOT>/vendor/l3-transport/scripts/review-result-writer.sh" \
  --capsule-file /tmp/review-capsule-$$.txt \
  --baseline-key "<baseline_key>" \
  --review-kind "<plan|code>" \
  --cwd "$PWD" \
  --no-stop-marker
```

脚本行为：
- 内部调用 `codex-send-wait --mode review-only`
- 结果保存到 `~/.claude/review-baselines/<baseline_key>/result-<timestamp>.md`（无 Write 工具参与）
- baseline JSON 自动更新（含扩展 state 字段）
- stdout 只输出 verdict 摘要 + 前 3 个 findings 关键字段 + 完整 result 文件路径
- 结构校验：缺少必需字段的 result 标记为 `malformed`

降级处理（codex-send-wait 不可用）：
- 脚本输出 `[REVIEW] ⚠️ DEGRADED — watch unavailable`
- capsule 保存到 baseline 目录供手动处理
- **不输出 APPROVED**，**不假装 review 完成**

无论哪种结果，**不自动执行任何操作**，由用户决定下一步。
- **review-stop hook 护栏**：PostToolUse hook 检测到 VERDICT 后写入 marker
- PreToolUse hook 阻断后续 Edit/Write/Bash 修改，直到用户明确说"执行修复"

---

## 硬停止规则

Review 结束后（无论 APPROVED 还是 REQUIRES_CHANGES），Claude 必须：

1. 输出 verdict 摘要（由 review-result-writer.sh 脚本提供的短输出）
2. **立即停住**，不继续执行任何 Edit/Write/Bash 修改
3. 用户追问、要求解释、贴反馈 → 允许 Read 和只读 Bash，**不解除 guard**
4. 只有用户明确说"执行修复"/"fix it"/"apply changes"等修复意图时，guard 才解除

`fix_applied: true` 只能在用户另起一轮明确要求修复并完成后写入。

### 三层保障

1. **review-stop-marker.js** (PostToolUse) — 检测 VERDICT，写 marker
2. **review-stop-guard.js** (PreToolUse) — marker 存在时阻断所有写操作（含 Write 到 review-baselines）
3. **review-stop-clear.js** (UserPromptSubmit) — 只在用户 prompt 含修复意图关键词时才清 marker

### 禁止使用 Write 工具的文件

Review 流程中，以下路径**禁止**通过 Write/Edit 工具操作，只能通过 review-result-writer.sh：
- `~/.claude/review-baselines/**/*.md` (result 文件)
- `~/.claude/review-baselines/**/*.json` (baseline 文件)
- `~/.claude/review-baselines/**/*.txt` (capsule 文件)

---

## 与其他命令的关系

- `/plan` 不再自动触发 review。plan 完成后用户可选择 `/review1 plan`
- 代码实现完成后用户可选择 `/review1 code`
- 进入 plan 模式不触发 review
- 代码执行结束不触发 review
