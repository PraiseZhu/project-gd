# ucode Review Result

REV_VERDICT: REQUIRES_CHANGES
REVIEW_KIND: code
REVIEW_DOMAIN: ai_infra
run_id: 20260509T194202Z-code.0cyqhu
timestamp: 2026-05-09T19:42:03Z

## Raw Output

source=local_conformance_gate
conformance_errors=2

REV_VERDICT: REQUIRES_CHANGES
REVIEW_KIND: code
REVIEW_DOMAIN: ai_infra

## 本地 Conformance Gate 拒绝

执行结果未通过本地 SC 覆盖验证。详见 conformance.json。
- Missing SCs from baseline: ['SC-3']
- SC-2: evidence lacks backtick anchor — must contain `exit`, `stdout`, `stderr`, `diff`, `→`, `result.*` or a file path like `/path/to/file.ext`
