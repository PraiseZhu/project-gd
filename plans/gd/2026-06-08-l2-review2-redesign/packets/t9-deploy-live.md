# Task Packet: t9-deploy-live

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t9-deploy-live
agent_role: implementer
parent_step: T9
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
created_at: 2026-06-08T00:00:00Z
```

---

## 2. 目标链

```text
PROJECT_GOAL: 用长模板 + Goal-Driven 机制减少"格式完整但计划不具体"的 AI 填表
CHAIN_GOAL:   让 L2(/review2)成为可日常使用的审查链——计划审查防填表、代码/执行结果审查闭环到可提交
PHASE_GOAL:   为 L2 spec T1-T9 各产出一份自包含、可被 /gd execute 消费的 task packet
TASK_GOAL:    把 T1-T8 全部新增/修改的 artifact 录进 .deploy-manifest.jsonl，使 deploy live 能把 source 一次性回灌到 ~/.claude/ live runtime，并消除 review2.md installed 副本的 scripts/→tools/ 路径漂移；deploy 后 source==installed 全一致、parity gate 通过
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t1-exhaustive-and-dual-codex
  - t2-dryrun-gate
  - t3-plan-mode-template
  - t4-antifill-hard-gate
  - t5-split-commands-triage
  - t6-fix-bridge-target
  - t7-controller-baseline-convergence
  - t8-deliverable-packaging
can_parallel_with: []
required_context:
  - docs/2026-06-07-l2-review-workflow-redesign-spec.md
  - .deploy-manifest.jsonl
```

> 说明：T9 是 spec §4 依赖图的阶段 4（部署），硬依赖 T1-T8 全部实现完成——manifest 只能录已存在的 source 文件，缺一不可录。本任务不可与任何 T1-T8 并行。

---

## 4. 路径权限

```yaml
owned_paths:
  - .deploy-manifest.jsonl
