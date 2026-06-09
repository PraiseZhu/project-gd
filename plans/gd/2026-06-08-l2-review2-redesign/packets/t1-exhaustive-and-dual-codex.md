# Task Packet: t1-exhaustive-and-dual-codex

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t1-exhaustive-and-dual-codex
agent_role: implementer
parent_step: T1
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T15:03:25Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表（ref GOAL_SOURCE）
CHAIN_GOAL:   让 L2(/review2) 成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交（ref GOAL_SOURCE）
PHASE_GOAL:   为 L2 spec T1-T9 各产出可被 /gd execute 消费的自包含 task packet；本 packet 实现 spec §3 的 T1（ref master-plan.md SC-1）
TASK_GOAL:    在 prompts/gd-review-standard.md 增加"穷举强制"段，使 reviewer 必须一次列全所有可发现 finding（明知多处只报一条 = degraded）；在 scripts/gd-codex-bridge-review.py 的 capsule 新增 REVIEW_LENS_EMPHASIS 字段，并实现 Round 1 双 codex（codex_A/codex_B 不同 emphasis）+ Claude self-review 三方 findings 并集去重，使 baseline 不因单 reviewer 漏检而漏掉问题。
```

---

## 3. 依赖与并发

```yaml
blocked_by: []
can_parallel_with:
  - t3
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md   # 实现权威源：§1 F4、§2.3 无状态不变量、§2.4 D4 双 reviewer 并集 + H5、§3 T1 段
  - prompts/gd-review-standard.md                          # 被改文件之一：需在此追加"穷举强制"段
  - scripts/gd-codex-bridge-review.py                      # 被改文件之一：build_capsule_text(922 起) Reviewer Instructions(1059) + capsule 字段(REVIEW_FOCUS:999 / REVIEW_ROUND:1002)
```

---

## 4. 路径权限

```yaml
owned_paths:
  - prompts/gd-review-standard.md
  - scripts/gd-codex-bridge-review.py
forbidden_paths:
  - "/Users/praise/.claude/**"
  - 旧 /rev artifacts
  - commands/review2.md                                    # T5 owned，本任务不碰
  - scripts/gd-validate-review2-plan-target.py             # T4 owned
  - scripts/gd-review-router.py                            # T7 owned
  - scripts/gd-review-controller.py                        # T7 owned（新增）
  - schema/gd-baseline-findings.schema.json                # T7 owned（新增）
  - Project GD/templates/plan-mode-template.md             # T3 owned（新增）
  - .deploy-manifest.jsonl                                 # T9 owned
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（`prompts/gd-review-standard.md`、`scripts/gd-codex-bridge-review.py`）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许读取以下三类，超出此范围视为越界：
  1. `required_context` 列出的文件
  2. 已完成的 `blocked_by` task 的 deliverables（本任务 `blocked_by: []`，无此类）
  3. 公共只读资源（GOAL_SOURCE、GD_STANDARD、master-plan.md、lock files、schema）
- T3 可并行（`can_parallel_with: [t3]`），但 T3 的 `owned_paths`（plan-mode 模板）禁止读写。

---

## 5. 成功标准（SC）

> 本 packet 对应 master-plan SC-1。下列 SC-1.1 ~ SC-1.3 是 SC-1 的可验证子条件，全部 pass 才算 SC-1 达成。

- [ ] SC-1.1（穷举强制段）：`prompts/gd-review-standard.md` 新增一段标题含"穷举"或"一次列全"的小节，正文必须同时表达两层语义：(a) reviewer 须扫完 target 内全部 SC / 模块 / fallback 路径并**一次列全**所有可发现 finding；(b) 明知有多处问题却只报一条 = 协议违规，判定 `degraded`。验收命令见 §7 verify SC-1.1。
- [ ] SC-1.2（capsule REVIEW_LENS_EMPHASIS 字段 + 同步穷举指令）：`scripts/gd-codex-bridge-review.py` 的 `build_capsule_text` 生成的 capsule 文本含 `REVIEW_LENS_EMPHASIS` 字段；其值由调用方传入的 emphasis 决定（支持 `codex_A` / `codex_B` / 中性三种），且 Reviewer Instructions 区追加与 SC-1.1 一致的"一次列全 / 明知多处只报一条=degraded"指令句。验收命令见 §7 verify SC-1.2。
- [ ] SC-1.3（Round 1 双 codex + Claude self-review 三方并集）：实现使 Round 1 并行发 2 个 codex（`codex_A` emphasis = SC-conformance→边界/路径越界→接口/契约→失败模式/fallback→anti-fill 泛化；`codex_B` emphasis = 失败模式/fallback→安全/secret 泄漏→anti-fill 泛化→SC-conformance→边界/路径越界），两 capsule 唯一差异为 `REVIEW_LENS_EMPHASIS`；三方（codex_A、codex_B、Claude self-review）findings 取并集后去重（键：文件 + 行号±3 + 类别，严重度取高）→ baseline。代码须含可被单测覆盖的并集去重函数；构造 codex_A 漏报 / codex_B 命中的 fixture，并集 baseline 必含该 finding。验收命令见 §7 verify SC-1.3。

