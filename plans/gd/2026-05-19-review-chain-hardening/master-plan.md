# Review Chain Hardening v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-master-plan

日期：2026-05-19
状态：draft
负责人：Claude 执行；Codex 可选 cross-review
COMMAND_CWD: Project GD/.claude/worktrees/swirling-tickling-flask

---

## 1. 目标链

```text
PROJECT_GOAL: 在 Claude Code 中建设 /gd Goal-Driven 多 Agent 主链路，提升复杂任务的计划、审查、执行、验收效率，并通过 Codex 作为 cross-review sidecar 降低填表式计划与执行遗漏风险。
CHAIN_GOAL:   用 shared core 固定目标链、SC、任务包、review contract 和 anti-fill 标准，保证后续 /gd command、multi-agent dispatch、execution review、Codex cross-review 都引用同一套契约。
PHASE_GOAL:   关闭 /gd review chain 两个 root cause —— (1) plan review capsule 过重导致 transport_failed 在 12 轮 Sentinel 卡顿；(2) execution review 缺传递性 Read 强制导致 "信 JSON 字面值" 形式化审。本批次落地后 /gd review 在 plan + execution_outcome + code_diff + combined 四个 kind 上均有 fail-closed 的内容真实性护栏。
```

---

## 2. Review 对齐

- **REVIEW_DOMAIN**: `ai_infra`
- **REVIEW_FOCUS**: capsule_size_reduction; codex_traversal_read_enforcement; content_evidence_validation; production_path_integration
- **Domain-specific notes**:
  - 本计划是对 `/gd review` 链路自身的 meta 升级；所有改动局限 `Project GD/scripts/` + `Project GD/templates/`，不动外部业务项目。
  - 已完成 3 项（L1 + L3 + master-plan preflight）通过 `SC-PRE-*` 作为 baseline inventory，不重做但保留 verify 命令做回归。

---

## 3. 成功标准（SC）

> Anti-fill：每条 SC 绑定**命令 / 路径 / 输出断言**；禁止"完善 / 优化 / 系统性"。

### 已完成项（baseline verify）

- [x] SC-PRE-1：`scripts/gd-codex-bridge-review.py:build_capsule_text` 已移除 `target_text` 全文嵌入，capsule 含 `PRIMARY_TARGET_PATH` + `PRIMARY_TARGET_HASH` + `MANDATORY READ STEP`。验证：`grep -q "PRIMARY_TARGET_PATH" scripts/gd-codex-bridge-review.py`
- [x] SC-PRE-2：`scripts/gd-validate-review-content-evidence.py` 存在且 5 类 fixture (valid + 4 类造假) 测试通过。验证（两步）：(1) 脚本存在 `test -f scripts/gd-validate-review-content-evidence.py`；(2) 对造假 review（伪造 SC-X99）返回 exit=1：`python3 scripts/gd-validate-review-content-evidence.py --target fixtures/preflight/negative-sc-verify-missing.md --review fixtures/preflight/l3-fake-review-sample.md 2>&1 | grep -q FAKE_EVIDENCE_DETECTED`
- [x] SC-PRE-3：`scripts/gd-validate-master-plan-consistency.py` 已接入 `gd-review-suite-controller.py` 在 dispatch 前 preflight。验证：`grep -q "PREFLIGHT_SCRIPT" scripts/gd-review-suite-controller.py && grep -q "preflight_failed" scripts/gd-review-suite-controller.py`

### W1 — 生产路径关闭 root cause

- [ ] SC-W1-1：`cmd_run_bridge` 在 `raw_text` parse 后自动调 `gd-validate-review-content-evidence.py --target <primary> --review <raw>`；validator exit ≠ 0 → `review_run_status` 写 `wrapper_schema_fail`。验证：`grep -n "gd-validate-review-content-evidence" scripts/gd-codex-bridge-review.py`（≥1 命中）+ 单元测试 `python3 scripts/gd-codex-bridge-review.py self-test` 通过
- [ ] SC-W1-2：execution_outcome / combined kind 的 capsule 含 `## MANDATORY VERIFY STEP` 段，明示 reviewer 必须 Read 每个 `deliverables_produced.path` + rerun 每个 `verify_results.cmd` 并 echo 真实 exit code。验证（两步）：(1) source 中存在 `grep -q "MANDATORY VERIFY STEP" scripts/gd-codex-bridge-review.py`；(2) build-capsule 输出含该段：先运行 `python3 scripts/gd-codex-bridge-review.py build-capsule --kind execution_outcome --target fixtures/execution-results/valid-closure.json --cwd . --out /tmp/w1s02-check.json`，再 `grep -q "MANDATORY VERIFY STEP" /tmp/w1s02-check.json`

