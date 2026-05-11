# Phase 2 Report：同步 Runner + 精简 Baseline

REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

> 执行日期：2026-05-10
> 执行者：Claude（claude-sonnet-4-6）
> Phase 状态：**completed_with_constraint**
> 约束：live runner smoke（verdict=APPROVED/REQUIRES_CHANGES 且 failure_reason=null）为后续阻塞项，当前 sandbox 环境 proxy 阻断 OpenAI API（chatgpt.com），bin/rev plan 仅能产出 codex_nonzero/codex_timeout；Phase 2 闭环范围为 dry-run + fixtures

---

## PHASE_GOAL 验收

**目标**：`Project GD/bin/rev plan` 可以完成一次同步 plan review，并在 APPROVED 时生成 `latest-rev-baseline.json`。

**状态**：⚠️ completed_with_constraint — dry-run + fixtures 闭环（见下方约束说明）；live codex smoke（verdict≠runner_failure）为后续阻塞项

---

## 交付物清单

| 文件 | 类型 | 状态 |
|------|------|------|
| `bin/rev` | new | ✅ 已创建，chmod +x |
| `scripts/rev-baseline.py` | new | ✅ 已创建，py_compile PASS |
| `scripts/rev-result-writer.sh` | new | ✅ 已创建，chmod +x |
| `schema/rev-baseline.schema.json` | new | ✅ JSON Schema Draft-07，json.tool PASS |
| `fixtures/plans/phase2-good-plan.md` | new | ✅ extract → 3 SCs |
| `fixtures/plans/phase2-bad-generic-plan.md` | new | ✅ 泛化步骤 fixture |
| `fixtures/plans/phase2-bad-sc-verify-plan.md` | new | ✅ SC gap fixture |
| `fixtures/expected/raw-approved.md` | new | ✅ writer → APPROVED |
| `fixtures/expected/raw-requires-changes.md` | new | ✅ writer → REQUIRES_CHANGES |
| `fixtures/expected/raw-failed.md` | new | ✅ writer → FAILED/codex_timeout |
| `fixtures/expected/raw-bare-verdict.md` | new | ✅ writer exit non-zero |
| `fixtures/expected/raw-multi-verdict.md` | new | ✅ writer exit non-zero |
| `fixtures/expected/raw-missing-verdict.md` | new | ✅ writer exit non-zero |
| `fixtures/expected/malformed-baseline.json` | new | ✅ validate exit non-zero（禁止字段） |
| `fixtures/expected/missing-non-goals-baseline.json` | new | ✅ validate exit non-zero（缺 non_goals/accepted_decisions） |
| `reports/phase-2-runner-baseline.md` | new | ✅ 本文件 |
| `manifest.json` | modified | ✅ phases.{1,2} 演进 |
| `PROJECT_GOAL.md` | modified | ✅ PROJECT_GOAL: 字段补充 |
| `reports/phase-2-start.marker` | new | ✅ 2026-05-09T16:19:46Z |

---

## 验收结果

### SC-0：Phase 2 起点 marker

```bash
test -f "reports/phase-2-start.marker"
```

→ PASS（marker: 2026-05-09T16:19:46Z）

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-0 | phase-2-start.marker 存在 | `test -f "$GD_ROOT/reports/phase-2-start.marker"` | ✅ pass |

---

### SC-1：PROJECT_GOAL: 字段

```bash
grep -E '^PROJECT_GOAL:' PROJECT_GOAL.md
# → PROJECT_GOAL: 在不破坏现有 /review 链路的前提下...
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-1 | `PROJECT_GOAL.md` 含精确字段 | `grep -E '^PROJECT_GOAL:' "$GD_ROOT/PROJECT_GOAL.md"` → exit 0 + 1 行 | ✅ pass |

---

### SC-2：bin/rev --help

```bash
"$GD_ROOT/bin/rev" --help
# 输出含 plan <file>, code <file>, Phase 3 reserved
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-2 | --help 暴露必要信息 | help 含 `plan <file>`、`code <file>`、`Phase 3 reserved` | ✅ pass |

