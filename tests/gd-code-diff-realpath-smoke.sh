#!/usr/bin/env bash
# gd-code-diff-realpath-smoke.sh — code_diff 真实路径回归测试
#
# 覆盖范围（全部不调 codex / 无外部依赖）：
#   SC-DIR-1 (SC-1): build-capsule --kind code_diff --target <目录>
#              → 不崩 IsADirectoryError，输出 CODE_DIFF_TARGET_MUST_BE_FILE
#   SC-DIR-2 (SC-3): build-capsule --kind code_diff --target <.patch 文件>
#              → exit 0 + target_hash + capsule 写入
#   SC-DIR-3 (SC-4): build-capsule --kind plan --out <目录>
#              → 不崩 IsADirectoryError，输出 OUT_PATH_MUST_BE_FILE
#   SC-DIR-4 (SC-2): _materialize_code_diff_target() 对同时含 tracked 改动
#              + untracked 新文件的临时仓产出 .patch，且不改动 index

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BRIDGE="$PROJECT_ROOT/scripts/gd-codex-bridge-review.py"
CONTROLLER="$PROJECT_ROOT/scripts/gd-review-controller.py"
GOOD_PLAN="$PROJECT_ROOT/plans/gd/2026-06-16-fix-review-chain-bugs/master-plan.md"

PASS_COUNT=0
FAIL_COUNT=0
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

pass() { echo "  PASS: $1"; ((PASS_COUNT++)); }
fail() { echo "  FAIL: $1"; ((FAIL_COUNT++)); }

echo "=== gd-code-diff-realpath-smoke ==="
echo ""

# ---------------------------------------------------------------------------
# SC-DIR-1 (SC-1): directory --target → CODE_DIFF_TARGET_MUST_BE_FILE, no traceback
# ---------------------------------------------------------------------------
echo "--- SC-DIR-1: code_diff 目录 target → CODE_DIFF_TARGET_MUST_BE_FILE ---"
WDIR="$TMPROOT/wt1"
mkdir -p "$WDIR"
git -C "$WDIR" init -q
printf 'a\n' > "$WDIR/f.py"
git -C "$WDIR" add .
git -C "$WDIR" -c user.email=t@t -c user.name=t commit -qm seed
printf 'b\n' >> "$WDIR/f.py"  # tracked change

_ex=0
out=$(python3 "$BRIDGE" build-capsule \
    --kind code_diff \
    --target "$WDIR" \
    --cwd "$WDIR" \
    --out "$TMPROOT/sc1-out.json" \
    2>&1) || _ex=$?

if echo "$out" | grep -qE "IsADirectoryError|Traceback"; then
    fail "SC-DIR-1: 仍崩 IsADirectoryError/Traceback，守卫未生效"
elif echo "$out" | grep -qE "CODE_DIFF_TARGET_MUST_BE_FILE"; then
    pass "SC-DIR-1: 目录 target → CODE_DIFF_TARGET_MUST_BE_FILE (exit=$_ex)"
else
    fail "SC-DIR-1: 未见 CODE_DIFF_TARGET_MUST_BE_FILE，exit=$_ex，输出: $(echo "$out" | head -3)"
fi

# ---------------------------------------------------------------------------
# SC-DIR-2 (SC-3): .patch 文件 --target → exit 0 + target_hash
# ---------------------------------------------------------------------------
echo "--- SC-DIR-2: code_diff .patch 文件 target → capsule 产出 ---"
WDIR2="$TMPROOT/wt2"
mkdir -p "$WDIR2"
git -C "$WDIR2" init -q
printf 'hello\n' > "$WDIR2/main.py"
git -C "$WDIR2" add .
git -C "$WDIR2" -c user.email=t@t -c user.name=t commit -qm seed
printf 'world\n' >> "$WDIR2/main.py"

PATCH_FILE="$TMPROOT/test.patch"
git -C "$WDIR2" diff HEAD > "$PATCH_FILE"

_ex=0
out=$(python3 "$BRIDGE" build-capsule \
    --kind code_diff \
    --target "$PATCH_FILE" \
    --cwd "$WDIR2" \
    --out "$TMPROOT/sc2-capsule.md" \
    2>&1) || _ex=$?

if [[ $_ex -eq 0 ]] && echo "$out" | grep -qE "target_hash|capsule.*写入"; then
    pass "SC-DIR-2: .patch 文件 target → exit 0 + capsule 产出"
elif echo "$out" | grep -qE "IsADirectoryError|Traceback"; then
    fail "SC-DIR-2: 仍崩 IsADirectoryError/Traceback"
else
    fail "SC-DIR-2: 未见 target_hash/capsule，exit=$_ex，输出: $(echo "$out" | head -3)"
fi