### W2 — 扩展 + 回归

- [ ] SC-W2-1：combined 大 bundle (≥30KB) 跑 L1 capsule 实测，capsule 总大小 ≤ 30KB（standard+template+meta+ref，无 target inline）。验证：`python3 scripts/gd-codex-bridge-review.py build-capsule --kind combined --target <real-30kb-target>` 输出 capsule_size ≤ 30720
- [x] SC-W2-2：`gd-validate-review-content-evidence.py` 加 `--reference-target <plan-path>` 参数，code_diff review 时 SC-ID 真实性校验跨 plan 引用；router `_run_live_code_only` 接入 L3 + reference plan。验证（三步）：(1) `python3 scripts/gd-validate-review-content-evidence.py --help 2>&1 | grep -q "reference-target"`；(2) 跨 target 造假被抓（以 JSON 为 target，无 SC-ID）：`python3 scripts/gd-validate-review-content-evidence.py --target fixtures/preflight/dispatch-map-without-ghost-step.json --review fixtures/preflight/l3-fake-review-sample.md --reference-target fixtures/preflight/negative-sc-verify-missing.md 2>&1 | grep -q FAKE_EVIDENCE_DETECTED`；(3) router wired：`grep -q "reference-target" scripts/gd-review-router.py`
- [ ] SC-W2-3：`gd-final-closure-status.sh` 加 5 条新 sanity check（L1 capsule 减重 / L3 接入 parse-transport / L3 fake-SC-ID 抓 / L1.5 verify step 存在 / combined L1 实测）。验证：`grep -cE "L1|L3|L1\.5" scripts/gd-final-closure-status.sh` ≥ 5

### W3 — 打磨

- [ ] SC-W3-1：bridge writer subprocess timeout 从 600s 起步保留，但新增 `--writer-timeout-sec` argparse 允许 300-1800s 范围调节，默认 600。验证：`python3 scripts/gd-codex-bridge-review.py run-bridge --help` 输出含 `--writer-timeout-sec`
- [ ] SC-W3-2：`gd-validate-review-content-evidence.py` 加 `--target-kind json` 模式，SC-ID 校验从文本流转为 JSONPath 查询。验证（两步）：(1) 参数存在 `python3 scripts/gd-validate-review-content-evidence.py --help 2>&1 | grep -q "target-kind"`；(2) JSON target smoke：`python3 scripts/gd-validate-review-content-evidence.py --target fixtures/execution-results/valid-closure.json --target-kind json --review fixtures/preflight/semantic-regression-passes-preflight.md 2>&1 | grep -q "EVIDENCE_VALID"`
- [ ] SC-W3-3：`fixtures/review-bridge/v1/*.md` 全部历史 raw 跑 L3，无误报。验证：脚本 `scripts/gd-l3-regression-v1-fixtures.sh` 退出 0，输出 `PASS_COUNT > 0 FAIL_COUNT = 0`

---

## 4. 实现步骤（对应 SC）

详见下方 `gd-step-plan-inventory` fenced block。每步 `verify` 字段对齐上方 SC，`sc_refs` 双向可追溯。

任务包模式：**inline**（11 步均为小动作，无需独立 step-plan 文件）。

---

## 5. 多 Agent Dispatch

DISPATCH_MAP_PATH: plans/gd/2026-05-19-review-chain-hardening/artifacts/dispatch_map.json
VALIDATE_CMD: python3 scripts/gd-validate-dispatch.py plans/gd/2026-05-19-review-chain-hardening/artifacts/dispatch_map.json

> **注意**：`dispatch_map.json` 需手工生成（`gd-build-dispatch-map.py` 尚不存在）或从 §5a gd-step-plan-inventory 手工构造。
> 若 dispatch_map.json 不存在，执行时跳过 VALIDATE_CMD，直接按 wave 顺序串行推进（proof_mode: fail_closed_no_dispatch）。

