# Raw Memories

Merged stage-1 raw memories (stable ascending thread-id order):

## Thread `019dfc53-5a1d-74f1-8f21-90b2d430776b`
updated_at: 2026-05-06T08:08:45+00:00
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
rollout_path: /Users/praise/.codex/sessions/2026/05/06/rollout-2026-05-06T16-06-54-019dfc53-5a1d-74f1-8f21-90b2d430776b.jsonl
rollout_summary_file: 2026-05-06T08-06-54-VaBl-rosetta_context_archive_mirror_check.md

---
description: Verified Rosetta context-archive and todo mirror files were identical, then extracted the authoritative continuation state for the Project Rosetta handoff.
task: read and verify Rosetta checkpoint/todo mirrors; summarize current handoff state
task_group: claude_history_rosetta_handoff
task_outcome: success
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
keywords: rosetta, checkpoint, todo, shasum, codex, claude history, mirror files, PRD, DECISIONS, prototype, xlsx, csv
---

### Task 1: Read and verify Rosetta mirror files

task: verify screenshot-mentioned Rosetta checkpoint/todo files and read the authoritative contents
task_group: claude_history_rosetta_handoff
task_outcome: success

Preference signals:
- when the user said `完整读一下`, they wanted the content read end-to-end before summarizing -> for similar context-handoff tasks, read all relevant files fully rather than giving a partial skim.
- when continuing Rosetta, the user emphasized Claude-side file/spec compatibility (`必须按 Claude 生成文件的规格和各种文件格式来，不要只放散文件`) -> similar handoff tasks should preserve structured file artifacts, not just conversational notes.

Reusable knowledge:
- The two Rosetta checkpoint paths were exact mirrors: both 82 lines and identical SHA-256 (`bd81e6dcf2043a2403f079bdc44c181ab71d280a0c9a8833fc6895869a081b5b`).
- The two todo paths were exact mirrors: both 11 lines and identical SHA-256 (`5d4ccc7ff6fde330191a1ffde68db13780752feec99182d7e6589b099d263bd3`).
- The checkpoint states that Rosetta’s current Project git status is clean, the hi-fi prototype baseline is at commit `8eb0a6b`, and the current business rules are already settled (local `xlsx/csv` only, write-back copy with `style` column, fixed 12 language headers, no alias headers, long translations do not resize frames, hidden layers are deleted, locked layers are unlocked before writing).
- The project-internal ignored checkpoint copy is not authoritative; Claude history / memory paths are the continuation source of truth.

Failures and how to do differently:
- No substantive failure occurred. For this kind of task, first prove file equivalence with hashes, then read the canonical copy and summarize; do not infer differences from path names alone.

References:
- `wc -l '/Users/praise/.claude/history/checkpoints/rosetta-context-archive-2026-05-06-interim.md'` -> `82`
- `wc -l '/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/history/checkpoints/rosetta-context-archive-2026-05-06-interim.md'` -> `82`
- `wc -l '/Users/praise/.claude/history/todos/2026-05-06.md'` -> `11`
- `wc -l '/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/history/todos/2026-05-06.md'` -> `11`
- Checkpoint SHA-256 mirror pair: `bd81e6dcf2043a2403f079bdc44c181ab71d280a0c9a8833fc6895869a081b5b`
- Todo SHA-256 mirror pair: `5d4ccc7ff6fde330191a1ffde68db13780752feec99182d7e6589b099d263bd3`

### Task 2: Extract Rosetta continuation state

task: summarize the current Rosetta handoff state from the verified checkpoint/todo files
task_group: claude_history_rosetta_handoff
task_outcome: success

Preference signals:
- The user accepted the approach of checking mirror files and then reading the canonical content, which suggests similar continuation tasks should prioritize verification and then summarize rather than jumping directly to implementation.

Reusable knowledge:
- Rosetta was explicitly at a “PRD / DECISIONS / hi-fi prototype already settled” stage, not yet at code implementation.
- The next natural step recorded in the todo is to either split an implementation plan from `PRD.md` / `DECISIONS.md` / the prototype, or to start the plugin source structure (`manifest.json`, `src/code.ts`, UI, xlsx/csv parsing, Figma scanning/classification, write-back generation, execution report module).
- The recovery file set to read first on the next continuation is the Claude checkpoint/memory/todo trio, then the project docs.

