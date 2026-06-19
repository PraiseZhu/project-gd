#!/usr/bin/env bash
# gd-step4-controller-transport-smoke.sh
# Step-4 regression guard for the shared-controller / transport fail-open fixes
# (plan: 2026-06-16-fix-review-chain-bugs, task step-4-shared-controller-transport).
#
# Covers, with positive AND negative assertions:
#   SC-9  N7  — controller wraps fut.result(); a bridge timeout/exception emits
#               CONVERGENCE_TIMEOUT (exit 1) instead of crashing the process.
#   SC-9  N10 — git-delta failure injects diff_unavailable (fanout=2 + capsule
#               flag) rather than fabricating a fake empty/clean delta.
#   SC-10 #13 — install-transport.sh uses exact `launchctl list "$label"` lookup,
#               not a substring grep.
#   SC-10 T1  — review-result-writer.sh emits `[REVIEW] ✗ FAILED` when a key
#               write (capsule copy) fails, instead of silently aborting.
#   SC-10 T-deep — review-result-writer.sh accepts deep bridge mode/timeout args
#               and forwards them to codex-send-wait.
#   SC-10 T-exit — review-result-writer.sh exits non-zero when transport is
#               unavailable, while parsed review verdicts still transport cleanly.
#   SC-10 T-watch — watch-state.sh recent_failed_jobs uses a glob (space-safe),
#               not `ls -r` word-splitting.
#
# Pinned to /bin/bash (macOS 3.2 — the daemon's runtime). NEVER deploys / loads
# a daemon: only --dry-run install-transport, sourced functions, and fixtures.
# Python harnesses are written to temp .py files (NOT heredoc-in-$()), so the
# f-string braces never trip bash-3.2 command-substitution parsing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTROLLER="$ROOT/scripts/gd-review-controller.py"
INSTALLER="$ROOT/vendor/l3-transport/scripts/install-transport.sh"
WRITER="$ROOT/vendor/l3-transport/scripts/review-result-writer.sh"
WATCH_STATE="$ROOT/vendor/l3-transport/handoff/lib/watch-state.sh"
STATE_PATHS="$ROOT/vendor/l3-transport/handoff/lib/state-paths.sh"

for f in "$CONTROLLER" "$INSTALLER" "$WRITER" "$WATCH_STATE" "$STATE_PATHS"; do
  [ -f "$f" ] || { echo "MISSING: $f" >&2; exit 1; }
done

