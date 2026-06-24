<!--
gd-skill-shell-template.md — maker 适配薄壳生成模板（单一权威骨架）。

由 scripts/gd-plugin-setup.sh --gen-shells 消费：读取本文件，对 7 个 skill
（gd-plan / gd-review-plan / gd-exec / gd-review / gd-setup / review1 / review2）
各自替换下列 4 个占位符后，落地到 ${GD_PROJECT_ROOT}/.claude/skills/<name>/SKILL.md。

占位符（仅 4 个，故意为最小集——薄壳不复述 plugin 逻辑，body 越薄漂移越小）：
  {{SKILL_NAME}}       skill 名（= trigger，= 文件 dir 名）
  {{DESCRIPTION}}      frontmatter description（含中文用途说明，maker `/` 补全展示的就是它）
  {{GD_PROJECT_ROOT}}  plugin 根绝对路径（/gd-setup 采集时从脚本位置推断并持久化到 config；
                       非硬编码，解决 P1 可移植）
  {{REDIRECT_TARGET}}  本薄壳读取的 plugin command 文件名（gd.md / gd-setup.md /
                       review1.md / review2.md）

生成后的薄壳只是 maker `/` 补全的适配壳：被触发时读 ${GD_PROJECT_ROOT}/commands/<REDIRECT_TARGET>
全文并按其指令执行。不复述任何阶段路由、模板、schema 路径——全部从原文取。
若该 command 文件不存在 → blocked_missing_artifact fail-closed。
-->
---
name: {{SKILL_NAME}}
description: {{DESCRIPTION}}
trigger: {{SKILL_NAME}}
---

# /{{SKILL_NAME}} — maker 适配薄壳

> 本 skill 是 maker `/` 补全的**适配薄壳**，让 `/{{SKILL_NAME}}` 在 maker 里能被搜到并触发。真正权威是 plugin 的 `{{REDIRECT_TARGET}}`，本文件不复述其逻辑以免漂移。

## 路径解析（覆盖 plugin 的 CLAUDE_PLUGIN_ROOT）

```
GD_PROJECT_ROOT: {{GD_PROJECT_ROOT}}
```

- 等价别名 `GD_ROOT` 同此值（部分 command 用 `GD_ROOT`）。
- 读取 `{{REDIRECT_TARGET}}` 时，其中字面量 `${CLAUDE_PLUGIN_ROOT}` 即此绝对路径。
- `{{REDIRECT_TARGET}}` body 全程用 `${GD_PROJECT_ROOT}` 拼路径，故 body 不需任何改动。

## 触发后行为

被触发时（用户敲 `/{{SKILL_NAME}} ...`）：

1. **读取** `${GD_PROJECT_ROOT}/commands/{{REDIRECT_TARGET}}` 全文。
2. 按 `{{REDIRECT_TARGET}}` 对应段落的指令执行——具体阶段路由、合约、模板、schema 路径全部从原文取，本薄壳不复述。
3. **完整遵守 `{{REDIRECT_TARGET}}` 声明的全部规则与合约**（以原文实际声明为准——review 链路含 child-dispatch/fail-closed/closure eligibility 等；setup 等配置命令含全选项制/零内置 key 等）。`{{REDIRECT_TARGET}}` 为唯一权威。

## 边界

- 本薄壳不复制 `{{REDIRECT_TARGET}}` 任何逻辑、模板、schema 路径——全部从原文取。
- plugin 的 `/{{SKILL_NAME}}` command（打全名）仍可直接用，二者读同一份 `{{REDIRECT_TARGET}}`，行为等价。
- 若 `${GD_PROJECT_ROOT}/commands/{{REDIRECT_TARGET}}` 不存在 → 输出 `blocked_missing_artifact: {{REDIRECT_TARGET}} not found at <path>`，停止。
