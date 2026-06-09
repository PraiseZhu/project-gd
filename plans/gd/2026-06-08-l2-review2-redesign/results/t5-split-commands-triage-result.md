template_kind: gd-execution-result
result_id: t5-split-commands-triage-result
task_id: t5-split-commands-triage
parent_step: T5
parent_plan: plans/gd/2026-06-08-l2-review2-redesign/master-plan.md
executor_role: claude_subagent
executed_at: 2026-06-09T05:00:00Z
exec_status: completed
sc_acceptance:
  - sc_ref: SC-5.1
    status: pass
    evidence: |
      cmd: grep -nE '/review2 (plan|code)' commands/review2.md | wc -l
      stdout: 6
      exit: 0
      note: 6 >= 2，文档同时出现 /review2 plan 与 /review2 code 子命令用法

      cmd: grep -nE 'original_plan_only' commands/review2.md
      stdout:
        38:BRIDGE_TARGET_POLICY: original_plan_only
      exit: 0
      note: 1 行命中，/review2 plan 保留 BRIDGE_TARGET_POLICY: original_plan_only 语义
    not_run_reason: ""

  - sc_ref: SC-5.2
    status: pass
    evidence: |
      cmd: test -f scripts/gd-detect-review2-code-target.py && echo SCRIPT_EXISTS
      stdout: SCRIPT_EXISTS
      exit: 0

      cmd: python3 scripts/gd-detect-review2-code-target.py --help; echo EXIT=$?
      stdout: |
        usage: gd-detect-review2-code-target [-h] [--cwd DIR] [--code | --result |
                                             --combined]

        /review2 code 三档判定脚本。
        自动探测 git 工作树改动（has_code）与执行产物文件（has_result），
        输出 REVIEW2_CODE_TARGET: code-only|execution-only|combined|INDETERMINATE
        与 REVIEW2_TRIAGE_BASIS: <依据>。

        覆盖 flag（--code / --result / --combined）互斥：传一个则跳过自动判定直接输出对应档位；
        传 >=2 个互斥 flag 则报错 exit 1。

        INDETERMINATE 时 exit 2（交上层问用户，守 D1：判不准不擅自猜）。

        options:
          -h, --help  show this help message and exit
          --cwd DIR   git 工作目录（默认：当前目录）
          --code      覆盖：强制 REVIEW2_CODE_TARGET=code-only，跳过自动判定
          --result    覆盖：强制 REVIEW2_CODE_TARGET=execution-only，跳过自动判定
          --combined  覆盖：强制 REVIEW2_CODE_TARGET=combined，跳过自动判定
        EXIT=0
      exit: 0
      note: --help exit 0；usage 含 --cwd 与 --code/--result/--combined 三个覆盖 flag
    not_run_reason: ""

  - sc_ref: SC-5.3
    status: pass
    evidence: |
      # g1: 仅代码改动（未提交 diff，无执行产物 JSON）→ 期望 code-only
      cmd: |
        d=$(mktemp -d)
        git -C "$d" init -q
        printf 'a\n' > "$d/f.txt"
        git -C "$d" add f.txt
        git -C "$d" -c user.email=t@t -c user.name=t commit -qm base
        printf 'b\n' >> "$d/f.txt"
        python3 scripts/gd-detect-review2-code-target.py --cwd "$d"
        echo EXIT=$?
        rm -rf "$d"
      stdout: |
        REVIEW2_CODE_TARGET: code-only
        REVIEW2_TRIAGE_BASIS: has_code=True(git_diff_unstaged=non-empty),has_result=False(gd_review_detection.has_execution_artifacts_in_dir)
        EXIT=0
      exit: 0

      # g2: 仅执行结果（无 diff，committed outcome.json 含 outcome_id/execution_status）→ 期望 execution-only
      cmd: |
        d=$(mktemp -d)
        git -C "$d" init -q
        printf '{"outcome_id":"x","execution_status":"completed"}\n' > "$d/outcome.json"
        git -C "$d" add outcome.json
        git -C "$d" -c user.email=t@t -c user.name=t commit -qm base
        python3 scripts/gd-detect-review2-code-target.py --cwd "$d"
        echo EXIT=$?
        rm -rf "$d"
      stdout: |
        REVIEW2_CODE_TARGET: execution-only
        REVIEW2_TRIAGE_BASIS: has_code=False(git_diff=empty,git_diff_cached=empty,git_untracked=empty),has_result=True(gd_review_detection.has_execution_artifacts_in_dir)
        EXIT=0
      exit: 0

      # g3: 代码 + 执行结果（未提交 diff + outcome.json 并存）→ 期望 combined
      cmd: |
        d=$(mktemp -d)
        git -C "$d" init -q
        printf '{"outcome_id":"x","execution_status":"completed"}\n' > "$d/outcome.json"
        printf 'a\n' > "$d/f.txt"
        git -C "$d" add f.txt outcome.json
        git -C "$d" -c user.email=t@t -c user.name=t commit -qm base
        printf 'b\n' >> "$d/f.txt"
        python3 scripts/gd-detect-review2-code-target.py --cwd "$d"
        echo EXIT=$?
        rm -rf "$d"
      stdout: |
        REVIEW2_CODE_TARGET: combined
        REVIEW2_TRIAGE_BASIS: has_code=True(git_diff_unstaged=non-empty),has_result=True(gd_review_detection.has_execution_artifacts_in_dir)
        EXIT=0
      exit: 0

      # 信号串断言
      cmd: |
        python3 scripts/gd-detect-review2-code-target.py --help | grep -niE 'REVIEW2_CODE_TARGET|triage|three|三档|code-only|execution-only|combined' | wc -l
        grep -nE 'REVIEW2_CODE_TARGET|REVIEW2_TRIAGE_BASIS' scripts/gd-detect-review2-code-target.py | wc -l
      stdout: |
        8
        25
      note: 第二条计数 25 >= 2，脚本源码含 REVIEW2_CODE_TARGET 与 REVIEW2_TRIAGE_BASIS 两个输出信号串
    not_run_reason: ""

  - sc_ref: SC-5.4
    status: pass
    evidence: |
      # --result 覆盖（repo 无产物，但用户覆盖优先）→ execution-only, exit 0
      cmd: |
        d=$(mktemp -d)
        git -C "$d" init -q
        printf 'a\n' > "$d/f.txt"
        git -C "$d" add f.txt
        git -C "$d" -c user.email=t@t -c user.name=t commit -qm base
        python3 scripts/gd-detect-review2-code-target.py --cwd "$d" --result
        echo EXIT=$?
        rm -rf "$d"
      stdout: |
        REVIEW2_CODE_TARGET: execution-only
        REVIEW2_TRIAGE_BASIS: user_override(--result)
        EXIT=0
      exit: 0
      note: --result 覆盖生效，REVIEW2_TRIAGE_BASIS 含 user_override

      # --code --combined 互斥，exit 非 0
      cmd: |
        d=$(mktemp -d)
        git -C "$d" init -q
        python3 scripts/gd-detect-review2-code-target.py --cwd "$d" --code --combined
        echo EXIT=$?
        rm -rf "$d"
      stdout: |
        usage: gd-detect-review2-code-target [-h] [--cwd DIR] [--code | --result |
                                             --combined]
        gd-detect-review2-code-target: error: argument --combined: not allowed with argument --code
        EXIT=2
      exit: 2
      note: argparse mutually_exclusive_group 阻止 >=2 互斥 flag，exit 2（非零）

      # INDETERMINATE：空 repo 无 diff 无产物，exit 2
      cmd: |
        d=$(mktemp -d)
        git -C "$d" init -q
        git -C "$d" -c user.email=t@t -c user.name=t commit -q --allow-empty -m base
        python3 scripts/gd-detect-review2-code-target.py --cwd "$d"
        echo EXIT=$?
        rm -rf "$d"
      stdout (stderr suppressed, stdout only): |
        REVIEW2_CODE_TARGET: INDETERMINATE
        REVIEW2_TRIAGE_BASIS: has_code=False(git_diff=empty,git_diff_cached=empty,git_untracked=empty),has_result=False(gd_review_detection.has_execution_artifacts_in_dir)
        EXIT=2
      stderr: |
        ERROR: 无法自动判定审查档位（未发现 git 工作树改动，也未发现执行产物文件）。 请使用 --code / --result / --combined 明确指定后重试。
      exit: 2
      note: INDETERMINATE exit 2（非零），交上层问用户，守 D1
    not_run_reason: ""

  - sc_ref: SC-5.5
    status: pass
    evidence: |
      # review2.md 显式调用判定脚本
      cmd: grep -nE 'gd-detect-review2-code-target' commands/review2.md
      stdout: |
        29:- 三档自动判定（无覆盖 flag 时）：调用 `scripts/gd-detect-review2-code-target.py` 探测
        77:调用 `scripts/gd-detect-review2-code-target.py` 执行判定：
        80:python3 scripts/gd-detect-review2-code-target.py --cwd <git-root> [--code|--result|--combined]
        221:| `code`         | `active`（三档判定 `gd-detect-review2-code-target.py` + 用户确认 + 分支 A/B/C） |
      exit: 0
      note: 4 行命中（>= 1）

      # 无裸 VERDICT: 行
      cmd: grep -nE '^[[:space:]]*VERDICT:' commands/review2.md scripts/gd-detect-review2-code-target.py | wc -l
      stdout: 0
      exit: 0
      note: 0 行，脚本与文档均不输出裸 VERDICT:，守 spec §5

      # 语法检查
      cmd: python3 -c "import ast; ast.parse(open('scripts/gd-detect-review2-code-target.py').read()); print('SYNTAX_OK')"
      stdout: SYNTAX_OK
      exit: 0
    not_run_reason: ""

