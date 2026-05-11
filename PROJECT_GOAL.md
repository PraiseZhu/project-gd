PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。

# Plan: `/rev` Goal-Driven Anti-Fill Lab v6

日期：2026-05-09
状态：reviewed
负责人：Claude 执行，Codex review

## Context

现有 `/review` 链路已全量落地在 `~/.claude/`：
- 入口：`~/.claude/commands/review.md`（plan / code 两种 review kind）
- Capsule：21+ 标准化字段
- Cross-review：`~/.claude/handoff/bin/codex-send-wait` → `codex-watch` daemon → `codex exec --ephemeral` → result file
- Baseline：`~/.claude/review-baselines/<key>/latest-plan-baseline.json`
- Hook 强制路由：review-stop-marker / review-stop-guard / review-writer-required-gate

存在的真实问题：**AI 填表化**——模板字段填全但内容泛化。三个独立攻击面：
- **作者层**：Claude 写 plan 时把成功标准、实现步骤填得空洞
- **追溯层**：baseline 只存 `last_review_focus`，无 goal chain / SC ID，导致 `/review code` 时审查者看不到原计划要什么
- **审查层**：`codex-watch build_review_prompt()` 硬编码 prompt 无 anti-generic 判定

**用户最终决策**：在 `Project GD/` 内建 lab-only `/rev` 同步 runner 升级链路，旧 `/review` 完全保留供对比。Codex 桌面端不参与 review 执行，但与 CLI 共用同一份 review 标准文档（`rev-review-standard.md`）实现 parity。

## Review 对齐

REVIEW_DOMAIN：ai_infra

REVIEW_FOCUS：
- `/rev` 是否是同步 lab runner，不复用 live `codex-watch` review path，也不新增 daemon
- "复用 vs 绕开"边界是否明确，避免不必要重写或误用旧链路
- `rev-review-standard.md` 是否成为 CLI 与桌面端共同引用的 review 标准源
- A/B 旧链路对照是否只读提取旧 prompt，不运行 live `/review`
- baseline 是否只保存目标追溯字段，parity 是否进入最终报告

Domain-specific notes：
- ai_infra：涉及 trigger surface、generation surface、state/baseline、review prompt runner、template parity、review parity；不启用 live command、hook、MCP、cron，不新增第二个 watch daemon。
- app_code：无。
- docs_content：仅新增或修改 `Project GD/` 内模板、脚本、fixtures、reports。
- other：无。

## 目标与验收

用户目标：
- 在不破坏现有 `/review` 链路的前提下，用 `Project GD/` 建设 lab-only `/rev` 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。

成功标准：
- [ ] **SC-1**：所有新增/修改文件只在 `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD/**` 下。
- [ ] **SC-2**：`/rev` 在实验期不是 Claude Code slash command；真实入口是 `Project GD/bin/rev plan <file>` / `Project GD/bin/rev code <file>`。
- [ ] **SC-3**：不创建、不软链、不注册 `/Users/praise/.claude/commands/rev.md`，不新增 `rev-watch` daemon。
- [ ] **SC-4**：`bin/rev` 直接调用 `codex exec --ephemeral`，自行拼接 prompt、解析 `REV_VERDICT`、写 lab result/baseline。
- [ ] **SC-5**：明确复用 `codex exec --ephemeral`、`codex-watch` timeout/kill 思路、旧 capsule 字段骨架；明确不复用 `codex-watch build_review_prompt()`、`process_capsule()`、`codex-send-wait` 队列轮询、`review-result-writer.sh`。
- [ ] **SC-6**：`Project GD/prompts/rev-review-standard.md` 是 `/rev` review 标准唯一真源；CLI runner 与桌面端计划/review 都引用它。
- [ ] **SC-7**：实验计划模板要求 `PROJECT_GOAL / CHAIN_GOAL / PHASE_GOAL / TASK_GOAL / SC-* / NON_GOALS`；每条 `SC-*` 必须有 verify；每个实现步骤必须映射 `SC-*`。
- [ ] **SC-8**：rev baseline 只保存目标追溯字段：`goal_chain`、`success_criteria[{id,text,verify}]`、`plan_hash`、`non_goals`、`accepted_decisions`。
- [ ] **SC-9**：execution result 模板要求逐条列出 baseline 中全部 `SC-*` 的状态、证据、未执行原因。
- [ ] **SC-10**：A/B fixtures 优先来自历史 checkpoints 只读候选，经用户确认后脱敏进入 `Project GD/fixtures/`。
- [ ] **SC-11**：旧 `/review` 对照通过只读提取 `codex-watch build_review_prompt()` heredoc 到 `Project GD/fixtures/old-review-prompt-readonly.md`，不运行 live `/review`。
- [ ] **SC-12**：最终报告包含 Claude/Codex plan template parity、Codex desktop/CLI review parity、全中文输出检查；每项必须有明确 PASS/FAIL verdict。
- [ ] **SC-13**：验证证明 `/Users/praise/.claude/commands`、`review-baselines`、`state`、`handoff`、`scripts/hooks` 未新增、未修改。

