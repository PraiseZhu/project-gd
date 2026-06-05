# GD KEEP-MANIFEST（隔离区定义 / 保留清单）

> 日期：2026-06-05
> 用途：把 GD 工程里**所有需要保留的文件和内容**一次性圈定。本清单 = **隔离区的定义**：
> **在单上 = 保留（隔离区内）；不在单上 = 可删（隔离区外）。**
> 验证依据：全部经实地 `grep` 引用闭包 + git 跟踪状态核实，非凭目录名猜测。
>
> **物理 vs 逻辑说明**：本清单是**逻辑隔离区**，不物理搬动文件。原因——`fixtures/`(58 处引用) `reports/`(9) `results/`(10) `mirrors/`(8) 等被代码按"仓库根相对路径"写死引用，物理搬进某个子目录需重指 ~95 处、且与代码目录约定对撞、高概率搞断自检；而物理搬动**对"哪些可删"零影响**。所以用清单划线，比搬家更安全、效果相同。

---

## 一、隔离区内 · Tier 1：进插件包（运行时权威链路）

用户跑 `/gd`、`/review2`（及待收编的 `/review1`）真正需要的运行时代码。封装时**进包**。

| 目录/文件 | 角色 | 为什么需要 |
|-----------|------|-----------|
| `commands/`（gd.md, review2.md, review1.md） | 命令入口 | L3 `/gd`、L2 `/review2`、L1 `/review1`（2026-06-05 收编）三档 review 触发面 |
| `scripts/` 34 个 py + `lib/` | 主链路运行时 | bridge/router/validator/controller/capsule-builder/SSOT 闭包 |
| `scripts/install-*.sh`、`uninstall-gd-command.sh` | 安装机制 | 命令安装/卸载（封装时或由 plugin.json 接管，但留仓库） |
| `schema/`（17） | 数据契约 | route-report / aggregate / probe / v2-result 等 SSOT schema |
| `templates/`（19） | review 模板 | plan/code/execution/combined + v2 模板 |
| `prompts/`（3） | review 标准 prompt | bridge 发给 codex 的审查标准 |
| `config/`（2） | 运行配置 | gd-runtime-parity-manifest.json、secret-scan-regexes.json |
| `vendor/l3-transport/`（14） | L3 传输层收编 | writer/codex-send(-wait)/codex-watch daemon/lib/plist/skill 壳 |

---

## 二、隔离区内 · Tier 2：留仓库不进包（开发/测试/治理/安装支撑）

链路的**周边支撑物**——不是运行时依赖，但开发/CI/治理/安装需要。封装时**不进包**（打包白名单排除）。

| 目录 | 角色 | 引用证据（删了会断什么） |
|------|------|------------------------|
| `tests/`（8） | smoke/回归测试脚本 | final-closure 跑它们；CI 门 |
| `fixtures/`（228） | 测试输入数据 | 11 个自检/smoke 脚本、58 处 `fixtures/...` 引用 |
| `tools/`（9） | 发布/安装治理脚本 | release-status/parity/closure/check-parity（D3 已隔离至此） |
| `mirrors/codex-chain/`（72） | L1/L2 审计快照 | release-status parity 闸读 `$ROOT/mirrors/`（8 处） |
| `bin/`（gd-sync-codex-chain.sh） | mirror 刷新工具 | 刷新 mirrors/ 的唯一入口 |
| `docs/`（11+） | 决策/盘点记录 | 封装边界 D1/D2/D3、隔离清单、本清单 |
| `plans/`（2） | 历史 master-plan | final-closure self-test 读 `plans/gd/...master-plan.md` |

---

## 三、隔离区内 · 根文件

| 文件 | 角色 |
|------|------|
| `README.md`、`CLAUDE.md`、`VERSIONING.md`、`PROJECT_GOAL.md` | 项目文档/目标 |
| `.gitignore` | git 元数据 |
| `.deploy-manifest.jsonl` | deploy-live 部署编排清单 |

---

## 四、混合目录的文件级规则

这些目录**部分保留、部分可删**：

### `reports/` — 绝大多数是历史过程，少数被引用
- **保留**（被活代码引用）：
  - `reports/project-gd-flow-closure-rev21/20260517T154346Z/backup-manifest.json`（final-closure 读）
  - `reports/review-trust/legacy-review-trust-audit.md`（audit 输出）
  - 运行时输出目录壳：`reports/review-router/`、`reports/_selftest_runtime_evidence/`、`reports/bridge-preflight/`（跑时自动重建，**内容可清空**，保留 `.gitkeep`）
  - `reports/gd-v7-plan6.5-b-codex-bridge.md`（被 keep prompt `gd-review-standard.md` 以"详见"引用，校验时发现，归入保留）
