# /review2 plan_review 与模板对齐修正 v8 — 最终报告

> 完成日期：2026-05-26
> Worktree：`.claude/worktrees/review2-plan-review-v8`
> 方案权威源：`/Users/praise/AI-Agent/Codex/plans/2026-05-25-project-gd-review2-plan-review-template-alignment.md` (v5)

## 修正目标

1. L2 helper 只负责生成审查上下文，不作为 Codex 的直接 review target
2. Bridge 发给 Codex 的 target 必须是原始计划文件，而非 `/review2` capsule
3. 计划模板、preflight、capsule validator、bridge guard、L3 content-evidence 校验统一到同一套字段语义合约

## 修改文件汇总

### 新增文件

| 文件 | 用途 | SC 覆盖 |
|------|------|---------|
| `scripts/lib/__init__.py` | 包初始化 | — |
| `scripts/lib/sc_extraction.py` | 共享 SC_ID_RE + extract_sc_ids() | SC-4 |
| `scripts/lib/path_classification.py` | is_review2_capsule_path() | SC-5, SC-7 |
| `scripts/gd-validate-review2-plan-target.py` | field-based plan preflight | SC-3, SC-5, SC-9 |
| `fixtures/review2-plan/good-plan.md` | preflight pass fixture | SC-3 |
| `fixtures/review2-plan/gd-step-style-good-plan.md` | gd-step-plan style pass fixture | SC-3 |
| `fixtures/review2-plan/missing-sc-plan.md` | preflight fail fixture (no SC) | SC-5 |
| `fixtures/review2-plan/old-rev-style-plan.md` | preflight fail fixture (old rev style) | SC-5 |
| `fixtures/review2-plan/results/review-route-split/case/capsule.md` | capsule-as-target fail fixture | SC-5, SC-7 |
| `fixtures/review2-plan/good-policy-capsule.md` | validator pass fixture | SC-2, SC-3 |
| `fixtures/review2-plan/bad-policy-capsule.md` | validator fail fixture (wrong policy) | SC-3 |
| `fixtures/review2-plan/expected/l3-validator-snapshot.txt` | L3 output snapshot baseline | SC-4 |
| `fixtures/mocks/review-result-writer-mock.sh` | mock writer for bridge smoke tests | SC-10 |
| `scripts/gd-review2-sc-extraction-snapshot-smoke.sh` | SC-4 smoke | SC-4 |
| `scripts/gd-review2-plan-template-preflight-smoke.sh` | SC-3/SC-5/SC-9 smoke | SC-3, SC-5, SC-9 |
| `scripts/gd-review2-capsule-policy-smoke.sh` | SC-2/SC-3 smoke | SC-2, SC-3 |
| `scripts/gd-review2-output-coverage-smoke.sh` | SC-6 smoke | SC-6 |
| `scripts/gd-review2-plan-routing-smoke.sh` | SC-7/SC-8/SC-10 smoke | SC-7, SC-8, SC-10 |
| `reports/v8-dependency-check.md` | Phase 1 dependency report | SC-1, SC-11 |

### 修改文件

| 文件 | 修改内容 | SC 覆盖 |
|------|---------|---------|
| `scripts/gd-validate-review-content-evidence.py` | import 改用 shared `sc_extraction.py` | SC-4 |
| `templates/plan-template.md` | 移除旧 `/rev` 引用；加 REVIEW_DOMAIN/REVIEW_FOCUS/步骤字段 | SC-9 |
| `scripts/gd-build-review2-capsule.py` | PROFILES 加 plan_review；plan_review capsule 含 REVIEW_TARGET_HASH + BRIDGE_TARGET_POLICY | SC-2 |
| `scripts/gd-validate-review2-capsule.py` | plan_review profile 强制 BRIDGE_TARGET_POLICY: original_plan_only | SC-3 |
| `scripts/gd-validate-review2-output.py` | 空 mandatory list 时 exit 0（SC-6 fix） | SC-6 |
| `scripts/gd-codex-bridge-review.py` | B2 (WRITER_PATH override)、B3 (_KINDS_REQUIRING_COMPAT_V1…)、B4 (exit 1)、plan live guard | SC-7, SC-8, SC-10 |
| `commands/review2.md` | 加 plan_review profile 文档、routing semantics、fail-closed rules | SC-1 |
| `docs/review-route-necessity-memo.md` | 追加 v8 plan_review 路由语义说明 | SC-1 |
| `fixtures/codex-bridge-v2/valid-v2-build-capsule-plan.json` | _expect: PASS → FAIL (B3 guard fires) | SC-8 |
| `fixtures/codex-bridge-v2/valid-v2-build-capsule-code-diff.json` | _expect: PASS → FAIL (B3 guard fires) | SC-8 |

