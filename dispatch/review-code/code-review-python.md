```yaml
reviewer: code-review-python
files_reviewed:
  - scripts/gd-review-controller.py
  - scripts/gd-codex-bridge-review.py
  - scripts/gd-detect-review2-code-target.py
  - scripts/gd-review-router.py
  - scripts/gd-validate-review2-plan-target.py
findings:
  # ----------------------------- HIGH -----------------------------
  - severity: HIGH
    file: scripts/gd-review-controller.py
    line: "175-187 (_finding_key), 80 (LINE_DEDUP_WINDOW)"
    category: logic_error
    description: >
      Dedup bucketing is mathematically wrong. _finding_key computes
      line_bucket = line // (2*LINE_DEDUP_WINDOW+1) = line // 7 and the docstring
      claims "Two lines within ±3 of each other always share a bucket." That is
      false: lines 4 and 7 are within ±3 (|4-7|=3) but land in bucket 0 and
      bucket 1 respectively. Verified by brute force — of all (a,b) pairs with
      |a-b|<=3 in [0,100), 84 pairs fall in different buckets. Consequence:
      identical findings reported at e.g. line 6 by codex_A and line 8 by codex_B
      (off by 2, within the spec's ±3 window) are NOT deduped, so the baseline
      double-counts the same issue, inflates baseline_unresolved, and can push the
      loop toward a spurious CONVERGENCE_TIMEOUT. This is the SC-7.1 dedup primitive
      and it does not implement the ±3 window it documents. (NB the OTHER dedup impl
      in gd-codex-bridge-review.py merge_findings_union L949-976 uses a correct
      abs(line_a-line_b)<=3 sliding comparison — the two files disagree on the
      dedup algorithm, which is itself a maintainability hazard.)
    suggested_fix: >
      Replace bucket arithmetic with the same O(n²) sliding-window comparison used
      in gd-codex-bridge-review.py merge_findings_union (group by (file,category)
      then compare abs(line_a-line_b) <= LINE_DEDUP_WINDOW), OR emit two bucket keys
      per finding (line//W and (line+W)//W ... ) — but the sliding comparison is the
      already-proven, in-repo convention; reuse it to kill the divergent second
      algorithm.
  - severity: HIGH
    file: scripts/gd-review-controller.py
    line: "756-771 (Branch C /simplify), 762"
    category: error_handling
    description: >
      The real-codex /simplify dispatch `subprocess.run(["codex","exec",
      "--ephemeral","--","/simplify"], cwd=str(cwd), capture_output=True,
      text=True)` has NO timeout. codex exec is an interactive agent call that can
      hang indefinitely; with capture_output=True and no timeout the whole
      controller (and the router that spawns it) blocks forever with no recovery.
      Every other live subprocess in this batch sets a timeout (bridge run-bridge
      uses timeout=420 at L288; router live bridge honors live_bridge_timeout_sec).
      This one is the only unbounded external-agent call.
    suggested_fix: >
      Add timeout= (e.g. a --simplify-timeout-sec arg, default 600) and wrap in
      try/except subprocess.TimeoutExpired, printing a degraded notice and
      continuing (the code already tolerates a non-zero /simplify exit at L766).
  - severity: HIGH
    file: scripts/gd-review-controller.py
    line: "122-154 (take_delta_snapshot) and all take_delta_snapshot callers"
    category: error_handling
    description: >
      take_delta_snapshot runs four git subprocesses (stash create, diff --stat,
      diff HEAD, rev-parse HEAD) with NO timeout and NO returncode checks. If the
      repo is mid-merge/rebase, has an index lock, or git stalls, the call blocks
      with capture_output=True. More concretely: returncodes are never inspected —
      `git stash create` failing (e.g. corrupted index) yields empty stdout, which
      is silently treated as "clean tree" and falls back to HEAD, masking the
      failure (rule 12: fail visibly, not silently). compute_delta_size then sees an
      empty diff and the D7 large-delta fanout decision is made on bad data.
    suggested_fix: >
      Add timeout= to each subprocess.run and check returncode; on non-zero, raise
      or surface a degraded marker rather than coercing to "clean tree".
  # ----------------------------- MEDIUM -----------------------------
  - severity: MEDIUM
    file: scripts/gd-review-controller.py
    line: "584-596"
    category: maintainability
    description: >
      `changed_files` is computed (git diff HEAD --name-only, with a staged
      fallback at L591-595) but never read afterward — target is unconditionally
      set to `cwd` at L596 ("bridge will detect diff"). Dead computation that runs
      two git subprocesses (also untimed) for no effect; misleads future readers
      into thinking the changed-file set drives the review target.
    suggested_fix: Delete the changed_files block, or actually pass it to the bridge target.
  - severity: MEDIUM
    file: scripts/gd-review-controller.py
    line: "311 (_invoke_bridge_mapped parse-transport), 129/136/140/148 (take_delta_snapshot)"
    category: error_handling
    description: >
      The parse-transport subprocess at L311 has no timeout (the sibling run-bridge
      call at L288 does have timeout=420). Same untimed pattern as the git calls.
      Lower severity than the /simplify and stash findings because parse-transport
      is a local stdlib-only Python script unlikely to hang, but it is inconsistent
      with the rest of the file's timeout discipline.
    suggested_fix: Add timeout= (e.g. 60) to the parse-transport subprocess.run.
  - severity: MEDIUM
    file: scripts/gd-review-controller.py
    line: "875-1233 (selftest functions), 898-919 monkeypatching sys.exit"
    category: maintainability
    description: >
      ~470 lines of selftest scaffolding (StubDispatch, _make_finding, six
      _selftest_* functions, SELFTESTS dict) live in the production module and are
      reachable via the public --selftest CLI flag. Tests monkeypatch the global
      sys.exit (L903/L1034/L1196) and mutate module globals
      (sys.modules[__name__].compute_delta_size at L950/L973/L976/L994). This is
      shipped in the same file the router imports/executes in production. Not a
      security hole (selftest is opt-in via flag, no prod path calls StubDispatch —
      every prod entry passes stub_dispatch=None), but it bloats the largest file in
      the batch (1340 lines, > the 800-line MEDIUM threshold) and the global
      monkeypatching is fragile.
    suggested_fix: >
      Move selftests to a tests/ module (e.g. tests/test_review_controller.py) and
      import the production functions; keep --selftest as a thin shim or drop it.
  - severity: MEDIUM
    file: scripts/gd-codex-bridge-review.py
    line: "1062-1260 (build_capsule_text ~200 lines), 1421-1607 (_cmd_run_bridge_inner ~185 lines), 2253 (file length)"
    category: function_length
    description: >
      build_capsule_text is ~200 lines and _cmd_run_bridge_inner is ~185 lines
      (both well over the 50-line MEDIUM threshold); cmd_self_test is ~300 lines.
      The whole file is 2253 lines (> 800-line threshold). High branch density in
      _cmd_run_bridge_inner (writer DEGRADED/MALFORMED/FAILED ladders + L3 pre/post
      blocks duplicated almost verbatim with cmd_parse_transport L1661-1697).
    suggested_fix: >
      Extract the L3 content-evidence block (duplicated at L1560-1599 and
      L1661-1697) into a shared helper; split capsule field assembly out of
      build_capsule_text.
  - severity: MEDIUM
    file: scripts/gd-review-router.py
    line: "608-1113 (_run_live_execution_only / _run_live_execution_plus_code)"
    category: maintainability
    description: >
      _run_live_execution_only (L608-837) and _run_live_execution_plus_code
      (L900-1113) are near-duplicate ~200-line functions differing mainly in
      kind="execution_outcome" vs "combined" and one outcome-first failure code.
      The Path A/B/C codex-injection ladder (raw fixture / mapped fixture / live
      bridge) is copy-pasted between them. `import hashlib` appears twice inside
      _run_live_execution_plus_code (L917 and L942). High duplication = two places
      to fix every future decision-matrix change.
    suggested_fix: >
      Factor the shared outcome-validate + codex-merge + ledger flow into one
      helper parameterized by kind and failure_code; remove the duplicate
      `import hashlib`.
validation:
  syntax:
    gd-review-controller.py: "ast.parse OK"
    gd-codex-bridge-review.py: "ast.parse OK"
    gd-detect-review2-code-target.py: "ast.parse OK"
    gd-review-router.py: "ast.parse OK"
    gd-validate-review2-plan-target.py: "ast.parse OK"
  security_scan: "no shell=True / os.system / eval / exec / pickle in any of the 5 files; all subprocess calls use list-form argv (no shell injection surface). --target/--cwd reach subprocess only as list elements, not shell strings."
decision: APPROVE_WITH_COMMENTS
```

