# Plan 5 v5 Execution Dispatch — Candidate 报告

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
START_MARKER: reports/gd-v7-execution-dispatch-v5.start.marker (2026-05-11T07:33:35Z)
GENERATED_AT: 2026-05-11T07:50:00Z
STAGE: candidate（review 前；不写 active state）
PLAN_VERSION: Plan 5 v5
PRIOR_REVIEW_RESULT: APPROVED (followup) — /Users/praise/.claude/review-baselines/0575daff2583/result-20260511T065615Z.md

---

## 1. 范围与原则

本报告记录 Plan 5 v5 §1-§5 的产出。**§7 final promotion（commands/gd.md / docs / manifest 1.2.1 active）尚未执行**，必须等本报告通过 final `/review code` gate 后才能写入。

v5 在 v4 基础上的两项核心修复：
1. positive fixture 与 dispatch 强绑定（响应 v4 F1）
2. active state 写入推迟到 final review pass 后（响应 v4 F2）

---

## 2. 已修改/新增文件清单

### 2.1 修改

| 文件 | before_hash | after_hash | 改动摘要 |
|------|-------------|------------|---------|
| `scripts/gd-validate-execution-batch.py` | `ab2844cc94af159c…` | `86261d0e86342923…` | 头注释更新；新增 v5 4 类语义校验函数；main 调用 |
| `fixtures/execution-batch/valid-batch.json` | `1e9373dc34bb4163…` | `b454a42ba8d8ac29…` | task_results 覆盖 t1+t2；produced path = dispatch deliverable path；verify cmd 与 dispatch 对齐 |
| `fixtures/execution-results/valid-closure.json` | `1d9d94f8160eeca3…` | `6522158798f35ef1…` | track_results 覆盖 t1+t2 |

### 2.2 新增

| 文件 | sha256 | 用途 |
|------|--------|------|
| `fixtures/dispatch/_workdir/t1/result.json` | `1d3cbca5b11e6ab2…` | 物理 deliverable for t1 |
| `fixtures/dispatch/_workdir/t2/result.json` | `e2d76ab5d0186029…` | 物理 deliverable for t2 |
| `fixtures/execution-batch/wave-membership-missing-invalid.json` | `5070009acd29cae5…` | v5 校验 1 negative fixture |
| `fixtures/execution-batch/deliverable-path-mismatch-invalid.json` | `ef26b694a68a697b…` | v5 校验 2 negative fixture |
| `fixtures/execution-batch/deliverable-missing-file-invalid.json` | `27a3bca0751d108d…` | v5 校验 4 negative fixture |
| `fixtures/execution-batch/deliverable-outside-owned-path-invalid.json` | `ac7c19c9cd22cbc7…` | v5 校验 3 negative fixture |
| `reports/gd-v7-execution-dispatch-v5.start.marker` | — | start marker for audit |
| `reports/gd-v7-execution-dispatch-v5.before-hashes.txt` | — | before-hash 记录 |
| `reports/gd-v7-execution-dispatch-v5.after-hashes.txt` | — | after-hash 记录 |
| `reports/gd-v7-execution-dispatch-v5.md` | — | 本报告 |

### 2.3 未触动（active state；§7 待执行）

| 文件 | hash（未变） |
|------|-------------|
| `commands/gd.md` | `d78767506459b672…` |
| `docs/gd-v7-claude-command.md` | `a2e42fd421080dbc…` |
| `docs/gd-v7-shared-core-index.md` | `dd1ea1de065c86b5…` |
| `manifest.gd-v7.json` | `2278b00d9a73a494…` |

---

## 3. validator v5 语义覆盖矩阵

| # | 语义 | 实现函数 | 覆盖 negative fixture |
|---|------|---------|---------------------|
| 1 | wave membership：`set(task_results.track_ref) == set(wave.track_ids)` | `check_v5_wave_membership` | `wave-membership-missing-invalid.json` |
| 2 | deliverable truth：dispatch must_exist=true 必须在 deliverables_produced 中且 verified=true | `check_v5_deliverable_and_path`（部分）| `deliverable-path-mismatch-invalid.json` |
| 3 | owned_paths containment：produced path 必须在对应 track owned_paths 内 | `check_v5_deliverable_and_path`（部分）| `deliverable-outside-owned-path-invalid.json` |
| 4 | physical existence：verified=true 时 produced path 必须实际存在（cwd-relative）| `check_v5_deliverable_and_path`（部分）| `deliverable-missing-file-invalid.json` |

