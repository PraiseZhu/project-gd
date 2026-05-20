# Negative Fixture: DELIVERABLE_NOT_OWNED

Trigger rule: deliverable path not covered by same-step owned_paths.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "unowned-deliv-01",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": ["output/"],
      "forbidden_paths": ["/Users/praise/.claude/**"],
      "required_context": [],
      "deliverables": [
        {"path": "output/result.txt", "kind": "file", "must_exist": true},
        {"path": "src/sneaky.py", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-D1"],
      "verify": [
        {"sc_ref": "SC-D1", "method": "path", "cmd": "test -f output/result.txt", "expect": "0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [{"track_id": "t1", "step_ids": ["unowned-deliv-01"], "max_parallel": 1, "mode": "execute"}]}
  ]
}
```
