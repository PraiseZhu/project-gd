# Child Planner Proposal — t1-transport

> child_planner 子 agent (Plan/opus) 机读输出存档；主 agent 用 gd-validate-child-proposal.py 校验、合并为 packets/t1-transport-guard.md。

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "l3-review-fusion-t1-transport-p1",
  "parent_dispatch_id": "l3-review-fusion",
  "parent_track_id": "t1-transport",
  "agent_role": "child_planner",
  "output_status": "completed",
  "summary_cn": "交付 t1-transport-guard packet：新建 gd-codex-transport-guard.py 落地 preflight 探活/bounded 重试/充足 timeout/healthcheck 四道确定性防线，并在 gd-review-suite-controller.py 的 _run_live_targets 派双 codex 前接入探活早退，任一 codex 不可用即 fail-closed 阻断，覆盖 SC-1 与 SC-5。",
  "task_packets": [
    {"task_id": "t1-transport-guard", "owned_paths": ["scripts/gd-codex-transport-guard.py", "scripts/gd-review-suite-controller.py"], "required_context": ["specs/l3-review-fusion/spec.md", "docs/constitution.md", "plans/gd/2026-06-09-l3-review-fusion/master-plan.md", "scripts/gd-review-suite-controller.py"]}
  ],
  "sc_refs": ["SC-1", "SC-5"],
  "verify": [
    {"sc_ref": "SC-1", "method": "command", "cmd": "test -f scripts/gd-codex-transport-guard.py && grep -qE 'retry|MAX_RETR' scripts/gd-codex-transport-guard.py && echo PASS"},
    {"sc_ref": "SC-5", "method": "command", "cmd": "python3 -m pytest tests/review-fusion -k 'fail_closed or retry_recover' -q 2>&1 | tail -1"}
  ],
  "blocked_reason": null
}
```
<!-- gd-child-plan-proposal-json:end -->
