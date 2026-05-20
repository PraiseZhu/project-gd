#!/usr/bin/env bash
# gd-sync-codex-chain.sh — 把 L1/L2 codex 链路工程文件镜像到 mirrors/codex-chain/
#
# 用法:
#   bash bin/gd-sync-codex-chain.sh              # dry-run，只预览不写文件
#   bash bin/gd-sync-codex-chain.sh --apply      # 实际同步
#   bash bin/gd-sync-codex-chain.sh --apply --skip-scan  # 跳过 secret 扫描（debug 用）
#
# 完成后手动喊「提交代码」触发 commit-projects skill 提交变更。

set -euo pipefail

# ─── 参数解析 ────────────────────────────────────────────────────────────────
APPLY=0
SKIP_SCAN=0
for arg in "$@"; do
  case "$arg" in
    --apply)     APPLY=1 ;;
    --skip-scan) SKIP_SCAN=1 ;;
  esac
done

# ─── 路径常量 ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$REPO_ROOT" ]]; then
  echo "❌ 必须在 Project GD git 仓库内执行" >&2
  exit 1
fi

MIRROR="$REPO_ROOT/mirrors/codex-chain"
L1_SRC="$HOME/.npm-global/lib/node_modules/@openai/codex"
L2_SRC="$HOME/.codex"

# ─── 前置检查：.git/index.lock ───────────────────────────────────────────────
# 不论 dry-run 还是 --apply，遇到 lock 一律退出。
# 只报告陈旧状态，不自动删除——删除是破坏性操作，需人工确认。
LOCK_FILE="$REPO_ROOT/.git/index.lock"
if [[ -f "$LOCK_FILE" ]]; then
  LOCK_AGE=$(( $(date +%s) - $(stat -f %m "$LOCK_FILE" 2>/dev/null || echo 0) ))
  echo "❌ .git/index.lock 存在 (${LOCK_AGE}s 前)，可能另一进程在运行" >&2
  echo "   如确认无其他 git 进程：rm -f '$LOCK_FILE'" >&2
  exit 1
fi

# ─── dry-run 提示 ────────────────────────────────────────────────────────────
if [[ $APPLY -eq 0 ]]; then
  echo "[dry-run] 以下是将要同步的内容（加 --apply 才实际写入）"
  echo ""
fi

RSYNC_FLAGS="-av --checksum"
[[ $APPLY -eq 0 ]] && RSYNC_FLAGS="$RSYNC_FLAGS --dry-run"

# ─── L1: npm codex 包 ────────────────────────────────────────────────────────
echo "=== L1: @openai/codex binary ==="
rsync $RSYNC_FLAGS \
  --exclude='node_modules/' \
  "$L1_SRC/bin/" "$MIRROR/l1-binary/" 2>/dev/null || true
rsync $RSYNC_FLAGS \
  "$L1_SRC/package.json" "$L1_SRC/README.md" \
  "$MIRROR/l1-binary/" 2>/dev/null || true

# ─── L2: 根配置文件（白名单，显式排除 auth.json）──────────────────────────
echo ""
echo "=== L2: config ==="
for f in config.toml AGENTS.md version.json; do
  # INCLUDE_FULL: user/version data — low churn, safe to commit verbatim
  # history.jsonl excluded per manifest (privacy — conversation history)
  # .codex-global-state.json, models_cache.json, cloud-requirements-cache.json:
  #   MANIFEST_ONLY per config/gd-runtime-parity-manifest.json — metadata only in
  #   sync-manifest.json, full content must NOT be written to mirror.
  [[ -f "$L2_SRC/$f" ]] && rsync $RSYNC_FLAGS "$L2_SRC/$f" "$MIRROR/l2-config/" || true
done
rsync $RSYNC_FLAGS \
  --exclude='.run-jitter-salt' \
  "$L2_SRC/rules/" "$MIRROR/l2-config/rules/" 2>/dev/null || true
# redact: default.rules 第 5 行含真实 sk-* key，替换为占位符
if [[ $APPLY -eq 1 && -f "$MIRROR/l2-config/rules/default.rules" ]]; then
  sed -i '' 's/sk-[A-Za-z0-9_-]\{20,\}/<REDACTED>/g' \
    "$MIRROR/l2-config/rules/default.rules" 2>/dev/null || true
fi

# ─── L2: automations ─────────────────────────────────────────────────────────
echo ""
echo "=== L2: automations ==="
rsync $RSYNC_FLAGS \
  --exclude='.run-jitter-salt' \
  "$L2_SRC/automations/" "$MIRROR/l2-automations/" 2>/dev/null || true

# ─── L2: memories（排除 .git/）───────────────────────────────────────────────
echo ""
echo "=== L2: memories ==="
rsync $RSYNC_FLAGS \
  --exclude='.git/' \
  --exclude='computer-use/' \
  "$L2_SRC/memories/" "$MIRROR/l2-memories/" 2>/dev/null || true

