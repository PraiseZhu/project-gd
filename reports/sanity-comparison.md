# Phase 4 Sanity Comparison Report

> **注意**：本报告为 static prompt comparison，不是旧 `/review` live verdict 对照。
> 旧 `/review` 的 `build_review_prompt()` 以静态文本分析（对照 `fixtures/old-review-prompt-readonly.md`），
> `/rev` 的 dry-run prompt 已生成（见各 run-dir/prompt.md），live verdict 因 sandbox proxy 阻断均为 `codex_timeout`。

---

## 报告概要

| 字段 | 值 |
|------|---|
| 报告类型 | static prompt comparison (非 live verdict) |
| 生成时间 | 2026-05-10T00:00:00Z |
| live runner 状态 | 全部 `codex_timeout`（sandbox proxy 阻断 OpenAI API）|
| 整体 sanity 结论 | `constrained`（dry-run + static comparison 通过，live verdict 无法获取） |

---

## Fixture 1: generic-bad-plan.md

### 元数据

| 字段 | 值 |
|------|---|
| `source_id` | `magical-humming-fern.md` |
| `expected_class` | `generic_bad` |
| `expected_rev_outcome` | `REQUIRES_CHANGES` |
| dry-run run-dir | `results/20260509T211740Z-plan.r2EEm5/` |
| live run-dir | `results/20260509T211847Z-plan.zERgyE/` |
| live verdict | `FAILED / codex_timeout` |

### Expected Findings

| tag | severity | match_terms |
|-----|----------|-------------|
| `missing_review_alignment` | P1 | "Review 对齐", "REVIEW_DOMAIN", "REVIEW_FOCUS" |
| `generic_sc_verify` | P2 | "验证", "可执行", "verify", "通过", "完成", "目视" |

### 旧 `/review` 限制（静态分析）

旧 `build_review_prompt()` 的主要限制：
- 无 `## Review 对齐` 节要求（不读取 REVIEW_DOMAIN/REVIEW_FOCUS）
- 无 SC 编号化验收结构要求
- verify 可执行性无专项检查
- 无 anti-fill 设计（"格式完整即通过"）

### `/rev` 新增约束

`rev-review-standard.md` 针对此类计划的检查点：
- SC-* 格式强制要求（每 SC 需有可执行 verify 命令）
- `## Review 对齐` 缺失为 P1 blocker
- "确认通过"/"目视确认" 等通用 verify 词被标为 generic_sc_verify (P2)

### dry-run evidence

```
bin/rev plan fixtures/sanity/generic-bad-plan.md --baseline-key phase4-generic-bad --dry-run
# exit 0
# stdout: DRY_RUN: true
# 无 REV_VERDICT: 行 ✓
# candidate-baseline.json: 4 SCs extracted
# prompt.md: contains rev-review-standard.md full text ✓
```

### live verdict

```
REV_VERDICT: FAILED
failure_reason: codex_timeout
```
_(sandbox proxy 阻断；静态分析替代 live verdict)_

---

## Fixture 2: concrete-good-plan.md

### 元数据

| 字段 | 值 |
|------|---|
| `source_id` | `phase-c-memory-index-first.md` |
| `expected_class` | `concrete_good` |
| `expected_rev_outcome` | `APPROVED` |
| dry-run run-dir | `results/20260509T211744Z-plan.GMJRPN/` |
| live run-dir | `results/20260509T211924Z-plan.UjlUzd/` |
| live verdict | `FAILED / codex_timeout` |

### Expected Findings

```
[] (空集 — 任何 P1/P2 finding 都算 sanity failure)
```

### 旧 `/review` 限制（静态分析）

旧 `build_review_prompt()` 不验证 SC verify 可执行性，也没有 anti-fill 机制。如果旧 reviewer "感觉这个计划结构完整"就可能 APPROVED，但无法区分"结构完整但 verify 形式化"和"结构完整且 verify 可执行"的差异。

### `/rev` 新增约束

`rev-review-standard.md` 额外检查：
- REVIEW_FOCUS 驱动检查方向（ai_infra domain）
- SC verify 可执行性（smoke test 命令可运行）
- 量化指标（< 8k token 增量）

### dry-run evidence

```
bin/rev plan fixtures/sanity/concrete-good-plan.md --baseline-key phase4-concrete-good --dry-run
# exit 0
# stdout: DRY_RUN: true
# 无 REV_VERDICT: 行 ✓
# candidate-baseline.json: 8 SCs extracted
# prompt.md: contains rev-review-standard.md full text ✓
```

### live verdict

```
REV_VERDICT: FAILED
failure_reason: codex_timeout
```
_(sandbox proxy 阻断；静态分析替代 live verdict)_

---

## Fixture 3: borderline-plan.md

### 元数据

| 字段 | 值 |
|------|---|
| `source_id` | `purring-puzzling-willow.md` |
| `expected_class` | `borderline` |
| `expected_rev_outcome` | `REQUIRES_CHANGES` |
| dry-run run-dir | `results/20260509T211751Z-plan.5hNgSL/` |
| live run-dir | `results/20260509T211946Z-plan.PZZN3Q/` |
| live verdict | `FAILED / codex_timeout` |

### Expected Findings

| tag | severity | match_terms |
|-----|----------|-------------|
| `sc_missing_executable_verify` | P2 | "验证", "命令", "test -f", "executable", "可执行", "目视" |

### 旧 `/review` 限制（静态分析）

旧 `build_review_prompt()` 不区分"有 Review 对齐"和"Review 对齐内容是否有深度"。SC 格式存在即可能通过检查。SC-1/2/3 的 verify 均为"目视确认"，旧 reviewer 可能认为"格式完整"而 APPROVED。

### `/rev` 新增约束

`rev-review-standard.md` 明确要求：
- 每个 SC 的 verify 必须有可执行命令或可重现测试用例
- "目视确认" 单独作为 verify 标准不满足要求
- 会触发 `sc_missing_executable_verify` (P2) finding

### borderline 判定依据

此计划 **格式正确**（有 Review 对齐、有 SC 表）但 **verify 弱**（全部"目视确认"）。这是典型的 borderline 案例：
- 旧 reviewer 可能 APPROVED（"格式符合要求"）
- `/rev` 应检测 verify 可执行性并出 `REQUIRES_CHANGES` (P2)

### dry-run evidence

```
bin/rev plan fixtures/sanity/borderline-plan.md --baseline-key phase4-borderline --dry-run
# exit 0
# stdout: DRY_RUN: true
# 无 REV_VERDICT: 行 ✓
# candidate-baseline.json: 3 SCs extracted
# prompt.md: contains rev-review-standard.md full text ✓
```

### live verdict

```
REV_VERDICT: FAILED
failure_reason: codex_timeout
```
_(sandbox proxy 阻断；静态分析替代 live verdict)_

---

## 整体 Sanity 判定

| 维度 | 结果 | 说明 |
|------|------|------|
| dry-run sanity | pass | 3 fixtures 均 exit 0，stdout 无 REV_VERDICT: |
| SC-15 embed | pass | 3 prompt.md 均含 rev-review-standard.md 全文 |
| live verdict | constrained | sandbox proxy 阻断 → codex_timeout × 3 |
| static prompt analysis | pass | old /review 与 /rev 结构差异已文档化 |

**overall sanity verdict: constrained**

---

## 说明

- 本报告是 static prompt comparison，不是旧 `/review` live verdict 对照
- 旧 `/review` live 调用未执行（非目标，参见 Project GD 约束）
- live `/rev` 受 sandbox proxy 阻断，不代表 `/rev` runner 本身缺陷
- Phase 4 最终状态：`completed_with_constraint`
