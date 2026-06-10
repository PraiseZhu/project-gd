# Task Packet: t6-deploy-manifest

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t6-deploy-manifest
agent_role: child_executor
parent_step: step-6
parent_track_id: t6-deploy
parent_dispatch_id: l3-review-fusion
parent_plan: plans/gd/2026-06-09-l3-review-fusion/master-plan.md
created_at: 2026-06-09T00:00:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，降低填表式计划与执行遗漏风险（引用 GOAL_SOURCE）
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准（引用 GOAL_SOURCE）
PHASE_GOAL:   把 L2 已验证收敛机制融合进 L3 review，质量/符合性分离，零破坏治理 gate（引用 master plan）
TASK_GOAL:    产出 .deploy-manifest.jsonl（gd.md + 本计划改动 scripts 条目）+ baselines/gd-v7-runtime-write-authorizations.jsonl 授权记录（dispatch-only）；runtime 回灌与 source==installed parity 验收明确归独立 Plan E / deploy-live，不在本 task 范围。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t5-regression                   # 回归（SC-7 治理零破坏 + 故障注入）通过后才准备部署物
can_parallel_with: []               # 末位 wave（w5）串行
required_context:
  - specs/l3-review-fusion/spec.md            # 部署边界 Assumptions
  - docs/constitution.md                       # 变更边界：触 ~/.claude/** 必走 deploy-live + ledger 授权 + parity
  - plans/gd/2026-06-09-l3-review-fusion/master-plan.md   # §3 SC-8 / §5 Step 6 / §6 边界 / §7 风险表
```

> 只读参考（理解既有真实格式，不修改）：`.deploy-manifest.jsonl`（现状含 header `#` 注释 + review2 route 行；本 task **append**，不重写既有行）、`baselines/gd-v7-runtime-write-authorizations.jsonl`（现状含历次 gd.md 授权条目，复用字段格式，append）。t1（transport-guard）产出的 `scripts/gd-codex-transport-guard.py` 是 manifest 一条 source；本 task 在 t5 绿后编排，届时该 source 应已存在。

---

## 4. 路径权限

```yaml
owned_paths:
  - .deploy-manifest.jsonl
  - baselines/gd-v7-runtime-write-authorizations.jsonl
forbidden_paths:
  - "/Users/praise/.claude/**"
  - scripts/gd-codex-transport-guard.py
  - scripts/gd-review-suite-controller.py
  - scripts/gd-codex-bridge-review.py
  - prompts/gd-review-standard.md
  - scripts/gd-review-merge-and-fix-loop.py
  - scripts/gd-review-router.py
  - tests/review-fusion
  - fixtures/review-fusion
  - 旧 /rev artifacts
```

读写权限分层：

- **写入**：仅限 `.deploy-manifest.jsonl` 与 `baselines/gd-v7-runtime-write-authorizations.jsonl`（均 append 增量，禁止重写既有行）。写入任何其他路径（尤其 `scripts/`、`prompts/`、`tests/`、`fixtures/`、`commands/gd.md`、`/Users/praise/.claude/**`）视为越界，[P1] 阻断。
- **读取**：允许 `required_context` + 已完成 blocked_by（t5）的 deliverables + 公共只读资源（既有 manifest/ledger 现状、scripts source 存在性核对）。只读源码仅用于「source 路径是否存在」核对。

---

## 5. 成功标准（SC）

> 绑定 master SC-8（部署物准备，dispatch-only）。SC-1/SC-2 为 task 级条件，映射 master SC-8 两半（manifest + 授权 ledger）。

- [ ] SC-1（↔ master SC-8，manifest 准备）：`.deploy-manifest.jsonl` MUST 逐行为合法 JSON（空行/`#` 注释行除外），且 MUST 含一条 `target` 指向 `~/.claude/commands/gd.md` 的 gd.md 部署条目（method=`install_script`，ledger_scope=`install_claude_command`），并为本计划改动的 6 个 runtime artifact 各 append 一条部署条目（transport-guard / suite-controller / bridge / merge-and-fix-loop / router / gd-review-standard.md，method=`direct_cp`，ledger_scope=`sync_script_to_live`）。新增 append 在既有 review2 route 行之后，既有行不动。
- [ ] SC-2（↔ master SC-8，授权 ledger）：`baselines/gd-v7-runtime-write-authorizations.jsonl` MUST 逐行为合法 JSON，且 MUST append 一条 `target_path=/Users/praise/.claude/commands/gd.md`、`scope=install_claude_command`、`plan_ref=l3-review-fusion`、含 `new_source_hash`（`shasum -a 256 commands/gd.md`）的 runtime-write 授权条目；标注 gd.md 回灌为 runtime 写入、需用户显式授权（granted_by/authorization_source），并显式声明回灌与 parity 验收由 Plan E / deploy-live 后置执行。既有授权条目不动。

