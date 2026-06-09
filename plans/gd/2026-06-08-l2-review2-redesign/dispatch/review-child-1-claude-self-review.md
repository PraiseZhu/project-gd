# Plan Review Result

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-plan-review

---

## 1. 标识与运行状态

```text
REVIEWER: claude_subagent_plan_review
REVIEW_TARGET: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md (+ 9 packets)
REVIEW_KIND: plan
REVIEW_RUN_STATUS: completed
GD_REVIEW_DECISION: REQUIRES_CHANGES
```

`GD_REVIEW_DECISION` 取值见 `prompts/gd-review-standard.md` "Output Contract"；禁止裸 `VERDICT:`。

---

## 2. Scope Checked

| 检查面 | 结论 | 证据（≤30 字） |
|--------|------|---------------|
| master-plan 目标链完整性（SC-N 与 T-N 对应）| pass | §3 SC-1~SC-9 与 §5 T1~T9 一一对应 |
| SC verify 可执行性（规则 A）| fail | dispatch-map 各 track verify 仅测文件存在 + TASK_GOAL grep，未绑顶层 SC |
| 实施步骤动作具体性（规则 B）| pass | packets 步骤均用具体路径/命令/函数名，无纯泛词 |
| SC 至少绑定一个可验证物（规则 C）| fail | dispatch-map verify 未覆盖 master-plan SC-N 的实质内容 |
| task packet 自包含（规则 D）| pass | 9 个 packet 均声明 required_context 无"见上文"指代 |
| owned_paths 无跨 task 重叠 | fail | commands/review2.md 被 t2/t5/t7/t8 四个 packet 共同列入 owned_paths |
| can_parallel_with 双向关系 | fail | t1 声明 can_parallel_with: [t3]，但 t3 声明 can_parallel_with: [t4]，不含 t1；不对称 |
| dispatch-map waves 与 master-plan wave matrix 一致 | fail | master-plan §5a wave matrix 中 w1=[t1,t2]，dispatch-map 一致；但 master-plan §5 blocked_by 实现依赖与 dispatch-map planning blocked_by 的角色未区分说明 |
| required_context 路径在 owned_paths 之外 | pass | 各 packet required_context 列均不含自身 owned_paths |
| can_parallel_with task 互不在对方 blocked_by | fail | t2 blocked_by t5，但 dispatch-map 中 t2 can_parallel_with:[t1]，t1 can_parallel_with:[t2]——此对有效；然而 t4 blocked_by t5，t4 can_parallel_with:[t3]，t3 can_parallel_with:[t4]——此对有效；问题在 planning dispatch 层 blocked_by 均为空，实现 blocked_by 与 planning blocked_by 混用且 dispatch-map blocked_by 与 packet blocked_by 不一致 |
| SC-N 与 dispatch-map sc_refs 对齐 | pass | 每个 track sc_refs 匹配对应 SC |
| 裸 VERDICT 残留（规则 F）| pass | 全量 artifact 未发现行首裸 VERDICT: |
| t6 handoff_output result_path 非空具体路径 | fail | t6 §8 result_path 写 "<子 agent 写入 execution result 的相对路径>" 占位符，未填具体路径 |
| t8 handoff_output result_path 非空具体路径 | fail | t8 §8 result_path 同为占位符 |
| t7 handoff_output result_path 非空具体路径 | fail | t7 §8 result_path 同为占位符 |
| t9 SC 编号重用（SC-1~SC-6）| fail | t9 §5 成功标准编号 SC-1~SC-6，与 master-plan SC-1~SC-9 命名冲突，应为 SC-9.1~SC-9.6 |
| t6 verify cmd 路径用相对形式 | fail | t6 §7 verify cmd 含 `cd 'Project GD/.clone/worktrees/gd-l2-parity'` 相对路径，与其他 packet 用绝对路径不一致 |

---

## 3. Findings（严重度仅 P1 / P2 阻断）

### Finding 1 [P1] commands/review2.md 被四个 packet 共同列为 owned_paths，违反无重叠规则

