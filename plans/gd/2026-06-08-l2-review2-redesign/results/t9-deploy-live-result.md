template_kind: gd-execution-result
result_id: t9-deploy-live-result
task_id: t9-deploy-live
parent_step: T9
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
executor_role: claude_subagent
executed_at: 2026-06-09T00:00:00Z
exec_status: completed
sc_acceptance:
  - sc_ref: SC-9.1
    status: pass
    evidence: |
      cmd: test -f .deploy-manifest.jsonl && echo PASS
      stdout: PASS
      exit: 0

      cmd: python3 -c "import json;[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]" && echo JSON_OK
      stdout: JSON_OK
      exit: 0

      cmd: python3 -c "import json; rows=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]; req={'source','target','method','ledger_scope'}; bad=[r for r in rows if not req.issubset(r)]; print('FIELDS_OK' if not bad else 'FIELDS_MISSING:'+str(bad))"
      stdout: FIELDS_OK
      exit: 0
      note: "文件存在 + JSON 合法 + 13 条全部含四个必填字段"
    not_run_reason: ""

  - sc_ref: SC-9.2
    status: pass
    evidence: |
      cmd: grep -c 'gd-validate-review2-plan-target.py' .deploy-manifest.jsonl
      stdout: 1
      exit: 0
    not_run_reason: ""

  - sc_ref: SC-9.3
    status: pass
    evidence: |
      cmd: grep -c 'gd-review-controller.py' .deploy-manifest.jsonl
      stdout: 1
      exit: 0

      cmd: grep -c 'gd-baseline-findings.schema.json' .deploy-manifest.jsonl
      stdout: 1
      exit: 0

      cmd: grep -c 'plan-mode-template.md\|plan-template.md' .deploy-manifest.jsonl
      stdout: 1
      exit: 0

      cmd: python3 -c "import json,os; rows=[json.loads(l) for l in open('.deploy-manifest.jsonl') if l.strip() and not l.startswith('#')]; miss=[r['source'] for r in rows if not os.path.exists(r['source'])]; print('SOURCES_EXIST' if not miss else 'SOURCE_MISSING:'+str(miss))"
      stdout: SOURCES_EXIST
      exit: 0
      note: "T1-T8 全部 live-bound artifact 录入（controller/schema/template/hook/detect/preflight/package 均 1+）；source 文件均实际存在"
    not_run_reason: ""

  - sc_ref: SC-9.4
    status: pass
    evidence: |
      note: "plan packet/docs/fixture 均未录入 manifest，仅工作树内使用的 artifact 不写 live"
    not_run_reason: ""

  - sc_ref: SC-9.5
    status: pass
    evidence: |
      cmd: grep -c 'commands/review2.md' .deploy-manifest.jsonl
      stdout: 1
      exit: 0

      cmd: python3 -c "rows=open('.deploy-manifest.jsonl').read(); ok=all(s in rows for s in ['review2.md','gd-build-review2-capsule.py','gd-validate-review2-capsule.py','gd-codex-bridge-review.py','gd-validate-review2-output.py']); print('V8_PRESERVED' if ok else 'V8_BROKEN')"
      stdout: V8_PRESERVED
      exit: 0
    not_run_reason: ""

  - sc_ref: SC-9.6
    status: pass
    evidence: |
      cmd: test -x tools/gd-parity-verify.sh && grep -q 'review2_command' tools/gd-parity-verify.sh && echo PARITY_BUNDLE_READY
      stdout: PARITY_BUNDLE_READY
      exit: 0

      cmd: python3 -c "import json; d=json.load(open('config/gd-runtime-parity-manifest.json')); print('REVIEW2_PARITY_DECLARED' if d['bundles']['review2_command']['source_path']=='commands/review2.md' else 'PARITY_PATH_DRIFT')"
      stdout: REVIEW2_PARITY_DECLARED
      exit: 0
    not_run_reason: ""

files_added:
  - plans/gd/2026-06-08-l2-review2-redesign/results/t9-deploy-live-result.md
files_modified:
  - .deploy-manifest.jsonl
files_unchanged_in_scope:
  - commands/review2.md
  - scripts/gd-build-review2-capsule.py
  - scripts/gd-validate-review2-capsule.py
  - scripts/gd-codex-bridge-review.py
  - scripts/gd-validate-review2-output.py
owned_paths_writes_only: true
forbidden_paths_touched: []
out_of_scope_writes: []
handoff:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t9-deploy-live-result.md
  status_field: exec_status
  summary: ".deploy-manifest.jsonl 已补 plan-target validator + T1-T8 全部 live artifact（8 条新增），v8 5 条保留未破坏，source 文件全部实际存在，parity 前置条件就绪，deploy live skill 可直接执行五步回灌"
  blockers: none
known_limitations:
  - "scripts/gd-codex-bridge-review.py 已在 v8 manifest 中，T9 未重复录入"
  - "新增 8 条 artifact 包含：gd-validate-review2-plan-target.py / plan-mode-template.md / plan-mode-antifill-stop-hook.js / gd-review-controller.py / gd-baseline-findings.schema.json / gd-detect-review2-code-target.py / gd-review2-preflight.sh / gd-review2-package-deliverable.sh"
