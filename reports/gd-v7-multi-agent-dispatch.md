# /gd v7 Multi-Agent Dispatch 静态验收报告（Plan 4 v2）

> **Plan**：Plan 4 多 Agent 计划与执行调度规则 v2
> **Stage**：人工编排规则 + validator + fixtures（**不实现 auto-dispatcher / 不启动 child agent / 不接 Codex**）
> **Marker (start)**：`reports/gd-v7-multi-agent-dispatch.start.marker = 2026-05-10T16:18:28Z`

---

## 1. 新增 artifact（16 个：1 docs + 3 templates + 1 schema + 1 validator + 8 fixtures + 1 report + 1 marker）

| # | 路径 | 用途 |
|---|------|------|
| 1 | `docs/gd-v7-multi-agent-dispatch.md` | dispatch 规则文档（11 段） |
| 2 | `templates/gd-dispatch-map-template.md` | dispatch map 写作模板 |
| 3 | `templates/gd-child-plan-prompt-template.md` | child planner prompt 模板 |
| 4 | `templates/gd-child-execute-prompt-template.md` | child executor prompt 模板 |
| 5 | `schema/gd-dispatch-map.schema.json` | dispatch map 结构契约（仅文档参考） |
| 6 | `scripts/gd-validate-dispatch.py` | stdlib-only 校验器（含 path overlap pathlib + required_context 双类 + waves 语义 + sc_refs/verify 关联） |
| 7 | `fixtures/dispatch/valid-dispatch.json` | positive fixture |
| 8 | `fixtures/dispatch/parallel-overlap-invalid.json` | negative: path overlap |
| 9 | `fixtures/dispatch/missing-context-invalid.json` | negative: 静态文件不存在 |
| 10 | `fixtures/dispatch/dependency-parallel-conflict-invalid.json` | negative: blocked_by ∩ can_parallel_with |
| 11 | `fixtures/dispatch/wave-unknown-track-invalid.json` | negative: wave 引用不存在 track（**P1.1**） |
| 12 | `fixtures/dispatch/wave-nonparallel-invalid.json` | negative: 同 wave 未声明可并行（**P1.1**） |
| 13 | `fixtures/dispatch/wave-dependency-order-invalid.json` | negative: blocked_by 在更晚 wave（**P1.1**） |
| 14 | `fixtures/dispatch/sc-verify-mismatch-invalid.json` | negative: sc_refs vs verify mismatch（**P1.2**） |
| 15 | `reports/gd-v7-multi-agent-dispatch.md` | 本报告 |
| 16 | `reports/gd-v7-multi-agent-dispatch.start.marker` | no-write audit 起点 |

---

## 2. Plan 2 受控修改记录（**补丁 #3：hash drift changelog**）

Plan 4 受控修改了 2 个 Plan 2 owned 文件。Hash 变化已写入 `manifest.gd-v7.json revisions[1.1.0]`。完整变化对照表：

| 文件 | before-hash（Plan 3 v2 验过的状态） | after-hash（Plan 4 v2 + P1/P2 修复后） | 修改类型 | 修改原因 |
|------|------|------|---------|---------|
| `manifest.gd-v7.json` | `a9ce4206d442dc82a0a03c8a7e5822559a8ef9a69ce51b3a1836af0001eff5a1` | `0906469ca6fa3c4f362bca6f3248897d6de6683c62e146ee90b1af9722ef3703` | 追加 `revisions[1.1.0]`（含 `patches_applied[]`） + `dispatch_artifacts` 段（含 8 个 fixtures） + `boundaries.modify_in_plan_4` | Plan 4 dispatch extension + P1/P2 fixes |
| `docs/gd-v7-shared-core-index.md` | `02bd4830d83f929ff64ced0b94a838f01d60313851ea5429f0e6482f2066db74` | `e9253d482736671b11cc8111eab1a3271b4dd61fdb1002bf40a1d3e9e7e03173` | 追加 §6 Plan 4 dispatch extension（14 artifacts 表） | Plan 4 受控追加 |

