# Phase 4 Sanity + Parity Audit — 终点报告

> **项目状态**：`project_status: terminal`
> **efficacy verdict**: `out_of_scope`（三个限制：n=3 不足、live runner 全被 sandbox proxy 阻断、无对照组真实 verdict）
> **Phase 4 状态**：`completed_with_constraint`（dry-run/parity/no-write 全通过；live runner codex_timeout × 3）

---

## 总览

| 字段 | 值 |
|------|---|
| 报告类型 | Phase 4 终点审计 |
| 生成时间 | 2026-05-10T00:00:00Z |
| Phase 4 状态 | `completed_with_constraint` |
| project_status | `terminal` |
| efficacy verdict | `out_of_scope` |
| overall sanity verdict | `constrained` |

---

## Phase 1-4 状态表

| Phase | 名称 | 状态 |
|-------|------|------|
| 1 | Template Setup | `approved` |
| 2 | Runner + Baseline | `completed_with_constraint`（live runner sandbox 阻断） |
| 3 | Execution Conformance Gate | `completed` |
| 4 | Sanity Check + Parity Audit | `completed_with_constraint`（live runner codex_timeout × 3） |

---

## Sanity Fixtures 表

### 预期 vs 实际（dry-run + live）

| fixture | expected_class | expected_rev_outcome | dry-run | live verdict | sanity |
|---------|---------------|---------------------|---------|-------------|--------|
| `generic-bad-plan.md` | `generic_bad` | `REQUIRES_CHANGES` | exit 0, 4 SCs, 无 REV_VERDICT: ✓ | `codex_timeout` | `constrained` |
| `concrete-good-plan.md` | `concrete_good` | `APPROVED` | exit 0, 8 SCs, 无 REV_VERDICT: ✓ | `codex_timeout` | `constrained` |
| `borderline-plan.md` | `borderline` | `REQUIRES_CHANGES` | exit 0, 3 SCs, 无 REV_VERDICT: ✓ | `codex_timeout` | `constrained` |

### Expected findings（结构化 tag 集合）

| fixture | expected_findings |
|---------|-----------------|
| `generic-bad-plan.md` | `[{tag: missing_review_alignment, P1}, {tag: generic_sc_verify, P2}]` |
| `concrete-good-plan.md` | `[]`（任何 P1/P2 都算 sanity failure） |
| `borderline-plan.md` | `[{tag: sc_missing_executable_verify, P2}]`（严格等价） |

> Live verdict 均为 `codex_timeout`（sandbox proxy 阻断 OpenAI API），未能获取实际 finding 集合用于集合关系验证。
> 根据 SC-13：live runner 仅产出 `codex_timeout` → Phase 4 状态 = `completed_with_constraint`，不能 `completed`。

---

## Static Prompt Comparison 摘要

> 注：本摘要基于 static prompt analysis，不是旧 `/review` live verdict 对照（见 `reports/sanity-comparison.md`）。

### 旧 `/review` 结构特征（静态分析）

| 维度 | 旧 `/review` (`build_review_prompt`) |
|------|--------------------------------------|
| 模板来源 | 动态 heredoc，嵌入 codex-watch |
| VERDICT 标记 | `VERDICT:` |
| SC 对照 | 无 SC 编号化结构 |
| Review 对齐节 | 无 REVIEW_DOMAIN/REVIEW_FOCUS 要求 |
| anti-fill 机制 | 无针对性设计 |

### `/rev` 新增约束

| 维度 | `/rev` (`rev-review-standard.md`) |
|------|----------------------------------|
| 模板来源 | 单一文件，CLI + 桌面端共用 |
| VERDICT 标记 | `REV_VERDICT:`（避免触发 review-stop-marker.js） |
| SC 对照 | 逐条 SC 验收（conformance gate） |
| Review 对齐节 | 强制要求 REVIEW_DOMAIN/REVIEW_FOCUS |
| anti-fill 机制 | SC 编号化 + 证据 anchor + not_run_reason |

### 三类计划的静态分析差异

| fixture class | 旧 `/review` 可能结果（静态推断） | `/rev` 预期结果 | 关键差异 |
|--------------|--------------------------------|----------------|---------|
| `generic_bad` | 可能 APPROVED（无 SC 格式要求，verify 泛化不检查） | `REQUIRES_CHANGES`（P1: missing_review_alignment, P2: generic_sc_verify） | Review 对齐节 + verify 可执行性检查 |
| `concrete_good` | 可能 APPROVED（结构完整即通过） | `APPROVED`（无 P1/P2 finding） | 精细化 SC verify 检查 |
| `borderline` | 可能 APPROVED（格式完整即通过） | `REQUIRES_CHANGES`（P2: sc_missing_executable_verify） | "目视确认"单独作为 verify 不满足要求 |

---

## Parity 表

| 维度 | 结论 |
|------|------|
| CLI runner prompt embed | `bin/rev plan` 直接 `cat "$REVIEW_STD"` 嵌入原文 |
| 桌面端 parity 约定 | `CLAUDE.md` 明确要求 `REVIEW_STANDARD:` 声明 |
| 模板声明 | `plan-template.md` + `execution-result-template.md` 均硬编码引用 |
| 共同标准源 | `Project GD/prompts/rev-review-standard.md` — 唯一真源 |
| SC-15 embed 验证 | 6 个 prompt.md 全部 PASS（去空白后子串匹配） |

**parity verdict: PASS**

---

## `.claude` No-Write 审计（三层计数）

