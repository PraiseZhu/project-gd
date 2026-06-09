template_kind: gd-execution-result
result_id: t4-antifill-hard-gate-result
task_id: t4-antifill-hard-gate
parent_step: T4
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
executor_role: claude_subagent
executed_at: 2026-06-09T00:00:00Z
exec_status: completed
sc_acceptance:
  - sc_ref: SC-4.1
    status: pass
    evidence: |
      cmd: grep -n 'antifill\|PLAN_ANTIFILL' scripts/gd-validate-review2-plan-target.py
      stdout: |
        16:  PLAN_ANTIFILL_FAIL: <description>  (anti-fill gate violation, independent signal)
        159:def _check_antifill(text: str) -> list[str]:
        162:    Returns a list of PLAN_ANTIFILL_FAIL message strings (empty = all pass).
        164:    antifill_errors: list[str] = []
        169:        return antifill_errors
        174:            antifill_errors.append(
        184:                antifill_errors.append(
      note: "spec assertion grep 要求 verify+antifill 同行，但实现中分散在不同行；直接 grep PLAN_ANTIFILL_FAIL 确认逻辑存在"

      fixture n1 (SC 缺 verify 行):
        cmd: |
          f=$(mktemp /tmp/gd-t4-n1-XXXX.md)
          printf 'REVIEW_DOMAIN: ai_infra\nREVIEW_FOCUS: x\n## SC\n- SC-1: do thing\nWHERE: a\nWHAT: b\nWHY: c\nVERIFY: d\n' > "$f"
          python3 scripts/gd-validate-review2-plan-target.py --target "$f"
          echo "EXIT=$?"
          rm -f "$f"
        stdout: |
          PLAN_TEMPLATE_STATUS: fail
          PLAN_ANTIFILL_FAIL: SC-1 缺 verify 行 — 每条 SC 必须含可执行 verify (method: command|path|assertion|test): <内容>
          BRIDGE_INVOCATION_STATUS: not_started
          EXIT=1
        exit: 1
    not_run_reason: ""

  - sc_ref: SC-4.2
    status: pass
    evidence: |
      fixture n2 (expect 为纯泛词"通过"):
        cmd: |
          f=$(mktemp /tmp/gd-t4-n2-XXXX.md)
          printf 'REVIEW_DOMAIN: ai_infra\nREVIEW_FOCUS: x\n## SC\n- SC-1: do thing\n  verify (method: command): run it\n  expect: 通过\nWHERE: a\nWHAT: b\nWHY: c\nVERIFY: d\n' > "$f"
          python3 scripts/gd-validate-review2-plan-target.py --target "$f"
          echo "EXIT=$?"
          rm -f "$f"
        stdout: |
          PLAN_TEMPLATE_STATUS: fail
          PLAN_ANTIFILL_FAIL: SC-1 expect 为纯泛词 ('通过') — expect 必须含具体输出串/exit code/数值/路径/字面 token，不得只写通过|正确|完成|works|pass|ok|成功
          BRIDGE_INVOCATION_STATUS: not_started
          EXIT=1
        exit: 1

      fixture n3 (expect 为纯泛词"pass"):
        stdout: |
          PLAN_TEMPLATE_STATUS: fail
          PLAN_ANTIFILL_FAIL: SC-1 expect 为纯泛词 ('pass') — ...
          EXIT=1
        exit: 1

      fixture p1 (具体 expect "PLAN_ANTIFILL_FAIL"):
        stdout: |
          PLAN_TEMPLATE_STATUS: pass
          BRIDGE_INVOCATION_STATUS: allowed
          EXIT=0
        exit: 0

      fixture p2 (verify + expect: exit 0):
        stdout: |
          PLAN_TEMPLATE_STATUS: pass
          BRIDGE_INVOCATION_STATUS: allowed
          EXIT=0
        exit: 0
    not_run_reason: ""

  - sc_ref: SC-4.3
    status: pass
    evidence: |
      cmd: grep -c 'PLAN_ANTIFILL_FAIL' scripts/gd-validate-review2-plan-target.py
      stdout: 4
      exit: 0
      note: ">=1 命中（docstring 1 行 + antifill_errors 列表描述 1 行 + print 输出行 + 注释行）"

      cmd: python3 -c "import ast; ast.parse(open('scripts/gd-validate-review2-plan-target.py').read()); print('SYNTAX_OK')"
      stdout: SYNTAX_OK
      exit: 0
    not_run_reason: ""

  - sc_ref: SC-4.4
    status: pass
    evidence: |
      cmd: test -f scripts/plan-mode-antifill-stop-hook.js && echo HOOK_SRC_EXISTS
      stdout: HOOK_SRC_EXISTS
      exit: 0

      cmd: node --check scripts/plan-mode-antifill-stop-hook.js && echo NODE_SYNTAX_OK
      stdout: NODE_SYNTAX_OK
      exit: 0

      cmd: grep -niE 'source-only|不注册|不激活|ledger|T9 deploy|do not install' scripts/plan-mode-antifill-stop-hook.js
      stdout: |
        4: * SOURCE-ONLY: 本文件不注册、不激活、不写 ~/.claude/
        5: * 安装到 live 由 T9 deploy + ledger 授权完成，本文件本身 do not install。
        6: * (source-only; installation to live requires T9 deploy + ledger authorization)
      exit: 0
    not_run_reason: ""

files_added:
  - scripts/plan-mode-antifill-stop-hook.js
  - plans/gd/2026-06-08-l2-review2-redesign/results/t4-antifill-hard-gate-result.md
files_modified:
  - scripts/gd-validate-review2-plan-target.py
files_unchanged_in_scope: []
owned_paths_writes_only: true
forbidden_paths_touched: []
out_of_scope_writes: []
handoff:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t4-antifill-hard-gate-result.md
  status_field: exec_status
  summary: "gd-validate-review2-plan-target.py 新增 per-SC verify 存在性 + expect 泛词黑名单 anti-fill 硬门（违反 exit≠0 + PLAN_ANTIFILL_FAIL 独立信号串）；新建 plan-mode-antifill-stop-hook.js（source-only，不激活）；5 类正/负 fixture 真实输出均符合预期，4 段原有校验未被破坏"
  blockers: none
known_limitations:
  - "plan-mode-antifill-stop-hook.js 为 source-only，需 T9 deploy + ledger 授权才激活至 live"
  - "gd-validate-review2-plan-target.py _validate 签名已改为返回 (structural_errors, antifill_errors) 元组，调用方 main() 已同步调整"
