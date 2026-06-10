# Child Planner Proposal — t2-bridge

> child_planner 子 agent (Plan/opus) 机读输出存档；主 agent 用 gd-validate-child-proposal.py 校验、合并为 packets/t2-bridge-lens-conformance.md。
> 关键发现：gd-review-standard.md 现有 §9 已占用（与旧 /review 隔离），穷举强制节顺延为 §10（SC-6 grep 不依赖编号）。

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "l3-review-fusion-t2-bridge-p1",
  "parent_dispatch_id": "l3-review-fusion",
  "parent_track_id": "t2-bridge",
  "agent_role": "child_planner",
  "output_status": "completed",
  "summary_cn": "t2-bridge 在 build_capsule_text 注入 REVIEW_LENS_EMPHASIS 双视角参数化与 Reviewer Instructions conformance 声明，并在 review 标准末尾新增穷举强制节（明知多处只报一条判 degraded）；穷举节因现有 §9 占用顺延为 §10。",
  "task_packets": [
    {"task_id": "t2-bridge-lens-conformance", "owned_paths": ["scripts/gd-codex-bridge-review.py", "prompts/gd-review-standard.md"], "required_context": ["specs/l3-review-fusion/spec.md", "docs/constitution.md", "plans/gd/2026-06-09-l3-review-fusion/master-plan.md", "scripts/gd-codex-bridge-review.py", "prompts/gd-review-standard.md"]}
  ],
  "sc_refs": ["SC-2", "SC-6"],
  "verify": [
    {"sc_ref": "SC-2", "method": "command", "cmd": "grep -qE 'REVIEW_LENS_EMPHASIS' scripts/gd-codex-bridge-review.py && echo PASS"},
    {"sc_ref": "SC-6", "method": "command", "cmd": "grep -qE 'conformance|不重复找 bug|顺带' scripts/gd-codex-bridge-review.py prompts/gd-review-standard.md && echo PASS"}
  ],
  "blocked_reason": null
}
```
<!-- gd-child-plan-proposal-json:end -->
