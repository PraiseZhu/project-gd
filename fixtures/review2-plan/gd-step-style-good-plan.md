# Step 3: Template Update v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
TEMPLATE_KIND: gd-step-plan

日期：2026-05-26
状态：draft
负责人：Claude

---

## 1. 目标链（继承 + 当前 task goal）

```text
PROJECT_GOAL: validate /review2 plan_review chain
CHAIN_GOAL:   unified field contract between plan-template and preflight
PHASE_GOAL:   plan-template.md uses GD_STANDARD and WHERE/WHAT/WHY/VERIFY steps
TASK_GOAL:    bash scripts/gd-review2-plan-template-preflight-smoke.sh exits 0
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`docs_content`
- REVIEW_FOCUS：`template correctness; removed rev-style markers; added step fields`

---

## 3. 前置条件

- blocked_by：Phase 2
- 必须的 baseline：scripts/lib/sc_extraction.py, scripts/lib/path_classification.py

---

## 4. 成功标准（SC）

- [ ] SC-9：plan-template.md contains no REVIEW_STANDARD or REV_VERDICT
  - verify (method: command): `grep -c 'REVIEW_STANDARD\|REV_VERDICT' templates/plan-template.md`
  - expect: `0 or exit 1`
- [ ] SC-3：preflight accepts compliant plans
  - verify (method: command): `python3 scripts/gd-validate-review2-plan-target.py --target fixtures/review2-plan/good-plan.md`
  - expect: `PLAN_TEMPLATE_STATUS: pass`

---

## 5. 非目标

- 不动 gd-step-plan-template.md
- 不修改 ~/.claude/ runtime

---

## 6. 实现步骤

```text
Step.1  [SC-9]
  WHERE:  templates/plan-template.md
  WHAT:   Rewrite: replace REVIEW_STANDARD with GD_STANDARD; remove REV_VERDICT;
          add REVIEW_DOMAIN/REVIEW_FOCUS; convert steps to WHERE/WHAT/WHY/VERIFY
  WHY:    Aligns plan-template with gd-step-plan contract for /review2 preflight
  VERIFY: grep -c 'REVIEW_STANDARD\|REV_VERDICT' templates/plan-template.md → 0 or exit 1

Step.2  [SC-3, SC-5]
  WHERE:  scripts/gd-validate-review2-plan-target.py (new)
  WHAT:   Create field-based preflight that validates plan fields without binding to template
  WHY:    Accepts both plan-template.md and gd-step-plan-template.md style plans
  VERIFY: python3 scripts/gd-validate-review2-plan-target.py --target good-plan.md exits 0
```

---

## 8. 边界（修改 / 不修改）

修改：
- templates/plan-template.md
- scripts/gd-validate-review2-plan-target.py (new)

不修改：
- templates/gd-step-plan-template.md
- /Users/praise/.claude/**