Failures and how to do differently:
- No failure; but a useful guardrail is to avoid treating mirrored files as extra signal. The real signal is the canonical Rosetta state and the prioritized next step.

References:
- The checkpoint’s listed recovery files and next-step hint: `docs/PRD.md`, `docs/DECISIONS.md`, `docs/rosetta-hi-fi-prototype.html`, and `docs/archive/rosetta-figma-rules-2026-04-28.md`.
- The todo item: `- [>] [Rosetta] 基于当前 PRD / DECISIONS / 高保真原型拆 Figma 插件实现计划，或启动插件源码结构 {rosetta,prd,prototype,implementation-plan}`

## Thread `019dfd42-5530-75f3-a81b-31eb064b0969`
updated_at: 2026-05-09T19:39:33+00:00
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
rollout_path: /Users/praise/.codex/sessions/2026/05/06/rollout-2026-05-06T20-27-56-019dfd42-5530-75f3-a81b-31eb064b0969.jsonl
rollout_summary_file: 2026-05-06T12-27-56-90pP-akb2_migration_root_and_toolbox_stage_priority.md

---
description: AKB2 工具库从旧 Codex 根迁移到 Project AKB2 后，工程根已确认，5 个工具 L1/floor closure 完成，但 L2 regression、Promotion Gate、Automation Gate 和 Search Quality 仍按阶段待办；迁移后优先先冻结基线再重跑 L2。
task: AKB2 migration root verification + toolbox stage prioritization
task_group: ai-infra / akb2
task_outcome: success
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project AKB2
keywords: AKB2, Project AKB2, migration, toolbox, L1, L2, automation gate, promotion gate, search quality, verify-no-drift, pytest, llama-swap, blocked_l2_verdict_blocked, blocked_insufficient_user_queries
---

### Task 1: Migrate root verification

task: identify migrated AKB2 engineering root and verify post-migration baseline

task_group: ai-infra / akb2

task_outcome: success

Preference signals:
- when the user said "迁移完了，你先读下迁移后的工作根目录，工具库接下来的任务优先级是什么，一共分几个阶段？" -> future similar runs should start with read-only root discovery and status confirmation before proposing next actions.
- when the user said "迁移完了" / "继续" after aborts -> future similar runs should treat migration as a state reset and re-check the authoritative root instead of relying on prior-path memory.

Reusable knowledge:
- `Project AKB2` is the authoritative engineering root after migration; Obsidian `AKB2.0` is display-only.
- The migration closure report explicitly says Project AKB2 is the unique maintenance directory for AKB2 engineering files and toolbox, replacing the old Codex container.
- `verify-no-drift.sh` is the practical post-migration consistency check for install targets / mirrors / closure-manifest.
- Post-migration sanity checks passed: `pytest -q` 60 passed, `scripts/verify-no-drift.sh` 17/17 MATCH, llama-swap health OK, 6 models visible.

Failures and how to do differently:
- Do not use the old `Codex/ai-infra/akb2-toolbox-*` directories as the working-root source of truth after migration.
- Do not infer completion from the existence of reports alone; inspect the actual recommendation / gate outputs.

References:
- `Project AKB2/README.md`: "AKB2.0 工程根：lint/gate/intake CLI + MCP wrapper + tests + eval harness + engineering docs（不含知识库本体）"
- `reports/migration/akb2-engineering-root-migration-closure-2026-05-09.md`: "Project AKB2 是 AKB2 工程文件和工具库的唯一权威维护目录，取代迁移前的旧 Codex 容器"
- `pytest -q` → `60 passed in 3.79s`
- `bash scripts/verify-no-drift.sh` → `all 17 checks MATCH`
- `curl -sf http://127.0.0.1:8080/health && curl -sf http://127.0.0.1:8080/v1/models | jq -r '.data[].id'` → `OK` + `bge-m3 gemma-3-4b nomic-embed qwen2.5-14b qwen3-32b qwen3-8b`

### Task 2: Stage prioritization after migration

task: determine post-migration toolbox priorities and stage count

task_group: ai-infra / akb2

task_outcome: success

Preference signals:
- when the user asked "工具库接下来的任务优先级是什么，一共分几个阶段？" -> future similar runs should answer in explicit phases, separating completed closure work from remaining gates.
- when the user said "迁移完再说" earlier -> after migration, default to base-line freeze before any new implementation or gate progression.

