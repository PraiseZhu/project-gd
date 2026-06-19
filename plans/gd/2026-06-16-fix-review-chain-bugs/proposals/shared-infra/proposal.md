# Step plan 草稿：共享组件 + 传输层 fail-open 修复（track t1-shared-infra）

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-step-plan

日期：2026-06-16
状态：draft
负责人：Claude 执行；Codex 可选 cross-review
proposal_id：frcb-t1-shared-infra
parent_dispatch_id：fix-review-chain-bugs-20260616
parent_track_id：t1-shared-infra

---

## 0. 调查结论（先读，影响修复范围）

本桶在动手前对 A-E 五个组件逐行核对，发现**dispatch 引用的部分行号 / 病灶来自更早的 revision，当前代码已重构**。主 agent 必须按本节区分"仍活的 bug"与"已修但仍可加固"，不要对已 fail-closed 的路径重复打补丁（否则浪费两次 child 配额、引入回归）。

### 仍活的 bug（必须修）

| 代号 | 文件:行 | 现状 | 病类 |
|------|---------|------|------|
| N9-bridge | `scripts/gd-codex-bridge-review.py:1979` 与 `:2085` | `return 0 if decision=="APPROVED" else (1 if decision=="FAILED" else 0)` → REQUIRES_CHANGES 落入 else 返回 **exit 0** | returncode 非真相源 |
| V1 | `scripts/gd-validate-review-content-evidence.py:154-155, 190-191`（经 `validate():300` 的 `verdict = _extract_verdict(...) or "UNKNOWN"` 触发） | verdict=UNKNOWN 时 `_check_scope_coverage` 与 `_check_requires_changes_has_findings` 双双 `return`（早退），scope 覆盖 + finding 两大反造假检查被跳过 | 未知态倒向 fail-open |
| V16 | `scripts/gd-validate-review-content-evidence.py:123-124, 362` | 无 `### Finding` 块时 `_check_finding_has_line_evidence` 早 return；`--skip-line-ref-check` 一个 flag 关掉最强 line-ref 反造假检查 | 未知态/开关放水 |
| V3 | `scripts/gd-validate-execution-outcome.py:235-239` | build_gate 项 `declared in ("not_run","n_a") → continue`，不复跑（注释自认"can't enforce reason here without schema change, so accept it"） | 失败/缺验证当通过 |
| V4 | `scripts/gd-validate-execution-outcome.py:432` | Phase2 复跑门 `if args.plan_files and not errors:` → 任一 Phase1 schema 瑕疵即静默跳过命令级硬复跑 | 失败静默跳过 |
| P2-dup | `scripts/gd-validate-execution-outcome.py:481-489` | 重复 sc_ref 仅 `WARN ... later value overwrites earlier`，不报错；后写状态覆盖先写，可把 fail 洗成 pass | 重复键覆盖 |
| N10 | `scripts/gd-review-controller.py:145-150` | `git stash create` 非零仅 `print(... WARNING ...)`，仍 fall-through 到 HEAD blob fallback，把可能错误的 delta 当 clean tree 喂给 D7 fanout | git 失败注假增量 |
| #13 | `vendor/l3-transport/scripts/install-transport.sh:265` | `launchctl list \| grep -q "$_label"` 子串匹配：daemon label 是 healthcheck label 的子串时误判已加载 | 子串误匹配 |
| T1 | `vendor/l3-transport/scripts/review-result-writer.sh:130-131` | `echo "$CODEX_OUTPUT" > "$RESULT_FILE"` 在 `set -e` 下无失败分支：磁盘满/只读时中途 abort，不输出任何 `[REVIEW]` verdict（静默中断） | set -e 静默中断 |
| T-install | `install-transport.sh:276, 283` | `:276` kickstart 双失败仅 `log "NOTE: ..."`；`:283` `pgrep -f "codex-watch run"` 字面/子串匹配可被同名进程误判 | 双失败只 NOTE |
| T-watch | `vendor/l3-transport/handoff/lib/watch-state.sh:123` | `for sf in $(ls -r "${HANDOFF_ACTIVE}"/*.status ...)`：`$(ls)` 无引号 word-split，路径含空格断裂 | ls 解析断裂 |

### 已修但 dispatch 仍按旧态描述（不要重复改；可在 review 中确认即可）