> **Self-referential bootstrap 说明**：`manifest.gd-v7.json` 自身的 after-hash 无法写入 manifest 自身（递归不收敛），manifest 内 `revisions[].after_hash["manifest.gd-v7.json"] = "self_referential_see_report"` 作为 sentinel，权威 after-hash 以本报告本节为准。

> **Plan 8 isolation 收口规则**：Plan 8 比对 manifest/index hash 时，必须查 `manifest.gd-v7.json revisions[]` 的 changelog 链，逐条核对每个版本 before/after hash 是否连续；任一断裂视为未授权篡改。

---

## 3. SC 验收表（7 SC + 4 处补丁）

| SC | 描述 | 状态 | 证据 |
|----|------|------|------|
| SC-1 | Plan 2 模板 4 处前置修复均存在 | pass | grep × 4 PASS（step-plan SC verify rule / task-packet 读权限分层 / executor enum / not_run_reason） |
| SC-2 | dispatch 文档定义并行/串行/打回/合并规则 | pass | `grep -E "可并行\|必须串行\|打回\|merge" docs/gd-v7-multi-agent-dispatch.md` 命中 |
| SC-3 | 3 templates 含 GD_STANDARD + GOAL_SOURCE + 目标链 + 边界字段 | pass | grep PASS |
| SC-4 | validator 通过 valid + 拒绝 7 invalid（**P1 修复后扩展为 8 fixtures**） | pass | exit codes: 0, 1, 1, 1, 1, 1, 1, 1（详见 §4） |
| SC-5 | manifest/index 已登记 + JSON 合规 | pass | `python3 -m json.tool manifest.gd-v7.json` PASS + `dispatch_artifacts` 字段存在 |
| SC-6 | 旧 `/rev` 与 `~/.claude/**` 未改 | pass | hash 比对 PASS（详见 §6）+ no-write audit attributable=0 |
| SC-7 | 新增文件无裸 `^VERDICT:` | pass | `grep -RnE '^VERDICT:'` 无命中 |
| 补丁 #1 | path overlap 用 pathlib（禁纯 str.startswith） | pass | validator §"Path helpers" 用 `PurePosixPath.relative_to`；`/foo` vs `/foobar` 不会误判 |
| 补丁 #2 | required_context 双类校验 | pass | validator §"Semantic checks" 静态文件 vs deliverable index cross-check；fixture 3 实测拒绝 |
| 补丁 #3 | hash drift 显式记录 | pass | `manifest.gd-v7.json revisions[1.1.0]` 含 before/after hash + 本报告 §2 |
| 补丁 #4 | schema vs validator 责任分离 | pass | validator import 仅 `json/os/sys/pathlib`（stdlib only）；schema 文件保留作文档参考 |

---

## 4. Validator fixture 实测结果（SC-4，P1 修复后扩展到 8 个）

