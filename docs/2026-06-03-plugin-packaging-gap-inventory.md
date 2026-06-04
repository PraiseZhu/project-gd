# GD 插件封装 — L1/L2/L3 缺口盘点清单

> 日期：2026-06-03
> 目的：把 GD 项目封装成 Claude 插件前，盘点"围绕 L1-L3 链路展开"的权威机制与文件中，**当前不在 `Project GD/` 目录内**的内容，并给出每项处理方式。
> 性质：调查盘点（只读得出），非执行方案。落盘供封装决策复查。
> 方法：基于本会话对 `~/.claude/`、`~/.codex/`、`~/Library/LaunchAgents/`、`Project GD/` 的实地扫描，非推测。
> **验证修正（2026-06-03）**：经动态试跑 L1/L2/L3（`codex` 实跑 + `gd-review-router.py --self-test` + `gd-bridge-preflight.py` + 主链路 56 文件全路径扫描）回填修正，逐项以 🔬 标注。

---

## 0. 三链路语义（权威定义来源）

来源：`config/gd-runtime-parity-manifest.json` + `mirrors/README.md` + `docs/review-route-necessity-memo.md`

| 层 | 含义 | 运行时根 |
|----|------|---------|
| **L1** | Codex 执行引擎（二进制） | `~/.codex/packages/standalone/releases/0.136.0-aarch64-apple-darwin/bin/codex`（经 `~/.local/bin/codex` 软链） |
| **L2** | Codex 全局策略/配置 | `~/.codex/` |
| **L3** | Review 编排 + 传输层 | `/gd review`（唯一 formal authority）+ `/review2`（workbench）+ bridge + codex-watch 传输 |

### ⚠️ 关键前提：L3 是两套链路，封装时不可混为一谈

| 链路 | 组成 | 与 GD 关系 | 封装处置 |
|------|------|-----------|---------|
| **GD L3**（要封装的本体） | `/gd review` + `/review2` + `gd-codex-bridge-review.py` | 大部分已在 GD | 收齐 |
| **旧 /review L3**（对照物） | `~/.claude/commands/review.md` + 8 review-chain hooks | GD 刻意规避（用 `REV_VERDICT` 躲 hook regex），仅 A/B 只读对照 | **主动排除** |

两套**共享** codex-watch daemon 传输层。

> 🔬 **验证修正**：原表把 `review-result-writer.sh` 归入"旧 /review 应排除"，**实测错误**——见 §3 A 组，它是 GD bridge 的运行时默认依赖，不可排除。已从本行移除。

---

## 1. L1 — 未包含内容（处置：声明依赖，禁止 vendoring）

| 项 | 实际位置 | 处置 | 不处理的后果 |
|----|---------|------|------------|
| codex standalone 二进制 + 内置 `rg` | `~/.codex/packages/standalone/releases/0.136.0-aarch64-apple-darwin/bin/` | plugin.json/README 声明 `codex >= 0.136` 前置依赖 | bridge 调 codex 直接 command-not-found |
| 🔬 **L1 审计镜像形态错位（比"失效"更严重）** | mirror 的 `must_include` 是 `codex.js`（npm 形态），但实跑 `codex --version`=0.136.0，`file` 确认实际是 **Mach-O arm64 原生二进制**（`~/.codex/packages/standalone/releases/0.136.0-aarch64-apple-darwin/bin/codex`）。`runtime_base` 指向的 `~/.npm-global/lib/node_modules/@openai/codex` 实测已空。npm 形态的 `codex.js` 在原生二进制形态下**根本不存在** | 重写 mirror 以 standalone 二进制形态为准（或放弃 L1 二进制镜像，仅锁版本号） | "git 审计 L1 变更"目标完全落空：审计的是已不存在的 npm 文件形态 |

**禁止**：打包二进制 —— 平台锁定（aarch64 vs x86）、许可、自更新问题。参照 OpenAI Codex 官方插件（1.6M，不含二进制，只声明 "Use Codex"）。

---

## 2. L2 — 未包含内容（处置：不可打包，只镜像审计）