| 代号 | 当前真相（已 fail-closed） | 证据 |
|------|--------------------------|------|
| #1 bridge `_run_bridge_job` | 该函数名在当前文件**不存在**；等价逻辑是 `cmd_run_bridge`/`_cmd_run_bridge_inner`。writer 超时、MALFORMED、FAILED、exit≠0、result path 缺失、L3 校验器超时/异常 全部已映射成 `gd_review_decision: FAILED`（`:1796-1845, 1880-1911`）。**dispatch 的 `except:pass;return []` 已不在此处** | `:1796` `except subprocess.TimeoutExpired: ... _failed_mapped` |
| #1 的 `return []` | 唯一的 `return []` 在 `_split_findings:646`，是"raw 无 `## Findings` 段就返回空 finding 列表"——这是解析 helper 的合法空集，不是失败坍缩成 APPROVED；其上层对无 finding 的 REQUIRES_CHANGES 另有校验 | `:643-651` |
| #11 `--out` 当文件 vs 目录 | 当前 `--out` 在所有子命令均 `required=True` 且按**文件**写（`:1700/2029/2239` `out_path=Path(args.out); out_path.write_text(...)`）。若文档仍写"目录"才有 IsADirectoryError 风险——这是**文档 bug 不是代码 bug**；修法限定为校文档，不改写入语义 | `:2567/2586/2607/2614` `add_argument("--out", required=True)` |
| P2 `setdefault` 兜底必填字段（dispatch:316） | `:316` 实为 `_normalize_to_outcome` 把 flat 结果包成 1-elem `task_outcomes`，仅 `task.setdefault("task_id", ...)` 补 task_id（标识非校验关键字段）；缺 `exec_status`/`sc_acceptance` 时走 REQUIRED_TOP/REQUIRED_TASK 报错，**不会**被 setdefault 洗白。dispatch 的"缺必填字段被兜底"在当前代码不成立 | `:314-324, 342-359` |
| #12 CLAUDE_PLUGIN_DATA fallback 双抄 | 两处 fallback（`install-transport.sh:98` 与 `state-paths.sh:17`）当前值一致（均 `${CLAUDE_PLUGIN_DATA:-$HOME/.claude}`，注意 state-paths 再拼 `/gd-handoff`）。这是**重复定义漂移风险**不是当前断链；修法是抽公共定义或加 parity 断言，非紧急 | `state-paths.sh:17`, `install-transport.sh:98` |

> **N1 同源提醒（dispatch §3 要求显式标注）**：本桶 N9-bridge 修的是 bridge 侧 exit-code 映射。dispatch 称 `_run_bridge_job` fail-open 在 L3 另一个 child 的 `scripts/gd-review-merge-and-fix-loop.py:516-567`（代号 N1）有同源拷贝。**主 agent 在批准本桶 bridge 修复时，必须同步确保 L3 桶的 N1（merge-and-fix-loop 内 bridge 调用结果的 fail-open 处理）一并修；否则 L3 链仍漏。** 本 child 不动 merge-and-fix-loop（不在 owned_paths），仅在此挂提醒。

---

## 1. 目标链（继承 + 当前 task goal）

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，提升复杂任务计划/审查/执行/验收效率，Codex 作 cross-review sidecar 降低填表式计划与执行遗漏风险。
CHAIN_GOAL:   用 shared core 固定目标链/SC/任务包/review contract/anti-fill 标准，保证 /gd 各阶段引用同一套契约。
PHASE_GOAL:   为 GD 审查链路 fail-open/放水类 bug 生成可执行修复计划套件。
TASK_GOAL:    为「共享组件 + 传输层」桶的 fail-open bug 产出 step-plan 草稿 + 候选 task packet，每个修复标清「动哪几条链(L1/L2/L3)、测试须覆盖谁」，可被本 proposal 的 verify 命令验证。
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：`fail-closed 收口完整性; returncode 与 decision 一致性; 未知态判 fail 不放水; 跨链回归覆盖(L1/L2/L3); 传输层 set -e 失败分支`
- Domain-specific notes：这些组件被多链共用，每个 step 的 VERIFY 必须既验"新行为正确"（fail-closed），也验"老成功路径未回归"（APPROVED 仍 exit 0、completed 仍 PASS）。

---

## 3. 前置条件

- blocked_by：`—`
- 必须的 baseline / artifact：`scripts/gd-codex-bridge-review.py --self-test`、`tests/gd-l3-regression-v1-fixtures.sh`、`python3 scripts/gd-review-router.py --self-test` 当前为绿（修复后须仍绿）。
- Hard-stop 条件：任一现有 smoke / self-test 在动手前已红 → 先定位是否本桶引入，未确认前不继续。

---

## 4. 成功标准（SC，本 step 内的）

> Anti-fill 规则 A：每条 SC 绑定命令 / 路径 / 输出断言之一。

- [ ] SC-1：bridge 在 decision=REQUIRES_CHANGES 时返回非 0 exit（不再落 else 返回 0），APPROVED 仍 0、FAILED 仍 1。
  - verify (method: command): `python3 -c "import ast,sys; src=open('scripts/gd-codex-bridge-review.py').read(); bad=[n for n in ast.walk(ast.parse(src)) if isinstance(n,ast.Return) and isinstance(getattr(n,'value',None),ast.IfExp)]; sys.exit(0 if not any('APPROVED' in ast.dump(b.value) and 'FAILED' in ast.dump(b.value) for b in bad) else 1)"`
  - expect: `exit 0（修复后不再存在 APPROVED/FAILED 三元 return 把 REQUIRES_CHANGES 兜成 0）`
