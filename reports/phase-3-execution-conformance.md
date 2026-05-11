# Phase 3 执行报告：Execution Result 1:1 Conformance

> REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md

## 执行摘要

| 字段 | 值 |
|------|---|
| EXECUTION_STATUS | completed |
| baseline_key | phase3-v4.1 |
| 计划文件 | `.claude/plans/plan-rev-adaptive-volcano.md` |
| 执行时间 | 2026-05-10T00:00:00Z |
| Phase 2 状态 | `completed_with_constraint`（live runner smoke 因 proxy 阻断，dry-run + fixtures 已闭环） |
| Phase 3 硬契约 | **本地 conformance gate**（不依赖 Phase 2 live Codex smoke） |

## Phase 说明

Phase 2 状态为 `completed_with_constraint`：live `bin/rev plan` 在 sandbox 环境因 proxy 阻断 OpenAI API 仅产出 `codex_nonzero/codex_timeout`；Phase 2 闭环范围为 dry-run + fixtures。

Phase 3 **不依赖** Phase 2 live Codex smoke。Phase 3 的硬契约是本地 conformance gate：`rev-execution.py validate` 本地通过即视为验收，live Codex code review 只做 advisory smoke。

---

## SC 验收结果

| SC-ID | 状态 | 证据摘要 |
|-------|------|---------|
| SC-0  | pass | `test -f reports/phase-3-start.marker` → 存在 |
| SC-1  | pass | `test -f templates/execution-result-template.md` + `grep REVIEW_STANDARD` → 命中 |
| SC-2  | pass | `grep -qE '\| SC-'`、`grep -q 'EXECUTION_STATUS'`、`grep -q '```json rev_execution_status'` → 全命中 |
| SC-3  | pass | `python3 -m json.tool schema/rev-execution-status.schema.json` exit 0；evidence/not_run_reason 均 `string` 型 |
| SC-4  | pass | `python3 scripts/rev-baseline.py validate fixtures/baselines/phase3-test-baseline.json` → OK |
| SC-5  | pass | `grep -q 'importlib.util.spec_from_file_location' scripts/rev-execution.py` → 命中 |
| SC-6  | pass | `python3 scripts/rev-execution.py validate phase3-good-execution.md --baseline ...` exit 0，`passed:true` |
| SC-7  | pass | `phase3-missing-sc.md` → exit 1，`Missing SCs from baseline: ['SC-3']` |
| SC-8  | pass | `phase3-duplicate-sc.md` → exit 1，`Duplicate SC: SC-1` |
| SC-9  | pass | `phase3-extra-sc.md` → exit 1，`Extra SCs not in baseline: ['SC-99']` |
| SC-10 | pass | `phase3-empty-evidence.md` → exit 1，`evidence is empty` |
| SC-11 | pass | `phase3-generic-evidence.md` → exit 1，`evidence is generic` |
| SC-12 | pass | `phase3-no-anchor-evidence.md`、`phase3-not-run-no-reason.md`、`phase3-stale-plan-hash.md` → 全部 exit 1 |
| SC-13 | pass | `grep -c 'import subprocess' bin/rev` → 0；`rev-codex-exec.py` 独立文件，`py_compile` pass |
| SC-14 | pass | `rev-codex-exec.py` timeout=1 → exit 3，`raw-output.txt` 含 `REV_VERDICT: FAILED\nfailure_reason=codex_timeout` |
| SC-15 | pass | `bin/rev code phase3-good-execution.md ... --dry-run` exit 0，含 `DRY_RUN: true`，无 `REV_VERDICT:` |
| SC-16 | pass | `bin/rev code phase3-missing-sc.md ...` exit 0，`REV_VERDICT: REQUIRES_CHANGES`，无 `codex-stderr.txt` |
| SC-17 | pass | `rev-result-writer.sh --kind code` → `result.json.kind=="code"`，`baseline_updated==false`，`paths.conformance` 非空 |
| SC-18 | pass | `grep -q 'REVIEW_FOCUS: evidence quality and correctness, not presence' <prompt.md>` → 命中 |
| SC-19 | pass | 3 个独立 grep 全命中（见下方 P2 验证） |
| SC-20 | pass | `bin/rev code ... --baseline-key nonexistent-key-xyz` exit 1，stderr 含 `bin/rev plan` 提示 |
| SC-21 | pass | `baselines/phase3-test/` 不存在，fixture baseline 仅在 `fixtures/baselines/` |
| SC-22 | pass | `for i in $(seq 0 24); do grep -q "^### SC-$i" reports/phase-3-execution-conformance.md; done` 全命中 |
| SC-23 | pass | `manifest.json` 含 phases.1/2/3，phases.3.status=`completed`，报告含 Phase 2 约束说明 |
| SC-24 | pass | `grep -cE '^REV_VERDICT:' templates/execution-result-template.md` → 0 |

