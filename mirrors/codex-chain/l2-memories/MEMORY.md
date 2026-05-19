# Task Group: Cross-window handoff files and Codex skill packaging for Project GD / AKB2 continuations

scope: Preserve cross-window continuation state as a durable Markdown handoff file, then package that workflow as a local Codex skill when the user wants a reusable trigger like "交接窗口".
applies_to: cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex; reuse_rule=safe for Codex-root continuation and handoff tasks that bridge into Project GD or AKB2 worktrees; re-check the current authority roots and hard boundaries if the target project or review state has changed.

## Task 1: Write a durable Project GD / AKB2 handoff file for the next window, success

### rollout_summary_files

- rollout_summaries/2026-05-14T15-52-45-U6Ti-project_gd_window_handoff_skill.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/archived_sessions/rollout-2026-05-14T23-52-45-019e2730-bb54-7e41-8608-65a586ab573c.jsonl, updated_at=2026-05-15T20:07:51+00:00, thread_id=019e2730-bb54-7e41-8608-65a586ab573c, durable handoff file plus read-only verification)

### keywords

- context handoff, window transfer, 交接窗口, 上下文满了, 只读这个文件, 不要靠聊天记录, reports/gd-context-handoff-2026-05-16-live-gd-review.md, Project GD, AKB2, next-window prompt, do not modify /Users/praise/.claude

## Task 2: Package the handoff workflow as a local Codex skill, success

### rollout_summary_files

- rollout_summaries/2026-05-14T15-52-45-U6Ti-project_gd_window_handoff_skill.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/archived_sessions/rollout-2026-05-14T23-52-45-019e2730-bb54-7e41-8608-65a586ab573c.jsonl, updated_at=2026-05-15T20:07:51+00:00, thread_id=019e2730-bb54-7e41-8608-65a586ab573c, local skill packaging for reusable handoff trigger)

### keywords

- cc-window-handoff, Codex skill, SKILL.md, agents/openai.yaml, 交接窗口, 开新窗口继续, 写交接, handoff, context handoff, display_name, minimal skill files

## User preferences

- when context is getting full or continuation spans windows, the user asked "上下文满了如何进行窗口交接" and then "那你写啊" -> default to writing the handoff file immediately instead of only explaining the method [Task 1]
- when the user said the next window should "只读这个文件 + 权威根目录" and "不要靠聊天记录" -> make the handoff file the authority source for continuation, with chat history only as fallback context [Task 1]
- when the user required "当前事实、边界、证据、下一步、新窗口提示词" -> keep those sections in cross-window handoff files by default rather than producing a short narrative summary [Task 1]
- when the user explicitly requested "把你刚才做的交接模板 做成 codex skill，触发词‘交接窗口’" -> if a continuation workflow is likely to recur, consider packaging it as a local skill rather than leaving it as one-off instructions [Task 2]
- when the user followed up with "完成了么" after the first file was written -> for small local-skill creation, verify the minimal required file set before answering that the work is done [Task 2]

## Reusable knowledge

- For this Project GD / AKB2 continuation pattern, the handoff file should act as a single-source artifact containing authority roots, hard boundaries, current state, key evidence paths, decision state, next action, and a copyable new-window prompt [Task 1]
- The verified handoff path used in this rollout was `reports/gd-context-handoff-2026-05-16-live-gd-review.md`; verification stayed read-only via `wc -l` and `sed -n` after writing [Task 1]
- The handoff explicitly preserved the hard boundary `Do not modify /Users/praise/.claude unless explicitly authorized`, which matters when the continuation touches Codex/Claude state [Task 1]
- In this environment, a small local Codex skill can stay minimal: `SKILL.md` plus `agents/openai.yaml` were sufficient for the created `cc-window-handoff` skill [Task 2]
- The stable trigger phrases for this skill family were `交接窗口`, `上下文满了`, `开新窗口继续`, `写交接`, `handoff`, and `context handoff`; the output contract is "durable Markdown handoff file + new-window prompt", not chat-history preservation [Task 2]

