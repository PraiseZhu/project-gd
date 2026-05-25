# v8 Dependency Check Report

> 生成日期：2026-05-26
> 任务：`/review2 plan_review` 与模板对齐修正 v8 — Phase 1 输出
> SC 映射：SC-1、SC-11
> 权威源：`/Users/praise/AI-Agent/Codex/plans/2026-05-25-project-gd-review2-plan-review-template-alignment.md`（v5 + v8 增量）

---

## SECTION 1: V2_TEMPLATE_EXISTENCE

| Kind | Template File | Status | 说明 |
|------|--------------|--------|------|
| `plan` | `templates/gd-plan-review-v2-template.md` | **MISSING** | `TEMPLATE_BY_KIND_V2["plan"]` 指向不存在的文件 |
| `code_diff` | `templates/gd-code-diff-review-template.md` | **MISSING** | `TEMPLATE_BY_KIND_V2["code_diff"]` 指向不存在的文件 |
| `execution_outcome` | `templates/gd-execution-outcome-review-template.md` | EXISTS (2060B) | 正常可用 |
| `combined` | `templates/gd-combined-review-template.md` | EXISTS (1952B) | 正常可用 |

**当前影响**：`build_capsule_text`（line 967）对不存在的 template 静默退化为字符串 `"(missing)"`，不报错不退出。这是 SC-8 的根因。

---

## SECTION 2: COMPAT_V1_FALSE_CALLERS

### 2a. `_failed_mapped` error-path calls（非 `build_capsule_text`，不受 B3 影响）

这些是 `_failed_mapped(...)` 辅助函数调用，内部构造退化结果 object，`compat_v1=False` 是它们的参数，**不是** `build_capsule_text` 的调用：

| 文件 | 行号 | 说明 |
|------|------|------|
| `scripts/gd-codex-bridge-review.py` | 749 | `_failed_mapped(...)` — raw 缺 v2 title |
| `scripts/gd-codex-bridge-review.py` | 760 | `_failed_mapped(...)` — 缺 gd-review-result-json block |
| `scripts/gd-codex-bridge-review.py` | 769 | `_failed_mapped(...)` — degraded |
| `scripts/gd-codex-bridge-review.py` | 780 | `_failed_mapped(...)` — JSON block 解析失败 |
| `scripts/gd-codex-bridge-review.py` | 789 | `_failed_mapped(...)` — 顶层不是 object |
| `scripts/gd-codex-bridge-review.py` | 810 | `_failed_mapped(...)` — degraded |
| `scripts/gd-codex-bridge-review.py` | 824 | `_failed_mapped(...)` — degraded |
| `scripts/gd-codex-bridge-review.py` | 841 | `_failed_mapped(...)` — v2 mapped schema fail |

### 2b. Self-test parse/validate calls（非 `build_capsule_text`，不受 B3 影响）

| 文件 | 行号 | 调用 |
|------|------|------|
| `scripts/gd-codex-bridge-review.py` | 1692 | `parse_raw_to_mapped("plan", ..., compat_v1=False)` |
| `scripts/gd-codex-bridge-review.py` | 1693 | `parse_raw_to_mapped("plan", ..., compat_v1=False)` |
| `scripts/gd-codex-bridge-review.py` | 1694 | `validate_mapped_schema(mapped_a, compat_v1=False)` |
| `scripts/gd-codex-bridge-review.py` | 1695 | `validate_mapped_schema(mapped_b, compat_v1=False)` |

### 2c. Smoke test `--no-compat-v1` caller

| 文件 | 行号 | Kind | 说明 |
|------|------|------|------|
| `scripts/gd-bridge-compat-smoke.sh` | 65 | `execution_outcome` | 测试 v2 模式拒绝 v1 raw；该 kind 有 template，**不受 B3 guard 影响** |

**结论**：没有任何 smoke/caller 对 `plan` 或 `code_diff` 做 `compat_v1=False` 的 `build_capsule_text` 调用。B3 guard 仅影响 `build_capsule_text` 内部逻辑，不会误伤现有 smoke test。

---

## SECTION 3: BUILD_CAPSULE_TEXT_CALLERS

| 文件 | 行号 | 调用上下文 | B3 guard 影响 |
|------|------|-----------|--------------|
| `scripts/gd-codex-bridge-review.py` | 920 | **函数定义** — `def build_capsule_text(...)` | guard 加在此处 |
| `scripts/gd-codex-bridge-review.py` | 1081 | `cmd_build_capsule` — standalone `build-capsule` subcommand | 受影响：kind=plan → ValueError |
| `scripts/gd-codex-bridge-review.py` | 1174 | `_cmd_run_bridge_inner` — live bridge 执行路径 | 受影响：kind=plan → ValueError → exit 1 |
| `scripts/gd-codex-bridge-review.py` | 1797 | self-test v2 routing fixture | 受影响（见 Fixture Impact section） |

**Phase 5 修改点**：
1. Line 920 函数体内加 B3/B4 guard
2. Line 1174 的 caller (`_cmd_run_bridge_inner`) 的 `except ValueError` 分支需捕获 `V2_TEMPLATE_NOT_READY` → exit 1
3. Line 1081 caller (`cmd_build_capsule`) 是否同样需要 exit 1 处理 — 是，保持一致

---

## SECTION 4: PLAN_TEMPLATE_REFERENCES

非 `.planning/`、非 `.claude/`、非 `results/` 目录下的引用：

