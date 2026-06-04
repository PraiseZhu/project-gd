# GD 插件封装 — 主链路 vs 非主链路 隔离清单

> 日期：2026-06-03
> 目的：封装插件前，把 GD 项目里**与 3 条主链路（L1/L2/L3）无关的文件、旧代码、测试、一次性脚本、治理产物**与主链路运行时文件隔离，明确"进插件 / 留工程仓 / 归档删除"三个去向。
> 配套：缺口盘点见 [`2026-06-03-plugin-packaging-gap-inventory.md`](./2026-06-03-plugin-packaging-gap-inventory.md)
> 方法：以 `commands/gd.md` + `commands/review2.md` 直接引用脚本为种子，求二级调用闭包 → 主链路脚本集；其余为隔离候选。非推测，基于实地 grep。
> **验证修正（2026-06-03）**：动态试跑 L3（`gd-review-router.py --self-test`）暴露 fixtures 缺失，已补入 §3，以 🔬 标注。

---

## 0. 总览

| 区域 | 现状 | 隔离状态 |
|------|------|---------|
| 顶层目录 | 运行核心(`commands/scripts/prompts/schema/templates`) 与治理产物(`reports/results/fixtures/...`) **已分目录** | 半隔离，封装时用打包白名单挡治理目录即可 |
| **`scripts/`** | 55 个脚本：**34 主链路 + 21 非主链路混居同一目录** | ❌ 未隔离，重灾区 |

主链路脚本判定：55 个中 34 个属于 `/gd` + `/review2` 链路（30 直接引用 + 二级闭包），21 个无关。

---

## 1. `scripts/` 21 个隔离候选 — 按性质三分

### ① 旧 /rev 链路死代码（6）→ 归档 `archive/` 或删除
| 脚本 | 取代者 |
|------|--------|
| `rev-baseline.py` | — (lab 初版) |
| `rev-codex-exec.py` | `gd-codex-bridge-review.py` |
| `rev-execution.py` | `/gd execute` 链路 |
| `rev-result-writer.sh` | (GD 主链路不再用；⚠️ 勿与 bridge 默认调用的 `~/.claude/scripts/review-result-writer.sh` 混淆——后者是 live 旧 writer，见缺口盘点 §3 A 组) |
| `gd_review_detection.py` | `gd-detect-review-target.py` + `gd_review_contract.py` |
| `gd-codex-review.py` | `gd-codex-bridge-review.py` |

**痛点**：留着让 `scripts/` 看似有两套 review 实现，封装时易误打包旧链路；与 L3"旧 /review 应排除"原则一致。

### ② smoke / regression 测试（8）→ 移到 `tests/`
`gd-bridge-compat-smoke.sh` · `gd-l1-combined-bundle-smoke.sh` · `gd-l3-regression-v1-fixtures.sh` · `gd-review2-capsule-policy-smoke.sh` · `gd-review2-output-coverage-smoke.sh` · `gd-review2-plan-routing-smoke.sh` · `gd-review2-plan-template-preflight-smoke.sh` · `gd-review2-sc-extraction-snapshot-smoke.sh`

**痛点**：测试脚本与运行时脚本同目录，打包 `scripts/` 会把开发期 smoke 一起装进用户环境。

### ③ 一次性运维（2）→ 删除或归档
`gd-install-rev21-for-handtest.sh`（一次性 handtest 安装） · `gd-run-akb-plan3-fresh-rerun.sh`（一次性 akb rerun）

**痛点**：一次性任务已完成使命，是纯噪音。

### ④ 项目治理/诊断（5）→ 移到 `tools/` 或 `release/`（灰区，隔离前确认）
`gd-validate-release-evidence.py` · `gd-root-parity-status.sh` · `gd-owned-path-audit.py` · `gd-check-review-route-preflight.sh` · `gd-bridge-preflight.py`