# ---------------------------------------------------------------------------
# SC-DIR-3 (SC-4): --out 传目录 → OUT_PATH_MUST_BE_FILE, no traceback
# ---------------------------------------------------------------------------
echo "--- SC-DIR-3: --out 传目录 → OUT_PATH_MUST_BE_FILE ---"
OUT_DIR="$TMPROOT/outdir"
mkdir -p "$OUT_DIR"

_ex=0
out=$(python3 "$BRIDGE" build-capsule \
    --kind plan \
    --target "$GOOD_PLAN" \
    --cwd "$PROJECT_ROOT" \
    --out "$OUT_DIR" \
    2>&1) || _ex=$?

if echo "$out" | grep -qE "IsADirectoryError|Traceback"; then
    fail "SC-DIR-3: 仍崩 IsADirectoryError/Traceback，守卫未生效"
elif echo "$out" | grep -qE "OUT_PATH_MUST_BE_FILE"; then
    pass "SC-DIR-3: 目录 --out → OUT_PATH_MUST_BE_FILE (exit=$_ex)"
else
    fail "SC-DIR-3: 未见 OUT_PATH_MUST_BE_FILE，exit=$_ex，输出: $(echo "$out" | head -3)"
fi

# ---------------------------------------------------------------------------
# SC-DIR-4 (SC-2): _materialize_code_diff_target — tracked + untracked → .patch
#                   index 状态不变
# ---------------------------------------------------------------------------
echo "--- SC-DIR-4: _materialize_code_diff_target tracked+untracked .patch + index 不变 ---"
WDIR4="$TMPROOT/wt4"
mkdir -p "$WDIR4"
git -C "$WDIR4" init -q
printf 'tracked_original\n' > "$WDIR4/tracked.py"
git -C "$WDIR4" add .
git -C "$WDIR4" -c user.email=t@t -c user.name=t commit -qm seed

# tracked 改动
printf 'tracked_modified\n' >> "$WDIR4/tracked.py"
# untracked 新文件
printf 'brand_new\n' > "$WDIR4/untracked.py"

STATUS_BEFORE=$(git -C "$WDIR4" status --porcelain)

# 用 importlib 加载 controller（文件名含连字符，不能直接 import）
python3 - <<PYEOF
import importlib.util, pathlib, sys, tempfile

spec = importlib.util.spec_from_file_location(
    "gd_review_controller",
    "${CONTROLLER}",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

cwd = pathlib.Path("${WDIR4}")
output_dir = pathlib.Path("${TMPROOT}/mat_out")
output_dir.mkdir(parents=True, exist_ok=True)

# Reproduce what take_delta_snapshot does: git diff HEAD (tracked) +
# untracked via git ls-files --others + git diff --no-index
import subprocess

# tracked diff
r = subprocess.run(["git", "diff", "HEAD"], cwd=str(cwd),
                   capture_output=True, text=True)
diff_text = r.stdout or ""

# untracked files → pseudo-diff
uf_r = subprocess.run(
    ["git", "ls-files", "--others", "--exclude-standard"],
    cwd=str(cwd), capture_output=True, text=True,
)
for uf in (uf_r.stdout or "").splitlines():
    uf_path = cwd / uf
    nd_r = subprocess.run(
        ["git", "diff", "--no-index", "--", "/dev/null", str(uf_path)],
        capture_output=True, text=True,
    )
    # git diff --no-index exits 1 when files differ (expected)
    diff_text += nd_r.stdout or ""

patch = mod._materialize_code_diff_target(
    diff_text=diff_text,
    output_dir=output_dir,
    round_num=1,
    diff_unavailable=False,
)
if patch is None:
    print("MATERIALIZE_NONE")
    sys.exit(1)
if not patch.is_file():
    print("NOT_A_FILE")
    sys.exit(1)
content = patch.read_text(encoding="utf-8")
if "tracked_modified" not in content:
    print("MISSING_TRACKED_DIFF")
    sys.exit(1)
if "untracked.py" not in content:
    print("MISSING_UNTRACKED_FILE")
    sys.exit(1)
print(f"PATCH_OK: {patch} ({len(content)} bytes)")
PYEOF
_mat_exit=$?

STATUS_AFTER=$(git -C "$WDIR4" status --porcelain)

if [[ $_mat_exit -ne 0 ]]; then
    fail "SC-DIR-4: _materialize_code_diff_target 失败 (exit=$_mat_exit)"
elif [[ "$STATUS_BEFORE" != "$STATUS_AFTER" ]]; then
    fail "SC-DIR-4: index 状态被改动 (before='$STATUS_BEFORE' after='$STATUS_AFTER')"
else
    pass "SC-DIR-4: .patch 含 tracked+untracked diff，index 未变"
fi

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
echo ""
echo "=== 结果: PASS=${PASS_COUNT} FAIL=${FAIL_COUNT} ==="
if [[ $FAIL_COUNT -eq 0 ]]; then
    echo "ALL_PASS"
    exit 0
else
    echo "SOME_FAIL"
    exit 1
fi
