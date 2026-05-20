# Negative Fixture: VERIFY_FUTURE_REFERENCE

Trigger rule: step-1 verify.cmd references a file deliverable of step-2 (which runs later),
without step-2 being in step-1's blocked_by.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "early-step-01",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": ["output/early.txt"],
      "forbidden_paths": ["/Users/praise/.claude/**"],
      "required_context": [],
      "deliverables": [
        {"path": "output/early.txt", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-E1"],
      "verify": [
        {"sc_ref": "SC-E1", "method": "command", "cmd": "test -f output/early.txt && test -f output/late.txt", "expect": "0"}
      ]
    },
    {
      "step_id": "late-step-02",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": ["output/late.txt"],
      "forbidden_paths": ["/Users/praise/.claude/**"],
      "required_context": [],
      "deliverables": [
        {"path": "output/late.txt", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-L1"],
      "verify": [
        {"sc_ref": "SC-L1", "method": "path", "cmd": "test -f output/late.txt", "expect": "0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [{"track_id": "t1", "step_ids": ["early-step-01"], "max_parallel": 1, "mode": "execute"}]},
    {"wave_id": "w2", "tracks": [{"track_id": "t2", "step_ids": ["late-step-02"], "max_parallel": 1, "mode": "execute"}]}
  ]
}
```
