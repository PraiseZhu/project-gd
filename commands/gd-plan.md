---
description: GD L3 · 生成计划（等价 /gd plan）。多 Agent planning dispatch + task packets。
---

# /gd-plan — 等价 `/gd plan`

`/gd plan` 的顶层快捷别名，行为完全等价，不引入新语义。

**执行**：读取 `gd.md` 全文（插件 `${CLAUDE_PLUGIN_ROOT}/commands/gd.md`；本地 `~/.claude/commands/gd.md`，二者同目录），按其 **`### /gd plan`** 段落执行 `stage = plan`，**完整遵守 gd.md 声明的全部全局合约与该阶段规则**（gd.md 为唯一权威，本文件不复述以免漂移）。下方用户参数等价 `/gd plan $ARGUMENTS`。

$ARGUMENTS