Reusable knowledge:
- `cc-local-llm` and `cc-skill-stocktake` L2 regression v1 are still blocked in `evals/l2-regression-v1/*/recommendation.json`.
- `src/akb2/promotion_gate/v0/README.md` says Promotion Gate v0 remains a placeholder until both L2 recommendations are `recommend_promote_L2` and the user explicitly starts it.
- `src/akb2/automation_gate/README.md` says Automation Gate v0 is implemented as a dry-run mechanism only; current global verdict remains `blocked_l2_verdict_blocked` and `would_create_automation=false`.
- `src/akb2/search_quality/v0/README.md` / `run-evidence.md` show Search Quality v0 is hard-blocked because there are no qualifying `user_observed` queries yet.
- A clean stage ordering after migration is: P0 baseline freeze → P1 L2 rerun → P2 grandfathered L2 evidence → P3 Promotion Gate → P4 Automation Gate → P5 Search Quality.

Failures and how to do differently:
- Do not confuse a completed mechanism or report with a pass condition; several stages are intentionally implemented but still blocked.
- Do not prioritize Search Quality ahead of L2 / promotion / automation while the official runbooks still mark it as deferred or blocked by insufficient queries.

References:
- `docs/runbooks/run-l2-regression.md`: `cc-local-llm` / `cc-skill-stocktake` already blocked, `cc-executable-plan` / `cc-review` grandfathered, `cc-akb-search` later
- `src/akb2/promotion_gate/v0/README.md`: preconditions and explicit user trigger for Promotion Gate v0
- `src/akb2/automation_gate/README.md`: `global_verdict = blocked_l2_verdict_blocked`, `would_create_automation = false`
- `src/akb2/search_quality/v0/README.md` and `src/akb2/search_quality/v0/run-evidence.md`: `blocked_insufficient_user_queries`
- `evals/l2-regression-v1/cc-local-llm/recommendation.json` and `evals/l2-regression-v1/cc-skill-stocktake/recommendation.json`: `blocked`

## Thread `019e151d-35c0-73e0-86d6-21843261a3b8`
updated_at: 2026-05-11T07:43:34+00:00
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
rollout_path: /Users/praise/.codex/archived_sessions/rollout-2026-05-11T11-38-16-019e151d-35c0-73e0-86d6-21843261a3b8.jsonl
rollout_summary_file: 2026-05-11T03-38-16-cCF2-akb2_deep_read_graph_priority_and_x_cli.md

---
description: Deep read of AKB2.0 vault and downstream design synthesis: canonical AKB2.0 root, strict three-layer knowledge architecture, concept-graph/query-feedback priorities, and discovered local twitter CLI already installed and authenticated for reading X article posts.
task: Read AKB2.0; rank improvement tasks and define functional granularity; read 2 X posts after validating x/twitter CLI
task_group: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
 task_outcome: success
cwd: /Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/Praise Space/AKB2.0
keywords: AKB2.0, Obsidian vault, CONTENT-STANDARD, FOLDER-STRUCTURE, GRAPH-LINKING, AI-QUERY-CONTRACT, QUERY-WRITEBACK, lint, concept graph, query feedback loop, passive ingest, daily brief, weekly synthesis, twitter-cli, x cli, articleText, evidence_paths, graph_context
---

### Task 1: Read AKB2.0 deeply

task: inspect AKB2.0 vault architecture, standards, reports, and active concept state
task_group: knowledge-vault review
task_outcome: success

Preference signals:
- user asked "详细读下 akb2 项目" -> default should be broad project orientation before recommendations

Reusable knowledge:
- canonical AKB2.0 root is in the user’s Obsidian vault: `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/Praise Space/AKB2.0/`
- AKB2.0 is a three-layer knowledge system (`raw/`, `wiki/`, `docs/`) with support layers (`staging/`, `manifests/`, `toolbox/`, `archive/`)
- active concept graph already includes `concept-plan-and-execute` and `concept-agent-collaboration`; current graph work is moving from definition into operationalization
- `toolbox/registry|interfaces|evals` are machine-interface assets, not ordinary knowledge articles

Failures and how to do differently:
- a full recursive grep created excessive output; future audits should start with targeted standards/reports and only expand if needed
- `.akb-runtime/lint/akb2-lint.py` was referenced by reports but absent in the AKB2.0 root during this rollout; treat that as a drift/risk signal and verify before assuming the runner location

