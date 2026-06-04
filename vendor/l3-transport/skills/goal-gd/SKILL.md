---
name: goal-gd
description: 整合 /goal 持续驱动 + /gd 执行验证链，生成可直接使用的执行提示词
trigger: goal gd
---

<command-name>goal-gd</command-name>

# Goal GD — /goal + /gd 执行 整合提示词生成器

生成一条提示词，同时具备：
- **`/goal` 的韧性**：跨 turn 持续推进，不达目的不罢休
- **`/gd 执行` 的严谨**：batch validator、closure validator、path audit、fail-closed、SC acceptance 全套验证链

输出提示词供用户直接粘贴使用，本 skill 不执行任何东西。

## 执行步骤

### 1. 定位计划

按优先级查找：
1. **当前会话上下文**中最近通过 ExitPlanMode 或用户批准的计划
2. **`.claude/plans/` 目录**中最近修改的 plan 文件
3. **Project GD `plans/` 目录**中最近的 master-plan
4. **用户在触发时提供的路径参数**（如 `goal gd plans/xxx.md`）

找不到任何计划 → 停止并告知：「未找到计划。请先出计划或提供计划文件路径。」

### 2. 提取字段

| 模板变量 | 来源 |
|---------|------|
| `<PLAN_REF>` | 计划文件绝对路径，或「当前会话 plan mode 输出」 |
| `<TARGET_PROJECT_ROOT>` | 计划目标项目根目录（不一定是 Project GD） |
| `<GD_PROJECT_ROOT>` | Project GD 根目录（固定：`/Users/praise/AI-Agent/Claude/projects/Project GD`） |
| `<TURN_LIMIT>` | Step 总数 × 2，上限 30，默认 14 |
| SC 清单 | 所有 `SC-*` / `PLAN*-SC-*` ID 及标题 |
| `<NON_GOALS>` | 非目标章节的条目列表 |
| `<OWNED_PATHS>` | 计划允许修改的路径范围 |
| `<FORBIDDEN_PATHS>` | 计划禁止修改的路径 |
| `<HARD_STOP>` | 各 Step 的 Hard-stop 条件汇总 |
| `<EXECUTION_MODE>` | `human_exec`（默认）或 `agent_exec`（从计划或用户参数推断） |

### 3. 检查 /gd 执行前置 artifact

读取 `<GD_PROJECT_ROOT>` 下以下文件是否存在，在提示词末尾标注缺失项：
- `scripts/gd-validate-execution-batch.py`
- `templates/gd-execution-batch-template.md`
- `templates/gd-execution-closure-report-template.md`
- `schema/gd-task-packet.schema.json`

agent_exec 模式额外检查：
- `scripts/gd-build-child-prompt.py`
- `scripts/gd-detect-path-changes.py`
- `scripts/gd-validate-execution-dispatch-ledger.py`
- `templates/gd-child-execute-prompt-template.md`

### 4. 填充模板并输出

````
/goal 所有 SC-* 有 PASS 证据且 deliverables 物理存在且 batch/closure validator 均 exit 0 且路径不越界

执行合约（/gd 执行 语义）：
- 权威根目录：<TARGET_PROJECT_ROOT>
- GD 框架根：<GD_PROJECT_ROOT>
- 权威计划：<PLAN_REF>
- 执行模式：<EXECUTION_MODE>

执行流程：
1. 前置检查：验证所有 /gd 执行 artifact 存在（缺失 → blocked_missing_artifact，停止）
2. Batch validation：`python3 ${GD_PROJECT_ROOT}/scripts/gd-validate-execution-batch.py <batch.json> <dispatch_map.json>` → 必须 exit 0
3. 按计划 Step/SC 顺序逐项推进，每条 SC 需要：
   - 具体执行动作（代码修改 / 脚本运行 / 文件创建）
   - verify 命令或路径证据证明 PASS
   - 不可用"已完成/看起来通过"替代证据
4. Closure validation：`python3 ${GD_PROJECT_ROOT}/scripts/gd-validate-execution-batch.py --closure <closure.json>` → 必须 exit 0
5. Path audit：所有变更在 owned_paths 内、forbidden_paths 外

Fail-closed 规则：
- 任一 validator exit ≠ 0 → 输出 stderr，停止，不自行修补
- agent_exec 模式 capability unavailable → 停止，不得降级 human_exec
- deliverables 路径指向 /Users/praise/.claude/** → 拒绝（path-traversal 防护）
- 遇到 hard_stop 条件 → 停止并报 blocker

硬边界：
- NON_GOALS：<NON_GOALS>
- owned_paths：<OWNED_PATHS>
- forbidden_paths：<FORBIDDEN_PATHS>
- hard_stop：<HARD_STOP>
- 不重写计划，不扩大 scope
- 不写 /Users/praise/.claude/**（除非计划明确声明）

输出要求（goal 达成或 turn 用尽时）：
- SC 验收表：逐条 SC-ID → PASS/FAIL + 证据
- validator 命令及结果
- closure 文件路径
- changed files 列表
- 残余风险
- 是否可进入 `/gd review`

SC 清单（共 N 条）：
<逐条列出 SC-ID: 标题>

Stop after <TURN_LIMIT> turns or any hard_stop and report blockers.
````

### 5. 条件规则

- 若计划属于 **Project GD 基础设施计划**，追加硬边界：
  `不 commit；install 前停在 SOURCE_READY_INSTALL_BLOCKED`
- 若计划属于 **AKB2 执行计划**，保留计划声明的 AKB2 forbidden paths
- 若用户指定 `agent_exec`，在执行流程中展开 10 步 agent_exec 协议（capability probe → build child prompt → dispatch with concurrency cap → post-wave path audit → dispatch ledger → planning dispatch log → cross-validate hash → live dispatch smoke → batch + closure validation）

### 6. 输出后行为

- 输出提示词后**停止**，不自动执行
- 告知用户：「已生成 /goal + /gd 执行 整合提示词，覆盖 N 条 SC。粘贴到新会话或当前会话中使用。」
- 不确定的字段标注：「⚠ 以下字段为推断值，请确认：...」
- 前置 artifact 缺失标注：「⚠ 以下 /gd 执行 artifact 缺失，执行时会被 blocked：...」