- [ ] SC-2：content-evidence 验证器在 verdict 无法识别（UNKNOWN）时判 fail（exit 1），不再跳过 scope/finding 检查。
  - verify (method: command): `python3 scripts/gd-validate-review-content-evidence.py --target /dev/stdin --review - <<<'no verdict here' 2>/dev/null; test $? -eq 1 && echo PASS || echo FAIL`
  - expect: `PASS`
- [ ] SC-3：execution-outcome 验证器对声明 not_run 的 build_gate 项不再无条件放过（要求 not_run_reason 或复跑），用断言锁定旧的 `declared in ("not_run","n_a"): continue` 不再裸存在。
  - verify (method: assertion): `python3 -c "import re,sys; s=open('scripts/gd-validate-execution-outcome.py').read(); sys.exit(1 if re.search(r'declared in \(\"not_run\", \"n_a\"\):\n\s+# .*\n\s+# .*\n\s+# .*\n\s+continue', s) else 0)"`
  - expect: `exit 0（旧的 3 行注释 + 裸 continue 块已被替换为带 reason 校验/复跑的逻辑）`
- [ ] SC-4：execution-outcome Phase2 复跑不再被任意 Phase1 schema 瑕疵静默跳过——`if args.plan_files and not errors:` 改为 schema 失败也至少标记 verify 未跑（不静默）。
  - verify (method: assertion): `python3 -c "import sys; s=open('scripts/gd-validate-execution-outcome.py').read(); sys.exit(0 if 'if args.plan_files and not errors:' not in s else 1)"`
  - expect: `exit 0（旧的双条件门已被替换）`
- [ ] SC-5：execution-outcome 重复 sc_ref 不再仅 WARN——同一 sc_ref 出现冲突状态（一个 pass 一个 fail）时报 error（exit 1）。
  - verify (method: assertion): `python3 -c "import sys; s=open('scripts/gd-validate-execution-outcome.py').read(); sys.exit(0 if 'later value overwrites earlier' not in s or 'errors.append' in s.split('later value overwrites earlier')[0].rsplit('def ',1)[-1] else 1)"`
  - expect: `exit 0（重复键冲突路径已含 errors.append，不再只是 WARN）`
- [ ] SC-6：controller `take_delta_snapshot` 在 `git stash create` 非零时不再静默 fall-through，返回值能让上层判 DELTA_SCOPE 不可信（raise 或返回带失败标记的 tuple）。
  - verify (method: assertion): `python3 -c "import sys; s=open('scripts/gd-review-controller.py').read(); blk=s.split('def take_delta_snapshot',1)[1].split('\ndef ',1)[0]; sys.exit(0 if ('raise' in blk or 'returncode != 0' in blk and 'return None' in blk) else 1)"`
  - expect: `exit 0（git 失败分支有显式失败传播，不止 print WARNING）`
- [ ] SC-7：install-transport.sh 的 launchctl label 匹配改为精确（行首/制表锚定），不再 `grep -q "$_label"` 子串误匹配；用断言锁定旧子串匹配不再裸存在。
  - verify (method: assertion): `grep -n 'launchctl list | grep -q "\$_label"' vendor/l3-transport/scripts/install-transport.sh; test $? -ne 0 && echo PASS || echo FAIL`
  - expect: `PASS（旧裸子串 grep 已被精确匹配替换）`
- [ ] SC-8：review-result-writer.sh 写 RESULT_FILE 有失败分支：写失败时输出明确 `[REVIEW] ✗ FAILED` 并 exit 非 0，不在 set -e 下静默中断。
  - verify (method: assertion): `python3 -c "import sys; s=open('vendor/l3-transport/scripts/review-result-writer.sh').read(); seg=s.split('RESULT_FILE=',1)[1][:400]; sys.exit(0 if '|| {' in seg or '|| echo' in seg or 'if ! echo' in seg else 1)"`
  - expect: `exit 0（RESULT_FILE 写入后紧跟失败分支）`
- [ ] SC-9：watch-state.sh `recent_failed_jobs` 不再 `$(ls -r ...)` word-split：改用 glob 数组 / find -print0，路径含空格不断裂。
  - verify (method: assertion): `python3 -c "import sys; s=open('vendor/l3-transport/handoff/lib/watch-state.sh').read(); blk=s.split('recent_failed_jobs',1)[1].split('\n}',1)[0]; sys.exit(1 if 'in \$(ls -r' in blk else 0)"`
  - expect: `exit 0（裸 ls -r command-substitution 已移除）`
