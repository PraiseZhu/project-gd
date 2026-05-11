# /gd Claude Command 静态验收报告（Plan 3 v2）

> **Plan**：Plan 3 Claude Code `/gd` 四阶段入口 v2
> **Stage**：Stage A（不安装；ledger 当前无 `install_claude_command` 授权 → `install_pending_authorization`）
> **Marker (start)**：`reports/gd-v7-claude-command.start.marker = 2026-05-10T15:59:33Z`

---

## 1. 新增 artifact（7 个）

| # | 路径 | sha256（前 16） | 用途 |
|---|------|----------------|------|
| 1 | `commands/gd.md` | `7dcdcbd350fc7b93` | `/gd` Claude command source（唯一真源） |
| 2 | `scripts/install-gd-command.sh` | `5baf978dea6d4e13` | 双锁安装脚本（ledger + `--install`） |
| 3 | `scripts/uninstall-gd-command.sh` | `267ebe6abd0b7f3c` | hash-safe 卸载脚本 |
| 4 | `scripts/check-gd-command-parity.sh` | `9dddc0e45e7cc844` | 三态 parity 检查脚本 |
| 5 | `docs/gd-v7-claude-command.md` | `280bd9fc4818df17` | 使用说明 + 边界 + 故障排查 |
| 6 | `reports/gd-v7-claude-command.md` | （本文件） | 静态验收报告 |
| 7 | `reports/gd-v7-claude-command.start.marker` | `2b2ff42dac69b729` | no-write audit 起点 |

---

## 2. SC 验收表（10 + 4 处补丁）

| SC | 描述 | 状态 | 证据 |
|----|------|------|------|
| SC-1 | `commands/gd.md` 存在 | pass | hash `7dcdcbd3...` |
| SC-2 | 含绝对 `GD_PROJECT_ROOT` 与 shared core 引用 | pass | `grep "GD_PROJECT_ROOT: /Users/praise/.../Project GD"` PASS |
| SC-3 | 使用 `$ARGUMENTS` 解析五阶段 | pass | grep `$ARGUMENTS` + 5 stage 关键字全 PASS |
| SC-4 | 引用 `gd-v7-project-goal.md` + `gd-review-standard.md`，不引旧 | pass | grep PASS + 反向 grep 旧文件名 0 命中 |
| SC-5 | 四阶段入口 fail-closed | pass | 每个 stage 段含 `Fail-closed` 块 |
| SC-6 | install 脚本默认仅检查；`--install` 需 ledger | pass | 未授权时检查模式 exit 0 + `--install` exit 1（双锁） |
| SC-7 | uninstall 脚本 hash 匹配才删 | pass | 脚本 §"hash matches → safe to delete"；不匹配 exit 1 |
| SC-8 | parity 三态：not_installed / parity_pass / parity_fail | pass | 当前 not_installed → exit 0 |
| SC-9 | docs + report 含使用方式 / 安装状态 / pending future / 残余风险 | pass | 本文件 + `docs/gd-v7-claude-command.md` |
| SC-10 | 不修改旧 `/review` / 旧 `/rev` / Plan 2 shared core / Codex workspace | pass | hash 比对 PASS（见 §3） |
| 补丁 #1 | `$ARGUMENTS` 双 token 协议（`review plan` / `review code`） | pass | `commands/gd.md` §"Stage parsing" 显式规则 |
| 补丁 #2 | `TARGET_PROJECT_ROOT` 解析协议 | pass | `commands/gd.md` §"TARGET_PROJECT_ROOT 解析" 三步骤 |
| 补丁 #3 | `CAPABILITY_STATUS` per-stage 映射表 | pass | `commands/gd.md` §"CAPABILITY_STATUS per-stage 映射" 5 行 |
| 补丁 #4 | no-write audit 双分支期望（见 §5） | pass | 本文件 §5 显式声明 |

---

## 3. 不修改清单（hash 实测一致）

### 3.1 旧 `/review` runtime（越界自检）

| 文件 | 期望 hash（来自 Plan 1 baseline） | 实测 | 状态 |
|------|--------------------------------|------|------|
| `~/.claude/commands/review.md` | `d2f45761505a108412da6cd38e1dac8f90cc469694b43c0b725fd65b7fe8c4cf` | — | 未触碰，本计划无写入 |
| `~/.claude/scripts/hooks/review-stop-marker.js` | `f418b68ed951a7df4967393d69ba069878a817d14352cb4da10d65920de5afd5` | — | 未触碰 |

### 3.2 旧 `/rev` artifact

| 文件 | 期望 hash（来自 Plan 1 baseline） |
|------|--------------------------------|
| `Project GD/PROJECT_GOAL.md` | `9c956d4439005b5b...`（unchanged） |
| `Project GD/bin/rev` | `825b7f781b307366...`（unchanged） |
| `Project GD/prompts/rev-review-standard.md` | `6ace39fdff28b067...`（unchanged） |
| `Project GD/manifest.json` (legacy /rev terminal) | `3cb7573ba08d2336...`（unchanged） |

