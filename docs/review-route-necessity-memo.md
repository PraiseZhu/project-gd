# Review Route Necessity Memo (v3.1 B0)

> 输出 owned by: B0 phase of `.planning/2026-05-20-review-route-split-v3-1/task_plan.md`
> 决策依据: v3.1 §1 通过条件
> 不替代: `commands/gd.md` 的 `/gd review` 语义权威

## 10-字段对比表

| 字段 | 值 |
|------|---|
| **current_path** | `python3 scripts/gd-codex-bridge-review.py run-bridge` |
| **current_steps** | 6 步：(1) 识别 review 目标 → (2) 决定 kind → (3) 准备 target 文件 → (4) 拼 5 参数 → (5) 跑命令 → (6) 解析 result 路径并读取 |
| **current_required_args** | 5 必填：`--kind {plan\|execution_outcome\|combined\|code_diff}` / `--target <path>` / `--cwd <path>` / `--out <dir>` / `--live-transport`；可选 `--compat-v1` |
| **current_failure_modes** | (a) **capsule context 缺失**：本会话验证过——发 `code_diff` 时 capsule 只是 raw patch，Codex 看不到 git status / manifest / sync-manifest 对照，遗漏 3 个 P1 blocker（hardcoded SECRET_REGEX、manifest-only dir gap、MM state）<br>(b) **profile 隐式**：所有 kind 共用最小 capsule，没有"release_closure 必须含 git state + release-status + final-status snippet"的强制<br>(c) **mandatory_read 无强制覆盖**：Codex 可静默忽略关键文件（如 manifest），返回的 finding 看似合理但实际盲区<br>(d) **degraded ≠ FAILED 语义混淆**：`code_diff + live-transport` 返回 `GD_CODEX_BRIDGE_STATUS: degraded / GD_REVIEW_DECISION: FAILED`，含糊 |
| **new_route** | `/review2`（profile-aware Codex workbench）；`/review1` 暂不必要（仅 L1 quick wrap，无强 capsule 价值） |
| **new_steps** | 1-2 步：`/review2 <target>` 或 `/review2 <target> --profile release_closure` |
| **removed_args** | 4 项：`--cwd`（默认当前 git root）、`--out`（默认 `results/review-route-split/<run-id>/`）、`--live-transport`（默认 true）、`--kind`（由 profile 推导） |
| **prevented_failure_modes** | (a) **capsule completeness validator**（B1：`gd-validate-review2-capsule.py`）：`release_closure` profile 缺 git status / release-status / final-status / manifest 时 fail-closed 不发<br>(b) **mandatory_read coverage validator**（B1：`gd-validate-review2-output.py`）：每个 mandatory_read 必须在 Codex output 显式标 read/summarized_by_preflight/out_of_scope；release_closure 下 missing 直接 fail<br>(c) **profile 强制显式**：`release_closure`/`runtime_parity` 必须显式声明，默认 `code_diff` 时输出明确 `RELEASE_VERDICT: NOT_APPLICABLE`<br>(d) **degraded/FAILED 二分**：output_contract 强制 `CODEX_RUN_STATE` 与 `RELEASE_VERDICT` 分别声明 |
| **authority_boundary** | `/gd review` 仍是唯一 L3 formal review authority；`/review2` 输出**必须**含 `L3_GD_REVIEW_SEMANTICS: unchanged` + `RELEASE_VERDICT: NOT_APPLICABLE`（除 profile=release_closure 且走完整 evidence contract） |
| **decision** | **`create_slash_command`** |

## v3.1 通过条件检查

| 条件 | 满足 | 证据 |
|------|------|------|
| ≥1 `current_failure_mode` 被新入口 fail-closed | ✓ | capsule completeness (a)、mandatory_read coverage (b)、profile 强制 (c) 三项都属于新入口能 fail-closed 而 bridge 当前不能 |
| 必填参数数 >=5 降 <=2 | ✓ | 5 → 1-2 |
| 新入口能强制 profile/capsule contract | ✓ | profile + capsule + mandatory_read 三件套是 /review2 的核心设计，bridge 当前完全没有 |

3/3 满足 → decision = `create_slash_command`

## LIBRARY_CONSUMER_LIST

```text
LIBRARY_CONSUMER_LIST:
- consumer: review2_slash_command
  decision: create
  required_capabilities:
    - build_capsule          # gd-build-review2-capsule.py
    - validate_capsule       # gd-validate-review2-capsule.py (pre-send)
    - validate_output        # gd-validate-review2-output.py (post-receive)
- consumer: gd_codex_bridge_review
  decision: extend
  implementation_status: pending  # NOT YET IMPLEMENTED — bridge currently does not accept prebuilt capsule JSON
  required_capabilities:
    - accept_capsule         # bridge 接受 prebuilt capsule JSON 作为 alternative input（保持向后兼容现有 --target 调用）
  note: /review2 current path calls bridge with --target capsule.md directly; formal capsule-input API is backlog
- consumer: review1_slash_command
  decision: skip
  reason: /review1 仅 L1 quick wrap，无强 capsule 价值；用户可继续直调 bridge
```

## 不证明必要的部分

- `/review1` decision = **skip**：未发现 ≥1 failure mode 被 fail-closed；步骤数和参数差异小；不创建 slash command
- 三个新 Python 脚本仍待 B1 实施；本 memo 仅决定**可以**做，未授权**已**做

## Pending Authorization

- B1/B3 实施代码（创建 3 个 Python 脚本 + `commands/review2.md`）需用户显式授权
- live install（写 `/Users/praise/.claude/commands/review2.md`）需复用 `baselines/gd-v7-runtime-write-authorizations.jsonl` ledger
- 本 memo 不写 runtime；只产出决策
