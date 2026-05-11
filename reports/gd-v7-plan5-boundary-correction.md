# Plan 5 Boundary Correction 报告

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
GENERATED_AT: 2026-05-11T05:00:00Z
MANIFEST_VERSION: 1.1.1

---

## 1. 问题说明

Plan 5 v2 执行时，将 `/gd execute` 的 `CAPABILITY_STATUS` 从 `pending_future_plan` 升级为 `local_only`，并在 `manifest.gd-v7.json` 写入 `revisions[1.2.0]`。但 Plan 5 存在以下语义缺陷，不满足正式执行标准：

1. **validator 无 deliverable truth 验证**：`gd-validate-execution-batch.py` 只检查 JSON 结构，不验证 `deliverables_produced` 路径是否实际存在
2. **validator 无 wave membership 验证**：不检查 batch 中的 task 是否属于 dispatch map 声明的 wave
3. **validator 无 closure recomputation**：closure report 的 aggregation 字段由 agent 手填，不从 batch 结果重新计算

因此，Plan 5 v2 的所有"执行状态声明"被判定为 `draft_not_executed`，需要回收对主动边界的污染。

---

## 2. 回收范围

### 2.1 主动状态回收（已执行）

| 文件 | 回收内容 | 操作 |
|------|---------|------|
| `commands/gd.md` | `/gd execute` CAPABILITY_STATUS `local_only` → `pending_future_plan` | 已修改 |
| `docs/gd-v7-claude-command.md` | 状态说明同步回 Plan 4 | 已修改 |
| `templates/gd-execution-result-template.md` | 移除 §8 machine-readable JSON 块 + §9 machine-readable checkbox | 已修改 |
| `docs/gd-v7-shared-core-index.md` | §7 从主动状态降级为 Pending Draft 节 | 已修改 |
| `scripts/gd-validate-execution-batch.py` | 追加 DRAFT header | 已修改 |
| `manifest.gd-v7.json` | retract 1.2.0；新建 1.1.1 active tail；移除 execution_dispatch_artifacts + modify_in_plan_5；新增 pending_drafts | 已修改 |

### 2.2 Plan 5 draft artifacts（保留，不删除）

以下 18 个文件保留为 `draft_not_executed` 状态，见 `manifest.gd-v7.json` `pending_drafts.plan_5_execution_dispatch`：

```
docs/gd-v7-execution-dispatch.md
templates/gd-execution-batch-template.md
templates/gd-execution-closure-report-template.md
schema/gd-execution-batch.schema.json
schema/gd-execution-closure-report.schema.json
scripts/gd-validate-execution-batch.py（DRAFT header 已追加）
fixtures/execution-batch/valid-batch.json
fixtures/execution-batch/missing-verify-invalid.json
fixtures/execution-batch/skipped-no-reason-invalid.json
fixtures/execution-batch/status-mismatch-invalid.json
fixtures/execution-batch/json-block-missing-invalid.json
fixtures/execution-batch/json-block-duplicate-invalid.json
fixtures/execution-batch/path-traversal-invalid.json
fixtures/execution-batch/task-id-mismatch-invalid.json
fixtures/execution-results/valid-closure.json
fixtures/execution-results/failed-no-next-action-invalid.json
reports/gd-v7-execution-dispatch.md
reports/gd-v7-execution-dispatch.start.marker
```

---

## 3. Hash Drift 记录（revisions[1.1.1]）

| 文件 | before_hash（Plan 5 草稿后） | after_hash（回收后） | 说明 |
|------|---------------------------|---------------------|------|
| `manifest.gd-v7.json` | `ae13d48b5441eebba7f2b1e3a9dea21048905d53d29f8b7d8ac7fb92c58c60d3` | `2278b00d9a73a494e8e73ed623f83a8a50242aa15fa060d31fec6e5b69e5b2b0` | 版本 1.1.1；retract 1.2.0 |
| `commands/gd.md` | `a5683c2d9d5ed57dff6df261c7bb93d54aa02c1b31180128bbd0fb8f729b1745` | `d78767506459b6724e8092e844e83791ff3cf6594d1bd9482130ed39035df4b7` | /gd execute → pending_future_plan |
| `docs/gd-v7-claude-command.md` | `4ff74147ef5d2e9ba9b9f7559d689cfa78df0bf569b6a00819ce631b6d9371d2` | `a2e42fd421080dbc5ca9c8226eb7d2b60d92dab3b013fc67de7d830b78545b82` | 状态同步到 Plan 4 |
| `templates/gd-execution-result-template.md` | `b6ec6f37cd6ee259720c7848b1937a844c1c947dcf035b12a1e2514c128ac18f` | `2450c8522918b4a6f95ad9a01433a0a09b6e1ce0bf5e7ecc043f806cae716385` | §8 移除；after_hash prefix 与 Plan 2 baseline 一致 ✓ |
| `docs/gd-v7-shared-core-index.md` | `f6c42f7f0ebb90a21eaff613cc84653d22b26a8609c10d32fc9dbdcfcff85a55` | `dd1ea1de065c86b549c2cbedb3f0101c538cfb0dc085d7d53feece334c6c2571` | §7 降级 Pending Draft |
| `scripts/gd-validate-execution-batch.py` | `b245f0d989f40ab33469c876d644336710c1d7ec2b4d70306518a858d65612b4` | `ab2844cc94af159ced7489daed19d2e551d818330a2a6e80e83117f7c5adf9e0` | DRAFT header 追加 |

**关键验证**：`templates/gd-execution-result-template.md` after_hash prefix `2450c852...` 与 Plan 5 `revisions[1.2.0].before_hash` 前缀完全一致，证明 §8 移除成功恢复 Plan 2 baseline。

---

## 4. Review Baseline 说明

