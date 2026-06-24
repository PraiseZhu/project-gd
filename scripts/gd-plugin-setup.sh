#!/bin/bash
# gd-plugin-setup.sh — Project GD 插件预设配置脚本
#
# 纯 bash + stdlib（python3 仅用于 JSON 序列化与薄壳模板渲染，标准库，零 pip）。
# 兼容 macOS /bin/bash 3.2：不使用 ${var^^} / ${var,,} / declare -A 等 bash4+ 特性。
#
# 采集 5 个选项制字段并持久化到 ${CLAUDE_PLUGIN_DATA}/gd-setup-config.json：
#   a 审查产物输出位置 (output_location)
#   b codex key 类型(官方/第三方两类) + 值 (key_type / key_value)
#   c codex 模型 (codex_model)
#   d 模型强度 effort (effort)
#   e 运行环境 (runtime_env: xdt_maker / claude_code)
#         xdt_maker  → 生成 7 个 maker 适配薄壳到 ${GD_PROJECT_ROOT}/.claude/skills/（project scope）
#         claude_code → 移除上述薄壳（用 plugin command，${CLAUDE_PLUGIN_ROOT} 自动注入）
#   另持久化 gd_project_root（从脚本位置推断，非硬编码；薄壳模板渲染时读它）。
#
# 全选项制（零自由填路径/值），可重跑单改任一项，零内置默认 key。
# 子命令：
#   --self-check   只读自检，输出字段形态断言 + runtime_env + 薄壳状态（不交互、不写文件）
#   --gen-shells   读 config 的 runtime_env + gd_project_root，从模板生成 7 薄壳到 project scope
#   --rm-shells    移除 project scope 的 7 个 gd-*/review* 薄壳（不含裸 gd，gd 无指令）
#   --help / -h    显示帮助

set -u

# --- 预设持久化位置模板（PERSIST 行须含字面 CLAUDE_PLUGIN_DATA 供验收断言）---
CONFIG_PATH_TEMPLATE='${CLAUDE_PLUGIN_DATA}/gd-setup-config.json'

# --- 字段元数据（不内置任何 key 默认值）---
FIELD_COUNT=5
FREEFORM_FIELD_COUNT=0   # 全部字段为选项菜单，无自由填路径/值字段
KEY_TYPE_COUNT=2         # 官方 official + 第三方 third_party
SHELL_SKILL_COUNT=7
SHELL_SKILLS="gd-plan gd-review-plan gd-exec gd-review gd-setup review1 review2"

# --- GD_PROJECT_ROOT 解析 --------------------------------------------------
# 薄壳与模板渲染需要 plugin 根绝对路径。本脚本位于 ${GD_PROJECT_ROOT}/scripts/，
# 故从 $0 推断（非硬编码）。config 里的 gd_project_root 若指向有效 root 则优先用之
# （自愈：config 过期回落到脚本推断）。
infer_gd_project_root() {
  local script_dir root
  script_dir="$(cd "$(dirname "$0")" && pwd)" 2>/dev/null || script_dir=""
  [ -z "$script_dir" ] && { echo ""; return; }
  root="$(dirname "$script_dir")"
  if [ -f "$root/commands/gd.md" ]; then
    echo "$root"
  else
    echo ""
  fi
}

# 读 config 里某字段（config 不存在/字段缺失返回空）
read_config_field() {
  local field="$1"
  if [ -z "${CLAUDE_PLUGIN_DATA:-}" ] || [ ! -f "${CLAUDE_PLUGIN_DATA}/gd-setup-config.json" ]; then
    echo ""
    return
  fi
  python3 - "${CLAUDE_PLUGIN_DATA}/gd-setup-config.json" "$field" <<'PYEOF'
import json, sys
path, field = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        data = json.load(f)
    val = data.get(field, "")
    print("" if val is None else val)
except Exception:
    print("")
PYEOF
}

# 解析最终生效的 GD_PROJECT_ROOT：config 值有效则用 config 值，否则脚本推断
resolve_gd_project_root() {
  local inferred cfg_root
  inferred="$(infer_gd_project_root)"
  cfg_root="$(read_config_field gd_project_root)"
  if [ -n "$cfg_root" ] && [ -f "$cfg_root/commands/gd.md" ]; then
    echo "$cfg_root"
  else
    echo "$inferred"
  fi
}

