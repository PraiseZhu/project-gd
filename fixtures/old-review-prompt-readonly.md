# Old Review Prompt — READONLY

> **只读提取（Phase 4 SC-3）**
> 来源：`/Users/praise/.claude/handoff/bin/codex-watch` line 58–160
> 提取方式：`sed -n '58,160p' codex-watch`
> 用途：A/B 静态对照（不运行旧 live /review）
> 提取时间：2026-05-10T00:00:00Z

---

## 提取段落：`build_review_prompt()` 函数

```bash
build_review_prompt() {
  local capsule_content="$1"

  local review_kind review_domain review_delta_scope review_focus review_focus_source plan_alignment_present
  review_kind=$(grep -m1 '^REVIEW_KIND:' <<< "$capsule_content" | sed 's/^REVIEW_KIND:[[:space:]]*//' || echo "code")
  review_domain=$(grep -m1 '^REVIEW_DOMAIN:' <<< "$capsule_content" | sed 's/^REVIEW_DOMAIN:[[:space:]]*//' || echo "app_code")
  review_delta_scope=$(grep -m1 '^REVIEW_DELTA_SCOPE:' <<< "$capsule_content" | sed 's/^REVIEW_DELTA_SCOPE:[[:space:]]*//' || echo "full_matrix")
  review_focus=$(grep -m1 '^REVIEW_FOCUS:' <<< "$capsule_content" | sed 's/^REVIEW_FOCUS:[[:space:]]*//' || echo "")
  review_focus_source=$(grep -m1 '^REVIEW_FOCUS_SOURCE:' <<< "$capsule_content" | sed 's/^REVIEW_FOCUS_SOURCE:[[:space:]]*//' || echo "")
  plan_alignment_present=$(grep -m1 '^PLAN_ALIGNMENT_PRESENT:' <<< "$capsule_content" | sed 's/^PLAN_ALIGNMENT_PRESENT:[[:space:]]*//' || echo "false")

  local focus_instruction=""
  if [[ -n "$review_focus" && "$review_focus" != "N/A" ]]; then
    focus_instruction="
REVIEW_FOCUS (source: ${review_focus_source:-unknown}): ${review_focus}
The '## Scope Checked' table MUST use these focus items as the check rows. Do NOT substitute your own matrix."
  fi

  local template_instruction
  if [[ "$review_kind" == "plan" ]]; then
    template_instruction="OUTPUT FORMAT: Use the Plan Review template.
Your response MUST start with '# Plan Review Result' then VERDICT, REVIEW_DOMAIN, REVIEW_MODE, REVIEW_DELTA_SCOPE lines.
Then a '## Scope Checked' table (max 3-5 rows): | 检查面 | 结论 | 证据（≤30字） |${focus_instruction}
Then '## Findings' — ONLY P1/P2 blockers. Each finding:
### Finding N [P1|P2] <title>
问题: <plan gap that would cause goal failure>
证据: <plan paragraph/path/command>
影响: <what goes wrong if plan executes as-is>
最小修复: <what to add, not scope expansion>
验收: <how to confirm the fix>
Then '## Residual Risk' for P3/non-blocking items (or 'none')."
  else
    template_instruction="OUTPUT FORMAT: Use the Code Review template.
Your response MUST start with '# Code Review Result' then VERDICT, REVIEW_DOMAIN, REVIEW_MODE, REVIEW_DELTA_SCOPE lines.
Then a '## Scope Checked' table (max 3-5 rows): | 检查面 | 结论 | 证据（≤30字） |${focus_instruction}
Then '## Findings' — ONLY P1/P2 blockers. Each finding:
### Finding N [P1|P2] <short title, no paths>
问题: <obvious bug in current code>
证据: <file:line/command output/isolated repro>
影响: <which active path fails or makes validation unreliable>
最小修复: <which files/functions/configs to change>
验收: <executable command or isolated test case>
Then '## Residual Risk' for P3/non-blocking items (or 'none')."
  fi

  local convergence_instruction=""
  if [[ "$review_delta_scope" == "prior_findings_only" || "$review_delta_scope" == "direct_downstream" ]]; then
    convergence_instruction="
CONVERGENCE (follow-up review, DELTA_SCOPE=${review_delta_scope}):
- Default scope: ONLY check prior round blockers + their direct downstream.
- Narrow escape hatch: you MAY add a NEW finding ONLY if ALL conditions hold:
  (1) It is a P1/P2 blocker from the Blocker threshold list.
  (2) It was introduced in THIS round's diff (not a pre-existing issue).
  (3) The finding includes: changed_in_this_round: <diff/file/line> and why_not_scope_creep: <explanation>.
- Same root cause blocks at most 2 rounds. After round 2, only P1/P2 meeting blocker threshold may continue.
- Old findings not repeated; if superseded, one line in Residual Risk.
- Forbidden: unrelated historical issues, new global matrix scans, P3 cleanup, style/architecture preferences."
  fi

  cat <<PROMPT_EOF
You are a single-pass code review assistant. Read the Review Capsule and produce a lightweight structured review.

IMPORTANT: Your response MUST contain exactly one of these lines:
  VERDICT: APPROVED
  VERDICT: REQUIRES_CHANGES

REVIEW_MODE: single_pass — one pass, catch obvious bugs, minimal tokens, no multi-round.

${template_instruction}

DOMAIN: ${review_domain}
DELTA_SCOPE: ${review_delta_scope}
${convergence_instruction}

BLOCKER THRESHOLD (REQUIRES_CHANGES only for these):
- Active path will fail
- User goal not met
- Baseline/state/mirror affects subsequent runs
- Generation pipeline continues producing wrong output
- Security, data, irrecoverable risk
- Core validation missing to the point success cannot be judged

DO NOT BLOCK for:
- Style preferences, architecture aesthetics
- Dormant code
- Stale docs that don't affect runtime
- Non-active-path cleanup
- Potential optimizations without failure evidence
- Items listed in OUT_OF_SCOPE, USER_ACCEPTED_DECISIONS, or KNOWN_LIMITATIONS

QUALITY RULES:
- Each finding needs concrete evidence (file paths, line numbers, command output).
- Each finding needs 最小修复 (what exactly to fix) and 验收 (how to verify).
- No vague suggestions ('consider...', 'might want to...'). Non-blocking items go in Residual Risk only.
- P3 items MUST go in Residual Risk, never as findings.

Follow the REVIEW_RULES specified in the capsule.

--- BEGIN CAPSULE ---
${capsule_content}
--- END CAPSULE ---
PROMPT_EOF
}
```

---

## 与 `/rev` 的差异摘要（静态对照）

| 维度 | 旧 `/review` (`build_review_prompt`) | `/rev` (`rev-review-standard.md`) |
|------|--------------------------------------|-----------------------------------|
| 模板来源 | 动态 heredoc，嵌入 codex-watch | 单一文件，CLI + 桌面端共用 |
| VERDICT 标记 | `VERDICT:` | `REV_VERDICT:`（避免触发 review-stop-marker.js） |
| 输入形式 | Review Capsule（结构化字段） | Plan 文件或执行结果文件 |
| SC 对照 | 无 SC 结构 | 逐条 SC 验收（conformance gate） |
| anti-fill 机制 | 无针对性设计 | SC 编号化 + 证据 anchor + not_run_reason |
| 结果写入 | `review-result-writer.sh` | `scripts/rev-result-writer.sh`（lab-only） |

> 注：此对照为静态 prompt 分析，不代表旧 `/review` live verdict 结果。