- 末次 review baseline：`result-20260511T044154Z.md`（baseline-key `960d31368ac0`）
- 该 review 审核的是 Plan 5 草稿状态（commands/gd.md 含 `local_only`），不代表正式 Plan 5 执行认可
- 本 correction 完成后，`commands/gd.md` 已回退；该 baseline 记录的是已回收状态，**不得作为 Plan 5 正式 APPROVED 依据**

---

## 5. 当前主动边界

| Plan | 状态 | manifest revision |
|------|------|-------------------|
| Plan 1（baseline + ledger） | `completed` | — |
| Plan 2（shared core） | `completed` | initial |
| Plan 3（/gd scaffold） | `completed` | initial |
| Plan 4（dispatch） | `completed` | `revisions[1.1.0]` |
| Plan 5（execution dispatch） | `draft_not_executed` | `revisions[1.2.0]` **retracted** |
| 本次修正 | `completed` | `revisions[1.1.1]` active tail |

---

## 6. 未改变的文件

以下文件未被本次 correction 修改（Plan 4 active artifacts 均无影响）：

- `docs/gd-v7-multi-agent-dispatch.md`（Plan 4 owned，未修改）
- `scripts/gd-validate-dispatch.py`（Plan 4 owned，未修改）
- `fixtures/dispatch/*.json`（Plan 4 owned，未修改）
- `/Users/praise/.claude/**`（从未写入）
- 除本次修正明确列出的 `commands/gd.md` 与 `docs/gd-v7-claude-command.md` 外，其余 Plan 1-3 artifact 未修改（`bin/rev`、`prompts/rev-review-standard.md`、`templates/plan-template.md`、`templates/execution-result-template.md`、`schema/rev-baseline.schema.json`、`manifest.json` diff 均为空）

---

## 7. 执行完成合约

```text
EXEC_STATUS: completed
GD_STAGE: boundary_correction（不是 /gd 命令输出）
MANIFEST_VERSION: 1.1.1
ACTIVE_BOUNDARY: Plan 1-4（Plan 5 = draft_not_executed）
FILES_MODIFIED: 6
NO_WRITE_AUDIT: ~/.claude/** 未写入（无 phase_attributable 写入）
CORRECTION_SC: 6/6 pass（见 §3 hash drift 记录）
```

---

## 8. 验收命令与结果摘要

### 8.1 Manifest JSON 校验

```bash
python3 -m json.tool manifest.gd-v7.json > /dev/null && echo JSON_PASS
```
结果：`JSON_PASS`

### 8.2 /gd install / parity / uninstall

```bash
bash scripts/check-gd-command-parity.sh
```
结果：`INSTALL_STATUS: not_installed`

```bash
bash scripts/install-gd-command.sh
```
结果：`INSTALL_STATUS: install_pending_authorization`（ledger 缺 scope=install_claude_command；正确：未安装）

```bash
bash scripts/uninstall-gd-command.sh
```
结果：`UNINSTALL_STATUS: not_installed`（target 不存在，无需操作）

### 8.3 dispatch fixtures exit code

```bash
python3 scripts/gd-validate-dispatch.py fixtures/dispatch/valid-dispatch.json
# 结果：校验通过：dispatch_id=valid-fixture, tracks=3, waves=2  exit:0

for f in fixtures/dispatch/*-invalid.json; do
  python3 scripts/gd-validate-dispatch.py "$f" > /dev/null 2>&1
  code=$?; name="${f##*/}"; echo "$name: exit $code"
done
```

| fixture | 预期 | 实测 |
|---------|------|------|
| `valid-dispatch.json` | 0 | **0** ✓ |
| `parallel-overlap-invalid.json` | 1 | **1** ✓ |
| `missing-context-invalid.json` | 1 | **1** ✓ |
| `dependency-parallel-conflict-invalid.json` | 1 | **1** ✓ |
| `wave-unknown-track-invalid.json` | 1 | **1** ✓ |
| `wave-nonparallel-invalid.json` | 1 | **1** ✓ |
| `wave-dependency-order-invalid.json` | 1 | **1** ✓ |
| `sc-verify-mismatch-invalid.json` | 1 | **1** ✓ |

全部 8/8 与预期一致。汇总：valid-dispatch:0 ✓，7 个 invalid fixture: exit 1 ✓

### 8.4 裸 `VERDICT:` 检查

```bash
rg -n "^VERDICT:" commands/gd.md docs/gd-v7-claude-command.md templates/ schema/ scripts/
```
结果：**无命中**（返回非零退出码，无输出）

### 8.5 旧 /rev 核心文件 diff

```bash
git diff HEAD -- bin/rev prompts/rev-review-standard.md \
  templates/plan-template.md templates/execution-result-template.md \
  schema/rev-baseline.schema.json manifest.json
```
结果：**diff 为空**，所有旧 `/rev` 文件未被本次修正触及。

### 8.6 `templates/gd-execution-result-template.md` 关键词检查

```python
t = open('templates/gd-execution-result-template.md').read()
for kw in ['gd-execution-status-json', 'machine-readable', 'Plan 5 Patch']:
    print(kw, ':', t.count(kw))
```
结果：三个关键词均 **0 次**，确认 §8 machine-readable 块已移除。

### 8.7 最终 code review 状态

**未执行最终 `/review code`（code review: not_run）。**

原因：本次变更全部为 Markdown / JSON / Python 注释行修改，无可执行逻辑变更；8.1-8.6 验收命令全部 pass；v4 计划明确标注"boundary correction 改的是配置/文档/manifest，/review code 可选"。

**由此声明**：本报告为 *boundary correction 完成记录*，不能作为完整 code review APPROVED 声明。如需正式 code review 覆盖本次修改，须单独在会话中运行 `review` skill。