```
marker: reports/phase-4-start.marker (2026-05-09T20:47:19Z)
scan: ~/.claude/{commands,review-baselines,state,handoff,scripts/hooks}

raw_count:           4
filtered_count:      3  (排除 heartbeat: /handoff/state/heartbeat)
phase4_attributable: 0  (无 review-baselines/phase4-* 文件)
```

### 三层详情

| 层 | 文件 | 说明 |
|----|------|------|
| raw (4) | `/handoff/state/heartbeat` | heartbeat，下一层过滤 |
| filtered (3) | `state/review-chain-verify/baseline/4d46d3ce.json` | review-chain-verify 系统状态 |
| filtered (3) | `state/review-chain-verify/touched/bc744b19.json` | 当前会话 review-chain-verify |
| filtered (3) | `state/review-chain-verify/audit/bc744b19.json` | 当前会话 review-chain-verify |
| attributable (0) | —— | 无 `review-baselines/phase4-` 命中 |

**结论**：`attributable = 0`，Phase 4 未向 `.claude` 写入任何文件。
`filtered = 3 > 0`：3 个 `state/review-chain-verify/` 文件为 review-chain hook 系统自动维护（外部并发），非 Phase 4 触发 → 降级为 **warning**，不阻断。

**no-write verdict: PASS（attributable = 0）**

---

## SC 验收状态

| SC | 描述 | 状态 | 证据 |
|----|------|------|------|
| SC-0 | `reports/phase-4-start.marker` 存在 | pass | `test -f reports/phase-4-start.marker` → 0 |
| SC-1 | `manifest.json phases.3.status == "completed"` | pass | 读取确认 |
| SC-2 | `bin/rev plan --help` 含 `--dry-run`；smoke run 无 REV_VERDICT: | pass | P1 fix applied: 子命令 --help 支持已加入 bin/rev while 循环；`bin/rev plan --help \| grep -q -- '--dry-run' && echo PASS` → PASS；`bin/rev code --help \| grep -q -- '--dry-run' && echo PASS` → PASS |
| SC-3 | `fixtures/old-review-prompt-readonly.md` 存在（只读提取） | pass | 文件存在，build_review_prompt() 段提取 |
| SC-4 | `reports/phase-4-source-hashes.json` 含 4 个 sha256 字段 | pass | 文件存在，字段完整 |
| SC-5 | 候选 census ≥ 6 个，全 outside Project GD | pass | `reports/phase-4-sanity-candidate-census.md`，8 个候选 |
| SC-6 | Phase 4A 停在用户确认 gate；未确认前不创建 fixture | pass | 用户在对话中确认 3 个 fixture 后才固化 |
| SC-7 | `fixtures/sanity/` 下恰好 3 个脱敏 fixtures | pass | generic-bad / concrete-good / borderline |
| SC-8 | 每个 fixture 顶部 YAML frontmatter 含完整 metadata | pass | source_id/source_sha256/expected_class/expected_rev_outcome/expected_findings 均存在 |
| SC-9 | 3 个 fixtures 的 dry-run 生成 prompt.md + candidate-baseline.json，无 REV_VERDICT: | pass | exit 0 × 3，run-dir 各含两个产物 |
| SC-10 | live generic_bad 返回 REQUIRES_CHANGES，findings ⊇ expected | not_run | codex_timeout |
| SC-11 | live concrete_good 返回 APPROVED；任何 P1/P2 即 fail | not_run | codex_timeout |
| SC-12 | live borderline P1/P2 findings 严格等于 expected | not_run | codex_timeout |
| SC-13 | live runner failure → completed_with_constraint | pass | 全部 codex_timeout → Phase 4 状态 completed_with_constraint |
| SC-14 | `sanity-comparison.md` 标注 static prompt comparison | pass | 报告首行明确标注 |
| SC-15 | dry-run prompt.md 字面包含 rev-review-standard.md 全文 | pass | 6 prompt.md 去空白后子串匹配全 PASS |
| SC-16 | `parity-check.md` 含 SC-15 embed 证据 + 5 个引用点 | pass | R-1 至 R-5 全部文档化 |
| SC-17 | no-write 三层计数；attributable = 0 | pass | raw=4 / filtered=3 / attributable=0 |
| SC-18 | `efficacy verdict: out_of_scope`，`project_status: terminal`，不声称 /rev 优于 /review | pass | 本报告及 sanity-comparison.md 均符合 |
| SC-19 | `manifest.json` 新增 `phases.4` + 顶层 `project_status: terminal` | pass | 本次更新写入 |

---

## 残余风险

| 风险 | 级别 | 说明 |
|------|------|------|
| Live sanity 未完成 | P2 | sandbox proxy 阻断，codex_timeout × 3；干扰因素外部，非 /rev 缺陷 |
| Efficacy 未评估 | P3 | 明确 out_of_scope，本项目 n=3 + 无对照组 + 无 live verdict，三限制均不支持 efficacy 结论 |
| state/review-chain-verify 写入 | info | 3 个文件由 review-chain hook 系统自动维护，非 Phase 4 触发，attributable=0 |

---

## 项目终点声明

- **efficacy verdict: out_of_scope** — 本项目未评估 `/rev` 是否真正减少 anti-fill 问题。n=3，live runner 全被 sandbox 阻断，无对照组，三个限制均不支持 efficacy 结论。
- **project_status: terminal** — Phase 4 是最终阶段；Phase 5 不存在，不规划。
- **不声明 `/rev` 优于 `/review`** — 仅完成了 sanity（dry-run）+ parity（共同标准源）审计。
- **Phase 4 结论：completed_with_constraint** — dry-run sanity、SC-15 embed、parity、no-write 均通过；live sanity 受 sandbox 阻断，无法得出有效 verdict。
