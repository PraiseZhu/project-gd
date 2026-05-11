# Phase 4A — Sanity Fixture 候选 Census

> SC-5 验收：≥6 个真实历史候选，全部 source_path outside Project GD，覆盖 generic_bad / concrete_good / borderline

扫描范围：`~/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/plans/`（workspace 根目录 plans/，非 Project GD）

realpath 校验结果：全部 PASS（见下方各条目）

---

## 候选列表（共 6 个）

### C-1 — magical-humming-fern.md

```
source_path: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/plans/magical-humming-fern.md
candidate_type: generic_bad
```

**摘要**：cognee 项目深度评估计划（42 行）。

**推荐理由**：
- 无 `## Review 对齐` 节
- 无编号 SC 结构（仅有"执行流程"步骤列表）
- `## 验证` 仅 4 条裸 bullet（"成功""通过""验证通过"）无可执行命令
- 步骤以工具调用为主，缺失"验证方式"字段

**敏感信息风险**：无（已 grep 扫描，0 命中）

**推荐入选**：✅ 是（generic_bad 代表性强，短小、内容清晰、脱敏需求低）

---

### C-2 — moonlit-nibbling-tulip.md

```
source_path: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/plans/moonlit-nibbling-tulip.md
candidate_type: generic_bad
```

**摘要**：SOD/EOD history 路径修正方案（129 行）。

**推荐理由**：
- 无 `## Review 对齐` 节
- `## 改动清单` 结构完整，但以"替换什么"描述改动，无 SC 编号
- 验证是隐式的（改完即视为成功）
- "用户决策"节存在但没有验收标准

**敏感信息风险**：无

**推荐入选**：备选（可替代 C-1 作 generic_bad，但比 C-1 更像"设计决策"而不是"计划"）

---

### C-3 — phase-c-memory-index-first.md

```
source_path: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/plans/phase-c-memory-index-first.md
candidate_type: concrete_good
```

**摘要**：Memory SOD 索引化加载改动计划（含完整 Goal-Driven 结构）。

**推荐理由**：
- 有 `## Review 对齐`（REVIEW_DOMAIN + REVIEW_FOCUS + Domain-specific notes）
- 有"用户目标"、"成功标准"（SC 编号化 `- [ ]`）、"非目标"三段
- SC 含 3 个 Smoke Test，每个测试有具体触发词和预期行为（可执行）
- 当前状态、现有入口、约束清楚
- `/context` token 增量指标量化（`< 8k`）

**敏感信息风险**：无

**推荐入选**：✅ 是（concrete_good 最佳代表，完整 Goal-Driven 格式）

---

### C-4 — p1c-local-llm-contract-refresh-v6.md

```
source_path: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/plans/p1c-local-llm-contract-refresh-v6.md
candidate_type: concrete_good
```

**摘要**：AKB2.0 cc-local-llm 后端契约修正 v6（详细技术 plan，含 v5→v6 修正表）。

**推荐理由**：
- 有 `## Review 对齐`（含两个 sub-domain Review 1/2）
- v5→v6 修正表（10 条，每条标严重度）
- 有 C-4 smoke test fixtures（5 类完整 input.json）
- Review writeback 失败路径、verdict 三档 anchor 均有明确说明

**敏感信息风险**：无

**推荐入选**：备选（可替代 C-3 作 concrete_good，但比 C-3 更复杂，脱敏工作量稍大）

---

### C-5 — purring-puzzling-willow.md

```
source_path: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/plans/purring-puzzling-willow.md
candidate_type: borderline
```

**摘要**：英文输出根除计划 — 模板中文化 + 全局语言规则（131 行）。

**推荐理由**：
- 有 `## Review 对齐`（REVIEW_DOMAIN + REVIEW_FOCUS）✓
- 有"用户目标"、"成功标准"（3 条 `- [ ]`）、"非目标"三段 ✓
- **边界点**：SC-1（"模板中文化是否完整覆盖所有字段"）无可执行 verify 命令，判断依赖 reviewer 主观视察
- SC-2（"新增全局规则"）— 可用 `test -f` 验证，但未写命令
- SC-3（"不冲突、不重复"）— 纯文本分析，无机器验证手段
- 整体格式完整但 verify 层弱

**敏感信息风险**：无

**推荐入选**：✅ 是（borderline 最佳代表；格式正确但 verify 可执行性存疑，reviewer 判断会有分歧）

---

### C-6 — dreamy-finding-dijkstra.md

```
source_path: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/plans/dreamy-finding-dijkstra.md
candidate_type: borderline
```

**摘要**：new-project skill 触发器 + 版本管理规范 + 现有项目同步（含交付物列表）。

**推荐理由**：
- 有"预期结果"描述，有交付物表格
- 无独立 `## Review 对齐` 节
- 无编号 SC 结构（交付物表取代了验收标准）
- "关键设计决策"节记录了 Q&A，有一定 verify 意图但缺乏格式化
- 比 generic_bad 更"有结构"，但比 concrete_good 少 SC 编号

**敏感信息风险**：无

**推荐入选**：备选（可替代 C-5 作 borderline，但内容覆盖修改 live 文件，脱敏范围较宽）

---

## 推荐 3 个入选

| 序号 | 文件 | 类型 | 推荐理由摘要 | expected_rev_outcome |
|------|------|------|--------------|----------------------|
| R-1 | `magical-humming-fern.md` | generic_bad | 最短、格式最明显不足（无 Review 对齐、无 SC 编号、验证仅 bullet） | REQUIRES_CHANGES |
| R-2 | `phase-c-memory-index-first.md` | concrete_good | 完整 Goal-Driven 格式（Review 对齐 + SC + Smoke Test + 量化指标） | APPROVED |
| R-3 | `purring-puzzling-willow.md` | borderline | 格式完整但 verify 层弱，reviewer 会在 APPROVED / REQUIRES_CHANGES 之间存在判断空间 | 待用户确认 |

---

## outside-GD realpath 校验结果

| 文件 | realpath | outside Project GD? |
|------|----------|---------------------|
| magical-humming-fern.md | `.../Claude Code/plans/magical-humming-fern.md` | PASS |
| moonlit-nibbling-tulip.md | `.../Claude Code/plans/moonlit-nibbling-tulip.md` | PASS |
| phase-c-memory-index-first.md | `.../Claude Code/plans/phase-c-memory-index-first.md` | PASS |
| p1c-local-llm-contract-refresh-v6.md | `.../Claude Code/plans/p1c-local-llm-contract-refresh-v6.md` | PASS |
| purring-puzzling-willow.md | `.../Claude Code/plans/purring-puzzling-willow.md` | PASS |
| dreamy-finding-dijkstra.md | `.../Claude Code/plans/dreamy-finding-dijkstra.md` | PASS |

全部 6 个 PASS。
