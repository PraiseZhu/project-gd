# /gd Command Changelog

## rev22（2026-06-09）— execute agent_exec live（rev21 架构复用）

**变更范围**：`commands/gd.md`、`scripts/gd-validate-execution-batch.py`、`CLAUDE.md`（三档表新增）、`docs/gd-changelog.md`（本文件新建）

### 核心变更

1. **`/gd execute` agent_exec 子 agent 化已实装**（SC-1/SC-2/SC-3/SC-4）
   - execute 段从 `human_exec only + agent_exec pending_future_plan` 改写为 agent_exec 主模式
   - 复用 rev21 现有资产（**0 个新建脚本**）：`gd-validate-stage-dispatch-ledger.py`(stage=execute) + `gd-validate-controller-report.py` + `gd-validate-execution-batch.py` + `gd-child-execute-prompt-template.md`
   - 执行流：capability probe → fail-closed（unavailable/unknown → exit 1，不降级） → 按 wave 派 1-2 child executor → post-wave path audit → write stage-dispatch-ledger(stage=execute) + controller-report → 双 validator exit 0 才 closure-eligible
   - **execute 段不引入以下任一字样**（明确禁止）：`gd-build-child-prompt.py` / `gd-detect-path-changes.py` / `gd-validate-execution-dispatch-ledger.py` / `execution_dispatch_ledger`

2. **batch validator 解除 `agent_exec` PENDING 拒绝**（SC-2）
   - `_CLOSURE_INELIGIBLE_MODES = {"agent_exec", "dry_run"}` → `{"dry_run"}`（agent_exec 已实装，仅 dry_run 仍 pending）

3. **capability fail-closed**（SC-3）
   - capability `unavailable / unknown` → exit 1（`CAPABILITY_UNAVAILABLE_AGENT_EXEC`），不静默降级 human_exec
   - child_agent_count=0 → `CLOSURE_INELIGIBLE: zero_child_closure`（由 gd-validate-stage-dispatch-ledger.py 兜底）
   - child 写越 owned_paths → batch fail（由 gd-validate-execution-batch.py v5 owned_paths 校验兜底）

4. **human_exec 降为 emergency-only**（SC-4）
   - 不再是默认唯一支持模式
   - 需用户显式 `override: emergency_non_final`
   - 该状态属 `closure_ineligible`（见 commands/gd.md §Mandatory Subagent Stage Contract）

5. **文档收敛**（SC-5）
   - `commands/gd.md` CAPABILITY 表、help 表、Forbidden #9、revision 头（lock_revision=22）统一
   - 项目 `CLAUDE.md` 新增三档表（L1/L2/L3 现装状态）
   - `docs/gd-changelog.md`（本文件）新建

### 不变项（明确）

- 不新建 `gd-build-child-prompt.py` / `gd-detect-path-changes.py` / `gd-validate-execution-dispatch-ledger.py`
- 不引入 `execution_dispatch_ledger`（per-wave 第二套 ledger）；execute 统一用 `stage-dispatch-ledger`(stage-level)
- `dry_run` mode 仍 `pending_future_plan`
- pure code-only Codex sidecar 仍 pending Plan 6

---

## rev21（2026-05-xx）— Four-Stage Mandatory Subagent Contract

四阶段统一横向合同：每阶段必须发 1-2 个子 agent，0 child fail-closed，max_parallel=2 硬上限；closure_ineligible 全量列表扩展；stage dispatch ledger + controller-report 成为 final gate 必须证据；/gd review plan 改为 bounded-parallel；/gd review code 从 pending 改为 review_execution_code alias；fixture_mode/mock_only 显式拒绝；failed_to_run/transport_failed vocabulary 归一；passive gate 退出 production closure 路径。

## rev20（2026-05-xx）— Execution-Review Cross-Review v2

/gd review 对 execution_only_no_code / execution_plus_code target 必须经过三段闭环（outcome validator + Codex bridge kind=execution_outcome/combined + route validator）；缺 Codex result → codex_review_status=transport_failed + REQUIRES_CHANGES。

（rev1-rev19 历史见 `commands/gd.md` description 元数据字段）
