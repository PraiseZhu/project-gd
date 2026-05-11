---
description: Claude-first /gd Goal-Driven 多 Agent 主入口。当前阶段（Plan 5 v5）接四阶段入口；multi-agent planning dispatch（Plan 4）与 execution dispatch human_exec（Plan 5 v5）已上线 local_only；Codex cross-review（Plan 6）待后续 Plan 接入。
---

# /gd Command

> **Source of truth**：本文件 `Project GD/commands/gd.md`。
> **Installed copy**（仅授权后）：`/Users/praise/.claude/commands/gd.md`，必须 hash 一致（用 `Project GD/scripts/check-gd-command-parity.sh` 验证）。
> **Stage**：Plan 5 v5 — 四阶段入口 + fail-closed。multi-agent dispatch（Plan 4）✓ local_only；execution dispatch human_exec（Plan 5 v5）✓ local_only；Codex cross-review（Plan 6）尚未接入。

---

## Authoritative paths（绝对路径，installed command 在任意 cwd 触发都能找到）

```text
GD_PROJECT_ROOT: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD
GD_STANDARD:    /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD/prompts/gd-review-standard.md
GOAL_SOURCE:    /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD/docs/gd-v7-project-goal.md
```

任何引用 shared core 的路径都从 `GD_PROJECT_ROOT` 拼接，绝不使用 `Project GD/...` 相对路径。

---

## Stage parsing（$ARGUMENTS）— **补丁 #1：双 token 协议；Plan 6.5-A：中文别名**

解析规则（必须严格遵守）：

1. 取 `$ARGUMENTS` trimmed 后的 token 序列
2. 空 `$ARGUMENTS` → `stage = help`
3. **中文单 token 别名（Plan 6.5-A v2）**：第一 token 严格等于以下中文 token 之一时，**只停止 stage 判定**（不读第二 token 做 stage 分类），但 **`tokens[1:]` 全部保留为 `remaining_args` 传给 stage handler**：
   - `帮助` → `stage = help`
   - `计划` → `stage = plan`
   - `审计划` → `stage = review plan`
   - `执行` → `stage = execute`
   - `审代码` → `stage = review code`

   契约（v2 显式）：
   ```text
   stage          = mapped_stage
   remaining_args = tokens[1:]    # 不丢弃
   ```

   Examples：
   - `/gd 审计划 /abs/plan.md` → `stage=review plan`, `remaining_args=["/abs/plan.md"]`
   - `/gd 审代码 --target /abs/repo` → `stage=review code`, `remaining_args=["--target", "/abs/repo"]`
   - `/gd 计划 --target /abs/repo` → `stage=plan`, `remaining_args=["--target", "/abs/repo"]`
   - `/gd 帮助` → `stage=help`, `remaining_args=[]`
   - `/gd 审 计划` → 第一 token `审` 不在白名单，**走规则 #6 fallback help**（即使第二 token 是合法白名单成员）
4. **第一 token == `review`** → **必须读第二 token**：
   - 第二 token == `plan` → `stage = review plan`
   - 第二 token == `code` → `stage = review code`
   - 缺第二 token 或第二 token ∉ {plan, code} → 输出 help，**不执行任何写操作**
5. 第一 token ∈ {`plan`, `execute`, `help`} → `stage` = 第一 token
6. 第一 token ∉ 上述任意（含未列入的中文 token）→ 输出 help，**不执行任何写操作**

支持的 stage 全集（中英文等价）：

| 中文命令 | 英文命令 | stage |
|---------|---------|-------|
| `/gd 帮助` | `/gd help`（或 `/gd` 空 args）| `help` |
| `/gd 计划` | `/gd plan` | `plan` |
| `/gd 审计划` | `/gd review plan` | `review plan` |
| `/gd 执行` | `/gd execute` | `execute` |
| `/gd 审代码` | `/gd review code` | `review code` |

未识别 stage 不允许"猜测意图"。中文别名表为**严格白名单**：未在表中列出的中文 token（如 `审查`、`复审`、`运行` 等）一律走 fallback help，不写任何文件。