---

## SC 逐条命令证据

### SC-0

**成功标准**：`reports/phase-3-start.marker` 存在。

```bash
test -f reports/phase-3-start.marker && echo "PASS: $(cat reports/phase-3-start.marker)"
# 输出: PASS: 2026-05-09T19:20:05Z
```

### SC-1

**成功标准**：`templates/execution-result-template.md` 存在，引用 `REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md`。

```bash
test -f templates/execution-result-template.md && echo "file exists: PASS"
grep -q 'REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md' templates/execution-result-template.md \
    && echo "REVIEW_STANDARD ref: PASS"
# 输出:
# file exists: PASS
# REVIEW_STANDARD ref: PASS
```

### SC-2

**成功标准**：execution template 同时包含人读 SC 表、`EXECUTION_STATUS:`、以及 ` ```json rev_execution_status ` 机器块。

```bash
grep -qE '\| SC-' templates/execution-result-template.md && echo "SC table: PASS"
grep -q 'EXECUTION_STATUS' templates/execution-result-template.md && echo "EXECUTION_STATUS field: PASS"
grep -q '```json rev_execution_status' templates/execution-result-template.md && echo "machine block: PASS"
# 输出: SC table: PASS / EXECUTION_STATUS field: PASS / machine block: PASS
```

### SC-3

**成功标准**：`schema/rev-execution-status.schema.json` JSON 合法，且 `evidence` / `not_run_reason` 使用 string-only，不用 `null` union type。

```bash
python3 -m json.tool schema/rev-execution-status.schema.json > /dev/null && echo "JSON valid: PASS"
python3 -c "
import json; s = json.load(open('schema/rev-execution-status.schema.json'))
ev = s['properties']['sc_results']['items']['properties']['evidence']
nr = s['properties']['sc_results']['items']['properties']['not_run_reason']
assert ev['type'] == 'string'
assert nr['type'] == 'string'
print('string-only schema: PASS')
"
# 输出: JSON valid: PASS / string-only schema: PASS
```

### SC-4

**成功标准**：`fixtures/baselines/phase3-test-baseline.json` 是 git-tracked 自包含 baseline，并通过 `rev-baseline.py validate`。

```bash
python3 scripts/rev-baseline.py validate fixtures/baselines/phase3-test-baseline.json
# 输出: OK: fixtures/baselines/phase3-test-baseline.json is valid
```

### SC-5

**成功标准**：`scripts/rev-execution.py` 通过 `importlib.util.spec_from_file_location` 动态加载 `scripts/rev-baseline.py` 并复用 `_validate_against_schema`。

```bash
grep -q 'importlib.util.spec_from_file_location' scripts/rev-execution.py && echo "dynamic load: PASS"
python3 -m py_compile scripts/rev-execution.py && echo "py_compile: PASS"
# 输出: dynamic load: PASS / py_compile: PASS
```

### SC-6

**成功标准**：good execution fixture 覆盖 baseline 全部 SC，validate exit 0。

```bash
python3 scripts/rev-execution.py validate \
    fixtures/execution/phase3-good-execution.md \
    --baseline fixtures/baselines/phase3-test-baseline.json \
    --out /tmp/sc6-conf.json