## Failures and how to do differently

- Symptom: a handoff request turns into explanation-only guidance. Cause: treating "how to hand off" as a theoretical question instead of an artifact request. Fix: if the user asks in the context of an active thread and especially says "那你写啊", write the handoff file immediately [Task 1]
- Symptom: continuation state becomes chat-dependent or too narrative. Cause: relying on conversational summary instead of a fact-first handoff file. Fix: keep the handoff concise and operational, with authority roots, boundaries, evidence, current state, next step, and a copyable prompt [Task 1]
- Symptom: a skill-creation task looks done after only `SKILL.md`. Cause: not checking the environment's minimal metadata expectations. Fix: verify both `SKILL.md` and `agents/openai.yaml` before reporting completion for a small local skill [Task 2]

# Task Group: Codex workspace operating model, artifact routing, and productization-before-testing

scope: Clarify what work in the Codex workspace should default to, especially when deciding between planning/review tasks, direct implementation, and workflows where a runnable artifact must exist before meaningful testing.
applies_to: cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex; reuse_rule=safe for future work in the Codex workspace root when deciding task ownership, artifact placement, whether Codex should implement or stay in a plan/review role, and whether local productization should precede testing.

## Task 1: Set the Codex workspace default role to upstream planning and downstream review, clarified

### rollout_summary_files

- extensions/ad_hoc/notes/2026-05-15T18-48-42-codex-plan-review-control-plane.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=extensions/ad_hoc/notes/2026-05-15T18-48-42-codex-plan-review-control-plane.md, updated_at=2026-05-15, thread_id=ad-hoc-note-2026-05-15-codex-plan-review-control-plane, workspace operating-model clarification from authoritative extension note)

### keywords

- Codex workspace, control plane, task plans, review Claude outputs, AGENTS.md, README.md, references/codex-plan-review-operating-model.md, plans/, reviews/, references/, history/, archive/, ai-infra/, plugins/, primary implementation

## Task 2: Prefer getting to a usable installed/runnable artifact before testing when the workflow depends on it, clarified

### rollout_summary_files

- extensions/ad_hoc/notes/2026-05-17T14-01-15Z-finish-product-before-testing.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=extensions/ad_hoc/notes/2026-05-17T14-01-15Z-finish-product-before-testing.md, updated_at=2026-05-17, thread_id=ad-hoc-note-2026-05-17-finish-product-before-testing, authoritative workflow-order preference from extension note)

### keywords

- 我永远希望尽快做成成品再测, finish product before testing, installed artifact, runnable artifact, local hand testing, circular gate, install before test, productized state, final acceptance

## User preferences

- when working in `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex`, the user clarified that Codex should "produce task plans and review Claude outputs" -> default to plan/review work in this workspace instead of assuming Codex is the primary implementer [Task 1]
- when future work is in the Codex workspace root, the user’s rule was that Codex "should not default to primary implementation work unless the user explicitly asks Codex to implement" -> require an explicit implementation ask before turning a Codex-root task into direct product/code implementation [Task 1]
- when organizing durable outputs in the Codex workspace, the user codified directory expectations through workspace rules -> route artifacts into `plans/`, `reviews/`, `references/`, `history/`, `archive/`, `ai-infra/`, or `plugins/` instead of leaving outputs in ad-hoc locations [Task 1]
- when the workflow cannot be tested meaningfully until something is installable/runnable, the user explicitly said "我永远希望尽快做成成品再测" -> get to a usable local artifact quickly, then test, instead of creating a test-first circular gate [Task 2]
- when a task needs "install for local hand testing" before the user can validate it, treat that install/parity step as distinct from "final release/live closure/commit" and do not block local usability on final acceptance criteria [Task 2]

## Reusable knowledge

