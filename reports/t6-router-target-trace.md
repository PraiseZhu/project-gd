# T6 Router Target Trace Report

**task_id**: t6-fix-bridge-target
**traced_file**: scripts/gd-review-router.py
**traced_at**: 2026-06-09
**purpose**: SC-6.4 — confirm whether `--target` args passed by the router to the bridge point to real artifacts or capsule.md envelopes.

---

## Summary

All `--target str(target)` call sites in the router pass the **same `target` variable** that the router received as its top-level CLI argument (`--target <path>`). The router does NOT construct or synthesise a capsule.md path internally. The `target` value is therefore whatever the caller passed — which is the real execution artifact (JSON result file) or plan file.

**Verdict**: No router-side capsule-as-target bug was found. The "same disease" (H9) lives in the bridge's `build_capsule_text`, which previously wrote `PRIMARY_TARGET: <target_abs>` regardless of whether `target` was the real artifact or a capsule. That path has been fixed by T6 in the bridge via `_assert_not_capsule_target` + `_primary_target_for_kind`.

---

## Traced `--target` Call Sites

### Site 1 — Line 438 (`_run_live_codex_bridge`, run-bridge call)

```python
# Line 435-442
run_args = [
    sys.executable, str(bridge_script), "run-bridge",
    "--kind", kind,
    "--target", str(target),   # <-- line 438
    "--cwd", str(GD_ROOT),
    "--out", str(run_out),
    "--live-transport",
]
```

**Caller context**: `_run_live_codex_bridge(kind, target, ...)` where `target` is the Path
passed from `_run_live_execution_only` (line 683) or `_run_live_execution_plus_code`
(line 932) — in both cases `target` is the real execution artifact passed via CLI `--target`.

**Is target a real artifact?** YES — `target` is the execution result JSON or plan file.
`_run_live_execution_only` receives `target` from `run_live(...)` line 1060 which uses
`args.target` (the CLI argument). Same for `_run_live_execution_plus_code`.

**Verdict**: CLEAN — no capsule.md introduced here.

---

### Site 2 — Line 468 (`_run_live_codex_bridge`, parse-transport call)

```python
# Line 465-471
parse_args = [
    sys.executable, str(bridge_script), "parse-transport",
    "--kind", kind,
    "--target", str(target),   # <-- line 468
    "--raw-result", str(transport_raw),
    "--out", str(mapped_out),
]
```

**Same `target` variable** from Site 1. No transformation between lines 438 and 468.

**Is target a real artifact?** YES.

**Verdict**: CLEAN.

---

### Site 3 — Line 628 (`_run_live_execution_only`, Path A: parse-transport with injected raw)

```python
# Line 625-631
parse_args = [
    sys.executable, str(bridge_script), "parse-transport",
    "--kind", "execution_outcome",
    "--target", str(target),   # <-- line 628
    "--raw-result", str(codex_raw_result),
    "--out", str(mapped_out),
]
```

**Caller**: `_run_live_execution_only(target, ...)`. `target` is the execution artifact
received from `run_live(args)` line 1060. The injection path (Path A) is invoked when
`codex_raw_result` is provided via `--codex-raw-result` CLI arg; `target` is still the
real execution artifact.

**Is target a real artifact?** YES.

**Verdict**: CLEAN.

---

### Site 4 — Line 886 (`_run_live_execution_plus_code`, Path A: parse-transport with injected raw)

```python
# Line 883-889
parse_args = [
    sys.executable, str(bridge_script), "parse-transport",
    "--kind", "combined",
    "--target", str(target),   # <-- line 886
    "--raw-result", str(codex_raw_result),
    "--out", str(mapped_out),
]
```

**Caller**: `_run_live_execution_plus_code(target, ...)`. `target` is the execution artifact
received from `run_live(args)` line 1072. Same pattern as Site 3 for the combined kind.

**Is target a real artifact?** YES.

**Verdict**: CLEAN.

---

## Router-level Fix Needed?

**No router-side fix required.**

The router's `target` variable originates from `args.target` (CLI `--target <path>`) and is
passed unchanged through all four sites. The router never replaces it with a capsule path.

The root defect was in `build_capsule_text` (bridge):
- Previously: `PRIMARY_TARGET: {target_abs}` written unconditionally, and `REVIEW_FOCUS` was
  hardcoded as `"bridge candidate review of {target.name}"` regardless of kind.
- After T6: `_assert_not_capsule_target` raises early if a capsule.md arrives for non-plan
  kinds; `_review_focus_for_kind` generates kind-specific focus; `_primary_target_for_kind`
  ensures the correct path is used.

The router sites at 438/468/628/886 are all clean — they forward the real artifact.

---

## No Router Code Modified

Since all four `--target` sites are already pointing to real artifacts (not capsule.md),
no router code change is needed under T6. The SC-6.4 trace result is:

| Site | Line | Kind | target source | Points to real artifact? | Fix needed? |
|------|------|------|---------------|--------------------------|-------------|
| 1 | 438 | execution_outcome/combined | `_run_live_codex_bridge` arg from `_run_live_execution_only`/`_run_live_execution_plus_code` → `args.target` | YES | NO |
| 2 | 468 | execution_outcome/combined | same `target` as Site 1 | YES | NO |
| 3 | 628 | execution_outcome | `_run_live_execution_only` arg → `args.target` | YES | NO |
| 4 | 886 | combined | `_run_live_execution_plus_code` arg → `args.target` | YES | NO |

All CLEAN. Bridge fix in `build_capsule_text` is the correct and sufficient repair (T6).
