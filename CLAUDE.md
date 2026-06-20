# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> ⚠️ 文档版本：本 CLAUDE.md 反映 **v7 `/gd` 生产链路**（2026-06，gd.md lock_revision=23）。`README.md` 已更新到 v7 三档体系（仅残留少量 `/rev` 措辞，大体当前）；`PROJECT_GOAL.md` 仍停留在 v6 "lab-only `/rev`" 阶段（2026-05-09），**已过时**——架构与约束以本文件 + `commands/gd.md` + `docs/gd-changelog.md` 为准。

## 项目定位

Project GD（Goal-Driven Anti-Fill Lab）已从最初的 lab-only `/rev` 实验，演进为**生产级 `/gd` Claude-first Goal-Driven 多 Agent review 链路**，替代旧 `/review` 成为主链路。目标不变：用 Goal-Driven + Anti-Fill 长模板机制，减少"格式完整但计划不具体"的 AI 填表问题。

权威源：
- `commands/gd.md` — `/gd` 实现（Plan H lock_revision=23；rev1–rev22 见 changelog）
- `docs/gd-v7-project-goal.md` — v7 目标源（GOAL_SOURCE）
- `prompts/gd-review-standard.md` — review 标准唯一真源（GD_STANDARD，运行时经 `${CLAUDE_PLUGIN_ROOT}/prompts/`）
- `docs/gd-changelog.md` — 完整 revision 历史
- `.claude-plugin/{plugin.json,marketplace.json}` — 插件打包与分发清单（见下方「插件打包与安装者预设」段）
- `docs/constitution-plugin.md` + `specs/gd-plugin-packaging/` — 插件打包治理与决策

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

**四阶段强制子 agent 合同**（rev21 引入、rev22 延续）：每阶段必须发 1-2 个子 agent，0 child → fail-closed；`max_parallel=2` 为硬上限；大量 `closure_ineligible` 词汇（`human_exec`/`local_only`/`fixture_mode`/`mock_only`/`transport_failed`/`wrapper_schema_fail`/Claude-only/Codex-only 等）一旦出现在 final gate 路径即 `CLOSURE_INELIGIBLE` exit 1。rev22 把 `/gd execute` 的 agent_exec 落为 live（rev21 架构复用、**0 新建脚本**），`human_exec` 降为 emergency-only。

Shared Core（`docs/gd-v7-shared-core-index.md` 列全 15 artifact）：`GOAL_SOURCE` → master/step/task-packet/execution-result/plan-review/execution-review 模板 + `schema/*.json` → `gd-review-standard.md`。后续阶段只能消费、不得修改 review-standard 与 schema。

## 插件打包与安装者预设（2026-06 新增 — 最易被忽略）

Project GD 现以 **Claude Code 插件**形式分发（`.claude-plugin/plugin.json` + `marketplace.json`）：

- **布局与版本**：git-subdir 同仓——插件源就是本 repo，`name=project-gd`，**版本即 git SHA**（省略 `version` 字段，不用语义化版本号）。分发渠道为**私有 GitLab**（`git.xindong.com/game-ui/project-gd`）。
- **运行时锚点**（command 内引用共享资源必须用这两个变量，**不要硬编码项目路径**）：
  - `${CLAUDE_PLUGIN_ROOT}` — 插件只读区，指向 `commands/`、`prompts/`、`scripts/`。GD_STANDARD 即 `${CLAUDE_PLUGIN_ROOT}/prompts/gd-review-standard.md`。
  - `${CLAUDE_PLUGIN_DATA}` — 安装者可写区，插件 `update` **不清除**；`gd-setup-config.json` 落在此处。
- **`/gd-setup` 命令**（`commands/gd-setup.md` → `scripts/gd-plugin-setup.sh`）：交互式采集 **4 个安装者预设**，**全选项制**（禁止自由填路径/值，自由填会破坏传输协同与隔离）：

  | 字段 | 取值 |
  |------|------|
  | 审查产物输出位置 | `plugin_data`（默认）/ `target_project` / `cwd` |
  | codex key 类型 + 值 | `official` / `third_party`（类型决定 provider/base_url/env_key；key 值安装者自备，**绝不内置默认 key**） |
  | codex 模型 | `gpt-5.4` / `gpt-5.4-mini` / `gpt-5` 等 |
  | 模型强度 effort | `low` / `medium` / `high` / `xhigh` |

  - **`HANDOFF_ROOT` 不在预设内**（daemon↔client 必须一致，填错即断链，由插件统一管理，安装者不碰）。本命令只采集预设、**不触发任何链路**。
- **`/gd-*` 顶层快捷命令**（`commands/gd-{plan,review,review-plan,exec,执行}.md`）：`/gd <stage>` 的薄别名，各自委托 `gd.md` 对应段，**不复述规则**（gd.md 为唯一权威，本类文件只负责分发，避免漂移）。`gd-setup` 与三链路 `/review1` `/review2` `/gd` 并列分发。
- **决策溯源**：`docs/constitution-plugin.md` v1.1.0（**P1–P6 六原则**：一行安装装完即用 / 路径可移植零硬编码 / 分发完整性含 vendor / Runtime 写入隔离 / 外部依赖显式声明+缺失 fail-closed / 版本即 SHA）+ `specs/gd-plugin-packaging/spec.md`（治理文档，Draft）。

