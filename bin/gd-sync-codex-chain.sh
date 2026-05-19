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
for f in config.toml AGENTS.md .codex-global-state.json \
          models_cache.json cloud-requirements-cache.json \
          version.json history.jsonl; do
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

# ─── Secret 兜底扫描 ──────────────────────────────────────────────────────────
if [[ $APPLY -eq 1 && $SKIP_SCAN -eq 0 ]]; then
  echo ""
  echo "=== Secret 兜底扫描 ==="
  SECRET_REGEX=(
    'AKIA[A-Z0-9]{16}'
    'sk-[A-Za-z0-9_-]{20,}'
    'gh[pousr]_[A-Za-z0-9_]{36,}'
    'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.'
    'BEGIN (RSA |EC )?PRIVATE KEY'
  )
  HITS=0
  while IFS= read -r -d '' fpath; do
    file "$fpath" 2>/dev/null | grep -q "binary" && continue
    for re in "${SECRET_REGEX[@]}"; do
      if grep -qE -- "$re" "$fpath" 2>/dev/null; then
        echo "  🚨 命中 [$re]: $fpath" >&2
        HITS=$((HITS + 1))
        break
      fi
    done
  done < <(find "$MIRROR" -type f -print0 2>/dev/null)
  if [[ $HITS -gt 0 ]]; then
    echo "❌ Secret 扫描发现 $HITS 个命中，请人工处理后重试（可加 --skip-scan 跳过）" >&2
    exit 2
  fi
  echo "  ✅ 无 secret 命中"
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

  echo ""
  echo "=== git diff --stat ==="
  git -C "$REPO_ROOT" diff --stat HEAD -- mirrors/ 2>/dev/null || true
  git -C "$REPO_ROOT" status --short mirrors/ 2>/dev/null || true
  echo ""
  echo "✅ sync 完成。确认无误后喊「提交代码」触发 commit-projects skill。"
fi
