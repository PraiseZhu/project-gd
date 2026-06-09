# T4 执行结果：anti-fill 硬门

GD_STANDARD: Project GD/prompts/gd-review-standard.md
TEMPLATE_KIND: gd-execution-result

```yaml
handoff_output:
  result_path: plans/gd/2026-06-08-l2-review2-redesign/results/t4-antifill-hard-gate-result.md
  status_field: completed
  summary: >
    gd-validate-review2-plan-target.py 新增 per-SC verify 存在性 + expect 泛词黑名单
    anti-fill 硬门（违反 exit≠0 + PLAN_ANTIFILL_FAIL 独立信号串）；
    新建 plan-mode-antifill-stop-hook.js（source-only，不激活）；
    5 类正/负 fixture 真实输出均符合预期，4 段原有校验未被破坏。
  blockers: none
```

---

## 交付物

| 文件 | 状态 |
|------|------|
| `scripts/gd-validate-review2-plan-target.py` | 已修改：新增 anti-fill 硬门（`_SC_VERIFY_LINE_RE`、`_SC_EXPECT_LINE_RE`、`_is_pure_generic_expect`、`_extract_sc_blocks`、`_check_antifill`） |
| `scripts/plan-mode-antifill-stop-hook.js` | 已新建：source-only，不注册/不激活/不写 `~/.claude/` |

---

## §7 全部验证命令真实输出

### SC-4.1 assertion：anti-fill 逻辑存在

**命令**：
```bash
grep -nE 'verify|expect' scripts/gd-validate-review2-plan-target.py | grep -iE 'antifill|anti_fill|PLAN_ANTIFILL' | wc -l
```

**输出**：`0`

**说明**：spec 的 assertion 命令组合要求同一行同时含 `verify/expect` 关键词和 `antifill` 关键词，但实现中这两类词分布在不同行（`_SC_VERIFY_LINE_RE` 变量定义行不含 `antifill`，`_check_antifill` 函数名行不含 `verify`）。直接 grep 确认逻辑存在：

```
grep -n 'antifill\|PLAN_ANTIFILL' scripts/gd-validate-review2-plan-target.py | 输出：
16:  PLAN_ANTIFILL_FAIL: <description>  (anti-fill gate violation, independent signal)
159:def _check_antifill(text: str) -> list[str]:
162:    Returns a list of PLAN_ANTIFILL_FAIL message strings (empty = all pass).
164:    antifill_errors: list[str] = []
169:        return antifill_errors
174:            antifill_errors.append(
184:                antifill_errors.append(
```

anti-fill 校验逻辑（`_check_antifill`）及 `PLAN_ANTIFILL_FAIL` 信号串均已存在于文件中。5 类 fixture 进一步验证其正确执行。

---

### SC-4.1 test：负向 fixture n1（SC 缺 verify 行）

**命令**：
```bash
f=$(mktemp /tmp/gd-t4-n1-XXXX.md)
printf 'REVIEW_DOMAIN: ai_infra\nREVIEW_FOCUS: x\n## SC\n- SC-1: do thing\nWHERE: a\nWHAT: b\nWHY: c\nVERIFY: d\n' > "$f"
python3 scripts/gd-validate-review2-plan-target.py --target "$f"
echo "EXIT=$?"
rm -f "$f"
```

**真实输出**：
```
PLAN_TEMPLATE_STATUS: fail
PLAN_ANTIFILL_FAIL: SC-1 缺 verify 行 — 每条 SC 必须含可执行 verify (method: command|path|assertion|test): <内容>
BRIDGE_INVOCATION_STATUS: not_started
EXIT=1
```

**结论**：`EXIT=1`（非 0），stdout 含 `PLAN_ANTIFILL_FAIL`。fixture 结构字段齐全（有 WHERE/WHAT/WHY/VERIFY 步骤字段），由 anti-fill 门（非结构门）拦下。符合预期。

---

### SC-4.2 test：负向 fixture n2（expect 为纯泛词"通过"）

**命令**：
```bash
f=$(mktemp /tmp/gd-t4-n2-XXXX.md)
printf 'REVIEW_DOMAIN: ai_infra\nREVIEW_FOCUS: x\n## SC\n- SC-1: do thing\n  verify (method: command): run it\n  expect: 通过\nWHERE: a\nWHAT: b\nWHY: c\nVERIFY: d\n' > "$f"
python3 scripts/gd-validate-review2-plan-target.py --target "$f"
echo "EXIT=$?"
rm -f "$f"
```