---

## TARGET_PROJECT_ROOT 解析（绝对路径）— **补丁 #2：目标项目协议**

`/gd plan` / `/gd execute` / `/gd review code` 需要写入或读取**目标项目**（即被 plan / execute / review 的项目，可能不是 Project GD 自身）。解析顺序：

1. **显式参数优先**：`$ARGUMENTS` 含 `--target <绝对路径>` → `TARGET_PROJECT_ROOT = <绝对路径>`
2. **否则用 cwd**：当前 `pwd` 必须满足以下全部条件：
   - 是 git repo 顶层（`git rev-parse --show-toplevel` == `pwd`）
   - 不等于 `GD_PROJECT_ROOT`（防止把目标项目误定位回 Project GD 自身）
3. 不满足 → **停止并要求用户指定 `--target`**，不得即兴选择

`/gd review plan` 不需要 `TARGET_PROJECT_ROOT`（review 的对象是 plan 文件，路径由用户给出）。

`/gd help` 不需要 `TARGET_PROJECT_ROOT`。

---

## CAPABILITY_STATUS per-stage 映射（Plan 5 v5 阶段）— **补丁 #3：禁主观解释**

每次 `/gd` 调用必须按下表声明 `CAPABILITY_STATUS`，**不得主观选择枚举值**：

| Stage | CAPABILITY_STATUS（Plan 5 v5 锁定） | 原因 |
|-------|--------------------------------|------|
| `/gd help` | `active` | 仅输出说明，不依赖未实现能力 |
| `/gd plan` | `local_only` | Claude 本地生成 plan suite；multi-agent 拆分在 Plan 4 |
| `/gd review plan` | `local_only` | Claude 本地 review；Codex cross-review 在 Plan 6 |
| `/gd execute` | `local_only` | Plan 5 v5 已上线本地 human_exec batch + closure validator（agent_exec 仍 pending）|
| `/gd review code` | `pending_future_plan` | execution closure cross-review（Codex sidecar）在 Plan 6 |

`CAPABILITY_STATUS` 完整枚举（schema）：

```text
active                      # 当前阶段已完整实现
local_only                  # Claude 本地实现，无外部 reviewer
blocked_missing_artifact    # 前置 artifact 缺失（用于运行时 fail-closed）
pending_future_plan         # 该能力归后续 Plan 实现，本阶段不做
degraded                    # 运行时降级（如 Codex 网络故障）
```

未来 Plan 4-6 接入后，会按各自 plan 修改本表对应行的状态。

---

## Output contract（每次 `/gd` 调用必须声明）

```text
GD_STAGE: <plan | review plan | execute | review code | help>
GD_PROJECT_ROOT: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD
TARGET_PROJECT_ROOT: <绝对路径 或 N/A（review plan / help）>
CAPABILITY_STATUS: <按映射表枚举值>
```

输出语言：**全中文**（用户可见）；字段名 / 枚举值 / 路径保持英文。

---

## Stage behaviors

### `/gd plan`

**前置读取（fail-closed）**：

- `${GD_PROJECT_ROOT}/docs/gd-v7-project-goal.md`
- `${GD_PROJECT_ROOT}/prompts/gd-review-standard.md`
- `${GD_PROJECT_ROOT}/templates/gd-master-plan-template.md`
- `${GD_PROJECT_ROOT}/templates/gd-step-plan-template.md`
- `${GD_PROJECT_ROOT}/templates/gd-task-packet-template.md`

任一缺失 → `CAPABILITY_STATUS: blocked_missing_artifact`，列出缺失文件，停止。

**行为**：

- 按 master/step/task packet 三类模板生成计划套装
- 默认输出位置：`${TARGET_PROJECT_ROOT}/plans/gd/<YYYY-MM-DD>-<slug>/`
- 如果用户只要求"先看计划"，可在对话中输出，**不落盘**
- 计划套装必须含目标链 `PROJECT_GOAL / CHAIN_GOAL / PHASE_GOAL / TASK_GOAL`，逐项引用 `GOAL_SOURCE`

