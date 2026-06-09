# Task Packet: t5-split-commands-triage

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t5-split-commands-triage
agent_role: implementer
parent_step: T5
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T15:30:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表（ref GOAL_SOURCE）
CHAIN_GOAL:   让 L2(/review2) 成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交（ref GOAL_SOURCE）
PHASE_GOAL:   为 L2 spec T1-T9 各产出可被 /gd execute 消费的自包含 task packet；本 packet 实现 spec §3 的 T5（ref master-plan.md SC-5）
TASK_GOAL:    把 /review2 入口从 `--profile <profile>` 改成子命令式 `/review2 plan` 与 `/review2 code`——`/review2 plan <plan-file>` 等价于原 plan_review 路；`/review2 code` 为动手后审查，自动判定三档（code-only / execution-only / combined）后告知用户确认。判定逻辑落在新建脚本 scripts/gd-detect-review2-code-target.py：git diff 有改动 → has_code=true；发现执行产物文件（测试结果/输出日志/产物目录）→ has_result=true；据此输出 code-only / execution-only / combined 三档之一 + 判定依据；用户可用 --code / --result / --combined 覆盖；判不准（无法确定 has_code/has_result）时输出 INDETERMINATE 让上层问用户、不擅自猜（spec §6 决策表 D1）。release_closure / runtime_parity 按 Q4 暂留为旧式 flag，不拆子命令。
```

---

## 3. 依赖与并发

```yaml
blocked_by: []
  # T5 是 plan/code 入口拆分本身，无实现前置；反过来 T2/T4/T7 在 master-plan §5 中 blocked_by: T5（它们依赖 T5 拆出的子命令入口 + 三档判定结果）。
can_parallel_with:
  - t6
  # T6 改 scripts/gd-codex-bridge-review.py + scripts/gd-review-router.py（bridge target 修复），与本任务的 commands/review2.md 入口解析 + 新建 gd-detect-review2-code-target.py 无写入交集。
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md
    # 实现权威源：§2.1 三入口流程（plan / code 自动判定三档 + 用户确认 + 覆盖）、§2.3 按 kind 分容表（plan/code_diff/execution_outcome/combined 四 kind 与三档的映射）、§3 T5 段、§6 决策表 D1（自动判定三档 + 告知用户确认 + 可手动覆盖 + 判不准问用户不猜）、§5 边界（不输出裸 VERDICT、改动只落 Project GD/**）。
```

> 注：本 packet 只改 `commands/review2.md`（入口解析改子命令 + 路由说明）与新建 `scripts/gd-detect-review2-code-target.py`（三档判定脚本）。判定脚本可 import 复用仓库现有共享模块 `scripts/gd_review_detection.py`（导出 `classify_artifacts` / `has_execution_artifacts_in_dir` / `is_execution_json`）来探测执行产物，但**不得修改它**（不在 owned_paths）。该模块当前的枚举（`execution_plus_code` / `plan_only` / `execution_only_no_code` / `code_only` / `no_artifact`）面向 L3 router；T5 的三档（`code-only` / `execution-only` / `combined`）是 code 路专用输出，由本脚本基于 (has_code, has_result) 自行映射，不复用 router 枚举名。

---

## 4. 路径权限

```yaml
owned_paths:
  - commands/review2.md                          # 入口解析：--profile → 子命令 plan / code；补 code 路三档判定 + 确认 + 覆盖说明（在仓库）
  - scripts/gd-detect-review2-code-target.py     # 新建：三档判定脚本（has_code / has_result → code-only|execution-only|combined|INDETERMINATE）