非目标：
- 不替换 `/review`。
- 不修改 `/Users/praise/.claude/**`。
- 不复用 live `review-result-writer.sh` 写结果。
- 不调用 live `/review plan` 做 A/B。
- 不启用 hook、cron、MCP、Obsidian on-save。
- 不新增第二个 watch daemon。
- 不做短模板实验。
- 不把 goal-driven 项目的完整 prompt 塞进模板。

## 当前状态

相关事实：
- `Project GD/` 已存在，是本实验根目录（含 .git / .gitignore / CLAUDE.md / VERSIONING.md / README.md / 标准目录骨架）。
- 当前 live `/review` 链路位于 `/Users/praise/.claude/**`，必须视为受保护 runtime。
- `codex-watch` 不是纯 transport；其 `build_review_prompt()` (L58-160) 硬编码了旧 `/review` 的 prompt、`VERDICT:` 契约、blocker threshold、quality rules、convergence rules。
- `codex-watch` 不支持 `anti_fill_prompt_path` 或任意外置 prompt path。
- 当前 Claude live plan template 与 Codex workspace plan template 无 drift。
- baseline schema 不应承载 template parity / review parity；这些是报告验收项。

现有入口：
- 实验根目录：`/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD/`
- 旧 `/review` command：`/Users/praise/.claude/commands/review.md`
- live plan template：`/Users/praise/.claude/templates/plan-template.md`
- Codex plan template copy：`/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex/templates/plan-template.md`
- 旧 review prompt 源（用于只读提取）：`/Users/praise/.claude/handoff/bin/codex-watch` L58-160

约束：
- 不写 `/Users/praise/.claude/**`。
- 不递归复制 `.claude`。
- 不运行会写 live handoff/baseline/state 的命令。
- 不引入 daemon 生命周期管理。
- 每个 Phase 单独 plan / review / execute / code review。

## 代码执行方向

新增：
- `Project GD/bin/rev`：同步 lab runner（Bash）
- `Project GD/templates/plan-template.md`：实验计划模板
- `Project GD/templates/execution-result-template.md`：实验执行结果模板
- `Project GD/prompts/rev-review-standard.md`：唯一 `/rev` review 标准源
- `Project GD/schema/rev-baseline.schema.json`：精简 baseline schema
- `Project GD/scripts/rev-result-writer.sh`：lab-local result writer
- `Project GD/baselines/`：rev baseline
- `Project GD/fixtures/old-review-prompt-readonly.md`：只读提取的旧 review prompt 对照
- `Project GD/fixtures/plans/`：A/B plans
- `Project GD/reports/`：阶段报告、A/B report、parity report

修改：
- 只修改 `Project GD/` 内实验文件
- 不修改 live `/review`、Claude/Codex 正式模板或 settings

不修改：
- `/Users/praise/.claude/**`
- `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex/templates/**`
- `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex/plugins/**`
- AKB2.0 vault/wiki/toolbox/fetch 链路

**复用 vs 绕开**：

| 复用 | 不复用 |
|---|---|
| `codex exec --ephemeral` 作为实际 review 执行器 | `codex-watch build_review_prompt()` 运行路径 |
| `codex-watch` timeout/kill 思路（抄实现，不调用） | `codex-watch process_capsule()` |
| 旧 capsule 21+ 字段作为 baseline/capsule 参考骨架 | `codex-send-wait` / `codex-send` 队列轮询 |
| `codex-watch build_review_prompt()` heredoc 文本只读提取为 A/B 对照 | `review-result-writer.sh` |
| | live `/review plan` 调用 |

## 接口与数据合约

CLI 合约：
- `Project GD/bin/rev plan <plan-file>`
  - 输入：Markdown plan 文件
  - 输出：stdout 中文摘要 + `REV_VERDICT: APPROVED | REQUIRES_CHANGES | FAILED`
  - 结果文件：`Project GD/results/` 或 `Project GD/baselines/<key>/result-<timestamp>.md`
  - 错误：缺 plan、无法解析 `SC-*`、prompt runner 失败、输出裸 `VERDICT:`、写入路径越界 → exit non-zero