- The Codex workspace’s primary operating model is a control-plane role: Codex plans upstream work for Claude or other implementers, then reviews and accepts or rejects Claude outputs downstream [Task 1]
- The operating-model rule was codified in `AGENTS.md`, `README.md`, and `references/codex-plan-review-operating-model.md`; these are the first authority files to check when a Codex-root task seems ambiguous about whether to plan, review, or implement [Task 1]
- Direct implementation in the Codex workspace is still valid when the user explicitly asks Codex to implement, or when the task is organizing the Codex workspace itself [Task 1]
- The intended artifact-routing buckets for this workspace are `plans/`, `reviews/`, `references/`, `history/`, `archive/`, `ai-infra/`, and `plugins/`; use them as the default output map for durable deliverables [Task 1]
- For workflows that require a usable installed/runnable artifact before testing can say anything meaningful, local productization is allowed to come before the testing pass; do not force a test gate that depends on the artifact not yet existing [Task 2]
- Keep the distinction explicit between "install for local hand testing" and "final release/live closure/commit": the former can be a prerequisite for evaluation, while final acceptance still happens after the user’s hands-on test [Task 2]

## Failures and how to do differently

- Symptom: Codex-root work drifts into primary implementation by default. Cause: treating `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex` like a general build repo instead of a plan/review control plane. Fix: check the operating-model docs first and stay in planning/review mode unless the user explicitly asks for implementation [Task 1]
- Symptom: durable artifacts end up scattered or ambiguous. Cause: not applying the workspace routing rules. Fix: place outputs into the codified buckets (`plans/`, `reviews/`, `references/`, `history/`, `archive/`, `ai-infra/`, `plugins/`) as the default structure [Task 1]
- Symptom: a task gets stuck in "test before install" or "prove before runnable" loops. Cause: treating final verification requirements as prerequisites for creating the artifact that makes testing possible. Fix: first reach a usable installed/runnable local state, then test from that state [Task 2]
- Symptom: local hand-testing is blocked by release-grade closure requirements. Cause: collapsing "install for local hand testing" and "final release/live closure/commit" into one gate. Fix: separate local parity/usability from final acceptance, and let the former happen earlier when the workflow requires it [Task 2]

# Task Group: Obsidian vault Claudian credential drift cleanup and cross-device secret handling

scope: Diagnose and remove stale Claudian/Obsidian Anthropic credentials, especially when iCloud-synced config or macOS GUI environment re-injects old values across devices.
applies_to: cwd=/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents; reuse_rule=safe for future Obsidian/Claudian credential-drift or secret-storage cleanup tasks in this vault family; re-check paths and current provider/base-url settings if the plugin layout or auth flow has changed.

## Task 1: Find and replace stale Claudian/Obsidian Anthropic credentials, success

### rollout_summary_files

- rollout_summaries/2026-05-14T13-23-04-Ih0s-obsidian_claudian_stale_key_cleanup.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/archived_sessions/rollout-2026-05-14T21-23-04-019e26a7-b148-7140-8098-a4693ac1f620.jsonl, updated_at=2026-05-14T16:21:12+00:00, thread_id=019e26a7-b148-7140-8098-a4693ac1f620, active storage + GUI env traced and current key verified)

### keywords

- Obsidian, Claudian, Anthropic, API key, token, launchctl, .claudian, claudian-settings.json, data.json, CloudKit, iCloud sync, launchd, macOS GUI env, 401, LiteLLM_VerificationTokenTable, llm-proxy

## Task 2: Remove old key from synced legacy storage and explain cross-device behavior, success

### rollout_summary_files

- rollout_summaries/2026-05-14T13-23-04-Ih0s-obsidian_claudian_stale_key_cleanup.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/archived_sessions/rollout-2026-05-14T21-23-04-019e26a7-b148-7140-8098-a4693ac1f620.jsonl, updated_at=2026-05-14T16:21:12+00:00, thread_id=019e26a7-b148-7140-8098-a4693ac1f620, synced secret removal + multi-device prevention guidance)

### keywords

