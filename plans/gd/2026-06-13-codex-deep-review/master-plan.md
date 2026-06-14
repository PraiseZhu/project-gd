# Codex Deep-Review 能力计划 — 让 L2/L3 链路的 Codex CLI 达到 Codex App 审核水平

- 日期：2026-06-13
- 状态：DRAFT（待批准）
- 覆盖链路：L2（/review2，gd-review-controller.py）+ L3（/gd review，gd-review-router.py）
- 覆盖审查对象：审计划（plan）、审代码（code / code_diff）、审结果（execution_outcome / combined）

## 0. Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：（分号分隔）双档位向后兼容（快档零破坏=既有链路不能瘫）; 链路职责分离（L1 讨论 read-only 不接 deep / L2/L3 审查接 deep，deep 只动 ~/.claude writer 不碰 L1 vendor）; deep 档防幻觉（无运行证据不得伪 APPROVED）; 沙箱写权限边界（workspace-write 不得改源/动 git）; 提示词解锁不越界（解 conformance scoping 但不令 Codex 改代码）
- Domain-specific notes：本期改造审查链路的能力档位，不改既有 conformance 快档的判定语义；任何导致快档投递参数变化的改动均为 blocking。

## 1. 背景与问题

2026-06-12 Codex App 对 AKB2 content-quality-loop 执行结果审出 4 条 finding，而同一目标走
GD L3 链路的 Codex CLI 审查 0 命中其中 3.5 条。差距溯源（已逐条验证）不在模型，
而在链路自设的三道锁：

| 锁 | 位置 | 后果 |
|----|------|------|
| 沙箱锁 | `~/.claude/scripts/review-result-writer.sh:93` 写死 `--mode review-only` → `codex-watch:453` 以 `codex exec --sandbox read-only` 启动 | Codex 物理上跑不了 pytest，看不到 golden_replay 的 "1 skipped" |
| 提示词锁 | `scripts/gd-codex-bridge-review.py:1375` conformance scoping，"MUST NOT 把地毯式找 bug 当作职责"；:1082-1090 按 kind 的 scoping 表把 code_diff/combined 都限定为只验 conformance | 语义 bug（代码过自己的测试但逻辑与计划意图相反）零覆盖 |
| 输入锁 | capsule 内容 = 计划 + 自报结果，无"验证声明真伪"的任务定义 | 审查者只核"声明与计划对齐"，不核"声明是否为真" |

已验证的有利条件：

- `codex-watch` 的 `mode_to_sandbox()`（:173-180）**已支持 `workspace-write`** 分支，transport 层现成，只是没有调用方传该 mode。
- L2 与 L3 的 Codex 投递**共用同一条路径**：controller/router → bridge `run-bridge` → writer → `codex-send-wait` → `codex-watch`。改 writer + bridge 一处，两链路同时获得能力。

## 2. 目标

L2/L3 链路中 Codex CLI 对三类审查对象具备 App 级的两种发现机制：

1. **深读推理**：读改动代码，对照计划意图判断逻辑是否相符（抓语义 bug）。
2. **真跑观测**：在 workspace-write 沙箱内真实执行 verify/测试命令，报告
   passed/failed/skipped 计数与解释器版本等运行时事实（抓假 skip、环境不可复现）。

同时保持现有 conformance 快档**完整不变**（向后兼容是硬约束）。

## 3. 非目标

- 不替换 conformance 快档（deep 是新增档位，不是重写）。
- 不让 Codex 修改源文件 / 执行 git 操作（deep 仍是只读代码 + 跑测试）。
- 不解决需要真实外部 API 凭据的 integration 测试执行（这类仍标注 not_run + 原因；
  但 replay 类、被错误标记为 integration 的本地可跑项必须真跑）。
- 不动 AKB2 项目的 4 条 finding 本体（归 AKB2 执行 agent，另一窗口处理）。
- 不写 `/Users/praise/.claude` 之外的 runtime 路径（writer 改动除外，writer 本身在 `~/.claude/scripts/`）。

## 4. 架构决策

**双档位模型**：

```
快档（现状，保持不变）        deep 档（新增）
mode=review-only              mode=workspace-write
sandbox=read-only             sandbox=workspace-write
conformance scoping 提示词    深审提示词（解除 scoping + 要求真跑）
timeout 540/600s              timeout 1200/1500s
每次 /gd review 默认          显式 --deep / release 前触发
```

档位选择权在编排层（gd.md / controller CLI flag），bridge 与 writer 只透传。

**链路职责分离（本次明确为设计边界）**：

```
L1（/review1）讨论链路          L2/L3（/review2·/gd）审查链路
职责：讨论 / 第二意见 / 轻审      职责：审查判决 + deep 真跑/深读
能力：read-only（永不接 deep）    能力：review-only + deep(workspace-write)
writer：vendor（独立，不动）      writer：~/.claude（bridge 运行时，本计划改它）
输出：RECOMMENDATION             输出：VERDICT / GD_REVIEW_DECISION
```

- **deep 是 L2/L3 审查链路专属能力**——L1 纯讨论不需要 workspace-write 跑命令，故 deep 不接 L1。
- 因此两份 writer（L1 vendor / L2-L3 ~/.claude）**服务不同链路、本就该不同**——之前发现的"漂移"在职责分离后从 bug 变成有意分工，不再要求一致（这消解了原 P1 开放决策）。
- CLAUDE.md 记 vendor 是 writer 权威源、设计上"从 vendor 跑不部署"，与 bridge 实跑 ~/.claude 副本是**既存遗留矛盾**；本计划不根治（属 vendor README 待解耦清单），仅在 deep 只动 ~/.claude、不碰 vendor 的前提下推进，不加深也不依赖该矛盾。

## 5. Steps 与成功标准

### Step 0.5 — 前置准备：标准边界例外 + e2e fixture（Step 1 前置）