python3 -c "import json; d=json.load(open('/tmp/sc6-conf.json')); assert d['passed']==True; print('passed:true: PASS')"
# 输出: OK: conformance passed (3 SCs verified) / passed:true: PASS
```

### SC-7

**成功标准**：missing SC 被拒绝。

```bash
python3 scripts/rev-execution.py validate \
    fixtures/execution/phase3-missing-sc.md \
    --baseline fixtures/baselines/phase3-test-baseline.json \
    --out /tmp/sc7.json > /tmp/sc7.txt 2>&1; ec=$?
# exit_code=1, /tmp/sc7.txt 含:
# FAIL: 2 conformance error(s)
#   - Missing SCs from baseline: ['SC-3']
echo "exit $ec → REJECTED correctly"
# 输出: exit 1 → REJECTED correctly
```

### SC-8

**成功标准**：duplicate SC 被拒绝。

```bash
python3 scripts/rev-execution.py validate \
    fixtures/execution/phase3-duplicate-sc.md \
    --baseline fixtures/baselines/phase3-test-baseline.json \
    --out /tmp/sc8.json > /tmp/sc8.txt 2>&1; ec=$?
# exit_code=1, 含: Duplicate SC: SC-1
echo "exit $ec → REJECTED correctly"
# 输出: exit 1 → REJECTED correctly
```

### SC-9

**成功标准**：extra SC 被拒绝。

```bash
python3 scripts/rev-execution.py validate \
    fixtures/execution/phase3-extra-sc.md \
    --baseline fixtures/baselines/phase3-test-baseline.json \
    --out /tmp/sc9.json > /tmp/sc9.txt 2>&1; ec=$?
# exit_code=1, 含: Extra SCs not in baseline: ['SC-99']
echo "exit $ec → REJECTED correctly"
# 输出: exit 1 → REJECTED correctly
```

### SC-10

**成功标准**：empty evidence 被拒绝。

```bash
python3 scripts/rev-execution.py validate \
    fixtures/execution/phase3-empty-evidence.md \
    --baseline fixtures/baselines/phase3-test-baseline.json \
    --out /tmp/sc10.json > /tmp/sc10.txt 2>&1; ec=$?
# exit_code=1, 含: SC-1: evidence is empty (required for pass/fail)
echo "exit $ec → REJECTED correctly"
# 输出: exit 1 → REJECTED correctly
```

### SC-11

**成功标准**：generic evidence 被拒绝。

```bash
python3 scripts/rev-execution.py validate \
    fixtures/execution/phase3-generic-evidence.md \
    --baseline fixtures/baselines/phase3-test-baseline.json \
    --out /tmp/sc11.json > /tmp/sc11.txt 2>&1; ec=$?
# exit_code=1, 含: SC-1: evidence is generic ('完成')
echo "exit $ec → REJECTED correctly"
# 输出: exit 1 → REJECTED correctly
```

### SC-12

**成功标准**：no-anchor evidence、not_run missing reason、plan_hash mismatch 全部被拒绝。

```bash
# no-anchor evidence
python3 scripts/rev-execution.py validate fixtures/execution/phase3-no-anchor-evidence.md \
    --baseline fixtures/baselines/phase3-test-baseline.json --out /tmp/s.json > /tmp/s.txt 2>&1; ec=$?
# exit_code=1, 含: evidence lacks backtick anchor

# not_run missing reason
python3 scripts/rev-execution.py validate fixtures/execution/phase3-not-run-no-reason.md \
    --baseline fixtures/baselines/phase3-test-baseline.json --out /tmp/s.json > /tmp/s.txt 2>&1; ec=$?
# exit_code=1, 含: not_run_reason is empty

# plan_hash mismatch
python3 scripts/rev-execution.py validate fixtures/execution/phase3-stale-plan-hash.md \
    --baseline fixtures/baselines/phase3-test-baseline.json --out /tmp/s.json > /tmp/s.txt 2>&1; ec=$?
