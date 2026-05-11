---
source_id: magical-humming-fern.md
source_sha256: 6513feeb7dc79ffbd57ae76c64dfaed2edf617ee5f018cedd8ac1a83a98dc068
sanitized_by: claude
sanitization_checks:
  - no_secrets
  - no_tokens
  - no_keys
  - no_private_urls
  - no_emails
  - no_personal_paths
sanitization_notes: |
  "Praise Space/AKB/research/cognee AI Agent..." → "<VAULT_PATH>/research/cognee-report.md"
  "Praise Space/Toolbox/Agent_Framework.md" → "<VAULT_PATH>/Toolbox/Agent_Framework.md"
  Added required Goal-Driven wrapper (目标链 + 成功标准 table) to enable bin/rev plan parsing.
  Original plan had no Review 对齐 section; SC verify steps were bare bullets (now table with generic verify).
expected_class: generic_bad
expected_rev_outcome: REQUIRES_CHANGES
expected_findings:
  - tag: missing_review_alignment
    severity: P1
    match_terms: ["Review 对齐", "REVIEW_DOMAIN", "REVIEW_FOCUS"]
  - tag: generic_sc_verify
    severity: P2
    match_terms: ["验证", "可执行", "verify", "通过", "完成", "目视"]
---

# 评估计划: topoteretes/cognee — AI Agent 长期记忆引擎

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

> 作者：Claude
> 日期：2026-04-16
> 状态：draft

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: 在不破坏现有 /review 链路的前提下，用 Project GD/ 建设 lab-only /rev 同步 review runner，验证 Goal-Driven + Anti-Fill 长模板机制是否能减少"格式完整但计划不具体"的 AI 填表问题。
CHAIN_GOAL:   如果没有外部框架评估，团队可能错过有价值的工具或重复建设已有能力。
PHASE_GOAL:   完成 cognee 深度评估并入库 AKB，为 Agent 长期记忆选型提供依据。
TASK_GOAL:    执行 cognee 评估流程：研究 → 报告生成 → Obsidian 归档 → AKB 入库。
```

---

## 成功标准（Success Criteria）

| ID | 成功标准 | Verify（验收命令/路径/输出断言） |
|----|----------|---------------------------------|
| SC-1 | NotebookLM 报告生成成功 | 确认通过 |
| SC-2 | Obsidian 归档且排版美化通过 | 目视确认文件存在 |
| SC-3 | AKB DB 索引验证通过 | 运行验证脚本，确认成功 |
| SC-4 | _index.md 更新完成 | 确认更新 |

---

## Context

用户在小红书看到 cognee 项目推荐（15.5k Stars），要求深度评估。cognee 是一个开源知识引擎，为 AI Agent 提供持久化记忆（知识图谱 + 向量搜索），支持 remember/recall/forget/improve 四操作。

## 执行流程（Deep Research Skill）

1. **创建 NotebookLM Notebook** — `[Research] cognee AI Agent 长期记忆引擎 - 2026-04-16`
2. **添加源材料** — GitHub URL `https://github.com/topoteretes/cognee`
3. **启动 Deep Research** — `--mode deep --source web`，中文 query 聚焦评估维度
4. **轮询等待** — `--poll-interval 30 --max-wait 600`
5. **导入结果 + 生成报告** — `nlm research import` → `notebooklm generate report --format briefing-doc --language zh_Hans`
6. **下载报告** — 保存到本地
7. **归档到 Obsidian** — `<VAULT_PATH>/research/cognee-report.md`
8. **排版美化** — vault排版美化 skill
9. **AKB 索引** — `scripts.main research` 入库
10. **概念提取** — `backfill-concepts`
11. **更新 _index.md** — 重建导航索引
12. **输出报告** — 聊天中展示完整评估

## 评估维度（研究 query）

- 架构设计与技术实现
- 与同类方案对比（Mem0、LangMem、Zep）
- 生产就绪度与社区活跃度
- 安全性与数据隐私
- 适用场景与局限性
- 与我们 ECC 记忆系统的互补性

## 关键文件

- 报告输出: `<VAULT_PATH>/research/cognee-report.md`
- AKB DB: `Project AKB/`
- Toolbox 分类: `<VAULT_PATH>/Toolbox/Agent_Framework.md`（入库时追加工具卡）

## 边界约束

**允许写入**：`Project GD/**`

**绝对禁止写入**：`/Users/<REDACTED>/.claude/**`
