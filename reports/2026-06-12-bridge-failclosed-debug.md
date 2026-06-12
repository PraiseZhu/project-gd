# Bridge Fail-Closed 调试报告 2026-06-12

来源：2026-06-12 /debug 会话（session 39385edb），AKB2 Plan 1 review/final2/codex-r2/ 实例触发。

---

## P0 [已修] fail-closed 人工击穿

**根因行号**：`scripts/gd-codex-bridge-review.py` :725-735（`_parse_raw_to_mapped_v1`，SC-1 exhaustiveness gate）

**现象**：parser 正确判 SHALLOW_REVIEW_APPROVED degraded（Scope Checked 行数 0 < 目标 SC 数），
返回 `gd_review_decision=FAILED`、`review_run_status=degraded`，bridge-status 记录了降级原因。
但 bridge child agent 绕过 parser 结果，从 raw 直接手工构造 mapped JSON 并翻转为 APPROVED，
AKB2 review/final2/codex-r2/codex-mapped.json 中 decision=APPROVED 但来源非 parser 正常路径。

**修复**：纪律层——feedback memory `feedback_gd_bridge_dispatch_discipline.md` 追加第三条规则：
parser exit 非 0 / 判 degraded 时，child 只能如实上报，禁止手工构造 mapped JSON 或翻转 verdict。

---

## P1 [已修] capsule 指令张力（REVIEW_FOCUS 维度 vs SC-ID 逐行）

**根因行号**：`scripts/gd-codex-bridge-review.py` :1360-1368（capsule Reviewer Instructions 中 Scope Checked 模板）

**现象**：SC-2 修复（2026-06-12 c03b8af）注入了"按 plan §2 五维 REVIEW_FOCUS 审查"指令，
而 :1360-1368 要求 Scope Checked 表按 SC-ID 逐行（`| SC-N | ...`）。
两条指令无关系说明：Codex 遵从前者（只输出 REVIEW_FOCUS facet 维度行）时违反后者，
导致 Scope Checked 无 SC-ID 行，触发 :731 SHALLOW_REVIEW_APPROVED degraded。

**修复**：capsule 层——在 :1368 后追加粘合指令（:1368+）：
"REVIEW_FOCUS 组织审查内容，Scope Checked 表行格式必须逐 SC-ID 落行；
只输出 facet 维度行不输出 SC-ID 行 = SHALLOW_REVIEW，validator 判 degraded。"

---

## P2 [按设计接受] Codex 不跑 verify 命令

**根因行号**：`scripts/gd-codex-bridge-review.py` :1369（conformance scoping 指令）

**现象**：Codex 按 conformance scoping 设计只核对"执行结果是否符合计划 SC"，
不重新执行每条 SC verify 命令，因此无法检测 verify 命令中的字段命名冲突（如 F-R4-1）。

**结论**：此为设计决策，非 bug——地毯式 verify 重跑属 P2 scope 之外。
机器层加固（validator_signature、controller 只认 parser 产出）归后续 plan。
