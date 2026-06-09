/**
 * plan-mode-antifill-stop-hook.js — Plan Mode Anti-Fill Stop Hook (SOURCE ONLY)
 *
 * SOURCE-ONLY: 本文件不注册、不激活、不写 ~/.claude/
 * 安装到 live 由 T9 deploy + ledger 授权完成，本文件本身 do not install。
 * (source-only; installation to live requires T9 deploy + ledger authorization)
 *
 * Purpose:
 *   Intercept Claude Code "plan mode" Stop events and block plans that fail
 *   the anti-fill hard gate — the same semantic gate applied by
 *   gd-validate-review2-plan-target.py (SC-4.1 / SC-4.2):
 *
 *   SC-4.1  Every SC block must contain a non-empty `verify (method: ...): ...`
 *           or `verify: ...` line.
 *   SC-4.2  If an `expect:` line is present in an SC block, its value must not
 *           be a pure generic word (通过|正确|完成|works|pass|ok|成功) without
 *           any concrete output string / exit code / numeric value / literal token.
 *
 * Hook contract (Claude Code PostToolUse / Stop hook stdin schema):
 *   {
 *     "hook_event_name": "Stop",
 *     "session_id": "...",
 *     "transcript_path": "...",   // path to current transcript JSON
 *     "plan_text": "...",         // optional: injected plan text if available
 *     "stop_hook_active": true
 *   }
 *
 *   Hook output (stdout):
 *     On violation: non-zero exit + print PLAN_ANTIFILL_FAIL lines
 *     On pass:      exit 0 (no output required)
 *
 * Usage (once installed via T9):
 *   Node.js >= 16 required. Run as:
 *     node plan-mode-antifill-stop-hook.js  (reads JSON from stdin)
 */

"use strict";

// ---------------------------------------------------------------------------
// Anti-fill constants — mirror of the Python implementation
// ---------------------------------------------------------------------------

/** Generic words whose sole presence in an expect value signals empty fill. */
const GENERIC_WORDS = new Set([
  "通过", "正确", "完成", "works", "pass", "ok", "成功",
  "通过了", "已完成", "已通过", "已正确",
]);

// ---------------------------------------------------------------------------
// Regex patterns
// ---------------------------------------------------------------------------

/**
 * SC-ID pattern — mirrors SC_ID_RE in scripts/lib/sc_extraction.py.
 * Must end with a digit; supports compound forms like SC-W1-1, H2B-SC-14.
 */
const SC_ID_RE = /\b(?:[A-Za-z][A-Za-z0-9]*-)?SC-[A-Za-z]*[0-9]+(?:-[0-9]+)?\b/g;

/**
 * SC block start line: list item / heading containing an SC-ID near the start.
 */
const SC_START_RE = /^[\s\-*>]*(?:[A-Za-z][A-Za-z0-9]*-)?SC-[A-Za-z]*[0-9]+(?:-[0-9]+)?\b/gm;

/**
 * Per-SC verify line with non-empty content after the colon.
 * Matches: verify (method: ...): <non-empty>  OR  verify: <non-empty>
 */
const SC_VERIFY_LINE_RE = /verify\s*(?:\([^)]*\))?\s*[：:]\s*\S/i;

/**
 * Expect line — captures the value portion.
 */
const SC_EXPECT_LINE_RE = /expect\s*[：:]\s*(.+)/i;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Strip all whitespace, quotes, punctuation, and markdown emphasis chars,
 * then lowercase — used for generic-word comparison.
 *
 * @param {string} s
 * @returns {string}
 */
function stripPunctuationWhitespace(s) {
  return s.replace(/[\s\W_]+/gu, "").toLowerCase();
}

/**
 * Return true if the expect value is entirely composed of generic words
 * (no concrete output string, exit code, numeric value, path, or literal token).
 *
 * @param {string} value — raw text after the "expect:" colon
 * @returns {boolean}
 */
function isPureGenericExpect(value) {
  const stripped = stripPunctuationWhitespace(value);
  if (!stripped) return true; // empty expect = generic

  // Direct match against a single generic word.
  if (GENERIC_WORDS.has(stripped)) return true;

  // Concatenation-only check: remove all generic words; if nothing remains
  // the value was composed purely of generic words.
  let remainder = stripped;
  for (const word of GENERIC_WORDS) {
    remainder = remainder.split(word).join("");
  }
  return remainder.length === 0;
}

/**
 * Extract (scId, blockText) pairs from plan text.
 * Each block starts at an SC-ID line and ends just before the next SC-ID line
 * or end-of-text.
 *
 * @param {string} text
 * @returns {Array<{scId: string, block: string}>}
 */
function extractScBlocks(text) {
  const blocks = [];

  // Collect all SC start match positions.
  const startRe = new RegExp(SC_START_RE.source, "gm");
  const scIdRe = new RegExp(SC_ID_RE.source, "");

  const matches = [];
  let m;
  while ((m = startRe.exec(text)) !== null) {
    const idMatch = scIdRe.exec(m[0]);
    if (idMatch) {
      matches.push({ scId: idMatch[0], index: m.index });
    }
  }

  for (let i = 0; i < matches.length; i++) {
    const start = matches[i].index;
    const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
    blocks.push({ scId: matches[i].scId, block: text.slice(start, end) });
  }

  return blocks;
}