- [ ] SC-10：跨链回归——三套 self-test/smoke 在全部修复后仍绿（不引入回归）。
  - verify (method: command): `python3 scripts/gd-codex-bridge-review.py --self-test && python3 scripts/gd-review-router.py --self-test && bash tests/gd-l3-regression-v1-fixtures.sh`
  - expect: `三条全 exit 0`

---

## 5. 非目标

- 不动 `scripts/gd-review-merge-and-fix-loop.py`（N1 在 L3 桶，本桶仅挂同源提醒）。
- 不改 review-result-writer 的既有投递逻辑（codex-send-wait 调用路径、baseline 保存格式、stdout 格式）——只补失败分支（gd-review-standard §8.4 受限例外只授权透传参数，不授权改投递）。
- 不重写 schema（V3 注释提到的"需 schema change"如确需，留作独立 step，本桶先用 not_run_reason 校验兜）。
- 不动 `prompts/gd-review-standard.md`、`schema/*.json`（shared core 只消费不改）。
- 不启动 daemon / 注册 hook / 改 cron。

---

## 6. 实现步骤（按组件聚合为 3 批）

```text
Step.1  批1 共享 P0：bridge exit-code + 两个内容/执行验证器未知态/放水
  WHERE: scripts/gd-codex-bridge-review.py:1979,2085；scripts/gd-validate-review-content-evidence.py:154,190,123,362,300；scripts/gd-validate-execution-outcome.py:235,432,481
  WHAT:  (a) 把两处 `return 0 if APPROVED else (1 if FAILED else 0)` 改为 REQUIRES_CHANGES→非0；
         (b) content-evidence: verdict=UNKNOWN 判 fail（在 validate() 收尾对 UNKNOWN 追加 error），scope/finding 检查不再因非 APPROVED/非 REQUIRES_CHANGES 早退放水；评估 `--skip-line-ref-check` 是否收窄为仅 fixture 标记；
         (c) execution-outcome: build_gate not_run 要求 reason；Phase2 复跑门去掉 `and not errors` 静默跳过语义；重复 sc_ref 冲突状态报 error。
  WHY:   这三类是"未知态/失败坍缩成通过"的核心放水点，直接决定 L2/L3 审查能否拦住假通过。
  VERIFY: SC-1..SC-5 全 pass + SC-10 self-test 绿。
  影响链路: L2(/review2 直调 bridge + 内容/执行验证器)、L3(merge-loop/router 间接)。
  测试须覆盖: 用 fixture 造一份 verdict=UNKNOWN 的 raw review、一份 REQUIRES_CHANGES 的 mapped、一份 build_gate=not_run 无 reason 的 outcome，断言三者均判 fail。

Step.2  批2 共享 controller：delta snapshot git 失败传播
  WHERE: scripts/gd-review-controller.py:145-150（take_delta_snapshot）；run_round1:443-444 fut.result()
  WHAT:  git stash create / git diff 非零时不再仅 print WARNING fall-through——返回失败标记或 raise，让 DELTA_SCOPE 标记不可信；run_round1 的 fut_a/fut_b .result() 包 try/except，bridge 异常落 CONVERGENCE 失败态而非 crash controller。
  WHY:   git 失败注假 clean-tree delta 会误导 D7 fanout（大改当小改少派 reviewer）；fut.result() 裸抛会让整个 controller 崩，比超时更糟（无 verdict 也无降级标记）。
  VERIFY: SC-6 pass + controller self-test（若有）绿。
  影响链路: L2(/review2 code 主场)、L3(router 间接)。
  测试须覆盖: 模拟 git 命令非零 / 模拟 bridge 抛异常，断言 controller 不 crash 且产出 degraded/failed 标记。

Step.3  批3 传输层 bash：精确匹配 + set -e 失败分支 + ls 解析
  WHERE: vendor/l3-transport/scripts/install-transport.sh:265,276,283；vendor/l3-transport/scripts/review-result-writer.sh:130-131；vendor/l3-transport/handoff/lib/watch-state.sh:123
  WHAT:  (a) install-transport label 匹配 `grep -q "$_label"` → 精确（`grep -qx` 或带边界 regex）；kickstart 双失败从 NOTE 升为可观测失败（exit 或 WARNING+返回码）；pgrep 收窄；
         (b) review-result-writer `echo > "$RESULT_FILE"` 加 `|| { echo "[REVIEW] ✗ FAILED — 无法写结果文件"; exit 1; }`；
         (c) watch-state `for sf in $(ls -r ...)` → glob 数组或 `find ... -print0 | sort -rz` 读法。
  WHY:   子串误匹配让 installer 以为 daemon 已加载而跳过 reload；set -e 静默中断让磁盘满时无 verdict 静默失败；ls word-split 在含空格路径下漏报 failed jobs。
  VERIFY: SC-7..SC-9 pass + install-transport.sh --dry-run 可跑通。
  影响链路: L1+L2+L3 全链 + codex-watch daemon。
  测试须覆盖: 构造 label 互为子串场景、只读 RESULT_FILE 目录、含空格的 .status 路径，断言三者行为正确。
```

