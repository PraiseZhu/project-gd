# Negative Fixture: MASTER_PLAN_DISPATCH_DRIFT

Trigger rule: step_id in inventory not present in dispatch_map.json.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "ghost-step-99",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": ["output/ghost.txt"],
      "forbidden_paths": ["/Users/praise/.claude/**"],
      "required_context": [],
      "deliverables": [
        {"path": "output/ghost.txt", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-G1"],
      "verify": [
        {"sc_ref": "SC-G1", "method": "path", "cmd": "test -f output/ghost.txt", "expect": "0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [{"track_id": "t1", "step_ids": ["ghost-step-99"], "max_parallel": 1, "mode": "execute"}]}
  ]
}
```
