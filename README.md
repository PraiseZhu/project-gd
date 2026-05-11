# Project GD — Goal-Driven Anti-Fill Lab

> 状态：Phase 1 完成 | 技术栈：Bash + Markdown + JSON Schema
> 项目目标：[`PROJECT_GOAL.md`](./PROJECT_GOAL.md) | 项目指引：[`CLAUDE.md`](./CLAUDE.md)

## 项目目的

实验验证：**Goal-Driven + Anti-Fill 长模板机制**能否减少"格式完整但计划不具体"的 AI 填表问题。

现有 `/review` 链路的真实缺口：
1. **作者层**：计划模板没有强制 SC-* 编号化 verify，AI 填出"优化/完善"等泛化步骤
2. **追溯层**：baseline 无 goal chain，`/review code` 时审查者看不到原计划要什么
3. **审查层**：`codex-watch build_review_prompt()` 硬编码 prompt，无 anti-generic 判定规则

本项目在 `Project GD/` 内建设 lab-only `/rev` 同步 runner，旧 `/review` 完全保留做 A/B 对比。

## 快速上手

```bash
# Phase 2 完成后可用
bin/rev plan <plan-file>    # 对计划做 Goal-Driven review
bin/rev code <result-file>  # 对执行结果做 SC-* 完整性 review
```

review 结果以 `REV_VERDICT: APPROVED | REQUIRES_CHANGES | FAILED` 输出。

## 目录结构

```
Project GD/
├── PROJECT_GOAL.md         # v6 总计划权威源（不覆盖）
├── CLAUDE.md               # 项目指引（lab-only 约束）
├── manifest.json           # Phase 输出清单 + 约束摘要
├── bin/
│   └── rev                 # /rev 同步 runner（Phase 2 实现）
├── templates/
│   └── plan-template.md    # Goal-Driven 计划模板（Phase 1 产出）
├── prompts/
│   └── rev-review-standard.md  # review 标准唯一真源（Phase 1 产出）
├── schema/
│   └── rev-baseline.schema.json  # 精简 baseline（Phase 2 产出）
├── scripts/
│   └── rev-result-writer.sh     # lab-local result writer（Phase 2 产出）
├── baselines/              # rev baseline 持久化
├── fixtures/
│   ├── plans/              # A/B 历史计划（Phase 4 填充）
│   ├── expected/           # 人工标注 expected verdict（Phase 4 填充）
│   └── old-review-prompt-readonly.md  # 旧 review prompt 只读对照（Phase 4）
├── results/                # bin/rev 输出结果
├── reports/                # 阶段报告 / A/B / parity / final-validation
└── history/                # ECC 会话数据（不入 git）
    ├── checkpoints/
    └── daily/
```

## 核心约束

| 约束 | 内容 |
|------|------|
| lab-only | 所有写入限制在 `Project GD/**` 内 |
| 不动 live runtime | `/Users/praise/.claude/**` 一律不写 |
| 不注册 slash command | `/rev` 是 Bash 入口，不创建 `commands/rev.md` |
| 不新增 daemon | `bin/rev` 同步 runner，不新增 `rev-watch` |
| REV_VERDICT | 用 `REV_VERDICT:` 代替裸 `VERDICT:`（避免触发 live hook） |
| 全中文输出 | 所有面向用户的结论必须中文 |

## 阶段进度

| 阶段 | 名称 | 状态 | 核心产出 |
|------|------|------|---------|
| Phase 1 | 模板与 setup 收口 | ✅ 完成 | `plan-template.md` / `rev-review-standard.md` |
| Phase 2 | 同步 runner + 精简 baseline | ⏳ 待执行 | `bin/rev` / `schema/rev-baseline.schema.json` |
| Phase 3 | execution result 1:1 conformance | ⏳ 待执行 | `templates/execution-result-template.md` |
| Phase 4 | A/B + parity 最终验收 | ⏳ 待执行 | `reports/ab-comparison.md` / `reports/final-validation.md` |

## review 标准引用

所有计划和执行结果 review 均使用同一份标准：

```
REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md
```

CLI runner 与 Codex 桌面端通过引用同一文件保证 parity。
