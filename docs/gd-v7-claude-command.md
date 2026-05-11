# /gd Claude Code Command — 使用说明

> **Owner Plan**：Plan 3 v2（命令 scaffold）；Plan 4（multi-agent dispatch 接入）；Plan 5 v5（execution dispatch human_exec 接入）
> **Source**：`Project GD/commands/gd.md`
> **Installed location**（仅授权后）：`/Users/praise/.claude/commands/gd.md`
> **Status**：Plan 5 v5 — multi-agent planning dispatch（Plan 4）与 execution dispatch human_exec（Plan 5 v5）已接入 local_only；Codex cross-review 在 Plan 6 接入

---

## 1. 这是什么

`/gd` 是 Claude Code 中 Goal-Driven 多 Agent 主链路的**唯一入口**。当前阶段（Plan 5 v5）已上线四阶段入口 + multi-agent dispatch + execution dispatch (human_exec) + 中文命令别名（Plan 6.5-A）；后续 Plan 6/7/8 会接入：

- Plan 4：Multi-agent planning dispatch
- Plan 5：Multi-agent execution dispatch + result closure
- Plan 6：Codex cross-review sidecar

`/gd` **不替代** 旧 `/review`：`/review` 仍然可用且独立运行。`/gd` 与 `/review` 通过命令名隔离（不共享 hook、不共享 verdict 字段名）。

---

## 2. 五个 stage

| 中文命令 | 英文命令 | 用途 | Plan 5 v5 阶段 CAPABILITY_STATUS |
|---------|---------|------|----------------------------|
| `/gd 帮助` | `/gd help` | 输出帮助 | `active` |
| `/gd 计划` | `/gd plan` | 生成 master/step plan + task packets | `local_only`（multi-agent 拆分在 Plan 4） |
| `/gd 审计划` | `/gd review plan` | Claude 本地 review plan | `local_only`（Codex cross-review 在 Plan 6） |
| `/gd 执行` | `/gd execute` | 执行 batch + closure validator（human_exec） | `local_only`（Plan 5 v5 已上线；agent_exec 仍 pending） |
| `/gd 审代码` | `/gd review code` | 静态字段校验 + 后续接 Codex review | `pending_future_plan`（Codex cross-review 在 Plan 6） |

中英文命令严格等价（Plan 6.5-A 加入中文别名）。中文别名为**严格白名单**：未在表中列出的中文 token（如 `审查`/`复审`/`运行`/`查看` 等）一律降级到 `/gd help`，**不执行任何写操作**。

未识别英文 stage（如 `/gd foo`）→ 同样降级为 `/gd help`，**不执行任何写操作**。

---

## 3. 双 token 解析（重要）

英文路径：`/gd review` **不可单独使用**，必须带第二 token：

- ✅ `/gd review plan`
- ✅ `/gd review code`
- ❌ `/gd review` — 输出 help，不执行

中文路径（Plan 6.5-A v2）：`审计划` / `审代码` 是**单 token 别名**，**只停止 stage 判定**，但 `tokens[1:]` 全部保留为 `remaining_args` 传给 stage handler：

- ✅ `/gd 审计划`（`stage=review plan`, `remaining_args=[]`）
- ✅ `/gd 审代码`（`stage=review code`, `remaining_args=[]`）
- ✅ `/gd 审计划 /abs/plan.md`（`stage=review plan`, `remaining_args=["/abs/plan.md"]`）
- ✅ `/gd 审代码 --target /abs/repo`（`stage=review code`, `remaining_args=["--target", "/abs/repo"]`）
- ✅ `/gd 计划 --target /abs/repo`（`stage=plan`, `remaining_args=["--target", "/abs/repo"]`）
- ❌ `/gd 审` — 不在白名单 → 输出 help，不写文件
- ❌ `/gd 审查` — 不在白名单（同义词不模糊匹配）→ 输出 help，不写文件
- ❌ `/gd 审 计划` — 第一 token `审` 不在白名单 → 输出 help（即使第二 token 合法）

详见 `commands/gd.md` §"Stage parsing ($ARGUMENTS)"。

---

## 4. TARGET_PROJECT_ROOT 解析

`/gd plan` / `/gd execute` / `/gd review code` 需要确定**目标项目**（被 plan / execute / review 的项目，可能不是 Project GD）：

1. **显式优先**：`--target <绝对路径>`
2. **否则用 cwd**：当前 `pwd` 必须是 git repo 顶层 **且** 不等于 `GD_PROJECT_ROOT`
3. 不满足 → 停止并要求 `--target`

`/gd review plan` 与 `/gd help` 不需要 `TARGET_PROJECT_ROOT`。

---

## 5. 安装 / 卸载 / Parity

### 5.1 默认状态

Plan 3 v2 完成后默认 **不安装**。`/gd` 命令在 Claude Code 不可见，直到执行授权安装。

### 5.2 检查当前状态

```bash
cd "/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project GD"
scripts/install-gd-command.sh           # 仅检查
# 输出 INSTALL_STATUS: install_pending_authorization | ready_to_install | installed_parity_pass | install_blocked_hash_mismatch
```

### 5.3 授权 + 安装（用户显式触发）

**前置**：用户必须在对话中显式说"安装 /gd command"或等价请求。

**步骤**：