## Security summary (CRITICAL clean)

- **Command injection: NONE.** Every subprocess call across all 5 files uses list-form argv (`subprocess.run([...])`); no `shell=True`, no `os.system`, no string interpolation into a shell. User-controlled `--target` / `--cwd` flow into argv as discrete list elements and into `cwd=`, which git/codex/python treat as literal paths — not exploitable for shell escape.
- **Path traversal:** Scripts read/write under caller-supplied `--output-dir` / `--target`; no writes to `~/.claude/**`. WRITER_PATH points at `~/.claude/scripts/review-result-writer.sh` (read/exec only, via env override `GD_WRITER_PATH_OVERRIDE`) — invoked, never written. No `../` sanitization is done, but the tool's threat model is a local trusted operator, and paths are not concatenated into privileged locations. Acceptable for this context.
- **Hardcoded secrets: NONE.** Only hardcoded absolute paths (WRITER_PATH, SEND_WAIT_PATH) and test git identity `t@t.com` inside selftests.
- **Dangerous calls: NONE** (no eval/exec/pickle).
- **Bare except / silent swallow:** `gd-detect-review2-code-target.py` L49 (`except Exception: return None`) and L138 are intentional fail-closed fallbacks with documented behavior; `gd-review-router.py` L365 `except Exception: pass` swallows loop-report parse errors but defaults downstream_decision to "FAILED" (fail-closed), so acceptable.

## Selftest-in-production check

`gd-review-controller.py` carries StubDispatch + 6 selftests reachable via `--selftest`. Confirmed NOT in any production path: every prod caller (`run_branch_a/b/c`, `run_round1`, `run_round_n`) passes `stub_dispatch=None` and the stub branches are guarded by `if stub_dispatch is not None`. No leakage into live behavior — flagged only as maintainability (MEDIUM).
