# Task Packet: t8-deliverable-packaging

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t8-deliverable-packaging
agent_role: implementer
parent_step: T8
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T00:00:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表
CHAIN_GOAL:   让 L2(/review2)成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交
PHASE_GOAL:   为 L2 spec T1-T9 各产出一份自包含、可被 /gd execute 消费的 task packet（本 packet 对应 T8）
TASK_GOAL:    实现 /review2 code 的统一终点 stage——当全 gate 绿（conformance APPROVED + 工作树测试绿 +
              分支 A 的 post-simplify 重测绿）时，新增 scripts/gd-review2-package-deliverable.sh 产出三件套：
              ① git add 已 stage 的改动 ② SC 逐条证据表（命令 + 真实输出） ③ commit message / MR description 草稿；
              接 commit-projects / create-mr+submit-mr，**不自动 commit/push**。
              任一 gate 不绿 → 打印 DELIVERABLE_BLOCKED + 阻塞清单，不产出成品。
              并把该 stage 接进 commands/review2.md 终点编排，作为分支 A/B/C 收敛后的统一出口。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t7-controller-baseline-convergence   # T7 的 controller 产出 conformance APPROVED / CONVERGENCE_TIMEOUT 是本 stage 的进入条件；无"通过结果"不打包（spec §4 硬依赖 T7→T8）