## codex 依赖链（运维关键 — 最易踩坑）

三档链路全部依赖外部 **codex CLI**（即 `codex exec` 二进制，**不是** Claude Code 的 codex 插件）。完整链路：

```
/review1 · /review2 · /gd
  → review-result-writer.sh / codex-consult.sh / gd-codex-bridge-review.py
  → ~/.claude/handoff/bin/codex-send-wait
  → codex-watch daemon (com.praise.codex-watch LaunchAgent)
  → codex exec   ← 外部 codex CLI 二进制
  → TAPSVC 代理 (config.toml: model_provider=tapsvc, model=codex/gpt-5.5, base_url=https://llm-proxy.tapsvc.com/v1, effort=xhigh)
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

测试分两层：**shell smoke**（端到端链路）+ **pytest 单元**（schema/validator/router/controller 模块）：

```bash
# pytest 单元（tests/test_*.py + tests/review-fusion/；conftest.py 预注册带连字符的 scripts 为可导入模块）
pytest                                                  # 全量
pytest tests/test_router_deep.py -q                     # 跑单个测试文件
pytest tests/test_deep_capsules.py::test_xxx -q          # 跑单个测试函数

# 链路 smoke（tests/ 下 17 个 gd-*-smoke.sh，覆盖 L1/L2/L3 各维度）
bash tests/gd-l1-combined-bundle-smoke.sh
bash tests/gd-review2-plan-routing-smoke.sh
bash tests/gd-l3-regression-v1-fixtures.sh              # 跑单个直接指定脚本

# 路由状态机 self-test（fixture 模式，不实跑 codex，快）
python3 scripts/gd-review-router.py --self-test

# preflight / parity / 闭环 gate（tools/）
python3 tools/gd-bridge-preflight.py
bash    tools/gd-root-parity-status.sh                  # source ↔ installed hash（commands/gd.md ↔ ~/.claude/commands/gd.md）
bash    tools/gd-parity-verify.sh                        # runtime bundle parity
bash    tools/gd-check-review-route-preflight.sh         # /review1 /review2 安装前 preflight
python3 tools/gd-validate-release-evidence.py
bash    tools/gd-codex-chain-release-status.sh          # L1/L2/L3 RELEASE_STATUS
bash    tools/gd-final-closure-status.sh
python3 tools/gd-owned-path-audit.py

# transport 部署 / codex-chain 镜像同步
bash vendor/l3-transport/scripts/install-transport.sh --dry-run  # 预览（默认）
bash vendor/l3-transport/scripts/install-transport.sh --yes      # 执行
bash bin/gd-sync-codex-chain.sh

# 安装者预设配置（不触发链路，仅采集并持久化到 ${CLAUDE_PLUGIN_DATA}）
bash scripts/gd-plugin-setup.sh --self-check            # 只读自检
```

lint：仓库用 ruff（`.ruff_cache` 存在）但无项目级配置文件，按全局 `ruff check scripts tools`。pytest 配置见 `pytest.ini`（`testpaths = tests`，`pythonpath = . + scripts`）；仓库**未定义 `integration` marker**，无需 `-m` 过滤。

## 硬约束（仍有效）

- **全中文输出**：用户可见结论必须中文。
- **VERDICT 命名**：用 `GD_REVIEW_DECISION` / `REV_VERDICT`，**绝不输出裸 `VERDICT:`**——会触发 `~/.claude/scripts/hooks/review-stop-marker.js` 的 regex 误判。取值 `APPROVED|REQUIRES_CHANGES|FAILED`。
- **绝对路径 / 运行时锚点**：command 内引用 shared core 从 `GD_PROJECT_ROOT` 拼接——而 `GD_PROJECT_ROOT` 在 `gd.md:15` 被绑定到 `${CLAUDE_PLUGIN_ROOT}`，**不是开发者机器的绝对路径**。绝不使用 `Project GD/...` 相对路径（插件在安装者任意 cwd 触发都要能定位）。
- **source ↔ installed hash 一致**：`commands/*.md` 与 `~/.claude/commands/*.md`（及插件安装路径）必须逐字节相同（`tools/gd-root-parity-status.sh` 验 `gd.md`，`tools/gd-parity-verify.sh` 验 runtime bundle）。安装到 live 仅在用户明确授权时发生。
- **敏感数据**：绝不入 git `.env*` / `*.key` / `*.pem` / 含 API key·token 的文件；codex-chain sync 自动 redact `default.rules` 中真实 key。
- **分支**：`main` 主分支，功能开发 `feat/<name>`；push 是独立决策。

## 已废弃的 v6 约束（PROJECT_GOAL 仍在写，勿照搬）

项目已生产化，下列 lab-only 约束**不再成立**：
- ~~"`~/.claude/**` 一律不写"~~ → 现主动部署 transport 到 `~/.claude/handoff` + 命令到 `~/.claude/commands`；有 `deploy-live` skill。
- ~~"不注册 slash command"~~ → `/gd`、`/review1`、`/review2` 已注册。
- ~~"不新增 daemon"~~ → `codex-watch` daemon 是链路核心。
- ~~"`bin/rev` 是入口"~~ → 已被 `/gd` slash command 取代；`bin/` 现仅存 `gd-sync-codex-chain.sh`。
