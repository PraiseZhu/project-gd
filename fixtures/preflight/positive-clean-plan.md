# Positive Fixture: Clean Plan

Synthetic minimal plan that passes all 6 preflight rules.
Used as the canonical positive fixture for gd-validate-master-plan-consistency.py regression tests.
Does NOT depend on external project files that may change.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "clean-step-01",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["clean-step-01-impl"],
      "owned_paths": [
        "output/report.txt",
        "scripts/helper.py"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**",
        "/Users/praise/.claude/commands/**",
        "src/other/**"
      ],
      "required_context": [
        "prompts/gd-review-standard.md"
      ],
      "deliverables": [
        {"path": "output/report.txt", "kind": "file", "must_exist": true},
        {"path": "scripts/helper.py", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-C1", "SC-C2"],
      "verify": [
        {
          "sc_ref": "SC-C1",
          "method": "command",
          "cmd": "test -f output/report.txt && grep -q 'RESULT' output/report.txt",
          "expect": "exit 0"
        },
        {
          "sc_ref": "SC-C2",
          "method": "command",
          "cmd": "python3 scripts/helper.py --self-test",
          "expect": "exit 0"
        }
      ]
    },
    {
      "step_id": "clean-step-02",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["clean-step-02-impl"],
      "blocked_by": ["clean-step-01"],
      "owned_paths": [
        "output/summary.json"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**",
        "output/report.txt"
      ],
      "required_context": [
        "output/report.txt"
      ],
      "deliverables": [
        {"path": "output/summary.json", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-C3"],
      "verify": [
        {
          "sc_ref": "SC-C3",
          "method": "command",
          "cmd": "python3 -m json.tool output/summary.json > /dev/null",
          "expect": "exit 0"
        }
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [
      {"track_id": "t1", "step_ids": ["clean-step-01"], "max_parallel": 1, "mode": "execute"}
    ]},
    {"wave_id": "w2", "tracks": [
      {"track_id": "t2", "step_ids": ["clean-step-02"], "max_parallel": 1, "mode": "execute"}
    ]}
  ]
}
```
