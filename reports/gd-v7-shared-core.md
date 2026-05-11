# /gd v7 Shared Core 静态验收报告（Plan 2 v2）

> **Plan**：Plan 2 Shared Core 与 Review Contract v2
> **Stage**：建立 shared core；不接 runner / 不接 command / 不调 Codex
> **Marker (start)**：`reports/gd-v7-shared-core.start.marker = 2026-05-10T14:54:15Z`
> **Captured at**：2026-05-10T14:58:50Z（Step 8 验收完成时刻）

---

## 1. 新增 artifact（15 个）

| # | 路径 | 大小 | sha256（前 16） |
|---|------|------|----------------|
| 1 | `docs/gd-v7-project-goal.md` | — | 见 manifest |
| 2 | `prompts/gd-review-standard.md` | — | 见 manifest |
| 3 | `templates/gd-master-plan-template.md` | — | 见 manifest |
| 4 | `templates/gd-step-plan-template.md` | — | 见 manifest |
| 5 | `templates/gd-task-packet-template.md` | — | 见 manifest |
| 6 | `templates/gd-execution-result-template.md` | — | 见 manifest |
| 7 | `templates/gd-plan-review-template.md` | — | 见 manifest |
| 8 | `templates/gd-execution-review-template.md` | — | 见 manifest |
| 9 | `schema/gd-plan-suite.schema.json` | — | 见 manifest |
| 10 | `schema/gd-task-packet.schema.json` | — | 见 manifest |
| 11 | `schema/gd-execution-status.schema.json` | — | 见 manifest |
| 12 | `schema/gd-review-result.schema.json` | — | 见 manifest |
| 13 | `manifest.gd-v7.json` | — | — |
| 14 | `docs/gd-v7-shared-core-index.md` | — | 见 manifest |
| 15 | `reports/gd-v7-shared-core.md`（本文件） | — | — |

附 marker：`reports/gd-v7-shared-core.start.marker`

---

## 2. SC 验收表（9 条 + 4 处补丁）

| SC | 描述 | 状态 | 证据 |
|----|------|------|------|
| SC-1 | `/gd` 目标源存在且明确旧 `PROJECT_GOAL.md` 是 legacy `/rev` artifact | pass | `docs/gd-v7-project-goal.md` 第 1 节 + Plan 1 baseline `legacy_rev_goal_not_v7_authority` 字段 |
| SC-2 | 6 个模板 + review standard + 4 schema + manifest + index 全部存在 | pass | Test 1: 14 文件 PASS（15th = 本报告） |
| SC-3 | `/gd` review standard 使用 `GD_REVIEW_DECISION`，禁裸 `VERDICT:` | pass | Test 5: GD_REVIEW_DECISION × 3 + REVIEW_RUN_STATUS PASS；Test 6: 全部新增文件无裸 VERDICT |
| SC-4 | 4 schema + manifest 描述 plan suite / task packet / execution status / review result | pass | Test 7: 5 JSON `python3 -m json.tool` 全 PASS |
| SC-5 | 模板含目标链 / SC / non-goals / 边界 / 验证字段 | pass | 6 个模板文件全部含 `goal_chain` / `成功标准` / `非目标` / `边界` / `测试计划` 段；schema 强制 `required` |
| SC-6 | task packet 模板含 7 个必填字段 | pass | Test 4: owned_paths / forbidden_paths / blocked_by / can_parallel_with / required_context / deliverables / verify / handoff_output 8 字段 PASS |
| SC-7 | review standard 含 finding schema / anti-fill / merge matrix / degraded 规则 | pass | `prompts/gd-review-standard.md` 含 §2 anti-fill 6 规则 + §3 finding schema + §5 merge matrix + §7 degraded/timeout |
| SC-8 | 不修改旧 `/rev` 文件、不修改 Plan 1 baseline、不写 `~/.claude/**` | pass | Test 10: attributable=0；Test 9: Plan 1 baseline 3 hash 一致；Test 11b: 旧 `/rev` 4 hash 一致 |
| SC-9 | shared core index/report 列出全部 artifacts 与消费关系 | pass | `docs/gd-v7-shared-core-index.md` + 本报告 |
| 补丁 #1 | no-write 三层计数 raw/filtered/attributable，attributable=0 | pass | raw=8 filtered=0 attributable=0；8 个 raw 全在 `handoff/state/` 与 `handoff/active/`（codex-watch daemon 外部并发） |
| 补丁 #2 | Plan 1 baseline 3 文件 + 旧 `/rev` 4 文件哈希一致 | pass | `state-freeze.json` `c4c16d08…` / `ledger` `e3b0c442…` / `boundary-baseline.md` `bade75d3…` / `rev-review-standard.md` `6ace39fd…` / `PROJECT_GOAL.md` `9c956d44…` / `bin/rev` `825b7f78…` / `manifest.json` `3cb7573b…` 全部与 Step 1 快照一致 |
| 补丁 #3 | 裸 `VERDICT:` 检查覆盖 prompts/ + templates/ + schema/ + manifest + docs/ | pass | `grep -RnE '^VERDICT:'` 返回空 |
| 补丁 #4 | task packet `verify` 必须含命令 / 路径 / 断言 / 测试，禁"目视" | pass | `gd-task-packet.schema.json` `verify` items required `[sc_ref,method,cmd]` + method enum `[command,path,assertion,test]` + description 含 anti-fill 说明；`gd-review-standard.md` 规则 A；`gd-task-packet-template.md` 第 7 节硬约束注释 |

