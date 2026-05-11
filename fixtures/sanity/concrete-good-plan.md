---
source_id: phase-c-memory-index-first.md
source_sha256: 54ef1ee3b3c1b3cff18774d7d454a7c822b1ec681e3c49bdb728649455796249
sanitized_by: claude
sanitization_checks:
  - no_secrets
  - no_tokens
  - no_keys
  - no_private_urls
  - no_emails
  - no_personal_paths
sanitization_notes: |
  "负责人：praise + Claude" → "负责人：<USER> + Claude"
  Reformatted SC list (checkbox format) to required table format for bin/rev plan parsing.
  SC smoke tests preserved with executable verify commands.
expected_class: concrete_good
expected_rev_outcome: APPROVED
expected_findings: []
---

# Plan: Phase C — MEMORY.md 索引化加载

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

日期：2026-05-08
状态：draft v1.1（review 补丁后）
负责人：<USER> + Claude

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果 SOD 每次全量 Read 33 个 priority 文件，上下文浪费约 26k tokens，且多数文件与当前任务无关。
PHASE_GOAL:   改 SOD 加载语义：默认只读 MEMORY.md + USER.md，其他 priority 文件按关键词命中再 Read。
TASK_GOAL:    修改 context-guard.md 和 memory-zones.md，添加可执行的命中规则，并通过 3 个 smoke test 验证。
```

---

## Review 对齐

REVIEW_DOMAIN：ai_infra

REVIEW_FOCUS：
- 加载语义改动后，Agent 能否真正按关键词命中需要的 memory（而不是凭印象跳过该读的）
- USER.md 默认必读这条不能被跳过——这是用户画像，丢失会导致沟通风格全错
- feedback 漏读的最坏情况评估：哪些 feedback 漏读会立刻翻车（比如"压缩后保持中文"漏读会输出英文）

Domain-specific notes：
- ai_infra：runtime active = SOD 流程；trigger surface = context-guard.md / memory-zones.md / SOD skill；state baseline = 当前规则文本快照；validation = 新会话 SOD 后看 transcript Read 调用清单；stale cleanup = 无（无文件移动）

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | `context-guard.md` 修改后明确：SOD 默认 Read 序列 = MEMORY.md + USER.md，其他按命中规则 Read | `grep -q 'MEMORY.md.*USER.md' ~/.claude/rules/context-guard.md && echo PASS` |
| SC-2 | `memory-zones.md` 同步更新加载语义描述 | `grep -q '命中规则' ~/.claude/rules/memory-zones.md && echo PASS` |
| SC-3 | 命中规则可执行：写在规则文件里，Agent 能按规则判定是否 Read 某文件（关键词匹配 + 优先级） | `grep -q '关键词来源' ~/.claude/rules/context-guard.md && echo PASS` |
| SC-4 | Smoke test 1：开新会话喊"做 AKB 翻译" → Read 列表 ⊇ {USER.md, project_akb_*}，不含无关 feedback | 新会话 transcript 中 SOD 后 Read 列表包含 USER.md + project_akb_*，不含 feedback_eod_*.md |
| SC-5 | Smoke test 2：开新会话喊"提交代码" → Read 列表 = {MEMORY.md, USER.md}（最小集） | 新会话 transcript 中 SOD 后 Read 列表 = {MEMORY.md, USER.md}，无其他文件 |
| SC-6 | Smoke test 3：开新会话喊"压缩一下上下文" → Read 列表 ⊇ {feedback_chinese_after_compaction.md} | 新会话 transcript 中 SOD 后 Read 包含 feedback_chinese_after_compaction.md |
| SC-7 | /context 在 SOD 后的 Messages 区 token 增量 < 8k（基线预估 ~26k 全量 Read） | SOD 完成后 `/context` 显示 Messages token 增量 < 8000 |
| SC-8 | 备份快照存在 `<workspace>/_backup/memory-index-first-2026-05-08/` | `test -d <workspace>/_backup/memory-index-first-2026-05-08 && ls` 显示 context-guard.md + memory-zones.md |

---

## 非目标（Non-Goals）

- 不动 memory 文件本身（位置、内容、三区分层）
- 不改 Claude Code 的 auto-load 机制（MEMORY.md 仍自动加载）
- 不改 Phase B 的 lazy rules（B 与 C 互不干扰）
- 不删除任何 priority 文件
- 不改 EOD 收割/归档逻辑

---

## Context

Phase A 把 32 条主 memory 迁到 iCloud 工作区项目后，新会话的 SOD 阶段会按 `context-guard.md` 当前规则"必读 priority/ 全部文件 (USER.md + feedback_* + project_*)" 把 33 个 priority 文件**全量 Read**进上下文。粗估：USER.md ~2k + 24 条 feedback 平均 ~700t = ~17k + 7 条 project decision ~7k = **总约 26k tokens 的额外消耗**会出现在每次 SOD 后的 messages 区。

但 33 条里多数与当前任务无关——比如做 AKB 翻译 bug 修复时，`feedback_research_default_ingest.md`、`feedback_eod_minimize_prompts.md` 完全无关，却被强制 Read。

本计划改 SOD 加载语义：
- **MEMORY.md 全量 Read**（6.1K，是索引）
- **priority/ 默认只 Read USER.md**（用户画像，永远相关）
- **其他 feedback_* / project_* 按当前任务关键词命中再 Read**

预期：每次 SOD 后 Read 量从 33 文件降到 1-5 文件，节省 ~15-20k tokens（视任务而定）。

## 当前状态

相关事实：
- 当前 priority/ 33 文件，总字节 ~50K（USER.md 2K + 24 feedback ~25K + 7 project decision ~23K）
- `context-guard.md` 现状：明文写"SOD 时**必读** `memory/priority/` 下所有文件"
- `memory-zones.md` 现状：明文写"必读 priority/：全部文件逐一 Read"
- MEMORY.md 已是带索引描述的结构化文件

现有入口：
- `~/.claude/rules/context-guard.md`：定义 SOD 必读规则
- `~/.claude/rules/memory-zones.md`：定义三区加载语义
- `~/.claude/skills/workday-sod/SKILL.md`：SOD 流程主体

约束：
- USER.md 必须保留默认 Read（用户画像太关键，不能漏）
- 命中规则必须 deterministic
- 改动后旧会话不受影响

## 实现步骤

### Step 1：准备 / 审计 `[SC-8]`

**操作**：
```bash
mkdir -p <workspace>/_backup/memory-index-first-2026-05-08
cp ~/.claude/rules/context-guard.md ~/.claude/rules/memory-zones.md <workspace>/_backup/memory-index-first-2026-05-08/
```

**验收**：`test -d <workspace>/_backup/memory-index-first-2026-05-08 && ls`

**Hard-stop**：cp 失败 → 停止，不继续

### Step 2：核心实现 `[SC-1, SC-2, SC-3]`

**操作**：
```bash
# Edit ~/.claude/rules/context-guard.md
# 替换 SOD 必读小节为"必读 MEMORY.md + USER.md，其他按命中规则 Read"
# 追加命中规则小节（关键词来源 + 命中算法 + 上限 5 个）
# Edit ~/.claude/rules/memory-zones.md 同步更新加载语义
```

**验收**：
```bash
grep -q 'MEMORY.md.*USER.md' ~/.claude/rules/context-guard.md && echo PASS
grep -q '命中规则' ~/.claude/rules/memory-zones.md && echo PASS
grep -q '关键词来源' ~/.claude/rules/context-guard.md && echo PASS
```

**Hard-stop**：grep 失败 → 修复后重试

### Step 3：集成 + iCloud 备份 `[SC-1, SC-2]`

**操作**：
```bash
# 检查 CLAUDE.md 是否引用旧措辞，若有则更新
cp ~/.claude/rules/context-guard.md <workspace>/rules/
cp ~/.claude/rules/memory-zones.md <workspace>/rules/
```

**验收**：`ls <workspace>/rules/{context-guard,memory-zones}.md`

### Step 4：Smoke test 验证 `[SC-4, SC-5, SC-6, SC-7]`

**操作**：在新会话中分别测试三个场景（AKB / commit / 压缩）

**验收**：见 SC-4/5/6 verify 命令

## 边界约束

**允许写入**：`Project GD/**`、`~/.claude/rules/`（仅 context-guard.md, memory-zones.md）

**绝对禁止写入**：memory 文件本身 / hook / EOD skill
