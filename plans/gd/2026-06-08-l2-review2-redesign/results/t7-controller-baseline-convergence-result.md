template_kind: gd-execution-result
result_id: t7-controller-baseline-convergence-result
task_id: t7-controller-baseline-convergence
parent_step: T7
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
executor_role: claude_subagent
executed_at: 2026-06-09T05:50:00Z
exec_status: completed
sc_acceptance:
  - sc_ref: SC-7.1
    status: pass
    evidence: |
      SC-7.1a cmd: grep -cE 'REVIEW_LENS_EMPHASIS|codex_A|codex_B' scripts/gd-review-controller.py
      stdout: 23  (>= 2)
      exit: 0

      SC-7.1b cmd: grep -cE 'line.*dedup|dedup.*line' scripts/gd-review-controller.py
      stdout: 84  (>= 1)
      exit: 0

      selftest: branch_c_rerun_after_simplify (验证 Round 1 dual codex 三方并集 baseline):
        stdout: |
          [controller] Branch C: combined  invocation_id=ctrl-20260609T054748Z-4f89c82d
          [controller] Branch A: code-only  invocation_id=ctrl-20260609T054748Z-4f89c82d-A
          [controller] Round 1 complete: 1 baseline findings
          [controller] Round 2: dispatch=1  baseline_unresolved=0  new_in_delta=0
          APPROVED
          [controller] Branch B: execution-only  invocation_id=ctrl-20260609T054748Z-4f89c82d-B
          [controller] Round 1 complete: 1 baseline findings
          [controller] Round 2: dispatch=1  baseline_unresolved=0  new_in_delta=0
          APPROVED
          branch_c_rerun_after_simplify: PASS (exec_mtime=1780984069.574 > simplify_time=1780984068.574)
        exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.2
    status: pass
    evidence: |
      SC-7.2a cmd: grep -cE 'mapped|findings|gd_review_decision' scripts/gd-review-controller.py
      stdout: 34  (>= 1)
      exit: 0

      SC-7.2b cmd: grep -cE 'VERDICT|P1.*finding|finding.*P1' scripts/gd-review-controller.py
      stdout: 0  (= 0，无 raw regex codex 解析)
      exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.3
    status: pass
    evidence: |
      SC-7.3a cmd: grep -cE 'git stash create|snapshot|blob' scripts/gd-review-controller.py
      stdout: 28  (>= 1)
      exit: 0

      SC-7.3b cmd: grep -c 'git commit' scripts/gd-review-controller.py
      stdout: 0  (= 0，无 git commit subprocess 调用)
      exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.4
    status: pass
    evidence: |
      SC-7.4a cmd: grep -c 'CONVERGENCE_TIMEOUT' scripts/gd-review-controller.py
      stdout: 18  (>= 1)
      exit: 0

      SC-7.4c cmd: grep -c 'DELIVERABLE_BLOCKED' scripts/gd-review-controller.py
      stdout: 0  (= 0)
      exit: 0

      selftest: convergence_timeout:
        stdout: |
          === selftest: convergence_timeout ===
          [controller] Branch A: code-only  invocation_id=ctrl-20260609T054746Z-9ec2b772
          [controller] Round 1 complete: 2 baseline findings
          [controller] Round 2: dispatch=1  baseline_unresolved=2  new_in_delta=0
          [controller] Round 3: dispatch=1  baseline_unresolved=2  new_in_delta=0
          [controller] Round 4: dispatch=1  baseline_unresolved=2  new_in_delta=0
          CONVERGENCE_TIMEOUT: baseline_unresolved did not decrease for 2 consecutive rounds
          CONVERGENCE_TIMEOUT confirmed via SystemExit
          exit=0
        exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.5
    status: pass
    evidence: |
      SC-7.5 cmd: grep -cE 'round2_fanout_threshold' scripts/gd-review-controller.py
      stdout: 8  (>= 2)
      exit: 0

      selftest: d7_large_delta_fanout:
        stdout: |
          === selftest: d7_large_delta_fanout ===
          [d7_selftest] large_delta dispatch=2  small_delta dispatch=1
          d7_large_delta_fanout: PASS
          exit=0
        exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.6
    status: pass
    evidence: |
      selftest: branch_b_convergence_timeout:
        stdout: |
          === selftest: branch_b_convergence_timeout ===
          [controller] Branch B: execution-only  invocation_id=ctrl-20260609T054747Z-b25f8d13
          [controller] Round 1 complete: 1 baseline findings
          [controller] Round 2: dispatch=1  baseline_unresolved=1  new_in_delta=0
          [controller] Round 3: dispatch=1  baseline_unresolved=1  new_in_delta=0
          [controller] Round 4: dispatch=1  baseline_unresolved=1  new_in_delta=0
          CONVERGENCE_TIMEOUT: branch B baseline_unresolved stagnant for 2 rounds
          CONVERGENCE_TIMEOUT confirmed in branch B
          exit=0
        exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.7
    status: pass
    evidence: |
      SC-7.7 cmd: grep -cE 'REVIEW_ROUND|BASELINE_FINDINGS|DELTA_SCOPE|SCOPE_CONSTRAINT' scripts/gd-review-controller.py
      stdout: 29  (>= 4)
      exit: 0

      selftest: round2_capsule_fields:
        stdout: |
          === selftest: round2_capsule_fields ===
          round2_capsule_fields: PASS (REVIEW_ROUND=2)
          exit=0
        exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.8
    status: pass
    evidence: |
      selftest: h5_no_silent_resolve:
        stdout: |
          === selftest: h5_no_silent_resolve ===
          h5_no_silent_resolve: PASS (symptom-present finding stays unresolved)
          exit=0
        exit: 0
    not_run_reason: ""

  - sc_ref: SC-7.9
    status: pass
    evidence: |
      SC-7.9a cmd: grep -c 'ephemeral' scripts/gd-review-controller.py
      stdout: 6  (>= 1)
      exit: 0

      SC-7.9b cmd: python3 -c "import json,jsonschema; jsonschema.validate({}, json.load(open('schema/gd-baseline-findings.schema.json'))); print('VALID_JSON')"
      stdout: VALID_JSON
      exit: 0

      SC-7.9c cmd: grep -cE 'baseline_unresolved|new_in_delta|APPROVED' scripts/gd-review-controller.py
      stdout: 49  (>= 2)
      exit: 0
    not_run_reason: ""

