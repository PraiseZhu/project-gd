# /gd v7 边界与基线报告（Stage A）

> **Plan**：Plan 1 边界与基线 v2
> **Stage**：A（立即执行；Stage B 在 Step 8 收口时执行）
> **Captured at**：2026-05-10T14:36:37Z
> **Default execution host**：Claude Code
> **Codex execution required**：false

---

## 1. 本轮目标声明

本轮工作目标：**Claude-first `/gd` 多 Agent 链路**（v7 锁定）。

权威源：

- `memory/priority/project_gd_upgrade_plan.md`
- hash：`081f62b3a89d56550f893376f9934d4dc11f16a0f35a0a99562462a77c8a12bd`

v7 关键定位（与 v6 差异）：

- 主宿主全程 Claude Code（4 个阶段全部）
- Codex 收窄为 **cross-review sidecar**，仅出现在 Step 6
- Codex Desktop 全量 adapter 移至 backlog，不在当前 8-step 范围内

---

## 2. 旧 artifact 边界

### `Project GD/PROJECT_GOAL.md`

- hash：`9c956d4439005b5bb720a68d706075456c5fa6b32215a235ffe908b689426edd`
- 状态：`legacy_rev_goal_not_v7_authority`
- 含义：**当前 PROJECT_GOAL.md 是旧 `/rev` 实验 artifact，不是 v7 权威目标源。**
- 是否升级为 `/gd` 目标文件 → 留给后续 Shared Core 计划决定，本计划不修改。

### `Project GD/prompts/rev-review-standard.md`

- hash：`6ace39fdff28b067e5a045dc468be318ceb5e8184751a50f8e97b3853fd66a48`
- 状态：`legacy_rev_standard`
- 含义：v7 若建立新 Shared Core review standard，将替换它；此 hash 用于将来对比。

### `Project GD/manifest.json`

- hash：`3cb7573ba08d23360ff61392472ff518ac521733484b0c661ae198ad6c9241f3`
- 状态：Phase 4 终点状态（`project_status: terminal`），Plan 1 v2 **不修改 manifest**，避免与 Phase 4 终点声明冲突。

---

## 3. Protected Runtime 保护策略

以下 runtime 文件在 v7 全部 step 内**只读**；任何 hash 变化都视为未授权改动：

### 3.1 review_runtime_core（7 个）

```
/Users/praise/.claude/commands/review.md
/Users/praise/.claude/settings.json
/Users/praise/.claude/handoff/bin/codex-watch
/Users/praise/.claude/handoff/bin/codex-send
/Users/praise/.claude/handoff/bin/codex-send-wait
/Users/praise/.claude/scripts/review-result-writer.sh
/Users/praise/.claude/scripts/review-chain-verify.js
```

### 3.2 review_hooks_enumerated（8 个，**已展开通配符**）

```
/Users/praise/.claude/scripts/hooks/review-chain-session-init.js
/Users/praise/.claude/scripts/hooks/review-chain-touch-marker.js
/Users/praise/.claude/scripts/hooks/review-chain-verify-gate.js
/Users/praise/.claude/scripts/hooks/review-intent-marker.js
/Users/praise/.claude/scripts/hooks/review-stop-clear.js
/Users/praise/.claude/scripts/hooks/review-stop-guard.js
/Users/praise/.claude/scripts/hooks/review-stop-marker.js
/Users/praise/.claude/scripts/hooks/review-writer-required-gate.js
```

### 3.3 通配符禁令

baseline 中 `wildcard_storage_forbidden: true`。**禁止**用 `review-*.js` 形式存储——必须在采集时枚举展开为具体文件名。否则将来新增/重命名文件时，Stage B 的 hash 对比会出现假绿灯。

### 3.4 missing_at_baseline 处理

当前所有 protected 文件均存在，列表为空。若未来 Stage A 重跑时发现某文件缺失（被卸载/重命名），应记录 `hash: null + status: missing_at_baseline`，**不可静默跳过**。

---

## 4. 写入边界

### 4.1 本 Plan 允许写入

- `Project GD/baselines/**`
- `Project GD/reports/**`

### 4.2 本 Plan 不修改

- `/Users/praise/.claude/**`（任何子路径）
- `Project GD/bin/rev`
- `Project GD/prompts/rev-review-standard.md`
- `Project GD/PROJECT_GOAL.md`
- `Project GD/manifest.json`
- `Project GD/reports/source-hashes.json`
- `Project GD/reports/phase-4-source-hashes.json`
- 旧 `/review`、旧 `/rev` 任何运行入口
- Codex workspace 模板

### 4.3 后续安装 `/gd` command 的授权协议

`~/.claude/commands/gd.md` 的安装（或任何 `~/.claude/**` 写入）必须满足：