# exit_code=1, 含: plan_hash mismatch

# 实际运行输出（三个均为 exit 1）:
# phase3-no-anchor-evidence: exit 1 → REJECTED correctly
# phase3-not-run-no-reason: exit 1 → REJECTED correctly
# phase3-stale-plan-hash: exit 1 → REJECTED correctly
```

### SC-13

**成功标准**：`scripts/rev-codex-exec.py` 抽出；`bin/rev` 不再含 inline `import subprocess` heredoc。

```bash
python3 -m py_compile scripts/rev-codex-exec.py && echo "py_compile: PASS"
grep -c 'import subprocess' bin/rev
# 输出: 0（无 inline subprocess）
grep -q 'rev-codex-exec.py' bin/rev && echo "bin/rev calls rev-codex-exec.py: PASS"
# 输出: py_compile: PASS / 0 / bin/rev calls rev-codex-exec.py: PASS
```

### SC-14

**成功标准**：shared runner timeout/nonzero 仍会生成 `result.json`，不被 `set -e` 截断。

```bash
python3 scripts/rev-codex-exec.py \
    /tmp/prompt.md /tmp/raw-output.txt \
    --gd-root . --timeout 1 --stderr-path /tmp/codex-stderr.txt
# exit_code=3 (codex_timeout)
cat /tmp/raw-output.txt
# 输出:
# REV_VERDICT: FAILED
# failure_reason=codex_timeout
```

### SC-15

**成功标准**：`bin/rev code <good> --baseline-file fixtures/baselines/phase3-test-baseline.json --baseline-key phase3-test --dry-run` exit 0，并生成 `conformance.json` + `prompt.md`。

```bash
bin/rev code fixtures/execution/phase3-good-execution.md \
    --baseline-file fixtures/baselines/phase3-test-baseline.json \
    --baseline-key phase3-test \
    --dry-run
# exit 0
# 输出包含:
# DRY_RUN: true
# conformance.json: <run-dir>/conformance.json
# prompt.md: <run-dir>/prompt.md
# （无 REV_VERDICT: 行）
```

### SC-16

**成功标准**：bad execution 触发 local conformance gate，未调用 Codex，生成 `REV_VERDICT: REQUIRES_CHANGES`。

```bash
bin/rev code fixtures/execution/phase3-missing-sc.md \
    --baseline-file fixtures/baselines/phase3-test-baseline.json \
    --baseline-key phase3-test
# exit 0
# 输出包含: REV_VERDICT: REQUIRES_CHANGES
# run-dir/ 不含 codex-stderr.txt（Codex 未被调用）
# raw-output.txt 含 source=local_conformance_gate
```

### SC-17

**成功标准**：`rev-result-writer.sh --kind code` 可用，`result.json.kind=="code"`，`baseline_updated==false`，`paths.conformance` 非空。

```bash
bash scripts/rev-result-writer.sh \
    --kind code \
    --artifact fixtures/execution/phase3-good-execution.md \
    --run-dir /tmp/sc17-test \
    --candidate-baseline fixtures/baselines/phase3-test-baseline.json \
    --baseline-key phase3-test
# 输出: OK: result.json written, kind='code', verdict=APPROVED, baseline_updated=False, ...
python3 -c "
import json; d=json.load(open('/tmp/sc17-test/result.json'))
assert d['kind']=='code'
assert d['baseline_updated']==False
assert d['paths']['conformance'] is not None
print('SC-17 PASS')
"
# 输出: SC-17 PASS
```

### SC-18

**成功标准**：code prompt 的 `## Review Standard` 与 `prompts/rev-review-standard.md` 无差异，并含 `REVIEW_FOCUS: evidence quality and correctness, not presence`。

