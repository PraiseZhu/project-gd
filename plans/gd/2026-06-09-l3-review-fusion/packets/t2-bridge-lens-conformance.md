# Task Packet: t2-bridge-lens-conformance

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-task-packet

> **自包含合约**：本 packet 必须能被子 agent 单独执行；禁止"见上文 / 按之前讨论 / 参考会话上下文"等指代。
> 子 agent 只读本 packet + `required_context` 列出的文件，不读其他对话内容。

---

## 1. 标识

```yaml
task_id: t2-bridge-lens-conformance
agent_role: implementer
parent_step: step-2
parent_track_id: t2-bridge
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
TASK_GOAL:    在 gd-codex-bridge-review.py 的 build_capsule_text() 注入 REVIEW_LENS_EMPHASIS 占位（codex_A/codex_B 两份 capsule 唯一差异 = 视角侧重）+ 在 Reviewer Instructions 写入 conformance scoping 声明；并在 prompts/gd-review-standard.md 末尾新增穷举强制节（一次列全所有可发现 finding，明知多处只报一条判为 degraded）。
```

---

## 3. 依赖与并发

```yaml
blocked_by:
  - t1-transport                    # bridge 在 transport 加固（prevention 四道防线）落成之后改
can_parallel_with: []               # bridge 是 step-3/step-4 的共享 chokepoint，单独成 wave，不与任何 track 并行
required_context:
  - specs/l3-review-fusion/spec.md
  - docs/constitution.md
  - plans/gd/2026-06-09-l3-review-fusion/master-plan.md
```

---

## 4. 路径权限

```yaml
owned_paths:
  - scripts/gd-codex-bridge-review.py
  - prompts/gd-review-standard.md
forbidden_paths:
  - "/Users/praise/.claude/**"
  - scripts/gd-codex-transport-guard.py            # t1-transport owned
  - scripts/gd-review-suite-controller.py          # t1-transport owned（仅探活接入点）
  - scripts/gd-review-merge-and-fix-loop.py         # step-3 owned
  - scripts/gd-review-router.py                     # step-4 owned
  - tests/review-fusion                             # step-5 owned
  - fixtures/review-fusion                          # step-5 owned
  - .deploy-manifest.jsonl                          # step-6 owned
  - baselines/gd-v7-runtime-write-authorizations.jsonl  # step-6 owned
  - 旧 /rev artifacts
```

读写权限分层：

- **写入**：仅限本任务 `owned_paths`（`scripts/gd-codex-bridge-review.py` 与 `prompts/gd-review-standard.md`）；写入任何其他路径视为越界，review 中 [P1] 阻断。
- **读取**：允许 `required_context` 列出文件 + 已完成的 `blocked_by`（t1-transport）的 deliverables（仅作接口参照，不写入）+ 公共只读资源（schema、lock files、PROJECT_GOAL.md）。
- 不修改 `scripts/gd_review_contract.py`（SSOT enum 源；本任务不引入新 enum，只加 capsule 文本字段与 prompts 节）。

---

## 5. 成功标准（SC）

- [ ] SC-2（lens emphasis 双视角参数化）：`scripts/gd-codex-bridge-review.py` 的 `build_capsule_text()` 接受一个视角侧重入参（默认 None / neutral），并把字面量 `REVIEW_LENS_EMPHASIS` 作为 capsule 元数据行（与现有 `REVIEW_KIND` / `REVIEW_ROUND` 同区块）写入；传入 codex_A 视角渲染 codex_A 侧重文案，传入 codex_B 视角渲染 codex_B 侧重文案，两份 capsule 除该行（及其在 Reviewer Instructions 内对应展开句）外字节一致。验证：`grep -qE 'REVIEW_LENS_EMPHASIS' scripts/gd-codex-bridge-review.py && echo PASS` 输出 `PASS`。
- [ ] SC-6（conformance 声明 + 穷举强制）：(a) `build_capsule_text()` 的 `## Reviewer Instructions` 块新增 conformance scoping 声明，文案含「主审执行结果 / 已实现功能是否符合计划 SC」+「代码顺带扫一眼可指明显问题」+「不以地毯式找 bug 为职责（地毯式找 bug 由上游 /code-review 承担）」；(b) `prompts/gd-review-standard.md` 末尾新增穷举强制节，含标题 + 「一次列全所有可发现 finding」规则 + 「明知多处只报一条 → 判为 degraded」判定规则。bridge 文件须含 `conformance` 与「顺带」；standard 文件须含「一次列全所有可发现 finding」与 `degraded` 判定。验证：两条独立 grep 分别输出 `bridge/PASS` 与 `standard/PASS`。
- [ ] SC-2/SC-6 回归不破坏：`python3 scripts/gd-codex-bridge-review.py self-test` 仍 `exit 0`（注入 lens 字段与 conformance 文案后，既有 parse / merge / v2-routing 自测全绿，证明改动是 capsule 文本扩展、未动 schema / enum / 解析路径）。验证：`python3 scripts/gd-codex-bridge-review.py self-test; echo EXIT=$?` 末行 `EXIT=0`。

