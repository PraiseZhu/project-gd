# Task Packet: t4-antifill-hard-gate

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t4-antifill-hard-gate
agent_role: implementer
parent_step: T4
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T15:30:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表（ref GOAL_SOURCE）
CHAIN_GOAL:   让 L2(/review2) 成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交（ref GOAL_SOURCE）
PHASE_GOAL:   为 L2 spec T1-T9 各产出可被 /gd execute 消费的自包含 task packet；本 packet 实现 spec §3 的 T4（ref master-plan.md SC-4）
TASK_GOAL:    强化 scripts/gd-validate-review2-plan-target.py，在现有 SC-ID / REVIEW_DOMAIN-FOCUS / WHERE-WHAT-WHY-VERIFY / 旧 rev 标记校验之上新增 anti-fill 硬门——每条成功标准必须含可执行 verify（命令/路径/断言/测试）且 expect 不得为泛词黑名单（通过|正确|完成|works|pass|ok|成功 无具体串）；违反则 exit≠0 + 打印 PLAN_ANTIFILL_FAIL，作为 /review2 plan 强制第一步。并按 D5 新建 plan mode Stop hook source scripts/plan-mode-antifill-stop-hook.js，让不走 /review2 的普通 plan mode 产出的烂计划也被拦——hook 仅作为 source 交付，实际安装到 live 属 T9 deploy + ledger 授权，本 packet 不安装、不注册、不激活。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t5-split-commands-triage   # T4 设为 /review2 plan 强制第一步，需 T5 拆出 plan 子命令入口先存在（spec §3 T4 "设为 /review2 plan 强制第一步" + master-plan §5 T4 blocked_by: T5）
can_parallel_with:
  - t3                          # T3 改 plan 模板 source，与本任务校验器/hook 文件无写入交集
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md   # 实现权威源：§1 F5（plan 模板与 goal 提取错配）、§3 T4 段（anti-fill 硬门 + D5 Stop hook）、§6 决策表 D5/D6、§5 边界（动 live 需授权）
  - scripts/gd-validate-review2-plan-target.py            # 被改文件：现有 4 段校验（capsule guard / SC-ID / REVIEW_DOMAIN-FOCUS / WHERE-WHAT-WHY-VERIFY + 旧 rev 标记）需在此之上叠加 anti-fill 硬门
  - scripts/lib/sc_extraction.py                          # 现有依赖：extract_sc_ids，anti-fill 校验需按 SC 维度遍历，复用其 SC 抽取（不重写正则）
