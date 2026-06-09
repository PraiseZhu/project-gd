# L2(/review2)审查工作流重设计 Spec

GD_STANDARD: Project GD/prompts/gd-review-standard.md
TEMPLATE_KIND: gd-spec

> 日期：2026-06-07
> 状态：draft（D1/D2/D3 已拍板，待逐项实现）
> 作者：用户决策 + Claude 汇总
> 工作树：`Project GD/.claude/worktrees/gd-l2-parity`（branch `gd-l2-parity`，base = feature/gd-v2-self-contained HEAD）
> 记忆映射：`priority/project_gd_l2_review_workflow_redesign.md`

---

## 0. 目标链

```
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表
CHAIN_GOAL:   让 L2(/review2)成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交
PHASE_GOAL:   /review2 拆成 plan/code 两入口；plan 有强制填 WHAT 硬门；code 走 code-review+交叉验证固定循环；统一产出可直接 commit/MR 的交付物
TASK_GOAL:    本 spec 9 项任务全部实现并通过各自 verify，且部署到 live 后 source==installed
```

## 1. 背景与已确认问题（代码核实，非推测）

| ID | 问题 | 证据（文件:行 / 函数） |
|----|------|----------------------|
| F1 | L2 仅 `plan_review` 端到端正确 | `gd-codex-bridge-review.py:1199-1209` 守卫 `kind==plan` 强制 target=原始计划 |
| F2 | **code_diff 路 P0**：Codex 审 capsule 信封非代码 | `build_capsule_text` 第 999 行 `REVIEW_FOCUS: bridge candidate review of {target.name}`、1031 行 `PRIMARY_TARGET: {target_abs}`；`/review2 code_diff` 传 `--target capsule.md` |
| F3 | 根因=未做完的脚手架 | 同函数行内写死 `bridge candidate via Plan 6.5-B` / `KNOWN_LIMITATIONS: bridge candidate; not active`；review 标准 §8 自述 "bridge candidate；code active 升级由 Plan E 完成" |
| F4 | 审查标准无穷举强制 | `prompts/gd-review-standard.md` §2-§4 无"一次列全"要求 → reviewer 一轮一条不违规 |
| F5 | plan 模板与 goal 提取错配 | live `~/.claude/templates/plan-template.md`(V3)成功标准是无 ID 勾选框、无 verify/expect；`~/.claude/skills/goal/SKILL.md` 按 `SC-*` 结构提取 |
| F6 | 内置 /code-review 只做质量/bug 不看意图 | `~/.claude/commands/code-review.md` + codex 版均无"对照计划 SC"；conformance 是 GD 独有 |
| F7 | token 黑洞是轮数不是交叉验证本身 | 用户实测 12 轮 ping-pong；轮数 × capsule × reasoning 主导成本 |

## 2. 目标架构

### 2.1 三入口统一终点

```
【动手前】/review2 plan <plan-file>
  Step1 anti-fill 硬门(成功标准缺验收命令/expect泛词 → 拒审 exit≠0,不送)
  Step2 build capsule(plan 为 PRIMARY_TARGET) → Claude self-review + Codex cross-review(必须一次列全)
  Step3 REQUIRES_CHANGES → 用户改计划 → 回 Step1；APPROVED → 输出「确定版计划」+ baseline

【动手后】/review2 code   (自动判定三档,判完告诉用户确认)
  Step0 自动判定:
    git diff 有改动? → has_code = true
    发现执行产物文件? → has_result = true
    判定结果: code-only / execution-only / combined
    输出判定结果 + 依据,用户可覆盖(--code / --result / --combined)
  分支 A · 仅代码(code-only):
    LOOP { (a)/code-review 找 bug → (b)修 → (c)Claude+Codex 只验 conformance }
         (c) REQUIRES_CHANGES → 回 (a)；APPROVED → 退出 LOOP
    → /simplify 清理 → 重跑测试/验收(必须绿,红则回 LOOP) → 打包交付物
  分支 B · 仅执行结果(execution-only):
    LOOP { Claude+Codex 验执行结果是否符合计划(重跑 verify 命令) → 不符则修 } 直到 APPROVED
    → (不跑 simplify) → 打包交付物
  分支 C · 代码+执行结果(combined):
    先走分支 A 全流程(含 LOOP + simplify + 重测)
    → 再走分支 B 验证执行结果 vs 计划 SC
    → 两路都 APPROVED → 打包交付物

【统一终点】交付物 = tests/verify 全绿 + 每条 SC 有证据 + commit/MR 草稿
           → 交用户 / 接 commit-projects | submit-mr；**不自动 commit/push**
           → 任一 gate 不绿:报阻塞,不产出"成品"
```

