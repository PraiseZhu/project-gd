# Phase 2: SC Extraction Helper v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
TEMPLATE_KIND: gd-plan

> 作者：Test Author
> 日期：2026-05-26
> 状态：draft

---

## Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：`sc_extraction helper correctness; path_classification correctness; L3 snapshot byte-identical`

---

## 目标链（Goal Chain）

```
PROJECT_GOAL: validate /review2 plan_review chain
CHAIN_GOAL:   shared helpers reduce duplication between L3 validator and preflight
PHASE_GOAL:   scripts/lib/sc_extraction.py and path_classification.py exist and pass smoke
TASK_GOAL:    bash scripts/gd-review2-sc-extraction-snapshot-smoke.sh exits 0
```

---

## 非目标

- 不修改 live `/Users/praise/.claude/` runtime

---

## 成功标准（SC）

- [ ] SC-1：sc_extraction module importable
  - verify (method: command): `python3 -c "from scripts.lib.sc_extraction import extract_sc_ids"`
  - expect: `exit 0`
- [ ] SC-2：L3 validator output byte-identical after import change
  - verify (method: command): `bash scripts/gd-review2-sc-extraction-snapshot-smoke.sh`
  - expect: `SC-4: PASS`

---

## 实施步骤

### Step 1：Create sc_extraction.py `[SC-1]`

WHERE: scripts/lib/sc_extraction.py

WHAT: Create shared module exporting SC_ID_RE and extract_sc_ids

WHY: Avoids duplicating regex between L3 validator and preflight

VERIFY: `python3 -c "from scripts.lib.sc_extraction import extract_sc_ids"` → exit 0

---

### Step 2：Update L3 validator import `[SC-2]`

WHERE: scripts/gd-validate-review-content-evidence.py line 27

WHAT: Replace inline _SC_ID_RE with import from lib.sc_extraction

WHY: Single source of truth for SC-ID grammar

VERIFY: `diff snapshot.txt current.txt` → empty diff

---

## 边界約束

**允許写入**：`Project GD/scripts/lib/`, `Project GD/fixtures/`

**禁止写入**：`/Users/praise/.claude/**`

---

## 依赖与前置条件

- Phase 1 dependency check report complete

---

## 风险与防护

| 风险 | 防护 |
|------|------|
| L3 output drift | snapshot byte-identical test |

---

## 交付物清单

| 文件 | 类型 | SC映射 | 验收状态 |
|------|------|--------|---------|
| scripts/lib/sc_extraction.py | new | SC-1 | [ ] |
| scripts/lib/path_classification.py | new | SC-1 | [ ] |
