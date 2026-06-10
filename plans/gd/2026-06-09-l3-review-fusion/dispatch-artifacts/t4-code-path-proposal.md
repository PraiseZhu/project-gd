# Child Planner Proposal — t4-code-path

> child_planner 子 agent (Plan/opus) 机读输出存档；主 agent 校验、合并为 packets/t4-code-path-quality-conformance.md。
> 关键发现（anti-fill）：SC-5 的 dispatch-map verify `grep -qE 'fail.closed|fail_closed'` 是弱门——`.` 匹配现有注释里的 `fail-closed` 连字符，改动前即 PASS。packet 已补强断言 `grep -c 'fail_closed' >=1` + self-test，并明示不可拿 grep PASS 当完成证据。

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "l3-review-fusion-t4-code-path-p1",
  "parent_dispatch_id": "l3-review-fusion",
  "parent_track_id": "t4-code-path",
  "agent_role": "child_planner",
  "output_status": "completed",
  "summary_cn": "在 gd-review-router.py 的 code/执行三 handler 插入 /code-review+/simplify 上游质量门（非成功即 fail_closed 非通过 exit≠0 并落盘可验证输出），通过后再进经 bridge 收窄为 conformance 的 Codex cross-review，修复循环经 subprocess 复用 t3 收敛本体，两步产物分别可观测。",
  "task_packets": [
    {"task_id": "t4-code-path-quality-conformance", "owned_paths": ["scripts/gd-review-router.py"], "required_context": ["specs/l3-review-fusion/spec.md", "docs/constitution.md", "plans/gd/2026-06-09-l3-review-fusion/master-plan.md", "scripts/gd-review-router.py"]}
  ],
  "sc_refs": ["SC-5", "SC-6"],
  "verify": [
    {"sc_ref": "SC-5", "method": "command", "cmd": "grep -qE 'fail.closed|fail_closed' scripts/gd-review-router.py && echo PASS"},
    {"sc_ref": "SC-6", "method": "command", "cmd": "grep -qE 'conformance|code-review|simplify' scripts/gd-review-router.py && echo PASS"}
  ],
  "blocked_reason": null
}
```
<!-- gd-child-plan-proposal-json:end -->
