---
source_id: purring-puzzling-willow.md
source_sha256: 54cb961b6d195b71e1d1f8c4d211d15168b23d658aefb10459db71e4d6b9603a
sanitized_by: claude
sanitization_checks:
  - no_secrets
  - no_tokens
  - no_keys
  - no_private_urls
  - no_emails
  - no_personal_paths
sanitization_notes: |
  No personal paths, tokens, keys, or emails found.
  Reformatted SC list (checkbox format) to required table format for bin/rev plan parsing.
  SC verify steps preserved as-is: "目视确认" (subjective, not executable) — this is the borderline characteristic.
expected_class: borderline
expected_rev_outcome: REQUIRES_CHANGES
expected_findings:
  - tag: sc_missing_executable_verify
    severity: P2
    match_terms: ["验证", "命令", "test -f", "executable", "可执行", "目视"]
---

# Plan: 根除英文输出 — 模板中文化 + 全局语言规则

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

日期：2026-04-28
状态：draft
负责人：Agent

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果模板全英文，Agent 每次 Execution Complete 输出英文，违反用户中文输出要求。
PHASE_GOAL:   将 execution-result-template.md 全中文化，并新增全局语言规则文件。
TASK_GOAL:    修改模板字段名和说明为中文，新增 output-language.md 规则，验证不与 memory 层冲突。
```

---

## Review 对齐

REVIEW_DOMAIN：docs_content

REVIEW_FOCUS：
- 模板中文化是否完整覆盖所有字段
- 全局语言规则是否会被正确加载

Domain-specific notes：
- docs_content：模板文件修改 + 新增全局规则文件；无 publish path、无 policy compliance

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | `execution-result-template.md` 所有字段名和说明改为中文 | 目视确认模板文件无遗漏英文说明文字 |
| SC-2 | 新增全局规则 `~/.claude/rules/output-language.md`，明确"面向用户输出一律中文" | 目视确认文件存在且内容正确 |
| SC-3 | memory 中已有的 `feedback_language_chinese.md` 与新规则不冲突、不重复 | 目视对比两个文件，确认无重复 |

---

## 非目标（Non-Goals）

- 不改 plan 模板（已是中文）
- 不改代码中的英文变量名/注释/命令
- 不翻译规则文件本身（规则是给 Agent 读的内部文档，不是面向用户的输出）

---

## 当前状态

相关事实：
- `~/.claude/templates/execution-result-template.md` 全英文 — 这是 Agent 输出 Execution Complete 时的唯一模板
- `~/.claude/templates/plan-template.md` 已是中文
- `~/.claude/rules/` 下无任何输出语言规则
- `memory/priority/feedback_language_chinese.md` 已创建但仅是 memory 层
- 全局 CLAUDE.md 中的执行完成合约引用了模板但未指定语言

现有入口：
- 模板：`~/.claude/templates/execution-result-template.md`
- 规则目录：`~/.claude/rules/`

约束：
- 模板中 REVIEW_DOMAIN / REVIEW_FOCUS 等枚举值保持英文（机器可读 key）
- status 枚举值（pass/fail/not_run/n_a）保持英文

## 实现步骤

### Step 1：创建 output-language.md `[SC-2]`

**操作**：
```bash
cat > ~/.claude/rules/output-language.md << 'EOF'
# 输出语言规则
所有面向用户的文字输出必须使用中文。
例外：代码、变量名、枚举 key（pass/fail/APPROVED 等）。
EOF
```

**验收**：目视确认文件内容正确

### Step 2：中文化模板 `[SC-1]`

**操作**：修改 `~/.claude/templates/execution-result-template.md`
- 章节标题中文化：Success Criteria → 验收状态，Change Summary → 变更摘要，等
- 表头中文化：Criteria → 验收项，Status → 状态，Evidence → 证据，等

**验收**：目视确认无遗漏英文说明文字

### Step 3：验证不冲突 `[SC-3]`

**操作**：读取两个文件对比

**验收**：目视对比 output-language.md 与 feedback_language_chinese.md，确认无重复

## 边界约束

**允许写入**：`~/.claude/rules/output-language.md`（新增）、`~/.claude/templates/execution-result-template.md`（修改）

**绝对禁止写入**：plan 模板、代码文件、其他规则文件
