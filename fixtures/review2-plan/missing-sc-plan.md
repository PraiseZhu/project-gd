# Plan Without SC-IDs

GD_STANDARD: Project GD/prompts/gd-review-standard.md
TEMPLATE_KIND: gd-plan

> 状态：draft

## Review 对齐

- REVIEW_DOMAIN：`ai_infra`
- REVIEW_FOCUS：`missing sc test fixture`

## 目标链

```
PROJECT_GOAL: test plan
PHASE_GOAL: test state
TASK_GOAL: bash test.sh exits 0
```

## 实施步骤

### Step 1：Do Something

WHERE: scripts/test.py

WHAT: Do something

WHY: Because tests need it

VERIFY: `python3 scripts/test.py` → `OK`

## 边界约束

**允许写入**：`Project GD/`

**禁止写入**：`/Users/praise/.claude/**`