```yaml
severity: P1
title: commands/review2.md owned_paths 四 task 重叠
sc_refs:
  - SC-5
  - SC-2
  - SC-7
  - SC-8
evidence: |
  t2 §4 owned_paths: commands/review2.md（第 56 行）
  t5 §4 owned_paths: commands/review2.md（第 56 行）
  t7 §4 owned_paths: commands/review2.md（第 61 行）
  t8 §4 owned_paths: commands/review2.md（第 59 行）
  gd-review-standard.md §6："task packet 之间 owned_paths 无重叠"
impact: |
  review standard §6 要求 owned_paths 无重叠，四个 packet 同时声明写 commands/review2.md。
  虽然 packet 文本内通过"只改各自负责的段落"描述了串行写入意图，但 owned_paths 字段本身
  依然重叠——这违反 schema 层面的不重叠约束，会导致 gd-validate-dispatch.py 的 owned_paths
  重叠检查失败（若该检查存在），并使 execution dispatch 无法直接依赖字段约束来防并发写冲突。
required_fix: |
  将 commands/review2.md 的四段各自抽为独立的"分段路径"形式（如 commands/review2.md::plan-entry-section /
  commands/review2.md::code-loop-section / commands/review2.md::terminal-stage-section /
  commands/review2.md::preflight-gate-section），或将 commands/review2.md 从 t2/t5/t7/t8 的
  owned_paths 中移除，改为一个专属该文件编辑的 shared-file 协议：由唯一 owned_task 编辑全文，
  其他 task 通过 blocked_by 依赖顺序串行传递。最简修法：review2.md 仅归 t5（最早编辑方），
  t2/t7/t8 在 blocked_by 中依赖 t5，owned_paths 里删除 commands/review2.md，改为在
  deliverables 中描述"对 T5 已创建的 commands/review2.md 追加段落"。
verify: |
  python3 -c "
  import json
  tracks = json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['tracks']
  from collections import Counter
  all_owned = [p for t in tracks for p in t['owned_paths']]
  dups = [p for p,c in Counter(all_owned).items() if c > 1]
  print('OWNED_PATHS_CONFLICT:', dups if dups else 'NONE')
  "
  期望: OWNED_PATHS_CONFLICT: NONE
```

---

### Finding 2 [P1] t1 和 t3 的 can_parallel_with 声明不对称

```yaml
severity: P1
title: can_parallel_with 双向关系不对称：t1↔t3
sc_refs:
  - SC-1
  - SC-3
evidence: |
  t1 §3 can_parallel_with: [t3]（packet 文件第 40 行）
  t3 §3 can_parallel_with: [t4]（packet 文件第 44 行），不含 t1
  gd-review-standard.md §6："can_parallel_with 中的 task 必须互不在对方的 blocked_by"——
  虽然该规则讲的是 blocked_by 方向，但 can_parallel_with 本身应双向声明以保证一致性；
  dispatch-map t1 can_parallel_with:[t2]，t3 can_parallel_with:[t4]，同样不对称：
  master-plan §5a wave matrix 中 w1=[t1,t2]，w2=[t3,t4]，t1 与 t3 不在同一 wave，
  但 t1 packet 自行声明 can_parallel_with: [t3]，与 master-plan wave 设计冲突。
impact: |
  t1 packet 声称可与 t3 并行，但 t3 packet 并未声明可与 t1 并行，且 dispatch-map 也未
  建立 t1-t3 并行关系（t1 在 w1，t3 在 w2）。
  execution dispatch 按 packet can_parallel_with 字段排程时，双方不对称导致一个 task 认为
  可以并行、另一个 task 不知道，可能产生调度歧义。若 dispatch 校验器检查"A 可并行 B 当且仅当
  A ∈ B.can_parallel_with 且 B ∈ A.can_parallel_with"，则 t1-t3 对直接失败。
required_fix: |
  选项 A（推荐）：t1 和 t3 不在同一 wave，删除 t1 packet 中 can_parallel_with: [t3] 声明，
  保持与 master-plan §5a wave matrix 一致（w1=[t1,t2]，w2=[t3,t4]，跨 wave 不并行）。
  选项 B：若确认 t1 与 t3 确实可并行，则在 t3 packet 中补充 can_parallel_with: [t1]，
  并在 dispatch-map 中相应更新 t3.can_parallel_with 字段。
verify: |
  python3 -c "
  import json
  tracks = {t['track_id']:t for t in json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['tracks']}
  errors = []
  for tid,t in tracks.items():
      for peer in t.get('can_parallel_with',[]):
          if tid not in tracks[peer].get('can_parallel_with',[]):
              errors.append(f'{tid} -> {peer} not symmetric')
  print('CAN_PARALLEL_SYMMETRIC:', 'PASS' if not errors else errors)
  "
  期望: CAN_PARALLEL_SYMMETRIC: PASS
```

---

### Finding 3 [P1] dispatch-map 各 track verify 仅验文件存在与 TASK_GOAL 字段，未绑 master-plan SC-N 内容

