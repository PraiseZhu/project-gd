#!/bin/bash
# gd-plugin-setup.sh — Project GD 插件预设配置脚本
#
# 纯 bash + stdlib（python3 仅用于 JSON 序列化，标准库，零 pip）。
# 兼容 macOS /bin/bash 3.2：不使用 ${var^^} / ${var,,} / declare -A 等 bash4+ 特性。
#
# 采集 4 个选项制字段并持久化到 ${CLAUDE_PLUGIN_DATA}/gd-setup-config.json：
#   a 审查产物输出位置 (output_location)
#   b codex key 类型(官方/第三方两类) + 值 (key_type / key_value)
#   c codex 模型 (codex_model)
#   d 模型强度 effort (effort)
#
# 全选项制（零自由填路径/值），可重跑单改任一项，零内置默认 key。
# 提供 --self-check 只读子命令（不交互、不写文件）供验收抓取。

set -u

# --- 预设持久化位置模板（PERSIST 行须含字面 CLAUDE_PLUGIN_DATA 供验收断言）---
CONFIG_PATH_TEMPLATE='${CLAUDE_PLUGIN_DATA}/gd-setup-config.json'

# --- 字段元数据（不内置任何 key 默认值）---
FIELD_COUNT=4
FREEFORM_FIELD_COUNT=0   # 全部字段为选项菜单，无自由填路径/值字段
KEY_TYPE_COUNT=2         # 官方 official + 第三方 third_party

# --- 只读自检子命令 ---------------------------------------------------------
if [ "${1:-}" = "--self-check" ]; then
  echo "FIELDS=${FIELD_COUNT}"
  echo "FREEFORM=${FREEFORM_FIELD_COUNT}"
  echo "KEY_TYPES=${KEY_TYPE_COUNT}"
  echo "PERSIST=${CONFIG_PATH_TEMPLATE}"
  echo "BUILTIN_KEY=0"
  exit 0
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  cat <<'EOF'
用法：
  gd-plugin-setup.sh             交互式配置 4 个预设字段（选项菜单）
  gd-plugin-setup.sh --self-check  只读自检，输出字段形态断言（不交互、不写文件）
  gd-plugin-setup.sh --help        显示本帮助

字段：a 审查产物输出位置 / b codex key 类型(官方·第三方)+值 / c codex 模型 / d 模型强度 effort
预设写入：${CLAUDE_PLUGIN_DATA}/gd-setup-config.json（更新安全，可重跑单改任一项，零内置默认 key）
EOF
  exit 0
fi

# --- 解析持久化目录（fail-closed，不静默写 ~）-------------------------------
if [ -z "${CLAUDE_PLUGIN_DATA:-}" ]; then
  echo "错误：环境变量 \$CLAUDE_PLUGIN_DATA 未设置。" >&2
  echo "本脚本必须由 Claude Code 插件机制（/setup 命令）调用，以拿到更新安全的数据目录。" >&2
  echo "请通过插件命令 /setup 运行，而不要直接手动执行；不会静默写入 \$HOME。" >&2
  exit 2
fi

CONFIG_DIR="${CLAUDE_PLUGIN_DATA}"
CONFIG_FILE="${CONFIG_DIR}/gd-setup-config.json"

# --- 选项菜单工具：在固定选项中选一项（非自由填）---------------------------
# 用法：choose_option <提示> <当前值> <选项1> <选项2> ...
# 结果写入全局 CHOSEN
choose_option() {
  prompt="$1"; shift
  current="$1"; shift
  echo "" >&2
  echo "$prompt" >&2
  if [ -n "$current" ]; then
    echo "  （当前值：$current，直接回车保留）" >&2
  fi
  i=1
  # 用位置参数遍历选项，避免 bash3.2 无关联数组
  for opt in "$@"; do
    echo "    $i) $opt" >&2
    i=$((i + 1))
  done
  total=$#
  while true; do
    printf "请输入选项编号 [1-%s]: " "$total" >&2
    read -r reply
    if [ -z "$reply" ] && [ -n "$current" ]; then
      CHOSEN="$current"
      return 0
    fi
    # 仅接受纯数字且在范围内 —— 选项制，不接受自由填
    case "$reply" in
      ''|*[!0-9]*)
        echo "  无效输入：只能选编号。" >&2
        continue
        ;;
    esac
    if [ "$reply" -ge 1 ] && [ "$reply" -le "$total" ]; then
      idx=1
      for opt in "$@"; do
        if [ "$idx" -eq "$reply" ]; then
          CHOSEN="$opt"
          return 0
        fi
        idx=$((idx + 1))
      done
    fi
    echo "  无效编号，请重选。" >&2
  done
}