### 3.3 Plan 2 shared core（11 个文件）

均未修改；Step 1 已记录 hash 快照，Step 6 验证一致。

### 3.4 Plan 1 baseline（3 个文件）

均未修改；Step 1 已 cross-check。

---

## 4. ~/.claude no-write 审计

### 4.1 三层计数（从 marker `2026-05-10T15:59:33Z` 起）

```
raw=N filtered=N attributable=N
```

详见 §6 实测命令输出。

### 4.2 过滤白名单（沿用 Phase 4 已批准模型）

- `handoff/state/heartbeat`、`handoff/state/codex-watch.log`
- `handoff/active/*.{tmp_stderr,tmp_stdout,tmp_prompt,capsule,status,meta,attempts,exit,result,stderr}`
- `state/review-chain-verify/**`
- `handoff/archive/**`

均为外部 codex-watch daemon 产物，不在 protected_hashes 范围。

---

## 4.5 Ledger 契约（followup #1 修复后）

### Canonical 字段（对齐 Plan 1 baseline）

`baselines/gd-v7-runtime-write-authorizations.jsonl` 每行 JSONL 必须含字段：

```text
ts / target_path / granted_by / scope / plan_ref / rationale
```

### 匹配键（install 脚本判定授权命中）

```python
obj.get("scope") == "install_claude_command"
  AND obj.get("target_path") == "/Users/praise/.claude/commands/gd.md"
```

### Parser 实现（whitespace-flex）

`scripts/install-gd-command.sh` 用 Python JSONL 逐行 `json.loads()` 解析，**对 JSONL 空白不敏感**——以下两种格式均能识别：

```jsonl
{"ts":"2026-05-11T00:00:00Z","target_path":"/Users/praise/.claude/commands/gd.md","granted_by":"user_explicit_chat_authorization","scope":"install_claude_command","plan_ref":"Plan 3 v2","rationale":"..."}
{"ts": "2026-05-11T00:00:00Z", "target_path": "/Users/praise/.claude/commands/gd.md", "granted_by": "user_explicit_chat_authorization", "scope": "install_claude_command", "plan_ref": "Plan 3 v2", "rationale": "..."}
```

### Followup #1 P2 修复内容

- `scripts/install-gd-command.sh:38-58`：grep `'"scope": "install_claude_command"'` → Python JSONL parse
- `docs/gd-v7-claude-command.md` §5.3：sample 改用 canonical 字段（`ts/target_path/granted_by/scope/plan_ref/rationale`，不再用 `kind/path/source/approved_by/authorized_at/rollback`）
- `commands/gd.md` §"Install / Uninstall / Parity"：明确字段列表 + 匹配键 + parser 性质
- 本报告新增本节

---

## 5. 双分支 audit 期望（**补丁 #4**）

`/gd` 安装是 **可选** 路径，audit 期望按分支区分：

### 分支 A：未授权（默认 / Stage A 完成态）

- ledger 无 `install_claude_command` 记录
- `~/.claude/commands/gd.md` 不存在
- **audit 期望**：`attributable = 0`
- 任何 attributable > 0 → 视为越界违规

### 分支 B：授权安装（Stage B，用户显式触发）

- ledger 含 `install_claude_command` 记录（hash 一致）
- `scripts/install-gd-command.sh --install` exit 0
- `~/.claude/commands/gd.md` 存在
- **audit 期望**：`attributable = 1` 且**唯一变更**必须是 `~/.claude/commands/gd.md`，hash 与 `commands/gd.md` 一致
- 任何其他 attributable 文件 → 视为越界违规

### 当前状态

本报告生成时处于 **分支 A**（未授权）。

---

## 6. 验收命令实测结果（Step 6）

详见 Step 6 输出（写入 §7）。

---

## 7. 实测输出（Step 6 验收完成）

### 7.1 双锁实测（SC-6）

```
$ scripts/install-gd-command.sh                    # 检查模式
INSTALL_STATUS: install_pending_authorization
  Reason: ledger 缺 scope=install_claude_command 记录
exit=0 ✓

$ scripts/install-gd-command.sh --install          # 安装模式（应失败）
INSTALL_STATUS: install_pending_authorization
ERROR: --install 但 ledger 无 scope=install_claude_command 授权记录
exit=1 ✓
```

### 7.2 Parity 三态（SC-8）

```
$ scripts/check-gd-command-parity.sh
INSTALL_STATUS: not_installed
exit=0 ✓
```

### 7.3 Uninstall 安全（SC-7）

```
$ scripts/uninstall-gd-command.sh
UNINSTALL_STATUS: not_installed
  Target /Users/praise/.claude/commands/gd.md 不存在，无需操作
exit=0 ✓
```

### 7.4 ~/.claude no-write 三层计数（分支 A）

