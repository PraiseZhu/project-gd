# Plan: Project GD 最后一轮成品修复 v2

## Summary

目标不变：把 Project GD `/gd` 修成可直接在真实项目手测的成品。  
不新增"测试阶段再上线"。脚本只作为产品入口、安装入口、parity 入口和防漏执行护栏。

核心链路不变：

```text
/gd plan
  -> /gd review plan
  -> /gd execute
  -> /gd review execution/code
  -> final gate
```

核心机制不变：

- 每个环节必须派 child agent。
- `child_agent_count` 只能是 `1` 或 `2`。
- `max_parallel=2` 是硬上限。
- 并行必须由总计划的 DAG/wave 判断产生。
- 串行步骤按顺序推进，不能硬凑 2 个 agent。
- 主 agent 只调度、记录、合并、验门禁，不能包办 child agent 任务。
- Codex 是 cross-review sidecar，不是唯一裁判。

## Key Decisions

### Q1: DAG/wave 谁判断

使用现有 Project GD dispatch map 机制，不新增一套 DAG 引擎。

- `schema/gd-dispatch-map.schema.json` 是 dispatch map 结构合约。
- `scripts/gd-validate-dispatch.py` 是唯一 wave 判断器。
- `templates/gd-dispatch-map-template.md` 已有 `tracks` + `waves`。
- `templates/gd-master-plan-template.md` 需要补强：master plan 必须引用或内嵌对应 dispatch map / wave matrix。
- 主 agent 只能按已验证的 `waves` 顺序派 child agent。
- 同 wave 并行必须满足：
  - `can_parallel_with` 双向声明
  - `blocked_by` 不在同 wave 或后 wave
  - `owned_paths` 不重叠
  - `max_parallel_* <= 2`
- 单 track wave 合法，表示串行段 `child_agent_count=1`。

### Q2: bridge/router v1 raw 真实 bug 是什么

具体 bug 锚定为：execution_outcome/combined 路径收到合法 Codex v1 raw，却被 v2 parser 当成缺 v2 title，落到 `wrapper_schema_fail`。

已确认失败证据形态：

- `reports/execution-review-cross-review-closure/router-live-autoparse-*`
- `reports/execution-review-cross-review-closure/router-live-true-raw-*`
- 错误文本：`parse-error: missing v2 title Execution Outcome Review Result (v2)`
- raw 实际是 `# Code Review Result` + `VERDICT: ...`

修复边界：

- 合法 v1 execution raw 必须通过 `--compat-v1` 映射成功。
- malformed v1 raw、缺 verdict、多 verdict、wrong kind、缺 evidence 仍 fail-closed。
- 旧 fixture 中 "execution_outcome with compat-v1 must reject" 的预期如果仍存在，必须替换为 rev21 预期。
- 不允许把 `wrapper_schema_fail` 改成 APPROVED；只能修合法 raw 的解析路径。

### Q3: promote 范围与 dirty 主根处理

主根收敛必须走 allowlist + backup manifest，不能在 240 dirty 主根上盲拷。

Promote allowlist：

- `commands/gd.md`
- `scripts/gd-codex-bridge-review.py`
- `scripts/gd-review-router.py`
- `scripts/gd-review-suite-controller.py`
- `scripts/gd-review-merge-and-fix-loop.py`
- `scripts/gd-validate-stage-dispatch-ledger.py`
- `scripts/gd-validate-controller-report.py`
- `scripts/gd-validate-route-report.py`
- `scripts/gd-validate-parent-close-gate.py`
- `scripts/gd-validate-execution-batch.py`
- `scripts/gd-run-akb-plan3-fresh-rerun.sh`
- `scripts/install-gd-command.sh`
- `scripts/check-gd-command-parity.sh`
- `schema/gd-stage-dispatch-ledger.schema.json`
- `schema/gd-controller-report.schema.json`
- `schema/gd-route-report.schema.json`
- `schema/gd-execution-batch.schema.json`
- required execution/review templates
- minimal negative fixtures for final / route / execute / stage-ledger / controller-report

Wave ledger / merge report 决策：

- `reports/wave-1/2/3` 不作为 runtime 产品文件。
- 若需要保留本轮收口证据，统一放到 `reports/project-gd-flow-closure-rev21/`，带 manifest。
- 不把零散旧 reports 批量 promote。

Dirty 主根规则：

