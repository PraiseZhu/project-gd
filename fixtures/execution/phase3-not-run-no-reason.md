# Execution Result

## 机器可读块

```json rev_execution_status
{
  "baseline_key": "phase3-test",
  "plan_hash": "6af6e99aead16f67dfa676e989cce08fc229631cc9d58b898d27f8e919becb02",
  "execution_status": "partial",
  "sc_results": [
    {
      "id": "SC-1",
      "status": "pass",
      "evidence": "`bin/rev plan --dry-run` → `exit 0`",
      "not_run_reason": ""
    },
    {
      "id": "SC-2",
      "status": "pass",
      "evidence": "`grep -cE ...` → 5",
      "not_run_reason": ""
    },
    {
      "id": "SC-3",
      "status": "not_run",
      "evidence": "",
      "not_run_reason": ""
    }
  ]
}
```