WHERE：`prompts/gd-review-standard.md` §8.4（允许/禁止调用清单）、`fixtures/deep-review/`（新建只读快照）
WHAT：①在 §8.4 写明本计划对 `review-result-writer.sh` 的一次性受限例外——仅允许新增 `--mode` 与 `--send-timeout` 透传参数（默认值保持现状），禁止改既有投递逻辑；附回滚方式（git revert）与授权出处（本计划批准即授权）。②创建 owned **可执行合成靶** `fixtures/deep-review/synthetic-skip-target/`：含一个故意带无条件 `@pytest.mark.skip(reason="golden_replay placeholder")` 的测试文件 + 对应 outcome JSON（声明该 SC `pass`）+ plan snapshot（verify 命令跑该测试）。deep e2e 跑它**必**产 `skipped=1`，从而可验证 Codex 真跑而非幻觉（合成靶我们掌握确定输出，比 grep forbidden 的 AKB2 文本更强）。SC-2/SC-17 依赖此 fixture。③**改 writer 前**固化 writer 证据链到单一 tracked manifest `fixtures/deep-review/writer-runtime-manifest.json`，字段：`writer_pre_hash`（改前 writer sha256）、`writer_backup_path`（改前 writer 受控备份路径，Step 0.5 产出）、`writer_expected_hash`（Step 1 实现完成后的预期 writer sha256，Step 1 回填）、`captured_at`、`capture_cmd`；并把改前 writer 原样复制为仓内 tracked `fixtures/deep-review/writer-preimage.sh`（manifest 的 provenance 锚点，writer 本体在 `~/.claude` 不被 repo 跟踪）+ 捕获 no-flag 调用 argv/env/stdout 到 `fixtures/deep-review/writer-no-flag-golden.json`。SC-20/SC-21/SC-1/SC-18 全部以此 manifest + preimage 为唯一证据源，不引用不存在的 writer git commit
WHY：§8.4 现明文"禁止修改 review-result-writer.sh"，不先解边界则合规执行器在 Step 1 HALT；SC-2/SC-17 依赖合成靶 fixture、SC-1 依赖 writer golden+preimage，都必须在 Step 1 之前就位（golden 尤其有改前固化的时序硬约束）
VERIFY：见下方 SC-0/SC-19/SC-20 verify 命令

- [ ] SC-0 标准源 §8.4 含 writer 受限例外（授权 `--mode`/`--send-timeout`）且**旧的未限定 writer 禁改条款已改写**——不得「允许例外」与「无条件禁止修改 writer」并存（否则合规执行器仍 HALT）
  - verify (method: command, build-gate): `python3 -c "import re; t=open('prompts/gd-review-standard.md').read(); m=re.search(r'### 8\.4.*?(?=\n### |\Z)', t, re.S); b=m.group(0) if m else ''; assert '例外' in b and '--mode' in b and '--send-timeout' in b, '§8.4 须含授权 --mode/--send-timeout 的受限例外'; import re as r; lines=[l for l in b.splitlines() if ('禁止' in l or '禁' in l) and 'review-result-writer' in l]; assert all('例外' in l or '允许' in l for l in lines), '§8.4 不得残留未限定的 writer 禁改条款'; print('STANDARD_EXCEPTION_OK')"`（旧禁令未改写 / 例外缺失时 fail）
- [ ] SC-19 可执行合成靶就位且自身确实产 skipped=1（SC-2/SC-17 前置依赖；靶子本身可验真）
  - verify (method: command, build-gate): `O=$(python3 -m pytest fixtures/deep-review/synthetic-skip-target/ -q 2>&1); echo "$O" | grep -qE '1 skipped' && ! echo "$O" | grep -qE '[0-9]+ (failed|error)' && test -f fixtures/deep-review/synthetic-skip-target/outcome.json && test -f fixtures/deep-review/synthetic-skip-target/plan-snapshot.md`（断言纯 1 skipped 无 failed/error 夹带）