can_parallel_with:
  - t7                                   # planning 阶段两 packet 各写各文件互不重叠，可并发写；实现期 T8 仍 blocked_by T7（依赖记录在本字段供 /gd execute 重建）
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md   # §3 T8 段、§2.1 统一终点、§2.2 fail-visibly、§2.4 DELIVERABLE_BLOCKED ≠ CONVERGENCE_TIMEOUT、§5 不自动 commit/push 边界
```

> 读取前置依赖产物的合法性（§4）：`t7-controller-baseline-convergence` 完成后，其 controller（`scripts/gd-review-controller.py`）输出的最终判定（`baseline_unresolved=0 且 new_in_delta=0 → APPROVED`，或 `CONVERGENCE_TIMEOUT`）与 `baseline_findings.json` 是本 stage 的合法读取输入（gate 状态来源）。本 packet 只**读取**该判定与产物，不修改 T7 的 owned_paths。

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-review2-package-deliverable.sh  # 新建：打包脚本，按 gate 状态产三件套或打印 DELIVERABLE_BLOCKED
  # commands/review2.md 由 t5 owned；本任务 blocked_by t7（t7 blocked_by t5），对终点 stage 段追加内容，
  # deliverables 中说明"追加统一终点 stage 段到 T5 owned commands/review2.md"，不重复声明 owned_paths。
forbidden_paths:
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
  - scripts/gd-review-controller.py            # T7 owned（本 stage 只读其判定结果，不写）
  - schema/gd-baseline-findings.schema.json    # T7 owned
  - scripts/gd-codex-bridge-review.py          # T1/T6 owned
  - scripts/gd-review-router.py                # T6/T7 owned
  - prompts/gd-review-standard.md              # T1 owned
  - templates/plan-mode-template.md            # T3 owned
  - scripts/gd-validate-review2-plan-target.py # T4 owned
  - scripts/gd-detect-review2-code-target.py   # T5 owned
  - scripts/gd-review2-preflight.sh            # T2 owned
  - <任何其他 task 的 owned_paths>
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（`commands/review2.md` 的终点 stage 段 + 新建 `scripts/gd-review2-package-deliverable.sh`）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取 `required_context` 列出的 spec 文件、`blocked_by`（T7）已完成产物（`scripts/gd-review-controller.py` 输出的判定 + `baseline_findings.json` 结构），以及公共只读资源（goal 文件、`templates/`、`schema/`、`prompts/`）。
- `commands/review2.md` 是 T2/T5/T7/T8 共享文件，按 master plan §5 实现 wave 串行错开（w3·T2/T5 → w4·T7 → w5·T8）。本 packet 在 T7 落地的 LOOP 编排之后**追加**终点 stage 段，属合法续写，不重写他人段落。

---

## 5. 成功标准（SC）

对应 master plan SC-8。每条 SC 绑可执行 verify（见 §7）。

- [ ] SC-8.1（打包脚本存在且可执行）：`scripts/gd-review2-package-deliverable.sh` 文件存在、有可执行位、`bash -n` 语法通过。脚本接受 gate 状态输入（如 `--conformance-status APPROVED|REQUIRES_CHANGES`、`--tests-status green|red`、`--post-simplify-status green|red|n_a`，及待打包工作树/changed-file 列表来源），按状态分流到"产三件套"或"DELIVERABLE_BLOCKED"两条路径之一。
- [ ] SC-8.2（全绿 → 三件套正路）：当 conformance=APPROVED 且 tests=green 且 post-simplify=green（分支 B 无 simplify 时 post-simplify=n_a 视为满足）时，脚本 exit 0 并产出三件套：① 对工作树改动执行 `git add`（stage，**不 commit/push**） ② 打印/写出"SC 逐条证据表"（每条 SC 的 verify 命令 + 真实输出片段，非泛词） ③ 打印/写出 commit message 与 MR description 草稿。输出含可被下游识别的交付状态标记（如 `DELIVERABLE_STATUS: READY_FOR_HANDOFF`），并声明"接 commit-projects / create-mr+submit-mr"。
- [ ] SC-8.3（任一 gate 红 → DELIVERABLE_BLOCKED 负路）：当 conformance≠APPROVED 或 tests=red 或 post-simplify=red 中任一成立时，脚本 exit≠0 并打印 `DELIVERABLE_BLOCKED` + 阻塞清单（逐项列出哪个 gate 红 + 原因），**不执行 git add**、**不产出"成品"三件套**（fail-visibly，spec §2.2）。
- [ ] SC-8.4（状态码不混用 H4）：`DELIVERABLE_BLOCKED`（T8 终点 gate 红）与 `CONVERGENCE_TIMEOUT`（T7 LOOP 连续 2 轮不收敛）是两个不同字面状态码，脚本与终点编排只输出 `DELIVERABLE_BLOCKED`，**不输出** `CONVERGENCE_TIMEOUT`（后者属 T7 controller 的退出码，本 stage 收到它时归类为"上游未通过"，按 SC-8.3 走 DELIVERABLE_BLOCKED 路径但保留原因引用，不复用该字面码）。
- [ ] SC-8.5（不自动 commit/push）：脚本与终点 stage 全程不调用 `git commit` / `git push`；仅 `git add` stage。`grep` 脚本正文无 `git commit` / `git push` 调用（注释/草稿文本中作为"建议下游命令"出现的字符串需与实际执行命令区分——实际执行路径不得触发 commit/push）。
- [ ] SC-8.6（终点 stage 接入 commands/review2.md）：`commands/review2.md` 含"统一终点 stage"段，描述分支 A/B/C 收敛后调用 `gd-review2-package-deliverable.sh`，并记录全绿三件套 / 任一红 DELIVERABLE_BLOCKED 的二分支语义，引用"不自动 commit/push"边界。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-review2-package-deliverable.sh
    kind: file
    must_exist: true
    description: 终点打包脚本——全 gate 绿产三件套（git add stage + SC 证据表 + commit/MR 草稿）；任一红打印 DELIVERABLE_BLOCKED + 阻塞清单，不产成品，不自动 commit/push
  - path: commands/review2.md
    kind: file
    must_exist: true
    description: 追加"统一终点 stage"编排段——分支 A/B/C 收敛后的出口，二分支语义（全绿三件套 / 任一红 DELIVERABLE_BLOCKED），引用不自动 commit/push 边界
```

---

## 7. 验证（Anti-fill 硬约束）

> 每条 verify 含命令 / 路径 / 断言 / 测试之一。
> 正/负双测是本 packet 的核心防线：全绿路径产三件套、红 gate 路径输出 `DELIVERABLE_BLOCKED` 且无成品。
> 下方 fixture 命令以"脚本应接受 gate 状态 flag"为契约；实现时若 flag 名不同，须在脚本 `--help`/usage 暴露等价开关，并据此微调断言的 flag 名——但断言核心（全绿 exit0+三件套标记、任一红 exit≠0+DELIVERABLE_BLOCKED+无 git add）不可弱化。