- Obsidian, Claudian, iCloud-synced config, cross-device login, launchctl, ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL, .claudian/claudian-settings.json, provider console, revoke old key

## User preferences

- when the user said the old key may have been re-injected by another device and asked: "把旧的 key 和 token 删掉 换成目前 claude用的 key" -> treat cross-device sync drift as a likely cause and search multiple persistence layers, not just the obvious plugin config [Task 1]
- when the user said "好像还是不行 查查 / 彻查" -> widen the search to launchd GUI env, Obsidian/Electron caches, and legacy config files instead of assuming the first config edit was authoritative [Task 1]
- when the user asked "能把旧的 key 全部删掉么" -> if authorized, remove stale credential material from active config plus backups/history/caches, not only the currently loaded file [Task 1][Task 2]
- when the user asked "那我家里的电脑登录就会产生新的 token 怎么处理？" -> explain cross-device behavior directly, including the difference between local cleanup and server-side revocation, and how to prevent synced config from reintroducing stale secrets [Task 1][Task 2]

## Reusable knowledge

- Claudian’s effective runtime environment is the merge of process env plus its stored environment strings; the plugin reads `sharedEnvironmentVariables` and provider `environmentVariables`, then launches Claude with merged env, so both stored config and macOS GUI env can be active at once [Task 1]
- The active storage path in this vault family was `.claudian/claudian-settings.json`; `.claude/claudian-settings.json` was legacy/backup territory and should not be treated as the primary config source without verification [Task 1]
- For Finder/Dock-launched Obsidian on macOS, `launchctl` is the relevant place to inspect and set GUI-visible Anthropic variables; shell startup files alone are insufficient [Task 1]
- The live setup worked with synced config containing only `ANTHROPIC_BASE_URL`, while the actual API key came from per-machine environment rather than iCloud-synced vault files [Task 1][Task 2]
- `https://llm-proxy.tapsvc.com` was the consistent `ANTHROPIC_BASE_URL` in this setup, and a successful `GET /v1/models` probe after restart was the concrete verification that the current credential path worked [Task 1]
- For multi-device use, local deletion prevents reuse on that Mac, but old provider credentials should still be revoked in the provider console if the goal is to invalidate them everywhere [Task 2]

## Failures and how to do differently

- Symptom: editing the plugin data file did not fix the stale key. Cause: Obsidian GUI apps inherit `launchctl` env and Claudian also reads legacy `.claudian/claudian-settings.json`. Fix: check plugin config, `.claudian/claudian-settings.json`, and `launchctl getenv` before assuming one file is authoritative [Task 1]
- Symptom: stale key material still appears after the active config is fixed. Cause: iCloud/CloudKit mirrors, history, and caches preserved historical residues. Fix: separate active configuration sources from redaction targets and scrub only the latter when the user authorizes broader cleanup [Task 1]
- Symptom: stale credentials return after cross-device login. Cause: live secrets were stored in iCloud-synced vault config. Fix: keep only non-secret transport config in sync and source secrets from per-machine local env/launchctl [Task 2]

# Task Group: AKB2.0 vault deep-read, prioritization, and X article extraction

scope: Deep-read orientation for the Obsidian AKB2.0 knowledge system, dependency-ranked improvement planning, and reuse of the local X/Twitter CLI for article-style post reads.
applies_to: cwd=/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/Praise Space/AKB2.0; reuse_rule=safe for future AKB2.0 vault exploration, standards reading, and X-post reading tasks; re-check paths if working outside the Obsidian vault or if CLI/auth state may have changed.

## Task 1: Read AKB2.0 deeply and establish the canonical vault model, success

### rollout_summary_files

- rollout_summaries/2026-05-11T03-38-16-cCF2-akb2_deep_read_graph_priority_and_x_cli.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/archived_sessions/rollout-2026-05-11T11-38-16-019e151d-35c0-73e0-86d6-21843261a3b8.jsonl, updated_at=2026-05-11T07:43:34+00:00, thread_id=019e151d-35c0-73e0-86d6-21843261a3b8, canonical root + standards/report orientation)

