# Plan 6.5-B — Codex Bridge Candidate Segment Report

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
START_MARKER: reports/gd-v7-plan6.5-b.start.marker (2026-05-11T15:58:48Z)
GENERATED_AT: 2026-05-12T00:00:00Z
SEGMENT: B（Codex bridge replaces Plan 6 v3 direct sidecar）
PARENT_PLAN: /gd Claude-first 收口 v4 (Plan 6.5 拆 A-E)
DOWNSTREAM: C → D → E（A-D 不写 manifest active；E 才一次性 1.4.0）
PRIOR_REVIEWS:
  - Plan 6.5-B v3 plan review APPROVED（直接评估，不送 Codex；用户认可）

---

## 1. 范围与原则

Plan 6.5-B 把 Plan 6 v3 direct `codex exec` sidecar 降级为 deprecated artifact，新增 bridge wrapper 通过旧 `/review` transport 投递 Codex review。本段只建立 candidate；`/gd review plan` 仍 `local_only`，`/gd review code` 仍 `pending_future_plan`。Plan E 接线 + smoke 后才 promotion。

锁定的硬约束：

| 类别 | 状态 |
|------|------|
| 允许改 | `prompts/gd-review-standard.md` §8（重写）|
| 允许加注释 | `scripts/gd-codex-review.py`（仅头注释 deprecated marker；行为不变）|
| 允许新增 | `scripts/gd-codex-bridge-review.py`（5 子命令 wrapper）|
| 允许新增 | `fixtures/review-bridge/`（10 fixtures）|
| 允许新增 | 本 segment report |
| 禁止改 | `commands/gd.md`（active state） / `docs/gd-v7-claude-command.md` / `manifest.gd-v7.json` |
| 禁止改 | `templates/gd-plan-review-template.md` / `templates/gd-execution-review-template.md` |
| 禁止改 | 旧 `/review` / `/rev` / hooks / daemon / MCP；installed copy |
| 允许调用 | 旧 transport `~/.claude/scripts/review-result-writer.sh` + `~/.claude/handoff/bin/codex-send-wait`（仅 `run-bridge --live-transport`）|
| 禁止调用 | 旧 `/review` slash command；旧 `/rev`；codex-watch daemon API |

---

## 2. 改动文件清单

### 2.1 修改

| 文件 | before_hash | after_hash | 改动 |
|------|-------------|------------|-----|
| `prompts/gd-review-standard.md` | `f4e0585bdfa7b1aa…` | `d93989fef1a74950…` | §8 完全重写：标题改为 "Codex Cross-Review Bridge (Plan 6.5-B candidate; Plan 6 v3 direct sidecar deprecated)"；新增 §8.0-§8.9 — 状态变更 / 三层 verdict 隔离 / 职责分层 / capsule 字段分层（writer 实际只 grep 3 个）/ allow-deny 调用清单 / baseline key 公式 / mapped result 唯一权威 / 修订 merge matrix（degraded 改 FAILED 不再 completed_with_constraint）/ Plan E integration contract / 旧节废弃说明 |
| `scripts/gd-codex-review.py` | `39ca14127c5bcc25…` | `0bc2732abfacf989…` | 文件头追加 4 行 `DEPRECATED` marker，引用 Plan 6.5-B + manifest 1.3.0 + §8.0/§8.9 |

### 2.2 新增

