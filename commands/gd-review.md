---
description: GD L3 · 审查（等价 /gd review）。自动识别 target（代码/执行结果/代码+结果）后路由审查。
---

# /gd-review — 等价 `/gd review`（统一审查路由）

`/gd review`（不带第二 token）的顶层快捷别名。自动调 `gd-detect-review-target.py` 识别 target（code / execution / combined / plan / no-artifact），无需手动指定审什么。
> 若明确只审计划，直接用 `/gd-review-plan`。

**执行**：读取 `gd.md` 全文（插件 `${CLAUDE_PLUGIN_ROOT}/commands/gd.md`；本地 `~/.claude/commands/gd.md`，二者同目录），按其**统一审查路由段落**（gd.md 中标题 `### /gd review (unified router …)`，全篇唯一；区别于 `/gd review plan`、`/gd review code` 子段）执行 `stage = review`（无第二 token → unified router），**完整遵守 gd.md 声明的全部全局合约与该阶段规则**（gd.md 为唯一权威，本文件不复述以免漂移）。下方用户参数等价 `/gd review $ARGUMENTS`。

$ARGUMENTS