forbidden_paths:
  - "/Users/praise/.claude/**"
  - 旧 /rev artifacts
  - scripts/gd_review_detection.py               # 只读复用，禁改（其枚举面向 L3 router，T5 不动）
  - scripts/gd-detect-review-target.py           # L3 既有探测 CLI，禁改（本 packet 新建独立的 review2-code 判定脚本，不覆写此文件）
  - prompts/gd-review-standard.md                # T1 owned
  - scripts/gd-codex-bridge-review.py            # T1/T6 owned
  - scripts/gd-review-router.py                  # T6/T7 owned
  - scripts/gd-review-controller.py              # T7 owned（新增）
  - schema/gd-baseline-findings.schema.json      # T7 owned（新增）
  - scripts/gd-review2-preflight.sh              # T2 owned
  - scripts/gd-validate-review2-plan-target.py   # T4 owned
  - scripts/plan-mode-antifill-stop-hook.js      # T4 owned（新增）
  - scripts/gd-review2-package-deliverable.sh    # T8 owned
  - templates/plan-mode-template.md              # T3 owned（新增）
  - .deploy-manifest.jsonl                       # T9 owned
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（`commands/review2.md`、`scripts/gd-detect-review2-code-target.py`）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取以下三类，超出此范围视为越界：
  1. `required_context` 列出的文件
  2. 已完成的 `blocked_by` task 的 deliverables（本任务 `blocked_by: []`，无前置依赖产物可读）
  3. 公共只读资源（GOAL_SOURCE、GD_STANDARD、master-plan.md、lock files、schema，以及 forbidden 中标注"只读复用"的 `scripts/gd_review_detection.py`）
- T6 可并行（`can_parallel_with: [t6]`），但 T6 的 `owned_paths`（bridge / router）禁止写入。

---

## 5. 成功标准（SC）

> 本 packet 对应 master-plan SC-5。下列 SC-5.1 ~ SC-5.5 是 SC-5 的可验证子条件，全部 pass 才算 SC-5 达成。
> anti-fill 自我约束：每条 SC 的 expect 都是**字面输出串或具体 exit 行为**，不含泛词（通过|正确|完成|works|pass|ok|成功）作为唯一内容。

- [ ] SC-5.1（入口改子命令）：`commands/review2.md` 的 Usage / 路由说明从 `--profile code_diff|plan_review|...` 改为子命令形式——文档明确给出 `/review2 plan <plan-file>` 与 `/review2 code` 两条子命令，且说明 `/review2 plan` 等价于原 plan_review 路（保留 `BRIDGE_TARGET_POLICY: original_plan_only` 语义），`release_closure` / `runtime_parity` 按 Q4 暂留 flag。验收命令见 §7 verify SC-5.1。
- [ ] SC-5.2（判定脚本存在 + CLI 可用）：新建 `scripts/gd-detect-review2-code-target.py`，提供 `--help`（argparse），支持 `--cwd <dir>` 指定 git 工作目录、`--code`/`--result`/`--combined` 三个互斥覆盖 flag。`python3 scripts/gd-detect-review2-code-target.py --help` exit 0 且 usage 含上述 flag。验收命令见 §7 verify SC-5.2。
- [ ] SC-5.3（三档判定逻辑）：脚本据 (has_code, has_result) 输出三档之一并打印判定行 `REVIEW2_CODE_TARGET: code-only|execution-only|combined|INDETERMINATE` + 一行 `REVIEW2_TRIAGE_BASIS: <依据>`（说明 has_code/has_result 各自来源）。判定规则：has_code 且非 has_result → `code-only`；has_result 且非 has_code → `execution-only`；两者皆真 → `combined`；两者皆无法确定 → `INDETERMINATE`（exit≠0，交上层问用户，不擅自猜，守 D1）。has_code 由 git 工作树 diff（`git diff` / `git diff --cached` / untracked，经 `--cwd`）判定；has_result 由执行产物探测（复用 `gd_review_detection.has_execution_artifacts_in_dir` 或等价 JSON/日志/产物目录探测）判定。验收命令见 §7 verify SC-5.3（三种 git 状态 fixture 断言）。
- [ ] SC-5.4（用户覆盖优先）：传 `--code` / `--result` / `--combined` 时，脚本跳过自动判定、直接输出对应三档（`REVIEW2_CODE_TARGET` 取覆盖值，`REVIEW2_TRIAGE_BASIS` 标注 `user_override`），exit 0；三个 flag 互斥（同传 ≥2 个 → exit≠0 + 报错）。验收命令见 §7 verify SC-5.4。
- [ ] SC-5.5（不输出裸 VERDICT；review2.md 串接判定脚本）：`commands/review2.md` 在 code 路编排中调用 `scripts/gd-detect-review2-code-target.py` 并把判定结果交用户确认（文档说明"输出判定 + 依据，用户可 --code/--result/--combined 覆盖；INDETERMINATE 时问用户不猜"）；脚本与文档**均不**输出裸 `VERDICT:`（守 spec §5——用 `REVIEW2_CODE_TARGET` 等专用信号，避免触发 live hook 的 VERDICT regex）。验收命令见 §7 verify SC-5.5。