---

### SC-3：runner 形态

5 个独立 grep 全 pass：

```bash
grep -q 'python3' bin/rev        # OK
grep -q 'subprocess' bin/rev     # OK
grep -q 'codex exec' bin/rev     # OK
grep -q -- '--ephemeral' bin/rev # OK
grep -q -- '--skip-git-repo-check' bin/rev # OK
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-3 | 5 个独立 grep 全 pass | 见上 | ✅ pass |

---

### SC-4：timeout 协议

```bash
grep -q 'REV_CODEX_TIMEOUT' bin/rev # OK
grep -q '240' bin/rev               # OK
grep -q 'SIGTERM' bin/rev           # OK
grep -q 'time.sleep(2)' bin/rev     # OK
grep -q 'SIGKILL' bin/rev           # OK
grep -q 'codex_timeout' bin/rev     # OK
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-4 | timeout 协议 6 项全 pass | 默认 240s，SIGTERM→sleep(2)→SIGKILL，failure_reason=codex_timeout | ✅ pass |

---

### SC-5：timeout 不追加第二个 verdict

```bash
grep -c '^REV_VERDICT:' fixtures/expected/raw-failed.md
# → 1
```

raw-failed.md 内容（方案 A）：
```
REV_VERDICT: FAILED
failure_reason=codex_timeout
```

writer 处理后 result.json.failure_reason = "codex_timeout"

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-5 | timeout raw 只含 1 行 REV_VERDICT: | `grep -c '^REV_VERDICT:' raw-failed.md` → 1 | ✅ pass |

---

### SC-6：prompt 5 个 section 顺序固定

```bash
bin/rev plan fixtures/plans/phase2-good-plan.md --dry-run --baseline-key phase2-test
grep -cE '^## (Review Standard|Candidate Baseline|Review Context|Artifact|Output Contract)$' \
  results/20260509T162842Z-plan/prompt.md
# → 5
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-6 | prompt 5 section | count=5 PASS | ✅ pass |

---

### SC-7：Review Standard section 等于 prompts/rev-review-standard.md

```bash
python3 -c "
import re
prompt = open('results/20260509T162842Z-plan/prompt.md').read()
m = re.search(r'^## Review Standard\n(.+?)^## Candidate Baseline', prompt, re.M|re.S)
open('/tmp/extracted.md', 'w').write(m.group(1).strip()+'\n')
"
diff -B /tmp/extracted.md prompts/rev-review-standard.md
# → 无差异
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-7 | Review Standard section = rev-review-standard.md | `diff -B extracted.md prompts/rev-review-standard.md` → 无差异 | ✅ pass |

---

### SC-8：writer flags 接口

```bash
scripts/rev-result-writer.sh --help | grep -q 'kind'      # OK
scripts/rev-result-writer.sh --help | grep -q 'artifact'  # OK
scripts/rev-result-writer.sh --help | grep -q 'run-dir'   # OK
scripts/rev-result-writer.sh --help | grep -q 'candidate-baseline' # OK
scripts/rev-result-writer.sh --help | grep -q 'baseline-key' # OK
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-8 | writer --help 含 5 个 flags | 全命中 | ✅ pass |

---

### SC-9：writer 6 类 fixture 全覆盖

| Fixture | writer exit | result.json.verdict | failure_reason | baseline_updated |
|---------|------------|---------------------|----------------|------------------|
| raw-approved.md | 0 | APPROVED | JSON null | true |
| raw-requires-changes.md | 0 | REQUIRES_CHANGES | JSON null | false |
| raw-failed.md | 0 | FAILED | "codex_timeout" | false |
| raw-bare-verdict.md | non-zero | 无 result.json | bare_verdict (log) | false |
| raw-multi-verdict.md | non-zero | 无 result.json | multi_verdict (log) | false |
| raw-missing-verdict.md | non-zero | 无 result.json | missing_verdict (log) | false |

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-9 | 6 fixture 全跑过 | 见上表，6 行全命中 | ✅ pass |

---

### SC-10：FAILED 仅用于执行失败

raw-requires-changes.md → verdict=REQUIRES_CHANGES，failure_reason=null，exit 0

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-10 | REQUIRES_CHANGES 时 failure_reason=null | python3 assert rc['failure_reason'] is None | ✅ pass |

---

### SC-11：baseline 仅 APPROVED 更新

```bash
ls baselines/phase2-test/latest-rev-baseline.json
# → 存在（approved fixture 写入）
# requires-changes/failed fixture 不写入（verified by mtime check）
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-11 | APPROVED plan 更新 latest-rev-baseline.json | `test -f baselines/phase2-test/latest-rev-baseline.json` → PASS | ✅ pass |

