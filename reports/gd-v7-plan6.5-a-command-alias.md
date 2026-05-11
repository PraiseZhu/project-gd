# Plan 6.5-A — 中文 Token Alias Segment Report（v2 收口）

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
START_MARKER (v1): reports/gd-v7-plan6.5-a.start.marker (2026-05-11T14:16:26Z)
START_MARKER (v2 follow-up): reports/gd-v7-plan6.5-a.v2.start.marker (2026-05-11T14:37:05Z)
GENERATED_AT: 2026-05-11T14:42:00Z
SEGMENT: A（中文命令别名 + help 表 + remaining_args 契约 + line 12 stale Plan 3 修正）
PARENT_PLAN: /gd Claude-first 收口 v4
DOWNSTREAM: B → C → D → E（A-D 不写 manifest active；E 才一次性 1.4.0）

## v1 → v2 follow-up patch（本节为 v2 增补）

v1 已 APPROVED (`/Users/praise/.claude/review-baselines/0575daff2583/result-20260511T142102Z.md`)，但事后 v2 plan 识别出两个 v1 实现缺陷：

| v2 加固项 | v1 缺陷 | v2 修复 |
|----------|--------|--------|
| **remaining_args 契约** | v1 用 "停止 token 序列分析（不读第二 token）" 措辞模糊；grep "remaining_args" 0 命中 | commands/gd.md §"Stage parsing" 规则 #3 显式加 `stage = mapped_stage; remaining_args = tokens[1:]` 契约 + 4 类 example；docs/gd-v7-claude-command.md §3 加同步 example |
| **stale Plan 3 prose 修正** | docs line 12 仍写 "当前阶段（Plan 3）只接四阶段入口"，与同文件 §2 表 active state (Plan 5 v5) 直接冲突 | line 12 改写为 "当前阶段（Plan 5 v5）已上线四阶段入口 + multi-agent dispatch + execution dispatch (human_exec) + 中文命令别名（Plan 6.5-A）"；其他 Plan 3 引用（owner plan 谱系 line 3 / install 流程历史 line 72 / install ledger 示例 line 91 / source_missing 应急 line 199）属事实记录，**不动** |
| **/gd 审查 negative case** | v1 docs 只有 `/gd 审` → help | docs/gd-v7-claude-command.md §3 加 `/gd 审查` → help（"同义词不模糊匹配"）+ `/gd 审 计划` → help（"即使第二 token 合法"）|

### v2 改动文件 hash 漂移

| 文件 | v1 末态 hash | v2 末态 hash |
|------|-------------|-------------|
| `commands/gd.md` | `cbc53b03141382d3…` | `652617cad4c6f843…` |
| `docs/gd-v7-claude-command.md` | `e6ec41b8e81241b2…` | `cd2b39771afcb587…` |

### v2 边界证据（hash 与 v2 before-hashes.txt 比对）

- `manifest.gd-v7.json` UNCHANGED `239389aec26ff1c1…` ✓
- `prompts/gd-review-standard.md` UNCHANGED `f4e0585bdfa7b1aa…` ✓（Plan B §8 范围）
- `scripts/gd-codex-review.py` UNCHANGED `39ca14127c5bcc25…` ✓（Plan B B6 范围）
- `/Users/praise/.claude/commands/gd.md` NOT_PRESENT ✓（Plan D 解冻范围）

### v2 验收全表