- **可删**（历史过程产物）：`gd-v7-*.md`、`phase-*.md`、`*.start.marker`、`*-hashes.txt`、`*-hashes.json`、`sanity-*.md`、`parity-check.md` 等一次性计划执行记录

### `results/` — 跟踪=证据(留)，未跟踪=过程(删)
- **保留**：git 已跟踪的 `results/release-evidence/*/run-manifest.json` + curated 证据（.gitignore 明确要留）
- **可删**：未跟踪的 60 个文件（`raw-*`、`codex-output-*` 已 gitignore）

### `baselines/` — gd-v7 状态(留)，/rev 残留(删)
- **保留**：`gd-v7-lock-revisions.jsonl`、`gd-v7-runtime-write-authorizations.jsonl`、`gd-v7-state-freeze.json`（install/review2/controller 引用）
- **可删**：`baselines/phase2-test/`（旧 /rev lab 测试残留）

---

## 五、隔离区外 = 可删

> ⚠️ 删除前请确认本节。删除均为工作树操作，git 跟踪文件的历史仍保留在版本库。

**高置信（纯过程/死代码/缓存）：**
| 目标 | 性质 |
|------|------|
| `archive/`（8） | 旧 /rev lab 死代码 + 一次性脚本（git 历史已存） |
| `artifacts/`（17） | bridge run 日志（过程输出） |
| `.planning/`（7） | pwf 规划产物（已 gitignore） |
| `.ruff_cache/` | lint 缓存 |
| `history/`（空） | 空目录 |
| `reports/` 历史过程文件 | 见 §四规则（gd-v7-*/phase-*/marker/hashes） |
| `results/` 未跟踪（60） | 过程输出 |
| `baselines/phase2-test/` | /rev 残留 |

**待确认（可能可删，删前点头）：**
| 目标 | 判断 |
|------|------|
| `manifest.json` | 死 /rev lab 项目清单（project_status=terminal，讲 bin/rev）。**校验已确认**：3 处"引用"全是 CLI usage 占位/字段占位值，无真读取 → 可删（建议删后跑一遍 self-test 兜底） |
| `manifest.gd-v7.json` | gd-v7-shared-core 治理/hash 记录，**无活代码引用**。可作历史保留或删；删则一并清 `docs/gd-v7-shared-core-index.md` 相关 |

**/rev legacy 遗留（校验发现，单独决策）：**
- `reports/parity-check.md`：仅被 `prompts/rev-review-standard.md` 引用，后者被 `gd.md:454` 标 `legacy_rev_standard`（死 /rev）→ 可删
- `prompts/rev-review-standard.md` 本身是 /rev 遗留 prompt（gd.md 仅作 legacy 提及）。删它需同步去掉 gd.md:454 的 legacy 引用——属 /rev 残留清理,与本清单的"过程文件"分开决策

---

## 七、区外可删性验证结果（2026-06-05）

> 校验脚本：算出 keep-set 之外全部项 → 逐个 grep 所有 keep 可执行文件(scripts/tests/tools/bin/commands/vendor/config/schema/templates/prompts)是否引用它。被硬依赖=不可删。

- 工作树 **691** 文件：隔离区内 **445** / 区外 **246**
- **区外被 keep 硬依赖：0** ✓ → 区外全部可安全删除
- 软引用 2（已三角验证可删）：`manifest.json`(占位串)、`reports/parity-check.md`(legacy prompt 文档引用)
- 校验中修正了 3 处清单初判：①`gd-v7-plan6.5-b` 报告改判保留 ②`manifest.json` 确认可删 ③发现 /rev legacy 链(parity-check + rev-review-standard)

---

## 六、本清单未覆盖 / 后续

- **L1 `/review1` 已收编（2026-06-05）**：`commands/review1.md` 收编自 `~/.claude/commands/review.md`，命令名 `/review`→`/review1`，writer 调用重指 `vendor/l3-transport/`。运行层完整解耦（vendor writer 内部 `~/.claude` 引用）见 `vendor/l3-transport/README.md`，封装阶段完成。
- **机械化校验（建议）**：可写一个脚本读本清单 keep-set → 列出工作树里所有不在 keep-set 的项 = 区外可删集，做到"确保区外都可删"可重复验证，而非人工比对。
