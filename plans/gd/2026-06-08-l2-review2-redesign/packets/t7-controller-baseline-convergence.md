# Task Packet: t7-controller-baseline-convergence

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t7-controller-baseline-convergence
agent_role: implementer
parent_step: T7
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T15:20:45Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表
CHAIN_GOAL:   让 L2(/review2)成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交
PHASE_GOAL:   为 L2 spec T1-T9 各产出一份自包含、可被 /gd execute 消费的 task packet（本 packet 对应 T7）
TASK_GOAL:    实现 /review2 code 的循环状态机（分支 A/B/C）+ Baseline 收敛机制：
              新增确定性 Python controller（gd-review-controller.py，直调 codex CLI，不走 Claude 编排）
              + baseline_findings.json 的 JSON Schema；Round 1 双 codex（不同 lens）+ Claude self-review
              三方并集建 baseline，Round 2+ 单 codex 中性 lens 靠每轮重喂 BASELINE_FINDINGS/DELTA_SCOPE/
              SCOPE_CONSTRAINT 三字段对账；delta 用工作树快照（git stash create）不 commit；
              baseline_unresolved 连续 2 轮不减 → CONVERGENCE_TIMEOUT；大 delta（>150 行或 >5 文件，可配）
              降级双 codex。复用 bridge mapped JSON 的 findings[]，不正则解析 codex raw。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t5-split-commands-triage    # T5 在 commands/review2.md 拆 plan/code 子命令 + 三档判定脚本；controller 以三档判定结果(code-only/execution-only/combined)为分支 A/B/C 的入口，且 T7 也编排 review2.md，须在 T5 之后避免对同一文件并发冲突
  - t6-fix-bridge-target        # T6 修 bridge build_capsule_text 使 PRIMARY_TARGET 指向真实 diff/执行产物；controller 的每轮 capsule 与 bridge dispatch 必须建在已修正的 target 上，否则分支 B/C 建在坏 target 上空转（堵 H9）