### keywords

- AKB2.0, Obsidian vault, AKB-2.0-CONTENT-STANDARD.md, AKB-2.0-FOLDER-STRUCTURE.md, AKB-2.0-AI-QUERY-CONTRACT.md, AKB-2.0-QUERY-WRITEBACK.md, GRAPH-LINKING, concept-plan-and-execute, concept-agent-collaboration, .akb-runtime/lint/akb2-lint.py

## Task 2: Rank improvement tasks and define required functional grain, success

### rollout_summary_files

- rollout_summaries/2026-05-11T03-38-16-cCF2-akb2_deep_read_graph_priority_and_x_cli.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/archived_sessions/rollout-2026-05-11T11-38-16-019e151d-35c0-73e0-86d6-21843261a3b8.jsonl, updated_at=2026-05-11T07:43:34+00:00, thread_id=019e151d-35c0-73e0-86d6-21843261a3b8, dependency order + acceptance grain)

### keywords

- 索引层, 自愈 lint, 查询反馈闭环, 概念图谱升级, 知识复利式 ingest, 混合检索, graph_context, pending-nodes-2026-05-04.jsonl, page-level, rule-level, query-level, node-edge-path-level

## Task 3: Validate local X/Twitter CLI and read two article-style posts, success

### rollout_summary_files

- rollout_summaries/2026-05-11T03-38-16-cCF2-akb2_deep_read_graph_priority_and_x_cli.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/archived_sessions/rollout-2026-05-11T11-38-16-019e151d-35c0-73e0-86d6-21843261a3b8.jsonl, updated_at=2026-05-11T07:43:34+00:00, thread_id=019e151d-35c0-73e0-86d6-21843261a3b8, local CLI check before article extraction)

### keywords

- twitter-cli, /Users/praise/.local/bin/twitter, twitter-cli 0.8.5, PraiseZhu52, articleText, x.com/cyrilXBT, x.com/ziwenxu_, passive ingest, daily/weekly synthesis, AGENTS.md, CLAUDE.md

## User preferences

- when reading a project like AKB2.0, the user asked: "详细读下 akb2 项目" -> start with broad orientation across standards, structure, and current reports before proposing changes or priorities [Task 1]
- when asking for roadmap advice, the user asked: "排个任务优先级" and then clarified "我指的是这几项任务对应的功能，所要达到的颗粒度标准" -> answer in two layers: dependency order first, then the concrete acceptance grain for each item [Task 2]
- when the user asked to "重新汇总下任务优先级及颗粒度标准" -> be ready to restate the same plan more cleanly and compactly after the first pass instead of treating the earlier answer as final [Task 2]
- when the user asked to read X posts and later suggested installing the CLI, they were satisfied after a local tool check + article read -> check for existing local tooling and auth first instead of assuming installation work is needed [Task 3]
- when outside sources are used to inform design, the user’s follow-up shifted back to "标准" and "颗粒度" -> extract operational implications, not just summaries of the external posts [Task 2][Task 3]

## Reusable knowledge

- The canonical AKB2.0 root is `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/Praise Space/AKB2.0/`; treat it as an Obsidian-backed knowledge engineering system rather than a conventional code repo with one runtime entrypoint [Task 1]
- The vault uses a strict three-layer model: `raw/` immutable evidence, `wiki/` active synthesized knowledge, `docs/` schema/standards, with `staging/`, `manifests/`, `toolbox/`, and `archive/` as support layers; `toolbox/registry|interfaces|evals` are machine-interface assets, not ordinary knowledge pages [Task 1]
- The active concept graph was already past initial definition: `concept-plan-and-execute` and `concept-agent-collaboration` were active, so the more relevant upgrade target was operationalization rather than “should there be a graph at all” [Task 1][Task 2]
- A useful dependency order for the requested system improvements was: `索引层` -> `自愈 lint` -> `查询反馈闭环` / `概念图谱升级` -> `知识复利式 ingest` -> `混合检索` [Task 2]
- For AKB2.0, acceptance grain should be expressed as auditable units such as page-level, rule-level, query-level, and node-edge-path-level, not vague “AI assisted” behavior [Task 2]
- Graph upgrades should start with compute-and-report layers such as nodes, edges, paths, orphan/bridge/hub status, and `graph_context` construction before heavier storage/search work [Task 2]
- The local X reader was already available: `/Users/praise/.local/bin/twitter` -> `twitter-cli 0.8.5`, authenticated for `PraiseZhu52`; future similar reads should use the installed CLI directly rather than reinstalling [Task 3]
- The two X posts were useful as workflow inspiration for passive ingest and daily/weekly synthesis, but they do not override AKB2.0’s stricter evidence/gate rules [Task 3]