---

## 6. 交付物

```yaml
deliverables:
  - path: prompts/gd-review-standard.md
    kind: file
    must_exist: true
    description: 新增"穷举强制"小节（reviewer 必须一次列全；只报一条=degraded）
  - path: scripts/gd-codex-bridge-review.py
    kind: file
    must_exist: true
    description: build_capsule_text 新增 REVIEW_LENS_EMPHASIS 字段 + Reviewer Instructions 追加穷举指令；新增 Round 1 双 emphasis lens 生成 + 三方 findings 并集去重函数
  - path: handoff_output（见 §8）
    kind: report
    must_exist: true
    description: 子 agent 执行结果，含每条 SC 的 verify 命令真实输出
```

---

## 7. 验证（Anti-fill 硬约束）

> 每条 SC 绑定可执行命令 / 路径 / 断言 / 测试。执行后必须在 handoff_output 贴真实输出。
> 下列命令均在工作目录 `/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity` 下运行。

```yaml
verify:
  - sc_ref: SC-1.1
    method: command
    cmd: "grep -nE '穷举|一次列全' prompts/gd-review-standard.md"
    expect: ">=1 行命中（exit 0）"
  - sc_ref: SC-1.1
    method: assertion
    cmd: "grep -nE 'degraded|协议违规' prompts/gd-review-standard.md"
    expect: ">=1 行命中——证明'只报一条=degraded'语义存在（exit 0）"
  - sc_ref: SC-1.2
    method: command
    cmd: "grep -q REVIEW_LENS_EMPHASIS scripts/gd-codex-bridge-review.py && echo PASS"
    expect: "PASS"
  - sc_ref: SC-1.2
    method: assertion
    cmd: "grep -nE '一次列全|穷举|exhaustive' scripts/gd-codex-bridge-review.py"
    expect: ">=1 行命中——证明 capsule Reviewer Instructions 同步追加了穷举指令（exit 0）"
  - sc_ref: SC-1.3
    method: assertion
    cmd: "grep -nE 'codex_A|codex_B' scripts/gd-codex-bridge-review.py"
    expect: ">=2 行命中——证明两个 emphasis lens 在代码中定义（exit 0）"
  - sc_ref: SC-1.3
    method: test
    cmd: "python3 -c \"import ast,sys; src=open('scripts/gd-codex-bridge-review.py').read(); ast.parse(src); print('SYNTAX_OK')\""
    expect: "SYNTAX_OK（改完语法可解析，不引入 SyntaxError）"
  - sc_ref: SC-1.3
    method: test
    cmd: "cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && python3 -m pytest tests/ -k 'lens_emphasis or union or dual_codex' -q 2>&1 | tail -5"
    expect: "若已有/新增对应单测（双 lens emphasis 顺序、三方并集去重）则全绿；fixture: codex_A 漏报 + codex_B 命中的 finding 必须出现在并集 baseline 中（行号±3 同类去重，严重度取高）"
```

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t1-exhaustive-and-dual-codex-result.md
  status_field: <见 gd-execution-status.schema.json：completed | blocked | partial>
  summary: <一句话结论，例如：review-standard 增穷举强制段、bridge 加 REVIEW_LENS_EMPHASIS 字段与双 codex 三方并集去重，全部 verify 命令真实输出已贴>
  blockers: <未完成的依赖或外部阻塞；无则写 none>
```

handoff 必须贴 §7 全部 7 条 verify 命令的真实输出（命令 + stdout/exit code），不得只写"已验证 / 通过"。

---

## 9. 范围禁令

- 禁止 **写入** §4 `owned_paths` 之外任何路径（尤其 T3/T4/T5/T7/T9 的 owned）。
- 禁止 **读取** 其他 task 的 `owned_paths`，除非该 task 已完成且其 deliverables 列入本 packet 的 `required_context`（本任务 `required_context` 不含任何其他 task 产物）。
- 禁止访问 `/Users/praise/.claude/**`。
- 禁止启动 daemon、注册 hook、修改 cron。
- 禁止用对话上下文替代 `required_context`。
- **anti-fill 行为禁令**：实现步骤动作不得只写"完善 / 优化 / 系统性 / 全面 / 增强"等泛词；新增的 review-standard 文本与 capsule 指令本身也须给出具体可核验语义（"一次列全""明知多处只报一条=degraded""codex_A/codex_B emphasis 各自维度顺序"），不得写空泛要求。
- **范围边界**：本 packet 只做 (1) review-standard 穷举强制段 (2) capsule REVIEW_LENS_EMPHASIS 字段 + 同步穷举指令 (3) Round 1 双 codex emphasis lens 生成 + 三方并集去重函数。不实现 T7 的 controller 编排 / baseline_findings.json 持久化 / Round 2+ 收敛判定 / 大 delta 降级（D7）——那些是 T7 owned。本 packet 仅提供 T7 将复用的 lens emphasis 定义与并集去重原语。