can_parallel_with:
  - t8                          # T8 改 /review2 code 终点打包 stage（review2.md 终点段 + 打包脚本），逻辑接在 controller APPROVED 之后；与 T7 的 controller/router/schema 文件可并行设计，但二者都触碰 review2.md，须按依赖顺序串行编辑该文件（见下注）
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md   # §2.1 分支 A/B/C、§2.2 conformance scoping、§2.3 无状态不变量与上下文预算、§2.4 全部（Baseline 收敛 + D4 双 reviewer 并集 + D7 大 delta 降级 + 无状态 codex 如何在 baseline 之下审 + 实现要点）、§3 T7 段、§6 决策表 D3/D4/D7
```

> 读取前置依赖产物的合法性（§4）：`t5-split-commands-triage` 与 `t6-fix-bridge-target` 完成后，T5 对 `commands/review2.md`、T6 对 `scripts/gd-codex-bridge-review.py` / `scripts/gd-review-router.py` 的改动已落盘。本 packet 在 T5 已拆好的 review2.md 上追加 controller 编排段、在 T6 已修正的 bridge target 之上消费 bridge mapped JSON，属合法续写（同一 owned_path `commands/review2.md` 与 `scripts/gd-review-router.py` 由依赖顺序串行化，非越界）。
> review2.md 多任务共享说明：T5（入口拆分）、T7（code 循环编排）、T8（终点打包）均触碰 `commands/review2.md`。本 packet 仅追加/修改 T7 负责的 **code 路循环编排段**（调用 controller、传三档判定结果、衔接分支 A/B/C），不动 T5 的入口解析段与 T8 的终点打包段；写入时按段落定位，避免覆盖另两个 task 的区域。

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-review-router.py                 # 仅限把 controller 接入 execution_outcome/combined 路由（让 controller 成为多轮循环的驱动者，单轮 bridge dispatch 仍由 router 现有 _run_live_bridge 完成）；不重写 T6 已修正的 target 传参逻辑
  - scripts/gd-review-controller.py             # 新建：多轮循环状态机 + baseline 收敛 + delta 计算 + 退出判定 + 直调 codex CLI
  - schema/gd-baseline-findings.schema.json     # 新建：baseline_findings.json 的 JSON Schema
  # commands/review2.md 由 t5 owned；本任务 blocked_by t5 完成后对 code 循环编排段追加内容，
  # deliverables 中说明"追加 T7 code 循环编排段到 T5 owned commands/review2.md"，不重复声明 owned_paths。
forbidden_paths:
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
  - prompts/gd-review-standard.md                # 属 T1 owned（穷举强制 + REVIEW_LENS_EMPHASIS 文本）
  - scripts/gd-codex-bridge-review.py            # 属 T1/T6 owned；controller 只**消费**其 mapped JSON 输出，禁止改其源码
  - scripts/gd-validate-review2-plan-target.py   # 属 T4 owned
  - scripts/gd-validate-execution-outcome.py     # 公共只读复用（已含重跑 verify 的 MANDATORY VERIFY STEP），禁止改源
  - <任何其他 task 的 owned_paths 与 commands/review2.md 的 T5/T8 区域>
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（`commands/review2.md` 的 T7 code 循环段、`scripts/gd-review-router.py` 的 controller 接入点、新建 `scripts/gd-review-controller.py`、新建 `schema/gd-baseline-findings.schema.json`）；写入任何其他路径或越段写 review2.md 视为越界，review 中 [P1] 阻断。
- **读取**：允许读取 `required_context` 的 spec 文件；`blocked_by`（T5/T6）已落盘的 deliverables（T5 的三档判定脚本接口、T6 修正后的 bridge target 行为）；以及公共只读资源：
  1. `scripts/gd-codex-bridge-review.py`（读其 mapped JSON 字段契约：`review_run_status`/`gd_review_decision`/`findings[]`，findings 对象字段 `severity(P1|P2)`/`title`/`sc_refs`/`evidence`/`impact`/`required_fix`/`verify`），仅读不写
  2. `scripts/gd-review-suite-controller.py`（读其 `max_parallel=2` bounded-parallel ThreadPoolExecutor 范式，作 Round 1 双 codex 并发参照），仅读不写
  3. `scripts/gd-validate-execution-outcome.py`（读其重跑 verify 接口，分支 B/C 复用），仅读不写
  4. `vendor/l3-transport/handoff/bin/codex-watch`（读 `codex exec --ephemeral` 调用形态，确认无状态不变量），仅读不写
  5. 公共只读资源：PROJECT_GOAL.md、`templates/`、其他 `schema/*.schema.json`

---

## 5. 成功标准（SC）

对应 master plan **SC-7**。本 task 是整个 spec 最重的一项；下列 9 条 SC 各绑可执行 verify（见 §7），缺一不可。

- [ ] SC-7.1（Round 1 双 codex + Claude self-review 三方并集建 baseline）：`gd-review-controller.py` Round 1 并行 dispatch **2 个独立 codex job**，两 capsule 唯一差异是 `REVIEW_LENS_EMPHASIS` 不同维度排序（`codex_A`：SC-conformance → 边界/路径越界 → 接口/契约 → 失败模式/fallback → anti-fill 泛化；`codex_B`：失败模式/fallback → 安全/secret 泄漏 → anti-fill 泛化 → SC-conformance → 边界/路径越界），各自仍收完整穷举指令；与 Claude self-review 三方 findings 取并集，去重键 = (文件, 行号±3, 类别)，严重度取高 → 写 `baseline_findings.json`。构造 codex_A 漏报 / codex_B 命中的 fixture，baseline 必含该 finding。
- [ ] SC-7.2（Round 2+ 单 codex 中性 lens + 复用 bridge mapped findings，不正则解析 raw，堵 H3）：Round 2 起默认 dispatch **1 个 codex**（中性全维度 lens，无 `REVIEW_LENS_EMPHASIS` 偏置）；controller 消费 bridge `gd-codex-bridge-review.py` 输出的已 schema 校验 mapped JSON 的 `findings[]` 数组，**不自己正则解析 codex raw 文本**。controller 源码中无针对 codex raw 输出的正则解析（如 `re.search`/`re.findall` 抓 `VERDICT`/`P1`/`finding` 等 raw 文本模式）。
- [ ] SC-7.3（delta 用工作树快照不 commit，堵 H2）：controller 每轮起存工作树快照（`git stash create` 的 tree-ish 或 changed-file blob hash），delta = 本轮工作树 vs 上轮快照；全程**不产生新 commit**（守 spec §5"不自动 commit"，也不污染 T8 要打包的提交历史）。源码含 `git stash create`（或等价快照），不含 `git commit`。
- [ ] SC-7.4（CONVERGENCE_TIMEOUT 防死循环）：`baseline_unresolved` = baseline 中尚未修复的 finding 数；连续 2 轮 `baseline_unresolved` 未递减 → controller 退出码 ≠0 且打印 `CONVERGENCE_TIMEOUT`（与 T8 终点 gate 的 `DELIVERABLE_BLOCKED` 是两个不同状态码，不可混用；controller 永不输出 `DELIVERABLE_BLOCKED`）。
- [ ] SC-7.5（D7 大 delta 降级双 codex）：Round 2+ 组装 capsule 前算 delta 规模；改动行数 > 阈值（默认 150，`--round2-fanout-threshold-lines` 可配）**或** 改动文件数 > 阈值（默认 5，`--round2-fanout-threshold-files` 可配）→ 该轮改用双 codex（复用 codex_A/codex_B emphasis）并集，scope 仍限 delta（守 SCOPE_CONSTRAINT，不重审未改动代码）；按轮判定、无状态记忆，delta 回落则下一轮自动回单 codex。构造 delta > 阈值 fixture → 该轮 dispatch=2；delta < 阈值 → dispatch=1。
- [ ] SC-7.6（分支 B 也有 CONVERGENCE_TIMEOUT，堵 H8）：分支 B（execution-only）LOOP 仅验 conformance（复用 `gd-validate-execution-outcome.py` 重跑 verify），同样受 `CONVERGENCE_TIMEOUT`——连续 2 轮 unresolved 不减即停退出码 ≠0，不无限 LOOP。
- [ ] SC-7.7（无状态注入：每轮 capsule 重喂三字段）：Round 2+ 每轮 capsule 含 `REVIEW_ROUND: N`（N≥2，非写死 `initial`）+ `BASELINE_FINDINGS`（上轮整张清单 + 每条状态 已修/未修）+ `DELTA_SCOPE`（工作树快照 diff，只含改动行）+ `SCOPE_CONSTRAINT`（硬指令："只验 baseline 修没修 + 查 delta 新引入，禁止重审未改动代码"）。基本面存在 controller 的 `baseline_findings.json`，不在 codex 脑子里——每轮由 controller 重新喂入失忆 codex。
- [ ] SC-7.8（Round 2 客观核验 baseline finding，不重判是否问题，堵 H5）：验 baseline finding 是否已修时，controller 按 finding 原描述客观核验"该问题现象是否还在"，禁止重判"这是不是问题"；构造 baseline 含"本轮 codex 视角不认同但 codex_B 提过"的 finding，controller 不得自动判 resolved（该 finding 仍计入 `baseline_unresolved`，除非现象客观消失）。
- [ ] SC-7.9（controller 直调 codex CLI，D3，不走 Claude 编排 + 退出判定 + schema 校验 + 分支 C 重跑）：controller 用 `codex exec --ephemeral` 直调 codex CLI（确定性脚本，非 Claude 编排）；退出判定 `baseline_unresolved=0 且 new_in_delta=0 → APPROVED`；`baseline_findings.json` 通过 `schema/gd-baseline-findings.schema.json` 校验；分支 C（combined）= 先走分支 A 全流程（含 LOOP + simplify + 重测）→ simplify 改了代码必须重跑产生**新**执行结果（旧结果作废，堵 H7）→ 再走分支 B 验新执行结果，B 收到的执行结果文件 mtime 晚于 simplify。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-review-controller.py
    kind: file
    must_exist: true
    description: 多轮循环状态机（分支 A/B/C）+ baseline 收敛；Round 1 双 codex 并集、Round 2+ 单 codex/大 delta 降级双 codex；delta 用 git stash create 快照不 commit；CONVERGENCE_TIMEOUT；直调 codex exec --ephemeral；消费 bridge mapped findings 不正则解析 raw
  - path: schema/gd-baseline-findings.schema.json
    kind: file
    must_exist: true
    description: baseline_findings.json 的 JSON Schema（draft-07）；定义 findings 数组每条 severity/title/sc_refs/file/line/category/status(unresolved|resolved)/source(codex_A|codex_B|claude) 与 round 元数据
  - path: commands/review2.md
    kind: file
    must_exist: true
    description: code 路循环编排段——按三档判定结果(code-only/execution-only/combined)调用 controller，衔接分支 A 的 /code-review→修→conformance LOOP、simplify、重测节点
  - path: scripts/gd-review-router.py
    kind: file
    must_exist: true
    description: 把 controller 接入 execution_outcome/combined 路由作多轮循环驱动者（单轮 bridge dispatch 仍由 router 现有 _run_live_bridge 完成，不重写 T6 已修正的 target 传参）
```

> `baseline_findings.json` 是 controller 运行期写出的状态文件（写入 `reports/` 或 `GD_ROOT` 运行目录），不是源码交付物——本 packet 交付的是其 schema 与产出它的 controller 脚本。

---

## 7. 验证（Anti-fill 硬约束）

> 每条 verify 含命令 / 路径 / 断言 / 测试之一。所有命令的工作目录锚定本 worktree 绝对路径根，确保 packet 自包含可独立跑。
> 断言「Round 1 dispatch=2 / Round 2 dispatch=1」「连续 2 轮不减 → CONVERGENCE_TIMEOUT」「无 raw 正则」是核心防线，不可弱化为目视。

```yaml
verify:
  - sc_ref: SC-7.1
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE 'REVIEW_LENS_EMPHASIS|codex_A|codex_B' scripts/gd-review-controller.py | wc -l"
    expect: ">=2"
  - sc_ref: SC-7.1
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE '行号|line|±3|line_window|dedup|去重' scripts/gd-review-controller.py | wc -l"
    expect: ">=1"
  - sc_ref: SC-7.2
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE 'mapped|findings\\[|json\\.load|gd_review_decision|review_run_status' scripts/gd-review-controller.py | wc -l"
    expect: ">=1"
  - sc_ref: SC-7.2
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 -c \"import re,io; src=open('scripts/gd-review-controller.py',encoding='utf-8').read(); bad=re.findall(r'(re\\.search|re\\.findall|re\\.match)\\([^)]*(VERDICT|REV_VERDICT|P1|P2|finding)', src, re.I); print(len(bad))\""
    expect: "0"
  - sc_ref: SC-7.3
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE 'git stash create|stash create|snapshot|blob' scripts/gd-review-controller.py | wc -l"
    expect: ">=1"
  - sc_ref: SC-7.3
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 -c \"import re; src=open('scripts/gd-review-controller.py',encoding='utf-8').read(); print(len(re.findall(r'git[\\\"\\' ]+commit', src)))\""
    expect: "0"
  - sc_ref: SC-7.4
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE 'CONVERGENCE_TIMEOUT' scripts/gd-review-controller.py | wc -l"
    expect: ">=1"
  - sc_ref: SC-7.4
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 scripts/gd-review-controller.py --selftest convergence_timeout; echo \"exit=$?\""
    expect: "CONVERGENCE_TIMEOUT"
  - sc_ref: SC-7.4
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -c 'DELIVERABLE_BLOCKED' scripts/gd-review-controller.py"
    expect: "0"
  - sc_ref: SC-7.5
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -nE 'round2-fanout-threshold-lines|round2-fanout-threshold-files|round2_fanout_threshold' scripts/gd-review-controller.py | wc -l"
    expect: ">=2"
  - sc_ref: SC-7.5
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 scripts/gd-review-controller.py --selftest d7_large_delta_fanout; echo \"exit=$?\""
    expect: "exit=0"
  - sc_ref: SC-7.6
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 scripts/gd-review-controller.py --selftest branch_b_convergence_timeout; echo \"exit=$?\""
    expect: "CONVERGENCE_TIMEOUT"
  - sc_ref: SC-7.7
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -cE 'REVIEW_ROUND|BASELINE_FINDINGS|DELTA_SCOPE|SCOPE_CONSTRAINT' scripts/gd-review-controller.py"
    expect: ">=4"
  - sc_ref: SC-7.7
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 scripts/gd-review-controller.py --selftest round2_capsule_fields; echo \"exit=$?\""
    expect: "exit=0"
  - sc_ref: SC-7.8
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 scripts/gd-review-controller.py --selftest h5_no_silent_resolve; echo \"exit=$?\""
    expect: "exit=0"
  - sc_ref: SC-7.9
    method: command
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -n ephemeral scripts/gd-review-controller.py | wc -l"
    expect: ">=1"
  - sc_ref: SC-7.9
    method: path
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 -m json.tool schema/gd-baseline-findings.schema.json > /dev/null && echo VALID_JSON"
    expect: "VALID_JSON"
  - sc_ref: SC-7.9
    method: assertion
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && grep -cE 'baseline_unresolved|new_in_delta|APPROVED' scripts/gd-review-controller.py"
    expect: ">=2"
  - sc_ref: SC-7.9
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 scripts/gd-review-controller.py --selftest branch_c_rerun_after_simplify; echo \"exit=$?\""
    expect: "exit=0"
```

> 实现约定（供子 agent 落地，使上述 verify 可跑）：
> - controller 须实现 `--selftest <name>` 子命令，内置以下 selftest（用临时目录 + 桩 mapped JSON / 桩 codex 调用，不依赖真实 codex 网络）：`convergence_timeout`（连续 2 轮 baseline_unresolved 不减 → 打印 `CONVERGENCE_TIMEOUT` 且 exit≠0）、`d7_large_delta_fanout`（构造 delta>阈值 → dispatch=2，delta<阈值 → dispatch=1，断言通过则 exit 0）、`branch_b_convergence_timeout`（分支 B 同 timeout）、`round2_capsule_fields`（断言 Round2 capsule 含四字段且 `REVIEW_ROUND>=2`）、`h5_no_silent_resolve`（构造 codex 不认同但 codex_B 提过的 finding，断言不被判 resolved）、`branch_c_rerun_after_simplify`（断言 simplify 后 B 收到的执行结果 mtime 晚于 simplify）。
> - selftest 必须用桩（stub）模拟 codex dispatch 计数与 mapped findings 注入，**不真实联网调 codex**；dispatch 计数断言（Round1=2 / Round2=1 / 大 delta=2）在 selftest 内通过 monkeypatch / 计数器实现。
> - `git stash create` 在干净工作树会输出空 → 实现须处理空快照回退（fallback 到 `HEAD` tree 或 changed-file blob hash），selftest 在临时 git repo 内构造改动后再取快照。
> - codex CLI 不可用（无 `codex` 二进制）时 selftest 走桩，不因环境缺二进制而失败；真实多轮循环跑在 `/review2 code` 编排里，由 router 注入 `GD_REVIEW_ROUTER_INVOCATION_ID` 后驱动。

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t7-controller-baseline-convergence-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论：controller 实现 Round1 双 codex 并集建 baseline + Round2+ 单 codex 重喂三字段对账 + git stash 快照 delta 不 commit + CONVERGENCE_TIMEOUT + D7 大 delta 降级 + 直调 codex --ephemeral + baseline schema 校验通过>
  blockers: <未完成的依赖或外部阻塞，例如 T5 三档判定脚本接口未定 / T6 bridge target 未修导致 mapped findings 仍指 capsule / 环境无 codex 二进制（selftest 走桩不阻断，真实循环阻断）>
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 task 的 `owned_paths`（`prompts/gd-review-standard.md`、`scripts/gd-codex-bridge-review.py`、`scripts/gd-validate-review2-plan-target.py` 等），以及 `commands/review2.md` 中 T5 入口解析段与 T8 终点打包段
- 禁止 **读取** 未完成 task 的 `owned_paths`，除非该 task 已完成且其 deliverables 列入本 packet `required_context`（详见 §4 读取权限分层）
- 禁止改 `scripts/gd-codex-bridge-review.py` 源码——controller 只**消费**其 mapped JSON 输出
- controller **不自己正则解析 codex raw 文本**（findings 一律来自 bridge 已 schema 校验的 mapped JSON，堵 H3）
- controller **全程不 commit**（delta 用 `git stash create` 工作树快照对比，守 spec §5；不污染 T8 要打包的提交历史，堵 H2）
- `CONVERGENCE_TIMEOUT` 与 `DELIVERABLE_BLOCKED` 是两个不同状态码——controller 只输出前者，绝不输出后者（后者属 T8 终点 gate，堵状态码混用）
- 禁止访问 `/Users/praise/.claude/**`
- 禁止启动 daemon、注册 hook、修改 cron（controller 是被 `/review2 code` 同步调用的脚本，非常驻进程）
- 禁止用对话上下文替代 `required_context`
- 不改 L3 `/gd review` 语义、不动旧 `/review`/`/rev`/`codex-watch` daemon（守 spec §5 边界）
- 不在 `/review2` / controller 输出裸 `VERDICT:`（用 `REV_VERDICT`/`GD_REVIEW_DECISION`，避免触发 live hook regex）
- anti-fill：SC 与 verify 禁止用"完善/优化/系统性/全面/增强"占位；每条 SC 必带可执行断言或 selftest
```