```yaml
verify:
  - sc_ref: SC-8.1
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && test -x scripts/gd-review2-package-deliverable.sh && bash -n scripts/gd-review2-package-deliverable.sh && echo PASS"
    expect: "PASS"
  - sc_ref: SC-8.2
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && bash scripts/gd-review2-package-deliverable.sh --conformance-status APPROVED --tests-status green --post-simplify-status green --dry-run 2>&1 | grep -cE 'READY_FOR_HANDOFF|DELIVERABLE_STATUS|SC 证据|commit message|MR description'"
    expect: ">=1"
  - sc_ref: SC-8.3
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && bash scripts/gd-review2-package-deliverable.sh --conformance-status REQUIRES_CHANGES --tests-status green --post-simplify-status n_a --dry-run; echo \"exit=$?\" | grep -q 'exit=0' && echo UNEXPECTED_ZERO || echo NONZERO_OK"
    expect: "NONZERO_OK"
  - sc_ref: SC-8.3
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && bash scripts/gd-review2-package-deliverable.sh --conformance-status APPROVED --tests-status red --post-simplify-status n_a --dry-run 2>&1 | grep -c 'DELIVERABLE_BLOCKED'"
    expect: ">=1"
  - sc_ref: SC-8.4
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && bash scripts/gd-review2-package-deliverable.sh --conformance-status REQUIRES_CHANGES --tests-status green --post-simplify-status n_a --dry-run 2>&1 | grep -c 'CONVERGENCE_TIMEOUT'"
    expect: "0"
  - sc_ref: SC-8.5
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE '(^|[^#])git[[:space:]]+(commit|push)' scripts/gd-review2-package-deliverable.sh | grep -vE 'echo|printf|草稿|draft|建议|suggest|cat <<|#' | wc -l"
    expect: "0"
  - sc_ref: SC-8.6
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -cE 'gd-review2-package-deliverable|DELIVERABLE_BLOCKED|终点 stage|统一终点' commands/review2.md"
    expect: ">=1"
```

> 注 1：SC-8.2/8.3 的 `--dry-run` 用于在测试 fixture 中走"产三件套 / 报阻塞"判定逻辑而**不真改工作树**（避免污染 review 期工作树）；实现时 `--dry-run` 必须保留 gate 判定与输出标记，仅跳过真实 `git add` 副作用。
> 注 2：SC-8.5 的 grep 排除注释/echo/草稿文本里出现的 `git commit`/`git push`（这些是给用户看的"下游建议命令"字符串），只统计真实执行调用——若脚本通过 here-doc 写草稿提到这两个命令，须确保它们不在实际执行路径上。

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t8-deliverable-packaging-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论：终点打包脚本已实现，全绿产三件套 / 任一红 DELIVERABLE_BLOCKED 无成品，不自动 commit/push，已接进 review2.md 终点 stage>
  blockers: <未完成的依赖或外部阻塞，例如 T7 controller 判定接口未定导致 gate 状态来源未对接>
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 task 的 `owned_paths`（`scripts/gd-review-controller.py`、`schema/gd-baseline-findings.schema.json`、`scripts/gd-codex-bridge-review.py`、`scripts/gd-review-router.py`、`prompts/gd-review-standard.md` 等）
- 禁止 **读取** 未完成 task 的 `owned_paths`，除非该 task 已完成且其 deliverables 列入 `required_context`（本 packet 仅合法读取已完成 T7 的判定结果与 `baseline_findings.json` 结构）
- 禁止访问 `/Users/praise/.claude/**`
- 禁止启动 daemon、注册 hook、修改 cron
- **禁止自动 commit / push**——终点只产出可提交态，由用户 / `commit-projects` / `create-mr`+`submit-mr` 触发（守 spec §5 边界）
- 禁止用对话上下文替代 `required_context`
- 不改 L3 `/gd review` 语义、不动旧 `/review`/`/rev`/`codex-watch` daemon（守 spec §5 边界）
- 不在 `/review2` 输出裸 `VERDICT:`（用 `REV_VERDICT`/`GD_REVIEW_DECISION`，避免触发 live hook regex）
- 状态码不混用：本 stage 只输出 `DELIVERABLE_BLOCKED`，不复用 T7 的 `CONVERGENCE_TIMEOUT` 字面码（H4）
- anti-fill：SC 与 verify 禁止用"完善 / 优化 / 系统性 / 全面 / 增强"占位；每条 SC 必带可执行断言
