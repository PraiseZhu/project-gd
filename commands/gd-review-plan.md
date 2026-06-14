---
description: GD L3 · 审计划（等价 /gd review plan）。Claude self-review + Codex cross-review + merge/auto-fix。
---

# /gd-review-plan — 等价 `/gd review plan`

`/gd review plan` 的顶层快捷别名，行为完全等价。动手前审计划，防 AI 填表。

**执行**：读取 `gd.md` 全文（插件 `${CLAUDE_PLUGIN_ROOT}/commands/gd.md`；本地 `~/.claude/commands/gd.md`，二者同目录），按其 **`### /gd review plan`** 段落执行 `stage = review plan`，**完整遵守 gd.md 声明的全部全局合约与该阶段规则**（gd.md 为唯一权威，本文件不复述以免漂移）。下方用户参数（通常是待审 plan 文件路径）等价 `/gd review plan $ARGUMENTS`。

$ARGUMENTS