---

### SC-12：schema 文件存在 + validator 读取 schema

```bash
test -f schema/rev-baseline.schema.json  # PASS
python3 -m json.tool schema/rev-baseline.schema.json  # PASS
grep -q 'json.load' scripts/rev-baseline.py  # PASS
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-12 | schema 存在，validator 读文件 | 三项全 pass | ✅ pass |

---

### SC-13：result.json failure_reason JSON null vs string

```python
approved["failure_reason"] is None      # PASS
rc["failure_reason"] is None            # PASS
failed["failure_reason"] == "codex_timeout"  # PASS
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-13 | failure_reason JSON null vs 枚举字符串 | python3 assert 全 pass | ✅ pass |

---

### SC-14：stdout 含中文摘要 + REV_VERDICT:

dry-run stdout（Fix 2 修正后，dry-run 不输出 `REV_VERDICT:`，以免触发契约非法值）：
```
DRY_RUN: true
审查结果摘要：dry-run 模式，未调用 Codex，prompt 已生成
结果文件：.../results/<run-id>/prompt.md
```

non-dry-run（live smoke 待后续验证）stdout 应为：
```
审查结果摘要：Phase 2 /rev plan review 完成
REV_VERDICT: APPROVED | REQUIRES_CHANGES | FAILED
结果文件：.../results/<run-id>/result.md
```