---

## 6. 交付物

```yaml
deliverables:
  - path: scripts/gd-codex-bridge-review.py
    kind: file
    must_exist: true
    description: build_capsule_text() 注入 REVIEW_LENS_EMPHASIS 参数化字段 + Reviewer Instructions 加 conformance scoping 声明
  - path: prompts/gd-review-standard.md
    kind: file
    must_exist: true
    description: 末尾新增穷举强制节（一次列全 finding；明知多处只报一条 → degraded）
```

---

## 7. 验证（Anti-fill 硬约束）

```yaml
verify:
  - sc_ref: SC-2
    method: command
    cmd: "python3 -c \"import importlib.util, sys, inspect, pathlib; spec=importlib.util.spec_from_file_location('bridge','scripts/gd-codex-bridge-review.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); fn=getattr(m,'build_capsule_text',None); assert fn is not None, 'build_capsule_text not found'; sig=inspect.signature(fn); assert 'lens_emphasis' in sig.parameters, 'lens_emphasis param missing'; target=pathlib.Path('plans/gd/2026-06-09-l3-review-fusion/master-plan.md'); assert target.exists(), f'fallback target missing: {target}'; ca=fn(compat_v1=True, lens_emphasis='codex_A', kind='plan', target=target, cwd=pathlib.Path('.')); cb=fn(compat_v1=True, lens_emphasis='codex_B', kind='plan', target=target, cwd=pathlib.Path('.')); la=ca.split(chr(10)); lb=cb.split(chr(10)); assert len(la)==len(lb), f'line count differs: {len(la)} vs {len(lb)}'; diffs=[i for i,(a,b) in enumerate(zip(la,lb)) if a!=b]; assert len(diffs)>0, 'no diff between codex_A and codex_B'; for i in diffs: line=la[i]+lb[i]; assert 'REVIEW_LENS_EMPHASIS' in line or 'lens' in line.lower(), f'Unexpected diff at line {i}: {line[:80]}'; print('PASS')\"
    expect: "PASS"
    note: "target 改用 master-plan.md（在 cwd=Project GD/ 下必然存在），消除对 packets/ 相对路径的依赖；断言 f-string 含路径信息便于失败时定位。"
  - sc_ref: SC-6
    method: command
    cmd: "grep -q 'conformance scoping' scripts/gd-codex-bridge-review.py && grep -q '顺带' scripts/gd-codex-bridge-review.py && echo bridge/PASS"
    expect: "bridge/PASS"
    note: "改为 grep 'conformance scoping'（新增 bullet 的精确短语），而非裸 'conformance'——后者在改动前已存在于现有注释/变量名，会误通过。"
  - sc_ref: SC-6
    method: command
    cmd: "grep -q '一次列全所有可发现 finding' prompts/gd-review-standard.md && grep -q '挑刺漂移' prompts/gd-review-standard.md && grep -q 'degraded' prompts/gd-review-standard.md && echo standard/PASS"
    expect: "standard/PASS"
    note: "增加 grep '挑刺漂移'（§10 新增节的专有词，改动前不存在），三条串联确保穷举强制节被完整写入而非仅有 degraded 字面量。"
  - sc_ref: SC-2/SC-6-regression
    method: command
    cmd: "python3 scripts/gd-codex-bridge-review.py self-test; echo EXIT=$?"
    expect: "EXIT=0"
```

---

## HOW（实现指引，基于真实代码结构，禁止泛化动词）

### REVIEW_LENS_EMPHASIS 注入点（SC-2）

权威源 `scripts/gd-codex-bridge-review.py`：

1. **签名扩展**：`build_capsule_text()`（约第 922 行起）当前末参为 `compat_v1: bool = False`，其后追加 `lens_emphasis: str | None = None`（向后兼容，默认 None）。
2. **侧重文案常量**：在模块常量区新增两条侧重字面量，二者唯一差异即视角侧重：
   - `codex_A` 侧重：偏「目标链 / SC 覆盖完整性 / fail-closed 与治理不变量」（结构与符合性视角）。
   - `codex_B` 侧重：偏「边界条件 / fallback 路径 / 收窄 scope 语义 / 漏报风险」（对抗与边角视角）。
   两条均以「本视角额外侧重 …；但不改变 §Review Standard 的穷举与 conformance 职责」收口，确保两视角并集而非分裂职责。
