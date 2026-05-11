# Plan 6 v3 Codex Sidecar — Candidate 报告（completed_with_constraint）

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
START_MARKER: reports/gd-v7-plan6-codex-sidecar.start.marker (2026-05-11T08:56:58Z)
GENERATED_AT: 2026-05-11T09:10:00Z
STAGE: candidate（review 前；不写 active state；live smoke 失败 → 必然 completed_with_constraint）
PLAN_VERSION: Plan 6 v3
PRIOR_REVIEWS:
  - Plan 6 v3 followup plan review APPROVED — /Users/praise/.claude/review-baselines/0575daff2583/result-20260511T085433Z.md

---

## 1. 执行结论摘要（先行声明，方便 reviewer 锁住基调）

| 项 | 结果 |
|---|---|
| 基线确认 | manifest=1.2.1 ✓；/gd execute=local_only ✓ |
| 静态产物（runner/schema/templates/fixtures）| 全部完成 ✓ |
| Fixture 验证（5 merge + 6 parse）| 11/11 全过 ✓ |
| **Live Codex smoke** | **failed_to_run**（sandbox 阻 chatgpt.com / mcp.cloudflare.com 出站）|
| 因此 active 升级 | **不执行**（按 plan §8 fail-closed）|
| 候选 manifest revision | 候选 1.3.0 = `completed_with_constraint`，等 final review 决定是否写入 |

**关键约束**：本报告**不**修改 commands/gd.md / docs/gd-v7-claude-command.md / docs/gd-v7-shared-core-index.md / manifest.gd-v7.json 的 active 状态。`/gd review plan` 仍为 `local_only`，`/gd review code` 仍为 `pending_future_plan`。

---

## 2. 修改 / 新增文件清单

### 2.1 修改

| 文件 | before_hash | after_hash | 改动 |
|------|-------------|------------|-----|
| `prompts/gd-review-standard.md` | `37f60ff468a6eca3…` | `f4e0585bdfa7b1aa…` | §8 重写：旧 codex-send-wait/handoff/review-result-writer 依赖删除，改为 Project GD 内部 sidecar runner；新增 §8.1 Merge Matrix 5 行 |
| `schema/gd-review-result.schema.json` | (existing) | `4fe3255f50e472a9…` | 必填字段 + `timestamp`（ISO 8601 UTC pattern）|
| `templates/gd-plan-review-template.md` | `3aa49b0a3f1566fc…` | `32b30e6d4ae536e0…` | 追加 §6 machine-readable JSON block + 填写规则 |
| `templates/gd-execution-review-template.md` | `e0219bf66868ab98…` | `ed8dbbcb59bee4a5…` | 同上（gd-execution-review 模板版本）|

### 2.2 新增

| 文件 | sha256 | 用途 |
|------|--------|------|
| `scripts/gd-codex-review.py` | `39ca14127c5bcc25…` | sidecar runner；4 子命令 build-capsule / run-codex / parse / merge；`--kind plan|code` |
| `fixtures/review-sidecar/claude-approved.json` | `d6a99d5316da142b…` | merge fixture |
| `fixtures/review-sidecar/codex-approved.json` | `46057374e06c49a4…` | merge fixture |
| `fixtures/review-sidecar/codex-requires-changes.json` | `751cc3f3d1f8a93c…` | merge fixture |
| `fixtures/review-sidecar/codex-timeout.json` | `636e277af61e593f…` | merge fixture（failed_to_run 状态）|
| `fixtures/review-sidecar/claude-failed.json` | `46661e51e1a47a25…` | merge fixture（Claude FAILED 场景，响应 Plan 6 v2 F3）|
| `fixtures/review-sidecar/raw-approved.md` | `51c8a6e9c8673a3d…` | parse positive |
| `fixtures/review-sidecar/raw-bare-verdict.md` | `d3312c28098104ea…` | parse negative — 行首裸 `VERDICT:` |
| `fixtures/review-sidecar/raw-rev-verdict.md` | `afcb41baf00365cc…` | parse negative — 行首 `REV_VERDICT:` |
| `fixtures/review-sidecar/raw-missing-json.md` | `8c9ba9daaf9cfb73…` | parse negative — 缺 JSON block |
| `fixtures/review-sidecar/raw-duplicate-json.md` | `366128fb080801b0…` | parse negative — 多 JSON block |
| `fixtures/review-sidecar/raw-schema-fail-missing-sc-refs.md` | `8a8093103ae32421…` | parse negative — finding 缺 sc_refs |
| `reports/gd-v7-plan6-codex-sidecar.start.marker` | — | start marker |
| `reports/gd-v7-plan6-codex-sidecar.before-hashes.txt` | — | before-hash 记录 |
| `reports/gd-v7-plan6-codex-sidecar.after-hashes.txt` | — | after-hash 记录 |
| `reports/plan6-smoke/capsule.md` | — | live smoke capsule |
| `reports/plan6-smoke/codex-raw.md` | — | live smoke 输出（failed_to_run JSON）|