# --- 读取已有配置中的某字段（可重跑时回显当前值）---------------------------
read_existing() {
  field="$1"
  if [ -f "$CONFIG_FILE" ]; then
    python3 - "$CONFIG_FILE" "$field" <<'PYEOF'
import json, sys
path, field = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        data = json.load(f)
    val = data.get(field, "")
    if val is None:
        val = ""
    print(val)
except Exception:
    print("")
PYEOF
  else
    echo ""
  fi
}

mkdir -p "$CONFIG_DIR"

echo "=== Project GD 插件预设配置 ==="
echo "（全部字段为选项菜单；可随时重跑本命令单独修改任一项）"

cur_output="$(read_existing output_location)"
cur_key_type="$(read_existing key_type)"
cur_model="$(read_existing codex_model)"
cur_effort="$(read_existing effort)"

# a · 审查产物输出位置（选项制）
choose_option "a · 审查产物输出位置（链路 reports/baselines 等写到哪）" "$cur_output" \
  "plugin_data" "target_project" "cwd"
OUTPUT_LOCATION="$CHOSEN"

# b · codex key 类型（官方/第三方两类）+ 值
choose_option "b · codex key 类型（两类，对应不同 provider/base_url/env_key）" "$cur_key_type" \
  "official" "third_party"
KEY_TYPE="$CHOSEN"

# 不内置任何默认 key；key 值由安装者输入，不写日志、不进 git
echo ""
echo "请输入你自备的 codex key 值（不显示、不内置默认、不写入 git；留空则保留已有 key）："
printf "key: "
# -s 隐藏输入；bash3.2 支持 read -s
read -rs KEY_VALUE
echo ""

# c · codex 模型（选项制）
choose_option "c · codex 模型" "$cur_model" \
  "gpt-5.4" "gpt-5.4-mini" "gpt-5"
CODEX_MODEL="$CHOSEN"

# d · 模型强度 effort（选项制）
choose_option "d · 模型强度（effort）" "$cur_effort" \
  "low" "medium" "high" "xhigh"
EFFORT="$CHOSEN"

# --- 写入 JSON（python3 stdlib，保留未改动的 key 值）------------------------
GD_OUTPUT_LOCATION="$OUTPUT_LOCATION" \
GD_KEY_TYPE="$KEY_TYPE" \
GD_KEY_VALUE="$KEY_VALUE" \
GD_CODEX_MODEL="$CODEX_MODEL" \
GD_EFFORT="$EFFORT" \
python3 - "$CONFIG_FILE" <<'PYEOF'
import json, os, sys
path = sys.argv[1]

existing = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            existing = json.load(f)
    except Exception:
        existing = {}

cfg = {
    "output_location": os.environ["GD_OUTPUT_LOCATION"],
    "key_type": os.environ["GD_KEY_TYPE"],
    "codex_model": os.environ["GD_CODEX_MODEL"],
    "effort": os.environ["GD_EFFORT"],
}

# key 值留空 -> 保留已有；否则更新。绝不内置默认 key。
new_key = os.environ.get("GD_KEY_VALUE", "")
if new_key:
    cfg["key_value"] = new_key
elif "key_value" in existing:
    cfg["key_value"] = existing["key_value"]

with open(path, "w") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
os.chmod(path, 0o600)
print("已写入预设：" + path)
PYEOF

echo ""
echo "完成。预设已持久化到更新安全目录；重跑本命令可单独修改任一项。"
echo "提示：HANDOFF_ROOT 由插件管理，不在本预设内（填错即断链）。"