- `Project GD/bin/rev code <execution-or-diff-file>`
  - 输入：execution result、diff、或 code review capsule 文件
  - 输出：同上，使用 `REV_VERDICT`
  - 错误：找不到 matching baseline、`SC-*` 不完整、证据缺失 → `REQUIRES_CHANGES`

模块合约：
- `bin/rev`：
  - 读取 artifact + `prompts/rev-review-standard.md` → 拼完整 prompt → 直接 `codex exec --ephemeral`
  - 不调用 live `codex-watch`
  - 不创建 daemon
  - 保存实际发送给 Codex 的 prompt 到 `Project GD/results/` 或 `reports/`，用于验收
- `scripts/rev-result-writer.sh`：
  - 只写 `Project GD/`
  - 只解析 `REV_VERDICT`
  - 禁止调用 `~/.claude/scripts/review-result-writer.sh`
- `prompts/rev-review-standard.md`：
  - CLI runner 与桌面端 review parity 的唯一标准源
  - 计划模板和阶段计划必须写：`REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md`

数据/Schema：
- `rev-baseline.schema.json` 只包含：
  - `goal_chain: {project, chain, phase, task}`
  - `success_criteria: [{id, text, verify}]`
  - `plan_hash: sha256`
  - `non_goals: array`
  - `accepted_decisions: array`
- 不放入 baseline：
  - `template_parity` / `review_parity` / 中文输出检查 / A/B summary
- 这些检查写入：
  - `Project GD/reports/parity-check.md`
  - `Project GD/reports/ab-comparison.md`
  - `Project GD/reports/final-validation.md`

旧数据兼容：
- 不迁移旧 `/review` baseline
- A/B 旧链路对照只读使用提取出来的旧 prompt 或历史 result/capsule

## 实现步骤

### Phase 1：模板与 setup 收口
- **PHASE_GOAL**：固定 `Project GD/` 边界，建立实验模板和 review 标准源
- **包含 setup checklist**：
  - 确认 `Project GD/` 目录存在
  - 写 README/manifest
  - 白名单记录旧 `/review` source hash
  - 不复制 settings/state/baseline
- **输出**：
  - `templates/plan-template.md` → SC-7
  - `prompts/rev-review-standard.md` → SC-6
  - `manifest.json`
  - `reports/phase-1-template-setup.md`
- **hard-stop**：需要写 `.claude`、注册 slash command、复制 settings/state/baseline 时停止

### Phase 2：同步 runner + 精简 baseline
- **PHASE_GOAL**：建立不走 `codex-watch` 的 lab-local review path，并保存可追溯 baseline
- **输出**：
  - `bin/rev` → SC-2 / SC-4
  - `scripts/rev-result-writer.sh`
  - `schema/rev-baseline.schema.json` → SC-8
  - `baselines/`
  - prompt-run evidence
- **核心要求**：
  - 直接调用 `codex exec --ephemeral`
  - 不使用 `anti_fill_prompt_path`
  - 不调用 live `codex-watch build_review_prompt()` / `process_capsule()`
  - 不新增 `rev-watch` daemon
  - 不输出裸 `VERDICT:`
- **hard-stop**：实际 Codex 输入中找不到 `rev-review-standard.md` 内容，或输出触发旧 hook regex 风险时停止

### Phase 3：execution result 1:1 conformance
- **PHASE_GOAL**：让执行总结逐条证明计划 `SC-*`，形成闭环层
- **输出**：
  - `templates/execution-result-template.md` → SC-9
  - execution conformance fixtures
  - writer completeness check
- **要求**：
  - baseline 中全部 `SC-*` 必须列出
  - 每条有 status、evidence、not-run reason
  - 空 evidence 直接 fail
- **hard-stop**：execution result 可绕过 `SC-*` 说"完成"时停止

### Phase 4：A/B + parity 最终验收
- **PHASE_GOAL**：用真实历史计划验证 `/rev` 是否比旧 `/review` 更能阻断泛化且不误伤，同时证明 parity
- **fixture 来源**：
  - 只读扫描历史 checkpoints / archive
  - 产出候选清单，不直接复制正文
  - 用户确认 3 个：generic_bad、concrete_good、borderline
  - 脱敏后进入 `fixtures/plans/`
- **old `/review` 对照**：
  - 从 `codex-watch build_review_prompt()` heredoc 只读提取旧 prompt 到 `fixtures/old-review-prompt-readonly.md`
  - 或读取历史 `/review` result/capsule
  - 不运行 live `/review plan`