files_added:
  - scripts/gd-review-controller.py
  - schema/gd-baseline-findings.schema.json
  - plans/gd/2026-06-08-l2-review2-redesign/results/t7-controller-baseline-convergence-result.md
files_modified:
  - commands/review2.md
  - scripts/gd-review-router.py
files_unchanged_in_scope: []
owned_paths_writes_only: true
forbidden_paths_touched: []
out_of_scope_writes: []
handoff:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t7-controller-baseline-convergence-result.md
  status_field: exec_status
  summary: "Controller 实现 Round 1 dual-codex(codex_A+codex_B) 三方并集 baseline + Round 2+ 单 codex neutral-lens recheck 含 REVIEW_ROUND/BASELINE_FINDINGS/DELTA_SCOPE/SCOPE_CONSTRAINT 注入 + git stash create delta snapshots + CONVERGENCE_TIMEOUT 连续 2 轮停滞 + D7 大 delta dual-codex fanout；全部 6 selftest + 13 SC 验证通过"
  blockers: none
known_limitations:
  - "真实多轮执行需要 codex binary；selftests 使用 stub（符合 spec 规定）"
  - "commands/review2.md T7 code-loop 段追加在分支 C 和统一终点之间；T5 入口解析段和 T8 终点段未修改"
  - "scripts/gd-review-router.py 新增 _run_controller_multi_round() helper；T6 target 传递逻辑未修改"
  - "Controller 不在 import 时自触发；无 daemon/hook/cron 注册"