## Failures and how to do differently

- Symptom: huge noisy exploration output. Cause: full recursive `rg` over the whole workspace. Fix: start with targeted standards/reports/file lists, then zoom in by topic only if needed [Task 1]
- Symptom: roadmap answer felt too high-level. Cause: the first synthesis gave ordering without exact acceptance grain. Fix: define the functional grain proactively whenever the user asks for priorities in this project [Task 2]
- Symptom: lint/report drift risk. Cause: reports referenced `.akb-runtime/lint/akb2-lint.py`, but that path was absent in the AKB2.0 root during the rollout. Fix: verify runner locations before treating them as stable repo facts [Task 1]
- Symptom: quality judgments can be skewed. Cause: machine-interface pages (`toolbox/registry`, `interfaces`, `evals`) may get scanned with ordinary wiki-page rules. Fix: isolate scope before evaluating lint or content quality [Task 2]
- Symptom: X content may appear incomplete. Cause: the short post body may omit the useful article text or thread context. Fix: fetch the fuller JSON/article payload once and inspect fields like `articleText` instead of assuming the visible tweet text is enough [Task 3]

# Task Group: Project AKB2 migration root verification and post-migration stage ordering

scope: Migration-era AKB2 engineering-root discovery, baseline verification, and stage gating after the toolbox moved out of the old Codex container.
applies_to: cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Claude Code/Project AKB2; reuse_rule=safe for post-migration AKB2 engineering tasks when validating the current authoritative root and stage gates; re-check if another migration or root move has happened.

## Task 1: Identify the migrated AKB2 engineering root and verify the baseline, success

### rollout_summary_files

- rollout_summaries/2026-05-06T12-27-56-90pP-akb2_migration_root_and_toolbox_stage_priority.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/sessions/2026/05/06/rollout-2026-05-06T20-27-56-019dfd42-5530-75f3-a81b-31eb064b0969.jsonl, updated_at=2026-05-09T19:39:33+00:00, thread_id=019dfd42-5530-75f3-a81b-31eb064b0969, migration closure + baseline checks)

### keywords

- Project AKB2, migration, engineering root, verify-no-drift.sh, pytest -q, llama-swap, /v1/models, 60 passed, all 17 checks MATCH, unique maintenance directory

## Task 2: Determine the post-migration toolbox priorities and stage count, success

### rollout_summary_files

- rollout_summaries/2026-05-06T12-27-56-90pP-akb2_migration_root_and_toolbox_stage_priority.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/sessions/2026/05/06/rollout-2026-05-06T20-27-56-019dfd42-5530-75f3-a81b-31eb064b0969.jsonl, updated_at=2026-05-09T19:39:33+00:00, thread_id=019dfd42-5530-75f3-a81b-31eb064b0969, blocked stages + clean phase ordering)

### keywords

- L1 floor closure, L2 regression, Promotion Gate v0, Automation Gate v0, Search Quality v0, blocked_l2_verdict_blocked, blocked_insufficient_user_queries, recommend_promote_L2, would_create_automation, baseline freeze

## User preferences