3. **capsule 元数据行**：在 capsule 拼接的元数据段（现 `REVIEW_KIND` / `REVIEW_ROUND` / `REVIEW_DELTA_SCOPE` 行所在区块）插入 `f"REVIEW_LENS_EMPHASIS: {effective_lens}\n"`；`effective_lens` 由入参解析（None → `neutral`，`codex_A`/`codex_B` → 对应短标签）。字面 token `REVIEW_LENS_EMPHASIS` 必须出现在源码（满足 SC-2 grep）。
4. **Reviewer Instructions 展开**：在 `## Reviewer Instructions` 块追加一行把 `effective_lens` 全文侧重句渲染进去，使 codex_A / codex_B 两份 capsule 在该块产生唯一文本差异。
5. **不改调用方契约**：`cmd_build_capsule` / `_cmd_run_bridge_inner` 等调用点保持现有调用不传 lens（默认 neutral，行为不变）；lens 由 step-3 的 merge-and-fix-loop 在 Round 1 派双 job 时分别传 `codex_A` / `codex_B`——本 task 只负责 bridge 侧暴露入参与字段，不改 merge-and-fix-loop（step-3 owned）。

### conformance scoping 声明（SC-6 a）

在 `## Reviewer Instructions` 块追加一条 bullet（对齐 spec FR-006 / 宪法 P6）：

> - **审查定位（conformance scoping）**：你的主目标是核对「执行结果 / 已实现功能是否符合已批准计划的 SC（conformance）」；代码本身顺带扫一眼，可指出明显问题，但 MUST NOT 把地毯式找 bug 当作职责——地毯式找 bug 由上游 `/code-review` 承担。

该 bullet 必须含字面 `conformance` 与「顺带」二字（保证 SC-6 grep 命中 bridge 文件侧）。

### 穷举强制节（SC-6 b）— 编号顺延为 §10

权威源 `prompts/gd-review-standard.md` 现末节为 `## 9. 与旧 /review / /rev 的隔离`。**§9 已被占用**，故穷举强制节在文件末尾新增为 **`## 10`**（dispatch 文案称「§9 穷举强制」，落地时编号顺延为 §10 以免覆盖现有 §9；标题语义不变）。新增节须含：

1. 标题：`## 10. 穷举强制（Exhaustive Finding Enumeration）`。
2. 规则：reviewer MUST 一次扫完 target 内全部 SC / 模块 / fallback，并在**首轮一次列全所有可发现 finding**，MUST NOT 把可一次报全的 finding 分散到多轮。
3. 判定：reviewer 若明知 target 有多处可发现 finding 却只报其中一条（挑刺漂移）→ 该 review `REVIEW_RUN_STATUS: degraded`、进入 Merge Matrix degraded 行（不得 APPROVED）。
4. 关联：本节是宪法 P6 anti-fill 穷举条款在标准源的落地，服务 P5（收敛速度由首轮覆盖率决定），并与现有 Merge Matrix「degraded → 不得 approved」一致。

### 边界与禁令

- 全程 lab-local；本 task **不写** `/Users/praise/.claude/**`、不碰 t1 owned（transport-guard.py / suite-controller.py）、不碰 step-3/4/5/6 owned。
- 不改 schema（`schema/gd-review-result*.schema.json`）、不改 SSOT enum（`gd_review_contract.py`）；只做 capsule 文本扩展 + prompts 加节。
- 不自动 commit / push；终点只产出可提交态。

---

## 8. Handoff 输出

```yaml
handoff_output:
  result_path: reports/gd-t2-bridge-lens-conformance-execution-result.md
  status_field: <见 gd-execution-status.schema.json>
  summary: <一句话结论>
  blockers: <未完成的依赖或外部阻塞>
```

---

## 9. 范围禁令

- 禁止 **写入** 其他 task 的 `owned_paths`（任何场景）。
- 禁止 **读取** 其他 task 的 `owned_paths`，除非该 task 已完成且其 deliverables 列入本 packet 的 `required_context`。
- 禁止访问 `/Users/praise/.claude/**`。
- 禁止启动 daemon、注册 hook、修改 cron。
- 禁止用对话上下文替代 `required_context`。