- **输出**：
  - `reports/ab-comparison.md` → SC-10 / SC-11
  - `reports/parity-check.md` → SC-12
  - `reports/final-validation.md` → SC-13
- **hard-stop**：A/B 需要写 live `.claude` state/baseline/handoff 时停止

## 边界与失败模式

必须处理：
- `codex-watch` 不支持自定义 prompt
- `REV_VERDICT` 与旧 `VERDICT` 输出契约混用
- `/rev` 误写 `~/.claude/review-baselines`
- A/B 误运行 live `/review`
- fixtures 含敏感信息
- `SC-*` 字段存在但步骤没有映射
- 泛化词被简单词表误杀
- `Project GD/` 外路径被误写
- 桌面端 review 未引用 `rev-review-standard.md`，导致 parity 空转

明确不处理：
- AI 不读代码就写 plan 的 grounding hook 问题
- 短模板
- live migration
- slash command 启用
- watch daemon 新增
- codex-watch 修改
- 旧 review writer 修改

风险与防护：

| 风险 | 防护 |
|------|------|
| 同步 runner 少了 watch 的 timeout/retry | `bin/rev` 自己设置单次 timeout，参考 `codex-watch` timeout/kill 思路，失败写 `REV_VERDICT: FAILED` |
| lab runner 与 Codex desktop/CLI review 语义分叉 | `rev-review-standard.md` 作为唯一标准源，CLI 和桌面端计划都引用它 |
| anti-generic 词表误伤正常表达 | 只有"泛化词作为唯一动作且无路径/对象/命令/输出断言/`SC-*`"才 fail |
| A/B 样本被挑选偏置 | 先出候选清单，由用户确认 3 类样本 |

## 测试计划

单元测试：
- `bin/rev plan` 对 bad/good/borderline fixture 的 verdict 测试
- `rev-result-writer.sh` 只解析 `REV_VERDICT` 的测试
- baseline schema 校验测试
- execution result `SC-*` completeness 测试

集成验证：
- `diff -q /Users/praise/.claude/templates/plan-template.md "/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex/templates/plan-template.md"` → 无 drift
- `test ! -e /Users/praise/.claude/commands/rev.md` → exit 0
- `find "/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD" -type f | sort` → 所有新增/修改文件只在 `Project GD/`
- `rg -n "REVIEW_STANDARD: .*rev-review-standard.md" "/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD"` → 计划模板/阶段计划/报告引用唯一标准源
- `rg -n "anti-generic|SC-\*|WHERE|WHAT|WHY|VERIFY" "/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD/prompts" "/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD/templates"` → 命中 lab prompt/template
- `rg -n "^VERDICT:|\[REVIEW\]" "/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD"` → 不在 runtime output contract 中出现；只允许在旧链路对照说明中出现
- A/B report：3 个 fixture × 2 链路结果，含中文 summary、false positive/false negative
- `find /Users/praise/.claude/commands /Users/praise/.claude/review-baselines /Users/praise/.claude/state /Users/praise/.claude/handoff /Users/praise/.claude/scripts/hooks -newer <phase-start-marker>` → 无与本计划相关的新增/修改

测试隔离：
- 所有 baseline/result 写 `Project GD/`
- 不调用 live writer
- 不运行 live `/review plan`
- 不修改 settings/hook/MCP/cron
- fixtures 入库前脱敏

暂不执行的验证：
- live `/rev` slash command 验证
- watch daemon 验证
- hook/cron/MCP 验证
- 正式迁移验证

## 待确认

无。v6 已吸收：
- 4 个真正产出阶段
- `Project GD/` 作为实验根目录
- `rev-review-standard.md` 作为唯一标准源
- 同步 `bin/rev` runner
- 不复用 `codex-watch` review path
- 不新增第二个 watch daemon
- 旧 `/review` prompt 只读提取做 A/B 对照
- baseline schema 精简
- parity 和中文输出放入报告验收

## 实施前 Review Checklist

- [x] 目标、成功标准、非目标清楚
- [x] REVIEW_DOMAIN 和 REVIEW_FOCUS 清楚
- [x] 新增/修改/不修改的文件范围清楚
- [x] CLI/API/函数输出合约清楚
- [x] 数据迁移和旧数据兼容清楚
- [x] 边界情况和失败模式清楚
- [x] 测试夹具不会污染真实数据
- [x] live runtime、密钥、外部服务、持久配置没有被默认修改
