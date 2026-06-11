# 目标驱动链（Project GD）插件 — 安装与前置

本插件把**目标驱动链**（Project GD）的**三条 review 链路**封装为可分发的 Claude Code 插件：

- `/review1`（L1）：codex 交叉讨论 + 轻量审核
- `/review2`（L2）：profile-aware Codex 工作台
- `/gd`（L3）：四阶段（计划 → 审计划 → 执行 → 审代码）多 Agent 链

外加一个与三链路并列的 `/setup` 命令，用来配置安装者预设（审查产物输出位置 / codex key / codex 模型 / 模型强度）。

> **真实交付是两段式，不是一步到位。** 装插件是一行命令（下方「安装」段）；但链路的 cross-review 完整功能额外依赖 codex 传输栈——外部 codex CLI、安装者自己的认证 key、codex-watch daemon 部署——这部分插件装不了、密钥也不能随插件分发。所以请把「安装」与「codex 传输栈前置」分两段分别完成。

---

## 第 0 步 · 前提（先确认，否则后续命令拉不到来源或跑不动）

- **仅支持 macOS。** 传输层 daemon 基于 macOS LaunchAgent + launchctl 部署；Windows / Linux 本期 out-of-scope，不要在其他平台尝试安装。
- **需要私有 GitLab 仓库的访问权与凭据。** 分发源是私有 GitLab（`git@git.xindong.com:game-ui/project-gd.git`），没有 repo 访问权连 marketplace 来源都拉不到。请先确认你的 SSH/凭据能访问该仓库。
- 安装者本机已装有支持 `claude plugin marketplace add` / `install` / `update` 命令族的 Claude Code 版本。

---

<!-- gd-install-section -->
## 安装（一行命令装插件命令 + 一次 reload）

在终端粘贴**一行命令**完成注册 marketplace + 安装插件：

```bash
claude plugin marketplace add git@git.xindong.com:game-ui/project-gd.git && claude plugin install project-gd@project-gd-marketplace
```

然后在 Claude Code 里 reload 一次（命令面板执行 `/reload-plugins`，或重启 Claude Code）。reload 之后，`/review1`、`/review2`、`/gd`、`/setup` 会出现在可用命令列表并可触发。

- 本段交付的是**插件命令 + 框架内文件**。命令能不能跑出真实的 cross-review 结论，取决于下一段的 codex 传输栈前置。
- 本段**无需**手动编辑任何路径或配置文件，**无需** `pip install` 任何包。
- 命令安装完全由 `/plugin` 机制接管，不会向你的 `~/.claude/commands/` 写入命令副本。

<!-- /gd-install-section -->

---

<!-- gd-transport-prereq-section -->
## codex 传输栈前置（cross-review 完整功能所需，插件装不了，需你自备）

三条链路的 cross-review 命脉是 codex 传输栈。它**不在**上面那一行命令里——需要你一次性完成下面**三件套**。三件套缺任一环，cross-review 会 fail-closed（命令在，但审查跑不动），并给中文提示。

### ① codex CLI 二进制 + 认证

插件装不了外部二进制，你需要自行安装并认证 codex CLI：

```bash
npm i -g @openai/codex --prefix ~/.local
command -v codex   # 确认在 PATH
```

### ② 自备 codex 认证 key（官方 key 或第三方代理 key 两类，密钥不随插件分发）

这正是**单行安装命令无法直接交付 cross-review 全部能力的根本原因**——key 是你自己的凭据，分发物里绝不内置任何 key。请通过 `/setup` 命令选择 key 类型（官方 / 第三方代理）并填入你自己的 key 值；两类 key 对应不同的 codex provider / base_url / env_key。`/setup` 可随时重跑，单独改 key 不影响其他配置。

### ③ 部署 codex-watch daemon

跑 bundle 内的传输部署脚本，把 daemon 装到 `~/.claude/handoff` + LaunchAgent，并把你的 key 注入 daemon 运行环境：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/vendor/l3-transport/scripts/install-transport.sh --dry-run"  # 先预览
bash "${CLAUDE_PLUGIN_ROOT}/vendor/l3-transport/scripts/install-transport.sh --yes"      # 执行部署
```

完成三件套后，对一个非 GD 的目标项目跑 `/review2` 或 `/gd` 的 cross-review，即可拿到含 codex 侧意见的真实结论（非 fail-closed、非仅 Claude 的 APPROVED）。

<!-- /gd-transport-prereq-section -->

---

## 更新（维护者 push 即发布，安装者手动更新，无自动更新）

维护者改完链路 `git push` 即视为发布新版本（版本即 git SHA）。安装者按下面命令块手动更新（≤3 条命令）：

<!-- gd-update-commands:start -->
```bash
claude plugin marketplace update project-gd-marketplace
claude plugin update project-gd@project-gd-marketplace
```
然后 `/reload-plugins`（或重启 Claude Code）。
<!-- gd-update-commands:end -->

> **传输层改动需额外一步。** 如果本次更新涉及 `vendor/l3-transport/**`（daemon / binary / plist），上面三条命令之外，还要重跑 `install-transport.sh` 重新部署 daemon：
>
> ```bash
> bash "${CLAUDE_PLUGIN_ROOT}/vendor/l3-transport/scripts/install-transport.sh --yes"
> ```

---

## 配置预设（可随时重跑）

安装并备齐前置后，跑 `/setup` 配置安装者预设——审查产物输出位置、codex key（官方 / 第三方两类）、codex 模型、模型强度（effort）。四项全部以选项呈现，不让你自由填路径/值；预设存于更新安全位置，插件 `update` 不会清除；可随时重跑 `/setup` 单独修改任一项，不丢其他配置。