```

> 注：若 `scripts/lib/sc_extraction.py` 当前只导出 `extract_sc_ids`（仅返回 ID 列表，不返回每条 SC 的正文块），子 agent 可在 `gd-validate-review2-plan-target.py` 内**本地**实现"按 SC 块切分 + 提取该块内 verify/expect"的解析，不修改 `lib/sc_extraction.py`（它不在 owned_paths）。

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-validate-review2-plan-target.py            # 强化现有 validator（在仓库）
  - scripts/plan-mode-antifill-stop-hook.js               # D5 新建 Stop hook source（仅 source；动 live 经 T9 deploy + ledger 授权，本 packet 不安装）
forbidden_paths:
  - "/Users/praise/.claude/**"
  - 旧 /rev artifacts
  - scripts/lib/sc_extraction.py                          # 只读依赖，不改
  - prompts/gd-review-standard.md                         # T1 owned
  - scripts/gd-codex-bridge-review.py                     # T1/T6 owned
  - commands/review2.md                                   # T5/T7/T8 owned
  - scripts/gd-detect-review2-code-target.py              # T5 owned
  - scripts/gd-review2-preflight.sh                       # T2 owned
  - scripts/gd-review-router.py                           # T7 owned
  - scripts/gd-review-controller.py                       # T7 owned（新增）
  - schema/gd-baseline-findings.schema.json               # T7 owned（新增）
  - scripts/gd-review2-package-deliverable.sh             # T8 owned
  - templates/plan-mode-template.md                       # T3 owned（新增）
  - .deploy-manifest.jsonl                                # T9 owned
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（`scripts/gd-validate-review2-plan-target.py`、`scripts/plan-mode-antifill-stop-hook.js`）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取以下三类，超出此范围视为越界：
  1. `required_context` 列出的文件
  2. 已完成的 `blocked_by` task 的 deliverables（本任务 `blocked_by: [t5-split-commands-triage]`，可读 T5 已完成的交付物以确认 `/review2 plan` 入口形态，但 **不得写入** T5 的 owned_paths）
  3. 公共只读资源（GOAL_SOURCE、GD_STANDARD、master-plan.md、lock files、schema）
- T3 可并行（`can_parallel_with: [t3]`），但 T3 的 `owned_paths`（plan-mode 模板）禁止读写。

---

## 5. 成功标准（SC）

> 本 packet 对应 master-plan SC-4。下列 SC-4.1 ~ SC-4.4 是 SC-4 的可验证子条件，全部 pass 才算 SC-4 达成。
> anti-fill 自我约束：每条 SC 的 expect 都是**字面输出串或具体 exit 行为**，不含泛词黑名单（通过|正确|完成|works|pass|ok|成功）作为唯一内容——本 packet 的 verify 即 T4 要强制的标准的自我示范。

- [ ] SC-4.1（per-SC verify 缺失即拦）：`gd-validate-review2-plan-target.py` 新增检查——计划中每个 SC-ID 对应的成功标准块必须含可执行 `verify`（识别 `verify (method: command|path|assertion|test): ...` 或等价 `verify:` 行，含非空命令/路径/断言/测试内容）。任一 SC 缺 verify → 收集为 anti-fill 错误。验收命令见 §7 verify SC-4.1。
- [ ] SC-4.2（expect 泛词黑名单即拦）：`gd-validate-review2-plan-target.py` 新增检查——每个 SC 块的 `expect:` 字段值若**整体**落在泛词黑名单（去除标点/空白后等于 `通过` / `正确` / `完成` / `works` / `pass` / `ok` / `成功` 之一，或仅由这些词拼接且无任何具体输出串/exit code/数值/路径/字面 token）→ 收集为 anti-fill 错误。含具体串（如 `expect: "PLAN_ANTIFILL_FAIL"`、`expect: "exit 0"`、`expect: ">=1"`）则放行。验收命令见 §7 verify SC-4.2。
- [ ] SC-4.3（失败码与信号正确）：任一 SC-4.1/SC-4.2 检查不通过 → 脚本 **exit≠0**（保持现有非零退出语义）且 stdout 打印 `PLAN_ANTIFILL_FAIL`（与现有 `PLAN_TEMPLATE_STATUS: fail` / `PLAN_ERROR:` 并存，新增独立信号串，便于 /review2 plan 编排区分"结构缺失"与"anti-fill 填表"）；全部 SC 合规 → 现有 pass 路径不变（exit 0 + `PLAN_TEMPLATE_STATUS: pass`），不误伤合规计划。验收命令见 §7 verify SC-4.3。
- [ ] SC-4.4（Stop hook source 交付，不激活）：新建 `scripts/plan-mode-antifill-stop-hook.js`——一个 plan mode Stop hook 的 source 文件，逻辑上读取 plan mode 产出的计划文本（从 hook stdin / 约定输入），对其跑与 SC-4.1/SC-4.2 同语义的 anti-fill 判定（每条 SC 须有 verify + expect 非纯泛词），不合规则以非零状态 / 拦截信号阻止 Stop（拦下普通 plan mode 的烂计划）。文件须语法可解析（`node --check`），头部注释须显式声明"source-only；安装到 live 由 T9 deploy + ledger 授权，本文件本身不注册、不激活、不写 ~/.claude"。验收命令见 §7 verify SC-4.4。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-validate-review2-plan-target.py
    kind: file
    must_exist: true
    description: 在现有 4 段校验之上新增 anti-fill 硬门——按 SC 维度校验 verify 存在性 + expect 泛词黑名单；违反则 exit≠0 + 打印 PLAN_ANTIFILL_FAIL
  - path: scripts/plan-mode-antifill-stop-hook.js
    kind: file
    must_exist: true
    description: D5 plan mode Stop hook source（source-only，不安装/不注册/不写 live）——对普通 plan mode 计划跑同语义 anti-fill 判定，不合规则阻止 Stop
  - path: handoff_output（见 §8）
    kind: report
    must_exist: true
    description: 子 agent 执行结果，含每条 SC 的 verify 命令真实输出（含 5 类正/负 fixture 的 exit code 与 stdout）
```