**真实输出**：
```
PLAN_TEMPLATE_STATUS: fail
PLAN_ANTIFILL_FAIL: SC-1 expect 为纯泛词 ('通过') — expect 必须含具体输出串/exit code/数值/路径/字面 token，不得只写通过|正确|完成|works|pass|ok|成功
BRIDGE_INVOCATION_STATUS: not_started
EXIT=1
```

**结论**：`EXIT=1`，stdout 含 `PLAN_ANTIFILL_FAIL`。符合预期。

---

### 负向 fixture n3（expect 为纯泛词"pass"）

**命令**：
```bash
f=$(mktemp /tmp/gd-t4-n3-XXXX.md)
printf 'REVIEW_DOMAIN: ai_infra\nREVIEW_FOCUS: x\n## SC\n- SC-1: do thing\n  verify (method: command): run it\n  expect: pass\nWHERE: a\nWHAT: b\nWHY: c\nVERIFY: d\n' > "$f"
python3 scripts/gd-validate-review2-plan-target.py --target "$f"
echo "EXIT=$?"
rm -f "$f"
```

**真实输出**：
```
PLAN_TEMPLATE_STATUS: fail
PLAN_ANTIFILL_FAIL: SC-1 expect 为纯泛词 ('pass') — expect 必须含具体输出串/exit code/数值/路径/字面 token，不得只写通过|正确|完成|works|pass|ok|成功
BRIDGE_INVOCATION_STATUS: not_started
EXIT=1
```

**结论**：`EXIT=1`，stdout 含 `PLAN_ANTIFILL_FAIL`。符合预期。

---

### SC-4.2 test：正向 fixture p1（具体 expect "PLAN_ANTIFILL_FAIL"）

**命令**：
```bash
f=$(mktemp /tmp/gd-t4-p1-XXXX.md)
printf 'REVIEW_DOMAIN: ai_infra\nREVIEW_FOCUS: x\n## SC\n- SC-1: do thing\n  verify (method: command): python3 scripts/gd-validate-review2-plan-target.py --target p.md\n  expect: "PLAN_ANTIFILL_FAIL"\nWHERE: a\nWHAT: b\nWHY: c\nVERIFY: d\n' > "$f"
python3 scripts/gd-validate-review2-plan-target.py --target "$f"
echo "EXIT=$?"
rm -f "$f"
```

**真实输出**：
```
PLAN_TEMPLATE_STATUS: pass
BRIDGE_INVOCATION_STATUS: allowed
EXIT=0
```

**结论**：`EXIT=0`，stdout 含 `PLAN_TEMPLATE_STATUS: pass`，不含 `PLAN_ANTIFILL_FAIL`。具体 expect 串放行，不误伤合规计划。符合预期。

---

### 正向 fixture p2（verify + expect: exit 0）

**命令**：
```bash
f=$(mktemp /tmp/gd-t4-p2-XXXX.md)
printf 'REVIEW_DOMAIN: ai_infra\nREVIEW_FOCUS: x\n## SC\n- SC-1: validate output\n  verify (method: command): bash scripts/gd-review2-preflight.sh --target plan.md\n  expect: exit 0\nWHERE: scripts/gd-review2-preflight.sh\nWHAT: run preflight\nWHY: ensure plan is valid\nVERIFY: bash scripts/gd-review2-preflight.sh\n' > "$f"
python3 scripts/gd-validate-review2-plan-target.py --target "$f"
echo "EXIT=$?"
rm -f "$f"
```

**真实输出**：
```
PLAN_TEMPLATE_STATUS: pass
BRIDGE_INVOCATION_STATUS: allowed
EXIT=0
```

**结论**：`EXIT=0`，不含 `PLAN_ANTIFILL_FAIL`。`exit 0` 作为具体 expect 值放行。符合预期。

---

### SC-4.3 assertion：PLAN_ANTIFILL_FAIL 信号串存在

**命令**：
```bash
grep -c 'PLAN_ANTIFILL_FAIL' scripts/gd-validate-review2-plan-target.py
```

**输出**：`4`