---

## 4. fixture exit code 全表

### 4.1 positive

| fixture | 命令 | 预期 | 实测 |
|---------|------|------|------|
| `valid-batch.json` | `python3 scripts/gd-validate-execution-batch.py fixtures/execution-batch/valid-batch.json fixtures/dispatch/valid-dispatch.json` | 0 | **0** ✓ |
| `valid-closure.json` | `python3 scripts/gd-validate-execution-batch.py --closure fixtures/execution-results/valid-closure.json` | 0 | **0** ✓ |

### 4.2 negative（11 个 batch + 1 个 closure，全部 exit 1）

| fixture | 类别 | 实测 |
|---------|------|------|
| `wave-membership-missing-invalid.json` | v5 校验 1 | **1** ✓ |
| `deliverable-path-mismatch-invalid.json` | v5 校验 2 | **1** ✓ |
| `deliverable-missing-file-invalid.json` | v5 校验 4 | **1** ✓ |
| `deliverable-outside-owned-path-invalid.json` | v5 校验 3 | **1** ✓ |
| `json-block-duplicate-invalid.json` | v2 既有 | **1** ✓ |
| `json-block-missing-invalid.json` | v2 既有 | **1** ✓ |
| `missing-verify-invalid.json` | v2 既有 | **1** ✓ |
| `path-traversal-invalid.json` | v2 既有 | **1** ✓ |
| `skipped-no-reason-invalid.json` | v2 既有 | **1** ✓ |
| `status-mismatch-invalid.json` | v2 既有 | **1** ✓ |
| `task-id-mismatch-invalid.json` | v2 既有 | **1** ✓ |
| `failed-no-next-action-invalid.json` | v2 closure | **1** ✓ |

12/12 与预期一致。v2 既有 fixtures 在 v5 validator 下 cascade 行为正确，无 false-pass。

### 4.3 v5 fixture reject 理由精细化校验

每个 v5 fixture 触发的实际 reject 包含对应的 v5 prefix 字符串：

```
wave-membership-missing → "v5 wave membership: wave='w1' 缺 task_results 覆盖 tracks ['t2']"
deliverable-path-mismatch → "v5 deliverable truth: ... 缺 dispatch required deliverable"
                          + "v5 physical existence: ... wrong-name.json ... 物理文件/目录不存在"
deliverable-missing-file  → "v5 physical existence: ... does-not-exist.json ... 物理文件/目录不存在"
deliverable-outside-owned-path → "v5 owned_paths: ... 不在 track='t1' owned_paths"
```

---

## 5. final promotion candidate（仅在 final review pass 后应用）

### 5.1 commands/gd.md

CAPABILITY_STATUS 表第 4 行：
- 当前：`| /gd execute | pending_future_plan | 属 Plan 5 实现；当前阶段不做 |`
- 升级为：`| /gd execute | local_only | Plan 5 v5 已上线本地 human_exec 闭环：batch + closure validator |`

`/gd execute` Stage 行为段落：替换"Plan 4 阶段"pending 描述为"Plan 5 v5 阶段"local_only 行为，引用 `scripts/gd-validate-execution-batch.py` + `templates/gd-execution-batch-template.md` + `templates/gd-execution-closure-report-template.md` + 4 个新 fixture。

### 5.2 docs/gd-v7-claude-command.md

同步 `/gd execute` 状态到 `local_only`，标注 owner Plan = Plan 5 v5。

### 5.3 docs/gd-v7-shared-core-index.md

§7 标题与正文：
- 当前：`## 7. Plan 5 execution dispatch — 待执行草稿（v1.2.0 已回收）` + ⚠ PENDING DRAFT
- 升级为：`## 7. Plan 5 v5 execution dispatch（v1.2.1 active）`，列出 active artifacts（validator + 模板 + fixtures + 报告）。

### 5.4 manifest.gd-v7.json

- `version`：`1.1.1` → `1.2.1`
- `revisions[1.2.0]`：保持 `status: retracted`，**不变**
- 追加 `revisions[1.2.1]`：
  - `applied_at`：promotion 时刻 ISO 8601
  - `owner_step`：`Plan 5 v5`
  - `before_hash` / `after_hash`：基于本报告 §2 的 hash 表 + promotion 时新写文件
  - `superseded_revisions`: `["1.2.0"]`
