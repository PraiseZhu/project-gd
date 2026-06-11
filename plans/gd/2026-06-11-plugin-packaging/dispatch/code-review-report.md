# Code Review: GD 三链路插件封装实现

**Reviewed**: 2026-06-11
**Scope**: 执行代码 diff(commit 6230680 execute vs a1b5d0e plan),22 文件 858 行
**Reviewer**: code-reviewer 子 agent(sonnet)+ 主 agent 核实/修复
**Decision**: APPROVE（修复后；初评 APPROVE-with-comments，3 HIGH 已全修）

## Summary

0 CRITICAL；初评 3 HIGH + 3 MEDIUM + 3 LOW。无明文密钥入 git、无注入、无命令契约破坏、守卫语义整体正确。3 个 HIGH + 2 个安全相关 MEDIUM 已修复并实测;1 个 MEDIUM(M-1)记为接受残留;3 个 LOW 不阻断未改。

## 已修复（主 agent 核实属实后修，逐条实测）

| # | 严重度 | 问题 | 修复 | 验证 |
|---|--------|------|------|------|
| HIGH-3 | HIGH | gd-plugin-setup.sh 仅 set -u；python3 写入失败后仍 echo"完成"(silent failure，违反 fail-visibly) | python3 块包进 `if ! ...; then echo 错误 >&2; exit 1; fi`，写入失败明确报错退出 | 写到 /nonexistent → exit=1 且不打印"完成" ✓ |
| HIGH-1 | HIGH | install-transport.sh trap 在 sed 之后注册，临时 plist 泄漏窗口 | trap 移到 mktemp 后、sed 前立即注册 | bash -n OK；代码序正确 ✓ |
| HIGH-2 | HIGH | gd-validate-execution-batch.py / gd-validate-child-proposal.py 用 str.startswith 判 ~/.claude 守卫,违反项目自身"禁纯 str.startswith"约定(gd-validate-dispatch.py:9) | 两处改 PurePosixPath.relative_to 边界判定(新增 _under_home_claude helper) | ~/.claude/x=True, ~/.claudebar/x=False(误判已修), /tmp=False, rel=False ✓;validator 真实输入仍正常 ✓ |
| M-2 | MEDIUM | setup.sh open(0o644)→json.dump→chmod(0o600),key 有短暂 0644 可读窗口 | 改 os.open(O_CREAT,0o600) 原子创建,消除窗口 | --self-check 仍达标;key 文件 0o600 ✓ |
| M-3 | MEDIUM | install-transport.sh sed `\|` 分隔符无净化,路径含 `\|` 破坏渲染 | sed 前对 HANDOFF_BIN/STATE/ROOT/HOME 做含 `\|` fail-closed 检查 | 含 `\|` → exit 1 ✓ |

## 接受残留（documented，非缺陷）

- **M-1**(MEDIUM):codex key 经 `GD_KEY_VALUE` 环境变量传给 python3 子进程(运行期 ps auxe 可见)。reviewer 评"单用户 macOS 实际攻击面极小"。建议的 stdin 传 key 方案**与 heredoc 冲突**(python3 脚本本身经 `<<'PYEOF'` 占用 stdin),改走 argv 反而更易被 ps 看到。故保留 env 传递 + 0o600 文件权限,记为接受残留。

## 未改 LOW（不阻断）

- LOW-1:smoke `git commit ... \|\| true` 掩盖过宽 — 风格,smoke 内部多重断言已兜底。
- LOW-2:plugin.json 省略 version 无内联注释 — 有意为之,marketplace.json description 已说明。
- LOW-3:setup.sh choose_option `total=$#` 顺序可读性 — 值正确,纯风格。

## 七维总结

| 维度 | 修复后 |
|------|--------|
| correctness | pass（HIGH-3 fail-visibly 已修） |
| type-safety | pass |
| pattern-compliance | pass（HIGH-2 已对齐 PurePosixPath 约定） |
| security | pass（key 0o600 原子写 + 无明文入 git；M-1 接受残留） |
| performance | pass |
| completeness | pass（bundle 8 类 + smoke 3 模式 + no-codex fail-closed 中文提示） |
| maintainability | pass（sed 守卫 + trap 序已正） |

## Validation Results

| Check | Result |
|---|---|
| bash -n（setup / install-transport） | Pass |
| py_compile（2 validator） | Pass |
| validator 真实输入回归 | Pass |
| SC-002/003/007 实跑 | Pass |
| HIGH-3 / M-3 fail-closed 行为 | Pass |
| ruff（待 commit 前跑） | 见 commit |

## 残余风险（移交后续）

1. codex-watch:115 `/Users/praise/Library/...`(SC-007 正则范围外开发者路径)— 未纳入本次 SC-007 定义,供后续评估。
2. M-1 env 传 key(单用户 macOS,接受残留)。
3. P3 作废脚本物理仍在工作树(bundle-completeness --strict-p3 可硬门;最终打包排除)。