### 2.2 关键契约
- **simplify 位置**：分支 A 的 LOOP 通过后、最终重测前；分支 B 不跑。clean 后必重测（behavior-preserving 也要验证）。
- **conformance scoping**：code 交叉验证 capsule 必须显式声明"代码质量已由 /code-review 上游处理，本轮只验是否符合计划 SC，不重复找 bug"——缩小范围以省轮数。
- **强制填 WHAT**：模板被动、硬门主动。门是唯一强制点：不过门不准进入审查/执行。
- **fail-visibly**：交付物只在全部 gate 绿时产出；否则列出阻塞项（红测试/未收敛/缺证据），不得包装成"可提交"。

### 2.3 Capsule 分容 + 上下文隔离契约（codex 无状态保证）

**无状态不变量（代码核实，本设计依赖它）**
- 每次 review = 1 个 job（`codex-send` 生成独立 job_id，各自 status/result/stderr）= 1 次全新 `codex exec --sandbox <s> --skip-git-repo-check --ephemeral --cd <cwd>`（`vendor/l3-transport/handoff/bin/codex-watch:453`）。
- `--ephemeral` = 抛弃式进程：无 conversation 持久、无 resume、无 `--session`/continue。
- 结论：**每次发给 codex 的任务天然独立；codex 接新任务前上下文自动清空——由 `--ephemeral` 进程边界保证，不依赖提示词。** 跨轮/跨 job 零累积。

**上下文预算（防爆炸，三道）**
1. target 外置（L1）：capsule 不内联被审全文，codex 按需 Read；单次 capsule ≈ standard(~12KB)+kind 模板(2-3KB)+goal 摘要(3000 字符) ≈ **21KB 有界**。
2. 多文件用 `RELATED_CONTEXT` 的 path/hash 摘要（`_related_context_summary`），不内联 → combined/bundle 不撑爆。
3. 无状态 → 不累积：N 轮 LOOP = N 次独立 21KB+按需 Read，**非 21KB×N 滚雪球**。

**按 kind 分容（结果审核 vs 代码审核）** — 由 T6 落实

| kind | 入口 | PRIMARY_TARGET | 嵌入模板 | VERIFY STEP | focus 声明 |
|------|------|---------------|---------|:---:|-----------|
| plan | /review2 plan | 原始计划文件 | plan 模板 | 否 | 审计划完整性+anti-fill |
| code_diff | /review2 code(三档:code-only) | **真实 diff**（修 T6 前=错误指向 capsule） | code 模板 | 否 | **质量已由 /code-review 处理，只验 conformance** |
| execution_outcome | /review2 code(三档:execution-only) | 执行结果产物 | execution 模板 | **是**（重跑 deliverable/verify） | 只验执行结果 vs 计划 SC |
| combined | /review2 code(三档:combined) | 真实 diff（+执行结果走 RELATED_CONTEXT） | combined 模板 | **是** | conformance（质量上游已处理） |

> 现状缺口：今天 `build_capsule_text` 对 kind 的差异只有"模板+标题+VERIFY STEP"三点，PRIMARY_TARGET 单槽与 focus 声明未按职责分容；本表是 T6 的目标态。

**LOOP 轮次上下文（无状态的代价）** — 由 T7 落实
- codex 失忆：每轮从零审、不知上轮发现/已改什么；现 `REVIEW_ROUND: initial` 写死（`build_capsule_text:1002`）。
- T7 须在每轮 capsule 注入：`REVIEW_ROUND: N` + 上轮 findings 摘要（已修/未修）+ 本轮 delta scope（只看变更面）；否则每轮全量重审，与 T1 穷举叠加放大 token。