**痛点**：服务"GD 工程发布治理"而非"/gd 运行时"，混在 `scripts/` 让人分不清哪些是插件运行必需。
**注意**：`gd-check-review-route-preflight.sh` / `gd-bridge-preflight.py` 可能在 install/preflight 时被调用，隔离前需确认非运行依赖。

---

## 2. 顶层目录 — 封装进/留判定

| 进插件（运行时） | 留工程仓 / 不进插件（开发·治理·历史） |
|---------------|----------------------------------|
| `commands` `prompts` `schema` `templates` + `scripts/` 主链路 34 + `config`(运行所需) | `reports`(70) `results`(111) `fixtures`(198) `baselines`(5) `artifacts`(17) `plans`(2) `.planning`(7) `mirrors`(71,审计镜像) `docs`(9) `history` |

**体积**：治理目录占大头 — results 836K + fixtures 808K + reports 716K + mirrors 668K ≈ 3MB。已分目录，隔离成本低：一条打包白名单 / `.claudepluginignore` 即可挡在插件外。

---

## 3. 边角项

### 🔬 fixtures 缺失：被主链路引用但不在 git（动态验证发现）

| 缺失目录 | 被谁引用 | 证据 | 影响 |
|---------|---------|------|------|
| `fixtures/review-router-v2` | `commands/gd.md` + `gd-review-router.py`（self-test + live 路由） | `--self-test` 实跑报 `FIXTURES_V2 dir missing`；`git ls-files` = 0 | 干净 checkout / 插件分发上 router self-test 与部分 review 路由 FAIL |
| `fixtures/review-contract-drift` | `gd-validate-review-contract-drift.py` 链路 | `git ls-files` = 0，引用却存在 | contract drift 校验在干净 checkout 上无 fixture |

**痛点**：与隔离清单"fixtures 留工程仓"假设冲突——这两个目录被**主链路运行时**引用，却根本不在版本控制；插件分发后依赖功能直接崩。**封装前必须**：确认它们应入 git（补提交）还是改为运行时不依赖。

### `.claude/` 39M（5311 文件）
= worktree 残留(`worktrees/` + `settings.local.json`)，**已 gitignore**(git 跟踪 0 文件)，不会进插件。可顺手 `git worktree prune` 清理物理占用。

### 待核查脚本引用（主链路脚本内部引用了 `scripts/` 不存在的名字）
```
gd-command-parity.sh          gd-test-bridge-parser.py
gd-command.sh                 gd-validate-codex-cross-review-aggregate.py
gd-sync-codex-chain.sh ←实际在 bin/(误报)   gd-validate-review-contract-drift.py
gd-validate-runtime-evidence.py             gd-validate-runtime-strict-binding.py
gd-validate-subplan-codex-binding.py
```
**说明**：含误报 — `gd-sync-codex-chain.sh` 实在 `bin/`；`gd-command*.sh` 可能是 `check-gd-command-parity.sh`/`install-gd-command.sh` 的别名。其余为真悬空候选（指向不存在脚本 = 潜在断引用）。**封装前需逐一核实**，否则插件装到别处这些引用会断。

---

## 4. 建议隔离顺序

1. **先核查**：待核查脚本引用 + 🔬 缺失 fixtures（`review-router-v2`、`review-contract-drift`）逐一确认——前者防误删，后者决定补提交 git 还是解依赖。
2. **归档死代码**：① 组 6 个 `git mv` 到 `archive/`。
3. **建 `tests/`**：② 组 8 个 smoke 迁入。
4. **建 `tools/`**：④ 组 5 个治理脚本迁入（确认非运行依赖后）。
5. **删一次性**：③ 组 2 个。
6. **打包白名单**：顶层治理目录列入插件 ignore。
7. **清理**：`git worktree prune` 清 `.claude/worktrees`。

完成后 `scripts/` 应只剩 34 个主链路脚本 + `lib/`，目录语义清晰，可直接进插件。