---

## 6. 交付物

```yaml
deliverables:
  - path: commands/review2.md
    kind: file
    must_exist: true
    description: 入口从 --profile 改子命令 plan/code；plan 路保留 original_plan_only 语义；code 路接入三档自动判定 + 用户确认 + --code/--result/--combined 覆盖；release_closure/runtime_parity 暂留 flag；不输出裸 VERDICT
  - path: scripts/gd-detect-review2-code-target.py
    kind: file
    must_exist: true
    description: 新建三档判定脚本——(has_code, has_result) → code-only|execution-only|combined|INDETERMINATE，打印 REVIEW2_CODE_TARGET + REVIEW2_TRIAGE_BASIS；支持 --cwd 与 --code/--result/--combined 互斥覆盖；判不准 INDETERMINATE 且 exit≠0（交上层问用户）
  - path: handoff_output（见 §8）
    kind: report
    must_exist: true
    description: 子 agent 执行结果，含 §7 全部 verify 命令真实输出（含三种 git 状态 fixture 的 REVIEW2_CODE_TARGET 行与 exit code）
```

---

## 7. 验证（Anti-fill 硬约束）

> 每条 SC 绑定可执行命令 / 路径 / 断言 / 测试。执行后必须在 handoff_output 贴真实输出。
> 下列命令均在工作目录 `/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity` 下运行。
> fixture 约定：子 agent 自行在临时目录（`mktemp -d` / `/tmp` 下）构造三种 git 工作树状态，**不写入 owned_paths 外的版本管理路径**，且每个 fixture 用独立 `git init` 临时 repo（避免污染本工作树）：
>   (g1) 仅代码改动：临时 repo 有未提交 diff、无执行产物 JSON → 期望 `code-only`；
>   (g2) 仅执行结果：临时 repo 无 diff、目录含一个 execution outcome JSON（含 `outcome_id` 或 `execution_status` 等签名字段）→ 期望 `execution-only`；
>   (g3) 代码 + 执行结果：临时 repo 有未提交 diff 且目录含 execution outcome JSON → 期望 `combined`。
> handoff 必须贴这三类 fixture 的真实 `REVIEW2_CODE_TARGET` 行、`REVIEW2_TRIAGE_BASIS` 行与 exit code，不得只写"已验证 / 通过"。