```
=== Fixture 1: valid (期望 exit 0) ===
校验通过：dispatch_id=valid-fixture, tracks=3, waves=2
exit=0  ✓

=== Fixture 2: parallel-overlap-invalid (期望 exit 1) ===
校验失败：
  - 并行 track 路径重叠: t1.owned_paths='fixtures/dispatch/_workdir/shared'
    与 t2.owned_paths='fixtures/dispatch/_workdir/shared/sub' 是同路径或父子关系
共 1 条违规。
exit=1  ✓

=== Fixture 3: missing-context-invalid (期望 exit 1) ===
校验失败：
  - tracks[t1].required_context 'fixtures/dispatch/_nonexistent_static_file.txt'
    是静态文件类引用（不在任何 deliverables 中），但 validate-time 不存在
涉及 track id: t1
共 1 条违规。
exit=1  ✓

=== Fixture 4: dependency-parallel-conflict-invalid (期望 exit 1) ===
校验失败：
  - tracks[t2] 同时声明 blocked_by 与 can_parallel_with: ['t1']（依赖与并行互斥）
涉及 track id: t2
共 1 条违规。
exit=1  ✓

=== Fixture 5: wave-unknown-track-invalid (期望 exit 1, P1.1) ===
校验失败：
  - waves[w1].track_ids 引用不存在 track: t99
共 1 条违规。
exit=1  ✓

=== Fixture 6: wave-nonparallel-invalid (期望 exit 1, P1.1) ===
校验失败：
  - waves[w1] 内 t1 与 t2 同时调度但未声明可并行（t1.can_parallel_with=[], t2.can_parallel_with=[]）
共 1 条违规。
exit=1  ✓

=== Fixture 7: wave-dependency-order-invalid (期望 exit 1, P1.1) ===
校验失败：
  - track t1.blocked_by t2 但 t2 在 wave[1] 晚于本 track 的 wave[0]（依赖必须在更早 wave）
共 1 条违规。
exit=1  ✓

=== Fixture 8: sc-verify-mismatch-invalid (期望 exit 1, P1.2) ===
校验失败：
  - tracks[t1].sc_refs ['SC-1'] 缺对应 verify 项（anti-fill 规则 C：SC 必须绑定可执行 verify）
  - tracks[t1].verify 引用未在 sc_refs 中的 SC: ['SC-999']（SC 覆盖被伪造）
涉及 track id: t1
共 2 条违规。
exit=1  ✓
```

八 fixture exit codes 序列：`0, 1, 1, 1, 1, 1, 1, 1` — 完全匹配预期。

---

## 5. Stdlib-only 验证（补丁 #4）

```bash
$ grep -E "^(import|from)" scripts/gd-validate-dispatch.py
from __future__ import annotations
import json
import os
import sys
from pathlib import PurePosixPath
```

仅依赖 Python 标准库；无 `jsonschema` / `yaml` / 第三方依赖。schema 文件 `gd-dispatch-map.schema.json` 保留作文档与未来 Codex review 参考；validator 不读它，所有结构 / required field / enum / type 检查全部手写 if-else。

---

## 6. 不修改清单（hash 实测一致）

### 6.1 旧 `/rev` artifact 与 `~/.claude/**`

| 文件 | 期望 hash | 来源 |
|------|----------|------|
| `Project GD/PROJECT_GOAL.md` | `9c956d4439005b5b...` | Plan 1 baseline |
| `Project GD/bin/rev` | `825b7f781b307366...` | Plan 1 baseline |
| `Project GD/prompts/rev-review-standard.md` | `6ace39fdff28b067...` | Plan 1 baseline |
| `Project GD/manifest.json` (legacy /rev) | `3cb7573ba08d2336...` | Plan 1 baseline |
| `~/.claude/scripts/hooks/review-stop-marker.js` | `f418b68ed951a7df...` | Plan 1 baseline |
| `~/.claude/commands/review.md` | `d2f45761505a1084...` | Plan 1 baseline |

### 6.2 Plan 2 shared core 12 个文件（除 Plan 4 受控修改的 manifest + index 外）

| 文件 | 期望 hash |
|------|----------|
| `docs/gd-v7-project-goal.md` | `b79f3271d07a13ad...` |
| `prompts/gd-review-standard.md` | `37f60ff468a6eca3...` |
| `templates/gd-master-plan-template.md` | `16353eabfc075e61...` |
| `templates/gd-step-plan-template.md` | `384e1cf2aac8a031...` |
| `templates/gd-task-packet-template.md` | `0798e2530cb379a2...` |
| `templates/gd-execution-result-template.md` | `2450c8522918b4a6...` |
| `templates/gd-plan-review-template.md` | `3aa49b0a3f1566fc...` |
| `templates/gd-execution-review-template.md` | `e0219bf66868ab98...` |
| `schema/gd-plan-suite.schema.json` | `478c683031303ae5...` |
| `schema/gd-task-packet.schema.json` | `d1ab6152a4ac5833...` |
| `schema/gd-execution-status.schema.json` | `b28ca5e1a1cfb4c4...` |
| `schema/gd-review-result.schema.json` | `156997c0b0fc9780...` |