1. **追加授权 ledger**（Claude 代为追加，使用 Plan 1 baseline canonical 字段：`ts / target_path / granted_by / scope / plan_ref / rationale`）：

   ```jsonl
   {"ts":"<ISO-8601, e.g. 2026-05-11T00:00:00Z>","target_path":"/Users/praise/.claude/commands/gd.md","granted_by":"user_explicit_chat_authorization","scope":"install_claude_command","plan_ref":"Plan 3 v2","rationale":"用户在对话中明确授权安装 /gd Claude command; source=Project GD/commands/gd.md; rollback=Project GD/scripts/uninstall-gd-command.sh"}
   ```

   字段说明：
   - `ts`：授权时刻 ISO-8601
   - `target_path`：精确匹配 `/Users/praise/.claude/commands/gd.md`（install 脚本按此键比对）
   - `granted_by`：固定 `user_explicit_chat_authorization`（标识用户在对话中显式授权）
   - `scope`：精确匹配 `install_claude_command`（install 脚本按此键比对）
   - `plan_ref`：触发授权的 plan 名称
   - `rationale`：自由文本说明（推荐附带 source/rollback 路径便于审计）

   `install-gd-command.sh` 用 Python JSONL 解析，**对空白不敏感**（minified 与 spaced 两种 JSONL 都能识别）。

2. **运行安装**：

   ```bash
   scripts/install-gd-command.sh --install
   # 期望 INSTALL_STATUS: installed_now
   ```

3. **验证 parity**：

   ```bash
   scripts/check-gd-command-parity.sh
   # 期望 INSTALL_STATUS: installed_parity_pass
   ```

### 5.4 双锁机制

`scripts/install-gd-command.sh --install` 必须**同时通过**两道锁才会真写 `~/.claude/commands/gd.md`：

- **锁 1**：`baselines/gd-v7-runtime-write-authorizations.jsonl` 含 `scope: install_claude_command` 记录
- **锁 2**：CLI 必须显式传 `--install` 参数

任一未通过 → fail-closed，不写。

### 5.5 卸载

```bash
scripts/uninstall-gd-command.sh
# 期望 UNINSTALL_STATUS: uninstalled (hash 一致才删)
# 或 UNINSTALL_STATUS: blocked_hash_mismatch (拒绝删用户手写文件)
```

### 5.6 Parity 检查（CI 友好）

| INSTALL_STATUS | exit code | 含义 |
|---------------|-----------|------|
| `not_installed` | 0 | 未安装是合法状态 |
| `installed_parity_pass` | 0 | 已安装且与 source hash 一致 |
| `installed_parity_fail` | 1 | 已安装但 hash 不一致，需人工介入 |

---

## 6. Plan 实现进度

| 能力 | 归属 Plan | 状态 |
|------|----------|------|
| Multi-agent planning dispatch（dispatch map + validator） | Plan 4 | `local_only` ✓ |
| Multi-agent execution dispatch（batch + closure report，human_exec） | Plan 5 v5 | `local_only` ✓ |
| Codex cross-review sidecar | Plan 6 | `pending_future_plan` |
| Anti-fill fixtures + sanity validation | Plan 7 | `pending_future_plan` |
| 隔离收口 + Codex Desktop adapter backlog 记录 | Plan 8 | `pending_future_plan` |

---

## 7. 边界声明

`/gd` 命令**不会**：

- 修改旧 `/review` (`~/.claude/commands/review.md`)
- 调用旧 `/review plan` 或 `/review code`
- 引用旧 `Project GD/PROJECT_GOAL.md`（已标 `legacy_rev_goal_not_v7_authority`）
- 引用旧 `Project GD/prompts/rev-review-standard.md`（已标 `legacy_rev_standard`）
- 在未授权时写 `~/.claude/**`
- 启动 daemon / 注册 hook / 修改 cron / `LaunchAgent`
- 在 `CAPABILITY_STATUS` 上"主观选择"枚举值（必须按 `commands/gd.md` 映射表）
- 声称已接入 Codex cross-review（属 Plan 6）

---

## 8. 回滚

完整回滚（用户决定不再使用 `/gd`）：

```bash
# 1. 卸载 installed command（如已安装）
scripts/uninstall-gd-command.sh

# 2. 验证未安装
scripts/check-gd-command-parity.sh
# 期望 INSTALL_STATUS: not_installed

# 3. （可选）从 ledger 注释 install_claude_command 行
#    ledger 是 append-only，不删除历史记录；只在新行 append 一条 revoke 记录
```

旧 `/review` 链路完全独立，不受 `/gd` 安装/卸载影响。

---

## 9. 故障排查

| 现象 | 可能原因 | 修复 |
|------|---------|------|
| `INSTALL_STATUS: install_pending_authorization` | ledger 缺授权记录 | 用户授权后追加 ledger |
| `INSTALL_STATUS: install_blocked_hash_mismatch` | `~/.claude/commands/gd.md` 已存在但非 Project GD 安装 | 检查是否用户手写；备份后 `uninstall` 或手动处理 |
| `UNINSTALL_STATUS: blocked_hash_mismatch` | 同上 | 同上 |
| `INSTALL_STATUS: source_missing` | `Project GD/commands/gd.md` 被删除 | 从 git 恢复或重新走 Plan 3 |
| `/gd review` 直接退出 | 缺第二 token (`plan`/`code`) | 用 `/gd review plan` 或 `/gd review code` |
| `/gd plan` 报"找不到 TARGET_PROJECT_ROOT" | cwd 不是 git repo 或等于 GD_PROJECT_ROOT | 加 `--target <绝对路径>` |