---

## 7. Task Packet 拆分

| task_id | agent_role | owned_paths | blocked_by | can_parallel_with |
|---------|-----------|------------|-----------|-------------------|
| fix-bridge-failopen | implementer | scripts/gd-codex-bridge-review.py | — | fix-content-evidence-failopen, fix-execution-outcome-failopen, fix-controller-delta, fix-transport-bash |
| fix-content-evidence-failopen | implementer | scripts/gd-validate-review-content-evidence.py | — | fix-bridge-failopen, fix-execution-outcome-failopen, fix-controller-delta, fix-transport-bash |
| fix-execution-outcome-failopen | implementer | scripts/gd-validate-execution-outcome.py | — | fix-bridge-failopen, fix-content-evidence-failopen, fix-controller-delta, fix-transport-bash |
| fix-controller-delta | implementer | scripts/gd-review-controller.py | — | fix-bridge-failopen, fix-content-evidence-failopen, fix-execution-outcome-failopen, fix-transport-bash |
| fix-transport-bash | implementer | vendor/l3-transport/scripts/install-transport.sh, vendor/l3-transport/scripts/review-result-writer.sh, vendor/l3-transport/handoff/lib/watch-state.sh | — | （前四个全部） |

> 五个 task 的 owned_paths 互不重叠，可并发；但受 `/gd` `max_parallel=2` 硬上限，主 agent 应分波派发（每波≤2）。

---

## 8. 候选 Task Packets（自包含）

### Task: fix-bridge-failopen
- task_id: `fix-bridge-failopen`
- agent_role: implementer
- owned_paths: `scripts/gd-codex-bridge-review.py`
- required_context: `prompts/gd-review-standard.md`、`scripts/gd-codex-bridge-review.py`
- 要修的具体 bug：
  - N9-bridge `:1979` 与 `:2085`：`return 0 if decision == "APPROVED" else (1 if decision == "FAILED" else 0)` 把 REQUIRES_CHANGES 兜成 exit 0。
- 修法：两处统一改为「APPROVED→0；REQUIRES_CHANGES→非0（如 1）；FAILED→1」的显式映射（建议抽 helper `_decision_exit(decision)` 单点定义，两处共用，避免再次漂移）。调用方（controller/merge-loop）据此 exit≠0 即 fail-closed。
- verify 命令：`python3 -c "import ast,sys; src=open('scripts/gd-codex-bridge-review.py').read(); bad=[n for n in ast.walk(ast.parse(src)) if isinstance(n,ast.Return) and isinstance(getattr(n,'value',None),ast.IfExp) and 'APPROVED' in ast.dump(n.value) and 'FAILED' in ast.dump(n.value)]; sys.exit(1 if bad else 0)"` → exit 0
- 回归：`python3 scripts/gd-codex-bridge-review.py --self-test` → exit 0

### Task: fix-content-evidence-failopen
- task_id: `fix-content-evidence-failopen`
- agent_role: implementer
- owned_paths: `scripts/gd-validate-review-content-evidence.py`
- required_context: `prompts/gd-review-standard.md`、`scripts/gd-validate-review-content-evidence.py`
- 要修的具体 bug：
  - V1 `:154-155, 190-191`（由 `:300` `verdict or "UNKNOWN"` 触发）：verdict 非 APPROVED 非 REQUIRES_CHANGES 时 scope 覆盖 + finding 检查双双早退，UNKNOWN 等于免检。
  - V16 `:123-124, :362`：无 `### Finding` 块时 line-ref 检查早 return；`--skip-line-ref-check` 一个 flag 关掉最强 line-ref 反造假检查。
- 修法：(a) 在 `validate()` 收尾对 `verdict == "UNKNOWN"`（即 `_extract_verdict` 返回 None）追加一条 error（无法识别 verdict = fail-closed，不得 EVIDENCE_VALID）；(b) 评估把 `--skip-line-ref-check` 的适用面收窄为仅当 target 是显式 fixture/stub 标记时才允许（或保留但在 report 中显式记录"line-ref 检查被跳过"，让上层可见放水）。**不放宽**已有的 APPROVED/REQUIRES_CHANGES 检查。
- verify 命令：`printf 'review with no verdict line\n' | python3 scripts/gd-validate-review-content-evidence.py --target prompts/gd-review-standard.md --review - 2>/dev/null; test $? -eq 1 && echo PASS || echo FAIL` → PASS
- 回归：`bash tests/gd-l3-regression-v1-fixtures.sh` → exit 0