Wave matrix 详见下方 `gd-wave-matrix` fenced block：3 个 wave 串行执行（W1 → W2 → W3），W1 内串行（两步同文件），W2/W3 内允许并行 2 个子 agent（按 max_parallel=2）。

---

## 5a. Dispatch Map / Wave Contract（机器可读 SSOT）

下方两个 fenced JSON block 是本计划的 SSOT。`scripts/gd-validate-master-plan-consistency.py` preflight 会消费它们做一致性校验（自审）。

```json gd-step-plan-inventory
{
  "step_plans": [
    {
      "step_id": "w1-s01-l3-parse-transport-wiring",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w1-s01-impl"],
      "owned_paths": [
        "scripts/gd-codex-bridge-review.py"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**",
        "/Users/praise/.claude/commands/**",
        "/Users/praise/.claude/handoff/**",
        "../../**"
      ],
      "required_context": [
        "scripts/gd-codex-bridge-review.py",
        "scripts/gd-validate-review-content-evidence.py"
      ],
      "deliverables": [
        {"path": "scripts/gd-codex-bridge-review.py", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W1-1"],
      "verify": [
        {"sc_ref": "SC-W1-1", "method": "command", "cmd": "grep -q 'gd-validate-review-content-evidence' scripts/gd-codex-bridge-review.py", "expect": "exit 0"},
        {"sc_ref": "SC-W1-1", "method": "command", "cmd": "python3 scripts/gd-codex-bridge-review.py self-test", "expect": "all PASS"}
      ]
    },
    {
      "step_id": "w1-s02-l15-mandatory-verify-step",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w1-s02-impl"],
      "blocked_by": ["w1-s01-l3-parse-transport-wiring"],
      "owned_paths": [
        "scripts/gd-codex-bridge-review.py"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**",
        "/Users/praise/.claude/commands/**"
      ],
      "required_context": [
        "scripts/gd-codex-bridge-review.py",
        "fixtures/execution-results/valid-closure.json"
      ],
      "deliverables": [
        {"path": "scripts/gd-codex-bridge-review.py", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W1-2"],
      "verify": [
        {"sc_ref": "SC-W1-2", "method": "command", "cmd": "grep -q 'MANDATORY VERIFY STEP' scripts/gd-codex-bridge-review.py", "expect": "exit 0"}
      ]
    },
    {
      "step_id": "w2-s03-combined-bundle-l1-smoke",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w2-s03-impl"],
      "owned_paths": [
        "scripts/gd-l1-combined-bundle-smoke.sh"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**"
      ],
      "required_context": [
        "scripts/gd-codex-bridge-review.py"
      ],
      "deliverables": [
        {"path": "scripts/gd-l1-combined-bundle-smoke.sh", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W2-1"],
      "verify": [
        {"sc_ref": "SC-W2-1", "method": "command", "cmd": "bash scripts/gd-l1-combined-bundle-smoke.sh", "expect": "capsule_size <= 30720"}
      ]
    },
    {
      "step_id": "w2-s04-l3-reference-target-flag",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w2-s04-impl"],
      "owned_paths": [
        "scripts/gd-validate-review-content-evidence.py",
        "fixtures/preflight/l3-code-diff-cross-ref-sample.md"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**"
      ],
      "required_context": [
        "scripts/gd-validate-review-content-evidence.py"
      ],
      "deliverables": [
        {"path": "scripts/gd-validate-review-content-evidence.py", "kind": "file", "must_exist": true},
        {"path": "fixtures/preflight/l3-code-diff-cross-ref-sample.md", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W2-2"],
      "verify": [
        {"sc_ref": "SC-W2-2", "method": "command", "cmd": "python3 scripts/gd-validate-review-content-evidence.py --help 2>&1 | grep -q 'reference-target'", "expect": "exit 0"}
      ]
    },
    {
      "step_id": "w2-s05-final-status-new-sanity",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w2-s05-impl"],
      "owned_paths": [
        "scripts/gd-final-closure-status.sh"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**"
      ],
      "required_context": [
        "scripts/gd-final-closure-status.sh"
      ],
      "deliverables": [
        {"path": "scripts/gd-final-closure-status.sh", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W2-3"],
      "verify": [
        {"sc_ref": "SC-W2-3", "method": "command", "cmd": "grep -cE 'L1|L3|L1.5' scripts/gd-final-closure-status.sh", "expect": ">=5"}
      ]
    },
    {
      "step_id": "w3-s06-writer-timeout-config",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w3-s06-impl"],
      "owned_paths": [
        "scripts/gd-codex-bridge-review.py"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**"
      ],
      "required_context": [
        "scripts/gd-codex-bridge-review.py"
      ],
      "deliverables": [
        {"path": "scripts/gd-codex-bridge-review.py", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W3-1"],
      "verify": [
        {"sc_ref": "SC-W3-1", "method": "command", "cmd": "python3 scripts/gd-codex-bridge-review.py run-bridge --help 2>&1 | grep -q 'writer-timeout-sec'", "expect": "exit 0"}
      ]
    },
    {
      "step_id": "w3-s07-l3-json-target-mode",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w3-s07-impl"],
      "owned_paths": [
        "scripts/gd-validate-review-content-evidence.py"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**"
      ],
      "required_context": [
        "scripts/gd-validate-review-content-evidence.py"
      ],
      "deliverables": [
        {"path": "scripts/gd-validate-review-content-evidence.py", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W3-2"],
      "verify": [
        {"sc_ref": "SC-W3-2", "method": "command", "cmd": "python3 scripts/gd-validate-review-content-evidence.py --help 2>&1 | grep -q 'target-kind'", "expect": "exit 0"}
      ]
    },
    {
      "step_id": "w3-s08-v1-fixtures-l3-regression",
      "status": "draft",
      "task_packet_mode": "inline",
      "task_packets": ["w3-s08-impl"],
      "owned_paths": [
        "scripts/gd-l3-regression-v1-fixtures.sh"
      ],
      "forbidden_paths": [
        "/Users/praise/.claude/scripts/**"
      ],
      "required_context": [
        "scripts/gd-validate-review-content-evidence.py",
        "fixtures/review-bridge/"
      ],
      "deliverables": [
        {"path": "scripts/gd-l3-regression-v1-fixtures.sh", "kind": "file", "must_exist": true}
      ],
      "sc_refs": ["SC-W3-3"],
      "verify": [
        {"sc_ref": "SC-W3-3", "method": "command", "cmd": "bash scripts/gd-l3-regression-v1-fixtures.sh", "expect": "FAIL_COUNT=0"}
      ]
    }
  ]
}
```

