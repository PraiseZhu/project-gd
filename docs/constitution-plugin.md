<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.1.0  [MINOR amendment]
Bump rationale: ① 修正范围定义的事实错误——原文把 L1/L2/L3 误述为「/gd 四阶段」，
  实为三条独立命令 /review1（L1）· /review2（L2）· /gd（L3，四阶段在 /gd 内部）；
  ② 把 codex 传输层（vendor/l3-transport + codex-watch daemon）纳入 P3 分发完整性
  与 P5 外部依赖治理——此前完全缺失，是「装完命令但 cross-review 全 fail-closed」的根因。

Principles (6，编号不变；P3/P5 本次实质扩展):
  P1 一行安装、装完即用 (One-Command Install, Run on Arrival)
  P2 路径可移植，零硬编码绝对路径 (Portable Paths, Zero Hardcoded Absolutes)
  P3 分发完整性 (Distribution Completeness)        ← 扩展：纳入 vendor/l3-transport
  P4 Runtime 写入隔离 (Runtime Write Isolation)    ← 扩展：区分「传输层前置部署」与「插件写入」
  P5 外部依赖显式声明 + 缺失 fail-closed            ← 扩展：codex 传输栈（CLI + 自备 key + daemon）
  P6 更新可控、版本即 SHA (Controlled Manual Update, SHA-as-Version)

Sections: 变更边界 / 与 L3 Constitution 的关系 / 输出契约 / Governance

Files needing sync:
  ✅ docs/constitution.md — 一致（范围不重叠：本文件治理「打包与分发」，那份治理「L3 review 机制」）
  ✅ specs/gd-plugin-packaging/spec.md — 同步更新（架构订正 + 传输层 FR + 2 项 clarification 回填）
  ⚠ 待处理：.claude-plugin/plugin.json + marketplace.json + 安装 README（届时回填本报告为 ✅）

Deferred TODO: none（RATIFICATION_DATE = 2026-06-10；LAST_AMENDED = 2026-06-11）
-->

# Project GD Plugin Constitution

> **适用范围**：本 constitution 治理「将 Project GD 的**三条 review 链路**封装为可分发 Claude Code 插件」的工作——即「如何打包、如何让他人一行命令安装、如何更新分发」。
>
> **三条链路 = 三个独立命令**（这是 v1.1.0 的关键订正；早期版本误把它们说成「/gd 四阶段」）：
> - **L1 = `/review1`**：codex 交叉讨论 + 轻量 review
> - **L2 = `/review2`**：profile-aware Codex 工作台
> - **L3 = `/gd`**：四阶段（计划 → 审计划 → 执行 → 审代码）多 agent 链
>
> 「四阶段」是 **L3 一个命令的内部阶段**，不是三条链路本身。「封装三条链路」= 封装 `/review1` + `/review2` + `/gd` 三个命令及其全部运行时依赖。
>
> 本文件**不**重定义链路审查行为；审查机制语义归 [`docs/constitution.md`](./constitution.md) (v1.0.0)。本文件是 `/spec2`（spec 编写）→ `/spec3`（澄清）→ `/gd plan` 链路中、针对插件封装工作的最前置决策层，与 `CLAUDE.md`、`PROJECT_GOAL.md` 互补而非替代。

## Core Principles

### P1 · 一行安装、装完即用 (One-Command Install, Run on Arrival)

本次工作的北极星：他人 **MUST** 能用一行可粘贴的终端命令完成**插件**安装，reload 后立即使用插件提供的全部链路命令（`/review1` / `/review2` / `/gd`）。

- 插件安装路径 **MUST** 收敛为单行：`claude plugin marketplace add <repo> && claude plugin install <plugin>@<mkt>`（`&&` 串接 = 一行终端命令）。
- 「装完即用」严格定义为 **install + reload/restart 后命令可用**；安装 README **MUST** 显式包含 reload 步骤，**MUST NOT** 暗示 install 后无需重载即生效。
- 「装完即用」**MUST** 由跨机 / 跨目录冒烟（在非 Project GD 目录、模拟他人环境跑通 happy path）证明，**MUST NOT** 仅凭本仓自身目录的 self-test 断言成立。
- **范围诚实（v1.1.0 新增）**：一行命令交付的是**插件命令 + 框架内文件**。链路的 **cross-review 完整功能**额外依赖 codex 传输栈（见 P5），后者**不是**一条命令可达——安装 README **MUST** 把「一行装插件命令」与「自备 codex 传输栈前置」分两段写清，**MUST NOT** 宣称「复制一条命令即得三链路完整功能」。

