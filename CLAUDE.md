# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> ⚠️ 文档版本：本 CLAUDE.md 反映 **v7 `/gd` 生产链路**（2026-06）。同目录 `README.md` 与 `PROJECT_GOAL.md` 仍停留在 v6 "lab-only `/rev`" 阶段（2026-05-09），**已过时**——架构与约束以本文件 + `commands/gd.md` + `docs/gd-changelog.md` 为准。

## 项目定位

Project GD（Goal-Driven Anti-Fill Lab）已从最初的 lab-only `/rev` 实验，演进为**生产级 `/gd` Claude-first Goal-Driven 多 Agent review 链路**，替代旧 `/review` 成为主链路。目标不变：用 Goal-Driven + Anti-Fill 长模板机制，减少"格式完整但计划不具体"的 AI 填表问题。

权威源：
- `commands/gd.md` — `/gd` 实现（Plan H lock_revision=21）
- `docs/gd-v7-project-goal.md` — v7 目标源（GOAL_SOURCE）
- `prompts/gd-review-standard.md` — review 标准唯一真源（GD_STANDARD）
- `docs/gd-changelog.md` — 完整 revision 历史

## 三档 Review 体系（核心架构）

三个层级的 review 入口，全部最终经 codex 执行：

| 档 | 命令 | 角色 | 完成标记 |
|----|------|------|---------|
| L1 | `/review1` | 交叉讨论/第二意见(默认) + `--review` 轻量审核 | `RECOMMENDATION:` / `VERDICT:` |
| L2 | `/review2` | profile-aware Codex 工作台 | `VERDICT:` |
| L3 | `/gd` | 正式全链多 agent(plan→review→execute→review code) | `GD_REVIEW_DECISION` |

`/gd` 四阶段（中英文别名为**严格白名单**，未识别 token 一律 fallback help、不写任何文件）：

| 中文 | 英文 | stage 职责 |
|------|------|-----------|
| `/gd 计划` | `/gd plan` | 多 agent planning dispatch（capability probe + manual_packet fallback） |
| `/gd 审计划` | `/gd review plan` | Claude self-review + Codex cross-review + merge + auto-fix loop |
| `/gd 执行` | `/gd execute` | execution dispatch + ledger + path audit |
| `/gd 审代码` | `/gd review code` | unified router，5 种 review target 类型 |

**revision=21 四阶段强制子 agent 合同**：每阶段必须发 1-2 个子 agent，0 child → fail-closed；`max_parallel=2` 为硬上限；大量 `closure_ineligible` 词汇（`human_exec`/`local_only`/`fixture_mode`/`mock_only`/`transport_failed`/`wrapper_schema_fail`/Claude-only/Codex-only 等）一旦出现在 final gate 路径即 `CLOSURE_INELIGIBLE` exit 1。

Shared Core（`docs/gd-v7-shared-core-index.md` 列全 15 artifact）：`GOAL_SOURCE` → master/step/task-packet/execution-result/plan-review/execution-review 模板 + `schema/*.json` → `gd-review-standard.md`。后续阶段只能消费、不得修改 review-standard 与 schema。

## codex 依赖链（运维关键 — 最易踩坑）

三档链路全部依赖外部 **codex CLI**（即 `codex exec` 二进制，**不是** Claude Code 的 codex 插件）。完整链路：

```
/review1 · /review2 · /gd
  → review-result-writer.sh / codex-consult.sh / gd-codex-bridge-review.py
  → ~/.claude/handoff/bin/codex-send-wait
  → codex-watch daemon (com.praise.codex-watch LaunchAgent)
  → codex exec   ← 外部 codex CLI 二进制
  → TAPSVC 代理 (config.toml: model_provider=tapsvc, model=gpt-5.5, effort=xhigh)
```

链路通畅需同时满足（任一缺失整链断；排障按此顺序查）：

1. **codex CLI 在 PATH**：`command -v codex`。装法 `npm i -g @openai/codex --prefix ~/.local`（用户级，避开 `/usr/local` 的 root 权限）。
2. **transport 部署到 live**：`~/.claude/handoff/bin/{codex-send-wait,codex-watch,...}`。用 `vendor/l3-transport/scripts/install-transport.sh --yes` 从 vendor 部署（含 LaunchAgent + SHA 校验 + 幂等 + 备份）。
3. **daemon 在线**：`launchctl list | grep com.praise.codex-watch`。
4. **daemon 持有 TAPSVC key**：config.toml 配 `env_key="TAPTAP_API_KEY"`，codex **强制读该环境变量**（不回退 auth.json）。daemon 由 launchd 启动、**不读 shell profile**，故须 `launchctl setenv TAPTAP_API_KEY <sk-key>`（会话级，**重启失效**）或写进 plist 的 `EnvironmentVariables`。手动 `codex exec` 能成功而 daemon 失败，通常就是这条。
5. **bash 版本**：codex-watch 经 `/bin/bash`（macOS 3.2）运行，**禁用 bash 4+ 特性**（`${var^^}`/`${var,,}`/`declare -A`），用 `printf | tr` 替代——否则 `bad substitution` 导致 daemon 卡 `running`、客户端 540s 超时。