```yaml
severity: P1
title: dispatch-map track verify 未绑 master-plan SC-N 可执行验证，违反规则 A
sc_refs:
  - SC-1
  - SC-2
  - SC-3
  - SC-4
  - SC-5
  - SC-6
  - SC-7
  - SC-8
  - SC-9
evidence: |
  dispatch-map.json 每个 track 的 verify 命令形如：
  "cmd": "test -f <packet-path> && grep -q TASK_GOAL <packet-path> && echo PASS"
  这只验证 packet 文件存在且含 TASK_GOAL 字段，并不验证 master-plan SC-N 的内容
  合规性（如 SC-1 要求 gd-review-standard.md 含穷举段，SC-2 要求 preflight exit≠0）。
  gd-review-standard.md §6 规则 A："verify 字段满足规则 A"即必须含命令/路径/输出断言/测试用例。
  dispatch-map 的 verify 形式上满足"有命令"，但 master-plan §3 的顶层 SC 验证命令（如
  SC-1: grep -nE "穷举|一次列全" prompts/gd-review-standard.md）未被 dispatch-map
  的 verify 覆盖，导致 dispatch-map 无法独立验证 master-plan SC 是否达成。
impact: |
  这是 planning dispatch 层，dispatch-map verify 仅证明 packet 存在，不证明 packet 内容
  达到 master-plan SC。若 packet 内容不合规（如 verify 字段为空或泛词），dispatch-map 的
  verify gate 无法拦截，merge gate G4 也仅检查"每个 task packet 的 SC 均有可执行 verify"，
  不与 master-plan SC 顶层命令绑定。planning 阶段 SC 无法从 dispatch-map 层独立验收。
required_fix: |
  dispatch-map 每个 track 的 verify 至少补充一条与 master-plan SC-N 一致的内容验证命令。
  例如 t1 track 除现有文件存在断言外，补：
  {"sc_ref":"SC-1","method":"assertion","cmd":"grep -q REVIEW_LENS_EMPHASIS plans/gd/2026-06-08-l2-review2-redesign/packets/t1-exhaustive-and-dual-codex.md && echo PASS","expect":"PASS"}
  各 track 类推，至少覆盖各自 SC-N 的关键 token（参照 master-plan §3 verify 命令）。
verify: |
  python3 -c "
  import json
  tracks = json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['tracks']
  for t in tracks:
      verifies = t.get('verify',[])
      # 每个 track 至少有 2 条 verify（文件存在 + 内容验证）
      if len(verifies) < 2:
          print(f'TRACK {t[\"track_id\"]} VERIFY_THIN: only {len(verifies)} verify entries')
  print('VERIFY_COVERAGE_CHECK_DONE')
  "
  期望: 每个 track 输出无 VERIFY_THIN 行，只有 VERIFY_COVERAGE_CHECK_DONE
```

---

### Finding 4 [P1] t9 成功标准编号 SC-1~SC-6 与 master-plan SC-N 命名空间冲突

```yaml
severity: P1
title: t9 SC 编号重用 SC-1~SC-6，与 master-plan SC-1~SC-9 冲突
sc_refs:
  - SC-9
evidence: |
  t9 §5 成功标准列出 SC-1, SC-2, SC-3, SC-4, SC-5, SC-6（文件第 86~95 行）
  master-plan §3 已定义 SC-1~SC-9（对应 T1~T9 实现验收）
  其他 packet（t1~t8）均将子条件命名为 SC-N.M（如 t1 用 SC-1.1/SC-1.2/SC-1.3，
  t2 用 SC-2a/SC-2b/SC-2c/SC-2d），只有 t9 直接复用 SC-1~SC-6 裸编号。
impact: |
  t9 packet 被子 agent 执行时，若子 agent 引用 SC-1 验收，将无法区分是引用 master-plan
  的 SC-1（穷举强制）还是 t9 packet 内部的 SC-1（manifest JSON 合法性）。
  controller 收集各 task SC 状态时可能将 t9.SC-1 误判为 master SC-1 已通过。
  违反自包含合约中的命名清晰要求。
required_fix: |
  将 t9 §5 的 SC-1~SC-6 重命名为 SC-9.1~SC-9.6，并在 §7 verify 的 sc_ref 字段同步更新。
verify: |
  grep -n "^- \[ \] SC-[0-9]\+:" plans/gd/2026-06-08-l2-review2-redesign/packets/t9-deploy-live.md | grep -vE "SC-9\."
  期望: 无输出（t9 所有 SC 编号均以 SC-9. 前缀）
```

---

### Finding 5 [P2] t6 handoff_output result_path 为占位符，未填具体路径

```yaml
severity: P2
title: t6 handoff_output result_path 占位符未填
sc_refs:
  - SC-6
evidence: |
  t6 §8（文件第 153 行）:
  result_path: <子 agent 写入 execution result 的相对路径>
  对比 t1/t2/t3/t4/t5/t9 均已填写具体相对路径（如
  t1: plans/gd/2026-06-08-l2-review2-redesign/results/t1-exhaustive-and-dual-codex-result.md）
impact: |
  子 agent 执行 t6 时无法从 packet 得知 handoff 写入路径，需自行猜测或上下文推断，
  违反自包含合约。controller 收集各 task handoff 结果时无法定位 t6 结果文件。
required_fix: |
  将 t6 §8 result_path 改为具体路径：
  plans/gd/2026-06-08-l2-review2-redesign/results/t6-fix-bridge-target-result.md
verify: |
  grep -n "result_path:" plans/gd/2026-06-08-l2-review2-redesign/packets/t6-fix-bridge-target.md | grep -v "<"
  期望: >=1 行命中（无尖括号占位符）
```

---

### Finding 6 [P2] t7 和 t8 handoff_output result_path 同为占位符