## 回归测试结果

| smoke 脚本 | PASS | FAIL | SC |
|-----------|------|------|----|
| `gd-review2-sc-extraction-snapshot-smoke.sh` | 5 | 0 | SC-4 |
| `gd-review2-plan-template-preflight-smoke.sh` | 10 | 0 | SC-3, SC-5, SC-9 |
| `gd-review2-capsule-policy-smoke.sh` | 8 | 0 | SC-2, SC-3 |
| `gd-review2-output-coverage-smoke.sh` | 12 | 0 | SC-6 |
| `gd-review2-plan-routing-smoke.sh` | 6 | 0 | SC-7, SC-8, SC-10 |
| **v8 smoke 合计** | **41** | **0** | |

### SC-12 Regression Suite（分步，禁止 && 链式）

| 脚本/命令 | 结果 | 备注 |
|---------|------|------|
| `python3 scripts/gd-codex-bridge-review.py self-test` | PASS | self-test PASS（lock-sentinel: SKIPPED as expected） |
| `bash scripts/gd-bridge-compat-smoke.sh` | PASS (3/3) | compat smoke pass=3 fail=0 |
| `bash scripts/gd-l3-regression-v1-fixtures.sh` | PASS (10/10) | PASS_COUNT=10 FAIL_COUNT=0 |
| `bash scripts/gd-check-review-route-preflight.sh --route review2` | FAIL（pre-existing） | L3_GD_COMMAND_PARITY: FAIL — `commands/gd.md` is dirty (列入 v8 禁止触碰文件); 与本轮改动无关 |

**SC-12 说明**：三项 regression 全 PASS；route preflight 失败因 `commands/gd.md` 是 pre-existing dirty file，v8 scope 明确禁止触碰，不计入 v8 失败。

**总计（v8 smoke + SC-12 regression）**：PASS=55，FAIL=0（pre-existing 1 项除外）

## SC 覆盖矩阵

| SC | 描述 | 状态 |
|----|------|------|
| SC-1 | commands/review2.md 有 plan_review profile 文档（12 命中） | ✓ PASS |
| SC-2 | capsule builder 产出含 BRIDGE_TARGET_POLICY: original_plan_only 的 plan_review capsule | ✓ PASS |
| SC-3 | capsule validator 对 plan_review 强制 policy；good/bad 均正确 | ✓ PASS |
| SC-4 | SC_ID_RE 抽到 shared helper；L3 validator 输出 byte-identical | ✓ PASS |
| SC-5 | preflight 拒绝 missing-sc / old-rev-style / capsule-as-target / missing-WHERE / missing-WHAT / missing-WHY / missing-VERIFY | ✓ PASS |
| SC-6 | 空 mandatory list 时 validator exit 0（不误报） | ✓ PASS |
| SC-7 | bridge capsule target guard：PLAN_TARGET_MUST_BE_ORIGINAL_PLAN exit 1 | ✓ PASS |
| SC-8 | v2 template missing guard：V2_TEMPLATE_NOT_READY exit 1 | ✓ PASS |
| SC-9 | plan-template.md 无旧 /rev 字段；`rg 'rev-review-standard|REV_VERDICT' templates/plan-template.md` = 0 命中 | ✓ PASS |
| SC-10 | GD_WRITER_PATH_OVERRIDE + mock writer → bridge end-to-end APPROVED | ✓ PASS |
| SC-11 | hook probe HOOK_NEUTRAL（sandboxed HOME 验证，见 reports/v8-dependency-check.md §5） | ✓ PASS |
| SC-12 | 分步 regression：self-test + compat-smoke + L3-regression 全 PASS；route preflight pre-existing failure 不计入 | ✓ PASS |

## 关键决策记录

### B1: 不新增 gd-plan-review-v2-template.md（不在 v8 范围）
- v8 scope 只修正路由语义，不交付 v2 plan 审查模板
- B3 guard（V2_TEMPLATE_NOT_READY）使缺模板时 bridge fail 明确，而非静默降级

### B2: GD_WRITER_PATH_OVERRIDE 覆盖
- 允许 smoke test 在 lab-only 环境运行 bridge→writer→L3 完整链路
- 默认值保持 live writer 路径不变

### B3: _KINDS_REQUIRING_COMPAT_V1_WHEN_V2_TEMPLATE_MISSING
- 来自 Phase 1 报告：plan 和 code_diff 的 v2 模板均 MISSING
- code_diff 因 `_COMPAT_V1_DEFAULT_KINDS` 已自动降级到 compat_v1；B3 guard 主要保护 plan kind