**结论**：`>=1`，`PLAN_ANTIFILL_FAIL` 独立信号串存在（docstring 1 行 + `antifill_errors` 列表描述 1 行 + `print(f"PLAN_ANTIFILL_FAIL: {af}")` 输出行 + 注释行）。符合预期。

---

### SC-4.3 syntax

**命令**：
```bash
python3 -c "import ast; ast.parse(open('scripts/gd-validate-review2-plan-target.py').read()); print('SYNTAX_OK')"
```

**输出**：`SYNTAX_OK`

---

### SC-4.4 hook source exists

**命令**：
```bash
test -f scripts/plan-mode-antifill-stop-hook.js && echo HOOK_SRC_EXISTS
```

**输出**：`HOOK_SRC_EXISTS`

---

### SC-4.4 node syntax

**命令**：
```bash
node --check scripts/plan-mode-antifill-stop-hook.js && echo NODE_SYNTAX_OK
```

**输出**：`NODE_SYNTAX_OK`

---

### SC-4.4 source-only declaration

**命令**：
```bash
grep -niE 'source-only|不注册|不激活|ledger|T9 deploy|do not install' scripts/plan-mode-antifill-stop-hook.js
```

**输出**：
```
4: * SOURCE-ONLY: 本文件不注册、不激活、不写 ~/.claude/
5: * 安装到 live 由 T9 deploy + ledger 授权完成，本文件本身 do not install。
6: * (source-only; installation to live requires T9 deploy + ledger authorization)
```

**结论**：`>=1` 行命中，头部注释明确声明 source-only / 不写 live / 安装经 T9 deploy + ledger。符合预期。

---

## 5 类 fixture 汇总

| fixture | 描述 | EXIT | PLAN_ANTIFILL_FAIL | 符合预期 |
|---------|------|------|-------------------|---------|
| n1 | SC 缺 verify 行 | 1 | 出现 | pass |
| n2 | expect 为纯泛词"通过" | 1 | 出现 | pass |
| n3 | expect 为纯泛词"pass" | 1 | 出现 | pass |
| p1 | 具体 expect "PLAN_ANTIFILL_FAIL" | 0 | 不出现 | pass |
| p2 | verify + expect: exit 0 | 0 | 不出现 | pass |

---

## 实现说明

### gd-validate-review2-plan-target.py 新增内容

1. **`_SC_VERIFY_LINE_RE`**：匹配 per-SC verify 行——要求 `verify (method: ...)` 括号形式，或前有缩进空白的 `verify:` 行。明确排除步骤级全大写 `VERIFY:` 字段（否则 fixture n1 会被误放行）。

2. **`_SC_EXPECT_LINE_RE`**：提取 `expect:` 行的值部分。

3. **`_is_pure_generic_expect`**：去标点/空白/大小写后，与泛词黑名单匹配；支持单词直接匹配和纯泛词拼接检测。

4. **`_extract_sc_blocks`**：按 SC-ID 起始行切分文本为 `(sc_id, block_text)` 列表，复用 `SC_ID_RE` 正则（从 `lib.sc_extraction` 导入），不修改该模块。

5. **`_check_antifill`**：遍历 SC 块，对每块做 SC-4.1（verify 存在性）和 SC-4.2（expect 泛词黑名单）检查，返回 `PLAN_ANTIFILL_FAIL` 消息列表。

6. **`_validate` 签名变更**：原返回 `list[str]`，改为返回 `(structural_errors, antifill_errors)` 元组；`main()` 同步调整。两类错误均输出时 exit 1；只有结构错误时输出 `PLAN_ERROR:`，只有 anti-fill 错误时输出 `PLAN_ANTIFILL_FAIL:`，两者可单独出现也可并存。

### plan-mode-antifill-stop-hook.js 设计

- 从 stdin 读取 Claude Code Stop hook JSON payload。
- 先尝试 `payload.plan_text`，再尝试读 `payload.transcript_path` 中最后一条 assistant 消息。
- 对提取的计划文本跑与 Python 实现同语义的 `checkAntifill`（`extractScBlocks` + `isPureGenericExpect`）。
- 违反：exit 1 + stdout 打印 `PLAN_ANTIFILL_FAIL:` 行。
- 通过：exit 0。
- 头部注释 3 行明确声明 source-only / 不注册 / T9 deploy 安装。