*Rationale*：用户北极星是「分享给他人、尽量少步骤即可用」；但 codex 传输栈（外部二进制 + 密钥 + daemon）插件装不了，把「插件一行装」与「codex 前置」混为一谈会让安装者误判「装完应当全功能」，反而崩塌信任。诚实分段才守得住北极星。

### P2 · 路径可移植，零硬编码绝对路径 (Portable Paths, Zero Hardcoded Absolutes)

- 命令 / 脚本引用框架内文件 **MUST** 经 `${CLAUDE_PLUGIN_ROOT}` 解析；Python 脚本沿用 `Path(__file__).resolve().parent.parent` 自解析（已实测可移植，无需改动）。
- 交付物 **MUST NOT** 含任何字面开发者机器路径 `/Users/praise/...`（实测须清零：`gd.md`、`review1.md`、`review2.md`、`goal-gd.md`、`uninstall-gd-command.sh` 中的开发者绝对路径）。
- 被 plan / execute / review 的**目标项目根** **MUST** 经 `${CLAUDE_PROJECT_DIR}` 及既有解析顺序获取，**MUST NOT** 与框架根 `${CLAUDE_PLUGIN_ROOT}` 混淆——二者混用会把用户项目误写回插件目录。

*Rationale*：`${CLAUDE_PLUGIN_ROOT}` 在 command 正文 / bash 块可用已由 openai-codex 范本实证；写死开发者路径 = 别人机器第一步就找不到 prompts/templates/scripts，链路直接哑火。

### P3 · 分发完整性 (Distribution Completeness)

- 插件 bundle **MUST** 包含三条链路 runtime 引用的全部顶层目录：`commands`（含 `review1.md` / `review2.md` / `gd.md` **三个命令文件**）/ `scripts`（含 `scripts/lib/`）/ `prompts` / `templates` / `schema` / `docs` / `fixtures`。
- **`vendor/l3-transport/` MUST 进 bundle（v1.1.0 新增）**：L1/L3 的 cross-review 直接从 `vendor/l3-transport/scripts/{codex-consult.sh,review-result-writer.sh}` 运行，且传输层的 daemon/binary/plist/install-transport.sh 都在此目录。漏掉它 = 三条链路的 cross-review 在安装者机器上**全部 fail-closed**（命令在、审查跑不动）。
- 任一链路 runtime 引用的文件若不在 bundle 内 = 阻断（blocking）；打包验证 **MUST** 能检出缺漏，**MUST NOT** 让「链路跑到一半找不到文件」在安装者机器上才暴露。
- bundle **MUST NOT** 包含仅服务旧「安装到 `~/.claude/commands`」模型的脚本（`install-gd-command.sh` / `uninstall-gd-command.sh` / `check-gd-command-parity.sh`），以免两套**命令**安装逻辑并存打架。注意：这与 `vendor/l3-transport/scripts/install-transport.sh`（部署 codex 传输 daemon，属 P5 前置）是**两回事**，后者保留并进包。

*Rationale*：实测 `templates` 被 gd.md 引用 13 次、`scripts` 8 次，漏任一目录链路中途即断；而 `vendor/l3-transport` 是三链路 cross-review 的传输命脉，原 spec/constitution 完全漏列——这是「装完命令却全 fail-closed」的头号根因，故升为 blocking。

### P4 · Runtime 写入隔离 (Runtime Write Isolation)

- 链路运行时产物（`reports` / `baselines` / ledger / logs / mapped / manifest）**MUST** 写入 `${CLAUDE_PLUGIN_DATA}` 或调用方显式指定的目标项目路径。
- **MUST NOT** 写入插件安装目录（`~/.claude/plugins/cache/...`）——该目录在 `/plugin update` 时被覆盖，且可能只读。
- 凡默认写入路径指向框架根 / 插件目录的脚本，打包前 **MUST** 重定向到 `${CLAUDE_PLUGIN_DATA}` 或目标项目，并保留 `--out-dir` 等调用方覆写能力。
- **区分「传输层前置部署」与「插件写入」（v1.1.0 新增）**：codex 传输栈经 `install-transport.sh` 部署到 `~/.claude/handoff` + `~/Library/LaunchAgents`，这是安装者一次性的**前置基础设施 setup**（同 codex CLI 一样属外部依赖范畴，见 P5），**不**违反「插件 MUST NOT 写 `~/.claude/commands`」的禁区——二者是不同路径、不同性质。插件**命令**仍只走 `/plugin` 机制，**MUST NOT** 写 `~/.claude/commands`。

*Rationale*：实测 suite-controller / codex-bridge 会写 reports/ledger/manifest 等 6 类产物；写进插件目录 → 更新即丢数据或只读写失败。传输 daemon 必须落在 `~/.claude/handoff`（客户端硬编码引用，待解耦）——把它和「插件命令写入」混为一谈会让 P3/P4 自相矛盾，故显式区分。