- 追加 `pending_drafts.plan_5_execution_dispatch.superseded_by`: `"1.2.1"` + `promoted_with_fixes: true`（保留原 18 个 draft 路径作为审计轨）
- 追加顶层 `execution_dispatch_artifacts`（v5 active 集合）

### 5.5 promotion 后立即跑的 consistency smoke

```bash
python3 -m json.tool manifest.gd-v7.json >/dev/null
grep -q "/gd execute.*local_only" commands/gd.md
python3 scripts/gd-validate-execution-batch.py fixtures/execution-batch/valid-batch.json fixtures/dispatch/valid-dispatch.json
for f in fixtures/execution-batch/*-invalid.json; do
  python3 scripts/gd-validate-execution-batch.py "$f" fixtures/dispatch/valid-dispatch.json >/dev/null 2>&1 || true
  test $? -eq 1
done
```

---

## 6. no-write audit

```bash
find /Users/praise/.claude/{commands,review-baselines,state,handoff,scripts/hooks} \
  -newer reports/gd-v7-execution-dispatch-v5.start.marker -type f 2>/dev/null \
  | grep -v review-baselines/0575daff2583/ | grep -v heartbeat
```

结果：
- `state/review-chain-verify/touched/bc744b19-...json` — 由前次 `/review code`（plan 5 v5 plan review）写入；**非 Plan 5 v5 execution 归因**
- 无 commands/、handoff/、hooks/ 写入
- review-baselines/0575daff2583/ 下的 plan review capsule + result 是 review chain 正常产物

**结论**：Plan 5 v5 execution（§1-§5）对 `/Users/praise/.claude/**` 的 attributable_count = 0。

---

## 7. 旧 /rev 与裸 VERDICT 检查

```bash
grep -REn "^VERDICT:" commands/ docs/ templates/ schema/ scripts/ 2>/dev/null
# 0 命中（exit 1）✓

git diff HEAD -- bin/rev prompts/rev-review-standard.md \
  templates/plan-template.md templates/execution-result-template.md \
  schema/rev-baseline.schema.json manifest.json
# 待 final review 后再核（candidate 阶段不动旧 /rev artifact）
```

---

## 8. 当前主动边界（未变；§7 之前必然如此）

| Plan | 状态 | manifest version |
|------|------|------------------|
| Plan 1（baseline + ledger）| `completed` | — |
| Plan 2（shared core）| `completed` | initial |
| Plan 3（/gd scaffold）| `completed` | initial |
| Plan 4（dispatch）| `completed` | `revisions[1.1.0]` |
| boundary correction | `completed` | `revisions[1.1.1]` active tail |
| **Plan 5 v5 candidate** | **`candidate_pending_review`** | **未写入；候选 `1.2.1` 待 final review pass** |

---

## 9. 执行完成合约（candidate 阶段）

```text
EXEC_STATUS: completed_candidate
GD_STAGE: plan_5_v5_candidate（不是 /gd 命令输出）
MANIFEST_VERSION: 1.1.1（未变；候选 1.2.1 待 promotion）
ACTIVE_BOUNDARY: Plan 1-4 + boundary correction（Plan 5 v5 仍 candidate）
FILES_MODIFIED: 1 (validator)
FILES_ADDED: 9 (2 _workdir + 4 negative fixture + 3 report artifacts)
ACTIVE_FILES_TOUCHED: 0 (commands/gd.md / docs / manifest 全部 hash 未变)
NO_WRITE_AUDIT: ~/.claude/** attributable_count=0
FIXTURE_PASS: 12/12（2 positive exit 0 + 10 negative exit 1）
NEXT_STEP: final /review code gate（pass 后执行 §5 promotion + smoke；fail 则保留 candidate）
```

---

## 10. final review gate 要求

提交 final `/review code` 时，capsule 必须包含：
- validator diff（`scripts/gd-validate-execution-batch.py` before/after）
- positive + negative fixture 输出
- §5 final promotion candidate 详细文本
- §6 no-write audit 三层计数
- 本报告 §3 v5 语义覆盖矩阵

review FAILED / REQUIRES_CHANGES → §7 不执行，本报告保留为 candidate；`/gd execute` 保持 `pending_future_plan`，manifest 不新增 `1.2.1`。
