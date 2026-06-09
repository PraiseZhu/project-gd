```yaml
GD_REVIEW_DECISION: APPROVED
reviewer: claude_round2_verify
findings:
  - id: F1_FIXED
    status: fixed
    evidence: |
      代码读取验证（scripts/gd-codex-bridge-review.py 第 942-986 行）：
      - _dedup_key 已删除，替换为 _file_cat（返回 file+category 元组）和 _within_window（abs(a-b)<=3）
      - 去重逻辑改为 O(n²) 线性扫描 merged_list，match 用 _file_cat(existing)==fc and _within_window(...)
      - 最终排序用 sorted(merged_list, ...)，不用 merged.values()

      运行时验证输出：
        fa = [{"file":"a.py","line":1,"category":"sc","severity":"P2"}]
        fb = [{"file":"a.py","line":3,"category":"sc","severity":"P1"}]
        result = merge_findings_union([fa, fb])
        => F1_FIXED  (len=1, severity=P1)

      line 1 与 line 3 diff=2 ≤ 3，正确合并为单条，取高严重度 P1。

  - id: F2_FIXED
    status: fixed
    evidence: |
      代码读取验证（commands/review2.md 第 41-66 行）：

      /review2 plan 执行流程：
        Step1  gd-validate-review2-plan-target.py   ← 第一步是 anti-fill 硬门（T4 owned）
        Step3  gd-build-review2-capsule.py --kind plan
        Step4  gd-validate-review2-capsule.py
        Step5  gd-codex-bridge-review.py run-bridge ...
        Step6  gd-validate-review2-output.py
      → 无任何 gd-review2-preflight.sh 调用，原错误 Step1 已删除。

      fail-closed 规则（第 59-65 行）：
        - anti-fill 门不过 → PLAN_ANTIFILL_FAIL
        - capsule 验证失败 → CAPSULE_VALIDATE_FAIL
        - BRIDGE_TARGET_POLICY 缺失/错误 → 对应 fail
        - 桥接路径错误 → PLAN_TARGET_MUST_BE_ORIGINAL_PLAN
        - 计划目标字段校验失败 → PLAN_TEMPLATE_STATUS: fail
      → 无「无 preflight 证据文件」行，F2 中的错误规则行已删除。

      /review2 code Step0.5（第 98-113 行）：
        > GATE_BOUNDARY: 本门 **只挂 /review2 code 路**，不挂 /review2 plan 路。
        bash scripts/gd-review2-preflight.sh [--evidence <path>] 仍保留在 code 路。
      → code 路 preflight 完整保留，只删 plan 路误调，符合修复方案。
```
