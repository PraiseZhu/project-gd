```yaml
GD_REVIEW_DECISION: REQUIRES_CHANGES
reviewer: claude_child_1
scope: T1-T5
review_run_status: completed

# ─── SCOPE CHECKED ────────────────────────────────────────────────────────────
scope_checked:
  - file: prompts/gd-review-standard.md
    area: §9 穷举强制段（T1）
    result: pass
    evidence: §9.1-§9.3 完整；穷举义务 / 协议违规判定 / SCOPE_CHECKED 完整性三节全部存在

  - file: scripts/gd-codex-bridge-review.py
    area: REVIEW_LENS_EMPHASIS + dual codex emphasis（T1）
    result: pass
    evidence: line 1144-1162; codex_A/codex_B emphasis 字符串定义正确，lens_emphasis_line 注入 capsule

  - file: scripts/gd-codex-bridge-review.py
    area: merge_findings_union 三方并集去重（T1）
    result: fail
    evidence: line 905-986；bucket 数学边界有漏洞，见 F1

  - file: scripts/gd-review2-preflight.sh
    area: dry-run gate exit codes + --evidence 参数（T2）
    result: pass
    evidence: header lines 16-19 定义 exit 0/1/3；--evidence 参数 line 43-51 实现；
              python heredoc 校验 paths_exercised + fallback_no_api_key

  - file: templates/plan-mode-template.md
    area: SC-N + verify (method:...) + expect 结构（T3）
    result: pass
    evidence: SC-1 到 SC-4 均含 verify (method:...) 和 expect 字段；样例段完整

  - file: scripts/gd-validate-review2-plan-target.py
    area: PLAN_ANTIFILL_FAIL 硬门逻辑（T4）
    result: pass
    evidence: _check_antifill() SC-4.1 verify 缺失检测 + SC-4.2 expect 泛词黑名单检测均实现；
              _is_pure_generic_expect() 字符串去重逻辑正确；exit code 0/1/2 符合规范

  - file: scripts/plan-mode-antifill-stop-hook.js
    area: source-only 声明（T4）
    result: pass
    evidence: line 4 "SOURCE-ONLY: 本文件不注册、不激活、不写 ~/.claude/"；
              无 fs.writeFile 或 ~/.claude 写操作

  - file: commands/review2.md
    area: plan 子命令流程 Step0-Step5（T5）
    result: fail
    evidence: plan 流程 Step1 错误调用 gd-review2-preflight.sh，见 F2

  - file: scripts/gd-detect-review2-code-target.py
    area: 三档判定逻辑 + INDETERMINATE exit 2（T5）
    result: pass
    evidence: has_code/has_result 探测逻辑完整；INDETERMINATE → exit 2；
              覆盖 flag --code/--result/--combined 互斥由 argparse mutually_exclusive_group 保证

# ─── FINDINGS ─────────────────────────────────────────────────────────────────
findings:
  - id: F1
    severity: P2
    file: scripts/gd-codex-bridge-review.py
    line: "942-958 (_dedup_key)"
    category: logic_error
    description: |
      merge_findings_union() 的 bucket 数学存在边界漏洞，导致部分 ±3 行内的 finding 未被去重。

      代码注释声称 floor((line+3)/6) 能保证 ±3 行共享 bucket，但实际映射：
        line 1 → bucket 0，line 2 → bucket 0，line 3 → bucket 1
        line 8 → bucket 1，line 9 → bucket 2

      可复现：lines 1 & 3 (diff=2)、lines 1 & 4 (diff=3)、lines 8 & 11 (diff=3) 等
      均落入不同 bucket，不被去重。共有 47 对 1-50 行内差距 ≤3 的 line pair 未被正确去重。

      docstring 中的示例（lines 10 & 11）恰好在同一 bucket（2），通过了，但边界情况大量漏判。

      影响：Round 1 双 codex 对同一段代码（行差 ≤3）报告的相同类别 finding，
      可能重复出现在 baseline_findings.json，用户看到两条等价 finding 需要处理。
      不影响安全性，但违反"三方并集去重"的设计契约。

    suggested_fix: |
      改用双 bucket 覆盖：每条 finding 同时注册 floor(line/6) 和 floor((line+1)/6) 两个 key，
      确保任意两行 |L1-L2|<=3 都能在至少一个 key 上命中。
      或改为精确比较：collected list 内 O(n²) 扫描，|l1-l2|<=3 且 category 相同 → 合并。
      示例修复：
        def _dedup_key(finding):
            ...
            # 返回两个 key（行号下取整和上取整），均加入 merged dict
            return [(file_norm, line // 6, cat), (file_norm, (line + 3) // 6, cat)]

  - id: F2
    severity: P2
    file: commands/review2.md
    line: "45 (plan flow Step1)"
    category: sc_violation
    description: |
      /review2 plan 执行流程的 Step1 调用 gd-review2-preflight.sh（dry-run 证据门），
      但该脚本头部明确写明：
        "Gate only applies to the /review2 CODE path — NOT the plan path."
        "It must NOT be called from /review2 plan (plan phase has no code to run)."

      spec §2.1 plan 流程的 Step1 也只写 "anti-fill 硬门"（T4 对应的 gd-validate-review2-plan-target.py），
      未提及 preflight。T5 spec 也未授权 plan 路调用 preflight。

      影响：运行 /review2 plan 时，若用户没有 dry-run 证据文件（通常不会有，
      因为计划阶段根本没有代码可跑），Step1 会输出 DRYRUN_EVIDENCE_MISSING exit 3，
      导致正常计划审查请求被错误拦截，整个 plan 路无法使用。
      这是一个 active path 失败（fail-closed 策略在此处产生 false positive 阻断）。

    suggested_fix: |
      从 plan 执行流程中删除 Step1 的 gd-review2-preflight.sh 调用，
      调整步骤编号使 gd-validate-review2-plan-target.py 成为 Step1。
      修改后 plan 流程：
        Step1  gd-validate-review2-plan-target.py  # anti-fill 硬门（T4 owned）
        Step2  gd-build-review2-capsule.py --kind plan
        Step3  gd-validate-review2-capsule.py
        Step4  gd-codex-bridge-review.py run-bridge ...
        Step5  gd-validate-review2-output.py
      同时从 Fail-closed 规则中删除 "无 preflight 证据文件 → DRYRUN_EVIDENCE_MISSING" 一行
      （该行只属于 code 路的失败处理）。

  - id: F3
    severity: NF
    file: scripts/plan-mode-antifill-stop-hook.js
    line: "197-290 (main)"
    category: minor
    description: |
      main() 不检查 payload.hook_event_name === "Stop"，会对任何提供 JSON stdin 的 hook 事件
      （包括 PostToolUse）都运行 anti-fill 逻辑。

      由于文件为 source-only，实际注册行为由 T9 控制，此处仅为建议性观察：
      如果 T9 将此 hook 注册为 Stop 以外的事件类型，它会在非 plan mode 场景下误触发。

      建议 T9 部署时只将其注册为 Stop 事件，或在 main() 入口添加：
        if (payload.hook_event_name !== "Stop") process.exit(0);
      以使 source 与预期合约自文档化。
```
