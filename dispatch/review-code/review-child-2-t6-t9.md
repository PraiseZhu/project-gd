```yaml
GD_REVIEW_DECISION: APPROVED
reviewer: claude_child_2
scope: T6-T9
review_timestamp: 2026-06-09T06:50:00Z

findings:
  - id: F1
    severity: NF
    file: scripts/gd-review-router.py
    line: 1169-1187
    category: logic_error
    description: |
      use_controller=True 从未通过 run_live() 传入 _run_live_execution_only 和
      _run_live_execution_plus_code。run_live() 调用这两个函数时均未传 use_controller
      参数，导致 T7 controller 多轮循环路径在 router live 模式下无法激活。
      该参数仅在函数签名中有 default=False，但 run_live() 和 main() 的 argparse 中均未
      暴露 --use-controller CLI flag。
      可复现：python3 scripts/gd-review-router.py --mode live --target <exec_result>
      将永远走单轮 Codex bridge 路径，不经过 gd-review-controller.py。
    suggested_fix: |
      在 argparse 增加 --use-controller flag（或通过 review2.md command 固定传 True），
      并在 run_live() 调用 _run_live_execution_only / _run_live_execution_plus_code 时传入。
      由于 review2.md 的 code 分支直接调用 gd-review-controller.py（绕过 router），
      非阻断：router live 模式的单轮路径作为降级通道仍可用；
      T7 controller 由 commands/review2.md 直接编排，不依赖 router 的 use_controller 路径。

  - id: F2
    severity: NF
    file: scripts/gd-review2-package-deliverable.sh
    line: 196-227
    category: minor
    description: |
      SC 证据表（件套②）中的 verify cmd echo 包含字面量 "CONVERGENCE_TIMEOUT"（行219-220），
      该 echo 输出属于证据表正文，不影响 SC-8.4 的真实判定。
      但如果调用方对脚本全量输出做 grep CONVERGENCE_TIMEOUT，可能误报 1 次命中。
      SC-8.4 的实际验证命令是对 red-gate 路径的输出 grep，已验证输出为 0（无命中）。
      实际运行已确认：红 gate 路径 grep CONVERGENCE_TIMEOUT 返回空，无误报。
    suggested_fix: |
      无需修复（行为正确）。如需完全避免混淆，可将件套②的 verify cmd 示例用代码块
      包裹或改用不含 CONVERGENCE_TIMEOUT 字样的示例命令，但不影响合规性。
```

---

## 审查摘要

### T6 — gd-codex-bridge-review.py（SC-6.1~6.5）

| SC | 实现 | 状态 |
|----|------|------|
| SC-6.1 REVIEW_FOCUS 动态化 | `_review_focus_for_kind()` 函数 L996-1011，按 kind 返回不同 focus 字符串；capsule 写入 `REVIEW_FOCUS_SOURCE: kind_dynamic` | pass |
| SC-6.2 PRIMARY_TARGET 分容 | `_primary_target_for_kind()` L1014-1025，所有 kind 均返回 `str(target.resolve())`；对 non-plan kinds capsule 将自身列为 RELATED_CONTEXT（capsule_related_note）| pass |
| SC-6.3 capsule 守卫 | `_assert_not_capsule_target()` L1028-1041 在 `build_capsule_text` 和 `cmd_run_bridge` 两处守卫；code_diff/execution_outcome/combined 收到 capsule.md 时 raise ValueError / exit 1 | pass |
| SC-6.4 REVIEW_FOCUS_SOURCE 字段 | capsule 包含 `REVIEW_FOCUS_SOURCE: kind_dynamic` L1184 | pass |
| SC-6.5 router execution_outcome/combined 传递修复 | `_run_live_codex_bridge()` 统一封装 run-bridge + parse-transport，router 的 execution_only/combined 路径均调用此 helper | pass |

**router T6 fix 验证**：`_run_live_codex_bridge` helper（L392-500）正确注入 `GD_REVIEW_ROUTER_INVOCATION_ID` 以通过 bridge G1 sentinel；`_run_live_execution_only` Path C 和 `_run_live_execution_plus_code` else 分支均使用 helper。

### T7 — gd-review-controller.py（SC-7.1~7.9）+ router 接入

| SC | 实现 | 状态 |
|----|------|------|
| SC-7.1 Round 1 双 codex + 三方 union | `run_round1()` ThreadPoolExecutor(max_workers=2) dispatch codex_A+B；`merge_findings_union()` 三路 union，dedup key=(file, line±3, category) | pass |
| SC-7.2 不直接 regex codex 输出 | controller 只消费 bridge mapped JSON（`_extract_findings_from_mapped`），无原始 regex | pass |
| SC-7.3 git stash create（不 commit）| `take_delta_snapshot()` 用 `git stash create` L129-154；docstring 明确 "Never writes to git history" | pass |
| SC-7.4 CONVERGENCE_TIMEOUT（Branch A）| `stagnant_rounds >= 2` → `sys.exit(1)` L635-637；selftest `convergence_timeout` 实际运行 PASS（Round 4 触发）| pass |
| SC-7.5 D7 large delta fanout | `compute_delta_size()` L157-168；`run_round_n()` large_delta 判断，dispatch_count=2；selftest `d7_large_delta_fanout` PASS（large=2, small=1）| pass |
| SC-7.6 CONVERGENCE_TIMEOUT（Branch B）| `run_branch_b()` 相同 stagnant_rounds 逻辑 L702-711；selftest `branch_b_convergence_timeout` 已覆盖 | pass |
| SC-7.7 Round 2 capsule 字段注入 | `run_round_n()` 通过 env var 注入 REVIEW_ROUND/BASELINE_FINDINGS/DELTA_SCOPE/SCOPE_CONSTRAINT L268-277；selftest `round2_capsule_fields` PASS | pass |
| SC-7.8 H5 不静默 resolve | `update_baseline_statuses()` 纯 key-presence 判断（非主观再评判）；selftest `h5_no_silent_resolve` PASS | pass |
| SC-7.9 Branch C 先 A 后 B，exec_result mtime > simplify_time | `run_branch_c()` Step 1→simplify→Step 4；selftest `branch_c_rerun_after_simplify` PASS（mtime 验证通过）| pass |
| router 接入 | `_run_controller_multi_round()` L562-605 存在；review2.md 直接编排 controller CLI（绕过 router 的 use_controller 路径，行为正确）| pass |