| v2 Test Plan 项 | 命令 | 结果 |
|-----------------|------|------|
| 5 中文 → stage 映射 | `grep -n "X.*stage = Y" commands/gd.md` ×5 | 全 ≥1 hit ✓ |
| remaining_args 契约 | `grep -n "remaining_args\|tokens\[1:\]"` | commands/gd.md 6 hits ✓ |
| `/gd 审` negative | `grep -n "审[^计代]"` | docs line 53 ✓ |
| `/gd 审查` negative | `grep -n "审查"` | docs line 32, 54 ✓ |
| `/gd 审 计划` 不合法 | `grep` line 55 | ✓ |
| 边界 hash | manifest / prompts / scripts | 3/3 UNCHANGED ✓ |
| installed copy | `[ -e /Users/.../commands/gd.md ]` | NOT_PRESENT ✓ |
| 未提前 active grep | `grep -niE "Codex bridge.*active\|gd review (code\|plan).*active"` | 0 hits ✓ |
| `/gd review code` 仍 pending_future_plan | grep | line 84 ✓ |
| line 12 stale Plan 3 已修 | `sed -n '12p'` | "当前阶段（Plan 5 v5）已上线..." ✓ |

---



---

## 1. 范围与原则

Plan 6.5 拆分 5 段（A/B/C/D/E）的第 1 段。**只补中文命令体验**，不改 review / execution / child / bridge 行为。

锁定的硬约束（用户在 plan 启动时再次确认）：

| 类别 | 状态 |
|------|------|
| 允许改 | `Project GD/commands/gd.md`（source）|
| 允许同步改 | `Project GD/docs/gd-v7-claude-command.md`（docs）|
| 禁止改 | `/Users/praise/.claude/commands/gd.md`（installed copy）— Plan D 解冻 hold |
| 禁止改 | 旧 `/review`、旧 `/rev`、hooks、daemon、MCP、Codex sidecar 标准 |
| 禁止 | 执行 install / uninstall |
| 禁止 | 写 `manifest.gd-v7.json` active revision（A-D 期间不动；E 一次性写 1.4.0）|

---

## 2. 改动文件清单

### 2.1 修改

| 文件 | before_hash | after_hash | 改动 |
|------|-------------|------------|-----|
| `commands/gd.md` | `09e4e4ce08c0e6f8…` | `cbc53b03141382d3…` | §"Stage parsing" 加规则 #3 中文单 token 别名（5 项严格白名单）；§"支持的 stage 全集" 改为中英文等价表；§"`/gd help`" 加中英文等价命令对照表 |
| `docs/gd-v7-claude-command.md` | `dad0c69a8aeabd6a…` | `e6ec41b8e81241b2…` | §2 五个 stage 表加中文命令列；§3 双 token 解析加中文路径说明 |

### 2.2 未触动（边界证据，hash 与 before-hashes.txt 一致）

| 文件 | hash 状态 |
|------|----------|
| `manifest.gd-v7.json` | UNCHANGED `239389aec26ff1c1…` — A-D 期间不写 manifest |
| `prompts/gd-review-standard.md` | UNCHANGED `f4e0585bdfa7b1aa…` — Plan B 范围 |
| `scripts/gd-codex-review.py` | UNCHANGED `39ca14127c5bcc25…` — Plan B B6 范围 |
| `/Users/praise/.claude/commands/gd.md` | NOT_PRESENT — Plan D 解冻 hold |
| `~/.claude/**` 其他路径 | 未写入（attributable=0）|

---

## 3. 中文 Token Alias 设计

### 3.1 严格白名单

5 个中文 token，单 token 直接映射 stage，不读第二 token：

| 中文 | stage | 等价英文命令 |
|------|-------|-------------|
| `帮助` | `help` | `/gd help` 或 `/gd`（空 args）|
| `计划` | `plan` | `/gd plan` |
| `审计划` | `review plan` | `/gd review plan` |
| `执行` | `execute` | `/gd execute` |
| `审代码` | `review code` | `/gd review code` |

### 3.2 为什么要严格白名单

避免歧义匹配：
- `审` 不在白名单 → 即使是 `/gd 审 计划` 也走 fallback help（符合"双 token review 只对英文 review 生效"原则）
- `审查` / `复审` / `运行` / `查看` 等同义词不在白名单 → fallback help
- 中文 `计划` 是单 token alias，**不会**与英文 `/gd plan --target …` 后面的 `--target` 相混（因为中文走规则 #3 后立即停止）

### 3.3 解析规则改动（commands/gd.md §"Stage parsing"）

