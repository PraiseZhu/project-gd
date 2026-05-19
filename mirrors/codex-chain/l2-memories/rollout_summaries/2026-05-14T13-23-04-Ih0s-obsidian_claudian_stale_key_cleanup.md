thread_id: 019e26a7-b148-7140-8098-a4693ac1f620
updated_at: 2026-05-14T16:21:12+00:00
rollout_path: /Users/praise/.codex/archived_sessions/rollout-2026-05-14T21-23-04-019e26a7-b148-7140-8098-a4693ac1f620.jsonl
cwd: /Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex

# Cleared stale Claudian/Obsidian Anthropic key drift and removed iCloud-synced key storage

Rollout context: The user reported that Obsidian/Claudian was using an old API key, likely due to signing in on another device and re-injecting stale config. They wanted the old key and any related token removed and replaced with the current Claude key. The work happened in the Obsidian vault environment (`/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents`) with the active local workspace at `/Users/praise/Library/Mobile Documents/com~apple~CloudDocs/Codex`.

## Task 1: Find and replace stale Claudian/Obsidian Anthropic credentials

Outcome: success

Preference signals:
- The user said the old key may have been re-injected by cross-device login and asked to “把旧的 key 和 token 删掉 换成目前 claude用的 key” -> future runs should treat cross-device sync drift as a likely cause and proactively look for multiple persistence layers, not just the obvious config file.
- The user later asked “好像还是不行 查查 / 彻查” -> future runs should widen the search to launchd GUI env, Obsidian/Electron caches, and legacy config files when the first fix does not take.
- The user explicitly asked “能把旧的 key 全部删掉么” -> future runs should be willing to remove old key material from backups/history/caches when authorized, not only the active config.
- The user asked “那我家里的电脑登录就会产生新的 token 怎么处理？” -> future runs should address cross-device behavior directly and explain how to prevent iCloud or other sync sources from reintroducing the stale credential.

Key steps:
- Identified the active vault plugin config at `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.obsidian/plugins/claudian/data.json`.
- Confirmed the active Claude key in shell/launchd matched the current key suffix `5V6w`, while the stale key suffix `vD9Q` corresponded to the old error hash `46bd5d52bd07...`.
- Found the real legacy storage location: `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.claudian/claudian-settings.json` (and its backup), which was the active source of the stale key, not only `.obsidian/plugins/claudian/data.json`.
- Set `launchctl` GUI environment to the current key and unset `ANTHROPIC_AUTH_TOKEN`.
- Rewrote the iCloud-synced Claudian settings so they no longer store API keys/tokens, leaving only `ANTHROPIC_BASE_URL` there.
- Scrubbed stale key/hash fragments from `.claude` histories, CloudKit mirrors, and other local caches; also removed stale key content from legacy backup/session JSONL where it had been echoed.
- Restarted Obsidian so the GUI process and Claudian child process inherited the updated environment.
- Verified the proxy endpoint responded successfully with the current key (`GET https://llm-proxy.tapsvc.com/v1/models` returned `200`).

Failures and how to do differently:
- The first pass failed because it only updated the plugin config, but Obsidian GUI apps inherit `launchctl` environment and Claudian also reads legacy `.claudian/claudian-settings.json`. Future cleanup should check those before assuming the plugin data file is authoritative.
- A later pass found the stale key still present in iCloud/CloudKit and Claude history/cache; the effective fix was to separate active config from historical residues and treat history/cache as redaction targets, not configuration sources.
- `launchctl getenv` is the relevant place to check for Finder/Dock-launched GUI apps; `.zshrc` alone is insufficient for Obsidian on macOS.

Reusable knowledge:
- Claudian’s active runtime environment is the merge of process env + its own stored environment strings; the plugin code reads `sharedEnvironmentVariables` and provider `environmentVariables`, then passes `env: { ...process.env, ...ctx.customEnv, PATH: ... }` into the Claude process.
- The real active storage path is `.claudian/claudian-settings.json`; `.claude/claudian-settings.json` is legacy/backup territory.
- For this setup, `launchctl` is the right place to set GUI-visible Anthropic env vars on macOS, and `ANTHROPIC_AUTH_TOKEN` can be intentionally unset when the setup should only use `ANTHROPIC_API_KEY`.
- `ANTHROPIC_BASE_URL` was consistently `https://llm-proxy.tapsvc.com`.
- The current usable key suffix was `5V6w`; the stale key suffix was `vD9Q`.

References:
- [1] Active plugin config: `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.obsidian/plugins/claudian/data.json`
- [2] Legacy active Claudian settings: `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.claudian/claudian-settings.json`
- [3] Current shell/launchd key verification: `launchctl ANTHROPIC_API_KEY=sk-LY7WFL...5V6w`, `launchctl ANTHROPIC_AUTH_TOKEN=`
- [4] Successful auth probe: `GET https://llm-proxy.tapsvc.com/v1/models` returned status `200`
- [5] Obsidian process restart and re-launch were required for GUI env changes to take effect

## Task 2: Remove old key from synced legacy storage and explain cross-device behavior

Outcome: success

Preference signals:
- The user asked whether a family computer login would produce a new token and how to handle that -> future runs should explain that local deletion alone does not revoke the server-side credential, and should recommend revoking the old key at the provider.
- The user asked to delete the old key “全部” -> future runs should prefer a clean architecture where synced vault files do not contain secrets, and local machine-specific env supplies the live credential.

Key steps:
- Removed the old key from the iCloud-synced legacy Claudian settings and backup content so the vault no longer stores the credential.
- Confirmed the live setup still works with the current key via local environment, while the synced config only retains the base URL.
- Verified that remaining matches for the stale key/hash were no longer in the active vault config or Obsidian runtime cache; the remaining Codex cache residue was explicitly left alone because it was the live app’s own WAL.

Failures and how to do differently:
- Do not store live Anthropic credentials in iCloud-synced vault config when the same vault is used on multiple Macs; that can reintroduce stale values after cross-device login.
- The durable fix is to keep only non-secret transport config in sync and source secrets from per-machine local env/launchctl.

Reusable knowledge:
- Claudian can operate with synced config containing only `ANTHROPIC_BASE_URL`, while the actual API key comes from the machine’s environment.
- For multi-device use, the server-side old key/token should be revoked/removed in the provider console; local cleanup alone prevents reuse on the Mac but does not invalidate a compromised key everywhere.

References:
- [1] Final synced files contain no API key/token fields:
  - `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.claudian/claudian-settings.json`
  - `/Users/praise/Library/Mobile Documents/iCloud~md~obsidian/Documents/.obsidian/plugins/claudian/data.json`
- [2] Current machine env after cleanup: `ANTHROPIC_API_KEY` suffix `5V6w`, `ANTHROPIC_AUTH_TOKEN` unset, `ANTHROPIC_BASE_URL=https://llm-proxy.tapsvc.com`
- [3] Stale key/hash no longer found outside the live Codex cache/WAL area after cleanup