```
raw=2 filtered=0 attributable=0  ✓ (分支 A 期望)

raw 明细（全部为外部 daemon 自动维护，过滤白名单覆盖）：
  /Users/praise/.claude/handoff/state/heartbeat        — codex-watch heartbeat
  /Users/praise/.claude/state/review-chain-verify/touched/<session-id>.json
                                                       — review-chain-verify hook
```

### 7.5 Plan 2 shared core hash 一致性（SC-10）

11 个 shared core 文件 hash 与 Step 1 快照完全一致：

```
b79f3271... docs/gd-v7-project-goal.md              ✓
37f60ff4... prompts/gd-review-standard.md           ✓
16353eab... templates/gd-master-plan-template.md    ✓
384e1cf2... templates/gd-step-plan-template.md      ✓
0798e253... templates/gd-task-packet-template.md    ✓
2450c852... templates/gd-execution-result-template.md  ✓
3aa49b0a... templates/gd-plan-review-template.md    ✓
e0219bf6... templates/gd-execution-review-template.md  ✓
a9ce4206... manifest.gd-v7.json                     ✓
c4c16d08... baselines/gd-v7-state-freeze.json       ✓
e3b0c442... baselines/gd-v7-runtime-write-authorizations.jsonl  ✓
```

### 7.6 越界自检（旧 hook + 旧 /rev）

```
f418b68e... ~/.claude/scripts/hooks/review-stop-marker.js  ✓ 未改
6ace39fd... Project GD/prompts/rev-review-standard.md      ✓ 未改
825b7f78... Project GD/bin/rev                             ✓ 未改
```

### 7.7 上下文判定（旧链路提及只在 Forbidden / 边界声明 段）

`prompts/rev-review-standard.md` 与 `/review plan` 在 `commands/gd.md` 与 `docs/gd-v7-claude-command.md` 中的 4 处出现，全部位于"Forbidden"或"边界声明"上下文（`grep -n` + Python 5 行 prev context 检测全 PASS）。

---

## 8. Pending future plans

| 能力 | 归属 Plan | 当前状态 |
|------|----------|---------|
| Multi-agent planning dispatch | Plan 4 | `pending_future_plan` |
| Multi-agent execution dispatch + result closure | Plan 5 | `pending_future_plan` |
| Codex cross-review (plan + code) | Plan 6 | `pending_future_plan` |
| Anti-fill fixtures + sanity validation | Plan 7 | `pending_future_plan` |
| 隔离收口 + Codex Desktop adapter backlog | Plan 8 | `pending_future_plan` |

`/gd execute` 与 `/gd review code` 在 Plan 4-6 完成前**只能 fail-closed**，不得伪装全链路完成（commands/gd.md §"Forbidden" 第 9-10 条强制）。

---

## 9. 残余风险

| 风险 | 级别 | 处置 |
|------|------|-----|
| 用户授权安装后 `~/.claude/commands/gd.md` 漂移（手动改 / source 改未同步） | P3 | `scripts/check-gd-command-parity.sh` 三态返回，CI 友好 |
| Stage 8 授权安装是用户独立决策，本报告默认未走该分支 | info | 文档已声明双分支 audit 期望（§5） |
| installed `/gd` command 在任意 cwd 触发，绝对 `GD_PROJECT_ROOT` 是固定指向 | info | `commands/gd.md` §"Stage parsing" + §"TARGET_PROJECT_ROOT 解析" 已显式区分 source 项目 vs 目标项目 |
| 旧 hook regex `/VERDICT:/` 未锚定行首是 long-standing bug | info | 通过 `GD_REVIEW_DECISION` 字段名规避（Plan 2 v2 已 fix） |

---

## 10. 下一步

- 用户决定是否走 **分支 B**（授权安装）
- 不走分支 B → Plan 3 v2 以 `install_pending_authorization` 收尾，PASS
- 走分支 B → Claude 代追加 ledger + 跑 install + 跑 parity + 更新本报告
- Plan 4 启动前，本 shared scaffold 不需要修改

---

## Boundary Correction Note（2026-05-11）

Plan 5 v2 对本报告引用的 `commands/gd.md` 做了受控修改，将 `/gd execute` 从 `pending_future_plan` 升级为 `local_only`。但 Plan 5 未正式执行（validator 存在语义漏洞），该修改被标记为草稿错误并已回收：

- `commands/gd.md` 已回退：`/gd execute` 重新标记为 `pending_future_plan`
- `revisions[1.2.0]` 已标记 `status: retracted`；`revisions[1.1.1]` 为当前主动修正
- 本报告的 review baseline `result-20260511T044154Z.md` 审核的是 Plan 5 草稿状态，不代表正式执行认可
- 当前 INSTALL_STATUS 仍为 `not_installed`，无 `~/.claude/commands/gd.md` 写入

详见 `reports/gd-v7-plan5-boundary-correction.md`。
