<!--
Sync Impact Report
==================
Version change: (none) → 1.0.0  [initial ratification]
Bump rationale: 首次采纳。为「将 L1/L2/L3 三条链路封装为可分发 Claude Code 插件」建立前置决策层；
承接本会话「一行命令安装使用」端到端旅程分析（11 任务 / 5 缺口）。与 docs/constitution.md (v1.0.0,
L3 review 机制) 范围不重叠、互补。

Principles defined (6):
  P1 一行安装、装完即用 (One-Command Install, Run on Arrival)
  P2 路径可移植，零硬编码绝对路径 (Portable Paths, Zero Hardcoded Absolutes)
  P3 分发完整性 (Distribution Completeness)
  P4 Runtime 写入隔离 (Runtime Write Isolation)
  P5 外部依赖显式声明 + 缺失 fail-closed (Explicit External Deps, Fail-Closed on Absence)
  P6 更新可控、版本即 SHA (Controlled Manual Update, SHA-as-Version)

Sections added: 变更边界 (Change Boundaries) / 与 L3 Constitution 的关系 (Relationship) /
输出契约 (Output Contract, 引用不复述) / Governance

Files needing sync:
  ✅ docs/constitution.md — 一致（范围不重叠：本文件治理「打包与分发」，那份治理「L3 review 机制」；
     输出契约/不自动 commit 等重叠面二者措辞一致，本文件以引用方式继承不复述）
  ⚠ 待处理：插件封装 spec（/spec2 产出）应在顶部引用本 constitution 为前置决策层
  ⚠ 待处理：未来的 .claude-plugin/plugin.json + marketplace.json + 安装 README 必须落在
     Project GD/** 内并遵循 P2/P3/P4/P6（届时回填本报告为 ✅）

Deferred TODO: none（RATIFICATION_DATE 已知 = 2026-06-10）
-->

# Project GD Plugin Constitution

> 适用范围：本 constitution 治理 **将 `/gd` 四阶段三条链路（L1 planning dispatch / L2 plan cross-review / L3 execution review）封装为可分发 Claude Code 插件**的工作——即「如何打包、如何让他人一行命令安装、如何更新分发」。它**不**重定义链路的审查行为；审查机制语义归 [`docs/constitution.md`](./constitution.md) (v1.0.0) 治理。本文件是 `/spec2`（spec 编写）→ `/spec3`（澄清）→ `/gd plan` 链路中、针对插件封装工作的最前置决策层，与 `CLAUDE.md`、`PROJECT_GOAL.md` 互补而非替代。

## Core Principles

### P1 · 一行安装、装完即用 (One-Command Install, Run on Arrival)

本次工作的北极星：他人 **MUST** 能用一行可粘贴的终端命令完成安装，reload 后立即使用插件提供的全部链路命令。

- 安装路径 **MUST** 收敛为单行：`claude plugin marketplace add <repo> && claude plugin install <plugin>@<mkt>`（`&&` 串接 = 一行终端命令）。
- 「装完即用」严格定义为 **install + reload/restart 后可用**；安装 README **MUST** 显式包含 reload 步骤（`/reload-plugins` 或重启），**MUST NOT** 暗示 install 后无需重载即生效（`claude plugin update` 帮助明写 "restart required to apply"）。
- 「装完即用」**MUST** 由跨机 / 跨目录冒烟（在非 Project GD 目录、模拟他人环境跑通 happy path）证明，**MUST NOT** 仅凭本仓自身目录的 self-test 断言成立。

*Rationale*：用户北极星明确——分享给他人只需一行命令就能用全部链路；本仓内所有既有验证都在开发者自身目录完成，「别人能用」是未经证明的假设，故验证义务写进原则。

### P2 · 路径可移植，零硬编码绝对路径 (Portable Paths, Zero Hardcoded Absolutes)

- 命令 / 脚本引用框架内文件 **MUST** 经 `${CLAUDE_PLUGIN_ROOT}` 解析；Python 脚本沿用 `Path(__file__).resolve().parent.parent` 自解析（已实测可移植，无需改动）。
- 交付物 **MUST NOT** 含任何字面开发者机器路径 `/Users/praise/...`（实测须清零：`gd.md` 4 处、`goal-gd.md` 1 处、`uninstall-gd-command.sh` 1 处）。
- 被 plan / execute / review 的**目标项目根** **MUST** 经 `${CLAUDE_PROJECT_DIR}` 及既有解析顺序获取，**MUST NOT** 与框架根 `${CLAUDE_PLUGIN_ROOT}` 混淆——二者混用会把用户项目误写回插件目录。

*Rationale*：`${CLAUDE_PLUGIN_ROOT}` 在 command 正文 / bash 块可用已由 openai-codex 范本实证；写死开发者路径 = 别人机器第一步就找不到 prompts/templates/scripts，链路直接哑火。

### P3 · 分发完整性 (Distribution Completeness)

- 插件 bundle **MUST** 包含链路 runtime 引用的全部顶层目录：`commands` / `scripts`（含 `scripts/lib/`）/ `prompts` / `templates` / `schema` / `docs` / `fixtures`。
- 任一链路 runtime 引用的文件若不在 bundle 内 = 阻断（blocking）；打包验证 **MUST** 能检出缺漏，**MUST NOT** 让「链路跑到一半找不到文件」在安装者机器上才暴露。
- bundle **MUST NOT** 包含仅服务旧「安装到 `~/.claude`」模型的脚本（`install-gd-command.sh` / `uninstall-gd-command.sh` / `check-gd-command-parity.sh`），以免两套安装逻辑在安装者机器上并存打架。

*Rationale*：实测 `templates` 被 gd.md 引用 13 次、`scripts` 8 次，漏任一目录链路中途即断；裁掉旧安装脚本是 lab→插件模型切换的必然结果。

### P4 · Runtime 写入隔离 (Runtime Write Isolation)

- 链路运行时产物（`reports` / `baselines` / ledger / logs / mapped / manifest）**MUST** 写入 `${CLAUDE_PLUGIN_DATA}` 或调用方显式指定的目标项目路径。
- **MUST NOT** 写入插件安装目录（`~/.claude/plugins/cache/...`）——该目录在 `/plugin update` 时被覆盖，且可能只读。
- 凡默认写入路径指向框架根 / 插件目录的脚本，打包前 **MUST** 重定向到 `${CLAUDE_PLUGIN_DATA}` 或目标项目，并保留 `--out-dir` 等调用方覆写能力。

*Rationale*：实测 suite-controller / codex-bridge 会写 reports/ledger/manifest 等 6 类产物；写进插件目录 → 更新即丢数据或只读写失败，是「装完能跑一次、更新后崩」的隐性回归源。

### P5 · 外部依赖显式声明 + 缺失 fail-closed (Explicit External Deps, Fail-Closed on Absence)

- 插件无法自动安装的外部依赖 **MUST** 在 README 前置条件逐项声明，至少含：`codex` CLI + 认证、Python **≥3.9**（实测 28 文件用泛型下标注解）、以及链路实际调用的其他二进制（git / shasum 等）。
- 缺依赖时链路 **MUST** fail-closed 并给**中文**可读提示（说明缺什么、如何安装），**MUST NOT** 静默降级，**MUST NOT** 只抛英文 `transport_failed` 让安装者误判插件损坏。
- 特别地：`codex` 不可用时 L2/L3 cross-review **MUST NOT** 产出仅 Claude 的 `APPROVED`（与 `docs/constitution.md` P4 fail-closed 一致）。零 pip 依赖（全 stdlib + 本地 `lib/`）已实测成立，**MUST** 保持，新增链路代码 **MUST NOT** 引入需 `pip install` 的第三方包。

*Rationale*：L1 不依赖 codex 可独立跑，但 L2/L3 cross-review 硬依赖 codex（9 处调用），插件机制装不了它；不把前置讲清 + 不给人话提示，安装者会把「缺依赖」误读成「插件坏了」。

### P6 · 更新可控、版本即 SHA (Controlled Manual Update, SHA-as-Version)

- 分发采用 git-subdir 同仓布局（插件作为 Project GD 仓的子目录，无独立 build 步骤）。
- `plugin.json` **MUST** 省略 `version` 字段（git SHA 即版本）：开发者 `git commit && git push` 即发布；**SHOULD NOT** 引入手动 bump 语义版本的纪律负担（除非用户要求安装者看到人读版本号）。
- 安装者更新 **MUST** 仅走手动三命令（`/plugin marketplace update <mkt>` → `/plugin update <plugin>@<mkt>` → `/reload-plugins`），**MUST NOT** 引入任何 auto-update 基础设施（用户明确不要）。
- 更新三命令 **MUST** 写进安装 README，否则安装者无从获取后续链路改动。

*Rationale*：用户已定——只给安装者手动更新命令、不要自动更新；省略 version 让「push 即发布」成立、免去 bump 纪律。

## 变更边界 (Change Boundaries)

**范围内**：将 L1/L2/L3 三条链路打包为可分发插件，及其安装 / 更新 / 分发机制。

**范围外 / 边界约束**：

- **MUST NOT** 在本工作中重定义任一链路的审查行为或 review 判定语义——那归 `docs/constitution.md` (v1.0.0)；本文件只治理「如何打包与分发」。
- 插件脚手架（`.claude-plugin/`、`plugin.json`、`marketplace.json`、安装 README）**MUST** 落在 `Project GD/**` 内（lab-local，可直接改）。
- 安装由 `/plugin` 机制接管，**MUST NOT** 再向 `~/.claude/commands/` 写入命令副本（旧 `install-gd-command.sh` → `~/.claude` 模型作废）；此切换反而比旧模型更贴合 lab-only 约束（所有源都在 `Project GD/**`）。
- **MUST NOT** 自动 `commit` / `push`；终点只产出可提交态，由 `commit-projects` / `submit-mr` 触发。

## 与 L3 Constitution 的关系 (Relationship to docs/constitution.md)

- 两份 constitution 范围**不重叠**：本文件治理「插件打包与分发」，`docs/constitution.md` (v1.0.0) 治理「L3 review 机制优化」。
- 重叠面（输出契约全中文 / `REV_VERDICT` / 执行完成模板 / 不自动 commit）二者措辞一致；如未来出现冲突，在各自领域内以本领域 constitution 为准，跨领域以**更严格者**为准并在 spec 显式标出。
- 两份均 **MUST NOT** 凌驾于 `~/.claude/CLAUDE.md` 用户全局规则与项目 `CLAUDE.md` 硬约束之上（三者冲突时以更严格者为准）。

## 输出契约 (Output Contract)

本文件**继承** `docs/constitution.md` 的「输出契约」段（全中文 / `REV_VERDICT` ∈ {`APPROVED`,`REQUIRES_CHANGES`,`FAILED`} / mutation 后套用「执行完成」模板），**不复述**以避免两套措辞漂移。如该段未来修订，本文件自动跟随其最新版本。

## Governance

- **修订程序**：修改本文件任一原则 **MUST** 经 PR + 用户批准，并按版本策略 bump。本 constitution 在「插件打包与分发」领域内优先级高于本仓其他 spec/plan 的冲突措辞。
- **版本策略**（语义化）：MAJOR = 删除/重定义原则等向后不兼容治理变更；MINOR = 新增原则/章节或实质性扩展；PATCH = 措辞澄清 / typo / 非语义调整。
- **合规审查**：插件封装的 `/gd plan` `Review 对齐` 与后续 spec **MUST** 引用本 constitution 原则编号（P1–P6）作为质量约束；每份插件 spec/plan **MUST** 声明它遵循哪些原则、以及（若有）申请豁免哪条及理由。

**Version**: 1.0.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-10