| 文件 | sha256 | 用途 |
|------|--------|------|
| `scripts/gd-codex-bridge-review.py` | `60284310296940 30…` | bridge wrapper：5 子命令（build-capsule / run-bridge / parse-transport / merge / self-test）；run-bridge 默认 fail-closed（F9）；stdlib-only |
| `fixtures/review-bridge/raw-approved-plan.md` | `ef515983ecf3bf79…` | parse positive (plan APPROVED) |
| `fixtures/review-bridge/raw-requires-changes-plan.md` | `ef8f789a14f7df50…` | parse positive (plan REQUIRES_CHANGES + finding 含 SC + 5 中文字段) |
| `fixtures/review-bridge/raw-approved-code.md` | `886c1d74e5969226…` | parse positive (code APPROVED) |
| `fixtures/review-bridge/raw-requires-changes-code.md` | `32ac08cc8b96bb21…` | parse positive (code REQUIRES_CHANGES) — F11 补 |
| `fixtures/review-bridge/raw-missing-verdict.md` | `c1339c56bcf5e5e2…` | parse negative (no VERDICT) → degraded/FAILED |
| `fixtures/review-bridge/raw-multiple-verdict.md` | `e64ce3b96d302e33…` | parse negative (>1 VERDICT) → degraded/FAILED |
| `fixtures/review-bridge/raw-malformed-missing-field.md` | `35b8f939c9a1c086…` | parse negative (finding 缺 5 中文字段中 3 个) → degraded/FAILED |
| `fixtures/review-bridge/raw-requires-changes-missing-sc.md` | `2612d241d869182b…` | parse negative (finding 缺 SC; wrapper 加严层) → degraded/FAILED |
| `fixtures/review-bridge/writer-degraded.out` | `68e957bb8f7ee8cc…` | writer stdout fixture (DEGRADED) |
| `fixtures/review-bridge/writer-failed.out` | `4ceeb8c731f61ee8…` | writer stdout fixture (FAILED codex-send-wait exit 4) |
| `reports/gd-v7-plan6.5-b.start.marker` | — | start marker for audit |
| `reports/gd-v7-plan6.5-b.before-hashes.txt` | — | before-hash 记录 |
| `reports/gd-v7-plan6.5-b.after-hashes.txt` | — | after-hash 记录 |
| `reports/gd-v7-plan6.5-b-codex-bridge.md` | — | 本报告 |

### 2.3 未触动（边界证据；hash 与 before-hashes.txt 一致）

| 文件 | hash 状态 |
|------|----------|
| `commands/gd.md` | UNCHANGED `652617cad4c6f843…` — A-D 期间 active state 不动 |
| `docs/gd-v7-claude-command.md` | UNCHANGED `cd2b39771afcb587…` |
| `manifest.gd-v7.json` | UNCHANGED `239389aec26ff1c1…` — A-D 期间 manifest 不动 |
| `templates/gd-plan-review-template.md` | UNCHANGED `32b30e6d4ae536e0…` — Plan 6 v3 §6 JSON block 留作 sidecar 模板，bridge 不依赖 |
| `templates/gd-execution-review-template.md` | UNCHANGED `ed8dbbcb59bee4a5…` |
| `schema/gd-review-result.schema.json` | UNCHANGED `4fe3255f50e472a9…` — 复用 Plan 6 v3 schema 作 mapped 唯一权威 |
| `/Users/praise/.claude/commands/gd.md` | NOT_PRESENT — Plan D 解冻 hold |
| 旧 `/review` / `/rev` / hooks | UNCHANGED |

---

## 3. wrapper 实现要点

### 3.1 5 子命令 + F9 fail-closed