References:
- `docs/AKB-2.0-CONTENT-STANDARD.md`
- `docs/AKB-2.0-FOLDER-STRUCTURE.md`
- `docs/AKB-2.0-AI-QUERY-CONTRACT.md`
- `docs/AKB-2.0-QUERY-WRITEBACK.md`
- `docs/AKB-2.0-GRAPH-LINKING.md`
- `docs/phase-d-reports/akb2-census-week-2026-05-08.md`
- `docs/phase-d-reports/bl-d-014-source-recensus-2026-05-08.md`
- `docs/phase-d-reports/bl-d-014-concept-build-2026-05-08.md`
- `docs/phase-d-reports/lint-cli-v0.3-2026-05-10T004027.md`

### Task 2: Rank tasks and define granularity

task: prioritize index repair, self-healing lint, query feedback loop, hybrid search, knowledge-compounding ingest, and graph upgrade; specify functional grain
task_group: roadmap design
task_outcome: success

Preference signals:
- the user asked for task priority, then clarified they meant the functionality’s required granularity -> future responses should provide both ordering and acceptance grain
- the user then asked to re-summarize priority + grain -> future agents should be ready to restate the plan more cleanly, not just answer once

Reusable knowledge:
- best dependency order found: `索引层` -> `自愈 lint` -> `查询反馈闭环`/`概念图谱升级` -> `知识复利式 ingest` -> `混合检索`
- acceptance grain should be page-level / rule-level / query-level / node-edge-path-level rather than generic “AI assisted” behavior
- daily/weekly synthesis should be treated as the first real output surface for query feedback loops

Failures and how to do differently:
- initial answers were too abstract; future agents should proactively specify the minimum usable unit for each feature (index row, lint finding, query feedback unit, edge, snippet)
- graph/lint scope drift can happen when machine-interface pages are treated as wiki pages; future agents should segregate scopes before judging health

References:
- `docs/AKB-2.0-GRAPH-LINKING.md`
- `docs/AKB-2.0-AI-QUERY-CONTRACT.md`
- `docs/AKB-2.0-PAGE-TEMPLATES.md`
- `manifests/graph/pending-nodes-2026-05-04.jsonl`
- `docs/phase-d-reports/bl-d-014-concept-build-2026-05-08.md`

### Task 3: Read X posts via existing CLI

task: verify/install x CLI if needed, then read two X article posts and extract implications for AKB2.0 / LLM Wiki
task_group: external content review
task_outcome: success

Preference signals:
- user said "那你装一下 x 的 cli" and later asked to read the posts once the CLI was ready -> future agents should check for an existing local CLI before installing anything
- user expected the posts to be turned into design insight for Karpathy/AKB2.0, not a simple summary -> future agents should translate external content into operational implications

Reusable knowledge:
- `twitter-cli` is already installed at `/Users/praise/.local/bin/twitter`, version `0.8.5`, and authenticated
- X article content can be pulled directly via `twitter tweet <url> --json -n 20`
- The two posts strongly reinforce passive ingest, AGENTS.md/CLAUDE.md as instruction layers, and daily/weekly feedback loops
- The posts also surface a key caution: automatic pattern-linking can hallucinate cross-domain structure, so AKB2.0’s graph must remain evidence- and gate-governed

Failures and how to do differently:
- one fetch already produced the article body, but to inspect full reply context the CLI JSON pull was still needed; future agents should fetch JSON once and inspect `articleText` plus replies in one pass
- social-post evidence should be clearly labeled as inspiration, not as a substitute for AKB2.0 standards

References:
- `~/.local/bin/twitter`
- `twitter-cli 0.8.5`
- `https://x.com/cyrilXBT/status/2052235121416188114`
- `https://x.com/ziwenxu_/status/2053241837453029439`
- article titles: `How to Build an Obsidian Knowledge Vault That Gets Smarter Every Day Without You Doing Anything`; `How to Build Codex Knowledge Vault That Gets Smarter Every Day Without You Doing Anything`

## Thread `019e26a7-b148-7140-8098-a4693ac1f620`
updated_at: 2026-05-14T16:21:12+00:00
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
rollout_path: /Users/praise/.codex/archived_sessions/rollout-2026-05-14T21-23-04-019e26a7-b148-7140-8098-a4693ac1f620.jsonl
rollout_summary_file: 2026-05-14T13-23-04-Ih0s-obsidian_claudian_stale_key_cleanup.md