# --- 只读自检子命令 ---------------------------------------------------------
do_self_check() {
  echo "FIELDS=${FIELD_COUNT}"
  echo "FREEFORM=${FREEFORM_FIELD_COUNT}"
  echo "KEY_TYPES=${KEY_TYPE_COUNT}"
  echo "PERSIST=${CONFIG_PATH_TEMPLATE}"
  echo "BUILTIN_KEY=0"
  local rt root generated
  rt="$(read_config_field runtime_env)"
  echo "RUNTIME_ENV=${rt:-unset}"
  root="$(resolve_gd_project_root)"
  echo "GD_PROJECT_ROOT=${root:-unset}"
  generated=0
  if [ -n "$root" ] && [ -d "$root/.claude/skills" ]; then
    for s in $SHELL_SKILLS; do
      [ -f "$root/.claude/skills/$s/SKILL.md" ] && generated=$((generated + 1))
    done
  fi
  echo "SHELLS_GENERATED=${generated}/${SHELL_SKILL_COUNT}"
  echo "SHELL_SKILLS=$SHELL_SKILLS"
}

# --- 生成 maker 薄壳到 project scope ---------------------------------------
do_gen_shells() {
  local root tmpl rt
  root="$(resolve_gd_project_root)"
  if [ -z "$root" ]; then
    echo "错误：无法解析 GD_PROJECT_ROOT（脚本不在 plugin 结构内，且 config 无有效值）。" >&2
    exit 2
  fi
  tmpl="$root/templates/gd-skill-shell-template.md"
  if [ ! -f "$tmpl" ]; then
    echo "错误：薄壳模板不存在：$tmpl" >&2
    exit 2
  fi
  # 一致性守卫：config 显式选 claude_code 时拒生成（避免与安装者意图冲突）
  rt="$(read_config_field runtime_env)"
  if [ "$rt" = "claude_code" ]; then
    echo "错误：runtime_env=claude_code，不生成 maker 薄壳。重跑 /gd-setup 选 xdt_maker。" >&2
    exit 2
  fi
  GD_PROJECT_ROOT="$root" TEMPLATE_PATH="$tmpl" OUT_DIR="$root/.claude/skills" \
    python3 - <<'PYEOF'
import os, sys
root = os.environ["GD_PROJECT_ROOT"]
tmpl_path = os.environ["TEMPLATE_PATH"]
out_dir = os.environ["OUT_DIR"]
with open(tmpl_path) as f:
    raw = f.read()
# 模板文件首部可能有 <!-- ... --> 维护注释；从首个恰为 '---' 的行起才是 skill body。
lines = raw.splitlines(keepends=True)
start = 0
for i, ln in enumerate(lines):
    if ln.rstrip("\n") == "---":
        start = i
        break
skeleton = "".join(lines[start:])
# 7 薄壳注册表：(skill_name, description, redirect_target)
# description 是 maker `/` 补全展示的用途说明；redirect_target 是本薄壳读取的 plugin command。
REGISTRY = [
    ("gd-plan", "GD L3 · 生成计划（maker 适配薄壳，等价 /gd plan）。多 Agent planning dispatch + task packets。读取 plugin gd.md 的 /gd plan 段执行，gd.md 为唯一权威。", "gd.md"),
    ("gd-review-plan", "GD L3 · 审计划（maker 适配薄壳，等价 /gd review plan）。Claude self-review + Codex cross-review + merge/auto-fix。读取 plugin gd.md 的 /gd review plan 段执行，gd.md 为唯一权威。", "gd.md"),
    ("gd-exec", "GD L3 · 执行（maker 适配薄壳，等价 /gd execute）。agent_exec 子 agent 化执行 + dispatch ledger + path audit。读取 plugin gd.md 的 /gd execute 段执行，gd.md 为唯一权威。", "gd.md"),
    ("gd-review", "GD L3 · 审查（maker 适配薄壳，等价 /gd review）。自动识别 target（代码/执行结果/代码+结果）后路由审查，Claude+Codex 交叉验证。读取 plugin gd.md 的 unified router 段执行，gd.md 为唯一权威。", "gd.md"),
    ("gd-setup", "GD 插件预设配置（maker 适配薄壳）。采集安装者预设（审查产物输出位置/codex key 官方·第三方/codex 模型/effort 强度/运行环境），持久化到 CLAUDE_PLUGIN_DATA。读取 plugin gd-setup.md 执行，gd-setup.md 为唯一权威。", "gd-setup.md"),
    ("review1", "GD L1 交叉讨论/第二意见（默认）+ 轻量审核 --review（maker 适配薄壳）。/review1 让 Codex 给独立分析。读取 plugin review1.md 执行，review1.md 为唯一权威。", "review1.md"),
    ("review2", "GD L2 审查链路（maker 适配薄壳）。/review2 第二层审查。读取 plugin review2.md 执行，review2.md 为唯一权威。", "review2.md"),
]
n = 0
for name, desc, target in REGISTRY:
    body = skeleton
    body = body.replace("{{SKILL_NAME}}", name)
    body = body.replace("{{DESCRIPTION}}", desc)
    body = body.replace("{{GD_PROJECT_ROOT}}", root)
    body = body.replace("{{REDIRECT_TARGET}}", target)
    d = os.path.join(out_dir, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w") as f:
        f.write(body)
    print("  + {} -> {}/SKILL.md".format(name, d))
    n += 1
print("已生成 {} 个 maker 薄壳到 {}/".format(n, out_dir))
PYEOF
}

# --- 移除 project scope 的 maker 薄壳 --------------------------------------
do_rm_shells() {
  local root removed
  root="$(resolve_gd_project_root)"
  if [ -z "$root" ]; then
    echo "错误：无法解析 GD_PROJECT_ROOT。" >&2
    exit 2
  fi
  removed=0
  for s in $SHELL_SKILLS; do
    if [ -d "$root/.claude/skills/$s" ]; then
      rm -rf "$root/.claude/skills/$s"
      echo "  - $s"
      removed=$((removed + 1))
    fi
  done
  echo "已移除 ${removed} 个 maker 薄壳（${root}/.claude/skills/）。"
}

# --- 子命令分派 ------------------------------------------------------------
case "${1:-}" in
  --self-check) do_self_check; exit 0 ;;
  --gen-shells) do_gen_shells; exit 0 ;;
  --rm-shells)  do_rm_shells;  exit 0 ;;
