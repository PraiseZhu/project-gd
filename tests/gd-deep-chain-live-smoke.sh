#!/usr/bin/env bash
# gd-deep-chain-live-smoke.sh — Consolidated LIVE smoke for L2 + L3 deep review chains.
#
# PURPOSE:
#   Exercise the ACTUAL deep-review entry points end-to-end with live Codex and assert
#   each chain genuinely reviews (catches a fake skip / a semantic bug). This closes the
#   gap that let the phantom router-subcommand bug slip past unit tests: pytest tested
#   units (--help grep), but nothing ran the real `router review ... --deep` entry live.
#
#   L3-execution : router `review execution --deep`  → must catch fake skip (run_evidence skipped==1, non-APPROVED)
#   L3-code      : router `review code --deep`        → must catch semantic bug (finding → logic/semantic, non-APPROVED)
#   L2           : controller `--branch execution-only --deep` → must produce run_evidence skipped==1, non-APPROVED
#
# CLASSIFICATION: manual / release-time smoke — NOT a fast CI gate.
#   Each deep run takes ~2-5 min and requires:
#     - codex CLI on PATH + codex-watch daemon online (launchctl list | grep com.praise.codex-watch)
#     - daemon holding TAPSVC key (launchctl getenv TAPTAP_API_KEY)
#   Must run in NORMAL environment (not nested inside a Codex sandbox) — the deep paths
#   exercise ~/.claude runtime which a project-scoped sandbox cannot reach (see master-plan §9).
#
# USAGE:
#   bash tests/gd-deep-chain-live-smoke.sh
#   SKIP_L2=1 bash tests/gd-deep-chain-live-smoke.sh   # L3 only (faster)
#
# EXIT CODES:
#   0 — all enabled chains genuinely reviewed
#   1 — a chain failed to catch its planted defect (real regression)
#   3 — preconditions unmet (daemon offline / no key / nested sandbox)
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

SKIP_TGT="fixtures/deep-review/synthetic-skip-target"
SEM_TGT="fixtures/deep-review/synthetic-semantic-bug"
OUT_DIR="plans/gd/2026-06-13-codex-deep-review/results/live-smoke"
mkdir -p "$OUT_DIR"

# ── Preconditions ──────────────────────────────────────────────────────────
if [ -n "${GD_REVIEW_ROUTER_INVOCATION_ID:-}" ]; then
  echo "PRECOND_FAIL: GD_REVIEW_ROUTER_INVOCATION_ID is set — refusing to run inside a router/nested context"
  exit 3
fi
if ! command -v codex >/dev/null 2>&1; then
  echo "PRECOND_FAIL: codex CLI not on PATH — live smoke needs the deep chain online"
  exit 3
fi
if ! launchctl list 2>/dev/null | grep -q com.praise.codex-watch; then
  echo "PRECOND_FAIL: codex-watch daemon not running"
  exit 3
fi

FAIL=0
pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAIL=1; }

# ── L3-execution: review execution --deep must catch fake skip ───────────────
echo "[L3-execution] router review execution --deep (synthetic-skip-target)..."
R_EXEC="$OUT_DIR/l3-execution.json"; rm -f "$R_EXEC"
python3 scripts/gd-review-router.py review execution --deep \
  --target "$SKIP_TGT/outcome.json" \
  --plan-file "$SKIP_TGT/plan-snapshot.md" \
  --out "$R_EXEC" >/dev/null 2>&1 || true
if [ -f "$R_EXEC" ]; then
  python3 - "$R_EXEC" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
ev = d.get("run_evidence", []) or []
ok_skip = any(e.get("skipped") == 1 for e in ev)
ok_block = d.get("gd_review_decision") != "APPROVED"
ok_finding = any("skip" in json.dumps(f).lower() for f in d.get("findings", []))
sys.exit(0 if (ok_skip and ok_block and ok_finding) else 1)
PY
  if [ $? -eq 0 ]; then pass "L3-execution caught fake skip (run_evidence skipped==1, non-APPROVED, skip finding)"
  else fail "L3-execution did NOT catch fake skip — see $R_EXEC"; fi
else
  fail "L3-execution produced no result (entry point broken?) — see router output"
fi

# ── L3-code: review code --deep must catch semantic bug ──────────────────────
echo "[L3-code] router review code --deep (synthetic-semantic-bug)..."
R_CODE="$OUT_DIR/l3-code.json"; rm -f "$R_CODE"
python3 scripts/gd-review-router.py review code --deep \
  --target "$SEM_TGT/buggy_counter.py" \
  --plan-file "$SEM_TGT/plan-snapshot.md" \
  --out "$R_CODE" >/dev/null 2>&1 || true
if [ -f "$R_CODE" ]; then
  python3 - "$R_CODE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
ok_block = d.get("gd_review_decision") != "APPROVED"
txt = json.dumps(d.get("findings", []), ensure_ascii=False).lower()
ok_finding = any(k in txt for k in ("semantic", "语义", "logic", "buggy_counter", "计数", "failure", "pass"))
sys.exit(0 if (ok_block and ok_finding) else 1)
PY
  if [ $? -eq 0 ]; then pass "L3-code caught semantic bug (non-APPROVED, finding → logic/semantic)"
  else fail "L3-code did NOT catch semantic bug — see $R_CODE"; fi
else
  fail "L3-code produced no result (entry point broken?) — see router output"
fi

# ── L2: controller --deep must produce run_evidence skipped==1, non-APPROVED ─
if [ "${SKIP_L2:-0}" = "1" ]; then
  echo "[L2] skipped (SKIP_L2=1)"
else
  echo "[L2] controller --branch execution-only --deep (synthetic-skip-target)..."
  R_L2="$OUT_DIR/l2"; rm -rf "$R_L2"
  RID="livesmoke-l2-$(python3 -c 'import time; print(int(time.time()))')"
  python3 scripts/gd-review-controller.py --branch execution-only --deep \
    --queue-job-id "$RID" \
    --plan-file "$SKIP_TGT/plan-snapshot.md" \
    --cwd "$PROJECT_ROOT" \
    --output-dir "$R_L2" \
    --execution-result "$SKIP_TGT/outcome.json" \
    --max-rounds 2 >/dev/null 2>&1 || true
  if compgen -G "$R_L2/codex_mapped*.json" >/dev/null; then
    python3 - "$R_L2" <<'PY'
import json, sys, glob
fs = glob.glob(sys.argv[1] + "/codex_mapped*.json")
def _check(f):
    d = json.load(open(f))
    ev = d.get("run_evidence") or []
    return any(e.get("skipped") == 1 for e in ev) and d.get("gd_review_decision") != "APPROVED"
sys.exit(0 if any(_check(f) for f in fs) else 1)
PY
    if [ $? -eq 0 ]; then pass "L2 controller deep caught fake skip (run_evidence skipped==1, non-APPROVED)"
    else fail "L2 controller deep did NOT catch fake skip — see $R_L2"; fi
  else
    fail "L2 controller produced no codex_mapped result — see $R_L2"
  fi
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "DEEP_CHAIN_LIVE_SMOKE: PASS — both chains genuinely review (caught planted defects)"
  exit 0
else
  echo "DEEP_CHAIN_LIVE_SMOKE: FAIL — a chain failed to catch its planted defect (regression)"
  exit 1
fi