---
description: Removed stale Claudian/Obsidian Anthropic key drift by tracing the real active storage layers, moving live credentials out of iCloud-synced config, and using launchctl + per-machine env to prevent cross-device re-injection; verified the current key works.
task: remove stale Anthropic API key/token from Obsidian Claudian and replace with current Claude key
task_group: obsidian-vault
task_outcome: success
cwd: /Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents
keywords: Obsidian, Claudian, Anthropic, API key, token, launchctl, .claudian, data.json, CloudKit, iCloud sync, launchd, macOS GUI env, 401, LiteLLM_VerificationTokenTable, llm-proxy
---

### Task 1: Find and replace stale Claudian/Obsidian Anthropic credentials

task: remove stale Anthropic API key/token from Obsidian Claudian and replace with current Claude key
task_group: obsidian-vault
task_outcome: success

Preference signals:
- user said the old key may have been re-injected by cross-device login and asked to “把旧的 key 和 token 删掉 换成目前 claude用的 key” -> future runs should assume cross-device sync drift and search multiple persistence layers, not just the obvious config file
- user later said “好像还是不行 查查 / 彻查” -> future runs should widen the search to launchd GUI env, Obsidian/Electron caches, and legacy config files when the first fix does not take
- user asked “能把旧的 key 全部删掉么” -> future runs should be willing to remove old key material from backups/history/caches when authorized, not only the active config
- user asked “那我家里的电脑登录就会产生新的 token 怎么处理？” -> future runs should address cross-device behavior directly and explain how to prevent iCloud or other sync sources from reintroducing the stale credential

Reusable knowledge:
- Claudian’s active runtime environment is the merge of process env + its own stored environment strings; the plugin code reads `sharedEnvironmentVariables` and provider `environmentVariables`, then passes `env: { ...process.env, ...ctx.customEnv, PATH: ... }` into the Claude process
- The real active storage path is `.claudian/claudian-settings.json`; `.claude/claudian-settings.json` is legacy/backup territory
- For this setup, `launchctl` is the right place to set GUI-visible Anthropic env vars on macOS, and `ANTHROPIC_AUTH_TOKEN` can be intentionally unset when the setup should only use `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL` was consistently `https://llm-proxy.tapsvc.com`
- The current usable key suffix was `5V6w`; the stale key suffix was `vD9Q`

Failures and how to do differently:
- The first pass failed because it only updated the plugin config, but Obsidian GUI apps inherit `launchctl` environment and Claudian also reads legacy `.claudian/claudian-settings.json`; future cleanup should check those before assuming the plugin data file is authoritative
- A later pass found the stale key still present in iCloud/CloudKit and Claude history/cache; the effective fix was to separate active config from historical residues and treat history/cache as redaction targets, not configuration sources
- `launchctl getenv` is the relevant place to check for Finder/Dock-launched GUI apps; `.zshrc` alone is insufficient for Obsidian on macOS

References:
- Active plugin config: `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.obsidian/plugins/claudian/data.json`
- Legacy active Claudian settings: `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.claudian/claudian-settings.json`
- Current shell/launchd key verification: `launchctl ANTHROPIC_API_KEY=sk-LY7WFL...5V6w`, `launchctl ANTHROPIC_AUTH_TOKEN=`
- Successful auth probe: `GET https://llm-proxy.tapsvc.com/v1/models` returned status `200`
- Obsidian process restart and re-launch were required for GUI env changes to take effect

### Task 2: Remove old key from synced legacy storage and explain cross-device behavior

task: delete old key remnants and prevent cross-device re-injection via synced config
task_group: obsidian-vault
task_outcome: success

Preference signals:
- user asked whether a family computer login would produce a new token and how to handle that -> future runs should explain that local deletion alone does not revoke the server-side credential, and should recommend revoking the old key at the provider
- user asked to delete the old key “全部” -> future runs should prefer a clean architecture where synced vault files do not contain secrets, and local machine-specific env supplies the live credential

Reusable knowledge:
- Claudian can operate with synced config containing only `ANTHROPIC_BASE_URL`, while the actual API key comes from the machine’s environment
- For multi-device use, the server-side old key/token should be revoked/removed in the provider console; local cleanup alone prevents reuse on the Mac but does not invalidate a compromised key everywhere