```yaml
verify:
  - sc_ref: SC-5.1
    method: assertion
    cmd: "grep -nE '/review2 (plan|code)' commands/review2.md | wc -l"
    expect: ">=2——文档同时出现 /review2 plan 与 /review2 code 子命令用法"
  - sc_ref: SC-5.1
    method: assertion
    cmd: "grep -nE 'original_plan_only' commands/review2.md"
    expect: ">=1 行命中——/review2 plan 保留原 plan_review 的 BRIDGE_TARGET_POLICY: original_plan_only 语义"
  - sc_ref: SC-5.2
    method: command
    cmd: "test -f scripts/gd-detect-review2-code-target.py && echo SCRIPT_EXISTS"
    expect: "SCRIPT_EXISTS"
  - sc_ref: SC-5.2
    method: command
    cmd: "python3 scripts/gd-detect-review2-code-target.py --help; echo EXIT=$?"
    expect: "EXIT=0；--help usage 文本含 --cwd 与 --code/--result/--combined 三个覆盖 flag"
  - sc_ref: SC-5.3
    method: test
    cmd: "d=$(mktemp -d); git -C \"$d\" init -q; printf 'a\\n' > \"$d/f.txt\"; git -C \"$d\" add f.txt; git -C \"$d\" -c user.email=t@t -c user.name=t commit -qm base; printf 'b\\n' >> \"$d/f.txt\"; python3 scripts/gd-detect-review2-code-target.py --cwd \"$d\"; echo EXIT=$?; rm -rf \"$d\""
    expect: "stdout 含 'REVIEW2_CODE_TARGET: code-only'；EXIT=0（g1 仅未提交 diff、无执行产物 → code-only）"
  - sc_ref: SC-5.3
    method: test
    cmd: "d=$(mktemp -d); git -C \"$d\" init -q; printf '{\"outcome_id\":\"x\",\"execution_status\":\"completed\"}\\n' > \"$d/outcome.json\"; git -C \"$d\" add outcome.json; git -C \"$d\" -c user.email=t@t -c user.name=t commit -qm base; python3 scripts/gd-detect-review2-code-target.py --cwd \"$d\"; echo EXIT=$?; rm -rf \"$d\""
    expect: "stdout 含 'REVIEW2_CODE_TARGET: execution-only'；EXIT=0（g2 无未提交 diff、目录含 execution outcome JSON → execution-only）"
  - sc_ref: SC-5.3
    method: test
    cmd: "d=$(mktemp -d); git -C \"$d\" init -q; printf '{\"outcome_id\":\"x\",\"execution_status\":\"completed\"}\\n' > \"$d/outcome.json\"; printf 'a\\n' > \"$d/f.txt\"; git -C \"$d\" add f.txt outcome.json; git -C \"$d\" -c user.email=t@t -c user.name=t commit -qm base; printf 'b\\n' >> \"$d/f.txt\"; python3 scripts/gd-detect-review2-code-target.py --cwd \"$d\"; echo EXIT=$?; rm -rf \"$d\""
    expect: "stdout 含 'REVIEW2_CODE_TARGET: combined'；EXIT=0（g3 未提交 diff + execution outcome JSON 并存 → combined）"
  - sc_ref: SC-5.3
    method: assertion
    cmd: "python3 scripts/gd-detect-review2-code-target.py --help | grep -niE 'REVIEW2_CODE_TARGET|triage|three|三档|code-only|execution-only|combined' | wc -l; grep -nE 'REVIEW2_CODE_TARGET|REVIEW2_TRIAGE_BASIS' scripts/gd-detect-review2-code-target.py | wc -l"
    expect: "第二条计数 >=2——脚本源码含 REVIEW2_CODE_TARGET 与 REVIEW2_TRIAGE_BASIS 两个输出信号串"
  - sc_ref: SC-5.4
    method: test
    cmd: "d=$(mktemp -d); git -C \"$d\" init -q; printf 'a\\n' > \"$d/f.txt\"; git -C \"$d\" add f.txt; git -C \"$d\" -c user.email=t@t -c user.name=t commit -qm base; python3 scripts/gd-detect-review2-code-target.py --cwd \"$d\" --result; echo EXIT=$?; rm -rf \"$d\""
    expect: "stdout 含 'REVIEW2_CODE_TARGET: execution-only' 且 'REVIEW2_TRIAGE_BASIS' 行含 user_override；EXIT=0（--result 覆盖：repo 实际无执行产物，但用户覆盖优先）"
  - sc_ref: SC-5.4
    method: test
    cmd: "d=$(mktemp -d); git -C \"$d\" init -q; python3 scripts/gd-detect-review2-code-target.py --cwd \"$d\" --code --combined; echo EXIT=$?; rm -rf \"$d\""
    expect: "EXIT 非 0（--code 与 --combined 互斥，同传 ≥2 个覆盖 flag → 报错退出，不静默取一个）"
  - sc_ref: SC-5.4
    method: test
    cmd: "d=$(mktemp -d); git -C \"$d\" init -q; git -C \"$d\" -c user.email=t@t -c user.name=t commit -q --allow-empty -m base; python3 scripts/gd-detect-review2-code-target.py --cwd \"$d\"; echo EXIT=$?; rm -rf \"$d\""
    expect: "stdout 含 'REVIEW2_CODE_TARGET: INDETERMINATE'；EXIT 非 0（空 repo：无 diff 无执行产物，无法确定 → 不擅自猜，交上层问用户，守 D1）"
  - sc_ref: SC-5.5
    method: assertion
    cmd: "grep -nE 'gd-detect-review2-code-target' commands/review2.md"
    expect: ">=1 行命中——review2.md code 路编排显式调用三档判定脚本"
  - sc_ref: SC-5.5
    method: assertion
    cmd: "grep -nE '^[[:space:]]*VERDICT:' commands/review2.md scripts/gd-detect-review2-code-target.py | wc -l"
    expect: "0——脚本与文档均不输出裸 VERDICT:（守 spec §5，避免触发 live hook regex；用 REVIEW2_CODE_TARGET 等专用信号）"
  - sc_ref: SC-5.5
    method: test
    cmd: "python3 -c \"import ast; ast.parse(open('scripts/gd-detect-review2-code-target.py').read()); print('SYNTAX_OK')\""
    expect: "SYNTAX_OK（新建脚本语法可解析，不引入 SyntaxError）"
```

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t5-split-commands-triage-result.md
  status_field: <见 gd-execution-status.schema.json：completed | blocked | partial>
  summary: <一句话结论，例如：review2 入口由 --profile 改为子命令 plan/code；新建 gd-detect-review2-code-target.py 三档判定（code-only/execution-only/combined/INDETERMINATE，复用 gd_review_detection 探测执行产物），支持 --cwd 与三个互斥覆盖 flag，判不准输出 INDETERMINATE 且 exit≠0 交用户；三种 git 状态 fixture 真实输出已贴>
  blockers: <未完成的依赖或外部阻塞；无则写 none>