> 边界声明（MUST 体现在产物注释/字段，引 master-plan §6 + spec §Assumptions「部署边界」）：本 task 仅产出部署物「准备」（manifest + 授权 ledger）。runtime 写入 `~/.claude/commands/gd.md`、`source==installed` parity 验收、live scripts 同步 = 独立 Plan E / deploy-live 后置步骤，不在本 task SC 范围，全程不写 `/Users/praise/.claude/**`。

---

## 6. 交付物

```yaml
deliverables:
  - path: .deploy-manifest.jsonl
    kind: file
    must_exist: true
    description: append 7 条本计划部署条目（1 条 gd.md install_claude_command + 6 条改动 runtime artifact sync_script_to_live），逐行合法 JSON，既有 review2 route 行不动。
  - path: baselines/gd-v7-runtime-write-authorizations.jsonl
    kind: file
    must_exist: true
    description: append 1 条 gd.md → ~/.claude/commands/gd.md 的 install_claude_command 授权记录（plan_ref=l3-review-fusion），标注回灌 + parity 归 Plan E / deploy-live；既有条目不动。
```

---

## 7. HOW（基于现有 .deploy-manifest.jsonl + ledger 真实格式）

> 两文件均已存在；本 task 为 append 增量，禁止重写既有行 / 改动既有 review2 route 条目与历史授权条目。

### 7.1 `.deploy-manifest.jsonl` 真实字段 schema
文件头注释定义字段：`source`, `target`, `method`（`install_script`|`direct_cp`），可选 `installer`, 可选 `installer_args`, `ledger_scope`。既有 review2.md 行给出 `install_script` 范式（installer=`scripts/install-review-route-command.sh`，ledger_scope=`install_claude_command`）；scripts 类用 `direct_cp` + `ledger_scope=sync_script_to_live`。

### 7.2 改动 1 — append gd.md 命令部署条目（SC-1）
末尾 append gd.md 命令安装条目，使用现有 `scripts/install-gd-command.sh --install`（该脚本已实现 `scope=install_claude_command + target_path + new_source_hash` 三重校验，见 `scripts/install-gd-command.sh`）。`source=commands/gd.md`，`target=~/.claude/commands/gd.md`，`method=install_script`，`installer=scripts/install-gd-command.sh`，`installer_args=["--install"]`，`ledger_scope=install_claude_command`。**禁止臆造 installer 路径或降级为 direct_cp**。建议加 `"note":"runtime write deferred to Plan E / deploy-live; dispatch-only preparation"`。

### 7.3 改动 2 — append 6 条改动 runtime artifact 条目（SC-1）
master-plan §6「修改」清单中触 runtime 的 6 个 artifact，各 append `direct_cp`+`sync_script_to_live` 条目：
1. `scripts/gd-codex-transport-guard.py`（t1 新增）→ `~/.claude/scripts/gd-codex-transport-guard.py`
2. `scripts/gd-review-suite-controller.py`（t1 探活接入）→ `~/.claude/scripts/gd-review-suite-controller.py`
3. `scripts/gd-codex-bridge-review.py`（t2）→ `~/.claude/scripts/gd-codex-bridge-review.py`
4. `scripts/gd-review-merge-and-fix-loop.py`（t3）→ `~/.claude/scripts/gd-review-merge-and-fix-loop.py`
5. `scripts/gd-review-router.py`（t4）→ `~/.claude/scripts/gd-review-router.py`
6. `prompts/gd-review-standard.md`（t2）→ `~/.claude/prompts/gd-review-standard.md`
每条形如 `{"source":"scripts/gd-review-router.py","target":"~/.claude/scripts/gd-review-router.py","method":"direct_cp","ledger_scope":"sync_script_to_live","note":"sync deferred to Plan E / deploy-live"}`。target 前缀对齐现网既有条目（scripts→`~/.claude/scripts/`，prompt→`~/.claude/prompts/`）。

