# T9 执行结果：deploy-live manifest 更新

```yaml
task_id: t9-deploy-live
agent_role: implementer
executed_at: 2026-06-09
status: completed
```

---

## 摘要

`.deploy-manifest.jsonl` 已在保留全部 v8 5 条 review2 artifact 的基础上，追加 T1-T8 新增的 8 条 live-bound artifact。manifest 合法、source 文件全部实际存在、parity 前置条件就绪。deploy live skill 可直接消费本 manifest 完成回灌。

---

## 变更说明

**保留（未改动）— v8 既有 5 条**：
- `commands/review2.md`
- `scripts/gd-build-review2-capsule.py`
- `scripts/gd-validate-review2-capsule.py`
- `scripts/gd-codex-bridge-review.py`
- `scripts/gd-validate-review2-output.py`

**新增 8 条（T1-T8 live-bound artifacts）**：

| source | target | ledger_scope |
|--------|--------|-------------|
| `scripts/gd-validate-review2-plan-target.py` | `~/.claude/scripts/gd-validate-review2-plan-target.py` | sync_script_to_live |
| `templates/plan-mode-template.md` | `~/.claude/templates/plan-template.md` | install_plan_template |
| `scripts/plan-mode-antifill-stop-hook.js` | `~/.claude/hooks/plan-mode-antifill-stop-hook.js` | install_plan_mode_hook |
| `scripts/gd-review-controller.py` | `~/.claude/scripts/gd-review-controller.py` | sync_script_to_live |
| `schema/gd-baseline-findings.schema.json` | `~/.claude/schema/gd-baseline-findings.schema.json` | sync_script_to_live |
| `scripts/gd-detect-review2-code-target.py` | `~/.claude/scripts/gd-detect-review2-code-target.py` | sync_script_to_live |
| `scripts/gd-review2-preflight.sh` | `~/.claude/scripts/gd-review2-preflight.sh` | sync_script_to_live |
| `scripts/gd-review2-package-deliverable.sh` | `~/.claude/scripts/gd-review2-package-deliverable.sh` | sync_script_to_live |

注：`scripts/gd-codex-bridge-review.py` 已在 v8 manifest 中，未重复录入。

---

## 验证输出（真实命令执行结果）

### SC-9.1：文件存在且 JSON 合法

```
$ test -f .deploy-manifest.jsonl && echo PASS
PASS

$ python3 -c "import json;[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]" && echo JSON_OK
JSON_OK

$ python3 -c "import json; rows=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]; req={'source','target','method','ledger_scope'}; bad=[r for r in rows if not req.issubset(r)]; print('FIELDS_OK' if not bad else 'FIELDS_MISSING:'+str(bad))"
FIELDS_OK
```

### SC-9.2：gd-validate-review2-plan-target.py 录入

```
$ grep -c 'gd-validate-review2-plan-target.py' .deploy-manifest.jsonl
1
```

### SC-9.3：T1-T8 新 artifact 全录入

```
$ grep -c 'gd-review-controller.py' .deploy-manifest.jsonl
1

$ grep -c 'gd-baseline-findings.schema.json' .deploy-manifest.jsonl
1

$ grep -c 'plan-mode-template.md\|plan-template.md' .deploy-manifest.jsonl
1

$ python3 -c "import json,os; rows=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]; miss=[r['source'] for r in rows if not os.path.exists(r['source'])]; print('SOURCES_EXIST' if not miss else 'SOURCE_MISSING:'+str(miss))"
SOURCES_EXIST
```

### SC-9.5：v8 条目全部保留

```
$ grep -c 'commands/review2.md' .deploy-manifest.jsonl
1

$ python3 -c "rows=open('.deploy-manifest.jsonl').read(); ok=all(s in rows for s in ['review2.md','gd-build-review2-capsule.py','gd-validate-review2-capsule.py','gd-codex-bridge-review.py','gd-validate-review2-output.py']); print('V8_PRESERVED' if ok else 'V8_BROKEN')"
V8_PRESERVED
```

### SC-9.6：parity 工具前置条件就绪

```
$ test -x tools/gd-parity-verify.sh && grep -q 'review2_command' tools/gd-parity-verify.sh && echo PARITY_BUNDLE_READY
PARITY_BUNDLE_READY

$ python3 -c "import json; d=json.load(open('config/gd-runtime-parity-manifest.json')); print('REVIEW2_PARITY_DECLARED' if d['bundles']['review2_command']['source_path']=='commands/review2.md' else 'PARITY_PATH_DRIFT')"
REVIEW2_PARITY_DECLARED
```

---

## 成功标准验收

| SC | 状态 | 说明 |
|----|------|------|
| SC-9.1 文件存在且 JSON 合法 | pass | PASS / JSON_OK / FIELDS_OK |
| SC-9.1 每条含四个必填字段 | pass | FIELDS_OK，13 条全部合格 |
| SC-9.2 补录 plan-target validator | pass | grep 计数 = 1 |
| SC-9.3 T1-T8 live artifact 全录入 | pass | controller/schema/template/hook/detect/preflight/package 均 1+ |
| SC-9.3 source 文件均实际存在 | pass | SOURCES_EXIST |
| SC-9.4 不录仅工作树内 artifact | pass | plan packet/docs/fixture 均未录入 |
| SC-9.5 v8 5 条保留未破坏 | pass | V8_PRESERVED |
| SC-9.6 parity 工具前置就绪 | pass | PARITY_BUNDLE_READY + REVIEW2_PARITY_DECLARED |

---

## Handoff 输出

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t9-deploy-live-result.md
  status: completed
  summary: manifest 已补 plan-target validator + T1-T8 全部 live artifact（8 条新增），v8 5 条保留，source 文件全部实际存在，parity 前置条件就绪，deploy live skill 可直接执行五步回灌
  blockers: none
```
