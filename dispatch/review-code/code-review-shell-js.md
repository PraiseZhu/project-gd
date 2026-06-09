```yaml
reviewer: code-review-shell-js
files_reviewed:
  - scripts/gd-review2-package-deliverable.sh
  - scripts/gd-review2-preflight.sh
  - scripts/plan-mode-antifill-stop-hook.js
findings:
  - severity: HIGH
    file: scripts/plan-mode-antifill-stop-hook.js
    line: 218-269
    category: error_handling
    description: >-
      hook_event_name 在文件头部契约里声明为 "Stop"（行 21），但 main() 解析 payload
      后从不校验 payload.hook_event_name === "Stop"。一旦该文件被 T9 装为通用
      Stop / PostToolUse hook，它会对所有 Stop 事件（非 plan-mode）都跑 anti-fill
      gate：任何含 "SC-数字" 字样但缺 verify 行的普通对话都会被错误 block（exit 1）。
      gate 的语义边界（仅 plan mode）只靠注释保证，代码层无防护。与 obs 1301 一致。
    suggested_fix: >-
      在 main() parse 成功后、提取 planText 前加守卫：
      `if (payload.hook_event_name && payload.hook_event_name !== "Stop") process.exit(0);`
      若还需限定 plan mode，应额外检查 plan-mode 专属字段（如 payload.plan_text 存在
      或上游约定的 mode 标记），否则边界仍不收敛。
  - severity: LOW
    file: scripts/gd-review2-preflight.sh
    line: 80
    category: maintainability
    description: >-
      evidence_content="$(cat "$EVIDENCE_PATH")" 把整个文件读进变量，但下游 python
      直接用 $EVIDENCE_PATH 路径自行 open 读取，evidence_content 从未被引用。死代码 +
      一次多余的全文件读取。变量名加引号正确，无注入风险，纯冗余。
    suggested_fix: 删除第 80 行 evidence_content 赋值。
  - severity: LOW
    file: scripts/gd-review2-package-deliverable.sh
    line: 240,242,243
    category: error_handling
    description: >-
      git rev-parse / git diff --cached 用 `|| echo ...` / `|| true` 兜底，命令替换在
      set -e 下不会因子命令失败而退出（已正确处理）。但 CHANGED_COUNT 在管道 `wc -l`
      失败时的 `|| echo '0'` 实际不可达（wc 几乎不失败），属防御冗余，非缺陷。无需修改，
      仅记录：此处静默兜底是有意为之且安全（草稿生成场景，失败降级为占位文本）。
    suggested_fix: 无需修改（防御性兜底符合草稿生成语义）。
notes_positive:
  - >-
    SC-8.5 满足：唯一的写操作是 `git add -u`（行 183），只 stage 已跟踪文件的改动，
    不会误纳入未跟踪/新文件，范围正确（非 git add . / -A）。grep 真实 git commit/push
    命令返回 0 条——所有 commit/push 字符串都在 echo 草稿里（行 309 等），不在执行路径。
  - >-
    --dry-run 真正跳过副作用：实测 dry-run 后 staged 文件数=0；红 gate exit=1；
    参数错误 exit=2；与契约一致。
  - >-
    preflight JSON 解析健壮：用 python3 json.load + 显式 JSONDecodeError 捕获；
    实测畸形 JSON → exit 1 + DRYRUN_EVIDENCE_INVALID；缺文件 → exit 3；
    缺字段（paths_exercised 非空数组 / fallback_no_api_key=true）逐项校验。
  - >-
    JS 确为 source-only：唯一 require 是 fs，仅 readFileSync（行 238），无 writeFile /
    child_process / exec / eval / ~/.claude 写入。无路径遍历主动构造（transcript_path
    来自 hook payload，由 Claude Code 注入而非外部攻击者，且读失败 fail-open 跳过 gate）。
  - >-
    JS 正则无 stateful lastIndex bug：SC_VERIFY_LINE_RE / SC_EXPECT_LINE_RE 非 global
    （仅 /i），.test()/.exec() 复用安全；global 的 SC_START_RE / SC_ID_RE 在
    extractScBlocks 内以 new RegExp 重建（行 125-126），无跨调用状态残留。
  - 三个文件全部 `set -euo pipefail`（sh）/ "use strict"（js），错误处理基线达标。
validation:
  bash_n:
    gd-review2-package-deliverable.sh: PKG_SYNTAX_OK
    gd-review2-preflight.sh: PREFLIGHT_SYNTAX_OK
  node_check:
    plan-mode-antifill-stop-hook.js: JS_SYNTAX_OK
  runtime_checks:
    dry_run_no_side_effect: "staged_after_dryrun=0 (pass)"
    red_gate_exit: "1 (pass)"
    param_error_exit: "2 (pass)"
    preflight_malformed_json: "exit 1 DRYRUN_EVIDENCE_INVALID (pass)"
    preflight_missing_file: "exit 3 DRYRUN_EVIDENCE_MISSING (pass)"
    preflight_valid: "exit 0 DRYRUN_EVIDENCE_OK (pass)"
    git_add_scope: "git add -u only; zero real git commit/push in exec path (pass)"
decision: APPROVE_WITH_COMMENTS
```