| 文件 | 行号 | 引用类型 | 是否受 Phase 3 影响 |
|------|------|---------|-------------------|
| `manifest.gd-v7.json` | 565 | legacy reference（`"(legacy)"` 标注） | 不动（已标 legacy） |
| `PROJECT_GOAL.md` | 85, 86 | live template 路径 + Codex copy 路径 | **不动**（dirty file，禁止修改） |
| `PROJECT_GOAL.md` | 100 | GD lab copy 路径 | **不动**（dirty file） |
| `PROJECT_GOAL.md` | 185 | SC-7 引用 | **不动**（dirty file） |
| `PROJECT_GOAL.md` | 276 | diff check 命令引用 | **不动**（dirty file） |
| `manifest.json` | 17 | project manifest 文件列表 | 不动（清单，不影响逻辑） |
| `docs/gd-v7-shared-core-index.md` | 97 | 索引表（共存说明） | 不动（文档，不影响逻辑） |
| `fixtures/sanity/borderline-plan.md` | 80 | fixture 内部引用 `~/.claude/templates/plan-template.md` | 不动（fixture 内容，只是提及路径） |

**Phase 3 写入目标**：`templates/plan-template.md`（worktree 内的 source 副本）。
**live runtime 不同步**：`~/.claude/templates/plan-template.md` 在本 worktree 任务范围内不更新（残余 drift 在 Phase 6 final report 量化）。

---

## SECTION 5: HOOK_BEHAVIOR_PROBE

### 测试方法

Hook：`/Users/praise/.claude/scripts/hooks/review-stop-marker.js`
沙盒：`HOME=$(mktemp -d)`
输入格式：`{session_id, tool_input: {command: "..."}, tool_output: "..."}`
判定：`find $SANDBOX_HOME -name "*.json" -path "*/review-stop/*"` 是否非空

### Hook 触发条件（静态分析）

- line 33-36: 仅当 `command` 包含 `codex-send-wait` 或 `review-result-writer.sh` 时才继续
- line 40-43: 若 `command` 包含 `--no-stop-marker` → 立即 return（跳过 marker 写入）
- line 48-51: 匹配 output 中 `VERDICT: APPROVED|REQUIRES_CHANGES` 或 `[REVIEW] APPROVED|...` → 写入 marker

### Probe 结果

| 测试用例 | command 包含 | output 包含 | 结果 |
|---------|------------|-----------|------|
| CASE1（控制组） | `review-result-writer.sh` | `VERDICT: APPROVED` | **HOOK_BLOCKS**（marker 写入 sandbox）✓ |
| CASE2（bridge 实际调用模式） | `review-result-writer.sh --no-stop-marker` | `VERDICT: APPROVED` | **HOOK_NEUTRAL**（marker 不写入）✓ |

**结论**：bridge 现已在 line 1223 传入 `--no-stop-marker`。该调用模式确认为 `HOOK_NEUTRAL`，不会触发 stop marker 阻止后续写操作。B1 决策（沙盒 HOME probe 验证）**通过**，无需额外改动 hook 调用。

---

## DERIVED CONSTANT: `_KINDS_REQUIRING_COMPAT_V1_WHEN_V2_TEMPLATE_MISSING`

```python
_KINDS_REQUIRING_COMPAT_V1_WHEN_V2_TEMPLATE_MISSING = frozenset({"plan", "code_diff"})
```

**推导依据**：
- `plan`：`gd-plan-review-v2-template.md` MISSING → v2 路径不可用
- `code_diff`：`gd-code-diff-review-template.md` MISSING → v2 路径不可用
- `execution_outcome`：template EXISTS → 不加入常量
- `combined`：template EXISTS → 不加入常量

**Guard 逻辑（Phase 5 实施）**：
```python
if (not compat_v1
        and kind in _KINDS_REQUIRING_COMPAT_V1_WHEN_V2_TEMPLATE_MISSING
        and not template_path.exists()):
    raise ValueError(f"V2_TEMPLATE_NOT_READY: {kind} requires --compat-v1 until template ready")
```

---

## FIXTURE IMPACT（Phase 5 必做）

以下 fixture 当前 `_test_meta._expect = "PASS"`，B3/B4 guard 加入后行为变化，必须在 Phase 5 同步更新：

| Fixture 文件 | Kind | compat_v1 | 当前 _expect | 修改后 _expect | 理由 |
|-------------|------|-----------|------------|--------------|------|
| `fixtures/codex-bridge-v2/valid-v2-build-capsule-plan.json` | `plan` | `false` | `PASS` | **FAIL** | template missing → ValueError → exit 1 |
| `fixtures/codex-bridge-v2/valid-v2-build-capsule-code-diff.json` | `code_diff` | `false` | `PASS` | **FAIL** | template missing → ValueError → exit 1 |
| `fixtures/codex-bridge-v2/valid-v1-compat-build-capsule-plan.json` | `plan` | `true` | `PASS` | **PASS（不变）** | compat-v1 bypasses B3 guard |

---

## STOP CONDITION 检查

- Hook probe = `HOOK_NEUTRAL`（bridge 实际调用模式）→ 无 `GOAL_STOP_CONDITIONS` 触发
- 所有 5 个 section 数据完整
- **Phase 1 可标记 complete；Phase 2/3/4 可并发启动（Phase 5 依赖本报告的 `_KINDS_REQUIRING_COMPAT_V1...` 常量）**