esac

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  cat <<'EOF'
用法：
  gd-plugin-setup.sh               交互式配置 5 个预设字段（选项菜单）
  gd-plugin-setup.sh --self-check  只读自检：字段形态 + runtime_env + 薄壳状态（不交互、不写文件）
  gd-plugin-setup.sh --gen-shells  从模板生成 7 个 maker 薄壳到 project scope（runtime_env=xdt_maker 时）
  gd-plugin-setup.sh --rm-shells   移除 project scope 的 7 个 gd-*/review* 薄壳
  gd-plugin-setup.sh --help        显示本帮助

字段：a 审查产物输出位置 / b codex key 类型(官方·第三方)+值 / c codex 模型 / d 模型强度 effort
      e 运行环境 (xdt_maker 生成 project-scope 薄壳 / claude_code 移除薄壳用 plugin command)
预设写入：${CLAUDE_PLUGIN_DATA}/gd-setup-config.json（更新安全，可重跑单改任一项，零内置默认 key）
EOF
  exit 0
fi

# --- 解析持久化目录（fail-closed，不静默写 ~）-------------------------------
if [ -z "${CLAUDE_PLUGIN_DATA:-}" ]; then
  echo "错误：环境变量 \$CLAUDE_PLUGIN_DATA 未设置。" >&2
  echo "本脚本必须由 Claude Code 插件机制（/gd-setup 命令）调用，以拿到更新安全的数据目录。" >&2
  echo "请通过插件命令 /gd-setup 运行，而不要直接手动执行；不会静默写入 \$HOME。" >&2
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
cur_runtime="$(read_existing runtime_env)"

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

# c · codex 模型（选项制；gpt-5.5 为当前 latest/default，列首）
choose_option "c · codex 模型" "$cur_model" \
  "gpt-5.5" "gpt-5.4" "gpt-5.4-mini"