```

handoff 必须贴 §7 全部 verify 命令的真实输出（命令 + stdout/exit code），并单列三种 git 状态 fixture（g1 code-only / g2 execution-only / g3 combined）外加空 repo INDETERMINATE 的 `REVIEW2_CODE_TARGET` 行与 exit code，不得只写"已验证 / 通过"。

---

## 9. 范围禁令

- 禁止 **写入** §4 `owned_paths` 之外任何路径（尤其 T1/T2/T3/T4/T6/T7/T8/T9 的 owned，以及 `scripts/gd_review_detection.py`、`scripts/gd-detect-review-target.py`）。
- 禁止 **读取** 其他 task 的 `owned_paths`（本任务 `blocked_by: []`，无前置依赖产物可读）；`scripts/gd_review_detection.py` 作为公共只读共享模块可 import 复用但不得修改。
- 禁止访问 `/Users/praise/.claude/**`。
- 禁止启动 daemon、注册 hook、修改 cron：`scripts/gd-detect-review2-code-target.py` 仅作为 **source 脚本** 交付——不得 `cp`/symlink 到 `~/.claude`、不得写任何 settings.json；实际部署到 live 属 T9 deploy + ledger 授权，不在本 packet 范围。
- 禁止用对话上下文替代 `required_context`。
- **不擅自实现下游**：本 packet 只交付 (1) `commands/review2.md` 入口子命令化 + code 路三档判定/确认/覆盖说明 (2) `scripts/gd-detect-review2-code-target.py` 三档判定脚本。**不**实现 dry-run 送审门（T2 owned `gd-review2-preflight.sh`）、**不**改 bridge 的 PRIMARY_TARGET（T6 owned）、**不**实现 controller 循环/baseline 收敛（T7 owned）、**不**实现终点打包（T8 owned）。三档判定结果是这些下游任务的输入，本 packet 只负责产出该判定信号，不消费它。
- **anti-fill 行为禁令**：实现步骤动作不得只写"完善 / 优化 / 系统性 / 全面 / 增强"等泛词；判定逻辑须给出具体可核验语义（"has_code 由 git 工作树 diff 判定""has_result 由执行产物 JSON 探测判定""两者皆真 → combined""两者皆无法确定 → INDETERMINATE 且 exit≠0"），本 packet 自身 §7 verify expect 即满足该硬门示范。
```