---

## 7. 验证（Anti-fill 硬约束）

> 每条 SC 绑定可执行命令 / 路径 / 断言 / 测试。执行后必须在 handoff_output 贴真实输出。
> 下列命令均在工作目录 `/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity` 下运行。
> fixture 约定：子 agent 自行在临时目录（`mktemp` / `/tmp` 下，**不写入 owned_paths 外的版本管理路径**）构造正/负 fixture 计划文件，至少覆盖 5 类：
>   (n1) SC 缺 verify 行；(n2) expect 为纯泛词"通过"；(n3) expect 为纯泛词"pass"；
>   (p1) SC 含具体 verify + `expect: "PLAN_ANTIFILL_FAIL"`；(p2) SC 含 `verify (method: command): ...` + `expect: "exit 0"`。
> handoff 必须贴这 5 类 fixture 的真实 exit code 与 stdout（含 PLAN_ANTIFILL_FAIL 出现/不出现）。

```yaml
verify:
  - sc_ref: SC-4.1
    method: assertion
    cmd: "grep -nE 'verify|expect' scripts/gd-validate-review2-plan-target.py | grep -iE 'antifill|anti_fill|PLAN_ANTIFILL'"
    expect: ">=1 行命中——证明脚本内已加入按 SC 维度的 verify/expect anti-fill 校验逻辑（exit 0）"
  - sc_ref: SC-4.1
    method: test
    cmd: "f=$(mktemp /tmp/gd-t4-n1-XXXX.md); printf 'REVIEW_DOMAIN: ai_infra\\nREVIEW_FOCUS: x\\n## SC\\n- SC-1: do thing\\nWHERE: a\\nWHAT: b\\nWHY: c\\nVERIFY: d\\n' > \"$f\"; python3 scripts/gd-validate-review2-plan-target.py --target \"$f\"; echo \"EXIT=$?\"; rm -f \"$f\""
    expect: "EXIT 非 0（SC-1 无 per-SC verify/expect → anti-fill 拦截）；stdout 含 PLAN_ANTIFILL_FAIL。注意此 fixture 结构字段齐全，必须由 anti-fill 门而非结构门拦下"
  - sc_ref: SC-4.2
    method: test
    cmd: "f=$(mktemp /tmp/gd-t4-n2-XXXX.md); printf 'REVIEW_DOMAIN: ai_infra\\nREVIEW_FOCUS: x\\n## SC\\n- SC-1: do thing\\n  verify (method: command): run it\\n  expect: 通过\\nWHERE: a\\nWHAT: b\\nWHY: c\\nVERIFY: d\\n' > \"$f\"; python3 scripts/gd-validate-review2-plan-target.py --target \"$f\"; echo \"EXIT=$?\"; rm -f \"$f\""
    expect: "EXIT 非 0；stdout 含 PLAN_ANTIFILL_FAIL（expect 为纯泛词'通过'，无具体串 → 拦截）"
  - sc_ref: SC-4.2
    method: test
    cmd: "f=$(mktemp /tmp/gd-t4-p1-XXXX.md); printf 'REVIEW_DOMAIN: ai_infra\\nREVIEW_FOCUS: x\\n## SC\\n- SC-1: do thing\\n  verify (method: command): python3 scripts/gd-validate-review2-plan-target.py --target p.md\\n  expect: \"PLAN_ANTIFILL_FAIL\"\\nWHERE: a\\nWHAT: b\\nWHY: c\\nVERIFY: d\\n' > \"$f\"; python3 scripts/gd-validate-review2-plan-target.py --target \"$f\"; echo \"EXIT=$?\"; rm -f \"$f\""
    expect: "EXIT 0；stdout 含 PLAN_TEMPLATE_STATUS: pass；stdout 不含 PLAN_ANTIFILL_FAIL（expect 含具体输出串 → 放行，不误伤合规计划）"
  - sc_ref: SC-4.3
    method: assertion
    cmd: "grep -c 'PLAN_ANTIFILL_FAIL' scripts/gd-validate-review2-plan-target.py"
    expect: ">=1——PLAN_ANTIFILL_FAIL 作为独立信号串存在于脚本（与 PLAN_TEMPLATE_STATUS: fail / PLAN_ERROR 并存）"
  - sc_ref: SC-4.3
    method: test
    cmd: "python3 -c \"import ast; ast.parse(open('scripts/gd-validate-review2-plan-target.py').read()); print('SYNTAX_OK')\""
    expect: "SYNTAX_OK（强化后语法可解析，不引入 SyntaxError）"
  - sc_ref: SC-4.4
    method: command
    cmd: "test -f scripts/plan-mode-antifill-stop-hook.js && echo HOOK_SRC_EXISTS"
    expect: "HOOK_SRC_EXISTS"
  - sc_ref: SC-4.4
    method: test
    cmd: "node --check scripts/plan-mode-antifill-stop-hook.js && echo NODE_SYNTAX_OK"
    expect: "NODE_SYNTAX_OK（hook source 语法可被 node 解析）"
  - sc_ref: SC-4.4
    method: assertion
    cmd: "grep -niE 'source-only|不注册|不激活|ledger|T9 deploy|do not install' scripts/plan-mode-antifill-stop-hook.js"
    expect: ">=1 行命中——hook 头部显式声明 source-only / 不写 live / 安装经 T9 deploy + ledger（守 spec §5 边界，本 packet 不激活）"
```

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t4-antifill-hard-gate-result.md
  status_field: <见 gd-execution-status.schema.json：completed | blocked | partial>
  summary: <一句话结论，例如：validator 新增 per-SC verify 存在性 + expect 泛词黑名单 anti-fill 门（违反 exit≠0 + PLAN_ANTIFILL_FAIL），新建 plan mode Stop hook source（source-only 不激活），5 类正负 fixture 真实输出已贴>
  blockers: <未完成的依赖或外部阻塞；T5 入口若未就绪则记为 blocked；无则写 none>
