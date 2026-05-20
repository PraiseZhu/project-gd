# Negative Fixture: SC_VERIFY_MISSING

Trigger rule: sc_refs entry has no same-step verify entry.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "no-verify-step-01",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": ["output/"],
      "forbidden_paths": ["/Users/praise/.claude/**"],
      "required_context": [],
      "deliverables": [
        {"path": "output/result.txt", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-V1", "SC-V2"],
      "verify": [
        {"sc_ref": "SC-V1", "method": "path", "cmd": "test -f output/result.txt", "expect": "0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [{"track_id": "t1", "step_ids": ["no-verify-step-01"], "max_parallel": 1, "mode": "execute"}]}
  ]
}
```