**§2.3 验收**
- `grep -n "ephemeral" vendor/l3-transport/handoff/bin/codex-watch` 命中（无状态不变量成立）。
- 修 T6 后：execution_outcome 与 code_diff 的 capsule `PRIMARY_TARGET` 分别指向执行产物 / 真实 diff（assertion）。
- 修 T7 后：第 2 轮起 capsule 含 `REVIEW_ROUND: 2`（非 initial）+ 上轮 findings 摘要（assertion）。

### 2.4 Baseline 收敛机制（防 token 爆炸 + 防挑刺漂移）

**核心思路：第一轮建基线，后续轮次只对账**

```
Round 1 (全盘审查):
  - Codex 审全量代码 + 计划 SC
  - 输出结构化 findings 清单（文件:行号 | 问题描述 | 严重度）
  - 脚本解析 → 存入 baseline_findings.json

Round 2+ (收窄审查):
  - capsule 注入:
    * REVIEW_ROUND: N
    * BASELINE_FINDINGS: 上轮清单 + 状态（已修/未修）
    * DELTA_SCOPE: git diff 变更摘要（只含改动行）
    * SCOPE_CONSTRAINT: "只验修复 + 查 delta 新引入，禁止重审未改动代码"
  - Codex 只需看 delta + 验证修复，工作量递减

收敛判定:
  - unresolved = 0 且 new_findings_in_delta = 0 → APPROVED
  - 连续 2 轮 unresolved 不减 → DELIVERABLE_BLOCKED（防死循环）
```

**实现要点（T7 controller 脚本）**
- **gd-review-controller.py**：解析 Codex 输出（正则提取 findings）→ 生成 delta（git diff）→ 组装下轮 capsule → 判定退出条件
- **findings 提取不靠 LLM**：Codex 输出格式固定（`[severity] file:line — description`），用正则解析
- **delta 自动算**：`git diff HEAD~1`（每轮修完 commit 一次）
- **防死循环**：连续 2 轮 findings 数量不减 → 报错退出，不无限烧 token

**收敛效果预期**
```
Round 1: 全盘审 → 5 个问题
Round 2: 验 5 修复 + 查 delta → 4 修好，1 未修对 + delta 引入 1 新 → 剩 2
Round 3: 验 2 修复 + 查 delta → 全修好，无新 → APPROVED
```
**3 轮收敛**，而非 12 轮 ping-pong。

**§2.4 验收**
- Round 1 capsule 无 `REVIEW_ROUND` 或 `REVIEW_ROUND: 1`，输出 baseline_findings.json（assertion）
- Round 2 capsule 含 `REVIEW_ROUND: 2` + `BASELINE_FINDINGS` + `DELTA_SCOPE`（assertion）
- 连续 2 轮 findings 不减 → 脚本 exit≠0 + `CONVERGENCE_TIMEOUT`（test）

---

## 3. 任务规格（T1–T9）

> 验收方法标注 `method: command|path|assertion|test`；动 live 项需用户显式授权 + ledger。

### T1 · 审查标准"一次列全"强制 〔在仓库,价值高〕
- WHERE: `prompts/gd-review-standard.md`；`gd-codex-bridge-review.py:build_capsule_text` 的 Reviewer Instructions(1059-1069)
- WHAT: 新增 §"穷举强制"——reviewer 必须扫完 target 内全部 SC / 模块 / fallback 路径，**一次列全**所有可发现 finding；明知有多处只报一条 = 协议违规(degraded)。capsule 指令同步加该句。
- WHY: F4/F7——一轮一条是 ping-pong 一半根因；穷举直接决定 #T7 LOOP 收敛速度。
- VERIFY: `grep -n "穷举\|一次列全\|exhaustive" prompts/gd-review-standard.md` 命中；新增 fixture(一个含 ≥3 处问题的 target)经 reviewer 应一次返回 ≥3 finding（smoke）。