- [ ] SC-20 manifest 的 `writer_pre_hash` 经仓内 tracked preimage 可证为改前基线（preimage 缺失 / sha256(preimage) ≠ manifest.writer_pre_hash 则失败；以 manifest+preimage 为锚点，不依赖 writer git commit）
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k writer_runtime_manifest -q`（测试逻辑：断言 `fixtures/deep-review/writer-preimage.sh` 存在且 `sha256(preimage)` == manifest.writer_pre_hash；golden.writer_pre_hash 与 manifest 一致；改后重录 → hash 不符 → fail）
- [ ] SC-21 manifest 记录的回滚路径有效：`writer_backup_path` 存在且 hash 匹配 `writer_pre_hash`，改坏可恢复
  - verify (method: command, build-gate): `python3 -c "import json,os,hashlib; m=json.load(open('fixtures/deep-review/writer-runtime-manifest.json')); bp=os.path.expanduser(m['writer_backup_path']); assert os.path.exists(bp), '改前 writer 备份须存在'; assert hashlib.sha256(open(bp,'rb').read()).hexdigest()==m['writer_pre_hash'], '备份 hash 须等于 pre_hash'; print('ROLLBACK_OK')"`

### Step 1 — transport 深审通道（writer + bridge 参数透传）

WHERE：`~/.claude/scripts/review-result-writer.sh`（**L2/L3 bridge 运行时 writer**，bridge WRITER_PATH:78）、`scripts/gd-codex-bridge-review.py`（run-bridge 子命令 + 投递段）

> **writer 架构事实（本会话核实）**：L2/L3 经 bridge 跑 `~/.claude/scripts/review-result-writer.sh`（sha 03dc1d6a）；**L1（/review1）经 review1.md 跑 `vendor/l3-transport/scripts/review-result-writer.sh`（sha 43a1876e，独立文件）**。
> **已决策（见 §4 链路职责分离）**：deep 是 L2/L3 审查链路专属——Step 1 **只改 `~/.claude` writer（L2/L3），vendor writer（L1）完全不动**。L1 是 read-only 讨论链路，永不接 deep。两份服务不同链路，不强求一致（原"漂移开放决策"已消解）。CLAUDE.md 的 vendor-权威遗留矛盾不在本计划根治。
WHAT：①改 writer **前先验** live `~/.claude/scripts/review-result-writer.sh` 的 sha256 == manifest.writer_pre_hash（漂移门禁：Step 0.5 捕获后若 shared writer 被他流程改过则停，防基于过期 preimage 改咽喉）；writer 加 `--mode`/`--send-timeout` 透传参数（默认值=现状），改完把改后 writer sha256 回填 manifest.writer_expected_hash（SC-18 漂移检测据此）；②bridge run-bridge 加 `--deep` flag，置 mode=workspace-write 并放宽 timeout；③deep active path **隔离运行 + pre/post 污染 guard（含隔离副本自身 mutation audit）**——deep `--deep` 调用在 disposable worktree / temp copy 中运行；调用前后对**真实工作树**做全仓快照对比（SC-18）、对**隔离副本**做 source diff 审计：允许 results/ 写入与必要测试缓存，禁止 scripts/commands/tests/fixtures/prompts/schema 等源路径和 git 状态变化；隔离副本中的源改动同样 → mapped result=`FAILED`，防止 Codex 在隔离副本改源后自验自批；若检测到任何污染 → 恢复工作树到 before snapshot
WHY：现状 writer:93 写死 `--mode review-only` → codex-watch 以 read-only 沙箱启动，Codex 物理上跑不了测试；不开 workspace-write 通道深审无从观测；但 workspace-write 有写权限，安全边界必须在每次 active 调用强制 fail-closed，否则 Step 4/5 接入后真实 deep review 可污染源/git
VERIFY：见下方 SC-1/SC-23/SC-2 verify 命令

改动文件：`~/.claude/scripts/review-result-writer.sh`、`scripts/gd-codex-bridge-review.py`

- writer 新增 `--mode <review-only|workspace-write>` 参数，默认 `review-only`（不传 = 现状，
  全部既有调用方零感知）；:93 行改为透传 `$MODE`。
- writer 新增 `--send-timeout <sec>` 透传为 `CODEX_SEND_WAIT_TIMEOUT` 环境变量。
- bridge `run-bridge` 新增 `--deep` flag：置 mode=workspace-write、writer_timeout_sec 600→1500、
  send timeout 540→1200。
- vendor writer（L1 讨论链路专用）**完全不动**——deep 是 L2/L3 专属，L1 read-only 不需要。
- `codex-watch` 无需改动（mode_to_sandbox 已支持），仅验证。

- [ ] SC-22 改 writer 前 live writer hash 未漂移：live writer sha256 == manifest.writer_pre_hash（不符则停，防基于过期 preimage 改咽喉）
  - verify (method: command, build-gate): `python3 -c "import json,os,hashlib; m=json.load(open('fixtures/deep-review/writer-runtime-manifest.json')); w=os.path.expanduser('~/.claude/scripts/review-result-writer.sh'); h=hashlib.sha256(open(w,'rb').read()).hexdigest(); assert h==m['writer_pre_hash'], f'live writer 已漂移: {h} != {m[\"writer_pre_hash\"]}'; print('NO_DRIFT')"`（仅在 Step 1 改 writer 前运行；漂移即 fail，要求重捕 manifest）
- [ ] SC-1 writer 默认行为不变：不传 `--mode` 时投递给 codex-send-wait 的 argv/env/关键 stdout 与改动前逐字节一致
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k writer_no_flag_golden -q`（fixture：改前捕获 no-flag writer 调用 codex-send-wait 的 mode/timeout/baseline 路径/result 路径为 golden，改后逐字节 diff；`bash -n` 仅作辅助语法门）
- [ ] SC-23 deep active path 隔离 + 污染 fail-closed（含隔离副本自身 mutation audit）：模拟 deep 子进程写任意非 results 路径，①真实工作树 before/after 快照一致；②隔离副本内 scripts/commands/tests/fixtures 被改 → 同样 mapped result==FAILED（防自改源后自验自批）
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k deep_active_path_pollution_guard -q`（fixture 两类：A-真实树污染：stub 写 scripts/根目录，断言真实树 before==after + mapped FAILED；B-隔离副本污染：stub 在 temp copy 里改 scripts/，断言 audit 发现改动 + mapped FAILED；仅 results/ 输出时正常返回）
- [ ] SC-2 deep 通道打通：经 router 发起（G1 sentinel 已满足）的 `--deep` 投递，在 codex-watch **同一行** Completed 日志中同时出现该 run 的 job_id 与 `sandbox=workspace-write`
  - verify (method: command, integration): 先 `RID="deeptest-$(date +%s)"; GD_REVIEW_ROUTER_INVOCATION_ID="$RID" python3 scripts/gd-codex-bridge-review.py run-bridge --kind execution_outcome --deep --queue-job-id "$RID" --target fixtures/deep-review/synthetic-skip-target/outcome.json --cwd "$(git rev-parse --show-toplevel)" --out /tmp/$RID.json --live-transport`（显式设 GD_REVIEW_ROUTER_INVOCATION_ID=run_id，满足 G1 sentinel 要求，防 DIRECT_BRIDGE_FORBIDDEN_FOR_EXECUTION_KIND）；再 `grep "$RID" ~/.claude/handoff/logs/codex-watch.log | grep 'Completed' | grep -q 'sandbox=workspace-write'`（同一行含 Completed + job_id + sandbox=workspace-write；人为回退 review-only 时必失败）
- [ ] SC-30 G1 sentinel fail-closed（负向证明）：无 router invocation env 直调 bridge 仍被 DIRECT_BRIDGE_FORBIDDEN_FOR_EXECUTION_KIND 拦截、非绕过
  - verify (method: command, build-gate): `unset GD_REVIEW_ROUTER_INVOCATION_ID; python3 scripts/gd-codex-bridge-review.py run-bridge --kind execution_outcome --deep --target fixtures/deep-review/synthetic-skip-target/outcome.json --cwd "$(git rev-parse --show-toplevel)" --out /tmp/sc30-test.json --live-transport 2>&1 | grep -q DIRECT_BRIDGE_FORBIDDEN_FOR_EXECUTION_KIND`（必须被拦截；若通过则 deep 绕过了 G1 安全边界）
- [ ] SC-27 L1（/review1）讨论链路独立、不受 deep 改动影响：L1 用 vendor writer，Step 1 全程不碰它（vendor writer git 无 diff），L1 smoke 仍绿，review1.md 仍 read-only（discuss / review-only，无 workspace-write/deep）
  - verify (method: command, build-gate): `bash tests/gd-l1-combined-bundle-smoke.sh && git diff --exit-code HEAD -- vendor/l3-transport/scripts/review-result-writer.sh && grep -qE -- '--mode (review-only|discuss)' commands/review1.md && ! grep -qE 'workspace-write|--deep' commands/review1.md`（L1 smoke 绿 + vendor writer 零改动 + review1 保持 read-only 不含 deep；任一破坏即 fail）
- [ ] SC-29 deep timeout 透传：`--deep` 时 bridge→writer→codex-send-wait 的等待上限为 1200/1500s（非旧 540/600），默认无 flag 仍为旧值（防长验证被旧超时截断）
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k writer_deep_timeout_golden -q`（fixture：stub codex-send-wait 捕获 argv/env，deep 路径断言 CODEX_SEND_WAIT_TIMEOUT/writer_timeout 为 1200/1500，default 路径断言仍 540/600；漏传 timeout 即 fail）