1. 用户在对话中明确授权
2. 在 `Project GD/baselines/gd-v7-runtime-write-authorizations.jsonl` 追加一行授权记录
3. 字段：`ts / target_path / granted_by / scope / plan_ref / rationale`
4. 文件性质：append-only JSONL；不可修改、不可删除已有记录
5. **Stage B 仅认 ledger 内的授权记录**，对话中口头授权但 ledger 无记录视为无效

当前 `current_authorizations: []`（空），未授权任何 `~/.claude/**` 写入。

---

## 5. Stage B（延后产物）

### 5.1 触发时点

Step 8 收口时执行。

### 5.2 产物

`reports/gd-v7-final-isolation.md`（**Plan 1 v2 不创建**，Step 8 才创建）

### 5.3 执行规则

- 读取 `baselines/gd-v7-state-freeze.json`
- 重新 hash 所有 protected runtime 文件（按枚举清单逐一计算）
- 比对 before / after：
  - review_runtime_core 任一 hash 变化 → final verdict = `FAILED`
  - review_hooks_enumerated 任一 hash 变化 → final verdict = `FAILED`
  - 文件缺失或新增（不在 baseline）→ final verdict = `FAILED`
- 若 `~/.claude/commands/gd.md` 存在：
  - 必须在 ledger 中有对应授权记录 → 通过
  - 否则 final verdict = `FAILED`
- 不得临时重建 before baseline 来掩盖差异

### 5.4 Stage B fallback（Plan 1 v2 review 补丁 #3）

- 若 Step 8 在 Stage A 起 **≥ 30 天后** 仍未执行 Stage B：
  - baseline 标 `expired_unverified`
  - 重启 v7 工作前，**用户必须显式喊『提前 isolation 收口』** 触发 Stage B
  - 否则不得进入后续 v7 step
- 过期检查锚点：`expiry_check_anchor = 2026-06-09T14:36:37Z`（纯 ISO8601，可 strptime 解析）
- 公式参考：`expiry_check_formula = captured_at + 30 days`（说明性字段，不参与机器解析）

---

## 6. Project GD 当前状态记录

- 分支：`main`
- HEAD：`85563c7`
- modified：`CLAUDE.md`、`README.md`
- untracked：Phase 1-4 实验产物（`PROJECT_GOAL.md` / `manifest.json` / `bin/` / `prompts/` / `reports/` / `results/` 等）
- **既有状态记录但不阻塞 Stage A**；Stage B 对比时只看 protected runtime 与 v7_authority master plan hash，不把 Project GD 实验产物视为偷改面

---

## 7. Plan 1 v2 Review 修正回执

| # | Review 补丁 | 落地位置 |
|---|-----------|---------|
| 1 | v7 master plan hash 入 baseline | `v7_authority.master_plan_hash` |
| 2 | review-*.js 枚举展开禁通配符 | `review_hooks_enumerated`（8 个具体文件名）+ `wildcard_storage_forbidden: true` |
| 3 | Stage B 30 天 fallback | `stage_b_fallback` 块 |
| 4 | runtime write authorization ledger 格式定义 | `runtime_write_authorization.ledger_*` + 空 ledger 文件已建 |

可选补丁也已落地：

- `prompts/rev-review-standard.md` 入 baseline 标 `legacy_rev_standard`
- `missing_at_baseline` 字段 + hard-stop 处理规则
- 明确 `modifies_manifest_json: false`

---

## 8. Stage A 验收清单

```bash
cd "Project GD"
test -f baselines/gd-v7-state-freeze.json
test -f reports/gd-v7-boundary-baseline.md
test -f baselines/gd-v7-runtime-write-authorizations.jsonl
grep -q 'gd-boundary-baseline.v2' baselines/gd-v7-state-freeze.json
grep -q 'legacy_rev_goal_not_v7_authority' baselines/gd-v7-state-freeze.json
grep -q '/Users/praise/.claude/settings.json' baselines/gd-v7-state-freeze.json
grep -q 'review-stop-marker.js' baselines/gd-v7-state-freeze.json
grep -q 'master_plan_hash' baselines/gd-v7-state-freeze.json
grep -q 'wildcard_storage_forbidden' baselines/gd-v7-state-freeze.json
grep -q 'stage_b_fallback' baselines/gd-v7-state-freeze.json
grep -q 'runtime_write_authorization' baselines/gd-v7-state-freeze.json
```

---

## 9. 不在本 Plan 范围

- `/gd` 任何功能实现
- 运行 `/review`、`bin/rev`、调用 Codex
- 写 `~/.claude/**`
- 修改 `manifest.json`、`PROJECT_GOAL.md`、`bin/rev`
- 启动 Step 1（State Freeze + Capability Probe）正式工作（本 Plan 仅准备 baseline 数据，Step 1 step plan 仍待批准）