// ---------------------------------------------------------------------------
// Core anti-fill gate
// ---------------------------------------------------------------------------

/**
 * Run the anti-fill hard gate on plan text.
 *
 * @param {string} planText
 * @returns {string[]} Array of PLAN_ANTIFILL_FAIL message strings (empty = pass)
 */
function checkAntifill(planText) {
  const failures = [];
  const scBlocks = extractScBlocks(planText);

  if (scBlocks.length === 0) {
    // No SC blocks — structural validator will catch missing SC-IDs.
    return failures;
  }

  for (const { scId, block } of scBlocks) {
    // SC-4.1: each SC block must have a verify line with non-empty content.
    if (!SC_VERIFY_LINE_RE.test(block)) {
      failures.push(
        `${scId} 缺 verify 行 — 每条 SC 必须含可执行 verify (method: command|path|assertion|test): <内容>`
      );
    }

    // SC-4.2: if expect line present, its value must not be pure generic.
    const expectMatch = SC_EXPECT_LINE_RE.exec(block);
    if (expectMatch) {
      const expectValue = expectMatch[1].trim();
      if (isPureGenericExpect(expectValue)) {
        failures.push(
          `${scId} expect 为纯泛词 (${JSON.stringify(expectValue)}) — ` +
          "expect 必须含具体输出串/exit code/数值/路径/字面 token，" +
          "不得只写通过|正确|完成|works|pass|ok|成功"
        );
      }
    }
  }

  return failures;
}

// ---------------------------------------------------------------------------
// Hook entry point — reads JSON from stdin, exits non-zero on violations
// ---------------------------------------------------------------------------

/**
 * Read all stdin data, parse JSON hook payload, extract plan text, and run gate.
 */
async function main() {
  let rawInput = "";

  // Read stdin (works both in interactive pipe and when data is passed directly).
  await new Promise((resolve) => {
    if (process.stdin.isTTY) {
      // No piped input in TTY mode — nothing to check; exit clean.
      resolve();
      return;
    }
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { rawInput += chunk; });
    process.stdin.on("end", resolve);
    process.stdin.on("error", resolve);
  });

  if (!rawInput.trim()) {
    // No input — nothing to validate.
    process.exit(0);
  }

  let payload;
  try {
    payload = JSON.parse(rawInput);
  } catch {
    // Malformed JSON — fail visibly rather than silently pass.
    process.stderr.write("[plan-mode-antifill-stop-hook] WARNING: could not parse stdin JSON — skipping gate\n");
    process.exit(0);
  }

  // Extract plan text from hook payload.
  // Claude Code Stop hook may inject plan text via `plan_text` field,
  // or via the transcript at `transcript_path`. We check `plan_text` first.
  let planText = "";

  if (typeof payload.plan_text === "string" && payload.plan_text.trim()) {
    planText = payload.plan_text;
  } else if (typeof payload.transcript_path === "string") {
    // Attempt to read the last assistant message from the transcript.
    try {
      const fs = require("fs");
      const transcriptRaw = fs.readFileSync(payload.transcript_path, "utf8");
      const transcript = JSON.parse(transcriptRaw);
      // Transcript is an array of messages; find the last assistant text block.
      const messages = Array.isArray(transcript) ? transcript : (transcript.messages || []);
      for (let i = messages.length - 1; i >= 0; i--) {
        const msg = messages[i];
        if (msg.role === "assistant") {
          if (typeof msg.content === "string") {
            planText = msg.content;
          } else if (Array.isArray(msg.content)) {
            planText = msg.content
              .filter((b) => b.type === "text")
              .map((b) => b.text)
              .join("\n");
          }
          if (planText.trim()) break;
        }
      }
    } catch {
      // Transcript unreadable — skip gate rather than block erroneously.
      process.stderr.write("[plan-mode-antifill-stop-hook] WARNING: could not read transcript — skipping gate\n");
      process.exit(0);
    }
  }

  if (!planText.trim()) {
    // No plan text available — cannot validate; pass through.
    process.exit(0);
  }

  // Run anti-fill gate.
  const failures = checkAntifill(planText);

  if (failures.length === 0) {
    // All SC blocks pass — allow Stop.
    process.exit(0);
  }

  // Violations found — block Stop and print PLAN_ANTIFILL_FAIL signals.
  for (const f of failures) {
    process.stdout.write(`PLAN_ANTIFILL_FAIL: ${f}\n`);
  }
  process.stdout.write(
    "\n[plan-mode-antifill-stop-hook] Plan blocked: fix the above anti-fill violations before stopping.\n"
  );
  process.exit(1);
}

main().catch((err) => {
  process.stderr.write(`[plan-mode-antifill-stop-hook] ERROR: ${err.message}\n`);
  process.exit(1);
});