### Step 2 — deep capsule 模板（三类审查对象各一套深审指令）

WHERE：`scripts/gd-codex-bridge-review.py` 模板区（:271 emphasis、:1362-1380 提示词构建段）、`scripts/gd_review_contract.py` 枚举
WHAT：新增 deep 档提示词模板，按 review_kind 分 plan/code/outcome 三套；conformance 模板一字不动
WHY：现状 :1375 conformance scoping 明文禁止深读找 bug，语义 bug（计数反向、fail-closed 缺失）零覆盖
VERIFY：见下方 SC-3/SC-4/SC-5 verify 命令

改动文件：`scripts/gd-codex-bridge-review.py`（模板区）、可能新增 `scripts/gd_review_contract.py` 枚举

- 新增 deep 档提示词模板，按 review_kind 区分：
  - **plan**（审计划）：架构合理性、风险完备性、接口/契约设计、SC 可验证性与覆盖盲区
    ——不再局限于 verify 命令可执行性这一个模式。
  - **code / code_diff**（审代码）：深读全部改动文件 + 周边上下文，对照计划 SC 与意图
    判断逻辑正确性；明确允许并要求找语义 bug（计数方向、fail-closed 缺失、边界条件）。
  - **execution_outcome / combined**（审结果）：对计划中每条 SC verify 命令真实执行，
    输出 `cmd / exit / passed / failed / skipped` 五元组；`skipped > 0` 时必须打开对应
    测试文件查明 skip 原因并判定是否构成假验收；报告实际解释器版本与计划要求的差异。
- deep 模板保留既有硬约束：SC-ID 行格式、一次列全 findings、禁止修改源文件/git 操作。
- conformance 模板一字不动。

- [ ] SC-3 deep plan 模板含架构/风险/接口三维度指令且无 conformance scoping 句（专用断言，删任一维度或加 scoping 句时测试失败）
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k deep_plan_template -q`（fixture：build_capsule_text 产 deep plan capsule 后断言含「架构」/「风险」/「接口」三维度关键词；断言不含「MUST NOT 把地毯式找 bug 当作职责」等 conformance scoping 句；缺任一维度或有 scoping 句时测试 fail）
- [ ] SC-4 deep outcome 模板含「真跑 + 五元组 + skipped 必查因」指令（断言模板内容，非 import 占位）
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k deep_outcome_template -q`（fixture：build_capsule_text 产 deep outcome capsule 后 assert 含 `cmd`/`exit`/`passed`/`failed`/`skipped` 五元组关键词 + skip 原因检查指令；删任一关键词测试失败）
- [ ] SC-5 conformance 模板回归：既有 fixtures（review-bridge / codex-bridge-v2）全部通过
  - verify (method: command, build-gate): `python3 scripts/gd-codex-bridge-review.py self-test`

### Step 3 — parser 兼容 deep 输出形态

