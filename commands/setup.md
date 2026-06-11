---
description: Project GD 插件预设配置命令（与三链路 /review1 /review2 /gd 并列）。以选项菜单采集 4 个安装者预设字段——审查产物输出位置 / codex key（官方·第三方两类）/ codex 模型 / 模型强度 effort，持久化到 ${CLAUDE_PLUGIN_DATA}，可随时重跑单独改任一项，零内置默认 key。
---

# /setup Command

> **作用**：配置本插件的安装者预设。与三条链路命令（`/review1` / `/review2` / `/gd`）并列分发。
> **可重跑**：本命令**非一次性**——你可以随时再次运行进入配置、单独修改任意一项，无需重装插件、不丢其他项。
> **持久化位置**：预设写入 `${CLAUDE_PLUGIN_DATA}/gd-setup-config.json`（更新安全目录，插件 `update` 不清除）。

---

## 它配什么（4 个选项制字段）

所有字段**以选项菜单呈现，不允许自由填路径/值**——自由填易破坏传输协同与隔离。

| 字段 | 含义 | 取值（选项制） |
|------|------|---------------|
| a · 审查产物输出位置 | 链路运行时产物（reports / baselines 等）默认写到哪 | `plugin_data`（`${CLAUDE_PLUGIN_DATA}` 隔离区，默认）/ `target_project`（目标项目内）/ `cwd`（当前目录） |
| b · codex key 类型 + 值 | cross-review 用的 codex 认证 | key **类型**两类选项：`official`（官方）/ `third_party`（第三方代理）；两类映射不同 provider / base_url / env_key。类型选定后输入 key 值（你自备，绝不内置默认 key） |
| c · codex 模型 | cross-review 用哪个模型 | `gpt-5.4` / `gpt-5.4-mini` / `gpt-5` 等选项 |
| d · 模型强度（effort） | 推理强度 | `low` / `medium` / `high` / `xhigh` |

> **HANDOFF_ROOT 不在本预设内。** 传输协调目录 `HANDOFF_ROOT`（daemon↔client 必须一致）由插件管理、不让安装者填——填错即断链。本命令只管上面 4 项。

---

## 怎么用

直接运行本命令进入交互式选项菜单：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gd-plugin-setup.sh"
```

- 按菜单逐项选择；key 值仅在你选定类型后输入，**不随插件分发、不写入 git**。
- 想只改某一项时，重跑本命令并在该项选择新值即可——其他项保持上次配置。
- 只读自检（不交互、不写文件，用于验证配置形态）：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gd-plugin-setup.sh --self-check"
```

> 注：本命令仅采集 + 持久化预设，**不触发任何链路**。配置完成后再去跑 `/review1` / `/review2` / `/gd`。
