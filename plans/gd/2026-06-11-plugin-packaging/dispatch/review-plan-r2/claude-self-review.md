# Claude Self-Review — gd-plugin-packaging plan suite (round 2, post auto-fix)

REVIEWER: claude_main
REVIEW_TARGET: plans/gd/2026-06-11-plugin-packaging/{master-plan.md, track-a/step-plan.md, track-b/step-plan.md} + task packets
REVIEW_KIND: plan
REVIEW_RUN_STATUS: completed
GD_REVIEW_DECISION: APPROVED

> round-1 Codex findings 已逐条 auto-fix；本轮确认修复落实且未引入新 P1/P2。

---

## round-1 Codex findings → round-2 修复核对

| 来源 | finding | 修复 | 落点 |
|------|---------|------|------|
| track-a P2 #1 | SC-001 验证弱化为文档存在检查 | SC-001 verify 增加 plugin.json 声明三链路命令入口断言（CMDS_DECLARED）+ 明示端到端命令可见由 SC-003 冒烟+reload 覆盖 | track-a §4 SC-001、task-packets/gd-plugin-scaffold-manifests §7 |
| track-a P2 #2 | Task Packet 缺强制字段 | §7 改为每 packet 列全 7 字段（owned/forbidden/required_context/blocked_by/can_parallel/deliverables/verify）+ 指向完整 packet 文件 | track-a §7 |
| track-a P2 #3 | SC-005 没验证"≤3 条命令" | README 更新命令块加 marker `gd-update-commands:start/end`，verify 用 awk 抽块内命令行计数 ≤3 | track-a §4 SC-005、Step.3、task-packets/gd-plugin-install-readme §7 |
| track-a P2 #4 | SC-009 未验证"两段式不混淆" | README 用 marker `gd-install-section`/`gd-transport-prereq-section`，verify 断言两段存在 + 三件套只在前置段 | track-a §4 SC-009、Step.3、task-packets/gd-plugin-install-readme §7 |
| track-b P2 #1 | Task Packet 缺必填交付与验证字段 | §7 改为每 task_id 列全 7 字段，verify 绑定 §4/§10 已列命令 | track-b §7 |
| master degraded | FAKE_EVIDENCE: scope_checked SC-1 不在 target（Codex 用 "SC-001~010" range，校验器零填充归一为 SC-1） | master §3 加 SC 归一别名说明（SC-1…SC-10 等价），使去零 ID 在 target 内可被校验器匹配 | master §3 |

---

## SCOPE_CHECKED（全 10 SC 复扫）

| SC | verify 强度（round-2 后） | 判定 |
|----|--------------------------|------|
| SC-001 | manifest 命令入口声明 + 单行命令 + 无 version（三段断言） | pass |
| SC-002 | bundle-completeness --check（八类含 vendor/l3-transport） | pass |
| SC-003 | 跨目录冒烟（mktemp 非 GD repo） | pass |
| SC-004 | smoke --no-codex（fail-closed + 中文 + 无伪通过） | pass |
| SC-005 | marker 块内命令计数 ≤3（awk 抽取） | pass（强化） |
| SC-006 | smoke --assert-data-isolated | pass |
| SC-007 | grep 计数 = 0，正则 `[A-Za-z.]*` 稳健排除守卫串 | pass（强化，并修掉 round-1 自审 F3） |
| SC-008 | grep 无 pip + 无明文 key | pass |
| SC-009 | 两段 marker + 三件套只在前置段（awk 分段断言） | pass（强化） |
| SC-010 | setup --self-check（FIELDS=4/FREEFORM=0/KEY_TYPES=2/BUILTIN_KEY=0） | pass |

---

## FINDINGS

无 P1。无 P2。round-1 全部 P2 已修。

## Residual Risk（P3，execute 期落实，不阻断 plan）

- F1（保留自 round-1）：HANDOFF_ROOT 默认值变更须与 install-transport.sh 经同一 state-paths.sh 对齐——execute 期 must-verify（`grep -q 'state-paths.sh' vendor/l3-transport/scripts/install-transport.sh`）。
- F2（保留自 round-1）：track-b 行号锚点可能漂移——execute 期按内容定位（GD_PROJECT_ROOT/守卫行）而非纯行号。
- F4（保留自 round-1）：README 落点 `.claude-plugin/README.md` 的插件机制可发现性是假设——execute 期对照插件约定确认；SC verify 用固定路径，落点变更需同步。
- （round-1 F3 已在 round-2 修复：SC-007 正则改 `[A-Za-z.]*`。）

## MERGE_NOTES

- reviewer: claude_main round-2 = APPROVED（0 P1/P2）。
- 待与 round-2 Codex cross-review 合并；任一 REQUIRES_CHANGES/FAILED → 继续 auto-fix（剩余预算：本轮为第 2 轮，最多至第 3 轮）。
