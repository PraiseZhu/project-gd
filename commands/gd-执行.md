---
description: GD L3 · 执行（等价 /gd execute，/gd-exec 的中文别名）。agent_exec 子 agent 化执行。
---

# /gd-执行 — 等价 `/gd execute`

`/gd execute` 的顶层快捷别名（`/gd-exec` 的中文等价），行为完全等价。
> 中文命令名每次需切输入法；想纯英文快打用 `/gd-exec`（等价，可删其一）。

**执行**：读取 `gd.md` 全文（插件 `${CLAUDE_PLUGIN_ROOT}/commands/gd.md`；本地 `~/.claude/commands/gd.md`，二者同目录），按其 **`### /gd execute`** 段落执行 `stage = execute`，**完整遵守 gd.md 声明的全部全局合约与该阶段规则**（gd.md 为唯一权威，本文件不复述以免漂移）。下方用户参数等价 `/gd execute $ARGUMENTS`。

$ARGUMENTS