| 子命令 | 默认行为 | 写 ~/.claude/**? |
|--------|---------|-----------------|
| `build-capsule` | 拼 capsule + 计算 target_hash/capsule_hash/gd_baseline_key/run_id | 否 |
| `run-bridge` | **未传 `--live-transport` → exit 2，stderr `live-transport flag required for actual delivery`**（F9 决策）| 仅传 `--live-transport` 才会调旧 writer → writer 写 `~/.claude/review-baselines/<gd_baseline_key>/` |
| `parse-transport` | 离线解析 raw markdown → mapped JSON | 否 |
| `merge` | 合并两份 mapped JSON 按 §8.7 matrix | 否 |
| `self-test` | 跑 fixture 集合 | 否 |

### 3.2 wrapper 加严校验项（writer 不查的部分）

- raw finding 必须含 `SC: SC-<N>` 行（writer 不查；schema `findings[].sc_refs` minItems=1 强制）
- mapped JSON 必须通过 `schema/gd-review-result.schema.json`（schema additionalProperties=false → 多余字段也 reject）
- writer stdout 含 DEGRADED / FAILED / MALFORMED → wrapper 直接 fail-closed mapped FAILED，不再二次解析 raw

### 3.3 baseline key 公式

`gd_baseline_key = gd-<review_kind>-<target_slug>-<sha256(target_abs_path + target_hash + run_id)[:12]>`

由 wrapper 生成并传入 writer 的 `--baseline-key`。Writer 用此 key 创建 `~/.claude/review-baselines/<gd_baseline_key>/` 作 storage path。bridge 不再设计"双 baseline key"（v1 plan F7 残留已闭合）。

### 3.4 stdout 4 行固定顺序（F5）

`run-bridge` / `parse-transport` 输出：

```
GD_CODEX_BRIDGE_STATUS: <completed|degraded|failed_to_run>
GD_REVIEW_DECISION: <APPROVED|REQUIRES_CHANGES|FAILED>
MAPPED_RESULT: <path>
TRANSPORT_RESULT: <path or N/A>
```

---

## 4. self-test 全表

15/15 全过：

| # | fixture | kind | expected | actual |
|---|---------|------|----------|--------|
| 1 | raw-approved-plan.md | plan | completed/APPROVED | ✓ |
| 2 | raw-requires-changes-plan.md | plan | completed/REQUIRES_CHANGES | ✓ |
| 3 | raw-approved-code.md | code | completed/APPROVED | ✓ |
| 4 | raw-requires-changes-code.md (F11) | code | completed/REQUIRES_CHANGES | ✓ |
| 5 | raw-missing-verdict.md | plan | degraded/FAILED | ✓ |
| 6 | raw-multiple-verdict.md | plan | degraded/FAILED | ✓ |
| 7 | raw-malformed-missing-field.md | plan | degraded/FAILED | ✓ |
| 8 | raw-requires-changes-missing-sc.md | plan | degraded/FAILED | ✓ |
| 9 | merge claude-approved + codex-approved | — | APPROVED | ✓ |
| 10 | merge claude-approved + codex-requires-changes | — | REQUIRES_CHANGES | ✓ |
| 11 | merge claude-approved + codex-timeout | — | FAILED (matrix #4 收紧) | ✓ |
| 12 | merge claude-failed + codex-approved | — | FAILED | ✓ |
| 13 | merge claude-failed + codex-requires-changes | — | FAILED | ✓ |
| 14 | writer writer-degraded.out | — | degraded/FAILED | ✓ |
| 15 | writer writer-failed.out | — | failed_to_run/FAILED | ✓ |

---

## 5. 边界审计

| 项 | 命令 | 结果 |
|---|---|---|
| F9 fail-closed | `python3 scripts/gd-codex-bridge-review.py run-bridge ...`（无 --live-transport）| exit 2 + stderr "live-transport flag required for actual delivery" ✓ |
| e2e parse-transport | parse fixtures/plans/phase2-good-plan.md → raw-approved-plan.md → mapped JSON | completed/APPROVED + schema passing ✓ |
| 5 active state files unchanged | shasum 比对 before-hashes.txt | commands/docs/manifest/2 templates 全 UNCHANGED ✓ |
| 裸 VERDICT regression | `grep -REn "^VERDICT:" commands/ docs/ templates/ schema/ scripts/` | 0 hits ✓ |
| no-write audit ~/.claude/** | `find ~/.claude/{commands,scripts/hooks,handoff,state} -newer marker -type f` | 仅 `state/review-chain-verify/touched/<sessionId>.json` 来自历史 review chain；attributable=0 ✓ |
| installed copy | `[ -e /Users/praise/.claude/commands/gd.md ]` | NOT_PRESENT ✓ |

---

## 6. Plan 6 v3 sidecar 与 v3 fixtures 处理

| Item | 状态 |
|------|------|
| `scripts/gd-codex-review.py` | 文件头加 DEPRECATED marker；行为不变；保留作 audit/recovery |
| `fixtures/review-sidecar/*.json` (5) | bridge `merge` 子命令复用（Claude/Codex JSON）|
| `fixtures/review-sidecar/raw-*.md` (6) | 仅供 deprecated direct sidecar parser 使用（gd-review-result-json block 格式）；**不参与 bridge self-test** |
| `manifest.gd-v7.json revisions[1.3.0]` | UNCHANGED — Plan 6 v3 状态保持 `completed_with_constraint`；Plan E 时 superseded_by `1.4.0` |
| `schema/gd-review-result.schema.json` | UNCHANGED — bridge 复用作 mapped JSON 唯一权威，不新增第二套 schema |

---

## 7. §8 标准反转关键 diff

| Item | 旧（Plan 6 v3 active）| 新（Plan 6.5-B candidate）|
|------|---------------------|-------------------------|
| sidecar 入口 | `scripts/gd-codex-review.py` 直调 `codex exec --ephemeral` | `scripts/gd-codex-bridge-review.py` → 旧 transport → Codex |
| 调用旧 transport | **禁止** | **允许（仅 wrapper 在 `--live-transport` 模式）** |
| capsule 字段层级 | "Codex review capsule 必须含本文件第 1 节全部字段" | 分 3 类：writer 强制 3 (DOMAIN/FOCUS/FOCUS_SOURCE) / writer 审计轨 16 / wrapper 自用 8 |
| Codex raw 输出格式 | `<!-- gd-review-result-json:start --> ... :end -->` JSON block | 旧 writer 兼容 markdown：`# Plan|Code Review Result` 标题 + `VERDICT:` 行 + Scope/Findings/Residual + 5 中文字段 + SC: SC-N |
| bare `VERDICT:` 政策 | 全文禁止 | 三层隔离：transport raw/fixture 允许；mapped JSON / `/gd` final 禁止 |
| matrix 第 4 行 | degraded/failed_to_run → completed_with_constraint（不得 APPROVED）| degraded/failed_to_run → **FAILED**（更严格，Plan 6.5-B 收紧）|

理由：bridge 透过旧 transport 拿不到通过的 verdict 时，没有任何客观依据可以 merged 出 "completed_with_constraint" — 只能 FAILED 等用户重跑。

---

## 8. Plan E Integration Contract

Plan B 不修改 `commands/gd.md` active behavior。Plan E 接线时只能：

1. 调 wrapper `run-bridge --live-transport` 取得 mapped Codex JSON
2. 调 wrapper `merge --claude <claude.json> --codex <codex.json>` 获 merged JSON
3. 暴露 merged result 为 `/gd` final decision

Plan E 不得重新设计：
- bridge raw contract（§8.2 旧 transport 与 wrapper 职责分层）
- mapped schema（`schema/gd-review-result.schema.json`）
- merge matrix（§8.7）

Plan E 只允许：status flip、command 接线、smoke、manifest promotion。

---

## 9. 执行完成合约（candidate 阶段）

```text
EXEC_STATUS: completed_candidate
SEGMENT: 6.5-B
GD_STAGE: plan_6.5_b_candidate（不是 /gd 命令输出）
MANIFEST_VERSION: 1.2.1（未变；A-D 期间不动 manifest；Plan E 一次性 1.4.0）
ACTIVE_BOUNDARY: Plan 1-5 v5（Plan 6 v3 deprecated；Plan 6.5-A APPROVED；Plan 6.5-B candidate）
FILES_MODIFIED: 2（prompts/gd-review-standard.md / scripts/gd-codex-review.py 头注释）
FILES_ADDED: 14（1 wrapper + 10 fixtures + 3 reports + start.marker）
ACTIVE_FILES_TOUCHED: 0（commands/gd.md / docs / manifest / 2 templates 全部 hash 未变）
NO_WRITE_AUDIT: ~/.claude/** attributable_count=0
SELF_TEST: 15/15 PASS
F9_FAIL_CLOSED: ✓ exit 2 + stderr 提示
DOWNSTREAM_GATE: 本段 review APPROVED → 可开 Plan C（child agent orchestration）
```

---

## 10. 下游 Plan 触发条件

| 下游 | 触发条件 |
|------|---------|
| Plan C（child agent）| Plan B code review APPROVED；C 用 B 定义的 Claude self-review + Codex bridge 角色 |
| Plan D（install 解冻）| A+B+C 全 APPROVED + 用户明确授权 |
| Plan E（端到端 smoke + manifest 1.4.0）| D 通过 + smoke 全过 |