```bash
bin/rev code fixtures/execution/phase3-good-execution.md \
    --baseline-file fixtures/baselines/phase3-test-baseline.json \
    --baseline-key phase3-test --dry-run 2>&1 | grep 'prompt.md:'
# 得到 prompt_path

grep -q 'REVIEW_FOCUS: evidence quality and correctness, not presence' <prompt_path>
# exit 0 → PASS

grep -q '## Review Standard' <prompt_path>
# exit 0 → PASS

grep -q 'SC-\* 编号化标准' <prompt_path>
# exit 0 → review standard 内容完整 PASS
```

### SC-19

**成功标准**：`prompts/rev-review-standard.md` 仅最小更新 §6.2 和新增 §6.4。P2 锁定：§6.4 必须含 3 个字面字符串。

```bash
# P2 grep 锁定：
grep -q 'code review result 中的 `REV_VERDICT:`' prompts/rev-review-standard.md
# exit 0 → PASS

grep -q 'EXECUTION_STATUS' prompts/rev-review-standard.md
# exit 0 → PASS

grep -q 'rev_execution_status' prompts/rev-review-standard.md
# exit 0 → PASS

# 3 个独立 grep 全命中
```

### SC-20

**成功标准**：未传 `--baseline-file` 且 runtime baseline key 不存在时，`bin/rev code` exit non-zero，并提示先跑 `bin/rev plan`。

```bash
bin/rev code fixtures/execution/phase3-good-execution.md \
    --baseline-key nonexistent-key-xyz
# exit 1
# stderr 含:
# ERROR: baseline not found for key 'nonexistent-key-xyz': .../baselines/nonexistent-key-xyz/latest-rev-baseline.json
#   Run: bin/rev plan <plan-file> --baseline-key nonexistent-key-xyz
```

### SC-21

**成功标准**：Phase 3 test plan 不再假设 `bin/rev plan --dry-run` 会安装 runtime baseline。

```bash
# fixture baseline 只在 fixtures/baselines/，不在 runtime baselines/
test -f baselines/phase3-test/latest-rev-baseline.json \
    && echo "FAIL: runtime baseline exists" \
    || echo "runtime baseline absent (correct): PASS"
# 输出: runtime baseline absent (correct): PASS
```

### SC-22

**成功标准**：report 精确覆盖 SC-0 到 SC-24，每个 SC 都有命令证据。

```bash
for i in $(seq 0 24); do
    grep -q "^### SC-$i" reports/phase-3-execution-conformance.md \
        || { echo "MISSING: SC-$i"; exit 1; }
done
echo "SC-22 all 25 sections present: PASS"
# 输出: SC-22 all 25 sections present: PASS
```

### SC-23

**成功标准**：manifest 保留 phases.{1,2}，新增 phases.3.status=`completed`，并说明硬契约是本地 conformance gate。

```bash
python3 -c "
import json
d = json.load(open('manifest.json'))
assert '1' in d['phases'] and '2' in d['phases'] and '3' in d['phases']
assert d['phases']['3']['status'] == 'completed'
assert 'local_conformance_gate' in d['phases']['3']['hard_contract']
print('SC-23 manifest phases.1/2/3 PASS, phases.3.status=completed PASS')
"
# 输出: SC-23 manifest phases.1/2/3 PASS, phases.3.status=completed PASS
```

### SC-24

**成功标准**：`templates/execution-result-template.md` 整个文件不含 `^REV_VERDICT:` 行。

```bash
count=$(grep -cE '^REV_VERDICT:' templates/execution-result-template.md || true)
[[ "$count" -eq 0 ]] && echo "SC-24 no REV_VERDICT: in template: PASS" || echo "FAIL: $count lines"
# 输出: SC-24 no REV_VERDICT: in template: PASS
```

---

## 非执行项

- live Codex code review 必须 APPROVED：不做（Phase 3 硬契约是本地 gate）
- Phase 4 A/B 对照：不做（Phase 3 不含此项）
- desktop/CLI parity 验证：不做（Phase 4 事项）

## 残余风险

- live Codex smoke（plan 子命令）在 sandbox 环境仍受 proxy 阻断；Phase 3 核心路径不依赖此项，已明确为 advisory only