### Task: fix-execution-outcome-failopen
- task_id: `fix-execution-outcome-failopen`
- agent_role: implementer
- owned_paths: `scripts/gd-validate-execution-outcome.py`
- required_context: `prompts/gd-review-standard.md`、`scripts/gd-validate-execution-outcome.py`
- 要修的具体 bug：
  - V3 `:235-239`：build_gate 项 declared not_run/n_a 无条件 continue，不复跑、不要求 reason。
  - V4 `:432`：Phase2 复跑门 `if args.plan_files and not errors:`，任一 schema 瑕疵静默跳过命令级硬复跑。
  - P2-dup `:481-489`：重复 sc_ref 仅 WARN，后写覆盖先写，可把 fail 洗成 pass。
- 修法：(a) build_gate not_run 必须带 `not_run_reason`（缺 reason 报 error）；(b) Phase2 门改为「即使 Phase1 有 error 也不静默跳过 verify——至少在最终输出标记 `VERIFY_RERUN: SKIPPED due to schema errors`，让放水可见」（gd-review-standard P12 fail-visibly）；(c) 同一 sc_ref 出现冲突 status（pass vs fail）时升为 error 而非 WARN。
- verify 命令：`python3 -c "import sys; s=open('scripts/gd-validate-execution-outcome.py').read(); sys.exit(0 if ('if args.plan_files and not errors:' not in s and 'later value overwrites earlier' not in s) else 1)"` → exit 0
- 回归：构造一份 build_gate=not_run 无 reason 的 fixture outcome.json，断言 `python3 scripts/gd-validate-execution-outcome.py <fixture>` exit 1。

### Task: fix-controller-delta
- task_id: `fix-controller-delta`
- agent_role: implementer
- owned_paths: `scripts/gd-review-controller.py`
- required_context: `scripts/gd-review-controller.py`、`prompts/gd-review-standard.md`
- 要修的具体 bug：
  - N10 `:145-150`：`git stash create` 非零仅 print WARNING 后 fall-through 到 HEAD blob，注假 clean-tree delta。
  - N7 `:443-444`：`fut_a.result()` / `fut_b.result()` 无 try/except，bridge 异常让 controller crash 而非降级。
- 修法：(a) `take_delta_snapshot` git 命令非零时返回失败标记（如 `(None, "")` 配一个布尔 ok，或 raise 让 caller 判 DELTA_SCOPE=unknown 走保守 full_matrix fanout）；(b) `run_round1` 的 `fut.result()` 包 try/except，捕获后把对应 reviewer 标记 degraded/failed，输出 CONVERGENCE 失败态。
- verify 命令：`python3 -c "import sys; s=open('scripts/gd-review-controller.py').read(); blk=s.split('def take_delta_snapshot',1)[1].split('\ndef ',1)[0]; sys.exit(0 if ('raise' in blk or 'return None' in blk) else 1)"` → exit 0
- 回归：`python3 scripts/gd-review-router.py --self-test` → exit 0（controller 自测若有单独入口，一并跑）

### Task: fix-transport-bash
- task_id: `fix-transport-bash`
- agent_role: implementer
- owned_paths: `vendor/l3-transport/scripts/install-transport.sh`、`vendor/l3-transport/scripts/review-result-writer.sh`、`vendor/l3-transport/handoff/lib/watch-state.sh`
- required_context: `vendor/l3-transport/scripts/install-transport.sh`、`vendor/l3-transport/scripts/review-result-writer.sh`、`vendor/l3-transport/handoff/lib/watch-state.sh`、`Project GD/CLAUDE.md`（vendor↔live 方向章节）
- 要修的具体 bug：
  - #13 `install-transport.sh:265`：`launchctl list | grep -q "$_label"` 子串误匹配（daemon label 是 healthcheck label 子串）。
  - T-install `install-transport.sh:276`（kickstart 双失败只 NOTE）、`:283`（`pgrep -f "codex-watch run"` 子串误判）。
  - T1 `review-result-writer.sh:130-131`：`echo "$CODEX_OUTPUT" > "$RESULT_FILE"` 在 set -e 下无失败分支，磁盘满/只读时静默中断、无 verdict。
  - T-watch `watch-state.sh:123`：`for sf in $(ls -r "${HANDOFF_ACTIVE}"/*.status ...)` 无引号 word-split，路径含空格断裂。