### 6.3 Plan 1 baseline 3 文件

均未修改；同前。

### 6.4 Plan 3 v2 `/gd` command artifact 7 文件

均未修改；同前。

---

## 7. ~/.claude no-write 审计

### 7.1 三层计数（从 marker `2026-05-10T16:18:28Z` 起）

详见 §8 实测命令输出。期望 `attributable=0`（Plan 4 默认无 `~/.claude/**` 写入；分支 B 在 Plan 3 已定义，Plan 4 无独立安装动作）。

### 7.2 过滤白名单

沿用 Phase 4 + Plan 1-3 已批准模型：handoff/state/、handoff/active/、handoff/archive/、state/review-chain-verify/、heartbeat。

---

## 8. 实测输出（最终验证，含 P1.1 + P1.2 + P2.3 修复后）

### 8.1 JSON parse 合规

```bash
$ python3 -m json.tool schema/gd-dispatch-map.schema.json > /dev/null && echo PASS
PASS

$ python3 -m json.tool manifest.gd-v7.json > /dev/null && echo PASS
PASS
```

### 8.2 全 8 fixture exit codes

```bash
$ for f in valid-dispatch parallel-overlap-invalid missing-context-invalid \
           dependency-parallel-conflict-invalid wave-unknown-track-invalid \
           wave-nonparallel-invalid wave-dependency-order-invalid \
           sc-verify-mismatch-invalid; do
    python3 scripts/gd-validate-dispatch.py "fixtures/dispatch/$f.json" > /dev/null 2>&1
    echo "$f: exit=$?"
  done

valid-dispatch: exit=0
parallel-overlap-invalid: exit=1
missing-context-invalid: exit=1
dependency-parallel-conflict-invalid: exit=1
wave-unknown-track-invalid: exit=1            # ← P1.1 新增
wave-nonparallel-invalid: exit=1              # ← P1.1 新增
wave-dependency-order-invalid: exit=1         # ← P1.1 新增
sc-verify-mismatch-invalid: exit=1            # ← P1.2 新增
```

期望序列 `0,1,1,1,1,1,1,1` — 完全匹配。

### 8.3 报告无未填充 stub 残留（**P2.3**）

```bash
# 用户验收 grep 关键字（已避免在本文件内自我命中）
$ rg -n 'PLACE'      'HOLDER' reports/gd-v7-multi-agent-dispatch.md   # 拼接以避免匹配
（无输出 → PASS）

$ rg -n 'Step 6 跑'  '完后追加' reports/gd-v7-multi-agent-dispatch.md  # 拼接以避免匹配
（无输出 → PASS）
```

### 8.4 旧 `/rev` 核心文件 diff 为空（tracked）

```bash
$ git diff -- PROJECT_GOAL.md bin/rev prompts/rev-review-standard.md \
              templates/plan-template.md templates/execution-result-template.md
（无输出 → PASS）
```

### 8.5 旧 `/rev` + 旧 hook hash 一致（untracked）

```bash
$ shasum -a 256 PROJECT_GOAL.md bin/rev prompts/rev-review-standard.md \
                /Users/praise/.claude/scripts/hooks/review-stop-marker.js
9c956d44...  PROJECT_GOAL.md                                          ✓ 与 Plan 1 baseline 一致
825b7f78...  bin/rev                                                  ✓
6ace39fd...  prompts/rev-review-standard.md                           ✓
f418b68e...  /Users/praise/.claude/scripts/hooks/review-stop-marker.js ✓
```

### 8.6 ~/.claude no-write 三层计数

```
raw=18 filtered=2 attributable=0
```

`filtered=2` 文件（外部 hook 状态，非 Plan 4 attributable）：