### 2.3 未触动（active state；plan §8 fail-closed 必然如此）

| 文件 | hash（未变） |
|------|-------------|
| `commands/gd.md` | `09e4e4ce08c0e6f8…` |
| `docs/gd-v7-claude-command.md` | `dad0c69a8aeabd6a…` |
| `docs/gd-v7-shared-core-index.md` | `c074671fc9924b69…` |
| `manifest.gd-v7.json` | `45df394dc7a1687d…` |

---

## 3. Sidecar runner 4 子命令实现

| 子命令 | 用途 | 关键行为 |
|--------|------|---------|
| `build-capsule --kind plan|code --target <path> [--out <path>]` | 拼接 review capsule | 按 `--kind` 选择 `gd-plan-review-template.md` 或 `gd-execution-review-template.md`；含 goal chain + standard + template + target |
| `run-codex --capsule <path> [--root <path>] [--timeout <sec>] [--out <path>]` | 调用 codex CLI | `codex exec --ephemeral --sandbox read-only --skip-git-repo-check --cd <root> -`；timeout 默认 240 秒 / `GD_CODEX_TIMEOUT`；FileNotFoundError / TimeoutExpired / non-zero exit 都生成可解析 `failed_to_run` JSON |
| `parse <raw.md> [--kind plan|code] [--out <path>]` | 提取并校验 JSON block | 拒绝裸 `VERDICT:` / `REV_VERDICT:`；要求恰好一个 `gd-review-result-json` block；schema 校验；`--kind` 与 JSON `review_kind` 字段比对 |
| `merge <claude.json> <codex.json>` | 合并两份 review JSON | 任一 schema fail → matrix #5 → FAILED；矩阵优先级 #3 (FAILED) > #5 (parse fail) > #2 (REQUIRES_CHANGES) > #4 (degraded → REQUIRES_CHANGES + completed_with_constraint) > #1 (全 APPROVED) |

`--kind plan|code` 在 build-capsule 与 parse 都可用，吸收 review P3 提示 #1。

---

## 4. Fixture 验证全表

### 4.1 parse fixtures (positive 1 + negative 5)

| fixture | 类别 | 期望 | 实测 |
|---------|------|------|------|
| `raw-approved.md` | positive | exit 0 | **0** ✓ |
| `raw-bare-verdict.md` | parse negative | exit 1 | **1** ✓ |
| `raw-rev-verdict.md` | parse negative | exit 1 | **1** ✓ |
| `raw-missing-json.md` | parse negative | exit 1 | **1** ✓ |
| `raw-duplicate-json.md` | parse negative | exit 1 | **1** ✓ |
| `raw-schema-fail-missing-sc-refs.md` | schema negative | exit 1 | **1** ✓ |

### 4.2 merge fixtures (5 cases)

| claude | codex | 期望 merged_decision | 期望 exit | 实测 |
|--------|-------|---------------------|-----------|------|
| approved | approved | APPROVED | 0 | **APPROVED, exit 0** ✓ |
| approved | requires_changes | REQUIRES_CHANGES | 0 | **REQUIRES_CHANGES, exit 0** ✓ |
| approved | timeout | not APPROVED (FAILED) | 1 | **FAILED, exit 1** ✓ |
| failed | approved | FAILED | 1 | **FAILED, exit 1** ✓ |
| failed | requires_changes | FAILED | 1 | **FAILED, exit 1** ✓ |

11/11 全部通过。

---

## 5. Live Codex smoke 结果

### 5.1 命令