- 修法：(a) label 匹配用 `grep -qx` 或 `grep -qE "(^|\s)${_label}(\s|$)"`；(b) kickstart 双失败升为带返回码的 WARNING（或在 verify 段 pgrep 失败时 exit 非 0），pgrep 模式收窄到精确二进制名；(c) RESULT_FILE 写入加 `|| { echo "[REVIEW] ✗ FAILED — 无法写结果文件 $RESULT_FILE" >&2; exit 1; }`；(d) `recent_failed_jobs` 改 glob 数组或 `find "$HANDOFF_ACTIVE" -name '*.status' -print0 | sort -rz` 读法。改动后保持 vendor 文件可被 `install-transport.sh --dry-run` 解析。
- verify 命令：`grep -q 'launchctl list | grep -q "\$_label"' vendor/l3-transport/scripts/install-transport.sh && echo FAIL || echo PASS` → PASS（旧子串匹配已替换）
- 回归：`bash vendor/l3-transport/scripts/install-transport.sh --dry-run` → 可跑通无语法错（`bash -n` 三个改动文件均通过）

---

## 9. 边界（修改 / 不修改）

修改：
- `scripts/gd-codex-bridge-review.py`
- `scripts/gd-validate-review-content-evidence.py`
- `scripts/gd-validate-execution-outcome.py`
- `scripts/gd-review-controller.py`
- `vendor/l3-transport/scripts/install-transport.sh`
- `vendor/l3-transport/scripts/review-result-writer.sh`
- `vendor/l3-transport/handoff/lib/watch-state.sh`

不修改：
- `scripts/gd-review-merge-and-fix-loop.py`（N1，L3 桶；本桶仅挂同源提醒）
- `prompts/gd-review-standard.md`、`schema/*.json`（shared core）
- `vendor/l3-transport/handoff/bin/codex-send-wait`、`codex-watch` daemon、任何 live `~/.claude/**`
- `~/.claude/**`、其他 step 的 owned_paths

---

## 10. 风险与防护

| 风险 | 防护 |
|------|------|
| 改 bridge exit-code 误伤 APPROVED 路径（变成非 0 阻断正常通过） | SC-1 同时断言 APPROVED→0；self-test 覆盖三态 |
| content-evidence UNKNOWN 判 fail 误杀 legacy fixture（本就无 verdict 的 parser stub） | 与 `--skip-line-ref-check` 同款，给 fixture 显式豁免标记；改前先跑 `tests/gd-l3-regression-v1-fixtures.sh` 确认豁免面 |
| Phase2 门改动让大量历史 outcome 突然报错 | 改为"标记 SKIPPED 可见"而非"硬 fail"，渐进收口；P12 fail-visibly 而非 fail-loud |
| 传输层改 vendor 后 vendor↔live hash 漂移 | 改 vendor 源后必须重新 `install-transport.sh`（用户授权时）；本桶只改 vendor，部署是独立决策 |
| set -e 下新加失败分支自身语法错导致 writer 整体崩 | 每个改动文件过 `bash -n`；install-transport `--dry-run` 验证 |
| N1 同源拷贝未同步修 → L3 仍漏 | §0 已显式挂提醒；主 agent 批准时须 cross-check L3 桶 |

---

## 11. 测试计划

```bash
# 单点 verify（对应 SC-1..SC-9，已在各 task packet 内列）
python3 scripts/gd-codex-bridge-review.py --self-test
python3 scripts/gd-review-router.py --self-test
bash tests/gd-l3-regression-v1-fixtures.sh
bash -n vendor/l3-transport/scripts/install-transport.sh
bash -n vendor/l3-transport/scripts/review-result-writer.sh
bash -n vendor/l3-transport/handoff/lib/watch-state.sh
bash vendor/l3-transport/scripts/install-transport.sh --dry-run
# 跨链 smoke（按 CLAUDE.md 命令章节，覆盖 L1/L2/L3）
bash tests/gd-review2-plan-routing-smoke.sh
```

---

## 12. Assumptions

- dispatch 的 A-E 行号取自更早 revision；本 proposal 已以当前文件实测为准（见 §0），主 agent 应信 §0 的"仍活/已修"分类。
- 修复保持 stdlib-only（验证器无第三方依赖），与现有约定一致。
- vendor 改动不触发自动部署到 live；部署是独立、需用户授权的决策（CLAUDE.md 红线 7 + deploy-live skill）。
- `--out` 文档/目录矛盾（#11）当前是文档问题不是代码问题，本桶若处理仅校文档不改写入语义，已在 §0 标注；如确认文档无误则该项无需动。

---