验收命令：
```bash
# dry-run 不含 REV_VERDICT:
bin/rev plan fixtures/plans/phase2-good-plan.md --dry-run --baseline-key phase2-test | grep -q '^REV_VERDICT:' && exit 1 || exit 0
# → exit 0（PASS）

# live smoke（需 OpenAI API 可用，sandbox 暂不可达，标为 PENDING）
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-14（dry-run 部分） | dry-run stdout 不含 `^REV_VERDICT:`，含中文摘要 | `grep -q '^REV_VERDICT:' \| exit 1 \|\| exit 0` → exit 0 | ✅ pass（Fix 2 修正） |
| SC-14（live 部分） | live stdout 含 `REV_VERDICT:` + 中文摘要 | live smoke 需 OpenAI API 可用 | ⏳ PENDING |

---

### SC-15：不写 ~/.claude/**

```bash
test ! -e "$HOME/.claude/commands/rev.md"  # PASS
find ~/.claude/commands ~/.claude/review-baselines ... -newer phase-2-start.marker 2>/dev/null | grep -v heartbeat
# → 空（无本阶段写入）
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-15 | 零写入 ~/.claude/** | find -newer marker → 空 | ✅ pass |

---

### SC-16：manifest.json phases.{1,2} 双存

```bash
python3 -c "import json; m=json.load(open('manifest.json')); assert '1' in m['phases'] and '2' in m['phases']"
# → PASS（phases.1.status=approved, phases.2.status=completed_with_constraint）
```

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-16 | manifest phases.1 + phases.2 | python3 assert PASS；phases.2.status=completed_with_constraint | ✅ pass |

---

### SC-17：PROJECT_GOAL: 字段补充说明

Phase 2 在 `PROJECT_GOAL.md` 顶部补充了 `PROJECT_GOAL:` 前置字段，**原因是 parser 可机读**：`scripts/rev-baseline.py` 的 `cmd_extract()` 通过 `grep -E '^PROJECT_GOAL:'` 解析此字段，做计划与总目标的精确比对，防止 AI 填表时把 PROJECT_GOAL 改写或缩略。这是 Phase 2 为让 parser 前置可机读而补的字段，不是 Phase 1 的遗漏项。

| SC | 内容 | Verify | 状态 |
|----|------|--------|------|
| SC-17 | 报告说明 PROJECT_GOAL: 补字段原因（parser 可机读） | 本节包含"parser 可机读"说明 | ✅ pass |

---

## 执行摘要

### Phase 2 核心链路验证

1. **bin/rev plan --dry-run**：`results/20260509T162842Z-plan/prompt.md` 生成，5 section 齐全，Review Standard section = `prompts/rev-review-standard.md` 全文（diff -B 无差异）
2. **rev-baseline.py extract**：成功解析 phase2-good-plan.md，产出 3 SCs baseline，通过 schema validation
3. **rev-baseline.py extract（negatives）**：SC gap（SC-1→SC-3）→ exit 1；malformed-baseline validate → exit 1
4. **rev-result-writer.sh（6 类 fixture）**：approved/requires-changes/failed 各写 result.json；bare/multi/missing verdict 各 exit non-zero
5. **failure_reason JSON null vs string**：approved/rc → None（JSON null）；failed → "codex_timeout"（字符串）
6. **code mode exit 64**：`bin/rev code` → exit 64，stderr 含"Phase 3 reserved"

### 特殊说明

- **live codex smoke（Test 10，后续阻塞项）**：`codex` CLI 存在（`codex-cli 0.130.0`）但 sandbox proxy 阻断 `chatgpt.com`（OpenAI API），`bin/rev plan` 仅能产出 `codex_nonzero` 或 `codex_timeout`，不是 `failure_reason=null` 的正常 verdict。Phase 2 不能在此状态下标"完成"，故状态为 `completed_with_constraint`。解封 OpenAI 出口后应立即运行：`bin/rev plan fixtures/plans/phase2-good-plan.md --baseline-key phase2-test`，验收 `result.json.verdict in {APPROVED, REQUIRES_CHANGES}` 且 `failure_reason == null`。
- **timeout 实物验证（Test 11 通过）**：`REV_CODEX_TIMEOUT=1` 触发真实 SIGTERM→sleep(2)→SIGKILL 路径；`raw-output.partial.txt` 存在；`grep -c '^REV_VERDICT:' raw-output.txt` → 1；`result.json.failure_reason == "codex_timeout"`。
- **baseline_updated = true 限制**：writer 仅在 kind=plan + verdict=APPROVED 时更新 baselines/<key>/latest-rev-baseline.json（JSON boolean true/false）。

---

## baseline key 双路径验证

默认 key（sha256 首 12 位）：
```bash
python3 -c "import hashlib, os; print('gd-' + hashlib.sha256(os.path.realpath('$GD_ROOT').encode()).hexdigest()[:12])"
```

命名 key：`phase2-test`（`--baseline-key phase2-test` 参数）

两个路径均通过 approved fixture 写入测试。

---

## Phase 3 前提条件

| 前提 | 状态 |
|------|------|
| `bin/rev` 存在且可执行 | ✅ |
| `schema/rev-baseline.schema.json` 就绪 | ✅ |
| `scripts/rev-result-writer.sh` 6 类 verdict 覆盖 | ✅ |
| `baselines/<key>/latest-rev-baseline.json` 格式 | ✅ |
| 执行结果模板（Phase 3 产出）| ⏳ |
| `bin/rev code` 实现（Phase 3 产出）| ⏳ |
| live runner smoke（verdict=APPROVED/REQUIRES_CHANGES，failure_reason=null）| ⏳ PENDING |
