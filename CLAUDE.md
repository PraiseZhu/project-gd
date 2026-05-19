# Project GD — Goal-Driven Anti-Fill Lab

> 创建日期：2026-05-09
> 技术栈：Bash + Markdown + JSON Schema
> 项目目标权威源：[`PROJECT_GOAL.md`](./PROJECT_GOAL.md)

## 项目身份

lab-only 实验项目。建设 `/rev` 同步 review runner，验证 **Goal-Driven + Anti-Fill 长模板机制**能否减少"格式完整但计划不具体"的 AI 填表问题，作为现有 `/review` 链路的升级实验。

完整目标、13 条 SC、复用边界、4 个 Phase 拆分见 [`PROJECT_GOAL.md`](./PROJECT_GOAL.md)。

## 核心约束（MANDATORY）

1. **lab-only**：所有新增/修改文件只在 `Project GD/**` 下
2. **不动 live runtime**：`/Users/praise/.claude/**` 一律不写，包括 commands/templates/scripts/hooks/handoff/state/review-baselines
3. **不注册 slash command**：`/rev` 是 Bash 脚本入口（`bin/rev`），不创建 `~/.claude/commands/rev.md`
4. **不新增 daemon**：`bin/rev` 是同步 runner，不复用 `codex-watch`、不新增 `rev-watch`
5. **旧 `/review` 保留对比**：旧链路完全不动，仅用于 A/B 对照

## 技术栈

- **入口**：Bash (`bin/rev`)
- **模板/Prompt**：Markdown (`templates/`、`prompts/`)
- **数据 schema**：JSON Schema (`schema/rev-baseline.schema.json`)
- **依赖外部命令**：`codex exec --ephemeral`（直接调用 Codex CLI）
- **编码规范**：参考 `~/.claude/rules/common/coding-style.md`（无 generic 子集）

## 目录约定

```
Project GD/
├── CLAUDE.md           # 本文件 — 项目指引
├── PROJECT_GOAL.md     # 项目目标权威源（v6 总计划）
├── VERSIONING.md       # 版本管理规范
├── README.md           # 项目说明
├── .gitignore
├── bin/
│   └── rev             # /rev 同步 runner（Bash 入口）
├── templates/
│   ├── plan-template.md            # Goal-Driven plan 模板（SC-* + verify + 步骤映射）
│   └── execution-result-template.md # 1:1 SC mapping 执行结果模板
├── prompts/
│   └── rev-review-standard.md      # /rev review 标准唯一真源（CLI + 桌面端共用）
├── schema/
│   └── rev-baseline.schema.json    # 精简 baseline schema
├── scripts/
│   └── rev-result-writer.sh        # lab-local result writer
├── baselines/                      # rev baseline 持久化
├── fixtures/
│   ├── plans/                      # A/B 历史计划（脱敏后）
│   ├── expected/                   # 人工标注 expected verdict
│   └── old-review-prompt-readonly.md  # 只读提取的旧 review prompt 对照
├── reports/                        # 阶段报告 / A/B / parity / final-validation
├── docs/                           # 设计文档（按需）
├── mirrors/                        # 外部链路只读快照镜像（不动 live runtime）
│   └── codex-chain/                # L1 codex 二进制 + L2 ~/.codex 策略文件快照
└── history/                        # ECC 会话数据（不入 git）
    ├── checkpoints/
    └── daily/
```

## 协作工作流

### Plan / Review / Execute 循环

每个 Phase 独立走完整循环（PROJECT_GOAL.md "约束"段落定义）：

```
阶段计划（继承总计划 SC + 复用边界 + hard-stop）
  → Codex CLI review（用 prompts/rev-review-standard.md）
  → Claude 执行
  → bin/rev code <execution-result>（自审）
  → 进入下一 Phase
```

### Review 入口

| 用途 | 命令 | 标准源 |
|------|------|--------|
| 本项目 plan 自审 | `bin/rev plan <plan-file>` | `prompts/rev-review-standard.md` |
| 本项目执行结果自审 | `bin/rev code <result-file>` | `prompts/rev-review-standard.md` |
| A/B 对照（旧链路） | 只读提取 `~/.claude/handoff/bin/codex-watch` 的 `build_review_prompt()` heredoc 到 `fixtures/old-review-prompt-readonly.md`，不运行 live `/review` | （仅用于对照） |

### Codex 桌面端 parity 约定

桌面端出方案时，plan 模板顶部必须写：

```
REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md
```

桌面端按此引用的标准做自检，CLI runner 加载同一文件，两端 parity 靠**同一份文档源**保证。

## 输出契约

- 用户可见结论必须**全中文**
- VERDICT 字段用 `REV_VERDICT:`（不用裸 `VERDICT:`，避免触发 `~/.claude/scripts/hooks/review-stop-marker.js` 的 regex）
- `REV_VERDICT` 取值：`APPROVED | REQUIRES_CHANGES | FAILED`

## 敏感数据保护

绝不入 git：`.env*` / `*.key` / `*.pem` / `credentials/` / `*.token.json` / `.auth.json` / 任何含 API key/OAuth token/密码的文件 / PII。

`.gitignore` 已配置基础排除。新增敏感文件类型时同步更新。

## 测试与守卫

- A/B fixture 入库前必须脱敏（去人名、内部 URL、密钥痕迹）
- baseline / result 只写 `Project GD/**`
- 不调用 `~/.claude/scripts/review-result-writer.sh`
- 不运行 live `/review plan`
- 集成验证清单详见 [`PROJECT_GOAL.md` "测试计划"](./PROJECT_GOAL.md)

## 版本管理

详见 [`VERSIONING.md`](./VERSIONING.md)。

- 提交触发：手动喊"提交代码" → `commit-projects` skill
- 分支策略：`main` 主分支，功能开发 `feat/<name>`
- Push 策略：本地优先，push 到远端是独立决策

## 项目特定记录

### 2026-05-09 init
- new-project skill 创建，generic 模板
- v6 总计划归档为 `PROJECT_GOAL.md`
- 目录结构按 v6 计划重组（删除空 src/config/data/tests，新增 bin/templates/prompts/schema/scripts/baselines/fixtures/reports）

### 2026-05-19 codex-chain mirror 引入
- 新增 `mirrors/codex-chain/` 存放 L1/L2 codex 链路的只读快照（74 个文件，~888KB）
- 配 `bin/gd-sync-codex-chain.sh` 做白名单 rsync + secret 兜底扫描 + 内容哈希幂等检测
- 目的：让 Sentinel v1.6 之后绕过 L3 的 review 也能被 GD git 审计到 L1/L2 层变更
- 范围：不在 PROJECT_GOAL.md 的 4 个 Phase 内，仅作为 lab 辅助基础设施
- 注意：`default.rules` 含真实 API key，sync 后自动 redact 为 `<REDACTED>`
