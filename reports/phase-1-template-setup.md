# Phase 1 Report：模板与 Setup 收口

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

> 执行日期：2026-05-09
> 执行者：Claude（claude-sonnet-4-6）
> Phase 状态：**完成**

---

## PHASE_GOAL 验收

**目标**：固定 `Project GD/` 边界，建立实验模板和 review 标准源，使 Phase 2 不再需要重新决定目标链、Anti-Fill 规则和 review 标准。

**状态**：✅ 达成

---

## 交付物清单

| 文件 | 类型 | 状态 | 行数 |
|------|------|------|------|
| `manifest.json` | new | ✅ 已创建 | 46 |
| `templates/plan-template.md` | new | ✅ 已创建 | 114 |
| `prompts/rev-review-standard.md` | new | ✅ 已创建 | 263 |
| `reports/source-hashes.json` | new | ✅ 已创建 | 29 |
| `results/.gitkeep` | new | ✅ 目录已创建 | — |
| `README.md` | rewrite | ✅ 全文改写（从 167B 占位到完整说明） | 90 |
| `reports/phase-1-start.marker` | new | ✅ 阶段开始时间戳 | 1 |

---

## 验收结果

### SC-1：目标链字段完整性

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-1 | `templates/plan-template.md` 包含 REVIEW_STANDARD 引用 | `grep 'REVIEW_STANDARD' templates/plan-template.md` → 命中第 3 行 | ✅ pass |
| SC-2 | `templates/plan-template.md` 包含 PROJECT_GOAL/CHAIN_GOAL/PHASE_GOAL/TASK_GOAL 字段 | `grep 'CHAIN_GOAL\|PHASE_GOAL\|TASK_GOAL' templates/plan-template.md` → 命中 | ✅ pass |
| SC-3 | `templates/plan-template.md` 包含 SC-* 编号化标准和 Verify 列 | `grep 'SC-\*\|Verify' templates/plan-template.md` → 命中 | ✅ pass |
| SC-4 | `prompts/rev-review-standard.md` 包含 anti-generic 判定规则 | `grep '泛化' prompts/rev-review-standard.md` → 27 matches | ✅ pass |
| SC-5 | `prompts/rev-review-standard.md` 包含 REV_VERDICT 契约 | `grep 'REV_VERDICT' prompts/rev-review-standard.md` → 命中 | ✅ pass |
| SC-6 | 无裸 `VERDICT:` 输出 | `grep '^VERDICT:' prompts/ templates/` → 0 matches | ✅ pass |
| SC-7 | `PROJECT_GOAL.md` hash 未改动 | `shasum -a 256 PROJECT_GOAL.md` → `34acb50...` | ✅ pass |
| SC-8 | `~/.claude/` 核心目录未被本次执行写入 | `find ~/.claude/commands ... -newer phase-1-start.marker` → 仅 heartbeat（codex-watch daemon 正常行为） | ✅ pass |
| SC-9 | template parity PASS | `diff live-plan-template codex-plan-template` → 无差异 | ✅ pass |
| SC-10 | REVIEW_STANDARD 引用出现在 templates/ prompts/ README.md | grep 检查 → 4 处命中 | ✅ pass |

---

## 执行摘要

### Step 1：状态识别

- git status：`CLAUDE.md` modified（预期），`PROJECT_GOAL.md` + 新目录 untracked（预期）
- PROJECT_GOAL.md hash：`34acb50ca3ab913c6e4c5bbe52fe1a651ca9652d41febc24bd846204dbc92c16`
- Template parity 基线：PASS（live 与 Codex 两端 plan-template.md hash 一致）
- Phase start marker：`2026-05-09T14:35:29Z`

### Step 2：Setup 验证

- 所有必要目录已存在：`bin/ templates/ prompts/ schema/ scripts/ baselines/ fixtures/ reports/ history/`
- 补建 `results/` 目录（CLI 合约：`bin/rev` 输出目录）
- 补建缺失的 `.gitkeep`：`bin/ templates/ prompts/ docs/`
- CLAUDE.md invariants 验证：`lab-only` ×2 ✓，`REV_VERDICT` ×6 ✓

