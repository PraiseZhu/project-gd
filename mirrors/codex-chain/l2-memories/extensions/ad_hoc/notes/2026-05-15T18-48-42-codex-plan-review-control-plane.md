# Codex Workspace Plan/Review Control Plane

Date: 2026-05-15

The user clarified that the Codex workspace's primary role is to produce task plans and review Claude outputs. Future work in `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex` should default to this operating model:

- Codex plans upstream work for Claude or other implementers.
- Codex reviews and accepts or rejects Claude outputs downstream.
- Codex organizes durable artifacts automatically into `plans/`, `reviews/`, `references/`, `history/`, `archive/`, `ai-infra/`, or `plugins/` according to workspace rules.
- Codex should not default to primary implementation work unless the user explicitly asks Codex to implement, or the task is organizing the Codex workspace itself.

The workspace rule was codified in:

- `AGENTS.md`
- `README.md`
- `references/codex-plan-review-operating-model.md`
