# Plan Review Loop Report

TEMPLATE_KIND: gd-plan-review-loop-report
GD_STANDARD: Project GD/prompts/gd-review-standard.md

---

## 运行信息

```yaml
LOOP_ID: <plan-file-slug>-<YYYYMMDDHHmmss>
LOOP_STATUS: completed | auto_fix_exhausted | codex_transport_unavailable | degraded
TOTAL_ROUNDS: <N>
FINAL_VERDICT: APPROVED | REQUIRES_CHANGES | FAILED
```

---

## 各轮详情

<!-- 每轮复制以下 block，按 round 编号递增 -->

### Round 1

```yaml
round: 1
type: initial_review
claude_verdict: APPROVED | REQUIRES_CHANGES | FAILED
codex_verdict: APPROVED | REQUIRES_CHANGES | FAILED | transport_unavailable
merge_verdict: APPROVED | REQUIRES_CHANGES
findings_count:
  claude: <N>
  codex: <N>
  merged_unique: <N>
changes_applied: true | false
```

**Claude Findings**：

| # | Severity | SC Ref | 摘要 |
|---|----------|--------|------|
| 1 | P1/P2 | SC-N | <一句话> |

**Codex Findings**：

| # | Severity | SC Ref | 摘要 |
|---|----------|--------|------|
| 1 | P1/P2 | SC-N | <一句话> |

**Merged Findings（去重后）**：

| # | Severity | SC Ref | 摘要 | 来源 |
|---|----------|--------|------|------|
| 1 | P1/P2 | SC-N | <一句话> | claude / codex / both |

**本轮修复**：

- <具体修改描述>
- <文件路径 + 改动行数>

---

### Round 2（仅当 merge_verdict != APPROVED 时存在）

```yaml
round: 2
type: fix_round
claude_verdict: APPROVED | REQUIRES_CHANGES | FAILED
codex_verdict: APPROVED | REQUIRES_CHANGES | FAILED | transport_unavailable
merge_verdict: APPROVED | REQUIRES_CHANGES
findings_count:
  claude: <N>
  codex: <N>
  merged_unique: <N>
changes_applied: true | false
```

<!-- 重复 Round 1 的 Findings/Fix 结构 -->

---

### Round 3（仅当 merge_verdict != APPROVED 时存在）

```yaml
round: 3
type: fix_round
claude_verdict: APPROVED | REQUIRES_CHANGES | FAILED
codex_verdict: APPROVED | REQUIRES_CHANGES | FAILED | transport_unavailable
merge_verdict: APPROVED | REQUIRES_CHANGES
findings_count:
  claude: <N>
  codex: <N>
  merged_unique: <N>
changes_applied: true | false
```

<!-- 重复 Round 1 的 Findings/Fix 结构 -->

---

### Round 4（仅 auto_fix_exhausted 时存在）

```yaml
round: 4
type: exhausted_gate
note: "第 3 轮后 review 仍 REQUIRES_CHANGES，不再执行第 4 轮 fix"
```

---

## 残余风险

| 风险 | 严重度 | 原因 |
|------|--------|------|
| <描述> | P1/P2/P3 | <为何未修复 / 为何接受> |