# ─── L2: system skills ───────────────────────────────────────────────────────
echo ""
echo "=== L2: system skills ==="
rsync $RSYNC_FLAGS \
  "$L2_SRC/skills/.system/" "$MIRROR/l2-system-skills/" 2>/dev/null || true

# ─── L2: skills manifest（仅 --apply 时重新生成）────────────────────────────
if [[ $APPLY -eq 1 ]]; then
  echo ""
  echo "=== L2: 生成 skills manifest ==="
  MANIFEST_OUT="$MIRROR/l2-skills-manifest.json" python3 - <<'PYEOF'
import os, json
skills_dir = os.path.expanduser("~/.codex/skills")
manifest = []
for name in sorted(os.listdir(skills_dir)):
    if name.startswith('.') or name == '.system':
        continue
    skill_path = os.path.join(skills_dir, name)
    if not os.path.isdir(skill_path):
        continue
    skill_md = os.path.join(skill_path, "SKILL.md")
    description = ""
    if os.path.isfile(skill_md):
        with open(skill_md, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("description:"):
                    description = line[len("description:"):].strip().strip('"').strip("'")
                    break
    file_count = sum(len(files) for _, _, files in os.walk(skill_path))
    total_bytes = sum(
        os.path.getsize(os.path.join(dp, fn))
        for dp, _, files in os.walk(skill_path)
        for fn in files
    )
    manifest.append({
        "name": name,
        "description": description,
        "file_count": file_count,
        "total_bytes": total_bytes
    })
out = os.environ["MANIFEST_OUT"]  # 由 shell 显式传入，不从 __file__ 推导
with open(out, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"  manifest: {len(manifest)} skills → {out}")
PYEOF
fi

# ─── Secret 兜底扫描（regex 从 SSOT 加载） ────────────────────────────────────
if [[ $APPLY -eq 1 && $SKIP_SCAN -eq 0 ]]; then
  echo ""
  echo "=== Secret 兜底扫描 ==="
  SECRET_SSOT="$REPO_ROOT/config/secret-scan-regexes.json"
  if [[ ! -f "$SECRET_SSOT" ]]; then
    echo "❌ Secret scan SSOT 缺失: $SECRET_SSOT" >&2
    exit 2
  fi
  # 从 SSOT 构建 grep pattern（ERE-compatible，避免 PCRE lookahead）
  SECRET_PATTERN=$(python3 -c "
import json
d = json.load(open('$SECRET_SSOT'))
patterns = [p['regex'] for p in d.get('patterns', [])]
print('|'.join(patterns))
" 2>/dev/null)
  if [[ -z "$SECRET_PATTERN" ]]; then
    echo "❌ SSOT 解析失败或 patterns 为空" >&2
    exit 2
  fi
  HITS=0
  while IFS= read -r -d '' fpath; do
    file "$fpath" 2>/dev/null | grep -q "binary" && continue
    if grep -qE -- "$SECRET_PATTERN" "$fpath" 2>/dev/null; then
      echo "  🚨 secret 命中: $fpath" >&2
      HITS=$((HITS + 1))
    fi
  done < <(find "$MIRROR" -type f -print0 2>/dev/null)
  if [[ $HITS -gt 0 ]]; then
    echo "❌ Secret 扫描发现 $HITS 个命中，请人工处理后重试（可加 --skip-scan 跳过）" >&2
    exit 2
  fi
  echo "  ✅ 无 secret 命中 (SSOT: $SECRET_SSOT)"
fi

# ─── 幂等检测 + 条件性写 sync-history.jsonl ────────────────────────────────────────────
# 用内容哈希对比（排除 sync-history.jsonl 自身）检测是否有实际变更。
# 不依赖 git status，避免"未跟踪目录"导致永远非零的误判。
if [[ $APPLY -eq 1 ]]; then
  echo ""
  HASH_NOW=$(find "$MIRROR" -type f ! -name sync-history.jsonl ! -name .sync-content-hash -print0 | sort -z | xargs -0 md5 2>/dev/null | md5 || echo "")
  HASH_FILE="$MIRROR/.sync-content-hash"
  HASH_PREV=$(cat "$HASH_FILE" 2>/dev/null || echo "")

  if [[ "$HASH_NOW" == "$HASH_PREV" && -n "$HASH_NOW" ]]; then
    echo "[no-op] no mirror changes since last sync"
  else
    echo "$HASH_NOW" > "$HASH_FILE"
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    TOTAL_BYTES=$(du -sk "$MIRROR" 2>/dev/null | awk '{print $1 * 1024}' || echo 0)
    LOG_ENTRY="{\"timestamp\":\"$TIMESTAMP\",\"total_bytes\":$TOTAL_BYTES}"
    echo "$LOG_ENTRY" >> "$MIRROR/sync-history.jsonl"
    echo "📝 sync-history.jsonl 新增记录: $TIMESTAMP"
  fi

  # ─── sync-manifest.json 生成 (SC-7) ─────────────────────────────────────
  echo ""
  echo "=== 生成 sync-manifest.json ==="
  SYNC_MANIFEST="$MIRROR/sync-manifest.json"
  python3 - <<PYEOF
import json, os, hashlib, subprocess
from pathlib import Path

mirror = Path("$MIRROR")
l2_src = Path("$L2_SRC")

def sha256_dir(d):
    h = hashlib.sha256()
    for f in sorted(d.rglob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()

def file_count(d):
    return sum(1 for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0

buckets = {
    "l1_binary": mirror / "l1-binary",
    "l2_config":  mirror / "l2-config",
    "l2_memories": mirror / "l2-memories",
    "l2_system_skills": mirror / "l2-system-skills",
    "l2_automations": mirror / "l2-automations",
}
per_bucket = {}
included_count = 0
for name, path in buckets.items():
    cnt = file_count(path)
    included_count += cnt
    per_bucket[name] = {"file_count": cnt, "sha256": sha256_dir(path) if path.is_dir() else "missing"}

# L2 manifest-only metadata: record size+sha256 per file/dir, do NOT commit full content
import hashlib
manifest_only_files = [".codex-global-state.json", "models_cache.json", "cloud-requirements-cache.json"]
manifest_only_dirs = ["skills", "computer-use", "plugins"]
manifest_only_meta = []
for mof in manifest_only_files:
    p = l2_src / mof
    if p.is_file():
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest_only_meta.append({"name": mof, "type": "file", "size_bytes": p.stat().st_size, "sha256": h, "note": "metadata_only_not_committed"})
for mod in manifest_only_dirs:
    p = l2_src / mod
    if p.is_dir():
        fc = sum(1 for f in p.rglob("*") if f.is_file())
        tb = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        # Sample hash: hash of sorted file names for stability without reading all content
        names_hash = hashlib.sha256("\n".join(sorted(str(f.relative_to(p)) for f in p.rglob("*") if f.is_file())).encode()).hexdigest()
        manifest_only_meta.append({"name": mod + "/", "type": "directory", "file_count": fc, "total_bytes": tb, "names_hash": names_hash, "note": "metadata_only_not_committed"})
manifest_only = [".codex-global-state.json", "models_cache.json", "cloud-requirements-cache.json"]
excluded_files = ["auth.json", ".codex-global-state.json.bak", ".personality_migration",
                  "installation_id", "session_index.jsonl", "state_5.sqlite",
                  "state_5.sqlite-shm", "state_5.sqlite-wal", "history.jsonl",
                  "logs_2.sqlite", "logs_2.sqlite-shm", "logs_2.sqlite-wal"]
excluded_dirs = ["sessions", "archived_sessions", "log", "cache", "sqlite",
                 "tmp", ".tmp", "vendor_imports", "shell_snapshots", "ambient-suggestions", "pets"]

runtime_top = [e.name for e in l2_src.iterdir()] if l2_src.is_dir() else []
all_classified = [".codex-global-state.json", ".codex-global-state.json.bak",
                  ".personality_migration", "AGENTS.md", "auth.json",
                  "cloud-requirements-cache.json", "config.toml", "history.jsonl",
                  "installation_id", "logs_2.sqlite", "logs_2.sqlite-shm", "logs_2.sqlite-wal",
                  "models_cache.json", "session_index.jsonl", "state_5.sqlite",
                  "state_5.sqlite-shm", "state_5.sqlite-wal", "version.json",
                  "ambient-suggestions", "archived_sessions", "automations", "cache",
                  "computer-use", "log", "memories", "pets", "plugins", "rules",
                  "sessions", "shell_snapshots", "skills", "sqlite", "tmp", ".tmp",
                  "vendor_imports"]
unclassified = [e for e in runtime_top if e not in all_classified]

# Redaction count
redacted = 0
rules_file = mirror / "l2-config/rules/default.rules"
if rules_file.exists() and "<REDACTED>" in rules_file.read_text(errors="replace"):
    redacted = 1

manifest_data = {
    "generated_at": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]).decode().strip(),
    "apply_mode": True,
    "runtime_top_level_count": len(runtime_top),
    "included_count": included_count,
    "manifest_only_count": len(manifest_only),
    "manifest_only_metadata": manifest_only_meta,
    "excluded_count": len(excluded_files) + len(excluded_dirs),
    "unclassified_count": len(unclassified),
    "unclassified_entries": unclassified,
    "redaction_count": redacted,
    "secret_scan_status": "pass",
    "per_bucket_hash": per_bucket,
    "manifest_only_items": manifest_only,
    "secret_scan_regex_version": "1.0.0",
    "secret_scan_regex_ssot": "config/secret-scan-regexes.json"
}
out_path = Path("$SYNC_MANIFEST")
out_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False))
print(f"  sync-manifest.json: {included_count} included, {len(unclassified)} unclassified, {redacted} redacted")
PYEOF

  echo ""
  echo "=== git diff --stat ==="
  git -C "$REPO_ROOT" diff --stat HEAD -- mirrors/ 2>/dev/null || true
  git -C "$REPO_ROOT" status --short mirrors/ 2>/dev/null || true
  echo ""
  echo "✅ sync 完成。确认无误后喊「提交代码」触发 commit-projects skill。"
fi
