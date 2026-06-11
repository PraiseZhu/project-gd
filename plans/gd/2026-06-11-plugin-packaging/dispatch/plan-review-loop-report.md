# /gd review plan — Loop Report（gd-plugin-packaging）

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-plan-review-loop-report

review_target_set: master-plan.md + track-a/step-plan.md + track-b/step-plan.md（+ 7 task packets）
reviewers: claude_main（self-review）+ codex（cross-review，live transport，每轮 transport_ok 真实往返）
loop_budget: H2a 3 轮 + 用户显式授权 +2 轮 = 5 轮 fix；末轮 SC-007 grep 一致性修复未再 review（预算用满）
FINAL_STATUS: auto_fix_exhausted（内容 finding 全收敛；suite clean APPROVED 受工具 artifact 阻断）
GD_REVIEW_DECISION: REQUIRES_CHANGES（按合约不伪造 APPROVED）

---

## 1. 逐轮记录（6 轮 Codex 真实双审）

| round | target | Codex verdict | findings | 处置 |
|-------|--------|---------------|----------|------|
| 1 | master/track-a/track-b | master=APPROVED(degraded) / track-a=REQUIRES_CHANGES / track-b=REQUIRES_CHANGES | track-a 4×P2；track-b 1×P2；master degraded-artifact | auto-fix #1 |
| 2 | master/track-a/track-b | master+track-a=APPROVED(degraded) / track-b=REQUIRES_CHANGES | track-b 2×P2 | auto-fix #2 |
| 3 | track-b | REQUIRES_CHANGES | 1×P1 + 2×P2 | auto-fix #3（H2a 预算尽） |
| — | — | 用户授权 +2 轮修 SC-007 | — | — |
| 4 | track-b | REQUIRES_CHANGES | 1×P1 + 1×P2 | auto-fix #4（+2 第1轮） |
| 5 | track-b | REQUIRES_CHANGES | 2×P1 + 1×P2 | auto-fix #5（+2 第2轮） |
| 6 | track-b | REQUIRES_CHANGES | 1×P1（SC-007 grep 一致性/闭环） | auto-fix #6 一致性修复，**未再 review（预算用满）** |

> track-a 自 round-2 起、master 全程 = Codex 内容 APPROVED（仅 degraded-artifact）。track-b 内容经 6 轮收敛，finding 从结构性 → SC verify 精度 → grep 形式一致性，逐层缩小。

## 2. 已修复 findings 全集（~14 条真实 finding）

- **track-a（round-1，4×P2）**：SC-001 verify 加命令入口声明断言；§7 task packet 补全 7 字段；SC-005 加 marker 块计数 ≤3；SC-009 加两段 marker 分段断言。
- **track-b（round-2，2×P2）**：HANDOFF 一致性写死（install-transport.sh 纳入 t2，source 同一 state-paths.sh）；SC-003 smoke 改 fixture codex-send-wait 真调 writer 产实文件。
- **track-b（round-3，1×P1+2×P2）**：**P1** SC-007 verify 排除式 grep -v 漏判 .claude → 改直接 fail on /Users/praise/(AI-Agent|.claude) + 守卫断言；自循环 required_context 去 owned；§11 install-transport 归属矛盾修正。
- **track-b（round-4，1×P1+1×P2）**：**P1** SC-007 verify 范围 < 成功标准 → 扩到分发物运行时清单；§9 风险表残留排除式描述清除。
- **track-b（round-5，2×P1+1×P2）**：**P1** SC-007 scan 命中 scripts 但无清零任务 → 新增 t4 deusername-script-guards 清 5 validator 守卫；**P1** SC-007 漏扫 plist/extensionless bin → grep 改全文件类型 + plist 纳入 t2（占位符化由 install-transport 渲染）；**P2** /review1 的 codex-consult.sh（L1）未接 HANDOFF → 纳入 t2 source state-paths.sh。
- **track-b（round-6，1×P1）**：SC-007 grep 形式不一致（§10 残留 --include 漏 plist/bin）→ 全计划统一为 `grep -rEnI ... commands scripts vendor/l3-transport --exclude=<P3作废脚本>`（递归覆盖 scripts+handoff/bin+handoff/lib+launchagents），加清单↔扫描↔owned 闭环说明。**此条为一致性收尾，已应用但未再跑 Codex（+2 预算用满）。**
- **master（round-2 缓解）**：§3 加 SC 去零别名（缓解 L3 校验器对 "SC-001~010" range 的 FAKE_EVIDENCE；改变失败模式但未根除——见 §3 工具约束）。

## 3. 关键工具约束（systemic，根因，非计划缺陷）

**L3 content-evidence 校验器 与 Codex 干净 APPROVED 互斥**：校验器要求 Codex review 的 SCOPE_CHECKED 列出 target 内 SC-ID；Codex 对好计划给 APPROVED+0 findings 时 SCOPE_CHECKED 往往简短/无逐条 SC-ID → `FAKE_EVIDENCE_DETECTED` → degraded → 按 §7 degraded→FAILED 不得 APPROVED。后果：**计划越干净越拿不到 clean APPROVED**（master、track-a 即此）。plan 编辑无法消除；根治需改 review 机制（L3 校验器 SC-ID 提取/归一 或 Codex review 模板），属 docs/constitution.md 范畴、不在本封装 spec。prior 佐证：observations 1808-1810。

## 4. 终态与建议

- **dual-review 内容结论**：master=Codex APPROVED；track-a=Codex APPROVED（4 findings 全修）；track-b=内容经 6 轮全部 finding 已 addressed（round-6 一致性修复未再 review）。Claude self-review 各轮均 APPROVED（0 P1/P2）。
- **suite 级**：FAILED / auto_fix_exhausted —— 受 §3 工具约束（内容干净却 degraded）阻断，非内容缺陷。
- **不伪造**：未输出仅 Claude 的 APPROVED；未把 degraded 当通过（守 closure_ineligible + gd-review-standard §5/§7）。
- **plan 质量**：经 6 轮 Codex 对抗式审查大幅加固（修掉 1 个我引入的 P1 verify bug、HANDOFF 一致性、smoke 造假、validator 守卫失效、plist/bin/L1 覆盖缺口、grep 形式不闭环等——单审兜不住）。
- **建议下一步（待用户定）**：
  1. 接受当前计划进入 /gd execute（剩余仅工具 artifact + 1 条已应用未再审的 grep 一致性，不阻断实质执行）；
  2. 或再授权 1 轮 Codex 复审确认 round-6 一致性修复 + track-b 收敛；
  3. §3 工具约束单开 review-机制修复项（改 L3 校验器或 Codex 模板），不混入本封装 spec。
- **worktree 未并回**：计划产物在 worktree `plugin-packaging-plan`，已 git add（可提交态）未 commit；/gd execute 前需并回 feat/plugin-packaging。
