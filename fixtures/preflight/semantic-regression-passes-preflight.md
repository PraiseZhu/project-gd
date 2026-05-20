# Semantic Regression Fixture: Passes Preflight, Has Semantic Issue

This plan passes all mechanical preflight rules but has a semantic problem:
SC-SR1 description says "no placeholders" but the verify only checks file existence —
a Codex reviewer should flag this as anti-fill (file-existence check cannot prove
"no placeholders" semantically). Preflight MUST pass this plan (METRIC_ASSERTION_WEAK
is only a WARN, not a FAIL in v1).

Proves: preflight does not replace Codex semantic review.

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "semantic-step-01",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": [],
      "owned_paths": ["output/report.txt"],
      "forbidden_paths": ["/Users/praise/.claude/**"],
      "required_context": [],
      "deliverables": [
        {"path": "output/report.txt", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-SR1"],
      "verify": [
        {"sc_ref": "SC-SR1", "method": "path", "cmd": "test -f output/report.txt", "expect": "0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [{"track_id": "t1", "step_ids": ["semantic-step-01"], "max_parallel": 1, "mode": "execute"}]}
  ]
}
```

## SC-SR1

**报告无占位符**：output/report.txt 内容不含任何 TODO/TBD/placeholder 字样，每段均有实质内容。

Verify: `test -f output/report.txt` — FILE EXISTS CHECK ONLY (semantic issue Codex should catch)
