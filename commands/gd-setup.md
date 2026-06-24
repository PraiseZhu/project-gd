---
description: Project GD 插件预设配置命令（与三链路 /review1 /review2 /gd 并列）。以选项菜单采集 5 个安装者预设字段——审查产物输出位置 / codex key（官方·第三方两类）/ codex 模型 / 模型强度 effort / 运行环境，持久化到 ${CLAUDE_PLUGIN_DATA}，可随时重跑单独改任一项，零内置默认 key。
---

# /gd-setup Command

> **作用**：配置本插件的安装者预设。与三条链路命令（`/review1` / `/review2` / `/gd`）并列分发。
> **可重跑**：本命令**非一次性**——你可以随时再次运行进入配置、单独修改任意一项，无需重装插件、不丢其他项。
> **持久化位置**：预设写入 `${CLAUDE_PLUGIN_DATA}/gd-setup-config.json`（更新安全目录，插件 `update` 不清除）。

---

## 它配什么（5 个选项制字段）

所有字段**以选项菜单呈现，不允许自由填路径/值**——自由填易破坏传输协同与隔离。

| 字段 | 含义 | 取值（选项制） |
|------|------|---------------|
| a · 审查产物输出位置 | 链路运行时产物（reports / baselines 等）默认写到哪 | `plugin_data`（`${CLAUDE_PLUGIN_DATA}` 隔离区，默认）/ `target_project`（目标项目内）/ `cwd`（当前目录） |
| b · codex key 类型 + 值 | cross-review 用的 codex 认证 | key **类型**两类选项：`official`（官方）/ `third_party`（第三方代理）；两类映射不同 provider / base_url / env_key。类型选定后输入 key 值（你自备，绝不内置默认 key） |
| c · codex 模型 | cross-review 用哪个模型 | `gpt-5.5` / `gpt-5.4` / `gpt-5.4-mini` 等选项 |
| d · 模型强度（effort） | 推理强度 | `none` / `low` / `medium` / `high` / `xhigh` |
| e · 运行环境 | maker `/` 补全的薄壳 skill 放哪 | `xdt_maker`（生成 7 个薄壳到 `${GD_PROJECT_ROOT}/.claude/skills/`，project scope，maker 扫 project skills）/ `claude_code`（移除薄壳，用 plugin command，`${CLAUDE_PLUGIN_ROOT}` 由 Claude Code 自动注入） |

> **HANDOFF_ROOT 不在本预设内。** 传输协调目录 `HANDOFF_ROOT`（daemon↔client 必须一致）由插件管理、不让安装者填——填错即断链。本命令只管上面 5 项。
> **`gd_project_root` 不需安装者填。** 薄壳渲染需要的 plugin 根绝对路径由脚本从自身位置推断并随配置持久化（非硬编码，解决可移植）；安装者不碰。

---

## 怎么用

直接运行本命令进入交互式选项菜单：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gd-plugin-setup.sh"
```

- 按菜单逐项选择；key 值仅在你选定类型后输入，**不随插件分发、不写入 git**。
- 想只改某一项时，重跑本命令并在该项选择新值即可——其他项保持上次配置。
- **运行环境（e）的后置动作**：选 `xdt_maker` 时，本命令在持久化后自动生成 7 个 maker 薄壳到 `${GD_PROJECT_ROOT}/.claude/skills/`；选 `claude_code` 时自动移除。换环境时重跑本命令即可自动切换，无需手动操作。
- 只读自检（不交互、不写文件，用于验证配置形态 + 薄壳状态）：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gd-plugin-setup.sh --self-check"
```

- 单独生成 / 移除薄壳（不交互、不改其他预设，用于排查或手工切换）：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gd-plugin-setup.sh --gen-shells"   # 生成 7 薄壳（runtime_env=xdt_maker 时）
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gd-plugin-setup.sh --rm-shells"    # 移除 7 薄壳
```

> 注：本命令仅采集 + 持久化预设（并按运行环境生成/移除薄壳），**不触发任何链路**。配置完成后再去跑 `/review1` / `/review2` / `/gd`。

> **薄壳与 plugin command 的关系**：两套入口等价、读同一份 command 文件（`gd.md` / `gd-setup.md` / `review1.md` / `review2.md`）。maker（xdt maker）选 `xdt_maker` 用薄壳（因 maker 不自动展开 `${CLAUDE_PLUGIN_ROOT}`，薄壳给出绝对路径）；Claude Code 选 `claude_code` 用 plugin command（`${CLAUDE_PLUGIN_ROOT}` 自动注入，无需薄壳）。薄壳是 project scope（`Project GD/.claude/skills/`），不污染全局。