## vendor ↔ live 方向（改 transport 前必看）

`vendor/l3-transport/` 是 transport **权威源**：
- `handoff/bin/*` + `handoff/lib/*` + `launchagents/*.plist` → `install-transport.sh` 部署到 `~/.claude/handoff` 与 `~/Library/LaunchAgents`（live）。
- `scripts/{codex-consult.sh,review-result-writer.sh}` → **直接从 vendor 运行**，不部署（避免双拷贝漂移），但内部仍硬编码 `~/.claude/handoff` 引用（待解耦，见 vendor README）。

改 daemon 行为的正确做法：**改 vendor 源 → 重新 `install-transport.sh`**，并保持 vendor 与 live 文件 hash 一致（install-transport 幂等依赖此）。

`mirrors/codex-chain/` 是 codex L1/L2 链路的**只读审计快照**（含版本锁 `l1-binary/codex-package.json`），由 `bin/gd-sync-codex-chain.sh` 白名单 rsync + secret redact 维护，让绕过 L3 的 review 也能被 git 审计到 codex 侧变更。

## 命令

测试是 shell smoke 脚本（无 pytest / conftest）：

```bash
# 链路 smoke（tests/ 下 8 个 gd-*-smoke.sh，覆盖 L1/L2/L3 各维度）
bash tests/gd-l1-combined-bundle-smoke.sh
bash tests/gd-review2-plan-routing-smoke.sh
bash tests/gd-l3-regression-v1-fixtures.sh        # 跑单个直接指定脚本

# 路由状态机 self-test（fixture 模式，不实跑 codex，快）
python3 scripts/gd-review-router.py --self-test

# preflight / parity / 闭环 gate（tools/）
python3 tools/gd-bridge-preflight.py
bash    tools/check-gd-command-parity.sh           # source ↔ installed hash 一致
bash    tools/gd-parity-verify.sh
bash    tools/gd-codex-chain-release-status.sh      # L1/L2/L3 RELEASE_STATUS
bash    tools/gd-final-closure-status.sh
python3 tools/gd-owned-path-audit.py

# transport 部署 / codex-chain 镜像同步
bash vendor/l3-transport/scripts/install-transport.sh --dry-run  # 预览（默认）
bash vendor/l3-transport/scripts/install-transport.sh --yes      # 执行
bash bin/gd-sync-codex-chain.sh
```

lint：仓库用 ruff（`.ruff_cache` 存在）但无项目级配置文件，按全局 `ruff check scripts tools`。

## 硬约束（仍有效）

- **全中文输出**：用户可见结论必须中文。
- **VERDICT 命名**：用 `GD_REVIEW_DECISION` / `REV_VERDICT`，**绝不输出裸 `VERDICT:`**——会触发 `~/.claude/scripts/hooks/review-stop-marker.js` 的 regex 误判。取值 `APPROVED|REQUIRES_CHANGES|FAILED`。
- **绝对路径**：command 内引用 shared core 从 `GD_PROJECT_ROOT`（`/Users/praise/AI-Agent/Claude/projects/Project GD`）拼接，**不用 `Project GD/...` 相对路径**（installed command 在任意 cwd 触发要能定位）。
- **source ↔ installed hash 一致**：`commands/*.md` 与 `~/.claude/commands/*.md` 必须逐字节相同（`tools/check-gd-command-parity.sh` 验证）。安装到 live 仅在用户明确授权时发生。
- **敏感数据**：绝不入 git `.env*` / `*.key` / `*.pem` / 含 API key·token 的文件；codex-chain sync 自动 redact `default.rules` 中真实 key。
- **分支**：`main` 主分支，功能开发 `feat/<name>`；push 是独立决策。

## 已废弃的 v6 约束（README/PROJECT_GOAL 仍在写，勿照搬）

项目已生产化，下列 lab-only 约束**不再成立**：
- ~~"`~/.claude/**` 一律不写"~~ → 现主动部署 transport 到 `~/.claude/handoff` + 命令到 `~/.claude/commands`；有 `deploy-live` skill。
- ~~"不注册 slash command"~~ → `/gd`、`/review1`、`/review2` 已注册。
- ~~"不新增 daemon"~~ → `codex-watch` daemon 是链路核心。
- ~~"`bin/rev` 是入口"~~ → 已被 `/gd` slash command 取代；`bin/` 现仅存 `gd-sync-codex-chain.sh`。