---

## 3. 不修改清单（实测一致）

| 文件 | sha256（前 16） | 状态 |
|------|----------------|------|
| `baselines/gd-v7-state-freeze.json` | `c4c16d089d55a7b3` | 与 Plan 1 baseline 一致 |
| `baselines/gd-v7-runtime-write-authorizations.jsonl` | `e3b0c44298fc1c14` | 与 Plan 1 baseline 一致（empty） |
| `reports/gd-v7-boundary-baseline.md` | `bade75d388762314` | 与 Plan 1 baseline 一致 |
| `prompts/rev-review-standard.md` | `6ace39fdff28b067` | 与 Plan 1 baseline `legacy_rev_standard` 一致 |
| `PROJECT_GOAL.md` | `9c956d4439005b5b` | 与 Plan 1 baseline `legacy_rev_goal_not_v7_authority` 一致 |
| `bin/rev` | `825b7f781b307366` | 与 Plan 1 baseline 一致 |
| `manifest.json` (legacy /rev terminal) | `3cb7573ba08d2336` | 与 Plan 1 baseline 一致 |
| `~/.claude/**` | — | attributable=0 |

---

## 4. ~/.claude no-write 三层计数详情（补丁 #1）

```
raw=8 filtered=0 attributable=0

raw 8 行明细（全部为 codex-watch daemon 外部并发产物）：
  /Users/praise/.claude/handoff/active/20260510T145840Z-31607.tmp_stderr
  /Users/praise/.claude/handoff/state/codex-watch.log
  /Users/praise/.claude/handoff/active/20260510T145840Z-31607.capsule
  /Users/praise/.claude/handoff/state/heartbeat
  /Users/praise/.claude/handoff/active/20260510T145840Z-31607.status
  /Users/praise/.claude/handoff/active/20260510T145840Z-31607.meta
  /Users/praise/.claude/handoff/active/20260510T145840Z-31607.tmp_stdout
  /Users/praise/.claude/handoff/active/20260510T145840Z-31607.tmp_prompt

filtered 行：empty
attributable 行：empty
```

8 个 raw 文件全部在 `handoff/state/` 与 `handoff/active/` 路径，按 Phase 4 已批准的"外部并发不归因"模型过滤后 `filtered=0`。Plan 2 v2 对 `~/.claude/**` 零写入。

---

## 5. 4 处必须补丁落地点

| # | 补丁 | 落地位置 |
|---|------|---------|
| 1 | no-write audit（marker + find newer + 三层计数） | `reports/gd-v7-shared-core.start.marker` + Step 1 创建 + Step 8 验收 + 本报告 §4 |
| 2 | Plan 1 baseline + 旧 `/rev` 哈希一致性 | Step 1 快照 + Step 8 比对（本报告 §3） |
| 3 | 裸 `VERDICT:` grep 覆盖全部新增文件 | Test 6: `grep -RnE '^VERDICT:' prompts/gd-*.md templates/gd-*.md schema/gd-*.json manifest.gd-v7.json docs/gd-v7-*.md` |
| 4 | task packet `verify` 硬约束（命令/路径/断言/测试） | `gd-task-packet.schema.json` items required + method enum + anti-fill description；`gd-review-standard.md` 规则 A；`gd-task-packet-template.md` §7 |

---

## 6. 可选补丁（已落地）

- schema `$id` 字段：4 个 schema 全部含 `https://praise.local/gd-v7/<name>.schema.json`
- review-standard anti-fill 最小规则集：6 条规则 A-F（详见 `prompts/gd-review-standard.md` §2）
- Step 1 hard-stop 包括 Plan 1 review APPROVED 检查

---

## 7. 范围声明

**本计划仅产出 shared core，未实现以下能力**：

- `/gd` slash command 注册
- `bin/gd` runner 实现
- Codex cross-review 实际接入
- Multi-agent dispatch 实际触发
- 真实 fixture 验收

以上能力分别在 Plan 3-7 中规划，本报告不声称已具备。

---

## 8. 残余风险

| 风险 | 级别 | 处置 |
|------|------|-----|
| 外部 codex-watch daemon 在 `handoff/state/`、`handoff/active/` 持续产生临时文件 | info | 不在 protected_hashes 范围；按 Phase 4 模型过滤；Plan 8 收口同样规则 |
| Plan 3+ 可能误以为 `/gd` runner 已就绪 | P3 | 本报告 §7 与 `manifest.gd-v7.json.shared_artifacts.*.consumers` 已标注每个 artifact 的"第一次被消费的 step"，避免误判 |
| 旧 `/rev` 仍可被独立运行（`bin/rev plan ...`）但与 `/gd` 链路无引用关系 | info | manifest `do_not_modify` 显式列出旧 `/rev` 文件；`/gd` 模板不引用旧 artifact；通过 review-standard §9 隔离 |

---

## 9. 下一步建议

- 用户可选择：跑 `/review code` 让 Codex 对本 Plan 做 cross-review 预演（Plan 1 v2 已演示流程）
- 待 Plan 3 启动前，无需修改本 shared core；任何修改必须通过对应 Plan 的 `boundaries.modify` 显式声明