| 项 | 实际位置 | 处置 | 不处理的后果 |
|----|---------|------|------------|
| `~/.codex/` 全部（config.toml / AGENTS.md / rules / memories / automations / skills 1473 / plugins / computer-use） | `~/.codex/` | 仅保留 `mirrors/codex-chain/l2-*` 审计镜像；可选提供 config 模板 | — |
| `rules/default.rules` **含真实 API key** | `~/.codex/rules/` | 绝不打包（sync 时已 redact 为 `<REDACTED>`） | 打包即泄密 |
| 🔬 **L2 审计镜像漂移** | 实测 `~/.codex/AGENTS.md` = 7496 字节，但 `gd-runtime-parity-manifest.json` 仍记 `"AGENTS.md ... 0 bytes, empty"` | 重跑 `bin/gd-sync-codex-chain.sh --apply` 刷新镜像与 manifest | 审计镜像与运行时不一致，"git 审计 L2"对 AGENTS.md 失真 |

**禁止**：打包真实用户配置 —— 含密钥、每用户不同、属私有运行时数据。

---

## 3. L3 — 未包含内容（分两组）

### A 组：GD L3 真依赖，当前不在 GD —— 需收拢或决策 ⚠️

| 项 | 位置 | 处置 | 不处理的后果 |
|----|------|------|------------|
| codex-watch daemon 6 件套：`codex-send` / `codex-send-wait` / `codex-watch` / `codex-watch-healthcheck` / `watcher-alive` / `codex-status` | `~/.claude/handoff/bin/` | **灰区决策**：收进插件 `scripts/` 改硬编码 vs 声明前置依赖 | `gd-codex-bridge-review.py:73` 硬编码找不到 `codex-send-wait`，`/gd review` 传输层死 |
| handoff 共享库：`state-paths.sh` / `watch-state.sh` | `~/.claude/handoff/lib/` | 随 daemon 一起 | send-wait `source` 失败 |
| **daemon 常驻机制 2 个 plist**：`com.praise.codex-watch.plist`（`codex-watch run`，KeepAlive=true）/ `com.praise.codex-watch-healthcheck.plist`（每 60s） | `~/Library/LaunchAgents/` | 插件需提供安装脚本或文档 | watcher 不自启，capsule 投了没人消费，review 永久 pending |
| `goal-gd` / `gd-review` skill 壳 | `~/.claude/skills/` + `capabilities/source/skills/claude-active/` | 收进插件 `skills/` | 插件原生该承载，现散两处、装了不齐 |
| 🔬 **`review-result-writer.sh`（bridge 默认 writer）** | `~/.claude/scripts/review-result-writer.sh` | 收编或改 bridge 默认指向 GD 自带 `scripts/rev-result-writer.sh` | 实测 `gd-codex-bridge-review.py:72` 默认 `WRITER_PATH`=它，`:1253` 检查存在、`:1270` `bash` 真执行；不设 `GD_WRITER_PATH_OVERRIDE` 时 bridge 写结果环节硬依赖此旧 writer，缺失即报"writer 不存在"，`/gd review` execution/code 写出失败 |
| 🔬 **`~/.claude/history`（master-plan 校验路径常量）** | `~/.claude/history` | 解耦或声明 | `gd-validate-master-plan-consistency.py:40` 硬编码此路径；插件装到别处该引用断 |
| handoff 运行态 `active/` `archive/` `state/` | `~/.claude/handoff/` | **不包含**（数据非机制） | — |

### B 组：旧 /review L3 —— 不是 GD 机制，明确排除 🚫

| 项 | 位置 | 排除理由 |
|----|------|---------|
| 旧 `/review` 命令 | `~/.claude/commands/review.md`（21KB） | GD 要替代的对象 |
| 8 个 review-chain hooks：`review-stop-marker` / `review-chain-touch-marker` / `review-stop-guard` / `review-chain-session-init` / `review-chain-verify-gate` / `review-writer-required-gate` / `review-stop-clear` / `review-intent-marker` | `~/.claude/scripts/hooks/` + settings.json 注册 | 全部引用 `review-result-writer`（旧 writer），**无一引用 Project GD / bridge / review2**；GD 刻意用 `REV_VERDICT` 规避 |
| workspace-cleanup plist | `~/Library/LaunchAgents/com.praise.codex-workspace-cleanup.plist` | 与 codex/GD 无关的清理任务 |

> 🔬 **验证修正**：`review-result-writer.sh` 原列于此组（"旧 writer 应排除"），实测它是 GD bridge 运行时默认依赖，**已移至 §3 A 组**。8 个 hook 仍属旧链路（确实只引用旧 writer、不引用 bridge/review2），但"它们共用的 writer 同时被 GD bridge 默认调用"——排除 hook 时务必保留 writer 本身。
> 归属判断可信度：高（引用链 + CLAUDE.md 规避声明 + 动态验证）。**建议封装时实跑一次 `/gd review` 确认不触发这 8 个 hook，再定稿排除。**