Failures and how to do differently:
- Do not store live Anthropic credentials in iCloud-synced vault config when the same vault is used on multiple Macs; that can reintroduce stale values after cross-device login
- The durable fix is to keep only non-secret transport config in sync and source secrets from per-machine local env/launchctl

References:
- Final synced files contain no API key/token fields: `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.claudian/claudian-settings.json`, `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.obsidian/plugins/claudian/data.json`
- Current machine env after cleanup: `ANTHROPIC_API_KEY` suffix `5V6w`, `ANTHROPIC_AUTH_TOKEN` unset, `ANTHROPIC_BASE_URL=https://llm-proxy.tapsvc.com`
- Stale key/hash no longer found outside the live Codex cache/WAL area after cleanup

## Thread `019e2730-bb54-7e41-8608-65a586ab573c`
updated_at: 2026-05-15T20:07:51+00:00
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
rollout_path: /Users/praise/.codex/archived_sessions/rollout-2026-05-14T23-52-45-019e2730-bb54-7e41-8608-65a586ab573c.jsonl
rollout_summary_file: 2026-05-14T15-52-45-U6Ti-project_gd_window_handoff_skill.md

---
description: User likes durable cross-window handoff artifacts for long Project GD / AKB2 sessions, and asked to turn the handoff template into a local Codex skill triggered by “交接窗口”.
task: write a context-handoff markdown file and then create a local Codex skill for handoff generation
task_group: codex_skills_and_handoffs
task_outcome: success
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex
keywords: context handoff, window transfer, Codex skill, cc-window-handoff, 交接窗口, reports, Project GD, AKB2, cross-window continuation
---

### Task 1: Context handoff file

task: create a durable handoff markdown file for Project GD / AKB2 continuation

task_group: project-gd-handoff

task_outcome: success

Preference signals:
- user asked “上下文满了如何进行窗口交接” and then “那你写啊” -> when context is getting full, default to writing the handoff file rather than only explaining the method
- user said the new window should “只读这个文件 + 权威根目录” and “不要靠聊天记录” -> make the handoff file the authority source for continuation
- user required the handoff to include current state, boundaries, evidence, next step, and a new-window prompt -> keep those sections by default

Reusable knowledge:
- for this project, the handoff file is useful as a single-source continuation artifact with authority roots, hard boundaries, current state, key artifacts, open risks, decision state, next action, and a copyable new-window prompt
- verified file location used: `reports/gd-context-handoff-2026-05-16-live-gd-review.md`
- verification was read-only (`wc -l`, `sed -n`) after writing

Failures and how to do differently:
- avoid relying on narrative chat summaries for continuation; write the file immediately when asked for a window handoff
- keep the file operational and concise; the value is in the facts and next action, not in long explanation

References:
- `reports/gd-context-handoff-2026-05-16-live-gd-review.md`
- file verification showed 309 lines and readable first 40 lines
- the file explicitly warns not to modify `/Users/praise/.claude` unless authorized

### Task 2: Codex skill creation

task: turn the handoff template into a local Codex skill triggered by “交接窗口”

task_group: codex-skill-creation

task_outcome: success

Preference signals:
- user explicitly requested “把你刚才做的交接模板 做成 codex skill，触发词‘交接窗口’” -> future continuation workflows can be packaged as a local skill instead of being one-off instructions
- user later asked “完成了么” after the first file was written -> for multi-file skill creation, check that the minimal required set is complete before answering done

Reusable knowledge:
- this environment’s skills use `SKILL.md` plus optional `agents/openai.yaml`; no extra README/quick reference files are needed for a small utility skill
- the created skill lives at `/Users/praise/.codex/skills/cc-window-handoff/`
- the skill description should explicitly include the Chinese trigger `交接窗口` and related phrases like `上下文满了`, `开新窗口继续`, `写交接`, `handoff`, `context handoff`
- the skill’s purpose is to generate a durable Markdown handoff plus a copyable new-window prompt, not to preserve chat history

Failures and how to do differently:
- first pass wrote only `SKILL.md`; a follow-up user question revealed the missing `agents/openai.yaml` metadata, so future skill creation should verify both files up front
- keep the skill body lean and operational; if richer examples are needed later, put them in a references file rather than bloating `SKILL.md`

References:
- `/Users/praise/.codex/skills/cc-window-handoff/SKILL.md`
- `/Users/praise/.codex/skills/cc-window-handoff/agents/openai.yaml`
- directory check showed only those two files in the skill folder