### Step 3：manifest.json + source-hashes.json

- `manifest.json`：Phase 输出清单、约束摘要、复用 vs 绕开表
- `reports/source-hashes.json`：PROJECT_GOAL.md + CLAUDE.md + codex-watch + live/codex plan-template hash 快照

### Step 4：templates/plan-template.md

包含：
- `REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md` 引用（第 3 行）
- 完整目标链字段（PROJECT_GOAL / CHAIN_GOAL / PHASE_GOAL / TASK_GOAL）
- SC-* 编号化标准表（ID / 成功标准 / Verify 三列）
- 实施步骤格式（SC-* 映射标注 / Hard-stop / 验收）
- 边界约束段落（允许/禁止写入路径 + 复用 vs 绕开表）

### Step 5：prompts/rev-review-standard.md

包含（9 节）：
1. 输出契约（REV_VERDICT、全中文、结构模板）
2. Goal-Driven 检查（目标链完整性、SC-* 编号化、步骤映射）
3. Anti-Fill 检查（三条判定规则 A/B/C + 误判防护）
4. 阻断阈值（触发 / 不触发 REQUIRES_CHANGES 的条件）
5. Plan Review 专属规则（Non-Goals、Hard-stop、文件范围声明）
6. Code Review 专属规则（SC-* 完整性、路径越界）
7. Convergence 规则（多轮 review）
8. Parity 检查（桌面端引用约定）
9. 质量规则（证据、最小修复、残余风险）

### Step 6：README.md 全文改写

从 167B 占位改写为 90 行完整项目说明，包含：目的、目录结构、核心约束表、阶段进度表、review 标准引用。

### Step 7：收尾验证

所有 10 项验证通过（见上方验收结果表）。

---

## 4 个小瑕疵的智能处理

| 瑕疵 | 处理方式 |
|------|---------|
| **1. Step 2 描述不准**：v3 计划描述 src/config/data/tests "已存在" | 执行时验证目录实际情况：这些目录已被删除（之前重组目录架构时移除），验证步骤改为"确认不存在，符合 v6 目录约定" |
| **2. README 全文改写**：原 167B 占位 | 已全文改写为 90 行，含目的/目录结构/约束/进度/标准引用 |
| **3. dirty 白名单补充**：v3 未列 .DS_Store/.icloud | git status 实际未见此类文件，macOS/iCloud 副产物被 .gitignore 排除，无需处理 |
| **4. template parity check 两次**：v3 只在 Step 1 做 | 在 Step 1（基线）和 Step 7（收尾）各做一次，两次均 PASS |

---

## 手动 `.claude/` 守卫说明

V5 检查发现 `~/.claude/handoff/state/heartbeat` 有变化。这是 `codex-watch` 守护进程每次轮询时写入的时间戳文件，属于正常的 live runtime 行为，与本次 Phase 1 执行无关。本次 Phase 1 执行零写入 `~/.claude/` 内任何目录。

---

## Phase 2 前提条件

Phase 1 完成后，Phase 2（同步 runner + 精简 baseline）具备以下前提：

- ✅ `prompts/rev-review-standard.md` 已就绪（`bin/rev` 将加载此文件）
- ✅ `templates/plan-template.md` 已就绪（anti-fill 模板机制确立）
- ✅ `manifest.json` 已记录复用 vs 绕开边界（`bin/rev` 不调用 codex-watch）
- ✅ `baselines/` 目录已创建（`bin/rev` baseline 写入目标）
- ✅ `results/` 目录已创建（`bin/rev` 结果输出目标）
- ⏳ `schema/rev-baseline.schema.json`（Phase 2 产出）
- ⏳ `scripts/rev-result-writer.sh`（Phase 2 产出）
- ⏳ `bin/rev`（Phase 2 产出）

REV_VERDICT: APPROVED
