# Child Planner Proposal — t6-deploy

> child_planner 子 agent (Plan/opus) 机读输出存档；主 agent 校验、合并为 packets/t6-deploy-manifest.md。
> 关键发现（已核实属实）：master-plan/dispatch-map 的 SC-8 verify 原句未排除 .deploy-manifest.jsonl 的 # 注释行（现网第 1-5 行即注释），json.loads 会崩。packet verify 已加 `not l.lstrip().startswith('#')` 守卫。

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "l3-review-fusion-t6-deploy-p1",
  "parent_dispatch_id": "l3-review-fusion",
  "parent_track_id": "t6-deploy",
  "agent_role": "child_planner",
  "output_status": "completed",
  "summary_cn": "t6-deploy 为 dispatch-only：基于现网两文件真实字段，向 .deploy-manifest.jsonl append gd.md(install_claude_command) + 6 条改动 artifact(sync_script_to_live) 部署条目，并向 runtime-write-authorizations.jsonl append gd.md 回灌授权；runtime 写入与 parity 验收显式归 Plan E / deploy-live。",
  "task_packets": [
    {"task_id": "t6-deploy-manifest", "owned_paths": [".deploy-manifest.jsonl", "baselines/gd-v7-runtime-write-authorizations.jsonl"], "required_context": ["specs/l3-review-fusion/spec.md", "plans/gd/2026-06-09-l3-review-fusion/master-plan.md"]}
  ],
  "sc_refs": ["SC-8"],
  "verify": [
    {"sc_ref": "SC-8", "method": "command", "cmd": "python3 -c \"import json; [json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.lstrip().startswith('#')]\" && grep -q 'gd.md' .deploy-manifest.jsonl && echo MANIFEST_LEDGER_READY"}
  ],
  "blocked_reason": null
}
```
<!-- gd-child-plan-proposal-json:end -->