- allowlist 外文件一律不碰。
- allowlist 内如果目标文件已有主根改动，先记录 `backup-manifest`：source hash、target before hash、target after hash、动作、时间。
- 不处理 pycache、旧 reports、无关历史 dirty。
- 不做 `git reset`、不做大清理。

### Q4: install parity 与刚才 install 的关系

install 不是重复测试，是成品安装入口。

- 如果 promote 后主根 `commands/gd.md` hash 已等于 installed hash，则 install 脚本 no-op，但仍输出 `INSTALLED_PARITY_PASS`。
- 如果 promote 改了主根 `commands/gd.md`，必须通过授权 install 脚本更新 `/Users/praise/.claude/commands/gd.md`。
- installed `/gd` 指向 Project GD 主根，所以最终必须满足：

```text
main commands/gd.md hash == installed /Users/praise/.claude/commands/gd.md hash
```

## Implementation Changes

1. 主根成品收敛  
   用 allowlist 把 peppy rev21 成品文件推广回 Project GD 主根。推广前生成 backup manifest；推广后主根成为唯一 source of truth。

2. master plan wave contract 补强  
   修改 master plan 模板，要求每份总计划必须引用或包含 dispatch map / wave matrix。主 agent 不能口头判断并行，必须依据 `gd-validate-dispatch.py` 通过的 `waves` 调度。

3. mandatory child-agent contract 固化  
   四阶段均要求 `child_agent_count=1..2`。串行步骤用 `1`，同 wave 并行最多 `2`。`0 child`、`3 child`、`child_jobs` 数量不匹配、`max_parallel>2` 均 closure-ineligible。

4. review plan bounded parallel  
   保留 bounded-parallel controller，移除旧 global bridge lock / serial-only 机制。并发只发生在 controller 明确 dispatch 的两个 child review job 内。

5. execute 与 review execution/code 子 agent 化  
   `/gd execute`、`/gd review execution/code` 不得回退到 `human_exec`、`local_only`、`LOCAL_STATIC_ONLY`、`pending_future_plan`。  
   Step 5 明确包含 route child review enforcement：`route-*` negative fixtures 必须覆盖 Codex-only、transport_failed、local_static、missing child review ledger。

6. bridge/router v1 compat 修复  
   execution_outcome/combined 的合法 v1 raw 固定走 compat 解析。旧 v2-only 假设从 rev21 路径移除。错误 raw 仍失败，不能被宽松解析。

7. final gate 假闭合拒绝  
   final gate 必须拒绝：
   - root parity drift
   - installed parity drift
   - stale aggregate
   - missing stage dispatch ledger
   - missing controller/merge report
   - fixture/mock-only report
   - `.raw_unknown`
   - all-zero hash
   - transport_failed
   - wrapper_schema_fail
   - degraded
   - timeout
   - failed_to_run
   - Claude-only / Codex-only
   - local-only / human_exec
   - child failed but parent approved

8. 脚本化成品入口  
   增加或收敛以下脚本作为产品入口，不作为额外测试阶段：
   - `scripts/gd-root-parity-status.sh`
   - `scripts/gd-install-rev21-for-handtest.sh`
   - `scripts/gd-check-installed-parity.sh`
   - `scripts/gd-bridge-compat-smoke.sh`
   - `scripts/gd-final-closure-status.sh`

9. 提交收口  
   只提交 allowlist 产品文件、必要 schema/templates/scripts/minimal fixtures、backup manifest。  
   不提交 pycache、旧 reports 大包、业务项目、无关 dirty。

## Acceptance Policy

上线标准不是"跑完一大轮测试"，而是成品可手测：

- 新窗口 `/gd` 使用 rev21 installed command。
- installed command 与 Project GD 主根 hash 一致。
- 主根具备完整 rev21 scripts/schema/templates。
- master plan 有可验证 dispatch map / wave matrix。
- 每个环节强制 child agent，0 child 不可闭合。
- 合法 v1 execution raw 不再误报 `wrapper_schema_fail`。
- final gate 不接受任何假闭合。
- 用户可直接拿真实项目手测 `/gd plan / review plan / execute / review execution-code`。

## Non-Goals

- 不改 `PROJECT_GOAL / CHAIN_GOAL`。
- 不改变四阶段核心链路。
- 不把 Codex 改成唯一裁判。
- 不修 AKB2 知识复利业务。
- 不跑 AKB `--live`。
- 不放宽 fail-closed。
- 不为了提交清理 240 dirty 主根。
- 不把 reports 当产品大包提交。
