# Execution Result

## 机器可读块

```json rev_execution_status
{
  "baseline_key": "phase3-test",
  "plan_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "execution_status": "completed",
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
      "status": "pass",
      "evidence": "`python3 rev-baseline.py extract ...` → `exit 0`",
      "not_run_reason": ""
    }
  ]
}
```
