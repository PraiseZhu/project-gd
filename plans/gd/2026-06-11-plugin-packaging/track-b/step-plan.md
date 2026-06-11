# Step B: 可移植 + 写入隔离（commands 硬编码清零 / HANDOFF_ROOT 解耦 / 写产物隔离 / bundle 完整性 / 跨目录冒烟） v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-step-plan

日期：2026-06-11
状态：draft
负责人：Claude 执行；Codex 可选 cross-review

> 来源：child_planner（track-b-portability-isolation）草稿，由主 agent 持久化。

---

## 1. 目标链（继承 + 当前 task goal）

```text
PROJECT_GOAL: <ref docs/gd-v7-project-goal.md §1 — 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路>
CHAIN_GOAL:   <ref docs/gd-v7-project-goal.md — 用 shared core 固定目标链/SC/任务包/review contract/anti-fill 标准>
PHASE_GOAL:   把 /review1 /review2 /gd 三命令封装为可分发 macOS 插件（零硬编码路径、bundle 完整、传输栈前置分两段、setup 选项制预设、跨目录冒烟）
TASK_GOAL:    清零三命令文件的开发者绝对路径、把 HANDOFF_ROOT 与运行时写入隔离到插件管理/目标项目位置、建 bundle 完整性校验脚本与跨目录冒烟脚本，使 SC-002/003/004/006/007 各有可执行 verify 通过
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS（分号分隔）：`命令文件路径解析可移植性（${CLAUDE_PLUGIN_ROOT}/${CLAUDE_PROJECT_DIR} 不混淆）; HANDOFF_ROOT daemon↔client 一致性与 env 可覆盖; 运行时写产物隔离到 CLAUDE_PLUGIN_DATA/目标项目（不写插件安装目录）; bundle 完整性 blocking 校验覆盖 vendor/l3-transport; 跨目录冒烟不依赖本仓自测断言`
- Domain-specific notes：
  - 本 step 改的是命令文件与 shell 脚本的「路径解析层」，不改任一链路的 review 判定语义（归 docs/constitution.md，不在范围）。
  - SC-007 的「零命中」断言对象只能是**分发物中的开发者机器专属绝对路径**（`/Users/praise/AI-Agent/...` 与 `/Users/praise/.claude/...` 字面量）；但**作为防护语义存在**的 path-traversal 守卫字符串（gd.md:434 拒绝 deliverables 指向 `/Users/praise/.claude/**`）是安全机制，reviewer 须区分「待清零的解析路径」与「需保留的拒绝白名单字符串」——后者应改写为 `${HOME}/.claude/**` 模式匹配而非删除。

---

## 3. 前置条件

- blocked_by：`—`（track-b 独立于 track-a 的 `.claude-plugin/**` 与 setup 脚本；二者只在 bundle 完整性清单上交汇，本 step 只读 track-a 产物路径，不写）
- 必须的 baseline / artifact：
  - `commands/gd.md`、`commands/review1.md`、`commands/review2.md`（待清零源）
  - `vendor/l3-transport/handoff/lib/state-paths.sh`（HANDOFF_ROOT 第 8 行）
  - `vendor/l3-transport/scripts/review-result-writer.sh`（写产物硬编码 :51 :60 :88）
  - `vendor/l3-transport/README.md`（待解耦清单）、`.deploy-manifest.jsonl`（live 产物去向）
- Hard-stop 条件：若 `${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_DATA}` 在 Claude Code 运行时的注入行为无法在本仓验证（当前仓 0 处引用），则该假设进入 §11 Assumptions 并以 README/范本实证为准，不阻断改写但 verify 要降级为静态字符串断言而非运行时解析断言。

---

## 4. 成功标准（SC，本 step 内的）

> Anti-fill 规则 A：每条 SC 绑定命令/路径/输出断言之一。

- [ ] **SC-002**：安装后链路 runtime 引用文件（含 `vendor/l3-transport`）可解析率 = 100%（file not found = 0）。
  - verify (method: command)：`bash scripts/gd-bundle-completeness.sh --check && echo PASS`
  - expect：`PASS`（脚本对 commands/scripts/prompts/templates/schema/docs/fixtures/vendor/l3-transport 八类目标逐一存在性校验，任一缺漏 exit≠0 并列出缺失项）
- [ ] **SC-003**：在非 Project-GD 项目目录跑链路 happy path 端到端通（跨目录冒烟）。
  - verify (method: command)：`bash tests/gd-plugin-cross-dir-smoke.sh && echo PASS`
  - expect：`PASS`（脚本在临时非 GD git repo 内以 `${CLAUDE_PROJECT_DIR}` 指向该 repo，用临时 `${HANDOFF_BIN}` 下的 fixture `codex-send-wait` **真调** `review-result-writer.sh` 生成 result/baseline **实文件**到 `${CLAUDE_PLUGIN_DATA}`、退出 0；**禁止纯路径回显替代 happy path**；不读本仓任何自测断言）
- [ ] **SC-004**：缺 codex 环境下伪 APPROVED = 0 + 中文缺失提示 100%。
  - verify (method: command)：`bash tests/gd-plugin-cross-dir-smoke.sh --no-codex && echo PASS`
  - expect：`PASS`（无 codex 时 cross-review 阶段 fail-closed，输出含中文缺失提示，产物区不含通过结论字样）
- [ ] **SC-006**：插件 update 后安装者既有运行时数据保留率 = 100%。
  - verify (method: command)：`bash tests/gd-plugin-cross-dir-smoke.sh --assert-data-isolated && echo PASS`
  - expect：`PASS`（断言 reports/baselines/ledger/manifest 写入解析到 `${CLAUDE_PLUGIN_DATA}` 或目标项目，0 命中插件安装目录前缀）
- [ ] **SC-007**：**分发物运行时清单整体**开发者机器专属绝对路径出现次数 = 0（应对 Codex round-4 P1 + round-5 两 P1：scan 覆盖全文件类型含 extensionless bin 与 plist，且每个被 scan 命中的现有文件都有对应清零 owned task）。
  - **DIST_RUNTIME_PATHS（分发物运行时清单，全文件类型）**：`commands/`（gd/review1/review2/setup .md）+ `scripts/`（*.py/*.sh + scripts/lib/，**排除 P3 作废且不入 bundle 的** install-gd-command.sh / uninstall-gd-command.sh / install-review-route-command.sh / check-gd-command-parity.sh）+ `vendor/l3-transport/`（scripts/*.sh + handoff/bin/*（extensionless）+ handoff/lib/*.sh + launchagents/*.plist）。**按 spec 边界排除**：`docs/` `fixtures/` `mirrors/` `baselines/` `plans/`（历史引用 / 审计快照 / 计划产物）。
  - **被 scan 命中的现有文件 → 对应清零 owned task**（应对 round-5 P1「scan 但无清零任务」）：commands → t1；validator 脚本守卫（`gd-validate-*.py` / `gd-codex-bridge-review.py` 内 `/Users/praise/.claude` protected-runtime 守卫硬编码）→ **t4 deusername-script-guards**（脱为 `os.path.expanduser("~/.claude")`，否则守卫在安装者机器失效）；vendor scripts + plist → t2；handoff/bin/* 实测 0 命中（仅纳入 scan 作回归守卫，无清零动作）；P3 作废 install 脚本不入 bundle 故 scan 排除。
  - **统一 grep 形式（应对 Codex round-6 P1：本计划所有 SC-007 grep 共用同一形式，不混用 --include）**：grep 根 `commands scripts vendor/l3-transport` 经 `grep -rEnI` 递归即等价于显式 runtime path list —— `vendor/l3-transport` 递归覆盖 `scripts/` + `handoff/bin/`（extensionless）+ `handoff/lib/` + `launchagents/`（含 .plist）；`-I` 跳二进制；`--exclude` 掉 P3 作废脚本。全计划 SC-007 grep（§4 / §7 t3 / §10 / t4 verify / bundle packet）均用此形式，**禁止 `--include='*.ext'`（会漏 plist/bin）**。
  - verify (method: command)（不用 grep -v 排除守卫）→
    1. `! grep -rEnI '/Users/praise/(AI-Agent|\.claude)' commands scripts vendor/l3-transport --exclude='install-gd-command.sh' --exclude='uninstall-gd-command.sh' --exclude='install-review-route-command.sh' --exclude='check-gd-command-parity.sh' && echo NO_DEV_ABS`（运行时清单全文件类型含 plist/bin 零命中 → `NO_DEV_ABS`）
    2. `grep -q '\${HOME}/.claude' commands/gd.md && echo GUARD_DEUSERNAMED`（gd.md path-traversal 守卫脱用户名 → `GUARD_DEUSERNAMED`）
  - expect：`NO_DEV_ABS` 且 `GUARD_DEUSERNAMED`
  - **清单↔扫描↔owned 闭环**：被此 grep 命中的现有文件 = commands（t1 owned）+ vendor scripts/plist（t2 owned）+ scripts validator 守卫（t4 owned）；handoff/bin/* 实测 0 命中（仅回归守卫）；P3 作废脚本经 --exclude 不计。三者闭环，无「扫到但无 owner」缺口。

---

## 5. 非目标

- 不创建/修改 `.claude-plugin/**`、`plugin.json`、`marketplace.json`、`commands/setup.md`、任何 setup 脚本（属 track-a）。
- 不重定义任一链路的 review 判定语义（归 docs/constitution.md v1.0.0）。
- 不实际部署 daemon、不**运行** `install-transport.sh`、不注册 LaunchAgent、不改 cron。（注：本轮 round-3 按 Codex finding **会编辑 install-transport.sh 的 HANDOFF 解析来源**使其 source state-paths.sh，但不运行它、不改其部署动作语义。）
- 不删除 gd.md 的 path-traversal 安全守卫语义（只把字面 `/Users/praise/.claude` 改写为 `${HOME}/.claude` 模式以脱钩开发者用户名）。
- 不写任何 README 安装/前置文档正文（属 track-a / 文档 track）；本 step 只保证脚本与命令文件可移植 + 可校验。

---

## 6. 实现步骤

```text
Step.1  清零 commands/gd.md 开发者绝对路径
  WHERE: commands/gd.md 行 16-18（GD_PROJECT_ROOT/GD_STANDARD/GOAL_SOURCE）、行 148（Output contract 内 GD_PROJECT_ROOT）
  WHAT:  把三行 GD_PROJECT_ROOT/GD_STANDARD/GOAL_SOURCE 的 /Users/praise/AI-Agent/Claude/projects/Project GD 字面量改为 ${CLAUDE_PLUGIN_ROOT}（框架内文件解析），并把正文「绝不使用 Project GD/... 相对路径」改为「从 ${CLAUDE_PLUGIN_ROOT} 拼接」；行 8/519/525 的旧 ~/.claude/commands 安装模型描述按 P3 删除（旧 install-gd-command/parity 模型作废），行 434 的 path-traversal 守卫把 /Users/praise/.claude 改为 ${HOME}/.claude 保留拒绝语义
  WHY:   行 16-18/148 是安装者机器第一步就找不到 prompts/templates/scripts 的根因（P2/SC-007）；行 8/519/525 引用作废的 ~/.claude/commands 安装链（P3 禁止两套命令安装并存）；行 434 是安全守卫不能删，只能脱开发者用户名
  VERIFY: grep -c "/Users/praise/AI-Agent" commands/gd.md 返回 0；grep "CLAUDE_PLUGIN_ROOT" commands/gd.md 返回 ≥1

Step.2  清零 commands/review1.md 与 review2.md 开发者绝对路径
  WHERE: commands/review1.md 行 9（GD_ROOT）；commands/review2.md 行 4（Installed copy）
  WHAT:  review1.md GD_ROOT 由 /Users/praise/AI-Agent/... 改为 ${CLAUDE_PLUGIN_ROOT}；review2.md「Installed copy: /Users/praise/.claude/commands/review2.md」行删除或改为「由 /plugin 机制安装，无开发者机器副本」（旧 installed-copy 模型作废，P3）
  WHY:   两文件各 1 处开发者绝对路径，安装者机器解析失败/误导（P2/P3/SC-007）
  VERIFY: grep -c "/Users/praise/AI-Agent" commands/review1.md commands/review2.md 返回 0

Step.3  HANDOFF_ROOT 解耦为插件管理、env 可覆盖、daemon↔client 一致（state-paths.sh = 唯一真源）
  WHERE: vendor/l3-transport/handoff/lib/state-paths.sh 行 8 + vendor/l3-transport/scripts/install-transport.sh（HANDOFF 解析处）
  WHAT:  ① state-paths.sh：把 : "${HANDOFF_ROOT:=${HOME}/.claude/handoff}" 改为插件管理的协调位置：默认值取 ${CLAUDE_PLUGIN_DATA:-${HOME}/.claude}/gd-handoff，保留 := 使外部 export HANDOFF_ROOT 可覆盖；文件头注释写明「此目录是 daemon↔client 唯一协调点，install-transport.sh 与 codex-send-wait 必须解析到同一值；不进安装者 setup 预设」。
         ② install-transport.sh（按 Codex round-2 finding 1 纳入 track-b owned_paths，写死一致性）：把 install-transport.sh 内部任何独立的 HANDOFF/部署目录解析改为 **source 同一 `handoff/lib/state-paths.sh`** 取 ${HANDOFF_ROOT}/${HANDOFF_BIN}，使 daemon 部署目录与 client 解析目录恒等。**只改 HANDOFF 解析来源，不改其部署动作语义**（仍由安装者按 README 手动跑）。
         ③ **launchagents/*.plist（应对 Codex round-5 P1，plist 含 /Users/praise ProgramArguments）**：把 2 个 plist 的 `/Users/praise/...` 路径（ProgramArguments、WorkingDirectory 等）改为占位符（如 `__HANDOFF_BIN__`/`__HANDOFF_ROOT__`），由 install-transport.sh **在安装时按 state-paths.sh 解析值渲染替换**后写入 ~/Library/LaunchAgents；bundle 内 plist 不含任何 `/Users/praise` 字面（TAPTAP_API_KEY 已 redact 保持）。
  WHY:   决策已锁：HANDOFF_ROOT 必须由插件管理且两端一致，填错即断链；Codex round-2/round-5 指出一致性未写死 + plist 漏处理——本轮写死：state-paths.sh 为 HANDOFF_ROOT 唯一真源，install-transport.sh source 它并渲染 plist 占位符（FR-016/P4），不再 defer track-a。
  VERIFY: ① HANDOFF_ROOT=/tmp/h bash -c 'source vendor/l3-transport/handoff/lib/state-paths.sh; test "$HANDOFF_ROOT" = "/tmp/h"' && echo OVERRIDE_OK；② grep -q 'state-paths.sh' vendor/l3-transport/scripts/install-transport.sh；③ `! grep -rn '/Users/praise' vendor/l3-transport/launchagents/`（plist 已脱用户名/占位符化）

Step.4  writer(L3) + codex-consult.sh(L1) 写产物隔离 + codex-send-wait 路径脱钩
  WHERE: vendor/l3-transport/scripts/review-result-writer.sh 行 51（BASELINE_DIR）、行 60（WRITER_MARKER_FILE）、行 88（CODEX_BIN）；vendor/l3-transport/scripts/codex-consult.sh 行 54（CODEX_BIN="$HOME/.claude/handoff/bin/codex-send-wait"）
  WHAT:  ① review-result-writer.sh：行 51 BASELINE_DIR 由 $HOME/.claude/review-baselines 改为 ${CLAUDE_PLUGIN_DATA:-$HOME/.claude}/gd-review-baselines（更新安全隔离区），保留 --out-dir/--baseline-key 覆写；行 60 迁到 ${CLAUDE_PLUGIN_DATA} 下 state 子目录；行 88 CODEX_BIN 改为经 state-paths.sh 的 ${HANDOFF_BIN}/codex-send-wait；-x 失败分支输出中文缺失提示（支撑 SC-004）。
         ② **codex-consult.sh（L1 /review1 discuss 路径，应对 Codex round-5 P2）**：source `handoff/lib/state-paths.sh`，把行 54 的 `$HOME/.claude/handoff/bin/codex-send-wait` 改为 `${HANDOFF_BIN}/codex-send-wait`，与 Step.3 HANDOFF_ROOT 同一真源；-x 失败分支同样中文 fail-closed。
  WHY:   写进 ~/.claude/review-baselines 在 /plugin update 时可能被覆盖/只读失败丢数据（P4/SC-006）；writer 与 codex-consult.sh 各自硬编码 ~/.claude/handoff 与 Step.3 HANDOFF_ROOT 不一致会断链（P2/FR-016）；三链路中 L1（codex-consult）与 L3（writer）都走 codex-send-wait，必须同源，否则 /review1 discuss 在安装者机器断链
  VERIFY: writer 与 codex-consult.sh 内 `grep -nE '\$HOME/.claude/handoff/bin'` 均返回 0 行；`grep -c 'HANDOFF_BIN' vendor/l3-transport/scripts/codex-consult.sh` ≥1；`grep -c 'CLAUDE_PLUGIN_DATA' vendor/l3-transport/scripts/review-result-writer.sh` ≥1

Step.5  建 bundle 完整性校验脚本（blocking）
  WHERE: scripts/gd-bundle-completeness.sh（新建）
  WHAT:  写一个 stdlib-only bash 脚本，--check 模式逐一校验八类 bundle 目标存在且非空：commands（含 review1.md/review2.md/gd.md 三文件）、scripts（含 scripts/lib/）、prompts、templates、schema、docs、fixtures、vendor/l3-transport（含 codex-consult.sh / review-result-writer.sh / install-transport.sh / handoff/bin/codex-send-wait / handoff/lib/state-paths.sh / launchagents 下 plist）；任一缺漏列入 blocking、exit≠0 并打印缺失清单；明确排除作废的 install-gd-command.sh/uninstall-gd-command.sh/check-gd-command-parity.sh（命中即报 P3 违规）
  WHY:   实测 templates 被 gd.md 引用 13 次、scripts 8 次，漏任一目录链路中途断；vendor/l3-transport 漏掉则三链路 cross-review 全 fail-closed（FR-003/FR-015/P3/SC-002）
  VERIFY: bash scripts/gd-bundle-completeness.sh --check; echo $?（健康仓返回 0）；临时 mv vendor/l3-transport /tmp 后再跑返回非 0 且 stderr 含 vendor/l3-transport（mv 回原位）

Step.6  建跨目录冒烟脚本（不靠本仓自测；happy path 必须真调 writer，不得用回显替代）
  WHERE: tests/gd-plugin-cross-dir-smoke.sh（新建）
  WHAT:  写脚本：mktemp -d 建临时目录、git init 成非 GD 项目、export CLAUDE_PROJECT_DIR=该临时目录、export CLAUDE_PLUGIN_ROOT=本仓根、export CLAUDE_PLUGIN_DATA=临时 data 目录。
         **happy path（应对 Codex round-2 finding 2，禁止路径回显替代）**：在临时 ${HANDOFF_BIN} 放一个 **fixture `codex-send-wait`**（可执行 stub：读入 capsule、回写一份固定 `VERDICT: APPROVED` raw result，模拟 daemon 成功），export HANDOFF_BIN 指向该 fixture 目录；real-调用 `vendor/l3-transport/scripts/review-result-writer.sh`（带 --baseline-key + --out-dir 指向 ${CLAUDE_PLUGIN_DATA}），断言 writer **真生成** result/baseline 文件到 ${CLAUDE_PLUGIN_DATA}（`test -f` 实文件，非回显字符串）。
         断言：① 命令引用文件全部可解析（file not found = 0，复用 Step.5 校验）② writer 产物路径前缀 = CLAUDE_PLUGIN_DATA 或 CLAUDE_PROJECT_DIR，0 命中 CLAUDE_PLUGIN_ROOT/插件安装目录（SC-006）③ `--no-codex` 子模式：HANDOFF_BIN 指向**不存在**的 codex-send-wait（无 fixture stub），断言 writer fail-closed + 输出含中文提示 + 产物区不含通过结论字样（SC-004）④ `--assert-data-isolated` 与 `--print-outdir` 子开关供 SC-006/SC-004 verify 复用；happy-path 全过 exit 0。
  WHY:   constitution P1/FR-014 明令「他人可用」必须经跨机/跨目录冒烟证明，MUST NOT 仅凭本仓自身目录 self-test 或纯路径回显断言成立；Codex round-2 指出回显不足以证明 happy path，故必须真跑 writer 产出实文件（SC-003）
  VERIFY: bash tests/gd-plugin-cross-dir-smoke.sh; echo $?（备齐路径时返回 0，且 ${CLAUDE_PLUGIN_DATA} 下有 writer 生成的 result/baseline 实文件）；脚本内禁止以 $PWD/Project GD 命中或纯回显作为通过依据（自检脱钩，靠 mktemp 临时 repo + fixture codex-send-wait）；discuss 子路径用同一 fixture 真调 codex-consult.sh

Step.7  脱 validator 脚本守卫的开发者用户名（应对 Codex round-5 P1：SC-007 scan 命中 scripts 但无清零任务）
  WHERE: scripts/gd-validate-dispatch.py（is_under_protected_runtime 内 `/Users/praise/.claude` 字面）、gd-validate-execution-batch.py、gd-validate-master-plan-consistency.py、gd-validate-child-proposal.py、gd-codex-bridge-review.py（同类 protected-runtime 守卫硬编码 `/Users/praise/.claude`）
  WHAT:  把这 5 个 validator/bridge 脚本里硬编码的 `/Users/praise/.claude` protected-runtime 守卫改为运行时解析安装者 HOME：`os.path.expanduser("~/.claude")` 或 `os.environ.get("HOME")`/`Path.home()/".claude"`；只改守卫的「用户名解析」，保留拒绝语义（仍拒绝写 <安装者HOME>/.claude）。**P3 作废的 install-gd-command.sh/uninstall-gd-command.sh/install-review-route-command.sh/check-gd-command-parity.sh 不入 bundle，不在本步范围**（由 bundle-completeness 脚本断言它们不被打包）。
  WHY:   守卫硬编码 `/Users/praise/.claude` 在安装者机器上永不命中（安装者非 praise）→ 保护失效；脱用户名后守卫对安装者的 ~/.claude 才真正生效（P2/SC-007）。这是 round-4 把 SC-007 scan 扩到 scripts 后照出的真实清零缺口。
  VERIFY: `! grep -rEnI '/Users/praise/(AI-Agent|\.claude)' scripts --exclude='install-gd-command.sh' --exclude='uninstall-gd-command.sh' --exclude='install-review-route-command.sh' --exclude='check-gd-command-parity.sh'` 返回 0 命中；抽查 `python3 scripts/gd-validate-dispatch.py --help` 或 self-test 仍可跑（守卫语义未破坏）
```

禁止用「完善/优化/系统性/全面/增强」作为唯一动作描述（已遵守）。

---

## 7. Task Packet 拆分

> 应对 Codex F1（track-b 唯一 P2）：本节为每个 task packet 列全 7 个强制字段（owned_paths / forbidden_paths / required_context / blocked_by / can_parallel_with / deliverables / verify）。verify 绑定 §4（SC verify）/§10（测试计划）已列命令，不扩大实现范围。每个 packet 的**完整自包含定义见同目录 `task-packets/<task_id>.md`**，字段一致。

### t1 · zero-out-command-paths
- agent_role: implementer ｜ blocked_by: — ｜ can_parallel_with: isolate-transport-and-writes
- owned_paths: `commands/gd.md`, `commands/review1.md`, `commands/review2.md`
- forbidden_paths: `.claude-plugin/**`, `commands/setup.md`, `vendor/l3-transport/**`, `scripts/gd-bundle-completeness.sh`, `tests/gd-plugin-cross-dir-smoke.sh`, `/Users/praise/.claude/**`
- required_context: `docs/constitution-plugin.md`, `specs/gd-plugin-packaging/spec.md`（应对 Codex round-3 P2 自循环：owned 的三命令文件不再列入 required_context；实现者读自己将改的 owned 文件是隐含行为，required_context 只列外部上下文）
- deliverables: `commands/gd.md`(file)、`commands/review1.md`(file)、`commands/review2.md`(file) — 均 must_exist
- verify(SC-007): `! grep -rEn '/Users/praise/(AI-Agent|\.claude)' commands/gd.md commands/review1.md commands/review2.md && echo NO_DEV_ABS` 且 `grep -q '\${HOME}/.claude' commands/gd.md && echo GUARD_DEUSERNAMED`；assertion: `grep -c 'CLAUDE_PLUGIN_ROOT' commands/gd.md` ≥1

### t2 · isolate-transport-and-writes
- agent_role: implementer ｜ blocked_by: — ｜ can_parallel_with: zero-out-command-paths, deusername-script-guards
- owned_paths: `vendor/l3-transport/handoff/lib/state-paths.sh`, `vendor/l3-transport/scripts/review-result-writer.sh`, `vendor/l3-transport/scripts/install-transport.sh`, `vendor/l3-transport/scripts/codex-consult.sh`（round-5：L1 HANDOFF 解耦）, `vendor/l3-transport/launchagents/com.praise.codex-watch.plist`, `vendor/l3-transport/launchagents/com.praise.codex-watch-healthcheck.plist`（round-5：plist 占位符化）
- forbidden_paths: `commands/gd.md`, `commands/review1.md`, `commands/review2.md`, `.claude-plugin/**`, `scripts/gd-bundle-completeness.sh`, `tests/gd-plugin-cross-dir-smoke.sh`, `scripts/gd-validate-*.py`, `/Users/praise/.claude/**`
- required_context: `vendor/l3-transport/README.md`, `.deploy-manifest.jsonl`, `docs/constitution-plugin.md`（owned 文件不列入 required_context，仅外部上下文）
- deliverables: `state-paths.sh`、`review-result-writer.sh`、`install-transport.sh`、`codex-consult.sh`、2 个 plist — 均 must_exist
- verify(SC-006): `grep -nE '\$HOME/\.claude/(review-baselines|state)' vendor/l3-transport/scripts/review-result-writer.sh; test $? -ne 0 && echo PASS`；verify(SC-007/FR-016 两端一致): `HANDOFF_ROOT=/tmp/h bash -c 'source vendor/l3-transport/handoff/lib/state-paths.sh; test "$HANDOFF_ROOT" = /tmp/h' && echo PASS` 且 `grep -q 'state-paths.sh' vendor/l3-transport/scripts/install-transport.sh` 且 `! grep -rn '/Users/praise' vendor/l3-transport/launchagents/`（plist 脱用户名）；verify(SC-004/L1+L3 同源): `grep -c 'HANDOFF_BIN' vendor/l3-transport/scripts/review-result-writer.sh` ≥1 且 `grep -c 'HANDOFF_BIN' vendor/l3-transport/scripts/codex-consult.sh` ≥1

### t4 · deusername-script-guards（round-5 新增：SC-007 scan 命中 scripts 的清零任务）
- agent_role: implementer ｜ blocked_by: — ｜ can_parallel_with: zero-out-command-paths, isolate-transport-and-writes
- owned_paths: `scripts/gd-validate-dispatch.py`, `scripts/gd-validate-execution-batch.py`, `scripts/gd-validate-master-plan-consistency.py`, `scripts/gd-validate-child-proposal.py`, `scripts/gd-codex-bridge-review.py`
- forbidden_paths: `commands/**`, `vendor/l3-transport/**`, `.claude-plugin/**`, `tests/**`, `scripts/gd-bundle-completeness.sh`, `scripts/gd-plugin-setup.sh`, `/Users/praise/.claude/**`
- required_context: `docs/constitution-plugin.md`, `specs/gd-plugin-packaging/spec.md`
- deliverables: 上述 5 个 .py（file, must_exist）
- verify(SC-007): `! grep -rEnI '/Users/praise/(AI-Agent|\.claude)' scripts/gd-validate-dispatch.py scripts/gd-validate-execution-batch.py scripts/gd-validate-master-plan-consistency.py scripts/gd-validate-child-proposal.py scripts/gd-codex-bridge-review.py && echo PASS`（守卫脱用户名为 expanduser("~/.claude")，拒绝语义保留）；抽查 `python3 scripts/gd-validate-dispatch.py --self-test 2>/dev/null` 仍可跑或同等 self-test 不报错

### t3 · bundle-and-smoke-verifiers
- agent_role: implementer ｜ blocked_by: zero-out-command-paths, isolate-transport-and-writes, deusername-script-guards ｜ can_parallel_with: —
- owned_paths: `scripts/gd-bundle-completeness.sh`, `tests/gd-plugin-cross-dir-smoke.sh`
- forbidden_paths: `commands/gd.md`, `commands/review1.md`, `commands/review2.md`, `vendor/l3-transport/**`, `.claude-plugin/**`, `commands/setup.md`, `scripts/gd-validate-*.py`, `/Users/praise/.claude/**`
- required_context: `docs/constitution-plugin.md`, `specs/gd-plugin-packaging/spec.md`（t1/t2/t4 的 deliverables 经 blocked_by 合法只读，不另列入 required_context 以免自/跨循环误判）
- deliverables: `scripts/gd-bundle-completeness.sh`(file)、`tests/gd-plugin-cross-dir-smoke.sh`(file) — 均 must_exist
- verify(SC-002): `bash scripts/gd-bundle-completeness.sh --check && echo PASS`；verify(SC-003): `bash tests/gd-plugin-cross-dir-smoke.sh && echo PASS`；verify(SC-004): `bash tests/gd-plugin-cross-dir-smoke.sh --no-codex && echo PASS`；verify(SC-006): `bash tests/gd-plugin-cross-dir-smoke.sh --assert-data-isolated && echo PASS`；verify(SC-007 整清单 sweep，blocked_by t1+t2+t4 故可见全部清零): `! grep -rEnI '/Users/praise/(AI-Agent|\.claude)' commands scripts vendor/l3-transport --exclude='install-gd-command.sh' --exclude='uninstall-gd-command.sh' --exclude='install-review-route-command.sh' --exclude='check-gd-command-parity.sh' && echo SC007_BUNDLE_CLEAN`

说明：t1/t2/t4 owned_paths 互不重叠、互不在对方 blocked_by → 可并行（受 max_parallel=2 硬上限，execute 期最多同跑 2，分波调度）。t3 验证前三者改写结果（含 SC-007 整分发物清单 sweep：t1 清 commands、t2 清 vendor+plist、t4 清 scripts validator 守卫），故 blocked_by 三者、串行收口。完整 packet 文件：`task-packets/{zero-out-command-paths,isolate-transport-and-writes,deusername-script-guards,bundle-and-smoke-verifiers}.md`。

---

## 8. 边界（修改 / 不修改）

修改：
- commands/gd.md, commands/review1.md, commands/review2.md（t1）
- vendor/l3-transport/handoff/lib/state-paths.sh, scripts/review-result-writer.sh, scripts/install-transport.sh（仅 HANDOFF 解析）, scripts/codex-consult.sh（L1 HANDOFF）, launchagents/*.plist（占位符化）（t2）
- scripts/gd-validate-{dispatch,execution-batch,master-plan-consistency,child-proposal}.py, scripts/gd-codex-bridge-review.py（t4：脱守卫用户名 `/Users/praise/.claude` → `expanduser("~/.claude")`）
- scripts/gd-bundle-completeness.sh（新建，t3）
- tests/gd-plugin-cross-dir-smoke.sh（新建，t3）

不修改：
- `.claude-plugin/**`、commands/setup.md、任何 setup 脚本（track-a）
- install-transport.sh 的**部署动作语义**（仅改其 HANDOFF 解析 source state-paths.sh，不改它装 daemon/plist 的行为；不运行它）
- 任一链路 review 判定语义、旧 /rev / /review artifact
- `/Users/praise/.claude/**`（禁止写入）
- 其他 step 的 owned_paths

---

## 9. 风险与防护

| 风险 | 防护 |
|------|------|
| 把 path-traversal 守卫字符串（gd.md:434 `/Users/praise/.claude/**`）当解析路径误删，丢失安全语义 | Step.1 把守卫**改写为 `${HOME}/.claude/**`**（脱用户名，保留拒绝逻辑）；SC-007 **不得用 `grep -v` 排除**——守卫既已改 `${HOME}/.claude`，命令文件内不应再有任何 `/Users/praise` 字面，verify 直接 fail on `/Users/praise/(AI-Agent\|.claude)`（应对 Codex round-4 P2） |
| `${CLAUDE_PLUGIN_ROOT}` 在 command 正文运行时注入行为本仓无法实证（0 处现存引用） | 列入 §11 Assumptions，以 openai-codex 范本与 README 实证为准；verify 降级为静态字符串断言（grep 命中替换后 token），不假设运行时展开 |
| HANDOFF_ROOT 改默认后与 install-transport.sh 解析不一致 → 断链 | round-3 已写死：install-transport.sh 纳入 t2 owned_paths 并改为 source 同一 state-paths.sh（state-paths.sh = HANDOFF_ROOT 唯一真源）；Step.3 verify ③ `grep -q 'state-paths.sh' install-transport.sh`；冒烟 Step.6 用 fixture codex-send-wait 真调 writer 验证两端一致；不再 defer track-a |
| writer 改 BASELINE_DIR 默认后破坏既有 --baseline-key/--out-dir 覆写 | Step.4 只改默认值表达式，保留所有调用方覆写入口；冒烟脚本验证覆写仍生效 |
| 跨目录冒烟脚本退化成「在本仓目录跑」从而违反 FR-014 | Step.6 用 mktemp 临时 git repo 作 CLAUDE_PROJECT_DIR，脚本内禁止以 `$PWD`/`Project GD` 命中作为通过条件 |

---

## 10. 测试计划

```bash
# SC-007 — 分发物运行时清单整体清零（统一 grep 形式，全文件类型含 plist/bin，--exclude P3 作废脚本，不用 --include）
! grep -rEnI '/Users/praise/(AI-Agent|\.claude)' commands scripts vendor/l3-transport --exclude='install-gd-command.sh' --exclude='uninstall-gd-command.sh' --exclude='install-review-route-command.sh' --exclude='check-gd-command-parity.sh' && echo SC007_BUNDLE_CLEAN
grep -q '${HOME}/.claude' commands/gd.md && echo SC007_GUARD_DEUSERNAMED

# SC-002 / FR-015 — bundle 完整性 blocking 校验（含 vendor/l3-transport）
bash scripts/gd-bundle-completeness.sh --check && echo SC002_PASS

# HANDOFF_ROOT env 覆盖 + 默认脱用户名
HANDOFF_ROOT=/tmp/h bash -c 'source vendor/l3-transport/handoff/lib/state-paths.sh; test "$HANDOFF_ROOT" = "/tmp/h"' && echo OVERRIDE_OK

# writer 写产物隔离 — 0 处硬编码 ~/.claude 写路径
grep -nE '\$HOME/\.claude/(review-baselines|state)' vendor/l3-transport/scripts/review-result-writer.sh; test $? -ne 0 && echo WRITE_ISOLATED

# SC-003 — 跨目录冒烟 happy path
bash tests/gd-plugin-cross-dir-smoke.sh && echo SC003_PASS

# SC-004 — 缺 codex fail-closed + 中文提示 + 无伪通过结论
bash tests/gd-plugin-cross-dir-smoke.sh --no-codex && echo SC004_PASS

# SC-006 — 运行时数据隔离（不写插件安装目录）
bash tests/gd-plugin-cross-dir-smoke.sh --assert-data-isolated && echo SC006_PASS
```

---

## 11. Assumptions

- `${CLAUDE_PLUGIN_ROOT}` 在 command 正文与 bash 块运行时由 Claude Code 插件机制注入（依 constitution P2 已被 openai-codex 范本实证）；本仓当前 0 处引用，故 verify 以静态字符串断言为主，不假设运行时展开行为可在本仓直接观测。
- `${CLAUDE_PLUGIN_DATA}` 为插件更新安全的数据目录（constitution P4/FR-006 命名）；不可用时降级 `${HOME}/.claude` 仅作 fallback，不作默认写插件安装目录。
- `install-transport.sh` 的 **HANDOFF 解析改动属于本 step / t2**（round-3 按 Codex finding 纳入 t2 owned_paths，改为 source 同一 `state-paths.sh`，使 daemon↔client 恒等）；track-a **只承接** README/setup 文档与安装操作说明，**不承接**该代码改动。Step.3 verify ③ `grep -q 'state-paths.sh' install-transport.sh` 在本 step 内闭环。
- Python ≥3.9、git、shasum 在安装者机器可用（FR-008 外部依赖声明范畴，由 track-a README 承接）。
- 三命令文件中 path-traversal 拒绝白名单 **脱用户名为 `${HOME}/.claude`** 后保留拒绝语义；清零后命令文件内**不得残留任何 `/Users/praise/` 字面**（含 `.claude`），SC-007 直接 fail on `/Users/praise/(AI-Agent|.claude)` 而非排除式。
