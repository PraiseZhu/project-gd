# Negative Fixture: PROTECTED_RUNTIME_OWNED

Trigger rule: step owns a path under protected .claude runtime directories.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "protected-step-01",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": [
        "output/",
        "/Users/praise/.claude/scripts/hooks/my-custom-hook.js"
      ],
      "forbidden_paths": [],
      "required_context": [],
      "deliverables": [
        {"path": "output/result.txt", "kind": "file", "must_exist": true},
        {"path": "/Users/praise/.claude/scripts/hooks/my-custom-hook.js", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-P1"],
      "verify": [
        {"sc_ref": "SC-P1", "method": "path", "cmd": "test -f output/result.txt", "expect": "0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [{"track_id": "t1", "step_ids": ["protected-step-01"], "max_parallel": 1, "mode": "execute"}]}
  ]
}
```