WHERE：`schema/gd-review-result-v2.schema.json`、`scripts/gd-codex-bridge-review.py`（parse-transport + _validate_v2 + v2 标题检查 :826-834 + `run-bridge`/`build-capsule` 新增 `--plan-file` @:2324-2339）、`fixtures/codex-bridge-v2/` 新增 deep 样例
WHAT：①**修 mapped v2 标题 parser bug**（已知缺陷，本会话 19 轮 review 全程 degraded 的根因）——parse-transport 在 :826-834 硬查 `# {TITLE} (v2)` 精确标题，但 Codex(gpt-5.4) 实际输出无 `(v2)` 后缀的 `# Plan Review Result`，导致 findings 全丢、mapped 判 degraded；改为**容忍标题变体**：v2 路径接受带或不带 `(v2)` 后缀两种形态（不依赖模型吐精确 magic 字符串）。此修复是 deep plan/code 的前置——deep 输出同走 v2 parse，不修则 deep findings 同样被丢。②扩 schema——为 deep kind 定义 `run_evidence` 字段结构（数组：cmd/exit/passed/failed/skipped/skip_reason/**interpreter_version**），保持 `additionalProperties: false` 不变（新字段显式入 schema 而非放开约束）；`interpreter_version` 必填，供判断"声明的 verify 命令在本环境能否复现"类问题；③parse-transport 为 deep kind 走独立分支识别证据，**按 kind 区分证据模型**：execution_outcome/combined deep 强制 `run_evidence`（缺 → DEEP_EVIDENCE_MISSING fail-closed）；plan/code deep **不**产 run_evidence（不跑测试），其证据是深读 findings（缺深读 findings 段 → DEEP_FINDINGS_MISSING fail-closed），run_evidence 对 plan/code 为可选/不适用；④**bridge `run-bridge`/`build-capsule` 新增 `--plan-file` 参数**（当前 :2324-2339 无此参数）——deep outcome/combined capsule 必须包含 `PLAN_FILE_PATH`、plan hash、从计划 markdown 提取的 SC verify 命令（或注入"强制 Read plan snapshot"指令），确保 Codex 复核的是计划 SC verify 而非只依赖 outcome 自报的 `verify_results[].cmd`（:1338-1348）
WHY：现 schema `additionalProperties: false` 且无运行证据字段（schema:6,25-111），不扩 schema 则 deep 正样例会 schema fail 或证据被丢弃；v2 标题硬查 bug 不修则所有 v2 plan/code_diff（含 deep）的 findings 被静默丢弃，deep 成功与否不可判；bridge 无 `--plan-file` 则 capsule 只注入 outcome 自报命令，Codex 无法核对计划 SC verify 的真实性（outcome 漏写或篡改 verify_results 时仍可能无法发现）
VERIFY：见下方 SC-6/SC-7/SC-8/SC-26 verify 命令

改动文件：`schema/gd-review-result-v2.schema.json`、`scripts/gd-codex-bridge-review.py`（parse-transport + _validate_v2）、`fixtures/` 新增 deep 样例

- deep 输出在 findings 之外新增「运行证据」段（结构化：command/exit/counts）；
  parse-transport 为 deep kind 走独立解析分支，**不**往现有 SHALLOW_REVIEW_APPROVED /
  v1-compat 逻辑上打补丁。
- 运行证据缺失（deep 档下 Codex 没真跑就给结论）→ mapped 判 `DEEP_EVIDENCE_MISSING`，
  fail-closed，不得静默降级为快档语义。
- 新增 deep 正/反样例 fixtures（含：有证据通过、无证据 fail-closed、skipped>0 有解释、
  skipped>0 无解释判 P1）。

- [ ] SC-6 三类 deep 正样例均通过 schema：outcome/combined deep 含 `run_evidence`，plan/code deep 含深读 findings（按 kind 区分证据模型，缺对应 kind 证据时各自 fail-closed）
  - verify (method: command, build-gate): `python3 -c "import json,jsonschema; s=json.load(open('schema/gd-review-result-v2.schema.json')); mo=json.load(open('fixtures/codex-bridge-v2/deep-outcome-pass.mapped.json')); jsonschema.validate(mo,s); assert mo.get('run_evidence'); mp=json.load(open('fixtures/codex-bridge-v2/deep-plan-pass.mapped.json')); jsonschema.validate(mp,s); mc=json.load(open('fixtures/codex-bridge-v2/deep-code-pass.mapped.json')); jsonschema.validate(mc,s); assert mp.get('findings') is not None and mc.get('findings') is not None; print('SCHEMA_OK_3KINDS')"`
- [ ] SC-7 fail-closed 负例完备：①execution_outcome/combined deep 缺 `run_evidence` → `DEEP_EVIDENCE_MISSING`；②plan/code deep 缺深读 findings 段 → `DEEP_FINDINGS_MISSING`（两类各有负向 fixture 验证）
  - verify (method: command, build-gate): `python3 scripts/gd-codex-bridge-review.py self-test && python3 -m pytest tests/ -k 'deep_findings_missing' -q`（SC-7 扩展：plan/code deep raw 无 findings 时断言 parse-transport 输出 DEEP_FINDINGS_MISSING；SC-7 原有 execution outcome 负例保持在 self-test）
- [ ] SC-8 全部既有 v1/v2 fixtures 回归通过（快档零破坏）
  - verify (method: command, build-gate): `python3 scripts/gd-codex-bridge-review.py self-test && bash tests/gd-l3-regression-v1-fixtures.sh`
- [ ] SC-26 mapped v2 标题容忍：Codex 输出**无 `(v2)` 后缀**的 `# Plan Review Result` 时 parse-transport 仍提取 findings（不再 degraded），且带 `(v2)` 后缀的旧形态仍通过（双向兼容，修本会话 19 轮 degraded 根因）
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k v2_title_tolerance -q`（fixture：两个 raw 样例——`# Plan Review Result`（无后缀）与 `# Plan Review Result (v2)`（有后缀），均断言 parse-transport 提取出非空 findings 且 review_run_status != degraded；标题完全缺失时仍 degraded）
- [ ] SC-33 deep outcome capsule 含 plan-derived verify 命令（非仅 outcome 自报）：`build-capsule` 接收 `--plan-file` 后，生成的 deep outcome capsule 包含 `PLAN_FILE_PATH`、plan hash、从计划提取的 SC verify 命令列表；`/gd review --deep` 生产入口 smoke 证明 capsule 含 plan 来源字段而非仅 outcome `verify_results`
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k deep_capsule_plan_file -q`（fixture：build_capsule_text 传 --plan-file 后断言输出 capsule 含 PLAN_FILE_PATH + plan hash + 至少一条 plan-derived SC verify 命令；不传 --plan-file 时 deep outcome capsule 仍 fail-closed 或明确标注 PLAN_FILE_MISSING）

### Step 4 — L3 编排接入（gd.md + router）

WHERE：`commands/gd.md`（review 段）、`scripts/gd-review-router.py`（argparse + bridge 调用透传点，现仅 `--mode/--target/--output-dir`，见 :1620-1640）
WHAT：router 新增 SC-17/SC-25 所需的完整 CLI 形态——`review execution` **与** `review code`（含 code_diff）两个子命令，各支持 `--deep` + `--plan-file` + `--out`（单文件输出）参数；`--deep` 透传至 bridge run-bridge（execution→execution_outcome kind，code→code_diff kind）；无 `--deep` 行为逐字节不变；gd.md 补双档位文档（含 `review code --deep`）；SC-9 self-test 覆盖两个子命令调用形态。**补 deep-aware 外层 timeout**：router `review execution/code --deep` 路径的 bridge subprocess timeout 须 > writer deep timeout（1500s）；当前 router 外层默认 360s（:1637-1640），deep 路径须升到 ≥1800s，避免外层先杀 bridge
WHY：deep 档建好后若无编排入口则永不可达；SC-17 依赖 `review execution --deep`、SC-25 依赖 `review code --deep`；当前 router 外层 360s < bridge deep timeout 1500s，会先 kill bridge 导致 deep 永不能完成真跑；L2/L3 都补才能真正达到 App 级能力
VERIFY：见下方 SC-9/SC-10 verify 命令

改动文件：`commands/gd.md`、`scripts/gd-review-router.py`

- `/gd review <target> --deep`：router 透传 `--deep` 至 bridge run-bridge。
- 默认（无 --deep）行为与现状逐字节一致。
- gd.md 文档：双档位语义说明、何时用 deep（release 前 / 执行结果存疑 / 用户显式要求）、
  成本提示（5-20 分钟 + 大 token）。
- G1 sentinel（DIRECT_BRIDGE_FORBIDDEN）对 deep 档同样生效。

- [ ] SC-9 `--deep` 端到端：router 的 `review execution` 与 `review code` 子命令均暴露 `--deep --plan-file --out` 并透传至 bridge（对应 execution_outcome / code_diff kind）；无 --deep 时参数与现状一致
  - verify (method: command, build-gate): `for SUB in execution code; do python3 scripts/gd-review-router.py review $SUB --help 2>&1 | grep -q -- '--deep' && python3 scripts/gd-review-router.py review $SUB --help 2>&1 | grep -q -- '--plan-file' && python3 scripts/gd-review-router.py review $SUB --help 2>&1 | grep -q -- '--out' || exit 1; done; python3 scripts/gd-review-router.py --self-test`
- [ ] SC-10 gd.md 双档位文档与实际 CLI 参数一致（防虚标，对照 rev20 教训）：文档声明的 `--deep` flag 必须真实存在于 router 的 `review execution` 子命令（与 SC-9 同口径，非顶层 help）
  - verify (method: command, build-gate): `python3 scripts/gd-review-router.py review execution --help 2>&1 | grep -q -- '--deep' && grep -q -- '--deep' commands/gd.md`（双向：子命令 CLI 有该 flag 且文档提及；防文档写了 CLI 没有）
- [ ] SC-31 L3 router deep 外层 timeout 不先杀 bridge：stub bridge sleep > 420s 但 < 1800s 时，router `review execution --deep` 不 timeout（default 无 --deep 仍保持旧值 360s）
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k 'router and deep_timeout' -q`（fixture：stub bridge sleep=500s，deep 路径断言 subprocess timeout ≥ 1800s 不被杀；default 路径断言 timeout ≈ 360s 不变）

### Step 5 — L2 编排接入（controller）

WHERE：`scripts/gd-review-controller.py`（Round 1 dispatch 段）、`commands/review2.md`
WHAT：controller 加 `--deep` flag，Round 1 codex_A/B 改用 deep capsule；deep 档 tests-status 由运行证据推导；**补 deep-aware 外层 timeout**：controller `_invoke_bridge_mapped` 的 bridge subprocess timeout 须 > writer deep timeout（1500s），deep 路径升到 ≥1800s（当前 controller 外层固定 420s @:336-338，会先杀 bridge）；controller CLI 新增 `--queue-job-id` 参数，SC-28 的同一 run sandbox 证明依赖此参数透传；**controller CLI 同步新增 `--plan-file` 参数**（对齐 Step 4 router 的 `--plan-file`）：`--deep` 时传给 bridge run-bridge，确保 L2 deep outcome capsule 同样携带 plan-derived verify 命令（不传则 L2 deep 用 outcome 自报命令，P2 问题3 的修复不完整）
WHY：controller 外层 420s < bridge deep timeout 1500s，不补则 deep e2e（SC-28）永不完成；SC-28 verify 命令已用 `--queue-job-id "$RID"` 追踪同一 run，controller 若无此参数透传则 run_id 无法关联到 codex-watch 日志
VERIFY：见下方 SC-11/SC-12 verify 命令

改动文件：`scripts/gd-review-controller.py`、`commands/review2.md`

- controller 新增 `--deep` CLI flag：Round 1 codex_A/codex_B 双 lens 投递改用 deep capsule
  （沿用双 emphasis 并集去重原语，不改三方去重逻辑）。
- combined 分支（Branch C）的 execution-result 复审在 deep 模式下用 deep outcome 模板。
- deep 档下 `--tests-status` 不再接受调用方自报：由 deep 运行证据推导
  （快档维持 caller_supplied + 既有 WARNING，不回退）。

- [ ] SC-11 controller `--deep` 时 bridge 调用带 deep flag；无 flag 行为不变
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k controller -q`
- [ ] SC-12 deep 档 tests-status 来源为运行证据：caller 自报 green 与 deep evidence 冲突时，最终状态取 deep evidence
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k 'controller and deep_evidence' -q`（fixture：构造 caller-supplied green 但 deep evidence red 的输入，断言输出 `TESTS_STATUS_SOURCE: deep_evidence` 且最终 tests-status=red）
- [ ] SC-32 L2 controller deep 外层 timeout 不先杀 bridge，且 `--queue-job-id` 与 `--plan-file` 均透传至 bridge
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k 'controller and deep_timeout' -q`（fixture：stub bridge sleep=500s，controller --deep 路径断言 _invoke_bridge_mapped timeout ≥ 1800s 不被杀 + `--queue-job-id` 和 `--plan-file` 均出现在 bridge 调用 argv；default 路径断言 timeout ≈ 420s 不变）

### Step 6 — 确定性档位（option-A Phase 2）补洞（可与 Step 1-3,5 并行；对 `commands/gd.md` 的改动 blocked_by Step 4，避免与 Step 4 同文件冲突——gd.md 单一 owner 串行）

WHERE：`scripts/gd-validate-execution-outcome.py`（_substitute_python、verify-rerun 段）、`commands/gd.md`（execute 段）
WHAT：plan_ref 执行合约 + 修 `/usr/bin/env python3` 替换 bug + build-gate rerun 解析 pytest skipped 计数
WHY：Phase 2 现因 outcome 缺 plan_ref 永不激活；env python3 替换产非法命令；--collect-only 对假 skip 照样 exit 0
VERIFY：见下方 SC-13/SC-14/SC-15 verify 命令

改动文件：`scripts/gd-validate-execution-outcome.py`、`commands/gd.md`（execute 段）

- 6a `plan_ref` 执行合约：gd.md execute 段强制要求 outcome JSON 写 `plan_ref` 字段
  （指向 master-plan 路径），缺失时 router 打印激活提示（不 fail，渐进迁移）。
- 6b `_substitute_python` 修 `/usr/bin/env python3` 形态：替换后不得产生
  `/usr/bin/env /path/to/python3.13` 非法命令；env 前缀整体替换为锁定解释器。
- 6c build-gate rerun 解析 pytest 输出的 `N skipped` 计数：声明 pass 且 skipped>0 →
  WARNING（带测试名）；`--collect-only` 命令明确标注「不构成执行证据」。

- [ ] SC-13 `/usr/bin/env python3 -m X` 替换后为合法可执行命令
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k substitute -q`
- [ ] SC-14 skipped>0 + 声明 pass → stderr 出现 SKIP_UNDER_PASS 警告
  - verify (method: command, build-gate): `python3 -m pytest tests/ -k skip_under_pass -q`
- [ ] SC-15 gd.md execute 段（非全文任意位置）含 plan_ref 合约条目
  - verify (method: command, build-gate): `awk '/^#+.*execute/{f=1} f&&/plan_ref/{print; found=1} /^#+ /&&f&&!/execute/{if(NR>1)f=0} END{exit !found}' commands/gd.md`（限定在 execute 段内出现 plan_ref，防全文别处命中误判）

### Step 6.5 — 实现提交 checkpoint（Step 7 e2e 前置）

WHERE：git（Steps 1-6 的全部实现改动）
WHAT：Steps 1-6 实现完成且各自 SC 通过后，commit 这批改动（走 commit-projects），使 `scripts/commands/tests/fixtures` 工作树相对 HEAD 干净
WHY：SC-18 的 before 断言要求 e2e 前工作树已 clean（证明 baseline 是已提交态）；不设此 checkpoint 则 Step 7 跑 SC-18 必报 IMPL_NOT_COMMITTED，deep e2e 无法运行
VERIFY：见下方 SC-24 verify 命令

- [ ] SC-24 Steps 1-6 实现已提交（含 prompts 标准源 + 本计划目录），e2e 前工作树 clean（vendor writer 不在范围——本计划不改它）
  - verify (method: command, build-gate): `git diff --exit-code HEAD -- scripts commands tests fixtures schema prompts plans/gd/2026-06-13-codex-deep-review && test -z "$(git status --porcelain -- scripts commands tests fixtures schema prompts && git status --porcelain -- plans/gd/2026-06-13-codex-deep-review | grep -v '/results/')"`

### Step 7 — 安全边界 + 全链路回归（最终 gate）

WHERE：`scripts/gd-codex-bridge-review.py`（deep 提示词安全条款）、`tests/`、`plans/gd/2026-06-13-codex-deep-review/results/`
WHAT：①deep 提示词加安全条款（只读+跑测试、禁改源/git/网络）；②全链路回归绿；③**两类机制各一个 e2e 实证**：真跑观测——对 synthetic-skip-target 跑 deep e2e 须阻断假 skip（SC-17）；深读推理——新增 owned `fixtures/deep-review/synthetic-semantic-bug/`（plan snapshot + 明显反向逻辑的 code/diff，代码通过自己的测试但逻辑与计划意图相反），deep code/code_diff 审查须产非批准结果 + finding 指向语义不一致（SC-25）
WHY：workspace-write 沙箱有写权限，无提示词约束 + git status 验证则可能误改工作树；不实证则"获得 App 能力"只是口头声明
VERIFY：见下方 SC-16/SC-17/SC-18 verify 命令

- deep 提示词安全条款：只读源码 + 跑测试；禁止写源文件、git 操作、网络外联
  （workspace-write 沙箱 + 提示词双保险）。
- 全链路回归：9 项 smoke、`python3 -m pytest tests/`、router self-test、bridge self-test、
  L2 controller 测试，全部绿。
- 端到端实测一次：用 Step 0.5 的 owned 可执行合成靶（synthetic-skip-target）跑 `/gd review execution --deep`，
  验收 deep 档能报出 golden_replay skipped 事实（App 级能力的实证）。

- [ ] SC-16 全部回归绿
  - verify (method: command, build-gate): `python3 -m pytest tests/ -q && python3 scripts/gd-review-router.py --self-test && python3 scripts/gd-codex-bridge-review.py self-test`
- [ ] SC-17 端到端实证：对 owned 合成靶（声明 pass 但测试无条件 skip）新跑 deep e2e，不仅**报出** skipped==1，还**阻断**——最终 `gd_review_decision != APPROVED` 且 findings 含指向 skipped-under-pass 冲突的条目（证明真"抓假 skip"，非仅观测）
  - verify (method: command, execution-gate): `R=plans/gd/2026-06-13-codex-deep-review/results/e2e-deep-evidence.json; rm -f "$R"; python3 scripts/gd-review-router.py review execution --deep --target fixtures/deep-review/synthetic-skip-target/outcome.json --plan-file fixtures/deep-review/synthetic-skip-target/plan-snapshot.md --out "$R"; python3 -c "import json; d=json.load(open('$R')); ev=d.get('run_evidence',[]); assert any(e.get('skipped')==1 and 'cmd' in e and 'exit' in e for e in ev), 'deep e2e 须报 skipped==1 + 五元组'; assert any(e.get('interpreter_version') for e in ev), '每条运行证据须含 interpreter_version（解释器版本，环境不可复现类问题可判）'; assert d.get('gd_review_decision')!='APPROVED', '声明 pass 但实跑 skipped 必须阻断（非 APPROVED）'; assert any('skip' in json.dumps(f).lower() for f in d.get('findings',[])), 'findings 须含 skipped-under-pass 冲突'; print('FAKE_SKIP_CAUGHT')"`
- [ ] SC-25 深读推理 e2e 实证：对 owned `fixtures/deep-review/synthetic-semantic-bug/`（代码过自己的测试但逻辑与计划意图反向）跑 deep code/code_diff 审查，须产非批准结果 + finding 指向语义不一致（证明"深读推理"机制，与 SC-17 的"真跑观测"互补）
  - verify (method: command, execution-gate): `R=plans/gd/2026-06-13-codex-deep-review/results/e2e-deep-semantic.json; rm -f "$R"; python3 scripts/gd-review-router.py review code --deep --target fixtures/deep-review/synthetic-semantic-bug/ --plan-file fixtures/deep-review/synthetic-semantic-bug/plan-snapshot.md --out "$R"; python3 -c "import json; d=json.load(open('$R')); assert d.get('gd_review_decision')!='APPROVED', '反向逻辑须被深读阻断'; assert any(('语义' in json.dumps(f) or 'semantic' in json.dumps(f).lower() or 'logic' in json.dumps(f).lower() or 'intent' in json.dumps(f).lower()) for f in d.get('findings',[])), 'finding 须指向语义/逻辑不一致'; print('SEMANTIC_BUG_CAUGHT')"`
- [ ] SC-28 L2 deep 端到端实证（与 SC-17 的 L3 e2e 对称，拉平 L2 验证强度）：走 L2 controller `--deep` 入口对 synthetic-skip-target 跑，须报 run_evidence.skipped==1、`TESTS_STATUS_SOURCE: deep_evidence`、最终非 APPROVED，且同一 run 证明 sandbox=workspace-write
  - verify (method: command, execution-gate): `R=plans/gd/2026-06-13-codex-deep-review/results/e2e-l2-deep; rm -rf "$R"; RID="l2deep-$(date +%s)"; python3 scripts/gd-review-controller.py --branch execution-only --deep --queue-job-id "$RID" --plan-file fixtures/deep-review/synthetic-skip-target/plan-snapshot.md --cwd "$(git rev-parse --show-toplevel)" --output-dir "$R" --execution-result fixtures/deep-review/synthetic-skip-target/outcome.json; python3 -c "import json,glob; f=glob.glob('$R/*.json'); d=json.load(open(f[0])); assert any(e.get('skipped')==1 for e in d.get('run_evidence',[])), 'L2 deep 须报 skipped==1'; assert d.get('gd_review_decision')!='APPROVED', 'L2 deep 须阻断假 skip'; assert d.get('tests_status_source')=='deep_evidence' or 'TESTS_STATUS_SOURCE: deep_evidence' in json.dumps(d), 'tests-status 须来自 deep_evidence 非 caller 自报'; assert d.get('plan_file_path') or 'PLAN_FILE_PATH' in json.dumps(d), 'L2 deep capsule 须含 PLAN_FILE_PATH（plan-derived verify）'; print('L2_DEEP_FIELDS_OK')"; grep "$RID" ~/.claude/handoff/logs/codex-watch.log | grep 'Completed' | grep -q 'sandbox=workspace-write'`（四断言：skipped==1 + 非 APPROVED + TESTS_STATUS_SOURCE + PLAN_FILE_PATH，加 sandbox=workspace-write；缺任一即 fail。--plan-file 传给 controller → bridge，L2 capsule 携带 plan-derived verify）
- [ ] SC-18 deep e2e 不污染**全仓任何路径**（不限受保护目录）**且 writer runtime 处于预期态**：before/after 用全仓 `git status --porcelain` + `git diff --exit-code HEAD` 快照，仅 allow-list `plans/gd/2026-06-13-codex-deep-review/results/` 输出路径——写 docs/、根目录或任何其他 tracked/untracked 路径均抓；同时断言 writer 当前 hash 等于预期实现 hash + Step 0.5 备份/pre-hash 仍在（~/.claude writer 是 L2/L3 共用运行时咽喉）
  - verify (method: command, execution-gate): `bash tests/gd-deep-e2e-tree-guard.sh`（脚本内 before/after 均跑**全仓** `git diff --exit-code HEAD` + `git status --porcelain`，唯一 allow-list 为 `plans/gd/2026-06-13-codex-deep-review/results/`；并断言 `sha256(~/.claude/scripts/review-result-writer.sh)` == `writer-runtime-manifest.json` 的 `writer_expected_hash` 且 manifest.writer_backup_path 存在；写 docs/根目录/任意未列路径、writer hash 漂移、备份丢失均必失败）

## 6. 边界

- owned_paths：`projects/Project GD/scripts/**`、`projects/Project GD/commands/**`、
  `projects/Project GD/fixtures/**`、`projects/Project GD/tests/**`、
  `projects/Project GD/prompts/gd-review-standard.md`（Step 0.5 标准例外）、
  `projects/Project GD/schema/gd-review-result-v2.schema.json`（Step 3 run_evidence 字段）、
  `projects/Project GD/plans/gd/2026-06-13-codex-deep-review/**`、
  `~/.claude/scripts/review-result-writer.sh`（Step 1 唯一 runtime 例外，L2/L3 链路）
- forbidden_paths：`projects/Project AKB2/**`（另一窗口在执行）、`~/.claude/handoff/bin/**`
  （codex-watch 无需改，禁动）、`projects/Project GD/vendor/l3-transport/scripts/review-result-writer.sh`
  （L1 讨论链路专用 writer，deep 不接 L1，**禁动**）、其他项目
- hard_stop：任一既有 fixture 回归失败且 30 分钟内无法定位 → 停；writer 改动导致
  快档投递参数变化 → 立即回滚 writer 并停。

## 7. 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| workspace-write 下 Codex 意外改动工作树 | P1 | 沙箱限工作区内写 + 提示词禁改源文件 + Step 7 端到端后 `git status` 必须 clean |
| deep 档超时率高（integration 测试慢） | P2 | timeout 1200/1500s + deep 档明确非默认、按需触发 |
| ~/.claude writer 是 L2/L3 共用运行时咽喉，改坏 L2/L3 瘫 | P1 | `--mode` 默认值兜底 + SC-1 逐字节对比 + SC-22 漂移门禁 + SC-21 改前备份 |
| L1 讨论链路用独立 vendor writer，deep 只动 ~/.claude，不触 L1 | P2 | 链路职责分离（§4）；SC-27 验 L1 smoke 绿 + vendor writer 零 diff + review1 保持 read-only |
| CLAUDE.md vendor-权威遗留（bridge 实跑 ~/.claude 副本，非 vendor） | P3 | 既存矛盾，本计划不根治、不依赖；deep 只改 ~/.claude，vendor 不动；根治属 vendor README 待解耦清单（独立工作） |
| Codex 在 deep 档幻觉"已运行"未运行 | P1 | SC-7 运行证据缺失 fail-closed（DEEP_EVIDENCE_MISSING） |

## 8. 与既有未完成工作的关系

本计划开工前的基线状态（2026-06-13 更新）：option-A 4 个文件已 commit `a091962` 并 push 到 origin/main。当前 GD 工作树**只有本计划目录是未跟踪（untracked）**，无其他未提交改动。开工前须先 commit 本计划目录，在干净基线上开 deep-review 分支。
