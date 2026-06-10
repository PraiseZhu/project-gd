# L3 Review Fusion — 当前状态

**日期**: 2026-06-09
**分支**: feature/l3-chain-mechanism

---

## 产物清单

| 产物 | 路径 | 状态 |
|------|------|------|
| constitution | docs/constitution.md v1.0.0 | ✅ |
| feature spec | specs/l3-review-fusion/spec.md | ✅ |
| master-plan | plans/gd/.../master-plan.md | ✅ Codex r9+r10 双审 APPROVED |
| dispatch-map | plans/gd/.../dispatch-map.json | ✅ validator exit 0 |
| 6 task packets | plans/gd/.../packets/*.md | ⚠️ 见下 |
| merge report | plans/gd/.../dispatch-merge-report.md | ✅ |
| 3 batch ledger | plans/gd/.../ledgers/*.json | ✅ validator exit 0 |
| controller-report | plans/gd/.../controller-report.json | ✅ validator exit 0 |

---

## 6 个 Task Packet 审查状态

```
r1-r5 共 5 轮 Codex 双审，在 packet 层面反复（计划文档 SC verify 为 grep/assertion，
Codex 每轮找不同刺，与 master-plan 的 9 轮 ping-pong 同根因）。

r6 最新状态（patch 前）：
t1-transport-guard      r6: —（r5 APPROVED，r6 审查未单独运行）
t2-bridge               r6: 2f REQUIRES_CHANGES   owned_paths 与 SC-2 verify
t3-review-plan          r6: 2f REQUIRES_CHANGES   bridge path 例外 + t5 依赖（执行环）
t4-code-path            r6: 2f REQUIRES_CHANGES   SC-1 verify 弱门
t5-regression           r6: 0f FAILED             0 finding 但判定 FAILED（退化）
t6-deploy               r6: 2f REQUIRES_CHANGES   SC-1/SC-2 verify

--- patch 已应用（2026-06-10，待 r7 重新验证）---
patch 修复内容：
  t1: blocked_by: [t5] → [] （消除执行环）；verify 加 ensure_codex_available + healthcheck >=2 断言
  t2: SC-2 target 路径改为 master-plan.md；SC-6 改 grep 精确短语 conformance scoping + 挑刺漂移
  t3: blocked_by: [t2,t5] → [t2]（消除执行环）；新增 SC-3-bridge-callsite 行为验证
  t4: SC-1 expect 从 exit!=0 改为 PASS；补 SC-1-behavior + self-test 契约
  t5: verify 加 collection-guard（--collect-only 前置）；grep 精确匹配终态行
  t6: 新增 SYNC_ENTRIES_OK 逐条验证 source/target；ledger 加 target_path 断言
  master-plan: §9 加 constitution P5 例外仲裁声明（L3 申请 FR-004 豁免）

patch 后状态（pending r7）：
t1: PATCH_PENDING
t2: PATCH_PENDING
t3: PATCH_PENDING
t4: PATCH_PENDING
t5: PATCH_PENDING（原 FAILED 退化已修，待 r7 确认）
t6: PATCH_PENDING

注意：dispatch-merge-report.md 与 controller-report.json 记录的 APPROVED
是 patch 前状态，不代表当前可执行放行。待 r7 全部通过后才更新为 APPROVED。
```

---

## 已修复的基础设施 Bug

| # | 文件 | 问题 | 状态 |
|---|------|------|------|
| INFRA-1 | gd-review-suite-controller.py:972 | aggregate 传了不存在的 --consume-existing-results → 每次 exit 2 | ✅ 已修 |
| INFRA-2 | gd-review-suite-controller.py:1109 | batch_ledgers path 写相对路径导致 validator 找不到 | ✅ 已修 |
| INFRA-3 | controller + aggregate | aggregate 只读 raw .result(无 gd_review_decision)→6 个全红却报 APPROVED | ✅ 已修 |
| INFRA-4 | controller:210 | _secondary_gate 读 agg["summary"]但 aggregate 写的是 aggregate_summary → PARENT_GATE_MISMATCH | ✅ 已修 |
| INFRA-5 | controller:202 | _secondary_gate 不认 aggregate 的 closure_eligible/closure_blockers 格式 | ✅ 已修 |

---

## 已修复的 Master-Plan Bug

| # | 文件 | 问题 | 状态 |
|---|------|------|------|
| F1 | master-plan + dispatch-map | SC-8 verify 未排除 .deploy-manifest.jsonl 的 # 注释行 → json.loads 崩 | ✅ patch 3 处 |

---

## 根因说明

Codex 在 packet 层面反复的根本原因与 master-plan 的 9 轮相同：
`prompts/gd-review-standard.md` 缺少"一次列全所有可发现 finding"的穷举强制条款。
该条款正是 t2-bridge 要补的 §10，在 t2 执行完成前，Codex 不会一次报全。

---

## 下一步

**当前阶段：packet patch 完成，待 r7 re-review**

1. 触发 r7 Codex re-review（验证 6 个 packet patch 是否已消除所有 P1/P2 finding）
2. r7 APPROVED 后：t1-t6 按 wave 顺序执行（w1=t1 → w2=t2 → w3=t3/t4 并行 → w4=t5 → w5=t6）
3. 执行完成后 `/gd review` 做 code/执行路审查
4. Plan E / deploy-live 做 runtime 回灌 + parity

**已解决的阻塞项**：
- ✅ 执行环（t1/t3 错误依赖 t5）已修
- ✅ constitution P5 与 spec3 冲突已在 master-plan §9 仲裁（L3 申请 P5 豁免）
- ✅ 6 个 packet verify 弱验证已加强（path 稳定性/误通过/退化检测）