---

## 4. 已包含（对照，确认无缺口）

| 类别 | 位置 | 状态 |
|------|------|------|
| 命令源 | `commands/{gd,review2}.md` | ✅ 在 GD |
| 编排脚本 ~50 个 | `scripts/gd-*.py` `scripts/lib/` | ✅ 在 GD |
| bridge | `scripts/gd-codex-bridge-review.py` | ✅ 在 GD |
| review 标准 | `prompts/gd-review-standard.md` | ✅ 在 GD |
| schema | `schema/*.json` | ✅ 在 GD |
| **计划/执行/审查模板 16 个** | `templates/`（plan-template / gd-master-plan / gd-step-plan / gd-child-plan-prompt / gd-plan-review / execution 系列 …） | ✅ 在 GD，主链路与 /review2 共用 GD_STANDARD，零外部引用 |
| GD 自带 writer | `scripts/rev-result-writer.sh` | ✅ 在 GD |

---

## 5. 收口结论

“L1-L3 权威机制都要包含”的精确版本：

1. **L3 GD 链路机制要收齐**：补 `skills/`（goal-gd、gd-review）；决策 handoff daemon 体系（6 脚本 + 2 lib + 2 plist 常驻机制）。← 真缺口
2. **L1/L2 不能"包含"只能"声明 + 镜像"**：二进制声明依赖、配置只留审计镜像；否则平台锁定 + 泄密。
3. **旧 /review L3 机制要主动排除**：review.md + 8 hooks 不是 GD 链路，是 GD 要替代/规避的对照物。⚠️ 但 `review-result-writer.sh` **不在排除之列**——经验证它是 GD bridge 默认 writer（见 §3 A 组）。

**唯一真正卡住自包含的**：handoff daemon 体系 + 2 个 LaunchAgent —— runtime-only、无工程源、旧链路也在用的共享设施。要它进插件需四步：
- (a) 收源进 `scripts/`
- (b) 解 `gd-codex-bridge-review.py:73` 硬编码路径
- (c) 插件提供 plist 安装机制
- (d) 处理与现有 `~/.claude/handoff/` 共存（旧 /review 也依赖同一 daemon）

---

## 附：本盘点的证据扫描点（复查用）

- L1 路径：`which codex` → `~/.local/bin/codex` → standalone 0.136.0；`~/.npm-global/lib/node_modules/@openai/` 实测为空
- L2 清单：`ls ~/.codex/` + `config/gd-runtime-parity-manifest.json` 分类
- bridge 硬依赖：`scripts/gd-codex-bridge-review.py:73` = `Path("/Users/praise/.claude/handoff/bin/codex-send-wait")`
- daemon 链：`codex-send-wait` source `lib/state-paths.sh` + `lib/watch-state.sh`，第 48 行读 watcher 状态
- plist：`plutil`/plistlib 读 ProgramArguments，`com.praise.codex-watch` = `[handoff/bin/codex-watch, run]` KeepAlive=true
- hook 归属：8 个 hook 全 grep 命中 `review-result-writer`，无一命中 `Project GD`/`gd-codex-bridge`/`review2`
- 模板：`grep ${GD_PROJECT_ROOT}/templates/` 在 gd.md:165-166；review2 链路 grep 无 GD 外模板引用

### 🔬 动态试跑验证证据（2026-06-03 修正来源）

- L1 实跑：`codex --version`=`codex-cli 0.136.0`；`file` 确认 Mach-O arm64 原生二进制（非 npm/node 形态）
- L2 漂移：`ls ~/.codex/AGENTS.md`=7496B vs manifest 记 0B
- L3 bridge writer 依赖：`gd-codex-bridge-review.py:72/1253/1270`（默认 WRITER_PATH → 检查存在 → bash 执行）
- L3 history 依赖：`gd-validate-master-plan-consistency.py:40` = `PurePosixPath("/Users/praise/.claude/history")`
- L3 self-test：`gd-review-router.py --self-test` → FAIL（`fixtures/review-router-v2` 缺失，详见隔离清单）
- 主链路全路径扫描：56 文件，GD 外路径 11 类，全部已归入本清单
- **未做**：端到端真发 Codex 的 `/gd review`（避免外部消耗）