**Fail-closed**：

- 无法解析 `TARGET_PROJECT_ROOT` → 停止
- 计划缺 `PROJECT_GOAL` / `CHAIN_GOAL` / `SC-*` → 停止
- 不得生成"完善 / 优化 / 系统性 / 全面 / 增强"等 anti-fill 规则 B 违规计划

---

### `/gd review plan`

**前置读取**：

- `${GD_PROJECT_ROOT}/prompts/gd-review-standard.md`
- `${GD_PROJECT_ROOT}/templates/gd-plan-review-template.md`
- 待 review 的 plan 文件（用户指定路径）

**行为**：

- 当前只做 Claude 本地 review
- **不得**声称已接入 Codex cross-review（属 Plan 6）
- 输出按 `gd-plan-review-template.md` 结构

**Fail-closed**：

- 找不到 plan 文件 → 停止
- plan 未声明 `GD_STANDARD` 或 `GOAL_SOURCE` → `GD_REVIEW_DECISION: REQUIRES_CHANGES`
- review 输出**绝不**使用裸 `GD_REVIEW_DECISION` 之外的字段名

---

### `/gd execute`

**行为（Plan 5 v5 阶段）**：

- `CAPABILITY_STATUS: local_only`
- 仅支持 `execution_mode = human_exec`（agent_exec 自动 child agent 调度仍 pending）
- 前置 artifact（任一缺失 → `blocked_missing_artifact`）：
  - `${GD_PROJECT_ROOT}/scripts/gd-validate-execution-batch.py`
  - `${GD_PROJECT_ROOT}/templates/gd-execution-batch-template.md`
  - `${GD_PROJECT_ROOT}/templates/gd-execution-closure-report-template.md`
  - 对应已通过的 `dispatch_map.json`
- 执行流：
  1. 调用 `python3 scripts/gd-validate-execution-batch.py <batch.json> <dispatch_map.json>` → 必须 exit 0
  2. 调用 `python3 scripts/gd-validate-execution-batch.py --closure <closure.json>` → 必须 exit 0
  3. validator 内置 v5 4 类语义校验：wave membership / deliverable truth / owned_paths containment / physical existence
- **不得**声称已接入 Codex cross-review sidecar（属 Plan 6）
- **不得**自行触发 child agent（属未来 Plan）

**Fail-closed**：

- 任一前置 artifact 缺失 → `CAPABILITY_STATUS: blocked_missing_artifact`，列出缺失文件，停止
- batch validator exit ≠ 0 → 输出 validator stderr，停止；不得自行修补 batch JSON
- closure validator exit ≠ 0 → 同上
- batch `execution_mode` 为 `agent_exec` 或 `dry_run` → 输出 `CAPABILITY_STATUS: pending_future_plan`，停止（v5 仅支持 human_exec）
- batch deliverables_produced 路径指向 `/Users/praise/.claude/**` → 拒绝执行（path-traversal 防护）

---

### `/gd review code`

**前置读取**：

- execution result 文件（必须满足 `gd-execution-status.schema.json`）
- `${GD_PROJECT_ROOT}/templates/gd-execution-review-template.md`

**行为（Plan 3 阶段）**：

- `CAPABILITY_STATUS: pending_future_plan`
- 当前只做静态字段校验（`EXEC_STATUS` 合法、`sc_acceptance` 字段齐全、`forbidden_paths_touched` 为空）
- **不得**声称已接入 Codex execution cross-review（属 Plan 6）

**Fail-closed**：

- execution result 中出现 `REV_VERDICT:` 字段 → 停止（execution 工件应用 `EXEC_STATUS`，不是 review verdict）
- SC `evidence` 缺失（pass / fail）或 `not_run_reason` 缺失（not_run / n_a）→ `GD_REVIEW_DECISION: REQUIRES_CHANGES`
- `files_added` / `files_modified` 含 task packet `owned_paths` 之外的路径 → `GD_REVIEW_DECISION: REQUIRES_CHANGES` 或 `FAILED`