### T2 · 送审前"本地跑通(含 fallback)"门 〔在仓库,价值中〕
- WHERE: `/review2` 编排层（review2.md）+ 一个 preflight 脚本
- WHAT: 送 Codex 前必须存在"所有生产路径(含 fallback / 无 API key)已本地跑通"的证据文件；缺失 → `DRYRUN_EVIDENCE_MISSING` exit≠0，不送。
- WHY: 用户复盘 R1b/R4/R6——校验器与 fallback 自相矛盾，本地跑一次即可拦，不该让 Codex 替跑。
- VERIFY: 无证据时 `bash <preflight>` 返回非零 + 打印 `DRYRUN_EVIDENCE_MISSING`；有证据时放行（test）。

### T3 · 更新 plan mode 模板 〔动 live,价值高,已授权〕
- WHERE: `~/.claude/templates/plan-template.md`（live，PLAN_TEMPLATE_V3）
- WHAT: "成功标准"段从无 ID 勾选框 → 每条 `SC-N` + `verify (method: command|path|assertion|test): <命令>` + `expect: <字面输出串/exit code>`；"实施步骤"补 `WHERE/WHAT/WHY/VERIFY` + SC 映射。结构对齐 `Project GD/templates/plan-template.md`。
- WHY: F5——让 plan mode 产出可被 `goal` skill 提取的 SC，执行有可验收锚。
- VERIFY: `grep -E "SC-[0-9]|verify \(method|expect:" ~/.claude/templates/plan-template.md` 命中；用该模板出一份样例计划，`goal` skill 能提取出非空 SC 清单（test）。
- ✅ D2 已拍板：用户授权改全局模板，影响所有项目 plan mode。

### T4 · 强制填 WHAT 硬门 〔在仓库,价值高〕
- WHERE: `scripts/gd-validate-review2-plan-target.py`（强化现有 preflight）
- WHAT: 在现有 SC-ID / WHERE-WHAT-WHY-VERIFY 校验基础上新增：每条成功标准必须含可执行 `verify`(命令/路径/断言/测试) 且 `expect` 不得为泛词黑名单(`通过|正确|完成|works|pass|ok|成功`无具体串)；违反 → `PLAN_ANTIFILL_FAIL` exit≠0。设为 `/review2 plan` 强制第一步（可选：再加 plan mode Stop hook 做到普通 plan mode 也拦）。
- WHY: F5/项目核心——模板是被动的，硬门才是"最高优先级强制填 WHAT"的真正实现。
- VERIFY: 喂含泛词 expect 的 fixture → 脚本 exit≠0 + `PLAN_ANTIFILL_FAIL`；喂合规 fixture → exit 0（test，5 类正/负 fixture）。

### T5 · 拆 /review2 plan 与 /review2 code（三档判定+确认） 〔在仓库,价值中〕
- WHERE: `commands/review2.md` 入口解析 + 相关 stage 路由 + 新增判定脚本
- WHAT: 入口从 `--profile` 改子命令：`/review2 plan` = 原 plan_review；`/review2 code` = 动手后审查，**自动判定三档**后告知用户确认：
  - `git diff` 有改动 → has_code = true
  - 发现执行产物文件（测试结果/输出日志/产物目录）→ has_result = true
  - 判定结果: code-only / execution-only / combined
  - 输出判定结果 + 依据，用户可 `--code` / `--result` / `--combined` 覆盖
  - `release_closure`/`runtime_parity` 保留为 `/review2 release` / `/review2 parity`（或暂留 flag）。
- WHY: 一个命令混计划/代码/执行结果三种语义，使用者说不清在审什么。自动判定 + 确认机制兼顾省事和准确。
- VERIFY: `/review2 plan <plan>` 走计划路；`/review2 code` 在有/无代码/有代码+产物三种 git 状态下分别进入对应分支并输出判定确认（test）。