### 7.4 改动 3 — append gd.md runtime-write 授权条目（SC-2）
`baselines/gd-v7-runtime-write-authorizations.jsonl` 既有条目字段：`ts`, `target_path`, `granted_by`, 可选 `authorization_source`, `scope`, 可选 `target_revision`/`new_source_hash`/`expected_old_hash`/`before_hash`, `plan_ref`, `rationale`。`scope=install_claude_command` + `target_path=/Users/praise/.claude/commands/gd.md` 的条目就是历次 gd.md runtime 写入授权。末尾 append 一条本计划授权：
`{"ts":"<UTC ISO8601>","target_path":"/Users/praise/.claude/commands/gd.md","granted_by":"<用户显式授权标识>","authorization_source":"<用户授权原文引用>","scope":"install_claude_command","new_source_hash":"<shasum -a 256 commands/gd.md>","plan_ref":"l3-review-fusion","rationale":"L3 review fusion 改动后 gd.md 回灌授权（dispatch-only 准备）；实际 runtime 写入 + source==installed parity 由 Plan E / deploy-live 后置执行，本计划不写 /Users/praise/.claude/**"}`

### 7.5 gd.md 为何标 runtime-write-authorization（引宪法）
`commands/gd.md` 部署 target=`/Users/praise/.claude/commands/gd.md`（runtime 路径）。constitution §变更边界规定：触 `~/.claude/**`（含 L3 锚点 commands/gd.md）MUST 走 deploy-live + ledger 授权 + parity，MUST NOT 直接写 live。故 gd.md 每次 runtime 写入必须在该 ledger 留一条 `install_claude_command` 授权记录。

### 7.6 为何 runtime 写入与 parity 不在本 task（引 master-plan §6 + spec §Assumptions）
- master-plan §6「不修改」：`/Users/praise/.claude/**` 本 plan 全程不写；gd.md runtime 回灌 + parity 属独立 Plan E / deploy-live。§7 风险表「runtime 回灌破坏现网 /gd」行同。
- spec §Assumptions「部署边界」：L3 锚点 commands/gd.md 位于 live runtime；本 spec 只定义 WHAT/WHY，落地走 deploy-live + ledger + parity，不在范围。
- 故本 task dispatch-only：只编排「部署什么、谁授权」为 manifest + ledger 两份准备物，不执行 runtime 写入、不跑 parity。

### 不变量（零破坏，P3/P4）
- 两文件 append-only：既有 review2 route 行、既有全部历史授权条目不改/不删/不重排。
- 不写 `/Users/praise/.claude/**`；不触 scripts/prompt/tests/fixtures；不调 deploy-live；不跑 install/sync；不自动 commit/push。
- 新增行逐行合法 JSON（manifest 允许 `#` 注释行与空行）。

---

## 8. 验证（Anti-fill 硬约束）

> ⚠️ **既存张力（必须知晓）**：dispatch-map t6 与 master-plan §3/§8 的 SC-8 权威 verify 原句为
> `python3 -c "import json; [json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip()]" && grep -q 'gd.md' .deploy-manifest.jsonl && echo MANIFEST_LEDGER_READY`
> 但**现网 .deploy-manifest.jsonl 含 `#` 注释行**，该原句未排除注释行 → `json.loads('# ...')` 会抛 JSONDecodeError，**原句对真实文件会崩**。下方 SC-1 verify 已加 `not l.lstrip().startswith('#')` 守卫匹配真实结构。执行时**用守卫版**；不得为迁就原句删除既有注释行（既有行 append-only）。该缺陷已上报，待 master-plan/dispatch-map verify 同步修正。

