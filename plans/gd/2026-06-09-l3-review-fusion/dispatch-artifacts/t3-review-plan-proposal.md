# Child Planner Proposal — t3-review-plan

> child_planner 子 agent (Plan/opus) 机读输出存档；主 agent 校验、合并为 packets/t3-review-plan-convergence.md。
> 关键发现：现有 dedup 键=(reviewer,severity,description) 只去精确重复；L2 的 line//7 分桶会把相距 3 行的 finding 错分——改用 abs(a-b)<=3 窗口。

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "l3-review-fusion-t3-review-plan-p1",
  "parent_dispatch_id": "l3-review-fusion",
  "parent_track_id": "t3-review-plan",
  "agent_role": "child_planner",
  "output_status": "completed",
  "summary_cn": "把 gd-review-merge-and-fix-loop.py 的 ≤3 轮 auto-fix 升级为 L2 收敛机制：首轮 dual-codex+Claude 三方并集去重(键=文件+行号±3+类别,严重度取高)建 baseline_findings.json，r2 起注入 REVIEW_ROUND/BASELINE_FINDINGS/DELTA_SCOPE/SCOPE_CONSTRAINT 只验修复+查 delta、每轮仍 dual-codex 去 D7，5 轮硬上限、连续 2 轮 unresolved 不减触发 CONVERGENCE_TIMEOUT exit≠0，复用 t2 lens 入参不改 bridge。",
  "task_packets": [
    {"task_id": "t3-review-plan-convergence", "owned_paths": ["scripts/gd-review-merge-and-fix-loop.py"], "required_context": ["specs/l3-review-fusion/spec.md", "docs/constitution.md", "plans/gd/2026-06-09-l3-review-fusion/master-plan.md", "scripts/gd-review-merge-and-fix-loop.py", "scripts/gd-codex-bridge-review.py"]}
  ],
  "sc_refs": ["SC-2", "SC-3", "SC-4"],
  "verify": [
    {"sc_ref": "SC-2", "method": "command", "cmd": "python3 -m pytest tests/review-fusion -k 'union_baseline' -q 2>&1 | tail -1"},
    {"sc_ref": "SC-3", "method": "command", "cmd": "grep -qE 'REVIEW_ROUND|BASELINE_FINDINGS|DELTA_SCOPE' scripts/gd-review-merge-and-fix-loop.py && echo PASS"},
    {"sc_ref": "SC-4", "method": "command", "cmd": "python3 -m pytest tests/review-fusion -k 'convergence_timeout' -q 2>&1 | tail -1"}
  ],
  "blocked_reason": null
}
```
<!-- gd-child-plan-proposal-json:end -->
