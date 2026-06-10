# Child Planner Proposal — t5-regression

> child_planner 子 agent (Plan/opus) 机读输出存档；主 agent 校验、合并为 packets/t5-regression-fixtures.md。

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "l3-review-fusion-t5-regression-p1",
  "parent_dispatch_id": "l3-review-fusion",
  "parent_track_id": "t5-regression",
  "agent_role": "child_planner",
  "output_status": "completed",
  "summary_cn": "t5 在 tests/review-fusion 建 7 个 pytest 模块覆盖 t1-t4 的 SC 关键词并 subprocess 调被测脚本不改它们，在 fixtures/review-fusion 造 controller-report/stage-ledger/execution-batch+dispatch-map 四个 regression fixture 按真实 validator 字段满足 SC-4/SC-5/SC-7。",
  "task_packets": [
    {"task_id": "t5-regression-fixtures", "owned_paths": ["tests/review-fusion", "fixtures/review-fusion"], "required_context": ["specs/l3-review-fusion/spec.md", "plans/gd/2026-06-09-l3-review-fusion/master-plan.md", "scripts/gd-validate-controller-report.py", "scripts/gd-validate-stage-dispatch-ledger.py", "scripts/gd-validate-execution-batch.py"]}
  ],
  "sc_refs": ["SC-4", "SC-5", "SC-7"],
  "verify": [
    {"sc_ref": "SC-4", "method": "command", "cmd": "python3 -m pytest tests/review-fusion -k 'convergence' -q 2>&1 | tail -1"},
    {"sc_ref": "SC-5", "method": "command", "cmd": "python3 -m pytest tests/review-fusion -k 'fail_closed' -q 2>&1 | tail -1"},
    {"sc_ref": "SC-7", "method": "command", "cmd": "python3 scripts/gd-validate-controller-report.py fixtures/review-fusion/regression-controller-report.json && echo PASS"}
  ],
  "blocked_reason": null
}
```
<!-- gd-child-plan-proposal-json:end -->