```json gd-wave-matrix
{
  "waves": [
    {"wave_id": "w1", "tracks": [
      {"track_id": "t1-bridge", "step_ids": ["w1-s01-l3-parse-transport-wiring", "w1-s02-l15-mandatory-verify-step"], "max_parallel": 1, "mode": "execute"}
    ]},
    {"wave_id": "w2", "tracks": [
      {"track_id": "t2-combined", "step_ids": ["w2-s03-combined-bundle-l1-smoke"], "max_parallel": 1, "mode": "execute"},
      {"track_id": "t2-l3-ext", "step_ids": ["w2-s04-l3-reference-target-flag"], "max_parallel": 1, "mode": "execute"},
      {"track_id": "t2-final-status", "step_ids": ["w2-s05-final-status-new-sanity"], "max_parallel": 1, "mode": "execute"}
    ]},
    {"wave_id": "w3", "tracks": [
      {"track_id": "t3-timeout", "step_ids": ["w3-s06-writer-timeout-config"], "max_parallel": 1, "mode": "execute"},
      {"track_id": "t3-l3-json", "step_ids": ["w3-s07-l3-json-target-mode"], "max_parallel": 1, "mode": "execute"},
      {"track_id": "t3-v1-regression", "step_ids": ["w3-s08-v1-fixtures-l3-regression"], "max_parallel": 1, "mode": "execute"}
    ]}
  ]
}
```

---

## 6. 边界（修改 / 不修改）

**修改**：

- `Project GD/.claude/worktrees/swirling-tickling-flask/scripts/gd-codex-bridge-review.py`（W1-1, W1-2, W3-1）
- `Project GD/.claude/worktrees/swirling-tickling-flask/scripts/gd-validate-review-content-evidence.py`（W2-2, W3-2）
- `Project GD/.claude/worktrees/swirling-tickling-flask/scripts/gd-final-closure-status.sh`（W2-3）
- `Project GD/.claude/worktrees/swirling-tickling-flask/scripts/gd-l1-combined-bundle-smoke.sh`（W2-1，新）
- `Project GD/.claude/worktrees/swirling-tickling-flask/scripts/gd-l3-regression-v1-fixtures.sh`（W3-3，新）
- `Project GD/.claude/worktrees/swirling-tickling-flask/fixtures/preflight/l3-code-diff-cross-ref-sample.md`（W2-2，新）