fail=0
TMP_ROOT="$(mktemp -d "${TMPDIR:-/var/tmp}/gd-step4-smoke-XXXXXX")"
cleanup() {
  # Restore any chmod we did so rm -rf can clean up read-only fixtures.
  [ -d "$TMP_ROOT" ] && chmod -R u+rwx "$TMP_ROOT" 2>/dev/null || true
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

pass_msg() { echo "  ok: $*"; }
fail_msg() { echo "  FAIL: $*" >&2; fail=1; }

# ─────────────────────────────────────────────────────────────────────────────
# SC-9 N10 (positive): git-delta failure → diff_unavailable, fanout=2, no fake delta.
# Run take_delta_snapshot + run_round_n (stub path) against a NON-git dir so
# `git stash create` fails → diff_unavailable=true.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-9 N10: git-delta fail-closed (diff_unavailable, no fake delta) =="
N10_DIR="$TMP_ROOT/n10-nongit"
mkdir -p "$N10_DIR"
cat > "$TMP_ROOT/n10.py" <<'PY'
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("gd_review_controller", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

cwd = Path.cwd()  # NOT a git repo → git stash create fails → diff_unavailable

# 1) take_delta_snapshot must report diff_unavailable=True and EMPTY diff_text
#    (never a fabricated populated delta).
snap, diff_text, diff_unavailable = mod.take_delta_snapshot(cwd)
assert diff_unavailable is True, "expected diff_unavailable=True, got %r" % diff_unavailable
assert diff_text == "", "expected empty diff_text on failure, got %r" % diff_text

# 2) run_round_n with a stub: diff_unavailable must force fanout=2 (conservative)
#    and the capsule DELTA_SCOPE must carry diff_unavailable, not a "0 lines" delta.
stub = mod.StubDispatch()
f1 = mod._make_finding("F001")
stub._round_n_sequence = [[]]
baseline = [dict(f1)]
returned, snap_ref, dispatch_count = mod.run_round_n(
    round_num=2, kind="code_diff", target=cwd, cwd=cwd,
    output_dir=cwd / "out", invocation_id=mod.gen_id(),
    baseline_findings=baseline,
    threshold_lines=mod.DEFAULT_ROUND2_FANOUT_THRESHOLD_LINES,
    threshold_files=mod.DEFAULT_ROUND2_FANOUT_THRESHOLD_FILES,
    stub_dispatch=stub,
)
assert dispatch_count == 2, "diff_unavailable must fan out to 2, got %r" % dispatch_count
cf = stub.get_capsule_fields()[0]
assert cf["DIFF_UNAVAILABLE"] is True, "capsule DIFF_UNAVAILABLE should be True, got %r" % (cf,)
ds = cf["DELTA_SCOPE"]
assert "diff_unavailable: true" in ds, "DELTA_SCOPE must mark diff_unavailable, got: %r" % ds
assert "0 lines changed" not in ds, "must NOT fabricate a clean/0-line delta, got: %r" % ds
print("N10_OK")
PY
set +e
N10_OUT="$(cd "$N10_DIR" && python3 "$TMP_ROOT/n10.py" "$CONTROLLER" 2>&1)"
N10_RC=$?
set -e
if [ "$N10_RC" -eq 0 ] && echo "$N10_OUT" | grep -q "N10_OK"; then
  pass_msg "git-delta failure → diff_unavailable=true, fanout=2, no fake delta"
else
  fail_msg "SC-9 N10 assertions not satisfied (rc=$N10_RC, output: $N10_OUT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-9 N10 (control): a REAL git repo with changes must NOT be flagged
# diff_unavailable and must produce a populated delta — proves no blanket close.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-9 N10 (control): real git delta is available =="
N10G_DIR="$TMP_ROOT/n10-git"
mkdir -p "$N10G_DIR"
( cd "$N10G_DIR" \
  && git init -q . \
  && printf 'seed\n' > file.txt \
  && git add file.txt \
  && git -c user.email=t@t.com -c user.name=T commit -qm seed \
  && printf 'changed line\nsecond\n' >> file.txt )
cat > "$TMP_ROOT/n10ctrl.py" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("gd_review_controller", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
snap, diff_text, diff_unavailable = mod.take_delta_snapshot(Path.cwd())
assert diff_unavailable is False, "real repo should have available delta, got %r" % diff_unavailable
assert "changed line" in diff_text, "expected real diff content, got: %r" % diff_text
print("N10_CONTROL_OK")
PY
set +e
N10G_OUT="$(cd "$N10G_DIR" && python3 "$TMP_ROOT/n10ctrl.py" "$CONTROLLER" 2>&1)"
N10G_RC=$?
set -e
if [ "$N10G_RC" -eq 0 ] && echo "$N10G_OUT" | grep -q "N10_CONTROL_OK"; then
  pass_msg "real git delta available (diff_unavailable=false, populated diff)"
else
  fail_msg "SC-9 N10 control failed (rc=$N10G_RC, output: $N10G_OUT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-9 N7: a Round-1 codex future that RAISES must surface CONVERGENCE_TIMEOUT
# and exit 1 — not a raw traceback. Monkeypatch _invoke_bridge_mapped to raise.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-9 N7: codex future exception → CONVERGENCE_TIMEOUT (no crash) =="
N7_DIR="$TMP_ROOT/n7-git"
mkdir -p "$N7_DIR"
( cd "$N7_DIR" \
  && git init -q . \
  && printf 'seed\n' > f.txt \
  && git add f.txt \
  && git -c user.email=t@t.com -c user.name=T commit -qm seed )
cat > "$TMP_ROOT/n7.py" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("gd_review_controller", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def _boom(*a, **k):
    raise RuntimeError("simulated bridge timeout")
mod._invoke_bridge_mapped = _boom

try:
    mod.run_round1(
        kind="code_diff", target=Path.cwd(), cwd=Path.cwd(),
        output_dir=Path.cwd() / "out", invocation_id=mod.gen_id(),
        claude_findings=[], stub_dispatch=None,   # None = REAL dispatch path
    )
except SystemExit as e:
    print("GOT_SYSTEMEXIT code=%s" % e.code)
    sys.exit(0)
except BaseException as e:
    print("UNEXPECTED_RAW_EXCEPTION %s: %s" % (type(e).__name__, e))
    sys.exit(2)
print("NO_EXIT_NO_RAISE")
sys.exit(3)
PY
set +e
N7_OUT="$(cd "$N7_DIR" && python3 "$TMP_ROOT/n7.py" "$CONTROLLER" 2>&1)"
N7_RC=$?
set -e
if [ "$N7_RC" -eq 0 ] \
   && echo "$N7_OUT" | grep -q "CONVERGENCE_TIMEOUT" \
   && echo "$N7_OUT" | grep -q "GOT_SYSTEMEXIT code=1"; then
  pass_msg "Round-1 future exception → CONVERGENCE_TIMEOUT + SystemExit(1)"
else
  fail_msg "SC-9 N7 did not fail closed (rc=$N7_RC, output: $N7_OUT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-10 #13: install-transport.sh must use exact `launchctl list "$label"`
# lookup, NOT a substring `launchctl list | grep`. Static source assertion.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-10 #13: install-transport launchctl exact lookup =="
if grep -qE 'launchctl[[:space:]]+list[[:space:]]+"\$_?label"' "$INSTALLER"; then
  pass_msg "install-transport uses launchctl list \"\$_label\" (exact)"
else
  fail_msg "install-transport missing exact launchctl list \"\$label\" lookup"
fi
# Exclude comment lines ("N:<spaces>#...") so the prose describing the OLD
# pattern does not count as a live occurrence.
if grep -nE 'launchctl[[:space:]]+list[[:space:]]*\|[[:space:]]*grep' "$INSTALLER" \
     | grep -vE '^[0-9]+:[[:space:]]*#' >/dev/null; then
  fail_msg "install-transport still has fuzzy 'launchctl list | grep' lookup"
else
  pass_msg "no fuzzy 'launchctl list | grep' remains"
fi
set +e
INSTALL_DRY_OUT="$(bash "$INSTALLER" --dry-run 2>&1)"
INSTALL_DRY_RC=$?
set -e
if [ "$INSTALL_DRY_RC" -eq 0 ] && echo "$INSTALL_DRY_OUT" | grep -q "DRY-RUN COMPLETE"; then
  pass_msg "install-transport --dry-run completes without deploying"
else
  fail_msg "install-transport --dry-run failed (rc=$INSTALL_DRY_RC)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-10 T1: review-result-writer.sh must emit `[REVIEW] ✗ FAILED` when a key
# write (capsule copy) fails — never abort silently under set -e.
# BASELINE_DIR exists but is read-only so mkdir -p succeeds and `cp` fails.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-10 T1: writer fails loud on key-write failure =="
T1_OUTROOT="$TMP_ROOT/t1-out"
T1_KEY="abcdef012345"
T1_BASELINE_DIR="$T1_OUTROOT/$T1_KEY"
mkdir -p "$T1_BASELINE_DIR"
T1_CAPSULE="$TMP_ROOT/t1-capsule.txt"
printf 'REVIEW_DOMAIN: other\nPROJECT_ROOT: %s\n' "$TMP_ROOT" > "$T1_CAPSULE"
chmod -w "$T1_BASELINE_DIR"
set +e
T1_OUT="$(bash "$WRITER" \
  --capsule-file "$T1_CAPSULE" \
  --baseline-key "$T1_KEY" \
  --review-kind code \
  --out-dir "$T1_OUTROOT" \
  --cwd "$TMP_ROOT" 2>&1)"
T1_RC=$?
set -e
chmod u+w "$T1_BASELINE_DIR" 2>/dev/null || true
if [ "$T1_RC" -ne 0 ] && echo "$T1_OUT" | grep -q '\[REVIEW\] ✗ FAILED'; then
  pass_msg "writer emits [REVIEW] ✗ FAILED on key-write failure (rc=$T1_RC)"
else
  fail_msg "writer did not fail loud on key-write failure (rc=$T1_RC, output: $T1_OUT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-10 T-deep: bridge deep mode passes --mode workspace-write --send-timeout N.
# The vendor writer must accept and forward those args instead of rejecting them
# before codex-send-wait starts.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-10 T-deep: writer accepts deep bridge mode/timeout args =="
if grep -F -- '--mode) MODE="$2"; shift 2 ;;' "$WRITER" >/dev/null \
   && grep -F -- '--send-timeout) SEND_TIMEOUT="$2"; shift 2 ;;' "$WRITER" >/dev/null \
   && grep -F -- '--mode "$MODE"' "$WRITER" >/dev/null \
   && grep -F -- '--timeout "$SEND_TIMEOUT"' "$WRITER" >/dev/null; then
  pass_msg "writer accepts --mode/--send-timeout and forwards them to codex-send-wait"
else
  fail_msg "writer does not support deep bridge --mode/--send-timeout forwarding"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-10 T-paths: state-paths should align a normal shell with the installed
# plugin data root when CLAUDE_PLUGIN_DATA is unset, while preserving explicit
# HANDOFF_ROOT overrides for isolated tests.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-10 T-paths: state-paths plugin data fallback + override =="
TPATH_HOME="$TMP_ROOT/tpath-home"
mkdir -p "$TPATH_HOME/.claude/plugins/data/codex-openai-codex/gd-handoff"
TPATH_EXPECT="$TPATH_HOME/.claude/plugins/data/codex-openai-codex/gd-handoff"
TPATH_OUT="$(HOME="$TPATH_HOME" bash -c 'unset CLAUDE_PLUGIN_DATA; . "$1"; printf "%s" "$HANDOFF_ROOT"' _ "$STATE_PATHS")"
if [ "$TPATH_OUT" = "$TPATH_EXPECT" ]; then
  pass_msg "state-paths defaults to plugin data gd-handoff when installed"
else
  fail_msg "state-paths plugin data fallback mismatch (got '$TPATH_OUT', want '$TPATH_EXPECT')"
fi
TPATH_ENV_OUT="$(HOME="$TPATH_HOME" bash -c 'unset CLAUDE_PLUGIN_DATA; . "$1"; env | grep "^HANDOFF_ROOT=" | cut -d= -f2-' _ "$STATE_PATHS")"
if [ "$TPATH_ENV_OUT" = "$TPATH_EXPECT" ]; then
  pass_msg "state-paths exports HANDOFF_ROOT for child codex-send-wait"
else
  fail_msg "state-paths did not export HANDOFF_ROOT (got '$TPATH_ENV_OUT', want '$TPATH_EXPECT')"
fi
TPATH_OVERRIDE="$TMP_ROOT/explicit-handoff"
TPATH_OUT2="$(HOME="$TPATH_HOME" HANDOFF_ROOT="$TPATH_OVERRIDE" bash -c 'unset CLAUDE_PLUGIN_DATA; . "$1"; printf "%s" "$HANDOFF_ROOT"' _ "$STATE_PATHS")"
if [ "$TPATH_OUT2" = "$TPATH_OVERRIDE" ]; then
  pass_msg "state-paths preserves explicit HANDOFF_ROOT override"
else
  fail_msg "state-paths did not preserve HANDOFF_ROOT override (got '$TPATH_OUT2')"
fi
TPATH_PLUGIN_DATA="$TMP_ROOT/explicit-plugin-data"
mkdir -p "$TPATH_PLUGIN_DATA/gd-handoff"
TPATH_OUT3="$(HOME="$TPATH_HOME" CLAUDE_PLUGIN_DATA="$TPATH_PLUGIN_DATA" bash -c '. "$1"; printf "%s" "$HANDOFF_ROOT"' _ "$STATE_PATHS")"
if [ "$TPATH_OUT3" = "$TPATH_PLUGIN_DATA/gd-handoff" ]; then
  pass_msg "state-paths preserves explicit CLAUDE_PLUGIN_DATA precedence"
else
  fail_msg "state-paths did not preserve CLAUDE_PLUGIN_DATA precedence (got '$TPATH_OUT3')"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-10 T-exit: transport failure must not look successful to shell callers.
# codex-send-wait is intentionally absent under this isolated HANDOFF_ROOT.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-10 T-exit: writer transport failure exits non-zero =="
TEXIT_ROOT="$TMP_ROOT/texit-handoff"
TEXIT_PLUGIN="$TMP_ROOT/texit-plugin"
TEXIT_OUTDIR="$TMP_ROOT/texit-baselines"
mkdir -p "$TEXIT_ROOT/bin" "$TEXIT_PLUGIN" "$TEXIT_OUTDIR"
TEXIT_CAP="$TMP_ROOT/texit-capsule.md"
cat > "$TEXIT_CAP" <<'EOF'
REVIEW_DOMAIN: ai_infra
REVIEW_KIND: plan
REVIEW_ROUND: initial
REVIEW_DELTA_SCOPE: full_matrix
PLAN_ALIGNMENT_PRESENT: true
REVIEW_FOCUS: validation/runtime health
EOF
set +e
TEXIT_OUT="$(HOME="$TMP_ROOT/texit-home" HANDOFF_ROOT="$TEXIT_ROOT" CLAUDE_PLUGIN_DATA="$TEXIT_PLUGIN" \
  bash "$WRITER" --capsule-file "$TEXIT_CAP" --baseline-key texit --review-kind plan \
    --cwd "$ROOT" --out-dir "$TEXIT_OUTDIR" --no-stop-marker 2>&1)"
TEXIT_RC=$?
set -e
if [ "$TEXIT_RC" -ne 0 ] && printf '%s\n' "$TEXIT_OUT" | grep -q 'DEGRADED'; then
  pass_msg "writer transport unavailable → non-zero exit + DEGRADED output"
else
  fail_msg "writer transport unavailable did not fail closed (rc=$TEXIT_RC, output: $(printf '%s' "$TEXIT_OUT" | tr '\n' '|'))"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SC-10 T-watch: recent_failed_jobs must handle a HANDOFF_ACTIVE path with a
# space without slicing job names.
# ─────────────────────────────────────────────────────────────────────────────
echo "== SC-10 T-watch: recent_failed_jobs space-safe (no ls -r split) =="
# Exclude comment lines so the prose describing the OLD pattern isn't flagged.
if grep -nE 'for[[:space:]]+sf[[:space:]]+in[[:space:]]+\$\(ls[[:space:]]+-r' "$WATCH_STATE" \
     | grep -vE '^[0-9]+:[[:space:]]*#' >/dev/null; then
  fail_msg "watch-state still uses 'for sf in \$(ls -r ...)' (space-unsafe)"
else
  pass_msg "no 'ls -r' word-splitting in watch-state"
fi
TWATCH_BASE="$TMP_ROOT/handoff with space"
TWATCH_ACTIVE="$TWATCH_BASE/active"
mkdir -p "$TWATCH_ACTIVE" "$TWATCH_BASE/state"
printf 'failed\n'  > "$TWATCH_ACTIVE/job-one.status"
printf 'done\n'    > "$TWATCH_ACTIVE/job-two.status"
printf 'failed\n'  > "$TWATCH_ACTIVE/job-three.status"
touch "$TWATCH_ACTIVE/job-three.status"   # newest → "newest first" ordering check
cat > "$TMP_ROOT/twatch.sh" <<TWPY
set -euo pipefail
export HANDOFF_ACTIVE="$TWATCH_ACTIVE"
export HANDOFF_STATE="$TWATCH_BASE/state"
export HANDOFF_PID="$TWATCH_BASE/state/pid"
source "$WATCH_STATE"
recent_failed_jobs 5
TWPY
set +e
TWATCH_OUT="$(/bin/bash "$TMP_ROOT/twatch.sh" 2>&1)"
TWATCH_RC=$?
set -e
TWATCH_COUNT="$(printf '%s\n' "$TWATCH_OUT" | grep -c 'job-' || true)"
if [ "$TWATCH_RC" -eq 0 ] \
   && printf '%s\n' "$TWATCH_OUT" | grep -qx 'job-one' \
   && printf '%s\n' "$TWATCH_OUT" | grep -qx 'job-three' \
   && ! printf '%s\n' "$TWATCH_OUT" | grep -qx 'job-two' \
   && [ "$TWATCH_COUNT" = "2" ]; then
  pass_msg "recent_failed_jobs returns intact failed job ids under spaced path"
else
  fail_msg "recent_failed_jobs mis-handled spaced path (rc=$TWATCH_RC, count=$TWATCH_COUNT, out: $(printf '%s' "$TWATCH_OUT" | tr '\n' '|'))"
fi

# ─────────────────────────────────────────────────────────────────────────────
echo ""
if [ "$fail" = "0" ]; then
  echo "SMOKE_RESULT: PASS (SC-9 N7/N10 + SC-10 #13/T1/T-watch)"
  exit 0
else
  echo "SMOKE_RESULT: FAIL" >&2
  exit 1
fi