```yaml
verify:
  - sc_ref: SC-8
    method: command
    cmd: "python3 -c \"import json; lines=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.lstrip().startswith('#')]; gd=[e for e in lines if 'gd.md' in e.get('source','')]; assert gd, 'gd.md entry missing'; assert gd[0].get('installer')=='scripts/install-gd-command.sh', 'wrong installer'; scripts=[e for e in lines if e.get('ledger_scope')=='sync_script_to_live']; assert len(scripts)>=6, f'expected >=6 sync_script_to_live, got {len(scripts)}'; print('MANIFEST_ENTRIES_OK')\" 2>&1"
    expect: "MANIFEST_ENTRIES_OK"
  - sc_ref: SC-8
    method: command
    cmd: "test -f scripts/gd-codex-transport-guard.py && test -f scripts/gd-review-suite-controller.py && test -f scripts/gd-codex-bridge-review.py && test -f scripts/gd-review-merge-and-fix-loop.py && test -f scripts/gd-review-router.py && test -f prompts/gd-review-standard.md && test -f commands/gd.md && echo SOURCES_OK"
    expect: "SOURCES_OK"
  - sc_ref: SC-8-sync-entries-content
    method: command
    cmd: "python3 -c \"import json; lines=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.lstrip().startswith('#')]; sync=[e for e in lines if e.get('ledger_scope')=='sync_script_to_live']; assert len(sync)>=6, f'got {len(sync)}'; expected_sources=['gd-codex-transport-guard.py','gd-review-suite-controller.py','gd-codex-bridge-review.py','gd-review-merge-and-fix-loop.py','gd-review-router.py','gd-review-standard.md']; missing=[s for s in expected_sources if not any(s in e.get('source','') for e in sync)]; assert not missing, f'missing sync entries for: {missing}'; bad_target=[e for e in sync if not e.get('target','').startswith('~/.claude/')]; assert not bad_target, f'wrong target prefix: {[e[\"target\"] for e in bad_target]}'; print('SYNC_ENTRIES_OK')\" 2>&1"
    expect: "SYNC_ENTRIES_OK"
    note: "替换纯 grep -c 计数：逐条验证 6 个必需 source 文件名均有对应 sync_script_to_live 条目，且每条 target 以 ~/.claude/ 开头。防止无关行凑数或 target 路径错误。"
  - sc_ref: SC-8
    method: command
    cmd: "python3 -c \"import json, hashlib; [json.loads(l) for l in open('baselines/gd-v7-runtime-write-authorizations.jsonl') if l.strip()]; gd_hash=hashlib.sha256(open('commands/gd.md','rb').read()).hexdigest(); lines=[json.loads(l) for l in open('baselines/gd-v7-runtime-write-authorizations.jsonl') if l.strip()]; match=[e for e in lines if e.get('plan_ref')=='l3-review-fusion' and e.get('scope')=='install_claude_command' and e.get('new_source_hash')==gd_hash]; assert match, 'missing or mismatched new_source_hash'; entry=match[0]; assert entry.get('target_path')=='/Users/praise/.claude/commands/gd.md', f'wrong target_path: {entry.get(\\\"target_path\\\")}'; gb=entry.get('granted_by',''); au=entry.get('authorization_source',''); assert gb and len(gb)>3 and '<user' not in gb, 'granted_by is placeholder'; assert au and len(au)>3 and '<user' not in au, 'authorization_source is placeholder'; print('LEDGER_OK')\""
    expect: "LEDGER_OK"
    note: "增加 target_path=='/Users/praise/.claude/commands/gd.md' 断言，防止 plan_ref 和 scope 匹配但 target_path 错误时误通过。"
```

---

## 9. Handoff 输出

```yaml
handoff_output:
  result_path: <子 agent 写入 execution result 的相对路径>
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论>
  blockers: <如 t5 未绿 / t1 的 transport-guard source 缺失 / dispatch-map verify 原句与 manifest # 注释行的解析张力>
```

---

## 10. 范围禁令

- 禁止写入除 `.deploy-manifest.jsonl` 与 `baselines/gd-v7-runtime-write-authorizations.jsonl` 外任何路径；尤其禁改任何 `scripts/`、`prompts/`、`tests/`、`fixtures/`、`commands/gd.md`。
- 本 task dispatch-only：只产出 manifest + 授权 ledger；禁止执行 runtime 写入、禁止跑 source==installed parity、禁止调 deploy-live。
- 禁止访问 `/Users/praise/.claude/**`（读写均禁）；禁止 append 时重写/删除/重排既有行。
- 禁止 daemon/hook/cron；禁止用对话上下文替代 required_context；不自动 commit/push。