```yaml
severity: P2
title: t7/t8 handoff_output result_path 占位符未填
sc_refs:
  - SC-7
  - SC-8
evidence: |
  t7 §8（文件第 230 行）: result_path: <子 agent 写入 execution result 的相对路径>
  t8 §8（文件第 162 行）: result_path: <子 agent 写入 execution result 的相对路径>
  与 Finding 5 同类问题，t7 和 t8 均未填具体路径。
impact: |
  与 Finding 5 相同：子 agent 执行时无法从 packet 定位 handoff 输出路径，违反自包含合约。
required_fix: |
  t7: result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t7-controller-baseline-convergence-result.md
  t8: result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t8-deliverable-packaging-result.md
verify: |
  grep -n "result_path:" plans/gd/2026-06-08-l2-review2-redesign/packets/t7-controller-baseline-convergence.md | grep -v "<" && echo T7_OK
  grep -n "result_path:" plans/gd/2026-06-08-l2-review2-redesign/packets/t8-deliverable-packaging.md | grep -v "<" && echo T8_OK
  期望: T7_OK 和 T8_OK 均出现
```

---

### Finding 7 [P2] t6 verify 中 cd 命令使用相对路径而非绝对路径

```yaml
severity: P2
title: t6 verify cmd 使用相对路径 cd，与其他 packet 不一致且无法独立执行
sc_refs:
  - SC-6
evidence: |
  t6 §7 verify（文件第 119~141 行）各条 cmd 均以：
  cd 'Project GD/.clone/worktrees/gd-l2-parity' && ...
  对比其他 packet（如 t7 所有 verify 均以绝对路径
  cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' && ...）
  t6 使用的是相对路径形式，且路径中含 .clone 而非 .claude（可能是拼写错误）。
impact: |
  相对路径形式的 cd 命令在子 agent 从不同 cwd 执行时会失败（找不到目录）。
  ".clone" 路径若为拼写错误，执行时必然 exit≠0 导致所有 t6 verify 失败。
  即使路径正确，相对路径在自动化测试框架中不可靠，违反 packet 自包含约束（§7 注释：
  "下列命令均在工作目录...下运行"，但 t6 未使用绝对路径确保可移植性）。
required_fix: |
  将 t6 §7 所有 verify cmd 中的：
  cd 'Project GD/.clone/worktrees/gd-l2-parity' &&
  改为：
  cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity' &&
  同时确认 .clone 是否为 .claude 的拼写错误，若是则一并修正。
verify: |
  grep -n "cd 'Project GD" plans/gd/2026-06-08-l2-review2-redesign/packets/t6-fix-bridge-target.md | wc -l
  期望: 0（不再有相对路径 cd）
  grep -n ".clone" plans/gd/2026-06-08-l2-review2-redesign/packets/t6-fix-bridge-target.md | wc -l
  期望: 0（无拼写错误路径）
```

---

### Finding 8 [P2] dispatch-map 中 planning blocked_by 与 packet 实现 blocked_by 混用，未区分两个语义层

```yaml
severity: P2
title: dispatch-map blocked_by 均为空但各 packet blocked_by 有非空依赖，语义分层说明不充分
sc_refs:
  - SC-5
  - SC-2
  - SC-4
  - SC-7
  - SC-8
  - SC-9
evidence: |
  dispatch-map.json 所有 9 个 track 的 blocked_by 均为 []（第 24, 36, 48, 60, 72, 84, 96, 108, 122 行）
  但各 packet 内部 blocked_by 有：
    t2 blocked_by: [t5]（packet 第 41 行）
    t4 blocked_by: [t5]（packet 第 39 行）
    t6 blocked_by: [t1]（packet 第 43 行）
    t7 blocked_by: [t5, t6]（packet 第 45-46 行）
    t8 blocked_by: [t7]（packet 第 44 行）
    t9 blocked_by: [t1~t8 全部]（packet 第 40-48 行）
  master-plan §5a 说明："实现依赖（如 T7 实现 blocked_by T6）记录在各 task packet 内部的
  blocked_by 字段，供后续 /gd execute 的 execution dispatch 使用，不在本层。"
  但 dispatch-map.json 没有任何注释或字段说明这一语义分层，直接看 dispatch-map 会误以为
  所有 task 均无依赖可以完全并行，可能误导 execution dispatch 消费方。
impact: |
  execution dispatch 消费 dispatch-map 时若仅依赖 map 中的 blocked_by 字段排程，将忽略
  packet 内部的实现依赖，导致 t2 在 t5 完成前就启动（应阻塞）、t6 在 t1 完成前就启动等。
  虽然 master-plan §5a 有文字说明，但 dispatch-map JSON 本身不包含这一元数据，与 map 的
  机器可读定位不匹配。
required_fix: |
  在 dispatch-map.json 顶层增加 "dispatch_phase" 字段（值如 "planning"）和 "execution_blocked_by_note"
  说明字段，明确标注"planning blocked_by 均为空；实现依赖存于各 packet 内部 blocked_by，
  execution dispatch 需从 packet 文件中读取"。
  或：在每个 track 对象中增加 "execution_blocked_by" 字段，直接从 packet 中汇总实现依赖。
verify: |
  python3 -c "
  import json
  d = json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))
  has_phase = 'dispatch_phase' in d or 'execution_blocked_by_note' in d
  print('DISPATCH_PHASE_NOTED' if has_phase else 'DISPATCH_PHASE_MISSING')
  "
  期望: DISPATCH_PHASE_NOTED
```

