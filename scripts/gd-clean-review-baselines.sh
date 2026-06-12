#!/usr/bin/env bash
# gd-clean-review-baselines.sh
# 按 key 前缀保留最近 N 个 review-baseline 目录，其余列出待删（默认 dry-run）。
#
# 用法:
#   bash gd-clean-review-baselines.sh [--keep N] [--prefix PREFIX] [--execute]
#
# 参数:
#   --keep N       每个前缀保留最近 N 个目录（默认 20）
#   --prefix P     只处理指定前缀（默认处理全部 gd-* 前缀）
#   --execute      真实删除（不加此参数默认 dry-run）
#
# 示例:
#   bash gd-clean-review-baselines.sh                             # dry-run，默认保留 20
#   bash gd-clean-review-baselines.sh --prefix gd-plan-master-plan-md --keep 10
#   bash gd-clean-review-baselines.sh --execute --keep 5

set -euo pipefail

BASELINES_DIR="${HOME}/.claude/review-baselines"
KEEP=20
PREFIX_FILTER=""
EXECUTE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep)     KEEP="$2"; shift 2 ;;
    --prefix)   PREFIX_FILTER="$2"; shift 2 ;;
    --execute)  EXECUTE=true; shift ;;
    -h|--help)
      sed -n '/^# 用法/,/^$/p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$BASELINES_DIR" ]]; then
  echo "ERROR: $BASELINES_DIR 不存在" >&2; exit 1
fi

cd "$BASELINES_DIR"

# 收集所有唯一前缀（bash 3.2 兼容，不用 declare -A）
PREFIXES_FILE=$(mktemp /tmp/gd-clean-prefixes.XXXX)
trap 'rm -f "$PREFIXES_FILE"' EXIT

while IFS= read -r dir; do
  [[ -d "$dir" ]] || continue
  base=$(basename "$dir")
  prefix=$(echo "$base" | sed 's/-[a-f0-9]\{12\}$//')
  echo "$prefix"
done < <(find . -maxdepth 1 -type d -name 'gd-*' | sort) | sort -u > "$PREFIXES_FILE"

TO_DELETE=()

while IFS= read -r prefix; do
  # 可选前缀过滤
  if [[ -n "$PREFIX_FILTER" && "$prefix" != "$PREFIX_FILTER" ]]; then
    continue
  fi

  # 按目录修改时间倒序列出，保留最新 KEEP 个（bash 3.2 兼容，不用 mapfile）
  DIRS_FILE=$(mktemp /tmp/gd-clean-dirs.XXXX)
  find . -maxdepth 1 -type d -name "${prefix}-*" \
    -exec stat -f "%m %N" {} \; 2>/dev/null \
    | sort -rn | awk '{print $2}' | sed 's|^\./||' > "$DIRS_FILE"

  total=$(wc -l < "$DIRS_FILE" | tr -d ' ')
  if [[ $total -le $KEEP ]]; then
    rm -f "$DIRS_FILE"
    continue
  fi

  excess=$(( total - KEEP ))
  echo "PREFIX: $prefix  total=$total  keep=$KEEP  to_delete=$excess"

  idx=0
  while IFS= read -r dir; do
    idx=$(( idx + 1 ))
    if [[ $idx -gt $KEEP ]]; then
      echo "  DELETE: $dir"
      TO_DELETE+=("$dir")
    fi
  done < "$DIRS_FILE"
  rm -f "$DIRS_FILE"
done < "$PREFIXES_FILE"

if [[ ${#TO_DELETE[@]} -eq 0 ]]; then
  echo "无需清理（所有前缀均在保留阈值内）"
  exit 0
fi

echo ""
echo "TOTAL_TO_DELETE: ${#TO_DELETE[@]}"

if [[ "$EXECUTE" == "true" ]]; then
  echo "EXECUTING deletions..."
  for dir in "${TO_DELETE[@]}"; do
    rm -rf "${BASELINES_DIR}/${dir}"
    echo "  DELETED: $dir"
  done
  echo "DONE"
else
  echo "DRY_RUN: 加 --execute 参数执行真实删除"
fi