**selftest 可运行验证**（实际执行，非静态分析）：
- `convergence_timeout` → PASS（SystemExit 确认）
- `d7_large_delta_fanout` → PASS（large=2, small=1）
- `branch_c_rerun_after_simplify` → PASS（mtime 验证）

### T8 — gd-review2-package-deliverable.sh（SC-8.1~8.6）

| SC | 实现 | 状态 |
|----|------|------|
| SC-8.1 脚本存在可执行 | 文件存在于 worktree；bash -n 语法无误 | pass |
| SC-8.2 全绿 → 三件套正路 | 全绿路径实际运行返回 `DELIVERABLE_STATUS: READY_FOR_HANDOFF` + git add DRY-RUN + SC 证据表 + commit/MR 草稿 | pass |
| SC-8.3 任一红 → DELIVERABLE_BLOCKED + exit 1 | `ALL_GREEN=false` 路径 echo DELIVERABLE_BLOCKED + BLOCKED_ITEMS + exit 1；实际运行验证通过 | pass |
| SC-8.4 不输出 CONVERGENCE_TIMEOUT | 红 gate 路径 `grep CONVERGENCE_TIMEOUT` 返回空（零命中）；注释和 echo 证据表内有字面量但属正文非 terminal 信号 | pass |
| SC-8.5 不自动 commit/push | `grep -nE '(^|[^#])[[:space:]]*git[[:space:]]+(commit\|push)'` 返回空（无裸 commit/push 命令）| pass |
| SC-8.6 终点 stage 接入 review2.md | `commands/review2.md` L277-325 包含 `<!-- T8: 统一终点 stage -->` 段，调用 `gd-review2-package-deliverable.sh`，含 DELIVERABLE_BLOCKED / CONVERGENCE_TIMEOUT 处理说明 | pass |

**git add 位置验证**：`git add -u` 仅出现在 ALL_GREEN=true 路径（L183），在 `exit 1`（L159）之后，红 gate 不执行 git add。

**状态码隔离（H4）**：controller CONVERGENCE_TIMEOUT (exit 1) → 调用方传 `REQUIRES_CHANGES` → 脚本只输出 `DELIVERABLE_BLOCKED`。两者字面码完全隔离，review2.md L303 明确记录。

### T9 — .deploy-manifest.jsonl（SC-9.1~9.6）

| SC | 检查项 | 状态 |
|----|--------|------|
| SC-9.1 8 条 T1-T8 artifact 完整 | 已录入 8 条（gd-validate-review2-plan-target.py / plan-mode-template.md / plan-mode-antifill-stop-hook.js / gd-review-controller.py / gd-baseline-findings.schema.json / gd-detect-review2-code-target.py / gd-review2-preflight.sh / gd-review2-package-deliverable.sh）| pass |
| SC-9.2 所有 source 文件在 worktree 中真实存在 | Python 逐行验证：13 条 source 全部 OK，无 MISSING | pass |
| SC-9.3 无 source 指向 ~/.claude/** | 所有 source 字段均为相对路径（scripts/、schema/、commands/、templates/）；target 才指向 ~/.claude/ | pass |
| SC-9.4 method/ledger_scope 字段完整 | 全部 13 条均有 method（direct_cp / install_script）和 ledger_scope | pass |
| SC-9.5 install_script 条目有 installer + installer_args | review2.md 条目有 `installer` 和 `installer_args` 字段 | pass |
| SC-9.6 manifest 格式合法（每行 JSON）| Python json.loads 逐行解析无异常 | pass |

---

## 路径权限审查

- `gd-review-controller.py` 使用 `git stash create`（只读快照，不写历史）。
- 所有脚本写入 `output_dir`（传入参数）或 `GD_ROOT/reports/`（worktree 内），未写入 `~/.claude/**`。
- `gd-review2-package-deliverable.sh` 绿 gate 执行 `git add -u`（stage，非 commit），在 worktree 作用域内，符合约束。
- `.deploy-manifest.jsonl` 的 `target` 指向 `~/.claude/` 是 deploy-live 的预期行为；`source` 均为 worktree 内相对路径，无违规。

## 总结

T6-T9 实现覆盖所有对应 SC，selftest 可运行并通过，manifest 完整且 source 全存在，状态码隔离（CONVERGENCE_TIMEOUT vs DELIVERABLE_BLOCKED）已由代码和文档双重保障。F1 和 F2 均为 NF（非阻断），不影响当前功能正确性。