---

### Finding 9 [P2] t4 在 dispatch-map 中声明 blocked_by:[] 但 packet 内 blocked_by:[t5]，与 dispatch-map wave 矩阵 w2=[t3,t4] 逻辑冲突

```yaml
severity: P2
title: t4 dispatch-map blocked_by 为空但 packet blocked_by t5，planning wave 放 w2 不一致
sc_refs:
  - SC-4
evidence: |
  dispatch-map t4 track blocked_by:[]，被放入 wave w2（与 t3 并行）（第 55-66 行）
  t4 packet §3 blocked_by: [t5-split-commands-triage]（packet 第 39 行）
  master-plan §5 表格中 T4 实现 blocked_by: T5（第 63 行）
  Planning dispatch 说明（§5a）：planning blocked_by 为空是因为各 child 只写各自 packet 文件，
  但这意味着 t4 packet 文件本身就声明了实现依赖 t5，而 dispatch-map 把 t4 和 t3 放在 w2 并行
  ——这在 planning 层是可以的（只写 packet 文件），但 packet 内 blocked_by: [t5] 说明 t4 实现
  需要 t5 先完成，与 wave 矩阵（t4 在 w2，t5 在 w3）的顺序相悖（w2 在 w3 之前）。
impact: |
  execution dispatch 重建依赖图时，发现 t4 实现 blocked_by t5 但 t5 在 wave w3（晚于 w2），
  说明规划阶段的 wave 安排与实现依赖顺序不一致。虽然 planning dispatch 只需要写 packet
  文件（不执行实现），但 wave 矩阵本应反映"如果按 wave 顺序执行实现，依赖是否满足"，
  目前 t4 implementation wave（w2）早于 t5（w3），违反 t4 blocked_by t5 的实现约束。
required_fix: |
  实现 wave 矩阵须调整，使 t4 实现 wave 在 t5 之后（或与 t5 同 wave 但 blocked_by 保证顺序）。
  最简修法：将 t4 从 w2 移到 w3 后（与 t7 同 wave，或在 t5 完成后单独一 wave）。
  或在 master-plan 备注中明确"t4 planning 可在 w2 写 packet（无文件冲突），但 execution
  必须在 t5 完成后，execution dispatch 重建时须遵 packet 内 blocked_by"，防止误读。
verify: |
  # 验证 t4 实现 wave 确实在 t5 之后（或有 blocky_by 保证）
  python3 -c "
  import json
  waves = {w['wave_id']:w['track_ids'] for w in json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['waves']}
  t4_wave = next(wid for wid,tids in waves.items() if 't4' in tids)
  t5_wave = next(wid for wid,tids in waves.items() if 't5' in tids)
  wave_order = list(waves.keys())
  t4_idx = wave_order.index(t4_wave)
  t5_idx = wave_order.index(t5_wave)
  if t4_idx > t5_idx:
      print('T4_AFTER_T5: OK')
  else:
      print(f'T4_BEFORE_T5: CONFLICT t4={t4_wave} t5={t5_wave}')
  "
  期望: T4_AFTER_T5: OK
```

---

## 4. Merge Notes

```yaml
MERGE_NOTES:
  conflict_with_other_reviewer: false
  arbitration_reason: "单 reviewer 自审，无冲突"
  degraded_reason: "REVIEW_RUN_STATUS=completed，无降级"
```

---

## 5. Residual Risk（P3 或非阻断项）

- **P3 t1 can_parallel_with 写 [t3] 但 dispatch-map wave 为 [t2]**：packet 与 map 之间的轻微不一致，可能引起混淆，建议 t1 packet §3 can_parallel_with 与 dispatch-map wave 保持一致（改为 [t2] 或确认跨 wave 并行意图并双向声明）。
- **P3 t6 SC-6.1 verify 的 SC-6.1 assertion 调用 build_capsule_text 时假设调用签名**：t6 §7 SC-6.1 assertion 硬编码了 build_capsule_text 参数位置与数量，若 T1 新增参数不带默认值则该断言失败。t6 packet 已在注释中提醒"以 T1 落地后的真实签名调整"，但这只能在实现期修正，属已知设计依赖风险。
- **P3 t7 gd-review-router.py 同时列为 t6 和 t7 owned_paths**：t6 owned_paths 含 scripts/gd-review-router.py（专门处理 target trace），t7 owned_paths 也含 scripts/gd-review-router.py（接入 controller）。虽然两次编辑的修改区域说明不重叠，但字段重叠与 owned_paths 无重叠要求冲突（属 Finding 1 的延伸，但仅涉及 router 一个文件，影响范围较小，主要问题已在 Finding 1 覆盖）。
- **P3 t9 SC-3 验证"SOURCES_EXIST"在实现前必然失败**：t9 §7 SC-3 verify 命令检查 manifest 中所有 source 路径是否存在，但在 T1-T8 实现完成前这些 source 文件不存在，该 verify 在 planning 阶段必然返回 SOURCE_MISSING。t9 packet 末段注释已说明这属预期，但 SC 验证在 planning 阶段不可独立完成，是设计固有限制。
- **P3 t2 和 t5 的 commands/review2.md 写入区域描述不够精确**：t2 owned_paths 注释"只新增送审前 gate 段"，t5 注释"入口解析改子命令"，语义上不重叠，但依赖实现者自觉遵守文字约定，无机器可验证的段落边界约束。
- **P3 dispatch-map merge_gate G3 措辞"不含裸 VERDICT/GD_REVIEW_DECISION 字段"**：按 gd-review-standard.md §8.1，task packet（planning artifact）不应出现裸 VERDICT:，但 GD_REVIEW_DECISION 在 planning artifacts 中本身就不应出现，G3 措辞把两者并列可能造成混淆（GD_REVIEW_DECISION 是 review result 字段，不是 task packet 字段）。建议 G3 只写"不含裸 VERDICT: 行"。