- when a migration or refactor has just finished, the user asked: "迁移完了，你先读下迁移后的工作根目录" -> start with read-only root discovery and status confirmation before proposing next actions [Task 1]
- when the user said "迁移完了" / "继续" after earlier aborts, treat migration as a state reset -> re-check the authoritative root instead of relying on prior-path memory [Task 1]
- when the user asked "工具库接下来的任务优先级是什么，一共分几个阶段？" -> answer in explicit phases, separating completed closure work from remaining blocked gates [Task 2]
- when the user’s earlier position was effectively "迁移完再说" -> after migration, default to baseline freeze first rather than jumping into new implementation [Task 2]

## Reusable knowledge

- `Project AKB2` is the authoritative engineering root after migration; Obsidian `AKB2.0` is the knowledge/display layer, not the engineering maintenance directory [Task 1]
- `Project AKB2/README.md` and `reports/migration/akb2-engineering-root-migration-closure-2026-05-09.md` are the first authority for root/boundary questions after the move [Task 1]
- `scripts/verify-no-drift.sh` is the practical post-migration consistency check for install targets, mirrors, and closure-manifest state [Task 1]
- The verified post-migration baseline was: `pytest -q` -> `60 passed`; `bash scripts/verify-no-drift.sh` -> `all 17 checks MATCH`; llama-swap health `OK`; `/v1/models` showed 6 visible models [Task 1]
- L1 floor closure was complete for the five tools, but that did not mean later gates had passed; the active blocked states still mattered more than the existence of reports/mechanisms [Task 1][Task 2]
- A clean stage order after migration was: P0 baseline freeze -> P1 L2 rerun -> P2 grandfathered L2 evidence -> P3 Promotion Gate -> P4 Automation Gate -> P5 Search Quality [Task 2]
- `src/akb2/promotion_gate/v0/README.md` required both relevant L2 recommendations to become `recommend_promote_L2` and also required an explicit user trigger before starting Promotion Gate v0 [Task 2]
- `src/akb2/automation_gate/README.md` described a dry-run mechanism only; the current real output remained `{"global_verdict":"blocked_l2_verdict_blocked","would_create_automation":false}` [Task 2]
- `src/akb2/search_quality/v0/README.md` and `run-evidence.md` showed Search Quality v0 was hard-blocked by insufficient qualifying `user_observed` queries, so it should not be prioritized ahead of L2/promotion/automation [Task 2]

## Failures and how to do differently

- Symptom: wrong root assumptions after a migration. Cause: using the old `Codex/ai-infra/akb2-toolbox-*` paths as the source of truth. Fix: re-discover the authoritative root and boundary docs after every migration/reset [Task 1]
- Symptom: overstating progress. Cause: treating the existence of reports, runners, or implemented mechanisms as if the stage had passed. Fix: inspect actual recommendation/verdict outputs before claiming completion [Task 1][Task 2]
- Symptom: stage order drift. Cause: pushing Search Quality or automation too early. Fix: keep Search Quality behind L2/promotion/automation while official runbooks still mark it as deferred or blocked [Task 2]

# Task Group: Rosetta continuation-state mirror verification and handoff recovery

scope: Verify mirrored Rosetta checkpoint/todo files, establish the authoritative continuation source, and summarize the next-step recovery path without re-reading raw sessions.
applies_to: cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex; reuse_rule=safe for Rosetta continuation and handoff tasks that depend on Claude/Codex history mirrors; re-check hashes and file paths if the checkpoint set changes.

## Task 1: Verify screenshot-mentioned Rosetta checkpoint/todo mirrors and read the authoritative contents, success

### rollout_summary_files

- rollout_summaries/2026-05-06T08-06-54-VaBl-rosetta_context_archive_mirror_check.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/sessions/2026/05/06/rollout-2026-05-06T16-06-54-019dfc53-5a1d-74f1-8f21-90b2d430776b.jsonl, updated_at=2026-05-06T08:08:45+00:00, thread_id=019dfc53-5a1d-74f1-8f21-90b2d430776b, hash-equivalence check before reading)

