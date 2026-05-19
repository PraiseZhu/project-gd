# Weekly Codex Memory Refinement (automation memory)

Last run: 2026-05-18T01:07:00Z

- Ran: node ai-infra/sync/codex-session-memory.mjs weekly --line-budget 800 --stability-wait-ms 1500
- Result: FAILED with `ERR_FS_FILE_TOO_LARGE` (readFileSync): File size (3024347485) > 2 GiB, in `readSourceSnapshot` (codex-session-memory.mjs:349) called from `captureCodexSession` (codex-session-memory.mjs:272).
- Last successful step: `node ai-infra/sync/codex-session-memory.mjs status` (weekly sync did not complete).
- Coverage (ai-infra/reports/codex-session-memory-report.md, generated 2026-04-27T01:01:28.062Z): 11/11.
- Reliability counts (same report): missing 0; duplicate 0; partial 0; corrupt 0.
- Raw session dirs (status on 2026-05-18): 28
- Profile facts (status on 2026-05-18): 92 (stable: 31)
- user-profile.md lines (wc -l on 2026-05-18): 128 (ai-infra/memory/user-profile.md)

Next: fix the weekly sync buffer/string limit so new sessions can be indexed again.