<!-- gd-child-plan-proposal-json:start -->
```json
{
  "proposal_id": "frcb-t1-shared-infra",
  "parent_dispatch_id": "fix-review-chain-bugs-20260616",
  "parent_track_id": "t1-shared-infra",
  "agent_role": "child_planner",
  "output_status": "completed",
  "summary_cn": "共享组件+传输层 fail-open 修复套件：bridge exit-code(REQUIRES_CHANGES 误判0)、content/execution 验证器未知态放水、controller git-delta 假增量、传输层 set -e 静默中断与子串误匹配；标注 dispatch 部分行号属旧 revision 已修，并挂 N1 同源提醒。",
  "blocked_reason": null,
  "task_packets": [
    {"task_id": "fix-bridge-failopen", "owned_paths": ["scripts/gd-codex-bridge-review.py"], "required_context": ["prompts/gd-review-standard.md", "scripts/gd-codex-bridge-review.py"]},
    {"task_id": "fix-content-evidence-failopen", "owned_paths": ["scripts/gd-validate-review-content-evidence.py"], "required_context": ["prompts/gd-review-standard.md", "scripts/gd-validate-review-content-evidence.py"]},
    {"task_id": "fix-execution-outcome-failopen", "owned_paths": ["scripts/gd-validate-execution-outcome.py"], "required_context": ["prompts/gd-review-standard.md", "scripts/gd-validate-execution-outcome.py"]},
    {"task_id": "fix-controller-delta", "owned_paths": ["scripts/gd-review-controller.py"], "required_context": ["scripts/gd-review-controller.py", "prompts/gd-review-standard.md"]},
    {"task_id": "fix-transport-bash", "owned_paths": ["vendor/l3-transport/scripts/install-transport.sh", "vendor/l3-transport/scripts/review-result-writer.sh", "vendor/l3-transport/handoff/lib/watch-state.sh"], "required_context": ["vendor/l3-transport/scripts/install-transport.sh", "vendor/l3-transport/scripts/review-result-writer.sh", "vendor/l3-transport/handoff/lib/watch-state.sh"]}
  ],
  "sc_refs": ["SC-1", "SC-2", "SC-3", "SC-4", "SC-5", "SC-6", "SC-7", "SC-8", "SC-9", "SC-10"],
  "verify": [
    {"sc_ref": "SC-1", "method": "command", "cmd": "python3 -c \"import ast,sys; src=open('scripts/gd-codex-bridge-review.py').read(); bad=[n for n in ast.walk(ast.parse(src)) if isinstance(n,ast.Return) and isinstance(getattr(n,'value',None),ast.IfExp) and 'APPROVED' in ast.dump(n.value) and 'FAILED' in ast.dump(n.value)]; sys.exit(1 if bad else 0)\""},
    {"sc_ref": "SC-2", "method": "command", "cmd": "printf 'no verdict\\n' | python3 scripts/gd-validate-review-content-evidence.py --target prompts/gd-review-standard.md --review - 2>/dev/null; test $? -eq 1"},
    {"sc_ref": "SC-3", "method": "assertion", "cmd": "python3 -c \"import sys; s=open('scripts/gd-validate-execution-outcome.py').read(); sys.exit(1 if 'so accept it.' in s else 0)\""},
    {"sc_ref": "SC-4", "method": "assertion", "cmd": "python3 -c \"import sys; s=open('scripts/gd-validate-execution-outcome.py').read(); sys.exit(0 if 'if args.plan_files and not errors:' not in s else 1)\""},
    {"sc_ref": "SC-5", "method": "assertion", "cmd": "python3 -c \"import sys; s=open('scripts/gd-validate-execution-outcome.py').read(); sys.exit(0 if 'later value overwrites earlier' not in s else 1)\""},
    {"sc_ref": "SC-6", "method": "assertion", "cmd": "python3 -c \"import sys; s=open('scripts/gd-review-controller.py').read(); blk=s.split('def take_delta_snapshot',1)[1].split(chr(10)+'def ',1)[0]; sys.exit(0 if ('raise' in blk or 'return None' in blk) else 1)\""},
    {"sc_ref": "SC-7", "method": "assertion", "cmd": "python3 -c \"import sys; s=open('vendor/l3-transport/scripts/install-transport.sh').read(); sys.exit(1 if 'launchctl list | grep -q \\\"$_label\\\"' in s else 0)\""},
    {"sc_ref": "SC-8", "method": "assertion", "cmd": "python3 -c \"import sys; s=open('vendor/l3-transport/scripts/review-result-writer.sh').read(); seg=s.split('RESULT_FILE=',1)[1][:400]; sys.exit(0 if ('|| {' in seg or '|| echo' in seg or 'if ! echo' in seg) else 1)\""},
    {"sc_ref": "SC-9", "method": "assertion", "cmd": "python3 -c \"import sys; s=open('vendor/l3-transport/handoff/lib/watch-state.sh').read(); blk=s.split('recent_failed_jobs',1)[1].split(chr(10)+'}',1)[0]; sys.exit(1 if 'in $(ls -r' in blk else 0)\""},
    {"sc_ref": "SC-10", "method": "command", "cmd": "python3 scripts/gd-codex-bridge-review.py --self-test && python3 scripts/gd-review-router.py --self-test && bash tests/gd-l3-regression-v1-fixtures.sh"}
  ]
}
```
<!-- gd-child-plan-proposal-json:end -->
