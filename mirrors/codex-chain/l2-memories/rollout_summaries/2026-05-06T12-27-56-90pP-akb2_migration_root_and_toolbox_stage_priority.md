thread_id: 019dfd42-5530-75f3-a81b-31eb064b0969
updated_at: 2026-05-09T19:39:33+00:00
rollout_path: /Users/praise/.codex/sessions/2026/05/06/rollout-2026-05-06T20-27-56-019dfd42-5530-75f3-a81b-31eb064b0969.jsonl
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex

# AKB2.0 工具库从旧 Codex 根迁到 `Project AKB2` 后的状态核对与后续优先级

Rollout context: 先前在旧 Obsidian `AKB2.0` / Codex 工作区里完成了 `cc-local-llm` 后端契约刷新、L1 smoke / Tool Intake Gate 相关工作，以及 `cc-review` 风格的计划更新；随后用户明确表示“AKB2 的工作根目录整体在迁移，迁移完再说”。迁移完成后，用户要求先读迁移后的工作根目录，再判断工具库接下来的任务优先级与阶段划分。最终核对到的新工程根是 `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project AKB2`，而旧的 `Codex/ai-infra/akb2-toolbox-*` 目录已被迁走/清理；Obsidian `AKB2.0` 仍存在，但应视为展示层而不是工程实现根。

## Task 1: 迁移后工作根识别与基线核对

Outcome: success

Preference signals:
- 用户说“迁移完了，你先读下迁移后的工作根目录，工具库接下来的任务优先级是什么，一共分几个阶段？” -> 未来类似迁移后任务应先做只读根目录识别和状态核对，再谈计划，不要直接沿用旧路径或旧记忆。
- 用户多次强调“继续”“先读下迁移后的工作根目录” -> 说明在迁移/重构后，用户优先要的是当前权威根与可继续执行的阶段划分，而不是回顾旧流程细节。

Key steps:
- 通过只读 `find` / `sed` / `pytest` / `verify-no-drift` 核对到工程根为 `Project AKB2`，其 `README.md` 明确写着“AKB2.0 工程根：lint/gate/intake CLI + MCP wrapper + tests + eval harness + engineering docs（不含知识库本体）”。
- 迁移闭环报告 `reports/migration/akb2-engineering-root-migration-closure-2026-05-09.md` 明确给出：`Project AKB2` 是 AKB2 工程文件和工具库的唯一权威维护目录，取代迁移前的旧 Codex 容器；Obsidian AKB2.0 vault 仅作为知识库展示层。
- `find` 结果显示工程实现已迁入 `Project AKB2/toolbox/cc-{executable-plan,review,local-llm,skill-stocktake,akb-search}`，以及 `src/akb2/{lint,gate,toolbox_scan,automation_gate,closure,matrix,promotion_gate,search_quality}`。
- 只读验证显示：`pytest -q` 60 passed；`scripts/verify-no-drift.sh` 17/17 MATCH；llama-swap backend `GET /health` 为 `OK`，`/v1/models` 可见 6 个模型；`global_verdict = blocked_l2_verdict_blocked`；`cc-local-llm` 和 `cc-skill-stocktake` 的 L2 recommendation 仍为 `blocked`；Search Quality v0 为 `blocked_insufficient_user_queries`。

Failures and how to do differently:
- 旧路径 `Codex/ai-infra/akb2-toolbox-*` 已不再是权威工程根，未来类似迁移后任务不要先沿用旧路径判断状态。
- 迁移后要先区分工程根与展示层：`Project AKB2` 是工程维护目录，Obsidian `AKB2.0` 只是知识库展示层。

Reusable knowledge:
- `Project AKB2/README.md` + `reports/migration/akb2-engineering-root-migration-closure-2026-05-09.md` 是迁移后工程根与边界的第一权威入口。
- 迁移后 `verify-no-drift.sh` 仍可作为 install target / mirror / closure-manifest 的只读一致性总检查。
- 当前闭环证据显示：5 个工具已经完成 L1 floor closure，但并不意味着后续 L2 / promotion / automation 已放行。

References:
- [1] `Project AKB2/README.md`: “AKB2.0 工程根：lint/gate/intake CLI + MCP wrapper + tests + eval harness + engineering docs（不含知识库本体）”
- [2] `reports/migration/akb2-engineering-root-migration-closure-2026-05-09.md`: “Project AKB2 是 AKB2 工程文件和工具库的唯一权威维护目录，取代迁移前的旧 Codex 容器”
- [3] 只读校验：`pytest -q` → `60 passed in 3.79s`；`bash scripts/verify-no-drift.sh` → `all 17 checks MATCH`
- [4] 只读后端验证：`curl -sf http://127.0.0.1:8080/health && curl -sf http://127.0.0.1:8080/v1/models | jq -r '.data[].id'` → `OK` + `bge-m3 gemma-3-4b nomic-embed qwen2.5-14b qwen3-32b qwen3-8b`

