# Wave 1 Merge Report — execute stage

dispatch_id: fix-review-chain-bugs-20260616
wave: w1
batch: batch-fix-review-chain-bugs-20260616-wave1
max_parallel: 2
child_agent_count: 2

## Child jobs

| track | exec_status | owned 改动 | SC | 结论 |
|-------|-------------|-----------|----|------|
| step-1-shared-p0-failclosed | completed | 改 3 源(bridge / content-evidence / execution-outcome) + 新增 tests/gd-step1-shared-p0-smoke.sh | SC-1/2/3/4/12/13 全 pass | 共享 P0 fail-closed 收口（含 SC-12 误拒收口）|
| step-3-l3-validators | completed | 改 6/12 验证器 + 新增 tests/gd-validator-hardening-smoke.sh | SC-8 pass | L3 验证器硬化(20/0 fixture)，其余 6 验证器逐源排查无真 fail-open 未改 |

## 主 agent 合并判定

- **owned_paths 审计**：`git status` 实际改动 = step-1 的 3 文件 + step-3 的 6 文件 + 2 新 test，**无越界、无两 child 互相覆盖**（并行同目录但 owned 非重叠）。
- **post-wave batch 校验**：`gd-validate-execution-batch.py batch-wave1.json execution-dispatch-map.json` exit 0（wave membership / sc_refs↔verify / deliverable truth / owned containment / 物理存在 全过）。
- **回归守护**：step-3 硬化后的 stage-dispatch-ledger / controller-report 校验器对 plan 阶段旧 ledger/report 仍 exit 0；各自 self-test exit 0 → 合法输入未被误伤。
- **final_decision**：APPROVED（wave 内两 track 全 completed，SC 全 pass，无 blocking bucket）。

## 残留张力（surface 不平均）

- step-1 SC-3 的 `--skip-line-ref-check` 收紧仅作用于 .json target；对 .md RC target 未全面收紧，因既有 `tests/gd-l3-regression-v1-fixtures.sh` 4 个 .md RC 桩 fixture 依赖该 flag。已在 result known_limitations 记录，留待后续 wave 或测试重构处理。