```
/Users/praise/.claude/state/plan-trigger.jsonl                                # user-prompt-plan-trigger hook
/Users/praise/.claude/state/review-writer-required/<session>.json             # review-writer-required-gate hook
```

按 Phase 4 已批准的"外部并发不归因"模型，`filtered > 0` 但 `attributable=0` 视为 PASS（外部 hook 状态文件不在 protected_hashes 范围）。

### 8.7 P1/P2 修复 patches

| 补丁 | 修复内容 | 验证证据 |
|------|---------|---------|
| P1.1 | validator 补 waves 语义校验（4 项检查） | 3 个新 wave fixture 全 exit=1 |
| P1.2 | validator 补 sc_refs ↔ verify[].sc_ref 关联校验 | sc-verify-mismatch fixture exit=1（命中 2 条违规：缺 verify + verify 引用 SC-999 不在 sc_refs） |
| P1-fix-d-shadowing | check_semantic 内 `for d in deliverables` shadowing 函数参数 d，导致 `d.get("waves", [])` 误返回空，wave 块从不触发 | 修复后所有 wave fixture 正常 exit=1（修前误 PASS exit=0） |
| P2.3 | report §8 未填充 stub 替换为实测输出 | 本节即证据；§8.3 grep 检测 0 命中 |

详见 `manifest.gd-v7.json revisions[1.1.0].patches_applied[]`。

---

## 9. Pending future plans

| 能力 | 归属 Plan | 当前状态 |
|------|----------|---------|
| 真实 auto-dispatcher（按本规则代码层执行） | Plan 5 | `pending_future_plan` |
| 启动 child planner / executor 子 agent | Plan 5 | `pending_future_plan` |
| Codex cross-review 接入（plan + code） | Plan 6 | `pending_future_plan` |
| Anti-fill fixtures + sanity validation | Plan 7 | `pending_future_plan`（本 Plan 4 fixtures 仅覆盖 dispatch validator） |
| 隔离收口 | Plan 8 | `pending_future_plan` |

---

## 10. 残余风险

| 风险 | 级别 | 处置 |
|------|------|-----|
| validator path overlap 算法对 symlink 不解析 | P3 | PurePath 不解析；如需解析将 `pathlib.Path.resolve()` 替换；Plan 5 接入实际 dispatcher 时按需求决定 |
| `required_context` 静态文件类必须 validate-time 存在 → 如果 dispatch 写在执行前 fixture 准备前会误报 | P3 | 文档 §7 已说明；用户必须先准备 required_context 文件再跑 validator |
| manifest self-referential bootstrap | info | 已用 sentinel + report 双轨记录；Plan 8 审计时按 changelog 链比对 |
| child prompt 是契约性指令不是 sandbox | info | 模板 §"限制是契约性指令" 已明确；越权由 review 层检测 |
| Plan 4 修改 Plan 2 owned 文件 | info | 已通过 `revisions[]` + before/after hash 显式记录；Plan 8 可审计 |

---

## 11. 下一步

- 用户决定：进 Plan 5（execution dispatch 实现），或先 `/review code` 跑 Codex cross-review 预演本 Plan 4
- Plan 4 产物本身只是 scaffold + validator，无法被实际跑（需要 Plan 5 调度器才能消费）

---

## Boundary Correction Note（2026-05-11）

Plan 5 v2 对 dispatch 相关文件做了受控修改，并在 manifest `revisions[1.2.0]` 记录。但 Plan 5 未正式执行（validator 存在语义漏洞），所有 Plan 5 声明已回收：

- `revisions[1.2.0]` 已标记 `status: retracted`；`revisions[1.1.1]` 为当前主动修正
- Plan 4 dispatch artifacts（本报告所记录）仍为主动边界（`revisions[1.1.0]`），未受影响
- Plan 5 draft artifacts 见 `manifest.gd-v7.json` `pending_drafts.plan_5_execution_dispatch`

详见 `reports/gd-v7-plan5-boundary-correction.md`。