```bash
python3 scripts/gd-codex-review.py build-capsule --kind plan \
  --target fixtures/plans/phase2-good-plan.md \
  --out reports/plan6-smoke/capsule.md
# capsule 472 行 ✓

python3 scripts/gd-codex-review.py run-codex \
  --capsule reports/plan6-smoke/capsule.md --timeout 180 \
  --out reports/plan6-smoke/codex-raw.md
# exit 0（runner 自身正常运作；codex CLI 自身失败被捕获为 failed_to_run JSON）

python3 scripts/gd-codex-review.py parse \
  reports/plan6-smoke/codex-raw.md --kind plan
# exit 1（PARSE_FAIL: 缺 gd-review-result-json block — 因为 codex 失败时输出的是 JSON 不是 markdown）
```

### 5.2 Codex CLI 失败原因

直接调 `codex exec --ephemeral --sandbox read-only --skip-git-repo-check -` 报：

```
ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed,
  Client(HttpRequest("https://mcp.cloudflare.com/mcp"))
ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket:
  Proxy connection failed: HTTP CONNECT failed with status 403,
  url: wss://chatgpt.com/backend-api/codex/responses
```

**根因**：当前 sandbox 网络白名单不含 `chatgpt.com` / `mcp.cloudflare.com`。Codex CLI 物理无法跑通。

### 5.3 Runner 失败处理验证

`run-codex` 子命令正确捕获 codex non-zero exit，生成可解析 `failed_to_run` JSON：

```json
{
  "template_kind": "gd-plan-review",
  "reviewer": "codex",
  "review_target": "reports/plan6-smoke/capsule.md",
  "review_kind": "plan",
  "review_run_status": "failed_to_run",
  "gd_review_decision": "FAILED",
  "scope_checked": [{"facet": "sidecar runtime", "result": "fail",
                     "evidence": "codex non-zero exit 1: ... ERROR rmc..."}],
  "merge_notes": {"degraded_reason": "codex non-zero exit 1: ..."},
  "timestamp": "2026-05-11T09:04:31Z"
}
```

这是 fail-closed 设计的正确表现：codex 不可用 → 产生 FAILED + failed_to_run，**不**让上游误以为 reviewer 通过。

---

## 6. Active promotion 决策

按 Plan 6 v3 §8：
> active 条件：fixtures 全 pass + **live smoke 可解析** + no-write audit pass + command/docs 状态一致
> 如果 Codex CLI 不可用，只能记录 completed_with_constraint，不得把两个 review stage 标 active

| 条件 | 满足? |
|------|------|
| fixtures 全 pass | ✓ (11/11) |
| live smoke 可解析 | ✗ (sandbox 阻外网) |
| no-write audit | ✓ (无 attributable 写入) |
| command/docs 状态一致 | ✓ (未触动) |

**因此本轮不执行 active promotion**：
- `commands/gd.md` `/gd review plan` 保持 `local_only`，`/gd review code` 保持 `pending_future_plan`
- `docs/gd-v7-claude-command.md` 不动
- `docs/gd-v7-shared-core-index.md` 不动
- `manifest.gd-v7.json` 不写 `1.3.0` active；候选 1.3.0 在本报告 §7 列出，等 final review 决定

---

## 7. 候选 manifest 1.3.0（completed_with_constraint，待 final review 决定）

```json
{
  "version": "1.3.0",
  "applied_at": "<promotion 时刻>",
  "owner_step": "Plan 6 v3 (constrained)",
  "status": "completed_with_constraint",
  "constraint_reason": "Codex CLI 在执行环境 sandbox 中无法连接 chatgpt.com / mcp.cloudflare.com（HTTP 403）；live smoke 失败；按 Plan 6 v3 §8 fail-closed 不升级 /gd review plan/code 为 active",
  "supersedes": [],
  "added_artifacts": [
    "scripts/gd-codex-review.py",
    "fixtures/review-sidecar/* (11 文件)",
    "reports/gd-v7-plan6-codex-sidecar-review.md",
    "reports/plan6-smoke/* (capsule.md, codex-raw.md)"
  ],
  "modified_artifacts": [
    "prompts/gd-review-standard.md (§8 重写 + §8.1 Merge Matrix)",
    "schema/gd-review-result.schema.json (timestamp 字段)",
    "templates/gd-plan-review-template.md (§6 JSON block)",
    "templates/gd-execution-review-template.md (§6 JSON block)"
  ],
  "active_promotion_blocked_by": "live_codex_smoke_failed_to_run",
  "next_action": "在网络可达 chatgpt.com / mcp.cloudflare.com 的环境下重跑 step 5 live smoke；smoke 通过后再 promotion /gd review plan + /gd review code 为 active + REVIEW_MODE: claude_plus_codex",
  "fixtures_passed": "11/11 (5 merge + 6 parse)",
  "no_write_audit": "~/.claude/** attributable_count=0",
  "old_chain_audit": "新代码无 codex-send-wait/review-result-writer/handoff 引用；旧 reports 内有历史 audit 记录不算 attributable"
}
```