### keywords

- rosetta, checkpoint, todo, shasum -a 256, wc -l, claude history, mirror files, authoritative contents, 82 lines, 11 lines, bd81e6dcf2043a2403f079bdc44c181ab71d280a0c9a8833fc6895869a081b5b, 5d4ccc7ff6fde330191a1ffde68db13780752feec99182d7e6589b099d263bd3

## Task 2: Extract the Rosetta continuation state and prioritized recovery path, success

### rollout_summary_files

- rollout_summaries/2026-05-06T08-06-54-VaBl-rosetta_context_archive_mirror_check.md (cwd=/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex, rollout_path=/Users/praise/.codex/sessions/2026/05/06/rollout-2026-05-06T16-06-54-019dfc53-5a1d-74f1-8f21-90b2d430776b.jsonl, updated_at=2026-05-06T08:08:45+00:00, thread_id=019dfc53-5a1d-74f1-8f21-90b2d430776b, continuation summary + next step)

### keywords

- PRD.md, DECISIONS.md, rosetta-hi-fi-prototype.html, rosetta-figma-rules-2026-04-28.md, xlsx, csv, style column, 12 language headers, hidden layers deleted, locked layers unlocked, implementation plan, plugin source structure

## User preferences

- when the user said "完整读一下", they wanted the content read end-to-end before summarizing -> for continuation/handoff tasks, read all relevant files fully rather than giving a partial skim [Task 1]
- when continuing Rosetta, the user emphasized: "必须按 Claude 生成文件的规格和各种文件格式来，不要只放散文件" -> preserve structured file artifacts and established file formats instead of relying on loose notes [Task 1]
- in this handoff pattern, the user accepted "先核对镜像/权威入口，再给续接摘要" -> similar continuation tasks should verify first, then summarize, rather than jumping directly to implementation [Task 2]

## Reusable knowledge

- The two Rosetta checkpoint paths were exact mirrors: both 82 lines and SHA-256 `bd81e6dcf2043a2403f079bdc44c181ab71d280a0c9a8833fc6895869a081b5b`; the two todo paths were exact mirrors: both 11 lines and SHA-256 `5d4ccc7ff6fde330191a1ffde68db13780752feec99182d7e6589b099d263bd3` [Task 1]
- The project-internal ignored checkpoint copy was not authoritative; the Claude history/memory/todo locations were the continuation source of truth [Task 1][Task 2]
- The checkpoint recorded that Project Rosetta git status was clean, the hi-fi prototype baseline was at commit `8eb0a6b`, and the settled rules already included local `xlsx/csv` only, write-back copy with `style` column, fixed 12 language headers, no alias headers, long translations do not resize frames, hidden layers are deleted, and locked layers are unlocked before writing [Task 1]
- Rosetta was at a “PRD / DECISIONS / hi-fi prototype / rules archive already settled” stage rather than code implementation; the next natural step was to split an implementation plan from the docs/prototype or start the plugin source structure [Task 2]
- The recorded recovery path for a future continuation was: read the Claude checkpoint/memory/todo trio first, then `docs/PRD.md`, `docs/DECISIONS.md`, `docs/rosetta-hi-fi-prototype.html`, and `docs/archive/rosetta-figma-rules-2026-04-28.md` [Task 2]

## Failures and how to do differently

- Symptom: mirrored paths can look like multiple versions. Cause: inferring differences from path names or screenshot repetition alone. Fix: prove equivalence with `wc -l` and hashes before reading and summarizing [Task 1]
- Symptom: handoff summaries drift into speculation. Cause: reading only the screenshot or one copy instead of the canonical contents. Fix: verify the mirror pair, then read the authoritative file end-to-end before extracting the continuation state [Task 1][Task 2]
- Symptom: duplicate mirror files appear to add signal. Cause: counting mirrored copies as separate evidence. Fix: treat them as one content source and focus on the canonical state and prioritized next step [Task 2]