## Task 2: 工具库后续阶段优先级划分

Outcome: success

Preference signals:
- 用户问“工具库接下来的任务优先级是什么，一共分几个阶段？” -> 未来类似问题应直接给阶段化路线图，并标明哪些阶段已完成、哪些只是占位、哪些依赖外部前置条件。
- 在当前状态下，用户之前说过“迁移完再说” -> 迁移后先冻结基线，再推进后续阶段；不要一上来就继续做新开发。

Key steps:
- 结合 `Project AKB2` 下的 runbooks / evals / reports 判断：
  - `docs/runbooks/run-l2-regression.md` 仍写明：`cc-local-llm` / `cc-skill-stocktake` 的 L2 v1 已是 blocked，backend curl_exit=7 是已知阻塞；`cc-executable-plan` / `cc-review` 是 grandfathered L2，无 L2 evidence；`cc-akb-search` 要观察 7 天后再进 search quality 回归。
  - `src/akb2/promotion_gate/v0/README.md` 说明 Promotion Gate v0 仍是占位，前置条件之一是两个 L2 regression recommendation 都要是 `recommend_promote_L2`，且必须用户显式说“开始 promotion gate v0 plan”才启动。
  - `src/akb2/automation_gate/README.md` 说明 Automation Gate v0 已是 dry-run mechanism implemented，但当前真实状态仍是 `blocked_l2_verdict_blocked`，不会修改 `automation_allowed`。
  - `src/akb2/search_quality/v0/README.md` 和 `run-evidence.md` 说明 Search Quality v0 已完成只读审计机制，但因 `n_user_observed = 0 < 7` 被 hard fail，不进入 baseline/metrics/recommendation。

Failures and how to do differently:
- 不能把“有 runner / 有 report / 有机制”误当成“阶段已经放行”。
- `l2-regression-v1` 和 `automation-gate-v0` 都说明：机制完成 ≠ 条件满足；特别是 L2 regression 仍被 backend blocked / blocked verdict 卡住。
- Search Quality v0 目前应该继续等待真实 query 积累，而不是抢在 L2 / promotion / automation 前面。

Reusable knowledge:
- 迁移后可将工具库后续工作概括为 6 个阶段：P0 基线冻结 → P1 L2 重跑 → P2 补 L2 evidence → P3 Promotion Gate → P4 Automation Gate → P5 Search Quality。
- 现阶段最优先不是新开发，而是先把迁移后的基线固定住，再重跑 L2 regression；如果 L2 仍 blocked，再决定是否修 backend 或补证据。
- `src/akb2/automation_gate/outputs/current/gate-result.json` 当前结果为 `{"global_verdict":"blocked_l2_verdict_blocked","would_create_automation":false}`。

References:
- [1] `docs/runbooks/run-l2-regression.md`: `cc-local-llm` / `cc-skill-stocktake` 已跑过 L2 v1，verdict=blocked（backend curl_exit=7）；`cc-executable-plan` / `cc-review` 是 grandfathered L2，无 L2 evidence；`cc-akb-search` 观察 7 天后再纳入
- [2] `src/akb2/promotion_gate/v0/README.md`: Promotion Gate v0 先决条件要求 `cc-local-llm` 和 `cc-skill-stocktake` 的 L2 verdict 都是 `recommend_promote_L2`，且需用户显式触发
- [3] `src/akb2/automation_gate/README.md`: 当前真实状态 `global_verdict = blocked_l2_verdict_blocked`，`would_create_automation = false`
- [4] `src/akb2/search_quality/v0/README.md` / `run-evidence.md`: `blocked_insufficient_user_queries`，`n_user_observed = 0`，建议等到 `2026-05-15` 再重跑 SQ-1
- [5] `evals/l2-regression-v1/cc-local-llm/recommendation.json` 与 `evals/l2-regression-v1/cc-skill-stocktake/recommendation.json` 仍为 `blocked`

## 总体结论

Outcome: success

- 工具库的 **L1 floor closure 已完成**：5 个工具均已在新工程根下对齐到 active/L1，`automation_allowed:false` 保持不变。
- **迁移后的工程根已确认**：`Project AKB2` 是唯一权威工程维护目录；Obsidian `AKB2.0` 是展示层。
- **后续还没做完**：L2 regression、Promotion Gate、Automation Gate 放行、Search Quality baseline/评分都还未进入最终通过态，因此不能说“工具库全部做完了”。
- 未来默认动作应当是：先做迁移后基线冻结，再重跑 L2 regression；如果 backend / evidence 仍阻塞，再决定是否修复或补证据；Automation 和 Search Quality 继续保持独立阶段，不要混在一起。