forbidden_paths:
  - 旧 /rev artifacts
  - "/Users/praise/.claude/**"
  - commands/review2.md
  - scripts/**
  - schema/**
  - templates/**
  - config/gd-runtime-parity-manifest.json
  - tools/**
  - 其他 task 的任意 owned_paths
```

读写权限分层：

- **写入**：仅限 `.deploy-manifest.jsonl`。写入任何其他路径（含 review2.md、scripts/、schema/、templates/、config/、tools/）= 越界，review 中 [P1] 阻断。
- **关键边界（spec §5）**：本任务**不直接 ad-hoc 写 `~/.claude/**`**。实际把 source 推到 live 的动作由 `deploy live` skill 执行（强制 preflight + dry-run + backup + ledger 授权 + post-verify 五步），本 packet 只负责**让 manifest 正确**，使该 skill 跑通。本 packet 自身不调用 `deploy live`、不 cp 任何文件到 live。
- **读取**：允许读 `required_context` 两个文件 + 已完成 blocked_by task 的 deliverables（T1-T8 产出的 source 文件，仅为确认路径存在、决定是否录入 manifest，不修改它们）+ 公共只读资源（manifest schema、parity manifest、parity 工具）。

---

## 5. 成功标准（SC）

> 对应 master SC-9。每条绑可执行 verify（见 §7）。

- [ ] SC-9.1：`.deploy-manifest.jsonl` 每行（非空、非 `#` 注释）均为合法 JSON，且每条 artifact 含 `source` / `target` / `method` / `ledger_scope` 四个必填字段。
- [ ] SC-9.2：manifest 录入**当前缺失**的 `scripts/gd-validate-review2-plan-target.py`（review2.md 第 43 行引用但 v8 manifest 未含）——新增一条 `direct_cp` artifact，target = `~/.claude/scripts/gd-validate-review2-plan-target.py`，ledger_scope = `sync_script_to_live`。
- [ ] SC-9.3：manifest 录入 T1-T8 新增的全部 live-bound source（仅录"动 live 才生效"的 artifact）：
  - T3 plan-mode 模板：source `templates/plan-mode-template.md` → target `~/.claude/templates/plan-template.md`，经 install_script 或 direct_cp，ledger_scope = `install_plan_template`。
  - T4 plan mode Stop hook（spec D5：动 live，需 ledger）：source = T4 实现产出的 hook 脚本（实际相对路径以 blocked_by task t4 的 deliverables 为准，常见 `scripts/gd-plan-mode-stop-hook.*` 或 `hooks/*`），target 在 `~/.claude/` 下，ledger_scope = `install_plan_mode_hook`。
  - T6/T7 修改或新增、且被 `/review2` live 运行时实际加载的脚本：`gd-codex-bridge-review.py`（T6 改）、新增 `scripts/gd-review-controller.py`（T7）、`scripts/gd-review-router.py`（若 T7 改）、新增 `schema/gd-baseline-findings.schema.json`（T7）——凡 review2 live 链路运行时会读到的，逐一录 `direct_cp` 到对应 `~/.claude/scripts/...` 或 `~/.claude/schema/...`，ledger_scope = `sync_script_to_live`。
  - 录入前先确认该 source 文件在工作树中实际存在（blocked_by task 已交付）；不存在的不录（避免 manifest 指向空文件）。
- [ ] SC-9.4：manifest 不录"仅工作树内、不进 live"的 artifact（如 plan packet、master-plan、docs spec、纯 CI fixture）——只录 spec T9 WHAT 列举的 review2 live 链路相关项 + 三档判定/controller/schema/模板/hook。
- [ ] SC-9.5：review2 路 5 条既有 v8 artifact（review2.md + 4 个 review2 脚本）在 manifest 中保留，未被本次编辑删除或破坏。
- [ ] SC-9.6：deploy 后（由 deploy live skill 执行）`tools/gd-parity-verify.sh --bundle review2_command` 退出码 0，stdout 状态为 `installed_parity_pass`（source==installed）。本 packet 的 verify 仅断言 deploy 前置条件就绪（manifest 合法 + parity 工具支持 review2_command bundle）；实际 deploy + parity-pass 由 deploy live skill 在 T1-T8 全实现后执行。

> scripts/→tools/ 路径漂移说明（SC-6 关联）：review2.md source 第 14/116 行引用 `tools/gd-parity-verify.sh`、`tools/gd-codex-chain-release-status.sh`（已是 tools/ 前缀）。所谓"installed 的 scripts/→tools/ 漂移"指 live 旧副本可能仍写 `scripts/`。修法 = 通过 manifest 把当前 source（tools/ 前缀正确版）的 review2.md 经 install_script 回灌覆盖 live 旧副本，deploy 后 source==installed 即自动消除漂移；**本 packet 不改 review2.md source**（它已正确），只确保 review2.md 条目在 manifest 中且 deploy 会覆盖 live。

---

## 6. 交付物

```yaml
deliverables:
  - path: .deploy-manifest.jsonl
    kind: file
    must_exist: true
    description: 更新后的部署清单——保留 v8 5 条 review2 artifact，新增 gd-validate-review2-plan-target.py（补缺）+ T3 模板 + T4 hook + T6/T7 脚本与 schema，每条含 source/target/method/ledger_scope
```

---

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-9.1
    method: command
    cmd: "test -f .deploy-manifest.jsonl && echo PASS"
    expect: "PASS"
  - sc_ref: SC-9.1
    method: assertion
    cmd: "python3 -c \"import json;[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]\" && echo JSON_OK"
    expect: "JSON_OK"
  - sc_ref: SC-9.1
    method: assertion
    cmd: "python3 -c \"import json; rows=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]; req={'source','target','method','ledger_scope'}; bad=[r for r in rows if not req.issubset(r)]; print('FIELDS_OK' if not bad else 'FIELDS_MISSING:'+str(bad))\""
    expect: "FIELDS_OK"
  - sc_ref: SC-9.2
    method: assertion
    cmd: "grep -c 'gd-validate-review2-plan-target.py' .deploy-manifest.jsonl"
    expect: ">=1"
  - sc_ref: SC-9.3
    method: assertion
    cmd: "grep -c 'gd-review-controller.py' .deploy-manifest.jsonl"
    expect: ">=1"
  - sc_ref: SC-9.3
    method: assertion
    cmd: "grep -c 'gd-baseline-findings.schema.json' .deploy-manifest.jsonl"
    expect: ">=1"
  - sc_ref: SC-9.3
    method: assertion
    cmd: "grep -c 'plan-mode-template.md\\|plan-template.md' .deploy-manifest.jsonl"
    expect: ">=1"
  - sc_ref: SC-9.3
    method: assertion
    cmd: "python3 -c \"import json,os; rows=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]; miss=[r['source'] for r in rows if not os.path.exists(r['source'])]; print('SOURCES_EXIST' if not miss else 'SOURCE_MISSING:'+str(miss))\""
    expect: "SOURCES_EXIST"
  - sc_ref: SC-9.5
    method: assertion
    cmd: "grep -c 'commands/review2.md' .deploy-manifest.jsonl"
    expect: ">=1"
  - sc_ref: SC-9.5
    method: assertion
    cmd: "python3 -c \"rows=open('.deploy-manifest.jsonl').read(); ok=all(s in rows for s in ['review2.md','gd-build-review2-capsule.py','gd-validate-review2-capsule.py','gd-codex-bridge-review.py','gd-validate-review2-output.py']); print('V8_PRESERVED' if ok else 'V8_BROKEN')\""
    expect: "V8_PRESERVED"
  - sc_ref: SC-9.6
    method: command
    cmd: "test -x tools/gd-parity-verify.sh && grep -q 'review2_command' tools/gd-parity-verify.sh && echo PARITY_BUNDLE_READY"
    expect: "PARITY_BUNDLE_READY"
  - sc_ref: SC-9.6
    method: assertion
    cmd: "python3 -c \"import json; d=json.load(open('config/gd-runtime-parity-manifest.json')); print('REVIEW2_PARITY_DECLARED' if d['bundles']['review2_command']['source_path']=='commands/review2.md' else 'PARITY_PATH_DRIFT')\""
    expect: "REVIEW2_PARITY_DECLARED"
```

> deploy 后 source==installed 的终态验证（`tools/gd-parity-verify.sh --bundle review2_command` → exit 0 + `installed_parity_pass`）由 deploy live skill 在 T1-T8 全实现后执行；本 packet 阶段 live 尚未安装最新版，parity 工具会返回 `installed_runtime_drift`（exit 2）或 `runtime_missing`（exit 3），属预期，不计入本 packet verify 失败。

---

## 8. Handoff 输出

子 agent 完成后必须输出以下结构（使用 `gd-execution-result-template.md`）：

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t9-deploy-live-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论：manifest 已补 plan-target validator + T1-T8 live artifact，五步部署前置就绪>
  blockers: <若 T1-T8 任一 source 未交付导致无法录入，列出缺失 source 路径>
```

---

## 9. 范围禁令

- 禁止 **写入** 除 `.deploy-manifest.jsonl` 外任何文件（含 review2.md source、scripts/、schema/、templates/、config/、tools/）
- 禁止直接 ad-hoc 写 `/Users/praise/.claude/**`——部署必须经 `deploy live` skill + ledger 授权（spec §5），本 packet 不执行 cp/install 到 live、不调用 deploy live 自身
- 禁止录入旧 `/rev` artifacts 到 manifest（spec §5：不动旧 /review、/rev）
- 禁止录入"仅工作树内不进 live"的 artifact（plan packet / master-plan / docs / fixture）
- 禁止启动 daemon、注册 hook、修改 cron（hook 的安装由 deploy live skill 经 ledger 执行，本 packet 只在 manifest 声明）
- 禁止用对话上下文替代 `required_context`
```
