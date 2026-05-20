# Negative Fixture: OWNED_FORBIDDEN_OVERLAP

Trigger rule: step owns and forbids overlapping path.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "overlap-step-01",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": ["src/core/", "output/"],
      "forbidden_paths": ["src/core/scanner.py"],
      "required_context": [],
      "deliverables": [
        {"path": "src/core/base.py", "kind": "file", "must_exist": true},
        {"path": "output/report.txt", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-O1"],
      "verify": [
        {"sc_ref": "SC-O1", "method": "path", "cmd": "test -f src/core/base.py", "expect": "0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [{"track_id": "t1", "step_ids": ["overlap-step-01"], "max_parallel": 1, "mode": "execute"}]}
  ]
}
```
