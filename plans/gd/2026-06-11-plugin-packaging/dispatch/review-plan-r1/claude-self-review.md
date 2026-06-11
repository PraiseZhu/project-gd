# Claude Self-Review — gd-plugin-packaging plan suite (round 1)

REVIEWER: claude_main
REVIEW_TARGET: plans/gd/2026-06-11-plugin-packaging/{master-plan.md, track-a/step-plan.md, track-b/step-plan.md} + 6 task packets
REVIEW_KIND: plan
REVIEW_RUN_STATUS: completed
GD_REVIEW_DECISION: APPROVED

> 标准源：prompts/gd-review-standard.md。穷举扫描全部 SC-001~010、6 个 task packet、各 fallback/边界。一次列全可发现 finding。

---

## SCOPE_CHECKED（覆盖 PRIMARY_TARGET 全部 SC）

| SC | 覆盖 track | 绑定 verify 可执行 | anti-fill 规则 A/C | 判定 |
|----|-----------|-------------------|--------------------|------|
| SC-001 | track-a | python json + grep marketplace one-liner | 合规 | pass |
| SC-002 | track-b | bash gd-bundle-completeness.sh --check | 合规 | pass |
| SC-003 | track-b | bash gd-plugin-cross-dir-smoke.sh | 合规 | pass |
| SC-004 | track-b | smoke --no-codex（fail-closed + 中文 + 无伪通过） | 合规 | pass |
| SC-005 | track-a | grep marketplace/plugin update + install-transport.sh | 合规 | pass |
| SC-006 | track-b | smoke --assert-data-isolated | 合规 | pass |
| SC-007 | track-b | grep 计数 = 0（排除守卫串） | 合规（见 F3） | pass-with-note |
| SC-008 | track-a | grep 无 pip + 无明文 key | 合规 | pass |
| SC-009 | track-a | grep 三件套 + 第0步前提 + 无虚假完整宣称 | 合规 | pass |
| SC-010 | track-a | gd-plugin-setup.sh --self-check（FIELDS=4/FREEFORM=0/KEY_TYPES=2/BUILTIN_KEY=0） | 合规 | pass |

全部 10 SC 覆盖、各绑可执行 verify、无 anti-fill 规则 A（仅目视确认）/C（SC 无验证物）违规；实现步骤动词均具体（创建/写/清零/改/调用），无规则 B 泛化；task packet 均自包含、无规则 D（见上文/按之前讨论）；无裸 VERDICT（规则 F）。

---

## FINDINGS

无 P1。无 P2 阻断（最高为下方 F1 的跨 track 接口依赖，已被计划显式捕获并给出 execute 期解析路径，故不升级为 P2 阻断）。

---

## Residual Risk（P3，不阻断 plan，execute 期须落实）

### F1 · HANDOFF_ROOT 默认值变更 ↔ install-transport.sh 一致性（execute 期 must-verify）
- sc_refs: SC-002 / SC-006（间接 SC-004）
- evidence: track-b/step-plan.md Step.3 改 `state-paths.sh:8` HANDOFF_ROOT 默认值；`install-transport.sh` 属 track-a 范畴、不在 track-b owned_paths；merge-report.md §3.1 已记录此接口依赖。
- impact: 若 install-transport.sh 不 source 同一 state-paths.sh（另有独立 HANDOFF 解析），daemon 部署目录与 client 解析目录不一致 → cross-review 断链（codex-send-wait 找不到 daemon）。
- required_fix（execute 期）: execute 阶段须验证 install-transport.sh 经 state-paths.sh 取 HANDOFF_ROOT；以 state-paths.sh 为 HANDOFF_ROOT 唯一真源。
- verify: `grep -q 'state-paths.sh' vendor/l3-transport/scripts/install-transport.sh`（execute 期执行）

### F2 · track-b Step.1/Step.2 引用具体行号（16-18/148/434/8/519/525/行9/行4）可能漂移
- sc_refs: SC-007
- evidence: track-b/step-plan.md Step.1/Step.2 以行号定位待清零位置。
- impact: 若执行前 commands/gd.md 被其它改动移位，行号失准 → 改错行。
- required_fix: WHAT 已同时给出语义锚点（GD_PROJECT_ROOT/GD_STANDARD/GOAL_SOURCE 行、path-traversal 守卫行）；execute 期按内容定位而非纯行号。
- verify: 改后 `grep -c '/Users/praise/AI-Agent' commands/gd.md` = 0 且 `grep -c 'CLAUDE_PLUGIN_ROOT' commands/gd.md` ≥1

### F3 · SC-007 verify 的守卫排除（grep -v '/Users/praise/.claude'）正则不精确
- sc_refs: SC-007
- evidence: verify 用 `grep -rho '/Users/praise/[A-Za-z]*'`，对 `/Users/praise/.claude` 仅能截到 `/Users/praise/`（`.` 非字母停止），随后 `grep -v '/Users/praise/.claude'` 无法据此排除。
- impact: 仅当守卫串被「保留为 /Users/praise/.claude 字面」时该排除失效 → 误报非 0。但 track-b 计划是把守卫脱用户名为 `${HOME}/.claude`，执行后命令文件内无任何 `/Users/praise` 字面 → count=0 PASS，排除项成为冗余防御。
- required_fix（非阻断）: execute 期若决定保留 `/Users/praise/.claude` 守卫字面而不脱用户名，则需把 verify 正则改为 `'/Users/praise/[A-Za-z.]*'` 或显式两段 grep。当前计划（脱用户名）下不触发。
- verify: 执行后实跑 SC-007 verify 得 PASS。

### F4 · README 落点 .claude-plugin/README.md 的插件机制可发现性是假设
- sc_refs: SC-001 / SC-009
- evidence: track-a/step-plan.md §11 假设；Claude Code 插件 README 约定位置未在本仓实证。
- impact: 若插件机制不读 `.claude-plugin/README.md`，README 仍是分发包内文档（安装者可打开），不影响命令可用性；仅影响「打开即见」体验。
- required_fix: execute 期对照插件机制约定确认落点；SC verify 已用固定路径 `.claude-plugin/README.md`，落点变更需同步 verify。

---

## MERGE_NOTES

- reviewer: claude_main 单边结论 = APPROVED（plan 层；0 P1/P2）。
- 待与 Codex cross-review（suite-controller bridge）合并：任一 reviewer REQUIRES_CHANGES/FAILED → merged = REQUIRES_CHANGES，进入 auto-fix loop ≤3 轮。
- arbitration_reason: （待 Codex 结果回来后填；若 Codex 给出 F1 之外的 P1/P2，主 agent 据 gd-review-standard §5 Merge Matrix 取更严格 verdict。）