CODEX_MODEL="$CHOSEN"

# d · 模型强度 effort（选项制）
# none = gpt-5.5 显式无推理文本路径（reasoning.effort: none）；xhigh 为 codex 扩展上限。
choose_option "d · 模型强度（effort）" "$cur_effort" \
  "none" "low" "medium" "high" "xhigh"
EFFORT="$CHOSEN"

# e · 运行环境（决定 maker 薄壳生成到 project scope 还是移除）
choose_option "e · 运行环境（xdt_maker=生成 project-scope 薄壳 / claude_code=移除薄壳用 plugin command）" "$cur_runtime" \
  "xdt_maker" "claude_code"
RUNTIME_ENV="$CHOSEN"

# 推断 GD_PROJECT_ROOT（从脚本位置；非硬编码，解决 P1 可移植）
INFERRED_ROOT="$(infer_gd_project_root)"
if [ -z "$INFERRED_ROOT" ]; then
  echo "警告：无法从脚本位置推断 GD_PROJECT_ROOT，薄壳生成将不可用（其余预设仍保存）。" >&2
fi

# --- 写入 JSON（python3 stdlib，保留未改动的 key 值）------------------------
# fail-visibly：python3 写入失败时 if 分支捕获非零退出，明确报错并 exit 1，
# 绝不在写入失败时打印"完成"（否则 key 丢失却报成功）。
# key 经 GD_KEY_VALUE 环境变量传给子进程（单用户 macOS 场景；脚本由 heredoc 作
# stdin，无法再用 stdin 传 key）。
if ! GD_OUTPUT_LOCATION="$OUTPUT_LOCATION" \
     GD_KEY_TYPE="$KEY_TYPE" \
     GD_KEY_VALUE="$KEY_VALUE" \
     GD_CODEX_MODEL="$CODEX_MODEL" \
     GD_EFFORT="$EFFORT" \
     GD_RUNTIME_ENV="$RUNTIME_ENV" \
     GD_PROJECT_ROOT_INFERRED="$INFERRED_ROOT" \
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
    "runtime_env": os.environ["GD_RUNTIME_ENV"],
}

# gd_project_root：推断有效则持久化（薄壳渲染读它）；推断失败则保留已有值。
inferred = os.environ.get("GD_PROJECT_ROOT_INFERRED", "")
if inferred:
    cfg["gd_project_root"] = inferred
elif "gd_project_root" in existing:
    cfg["gd_project_root"] = existing["gd_project_root"]

# key 值留空 -> 保留已有；否则更新。绝不内置默认 key。
new_key = os.environ.get("GD_KEY_VALUE", "")
if new_key:
    cfg["key_value"] = new_key
elif "key_value" in existing:
    cfg["key_value"] = existing["key_value"]

# 以 0o600 原子创建（O_CREAT|O_TRUNC + mode），避免先 open(0o644) 再 chmod 的
# 明文短暂可读窗口。
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
os.chmod(path, 0o600)  # 幂等收紧（若文件已存在且权限更宽）
print("已写入预设：" + path)
PYEOF
then
  echo "错误：预设写入失败（${CLAUDE_PLUGIN_DATA:-未设置} 不可写 / 磁盘问题）。预设未保存。" >&2
  exit 1
fi

echo ""
echo "完成。预设已持久化到更新安全目录；重跑本命令可单独修改任一项。"
echo "提示：HANDOFF_ROOT 由插件管理，不在本预设内（填错即断链）。"

# --- 运行环境后置：按选择生成或移除 maker 薄壳（可重跑，换环境时自动切换）---
case "$RUNTIME_ENV" in
  xdt_maker)
    if [ -n "$INFERRED_ROOT" ]; then
      echo ""
      echo "→ runtime_env=xdt_maker，生成 maker 薄壳到 project scope…"
      do_gen_shells || echo "警告：薄壳生成失败（见上）。可单独重跑 --gen-shells。" >&2
    fi
    ;;
  claude_code)
    echo ""
    echo "→ runtime_env=claude_code，移除 project-scope maker 薄壳（改用 plugin command）…"
    do_rm_shells || echo "警告：薄壳移除失败（见上）。可单独重跑 --rm-shells。" >&2
    ;;
esac