---

## 8. Old handoff residue audit

```bash
grep -rEn "codex-send-wait|review-result-writer|rev-result-writer|~/\.claude/handoff" \
  prompts templates schema commands scripts docs reports
```

排除 `gd-review-standard.md` 的"禁止"声明文本与 `fixtures/review-sidecar/` 后：
- `reports/source-hashes.json` — 历史 boundary 文档 (Plan 1 baseline 记录旧链路位置)
- `reports/gd-v7-execution-dispatch.md` — Plan 5 v2 草稿报告（本身记录 audit 范围）
- `reports/phase-1-template-setup.md` — 旧 /rev Phase 1 报告（V5 audit 行）
- `reports/gd-v7-boundary-baseline.md` — Plan 1 boundary 记录（标注旧链路位置）
- `reports/phase-3-execution-conformance.md` — 旧 /rev Phase 3 报告（rev-result-writer.sh 描述）
- `reports/phase-2-runner-baseline.md` — 旧 /rev Phase 2 报告（rev-result-writer.sh 描述）

**全部为历史 reports 记录文本，非新代码引用**。Plan 6 v3 新代码（runner / schema / templates / fixtures）零引用。

---

## 9. no-write audit (~/.claude/**)

```bash
find ~/.claude/{commands,handoff,scripts/hooks,review-baselines,state} \
  -newer reports/gd-v7-plan6-codex-sidecar.start.marker -type f
```

去除 review-baselines/0575daff2583/* 与 heartbeat 后：
- `state/review-chain-verify/touched/<sessionId>.json` — 由前次 `/review` 命令写入

**Plan 6 v3 attributable_count = 0**。

---

## 10. 旧链路检查（commands/gd.md / 旧 /review / 旧 /rev / codex-watch）

| 检查 | 结果 |
|------|------|
| 旧 `/review` 链路 | 未调用 |
| 旧 `/rev` 链路 | 未调用 |
| `codex-watch` daemon | 未调用 |
| `codex-send-wait` | 未调用 |
| `review-result-writer.sh` | 未调用（注：本报告生成走 `/review code` skill，是 Claude Code 内置 review chain，不是 /gd 命令链路）|

---

## 11. 执行完成合约（candidate 阶段）

```text
EXEC_STATUS: completed_with_constraint
GD_STAGE: plan_6_v3_candidate（不是 /gd 命令输出）
MANIFEST_VERSION: 1.2.1（未变；候选 1.3.0 待 final review 决定）
ACTIVE_BOUNDARY: Plan 1-5 v5（Plan 6 v3 candidate；review stage 未升级）
FILES_MODIFIED: 4 (gd-review-standard.md / gd-review-result.schema.json / 2 templates)
FILES_ADDED: 12 (1 runner + 11 fixtures + smoke capsule + reports)
ACTIVE_FILES_TOUCHED: 0 (commands/gd.md / docs / manifest 全部 hash 未变)
NO_WRITE_AUDIT: ~/.claude/** attributable_count=0
FIXTURE_PASS: 11/11 (1 positive parse + 5 negative parse + 5 merge)
LIVE_SMOKE: failed_to_run (sandbox 阻外网；runner fail-closed 行为正确)
NEXT_STEP: final /review code gate；reviewer 决定 (a) constrained 收口接受候选 1.3.0 / (b) 等 sandbox 解锁后重跑 smoke 再 active promotion
```

---

## 12. final review gate 要求

提交 final `/review code` 时，capsule 必须包含：
- §2 改动文件清单 + before/after hash
- §3 sidecar runner 4 子命令实现
- §4 11/11 fixture 验证表
- §5 live smoke 失败实证 + runner fail-closed 验证
- §6 active promotion 决策（必然 not-active）
- §8-§10 三类 audit
- §11 完成合约