新规则插入在原"双 token review"之前：

```
1. 取 $ARGUMENTS trimmed 后的 token 序列
2. 空 $ARGUMENTS → stage = help
3. 中文单 token 别名（NEW）：第一 token 严格等于白名单 → 立即映射 stage
4. 第一 token == review → 必须读第二 token (英文路径不变)
5. 第一 token ∈ {plan, execute, help} → stage = 第一 token
6. 第一 token ∉ 上述任意（含未列入的中文）→ help
```

英文路径行为完全不变。中文路径作为 stage parser 第一优先级 fallthrough，简洁可证。

---

## 4. 验收

### 4.1 5 个中文 token 在 source 中可 grep（验收要求 #1-5）

```bash
for tok in 帮助 计划 审计划 执行 审代码; do
  grep -c "/gd ${tok}" docs/gd-v7-claude-command.md
done
# 1 / 1 / 2 / 1 / 2 —— 全部 ≥1
```

`commands/gd.md` 中 5 token 各自命中 ≥3 次（包括解析规则、stage 表、help 输出表）。

### 4.2 未识别中文 token 走 help（验收要求 #6）

实现机制：`commands/gd.md` 解析规则 #3 是**严格白名单**（不是 prefix/regex 匹配），#6 兜底 fallback 到 help。`docs/gd-v7-claude-command.md` 显式记录 `/gd 审` → help 这条 negative case。

### 4.3 仍不得声称 Plan B/C/D/E 能力 active（验收要求 #7）

```bash
grep -niE "Plan 6 v3 active|Codex bridge.*active|claude_plus_codex.*active|gd review code.*active|gd review plan.*active" \
  commands/gd.md docs/gd-v7-claude-command.md
# → 0 hits ✓
```

`/gd review code` 仍标 `pending_future_plan`（commands/gd.md line 84）；`/gd review plan` 仍标 `local_only`。

### 4.4 边界检查

- `manifest.gd-v7.json` UNCHANGED ✓
- `prompts/gd-review-standard.md` UNCHANGED ✓（Plan B §8 反转范围）
- `scripts/gd-codex-review.py` UNCHANGED ✓（Plan B B6 deprecated 标记范围）
- `/Users/praise/.claude/commands/gd.md` NOT_PRESENT ✓（Plan D 解冻范围）
- 旧 `/review` / `/rev` 文件 UNCHANGED（未尝试修改）
- 裸 `^VERDICT:` regression check：0 命中 ✓

---

## 5. 执行完成合约

```text
EXEC_STATUS: completed
SEGMENT: 6.5-A
GD_STAGE: plan_6.5_a_segment（不是 /gd 命令输出）
MANIFEST_VERSION: 1.2.1（未变；A-D 不动 manifest）
ACTIVE_BOUNDARY: Plan 1-5 v5（未变；Plan 6 v3 仍 completed_with_constraint；Plan 6.5 各段尚未 promotion）
FILES_MODIFIED: 2（commands/gd.md / docs/gd-v7-claude-command.md）
FILES_ADDED: 3（start.marker / before-hashes / after-hashes / 本报告）
ACTIVE_FILES_TOUCHED: 0（manifest / installed copy / 旧 /review / 旧 /rev / hooks 全部未变）
NO_WRITE_AUDIT: ~/.claude/** attributable_count=0
DOWNSTREAM_GATE: 本段 review 通过 → 可开 Plan B
```

---

## 6. 下游 Plan 触发条件

| 下游 | 触发条件 |
|------|---------|
| Plan B（Codex bridge）| Plan A code review APPROVED；可与 Plan A 完全独立（B 不读 A 的 token alias）|
| Plan C（child agent）| Plan B code review APPROVED（C 用 B 定义的 self-review + bridge 角色）|
| Plan D（install 解冻）| A+B+C 全 APPROVED + 用户明确授权 |
| Plan E（端到端 smoke + manifest 1.4.0）| D 通过 + smoke 全过 |