### T6 · 修 bridge:真 artifact 当 target 〔在仓库,价值高〕
- WHERE: `scripts/gd-codex-bridge-review.py:build_capsule_text`(922-1072) + `cmd_run_bridge`(1177-1215)
- WHAT: code/执行结果路与 plan 路对称——真实 diff / 执行结果文件当 `PRIMARY_TARGET`，L2 capsule 降为 `RELATED_CONTEXT`；`REVIEW_FOCUS` 按 kind 动态生成（去掉写死的 "bridge candidate review of"）。⚠️ `combined`/`execution_outcome` 经 `gd-review-router.py`(env `GD_REVIEW_ROUTER_INVOCATION_ID`)进入，**实现时先 trace 确认 router 的 target 传递是否同病**，再决定是否一并修。
- WHY: F2/F3——现状 Codex 审信封非代码，交叉验证空转；LOOP 里审错对象永不收敛。
- VERIFY: `/review2 code` 触发后，发给 Codex 的 capsule 中 `PRIMARY_TARGET` 指向真实 diff 而非 capsule.md；coverage 校验不再 `diff → MISSING`（smoke，断言 capsule 文本）。

### T7 · /review2 code 循环状态机 + Baseline 收敛 〔在仓库,价值高,依赖 T6〕
- WHERE: `commands/review2.md` 编排 + `scripts/gd-review-router.py` / **新增 `scripts/gd-review-controller.py`**；复用 `gd-validate-execution-outcome.py` 与 bridge `execution_outcome|combined` kind（已含重跑 verify 的 MANDATORY VERIFY STEP，build_capsule_text:1048-1056）
- WHAT: 实现 §2.1 分支 A/B/C 状态机 + §2.4 baseline 收敛机制。

  **gd-review-controller.py 职责**（D3 已拍板：Python 脚本，非 Claude 编排）：
  - Round 1：发全量代码 + 计划 SC 给 Codex → 解析返回 → 提取结构化 findings → 存 `baseline_findings.json`
  - Round 2+：自动组装 capsule：`REVIEW_ROUND: N` + `BASELINE_FINDINGS`（上轮清单+状态）+ `DELTA_SCOPE`（git diff HEAD~1）+ `SCOPE_CONSTRAINT`（只验修复+查 delta，禁止重审未改动代码）
  - 判定退出：unresolved=0 且 new_in_delta=0 → APPROVED；连续 2 轮 findings 不减 → `CONVERGENCE_TIMEOUT` exit≠0
  - `/code-review` 和 `/simplify` 触发方式：脚本直调 codex CLI（`codex exec --ephemeral`），不走 Claude 编排

  **分支 A LOOP** = `[/code-review 找 bug → 修 → conformance 交叉验证]`，conformance REQUIRES_CHANGES 则整组重跑（含重跑 /code-review）
  **分支 B LOOP** = 仅 conformance
  **分支 C** = 先 A 全流程（含 LOOP + simplify + 重测）→ 再 B

  交叉验证 capsule 注入 conformance-scoping 声明（见 §2.2）。

- WHY: 指令 6b + F6/F7——质量与 conformance 分离、缩范围降轮数。baseline 收敛解决 codex 无状态导致的 token 爆炸和挑刺漂移。
- VERIFY:
  - 构造"代码不符合计划"fixture → LOOP 至少一轮 REQUIRES_CHANGES 后修正再过（test）
  - 构造"执行结果不符"fixture → 分支 B 循环至 APPROVED（test）
  - Round 1 输出 baseline_findings.json（assertion）
  - Round 2 capsule 含 `REVIEW_ROUND: 2` + `BASELINE_FINDINGS` + `DELTA_SCOPE`（assertion）
  - 连续 2 轮 findings 不减 → 脚本 exit≠0 + `CONVERGENCE_TIMEOUT`（test）
  - `grep -n "ephemeral" scripts/gd-review-controller.py` 命中（直调 codex CLI）

### T8 · 终点交付物打包 〔在仓库,价值高〕
- WHERE: `/review2 code` 终点 stage（review2.md + 打包脚本）
- WHAT: 全 gate 绿(conformance APPROVED + 测试绿 + 分支A 的 post-simplify 重测绿)后产出：① `git add` 已 stage 的改动 ② SC 逐条证据表(命令+真实输出) ③ commit message / MR description 草稿；接 `commit-projects` / `create-mr`+`submit-mr`。**不自动 commit/push**。任一 gate 不绿 → 输出 `DELIVERABLE_BLOCKED` + 阻塞清单，不产出成品。
- WHY: 用户要"直接能提交 mr/commit 的交付物"，省去每次自核状态 + 手写 message。
- VERIFY: 全绿路径产出含"草稿 + SC 证据表 + 已 stage"三件套且工作树 tests 绿；任一 gate 红 → 输出 `DELIVERABLE_BLOCKED`，无成品（test 正/负）。