### SC-6 空 mandatory list 修复
- 原代码：空列表时仍要求 `MANDATORY_READ_COVERAGE:` section 存在 → 误报
- 修复：空列表时直接 return []（无错误），输出 MANDATORY_READ_COUNT: 0 / COVERED_COUNT: 0

## Codex 验收 P2 修复记录（v8 review-fix round）

### P2-A: preflight WHERE/WHAT/WHY/VERIFY 全字段强制

| | 内容 |
|--|------|
| **Finding** | `gd-validate-review2-plan-target.py` L77-88 仅要求四字段中「至少一个」存在（`step_fields_present == 0` 才报错），不符合模板要求的每步都具备全部四字段 |
| **Fix** | 改为逐字段检查：对 WHERE/WHAT/WHY/VERIFY 各自独立判断是否缺失，任一缺失均输出 `PLAN_ERROR: missing step field <FIELD>` |
| **Verify** | 新增 4 个 negative fixtures（`missing-where-plan.md` / `missing-what-plan.md` / `missing-why-plan.md` / `missing-verify-plan.md`）；`gd-review2-plan-template-preflight-smoke.sh` 新增 4 个 subtests → 14/14 PASS；原 good-plan.md / gd-step-style-good-plan.md 仍 PASS |

### P2-B: plan_review capsule builder --target 必填校验

| | 内容 |
|--|------|
| **Finding** | `gd-build-review2-capsule.py --profile plan_review` 未传 `--target` 时仍输出 `CAPSULE_BUILD_PASS`（target=None → REVIEW_TARGET / REVIEW_TARGET_HASH / BRIDGE_TARGET_POLICY 全缺），不符合 original_plan_only 语义 |
| **Fix** | 在 `main()` 开头加 plan_review 早期校验：`--target` 缺失 → `PLAN_REVIEW_TARGET_REQUIRED` exit 1；目标文件不存在 → `PLAN_REVIEW_TARGET_NOT_FOUND` exit 1；有效 target 保持 `CAPSULE_BUILD_PASS` |
| **Verify** | `python3 scripts/gd-build-review2-capsule.py --profile plan_review --out-dir $tmp` → exit 1 + `PLAN_REVIEW_TARGET_REQUIRED` ✓；`--target /no/such/plan.md` → exit 1 + `PLAN_REVIEW_TARGET_NOT_FOUND` ✓；`--target fixtures/review2-plan/good-plan.md` → exit 0 + `CAPSULE_BUILD_PASS` ✓；`gd-review2-capsule-policy-smoke.sh` → 10/10 PASS |

### P2 修复后回归

| 脚本 | PASS | FAIL |
|-----|------|------|
| `gd-review2-plan-template-preflight-smoke.sh` | 14 | 0 |
| `gd-review2-capsule-policy-smoke.sh` | 10 | 0 |
| `gd-review2-sc-extraction-snapshot-smoke.sh` | 5 | 0 |
| `gd-review2-output-coverage-smoke.sh` | 12 | 0 |
| `gd-review2-plan-routing-smoke.sh` | 6 | 0 |
| bridge self-test + compat-smoke + L3-regression | 14 | 0 |
| **合计** | **61** | **0** |

## Live Drift 声明（MANDATORY）

**本轮为 source-only 修正，以下 live runtime 文件未同步：**

| Live 路径 | 当前状态 | 同步方式 |
|----------|---------|---------|
| `/Users/praise/.claude/commands/review2.md` | 未安装 plan_review 文档 | `scripts/install-review-route-command.sh --route review2` + ledger |
| `/Users/praise/.claude/scripts/gd-build-review2-capsule.py` | 无 plan_review profile | 需用户显式授权 sync |
| `/Users/praise/.claude/scripts/gd-validate-review2-capsule.py` | 无 BRIDGE_TARGET_POLICY 校验 | 需用户显式授权 sync |
| `/Users/praise/.claude/scripts/gd-codex-bridge-review.py` | 无 B2/B3/B4 guards | 需用户显式授权 sync |
| `/Users/praise/.claude/scripts/gd-validate-review2-output.py` | 空 mandatory list 仍误报 | 需用户显式授权 sync |

Live drift 量化：5 个脚本未同步，source worktree 领先 live runtime。

## 禁止边界确认

- ✓ 未写入 `/Users/praise/.claude/**`（任何子目录）
- ✓ 未修改 dirty files（PROJECT_GOAL.md / commands/gd.md / docs/gd-v7-claude-command.md / scripts/uninstall-gd-command.sh）
- ✓ 未注册 slash command，未新增 daemon
- ✓ 所有写入在 worktree `review2-plan-review-v8` 内