### P5 · 外部依赖显式声明 + 缺失 fail-closed (Explicit External Deps, Fail-Closed on Absence)

- 插件无法自动安装的外部依赖 **MUST** 在 README 前置条件逐项声明。**codex 传输栈（v1.1.0 明确为三件套）**至少含：
  1. **codex CLI 二进制** + 其认证（插件装不了外部二进制）。
  2. **安装者自备的 codex / TAPSVC 认证 key**——这是**密钥，MUST NOT 随插件分发**；安装者必须用自己的凭据。这是「复制一条命令即全功能」**做不到**的根本原因，README MUST 讲明。
  3. **codex-watch daemon 部署**——经 bundle 内 `vendor/l3-transport/scripts/install-transport.sh` 装到 `~/.claude/handoff` + LaunchAgent，并把 key 注入 daemon 环境（`launchctl setenv` 或写进 plist）。
  - 以及链路实际调用的其他二进制（git / shasum 等）、Python **≥3.9**（实测 28 文件用泛型下标注解）。
- 缺依赖时链路 **MUST** fail-closed 并给**中文**可读提示（说明缺什么、如何安装），**MUST NOT** 静默降级，**MUST NOT** 只抛英文 `transport_failed` 让安装者误判插件损坏。
- 特别地：codex 不可用时 L2/L3 cross-review **MUST NOT** 产出仅 Claude 的 `APPROVED`（与 `docs/constitution.md` P4 fail-closed 一致）。零 pip 依赖（全 stdlib + 本地 `lib/`）已实测成立，**MUST** 保持，新增链路代码 **MUST NOT** 引入需 `pip install` 的第三方包。

*Rationale*：L1 的纯 planning dispatch 可不依赖 codex 跑，但三条链路的 cross-review 核心硬依赖 codex 传输栈（CLAUDE.md「codex 依赖链」记 9+ 处调用，任一环缺整链断）。原 P5 只说「codex CLI + 认证」，漏了 daemon 部署与 key 不可分享这两个致命点；不补，安装者会把「缺传输栈」误读成「插件坏了」。

### P6 · 更新可控、版本即 SHA (Controlled Manual Update, SHA-as-Version)

- 分发采用 git-subdir 同仓布局（插件作为 Project GD 仓的子目录，无独立 build 步骤）。**分发源为私有 GitLab**（用户已定）——意味着安装者 MUST 先具备该 repo 的访问权与凭据，「一行命令」对**无访问权的外部人不直接成立**；README MUST 标明此前提。
- `plugin.json` **MUST** 省略 `version` 字段（git SHA 即版本）：开发者 `git commit && git push` 即发布；**SHOULD NOT** 引入手动 bump 语义版本的纪律负担（除非用户要求安装者看到人读版本号）。
- 安装者更新 **MUST** 仅走手动三命令（`/plugin marketplace update <mkt>` → `/plugin update <plugin>@<mkt>` → `/reload-plugins`），**MUST NOT** 引入任何 auto-update 基础设施（用户明确不要）。若传输层有更新，安装者还需重跑 `install-transport.sh`（README MUST 说明）。
- 更新命令 **MUST** 写进安装 README，否则安装者无从获取后续链路改动。

*Rationale*：用户已定——只给安装者手动更新命令、不要自动更新；省略 version 让「push 即发布」成立。私有 GitLab 分发是用户明确选择，但需诚实记录其对「一行命令对外人」的限制。

## 变更边界 (Change Boundaries)

**范围内**：将三条链路（`/review1` L1 / `/review2` L2 / `/gd` L3）打包为可分发插件，及其安装 / 更新 / 分发机制；codex 传输栈的**前置部署声明与文档**（不含代装外部二进制、不含分享密钥）。

**范围外 / 边界约束**：

- **MUST NOT** 在本工作中重定义任一链路的审查行为或 review 判定语义——那归 `docs/constitution.md` (v1.0.0)；本文件只治理「如何打包与分发」。
- 插件脚手架（`.claude-plugin/`、`plugin.json`、`marketplace.json`、安装 README）**MUST** 落在 `Project GD/**` 内（lab-local，可直接改）。
- 插件**命令**安装由 `/plugin` 机制接管，**MUST NOT** 再向 `~/.claude/commands/` 写入命令副本（旧 `install-gd-command.sh` → `~/.claude/commands` 模型作废）；但 codex 传输 daemon 部署到 `~/.claude/handoff` 属 P5 前置，不在此禁区内。
- **MUST NOT** 代装 codex CLI 等外部二进制、**MUST NOT** 在分发物中内置任何 API key/密钥。
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

**Version**: 1.1.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-11