**不修改**：

- 旧 `/rev` 任何 artifact
- `/Users/praise/.claude/**`（runtime configs / commands / handoff / state）
- 其他 step 的 owned_paths
- worktree 外的 `Project GD/scripts/`（main 分支文件）
- 任何 `Project Sentinel/` / `Project AKB2/` / 其他业务项目

---

## 7. 风险与防护

| 风险 | 防护 |
|------|------|
| W1-1 接入 parse-transport 后历史 v1 fixture 突然 fail（误抓为造假）| 先跑 W3-3 v1 fixtures 回归确认零误报；若发现，调 L3 regex 而非放过 |
| W1-2 MANDATORY VERIFY STEP 让 codex 跑用户文件系统命令（rerun verify cmd）增加 review 时间 | 文档明示是 fail-closed 必要代价；timeout 配 600s 容纳 |
| W2-1 combined 30KB+ 真实样本难找 | 用 plan + closure JSON 合成；或拿 Sentinel master-plan 47KB 当 combined fixture |
| W2-2 双 target SC-ID 跨引用增加 validator 复杂度 | `--reference-target` 是 opt-in，单 target 行为不变 |
| codex transport_failed 仍偶发（非 capsule 大小问题）| 不在本批次解决，记录为 follow-up；本批 metric 是减重 + 拦截，不是 transport 稳定性 |

---

## 8. 测试计划

> 全部命令在 `COMMAND_CWD = Project GD/.claude/worktrees/swirling-tickling-flask` 下执行。

```bash
# pre-flight：master-plan 一致性自审（本计划必须先通过自己写的 preflight）
python3 scripts/gd-validate-master-plan-consistency.py plans/gd/2026-05-19-review-chain-hardening/master-plan.md
# expect: PREFLIGHT_PASSED

# build dispatch map（可选 — gd-build-dispatch-map.py 尚不存在时，手工写 artifacts/dispatch_map.json 替代）
# [ -f scripts/gd-build-dispatch-map.py ] && python3 scripts/gd-build-dispatch-map.py plans/gd/2026-05-19-review-chain-hardening/master-plan.md
# expect: 写出 artifacts/dispatch_map.json（手工写时直接跳到 validate 步）

# validate dispatch map（artifacts/dispatch_map.json 存在时必跑）
# python3 scripts/gd-validate-dispatch.py plans/gd/2026-05-19-review-chain-hardening/artifacts/dispatch_map.json
# expect: exit 0

# 整批 final-status 回归
bash scripts/gd-final-closure-status.sh
# expect: pass >= 30, fail = 0（包含本批次 SC-PRE + W1+W2+W3 全部 sanity）

# L3 全 kind regression
bash scripts/gd-l3-regression-v1-fixtures.sh
# expect: FAIL_COUNT=0

# capsule 减重实测
python3 -c "import importlib.util; \
  spec = importlib.util.spec_from_file_location('bridge', 'scripts/gd-codex-bridge-review.py'); \
  m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); \
  from pathlib import Path; \
  capsule, *_ = m.build_capsule_text(kind='plan', target=Path('plans/gd/2026-05-19-review-chain-hardening/master-plan.md'), cwd=Path('.'), compat_v1=True); \
  print(f'plan_capsule_bytes={len(capsule)}'); assert len(capsule) < 30720, 'capsule too large'"
# expect: < 30720 (30KB)
```

---

## 9. Assumptions

- worktree `swirling-tickling-flask` 在 commit `3609315` 基线 + 已完成 SC-PRE-1/2/3（L1 + L3 + preflight）。
- `gd-build-dispatch-map.py` 不存在；W1 启动前手工写 `dispatch_map.json` 或在 W1 内同步引入（不阻塞主路径，preflight 的 DISPATCH_DRIFT 是简化版字符串搜索，不强求 round-trip 生成器）。
- `codex` CLI 可用，bridge writer subprocess timeout 默认 600s（已实测足够 Sentinel xhigh review）。
- 本计划不涉及 install 到 `~/.claude/commands/gd.md`；只动 worktree 内文件。
- commit 时机：所有 W1+W2+W3 SC 通过后批量 commit；中间不 push。