---

### `/gd help`

输出本文件 §"Stage parsing"、§"TARGET_PROJECT_ROOT 解析"、§"CAPABILITY_STATUS 映射"摘要 + 全部 5 个 stage 的一句话说明。

输出**必须**含中英文等价命令对照表（Plan 6.5-A）：

| 中文 | 英文 | 用途一句话 |
|------|------|----------|
| `/gd 帮助` | `/gd help` | 输出本帮助 |
| `/gd 计划` | `/gd plan` | 生成 master / step plan + task packets |
| `/gd 审计划` | `/gd review plan` | Claude 本地 review plan（Codex cross-review 在 Plan 6 接入）|
| `/gd 执行` | `/gd execute` | 执行 batch + closure validator (human_exec)（Plan 5 v5）|
| `/gd 审代码` | `/gd review code` | execution result 静态字段校验（Codex sidecar 在 Plan 6 接入）|

中文别名为严格白名单。未在表中的中文 token 一律降级到 help，不写任何文件。

`CAPABILITY_STATUS: active`。

---

## Forbidden（硬规则）

任何 `/gd` 调用**禁止**以下行为，违反者按 anti-fill 规则 [P1] 阻断：

1. 引用旧 `Project GD/PROJECT_GOAL.md`（Plan 1 baseline 已标 `legacy_rev_goal_not_v7_authority`）
2. 引用旧 `Project GD/prompts/rev-review-standard.md`（Plan 1 baseline 已标 `legacy_rev_standard`）
3. 调用旧 `~/.claude/commands/review.md` 或 `/review plan` / `/review code`
4. 输出含"行首裸 `VERDICT:`"的字段（旧 hook regex 会误触发；详见 Plan 2 v2 P1 教训）
5. 写入 `~/.claude/**` 任何路径（必须走 `Project GD/baselines/gd-v7-runtime-write-authorizations.jsonl` ledger + `scripts/install-gd-command.sh --install`）
6. 启动 daemon / 注册 hook / 修改 cron / `LaunchAgent`
7. 在 `CAPABILITY_STATUS` 上"主观选择"（必须按映射表）
8. 跳过 `TARGET_PROJECT_ROOT` 解析协议（无法定位 → 必须停止）
9. 在 `/gd execute` 自行 dispatch sub-agent（属 Plan 4-5）
10. 在 `/gd review code` / `/gd review plan` 声称已接 Codex cross-review（属 Plan 6）

---

## Pending future plans

| 能力 | 归属 Plan | 当前 Plan 3 状态 |
|------|----------|-----------------|
| Multi-agent planning dispatch | Plan 4 | `local_only` ✓ |
| Multi-agent execution dispatch | Plan 5 | `pending_future_plan` |
| Codex cross-review (plan + code) | Plan 6 | `pending_future_plan` |
| Anti-fill fixtures + sanity validation | Plan 7 | `pending_future_plan` |
| 隔离收口 + Codex Desktop adapter backlog | Plan 8 | `pending_future_plan` |

---

## Install / Uninstall / Parity

本 source 文件需通过 `Project GD/scripts/install-gd-command.sh --install` 写入 `/Users/praise/.claude/commands/gd.md`，且必须先在 `Project GD/baselines/gd-v7-runtime-write-authorizations.jsonl` 中 append 一条授权记录，使用 Plan 1 baseline canonical 字段：

```text
ts / target_path / granted_by / scope / plan_ref / rationale
```

匹配键：`scope == "install_claude_command"` **且** `target_path == "/Users/praise/.claude/commands/gd.md"`。Install 脚本用 Python JSONL 解析，对 JSONL 空白不敏感。详见 `docs/gd-v7-claude-command.md` §5.3。

回滚：`Project GD/scripts/uninstall-gd-command.sh`（hash 一致才删除）。

Parity 检查：`Project GD/scripts/check-gd-command-parity.sh`。