```

handoff 必须贴 §7 全部 9 条 verify 命令的真实输出（命令 + stdout/exit code），并单列 5 类正/负 fixture（n1/n2/n3/p1/p2）的 exit code 与 PLAN_ANTIFILL_FAIL 出现情况，不得只写"已验证 / 通过"。

---

## 9. 范围禁令

- 禁止 **写入** §4 `owned_paths` 之外任何路径（尤其 T1/T2/T3/T5/T6/T7/T8/T9 的 owned，以及 `scripts/lib/sc_extraction.py`）。
- 禁止 **读取** 其他 task 的 `owned_paths`，除非该 task 已完成且其 deliverables 列入本 packet 的 `required_context`（本任务 `blocked_by: [t5-split-commands-triage]`：可读 T5 已完成交付物确认 `/review2 plan` 入口形态，但不得写入 T5 owned_paths）。
- 禁止访问 `/Users/praise/.claude/**`。
- **禁止启动 daemon、注册 hook、修改 cron**：`scripts/plan-mode-antifill-stop-hook.js` 仅作为 **source 文件** 交付——不得 `cp`/symlink 到 `~/.claude/hooks/`、不得写入任何 settings.json、不得执行任何注册/激活命令；实际安装到 live 属 T9 deploy + ledger 授权流程，不在本 packet 范围。
- 禁止用对话上下文替代 `required_context`。
- **anti-fill 行为禁令**：实现步骤动作不得只写"完善 / 优化 / 系统性 / 全面 / 增强"等泛词；新增校验逻辑须给出具体可核验语义（"每条 SC 须含非空 verify""expect 去标点空白后落黑名单且无具体串即拦""PLAN_ANTIFILL_FAIL 信号串"），本 packet 自身的 §7 verify expect 即满足该硬门示范。
- **范围边界**：本 packet 只做 (1) `gd-validate-review2-plan-target.py` 的 anti-fill 硬门强化（per-SC verify 存在性 + expect 泛词黑名单 + PLAN_ANTIFILL_FAIL + exit≠0）(2) `scripts/plan-mode-antifill-stop-hook.js` 的 source 文件交付（同语义、source-only、不激活）。不修改 `commands/review2.md` 把该校验串进编排（那是 T5/T7 owned）、不修改 plan 模板（T3 owned）、不部署 hook 到 live（T9 owned）、不复用/不修改 `lib/sc_extraction.py`（只读）。