files_added:
  - scripts/gd-detect-review2-code-target.py
  - plans/gd/2026-06-08-l2-review2-redesign/results/t5-split-commands-triage-result.md
files_modified:
  - commands/review2.md
files_unchanged_in_scope: []
owned_paths_writes_only: true
forbidden_paths_touched: []
out_of_scope_writes: []
handoff:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t5-split-commands-triage-result.md
  status_field: exec_status
  summary: >
    review2 入口由 --profile 改为子命令 plan/code；新建 gd-detect-review2-code-target.py
    三档判定脚本（code-only/execution-only/combined/INDETERMINATE），复用
    gd_review_detection.has_execution_artifacts_in_dir 探测执行产物，支持 --cwd 与
    --code/--result/--combined 三个互斥覆盖 flag（argparse mutually_exclusive_group），
    判不准输出 INDETERMINATE 且 exit 2 交用户；三种 git 状态 fixture 真实输出已贴；
    release_closure/runtime_parity 暂留旧式 flag，不拆子命令；文档与脚本均无裸 VERDICT: 行；
    SYNTAX_OK 验证通过。
  blockers: none
known_limitations:
  - >
    INDETERMINATE exit code 为 2（argparse stderr 默认行为），互斥 flag 冲突也是 exit 2；
    任务要求"exit≠0"已满足，但上层调用方若需区分 INDETERMINATE（exit 2）与互斥 flag 错误（exit 2）
    可通过 stdout 的 REVIEW2_CODE_TARGET 行区分。
  - >
    has_result 探测使用 gd_review_detection.has_execution_artifacts_in_dir（rglob "*.json"），
    探测范围为 --cwd 目录及其所有子目录；execution-only fixture g2 中 outcome.json 已 committed，
    探测仍命中（探测不依赖 git 状态，只看文件系统）——这与 spec §2.1 "发现执行产物文件" 定义一致。