### T9 · 部署 live + 修 parity 漂移 〔动 live,价值高,需授权〕
- WHERE: `.deploy-manifest.jsonl` + `deploy live` skill
- WHAT: 全部改完后 `deploy live` 回灌 `review2.md` / `gd-codex-bridge-review.py` / 各校验器 / 缺失的 `gd-validate-review2-plan-target.py`（补进 manifest）；修 review2.md installed 的 `scripts/`→`tools/` 路径漂移。
- WHY: 当前 live 是 v8 之前旧版且 parity 断；不部署，T1-T8 全在 feature 分支不生效于真实 `/review2`。
- VERIFY: 部署后 `diff` source==installed 全一致；`tools/gd-parity-verify.sh --bundle review2_command` 通过（command）。

---

## 4. 依赖图与建议顺序

```
T1 ─┐                         (穷举强制直接加速 T7 收敛)
T2 ─┤  阶段1: 便宜,救计划审查轮数
T5 ─┐
T3 ─┤  阶段2: plan 侧(拆命令→模板→硬门)  [T3 已授权]
T4 ─┘
T6 ──► T7 ──► T8              阶段3: code/执行结果侧(修 bridge→controller+循环→打包)
T9                            阶段4: 部署 live [需授权]
```

建议执行顺序：**T1, T2 → T5, T3, T4 → T6, T7, T8 → T9**。
硬依赖：T6 先于 T7（审错对象不收敛）；T7 先于 T8（无通过结果不打包）。
新增依赖：T5 先于 T7（controller 需要三档判定结果作为输入）。

## 5. 全局非目标与边界

- 不改 L3 `/gd review` 语义（`L3_GD_REVIEW_SEMANTICS: unchanged`）；不动旧 `/review`、`/rev`、`codex-watch` daemon。
- 不自动 commit / push（终点只产出可提交态，由用户/技能触发）。
- 不在 `/review2` 输出裸 `VERDICT:`（用 `REV_VERDICT`/`GD_REVIEW_DECISION`，避免触发 live hook regex）。
- 除 T3(plan 模板)/T9(部署)外，所有改动只落 `Project GD/**`；动 `~/.claude/**` 必须用户授权 + ledger。

## 6. 已拍板决策

| ID | 决策 | 结论 | 影响 |
|----|------|------|------|
| D1 | `/review2 code` 自动判有无代码 vs 显式标志 | **自动判定三档（code-only/execution-only/combined）+ 告知用户确认，可手动覆盖** | T5 增加判定脚本 + 确认交互 |
| D2 | T3 改全局 plan 模板 | **已授权**，影响所有项目 plan mode | T3 可直接改 `~/.claude/templates/plan-template.md` |
| D3 | T7 触发方式 | **Python 脚本直调 codex CLI**（`gd-review-controller.py`），不走 Claude 编排 | T7 新增 controller 脚本，确定性高 |

## 7. 版本记录
| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 2026-06-07 | 初始 spec：3 入口流水线 + 9 任务规格 + 依赖图，落盘自本会话决策汇总 |
| v2 | 2026-06-07 | 新增 §2.3 Capsule 分容+上下文隔离契约（codex --ephemeral 无状态不变量、上下文预算三道、按 kind 分容表、LOOP 轮次上下文）；T7 增补轮次上下文 |
| v3 | 2026-06-08 | D1/D2/D3 拍板落盘：三档自动判定+确认(D1)、全局模板授权(D2)、Python controller 直调(D3)；新增 §2.4 Baseline 收敛机制（首轮建基线+后续只对账+防死循环）；§2.1 流程改为三入口(A/B/C)；T5/T7 更新实现细节 |
