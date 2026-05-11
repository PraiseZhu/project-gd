# Phase 4 Parity Check Report

> 目的：证明 `prompts/rev-review-standard.md` 是 CLI runner (`bin/rev`) 与桌面端计划/review 的共同标准源。

---

## SC-15 Embed 证据

### 验证方法

```python
import re, glob
standard = open('prompts/rev-review-standard.md').read()
std_norm = re.sub(r'\s+', ' ', standard).strip()
for prompt_path in glob.glob('results/*-plan.*/prompt.md'):
    p_norm = re.sub(r'\s+', ' ', open(prompt_path).read()).strip()
    assert std_norm in p_norm, f'{prompt_path} does not embed rev-review-standard.md'
```

### 验证结果

| prompt.md 路径 | 状态 |
|----------------|------|
| `results/20260509T211740Z-plan.r2EEm5/prompt.md` | PASS（generic-bad dry-run） |
| `results/20260509T211744Z-plan.GMJRPN/prompt.md` | PASS（concrete-good dry-run） |
| `results/20260509T211751Z-plan.5hNgSL/prompt.md` | PASS（borderline dry-run） |
| `results/20260509T211847Z-plan.zERgyE/prompt.md` | PASS（generic-bad live） |
| `results/20260509T211924Z-plan.UjlUzd/prompt.md` | PASS（concrete-good live） |
| `results/20260509T211946Z-plan.PZZN3Q/prompt.md` | PASS（borderline live） |

**结论**：`bin/rev plan` 每次生成 prompt 时，直接 `cat "$REVIEW_STD"` 嵌入 `prompts/rev-review-standard.md` 全文（`bin/rev` line 170）。

---

## 共同标准源引用点

### 引用点 1：bin/rev（CLI runner）

```bash
# bin/rev line ~170
REVIEW_STD="$GD_ROOT/prompts/rev-review-standard.md"
{
    printf '## Review Standard\n\n'
    cat "$REVIEW_STD"
    ...
} > "$PROMPT_PATH"
```

- 来源文件：`Project GD/bin/rev`
- 引用方式：直接 cat 嵌入，非引用副本

### 引用点 2：Project GD CLAUDE.md（桌面端约定）

```
## 协作工作流 → Review 入口
| 本项目 plan 自审 | `bin/rev plan <plan-file>` | `prompts/rev-review-standard.md` |
| 本项目执行结果自审 | `bin/rev code <result-file>` | `prompts/rev-review-standard.md` |
```

- 来源文件：`Project GD/CLAUDE.md`
- 引用方式：Review 入口表格明确指向同一文件

### 引用点 3：桌面端 parity 约定（CLAUDE.md）

```
## 协作工作流 → Codex 桌面端 parity 约定
桌面端出方案时，plan 模板顶部必须写：
    REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md
桌面端按此引用的标准做自检，CLI runner 加载同一文件，两端 parity 靠同一份文档源保证。
```

- 来源文件：`Project GD/CLAUDE.md`
- 引用方式：明确要求桌面端计划顶部声明 `REVIEW_STANDARD:` 指向同一文件

### 引用点 4：templates/plan-template.md（计划模板）

计划模板顶部包含：
```
REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md
```

- 来源文件：`Project GD/templates/plan-template.md`
- 引用方式：模板硬编码引用，确保所有基于模板创建的计划都声明同一标准源

### 引用点 5：templates/execution-result-template.md

执行结果模板顶部包含：
```
REVIEW_STANDARD: Project GD/prompts/rev-review-standard.md
```

- 来源文件：`Project GD/templates/execution-result-template.md`
- 引用方式：模板硬编码引用

---

## Parity 结论

| 维度 | 结论 |
|------|------|
| CLI runner prompt embed | 直接嵌入原文（`cat "$REVIEW_STD"`），不是副本 |
| 桌面端 parity 约定 | CLAUDE.md 明确要求 `REVIEW_STANDARD:` 指向同一文件 |
| 模板声明 | plan-template.md + execution-result-template.md 均硬编码引用 |
| 共同标准源 | `Project GD/prompts/rev-review-standard.md` — 唯一真源 |

**parity verdict: PASS**

---

## 旧 `/review` 对比（静态）

| 维度 | 旧 `/review` (`build_review_prompt`) | `/rev` (`rev-review-standard.md`) |
|------|--------------------------------------|-----------------------------------|
| 模板来源 | 动态 heredoc，嵌入 codex-watch | 单一文件，CLI + 桌面端共用 |
| VERDICT 标记 | `VERDICT:` | `REV_VERDICT:`（避免触发 review-stop-marker.js） |
| SC 对照 | 无 SC 结构 | 逐条 SC 验收（conformance gate） |
| anti-fill 机制 | 无针对性设计 | SC 编号化 + 证据 anchor + not_run_reason |

> 注：此对照为静态 prompt 分析，不代表旧 `/review` live verdict 结果。

---

## 引用点汇总

共 5 个引用点均指向 `Project GD/prompts/rev-review-standard.md`：

| 编号 | 文件 | 引用方式 |
|------|------|---------|
| R-1 | `bin/rev` | `cat "$REVIEW_STD"` — runtime 嵌入 |
| R-2 | `CLAUDE.md` (Review 入口表) | 明确列出作为 review 标准文件 |
| R-3 | `CLAUDE.md` (parity 约定) | 要求桌面端 `REVIEW_STANDARD:` 声明 |
| R-4 | `templates/plan-template.md` | 顶部 `REVIEW_STANDARD:` 声明 |
| R-5 | `templates/execution-result-template.md` | 顶部 `REVIEW_STANDARD:` 声明 |
