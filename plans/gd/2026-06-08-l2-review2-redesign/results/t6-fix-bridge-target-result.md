template_kind: gd-execution-result
result_id: t6-fix-bridge-target-result
task_id: t6-fix-bridge-target
parent_step: T6
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
executor_role: claude_subagent
executed_at: 2026-06-09T00:00:00Z
exec_status: completed
sc_acceptance:
  - sc_ref: SC-6.1
    status: pass
    evidence: |
      SC-6.1a cmd: grep -nE 'REVIEW_FOCUS:.*bridge candidate' scripts/gd-codex-bridge-review.py | wc -l
      stdout: 0
      exit: 0
      note: "硬编码 'bridge candidate' 字符串已清除"

      SC-6.1b cmd: python3 -c "import ast,sys; ... len(set(focus_values))"
      stdout: 4
      exit: 0
      note: "4 种 kind 各有不同 REVIEW_FOCUS 值，去重后 >= 3"
    not_run_reason: ""

  - sc_ref: SC-6.2
    status: pass
    evidence: |
      cmd: python3 -c "... code_diff PRIMARY_TARGET not capsule.md ..."
      stdout: PASS
      exit: 0
      note: "code_diff kind 的 PRIMARY_TARGET 已指向真实 artifact 路径，不含 capsule.md"
    not_run_reason: ""

  - sc_ref: SC-6.3
    status: pass
    evidence: |
      cmd: grep -nE '_assert_not_capsule_target|capsule.*guard' scripts/gd-codex-bridge-review.py | wc -l
      stdout: 6
      exit: 0
      note: "capsule 守卫命中 6 行，>= 1，与 plan 路守卫对称"
    not_run_reason: ""

  - sc_ref: SC-6.4
    status: pass
    evidence: |
      cmd: test -f reports/t6-router-target-trace.md && grep -cE '\-\-target|[0-9]{3,4}行' reports/t6-router-target-trace.md
      stdout: 20
      exit: 0
      note: "trace 报告存在，追踪 router 四个 --target 传参点（438/468/628/886 行），结论：全部来自 args.target，无 capsule.md 注入"
    not_run_reason: ""

  - sc_ref: SC-6.5
    status: pass
    evidence: |
      cmd: python3 -c "... plan kind PRIMARY_TARGET contains plan.md path ..."
      stdout: PASS
      exit: 0
      note: "plan kind 的 PRIMARY_TARGET 含 plan.md 路径，回归验证通过"
    not_run_reason: ""

files_added:
  - reports/t6-router-target-trace.md
  - plans/gd/2026-06-08-l2-review2-redesign/results/t6-fix-bridge-target-result.md
files_modified:
  - scripts/gd-codex-bridge-review.py
files_unchanged_in_scope:
  - scripts/gd-review-router.py
owned_paths_writes_only: true
forbidden_paths_touched: []
out_of_scope_writes: []
handoff:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t6-fix-bridge-target-result.md
  status_field: exec_status
  summary: "bridge 三档(code_diff/execution_outcome/combined) PRIMARY_TARGET 已指真实 artifact（非 capsule.md），REVIEW_FOCUS 按 kind 动态化（4 种各异），capsule 守卫对称 plan 路；router target trace 已写 reports/t6-router-target-trace.md（4 site 均 CLEAN，无需修 router）"
  blockers: none
known_limitations:
  - "_primary_target_for_kind 正确性依赖调用方传入真实 artifact 而非 capsule——由 _assert_not_capsule_target 守卫保证；其他无效路径（如传错误的 .json）不在 T6 范围，由 L3 content-evidence validator 兜底"
  - "router 代码未修改（trace 结论：router --target 链路 CLEAN）"
  - "T7 owned 路径未动（scripts/gd-review-controller.py、commands/review2.md）"