---

## 6. Machine-readable Result

<!-- gd-review-result-json:start -->
```json
{
  "template_kind": "gd-plan-review",
  "reviewer": "claude_subagent_plan_review",
  "review_target": "plans/gd/2026-06-08-l2-review2-redesign/master-plan.md (+ 9 packets)",
  "review_kind": "plan",
  "review_run_status": "completed",
  "gd_review_decision": "REQUIRES_CHANGES",
  "scope_checked": [
    {"facet": "master-plan 目标链完整性（SC-N 与 T-N 对应）", "result": "pass", "evidence": "§3 SC-1~SC-9 与 §5 T1~T9 一一对应"},
    {"facet": "SC verify 可执行性（规则 A）", "result": "fail", "evidence": "dispatch-map verify 仅测文件存在+TASK_GOAL，未绑顶层 SC"},
    {"facet": "实施步骤动作具体性（规则 B）", "result": "pass", "evidence": "9 packets 步骤均用具体路径/命令/函数名"},
    {"facet": "SC 至少绑定一个可验证物（规则 C）", "result": "fail", "evidence": "dispatch-map verify 未覆盖 master SC-N 内容"},
    {"facet": "task packet 自包含（规则 D）", "result": "pass", "evidence": "9 packets 均声明 required_context 无上下文指代"},
    {"facet": "owned_paths 无跨 task 重叠", "result": "fail", "evidence": "commands/review2.md 被 t2/t5/t7/t8 四 packet 列为 owned"},
    {"facet": "can_parallel_with 双向关系", "result": "fail", "evidence": "t1 声明 can_parallel_with:[t3]，t3 不含 t1"},
    {"facet": "dispatch-map waves 与 master-plan wave matrix 一致", "result": "fail", "evidence": "t4 实现 blocked_by t5 但在 wave w2（t5 在 w3）"},
    {"facet": "required_context 路径在 owned_paths 之外", "result": "pass", "evidence": "各 packet required_context 不含自身 owned_paths"},
    {"facet": "crux can_parallel_with ↔ blocked_by 一致性", "result": "fail", "evidence": "dispatch-map blocked_by 全空，packet 内有非空依赖，未区分语义层"},
    {"facet": "SC-N 与 dispatch-map sc_refs 对齐", "result": "pass", "evidence": "每个 track sc_refs 匹配对应 SC"},
    {"facet": "裸 VERDICT 残留（规则 F）", "result": "pass", "evidence": "全量 artifact 未发现行首裸 VERDICT:"},
    {"facet": "handoff result_path 非占位符", "result": "fail", "evidence": "t6/t7/t8 result_path 均为尖括号占位符"},
    {"facet": "t9 SC 编号不与 master-plan 冲突", "result": "fail", "evidence": "t9 §5 SC-1~SC-6 与 master SC-1~SC-9 命名冲突"},
    {"facet": "t6 verify cd 命令使用绝对路径", "result": "fail", "evidence": "t6 verify 含相对路径 cd 'Project GD/.clone/...' 且疑有 .clone 拼写错误"}
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "commands/review2.md owned_paths 四 task 重叠（t2/t5/t7/t8）",
      "sc_refs": ["SC-5", "SC-2", "SC-7", "SC-8"],
      "evidence": "t2:56, t5:56, t7:61, t8:59 均声明 commands/review2.md 为 owned_paths；gd-review-standard §6 要求无重叠",
      "impact": "violates gd-review-standard.md §6 owned_paths 无重叠约束；dispatch 校验器或 execution dispatch 依赖此约束防并发写冲突",
      "required_fix": "将 commands/review2.md 改为唯一 owned task（t5）；t2/t7/t8 改用 blocked_by 依赖顺序串行写，owned_paths 删除 commands/review2.md 改为 deliverables 说明",
      "verify": "python3 -c \"import json; from collections import Counter; tracks=json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['tracks']; all_owned=[p for t in tracks for p in t['owned_paths']]; dups=[p for p,c in Counter(all_owned).items() if c>1]; print('OWNED_PATHS_CONFLICT:',dups if dups else 'NONE')\"; 期望: NONE"
    },
    {
      "severity": "P1",
      "title": "t1 ↔ t3 can_parallel_with 声明不对称",
      "sc_refs": ["SC-1", "SC-3"],
      "evidence": "t1 §3 can_parallel_with:[t3]（t1 packet 第 40 行）；t3 §3 can_parallel_with:[t4]（t3 packet 第 44 行），不含 t1",
      "impact": "双向不对称违反 gd-review-standard §6 规则；execution dispatch 排程歧义；与 master-plan wave matrix（t1 在 w1，t3 在 w2）冲突",
      "required_fix": "选项 A（推荐）：删除 t1 packet can_parallel_with:[t3]，保持与 wave matrix（t1↔t2 并行）一致；选项 B：t3 补充 can_parallel_with:[t1] 且 dispatch-map 同步更新",
      "verify": "python3 -c \"import json; tracks={t['track_id']:t for t in json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['tracks']}; errors=[f'{tid}->{peer} not symmetric' for tid,t in tracks.items() for peer in t.get('can_parallel_with',[]) if tid not in tracks[peer].get('can_parallel_with',[])]; print('CAN_PARALLEL_SYMMETRIC:','PASS' if not errors else errors)\"; 期望: PASS"
    },
    {
      "severity": "P1",
      "title": "dispatch-map track verify 未绑 master-plan SC-N 内容（规则 A）",
      "sc_refs": ["SC-1", "SC-2", "SC-3", "SC-4", "SC-5", "SC-6", "SC-7", "SC-8", "SC-9"],
      "evidence": "dispatch-map.json 每个 track verify 仅 test -f + grep TASK_GOAL，未验证 master-plan §3 SC-N 实质内容（如 SC-1 的 REVIEW_LENS_EMPHASIS token、SC-2 的 DRYRUN_EVIDENCE_MISSING 逻辑）",
      "impact": "dispatch-map 无法独立验收 master-plan SC；merge gate G4 检查仅限 packet 内部 verify，不验 map 层 SC 绑定；planning 阶段顶层 SC 验收缺失",
      "required_fix": "每个 track verify 至少补充一条与 master SC-N 关键 token 绑定的命令（参照 master-plan §3 各 SC 的验收命令）",
      "verify": "python3 -c \"import json; tracks=json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['tracks']; thin=[t['track_id'] for t in tracks if len(t.get('verify',[]))<2]; print('VERIFY_THIN:',thin if thin else 'NONE')\"; 期望: NONE"
    },
    {
      "severity": "P1",
      "title": "t9 SC 编号 SC-1~SC-6 与 master-plan SC-1~SC-9 命名空间冲突",
      "sc_refs": ["SC-9"],
      "evidence": "t9 §5 第 86~95 行 SC-1~SC-6；master-plan §3 已定义 SC-1~SC-9；其他 packet 用 SC-N.M 或 SC-Na 命名子条件",
      "impact": "执行期 controller 收集各 task SC 状态时可能将 t9.SC-1 误判为 master SC-1；子 agent 引用 SC-1 时语义歧义",
      "required_fix": "将 t9 §5 SC-1~SC-6 重命名为 SC-9.1~SC-9.6；同步更新 §7 verify sc_ref 字段",
      "verify": "grep -n '^- \\[ \\] SC-[0-9]' plans/gd/2026-06-08-l2-review2-redesign/packets/t9-deploy-live.md | grep -vE 'SC-9\\.'; 期望: 无输出"
    },
    {
      "severity": "P2",
      "title": "t6 handoff_output result_path 为占位符",
      "sc_refs": ["SC-6"],
      "evidence": "t6 §8 第 153 行 result_path: <子 agent 写入 execution result 的相对路径>；t1/t2/t3/t4/t5/t9 均填具体路径",
      "impact": "子 agent 执行 t6 时无法定位 handoff 写入路径，违反自包含合约；controller 无法收集 t6 结果",
      "required_fix": "t6 result_path 改为 plans/gd/2026-06-08-l2-review2-redesign/results/t6-fix-bridge-target-result.md",
      "verify": "grep -n 'result_path:' plans/gd/2026-06-08-l2-review2-redesign/packets/t6-fix-bridge-target.md | grep -v '<'; 期望: >=1 行命中"
    },
    {
      "severity": "P2",
      "title": "t7/t8 handoff_output result_path 为占位符",
      "sc_refs": ["SC-7", "SC-8"],
      "evidence": "t7 §8 第 230 行，t8 §8 第 162 行，均为尖括号占位符",
      "impact": "与 t6 问题相同；t7/t8 子 agent 无法定位 handoff 路径",
      "required_fix": "t7: plans/gd/2026-06-08-l2-review2-redesign/results/t7-controller-baseline-convergence-result.md；t8: plans/gd/2026-06-08-l2-review2-redesign/results/t8-deliverable-packaging-result.md",
      "verify": "grep -n 'result_path:' plans/gd/2026-06-08-l2-review2-redesign/packets/t7-controller-baseline-convergence.md | grep -v '<' && echo T7_OK; grep -n 'result_path:' plans/gd/2026-06-08-l2-review2-redesign/packets/t8-deliverable-packaging.md | grep -v '<' && echo T8_OK; 期望: T7_OK T8_OK"
    },
    {
      "severity": "P2",
      "title": "t6 verify cmd 使用相对路径 cd 且含 .clone 疑似拼写错误",
      "sc_refs": ["SC-6"],
      "evidence": "t6 §7 各 verify cmd 含 cd 'Project GD/.clone/worktrees/gd-l2-parity'（第 119~141 行）；应为 .claude；其他 packet 使用绝对路径",
      "impact": "相对路径 cd 在不同 cwd 下执行失败；.clone 若为拼写错误则所有 t6 verify 在任何环境下均失败",
      "required_fix": "将所有 cd 'Project GD/.clone/...' 替换为 cd '/Users/praise/AI-Agent/Claude/projects/Project GD/.claude/worktrees/gd-l2-parity'",
      "verify": "grep -c '.clone' plans/gd/2026-06-08-l2-review2-redesign/packets/t6-fix-bridge-target.md; 期望: 0"
    },
    {
      "severity": "P2",
      "title": "dispatch-map blocked_by 全空但 packet 内有实现依赖，语义分层未标注",
      "sc_refs": ["SC-5", "SC-2", "SC-4", "SC-7", "SC-8", "SC-9"],
      "evidence": "dispatch-map.json 9 个 track 的 blocked_by 全为 []；t2/t4/t6/t7/t8/t9 packet 内 blocked_by 非空；无字段说明 planning vs execution 两层 blocked_by 的区别",
      "impact": "execution dispatch 消费方若直接读 dispatch-map blocked_by 排程，将忽略 packet 内实现依赖，导致 t2/t4/t6/t7/t8/t9 提前启动",
      "required_fix": "在 dispatch-map 顶层增加 dispatch_phase:planning 字段和说明注释；或将 packet 内实现 blocked_by 汇总到每个 track 的 execution_blocked_by 字段",
      "verify": "python3 -c \"import json; d=json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json')); print('DISPATCH_PHASE_NOTED' if 'dispatch_phase' in d or 'execution_blocked_by_note' in d else 'DISPATCH_PHASE_MISSING')\"; 期望: DISPATCH_PHASE_NOTED"
    },
    {
      "severity": "P2",
      "title": "t4 实现 blocked_by t5 但 dispatch-map wave w2（t4）早于 w3（t5）",
      "sc_refs": ["SC-4"],
      "evidence": "t4 packet §3 blocked_by:[t5]；dispatch-map waves w2=[t3,t4]，w3=[t5,t6]；w2 先于 w3",
      "impact": "execution wave 矩阵 t4 实现排在 t5 之前，违反 t4 实现依赖 t5 的约束",
      "required_fix": "调整 implementation wave 矩阵，将 t4 实现 wave 移至 t5 之后；或在 master-plan 增加注释明确区分 planning wave 和 execution wave",
      "verify": "python3 -c \"import json; waves={w['wave_id']:w['track_ids'] for w in json.load(open('plans/gd/2026-06-08-l2-review2-redesign/dispatch-map.json'))['waves']}; wave_order=list(waves.keys()); t4w=next(w for w,ts in waves.items() if 't4' in ts); t5w=next(w for w,ts in waves.items() if 't5' in ts); print('T4_AFTER_T5:OK' if wave_order.index(t4w)>wave_order.index(t5w) else f'T4_BEFORE_T5:CONFLICT t4={t4w} t5={t5w}')\"; 期望: T4_AFTER_T5:OK"
    }
  ],
  "merge_notes": {
    "conflict_with_other_reviewer": false,
    "arbitration_reason": "单 reviewer 自审，无仲裁需要",
    "degraded_reason": null
  },
  "residual_risk": [
    "P3: t1 packet can_parallel_with:[t3] 与 dispatch-map wave（t1 在 w1，t3 在 w2）不一致，建议对齐",
    "P3: t6 SC-6.1 assertion 硬编码 build_capsule_text 调用签名，T1 新增参数须带默认值否则断言失败，属已知设计依赖",
    "P3: scripts/gd-review-router.py 同时列为 t6 和 t7 owned_paths，属 Finding 1 延伸，影响较小",
    "P3: t9 SC-3 SOURCES_EXIST verify 在 planning 阶段必然返回 SOURCE_MISSING，属设计固有限制，t9 注释已说明",
    "P3: dispatch-map merge_gate G3 措辞把裸 VERDICT 与 GD_REVIEW_DECISION 并列，建议 G3 只保留裸 VERDICT 禁止"
  ],
  "timestamp": "2026-06-09T00:00:00Z"
}
```
<!-- gd-review-result-json:end -->
