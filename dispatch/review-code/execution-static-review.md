---
review_kind: execution-static-field-validation
reviewer: claude_execution_review
reviewed_at: 2026-06-09T16:17:00+08:00
tasks_reviewed: [t1, t2, t3, t4, t5, t6, t7, t8, t9]
---

```yaml
GD_REVIEW_DECISION: REQUIRES_CHANGES
reviewer: claude_execution_review
findings:
  # ── T2 ──────────────────────────────────────────────────────────────────
  - task_id: t2
    field: exec_status
    severity: P2
    issue: >
      结果文件未使用 gd-execution-result YAML 模板格式。顶层 YAML frontmatter 使用
      `status: completed` 而非规定的 `exec_status:` 字段名，且模板前缀字段（template_kind /
      result_id / parent_step / parent_plan / executor_role / executed_at）全部缺失。
      合法枚举值（completed / completed_with_constraint / blocked / failed）无法从
      `exec_status` 字段读取，因为该字段根本不存在。

  - task_id: t2
    field: sc_acceptance
    severity: P2
    issue: >
      结果文件没有机器可读的 `sc_acceptance` YAML 块。SC 验收以 Markdown 散文（### SC-2a
      等小节 + 代码块 + "状态: `pass`"文字）呈现，缺少规定的
      `sc_acceptance[].sc_ref / status / evidence / not_run_reason` 结构化字段，
      无法通过字段扫描工具做合规性校验。

  - task_id: t2
    field: forbidden_paths_touched / out_of_scope_writes / files_added / files_modified / owned_paths_writes_only
    severity: P2
    issue: >
      结果文件完全缺失以下 YAML 字段：`forbidden_paths_touched`、`out_of_scope_writes`、
      `files_added`、`files_modified`、`owned_paths_writes_only`。
      范围合规信息仅以 Markdown 散文段落形式存在（"范围合规声明"小节），
      无法被静态字段校验工具自动读取。

  - task_id: t2
    field: handoff
    severity: P2
    issue: >
      结果文件末尾无结构化 `handoff:` YAML 块（仅有 `## blockers: none` 散文行）。
      `handoff.result_path`、`handoff.summary` 字段均不存在，违反 handoff 完整性要求。
      注：文件自引用路径可从 frontmatter YAML 中 `status: completed` 行上方推断，
      但不是 `handoff.result_path` 字段。

  # ── T4 ──────────────────────────────────────────────────────────────────
  - task_id: t4
    field: exec_status
    severity: P2
    issue: >
      顶层 YAML frontmatter 的 `status_field: completed` 是一个元字段（表示"用 status
      字段名"），而非 `exec_status` 字段本身。规定枚举值（completed / completed_with_constraint
      / blocked / failed）的 `exec_status` 字段缺失。`handoff_output.status_field: completed`
      同样是错误用法——`status_field` 应为字段名引用（值应为 `exec_status`），而非状态值本身。

  - task_id: t4
    field: sc_acceptance
    severity: P2
    issue: >
      结果文件没有顶层 `sc_acceptance` YAML 块。SC 验收以 Markdown 散文小节（### SC-4.1
      assertion、### SC-4.2 test 等）呈现，缺少规定的结构化数组字段。

  - task_id: t4
    field: forbidden_paths_touched / out_of_scope_writes / files_added / files_modified / owned_paths_writes_only
    severity: P2
    issue: >
      结果文件完全缺失 `forbidden_paths_touched`、`out_of_scope_writes`、`files_added`、
      `files_modified`、`owned_paths_writes_only` 五个 YAML 字段。交付物以 Markdown 表格
      （"## 交付物"段）呈现，无法被静态字段扫描读取。

  - task_id: t4
    field: handoff
    severity: P2
    issue: >
      `handoff_output` 块（非规定的 `handoff:` 字段名）中 `status_field: completed` 是错误用法
      ——该字段含义模糊（"字段名"还是"状态值"？），规定格式要求字段名为 `handoff.result_path`
      和 `handoff.summary`，且字段名层级应为 `handoff`（非 `handoff_output`）。
      `result_path` 存在且文件实际存在，但字段命名不合规。

  # ── T6 ──────────────────────────────────────────────────────────────────
  - task_id: t6
    field: exec_status
    severity: P2
    issue: >
      顶层 YAML frontmatter 使用 `status: completed` 而非 `exec_status: completed`。
      规定枚举字段 `exec_status` 缺失。`handoff_output.status_field: completed` 存在同 T4
      一样的命名混淆问题（`status_field` 应为字段名引用，值应为 `exec_status`）。

  - task_id: t6
    field: sc_acceptance
    severity: P2
    issue: >
      结果文件没有顶层 `sc_acceptance` YAML 块。SC 验收以 Markdown 表格（"## 执行完成 / ### 成功标准验收"
      表格段）呈现，缺少规定的结构化数组（sc_ref / status / evidence / not_run_reason）。

  - task_id: t6
    field: forbidden_paths_touched / out_of_scope_writes / files_added / files_modified / owned_paths_writes_only
    severity: P2
    issue: >
      结果文件缺失 `forbidden_paths_touched`、`out_of_scope_writes`、`files_added`、
      `files_modified`、`owned_paths_writes_only` 五个 YAML 字段。
      交付物描述在散文段落中，无法被静态字段扫描读取。

  - task_id: t6
    field: handoff
    severity: P2
    issue: >
      `handoff_output` 块（非规定的 `handoff:` 字段名）字段命名不合规，同 T4 问题。
      `result_path` 字段值指向的文件实际存在，`summary` 非空，但顶层字段名应为 `handoff`。

  # ── T7 ──────────────────────────────────────────────────────────────────
  - task_id: t7
    field: exec_status
    severity: P2
    issue: >
      顶层 YAML frontmatter 使用 `status: completed` 而非 `exec_status: completed`。
      模板前缀字段（template_kind / result_id / parent_step / parent_plan /
      executor_role / executed_at 等）全部缺失。`exec_status` 枚举字段不存在。

  - task_id: t7
    field: sc_acceptance
    severity: P2
    issue: >
      结果文件没有顶层 `sc_acceptance` YAML 块。SC 验收以 Markdown 表格
      （"## SC Checklist"段，含 SC-7.1 ~ SC-7.9 和 PASS 文字）呈现，
      缺少规定的结构化数组字段。

  - task_id: t7
    field: forbidden_paths_touched / out_of_scope_writes / files_added / files_modified / owned_paths_writes_only / handoff
    severity: P2
    issue: >
      结果文件缺失所有路径权限字段（`forbidden_paths_touched`、`out_of_scope_writes`、
      `files_added`、`files_modified`、`owned_paths_writes_only`）及顶层 `handoff:` 块。
      交付物列于 Markdown 表格，路径合规信息不可机读。

  # ── T8 ──────────────────────────────────────────────────────────────────
  - task_id: t8
    field: exec_status
    severity: P2
    issue: >
      顶层 YAML frontmatter 使用 `status: completed` 而非 `exec_status: completed`。
      模板前缀字段全部缺失，`exec_status` 枚举字段不存在。

  - task_id: t8
    field: sc_acceptance
    severity: P2
    issue: >
      结果文件没有顶层 `sc_acceptance` YAML 块。SC 验收以 Markdown 小节
      （### SC-8.1 ~ SC-8.6 散文 + 代码块 + "状态：pass"文字）呈现，
      缺少规定的结构化数组字段。

  - task_id: t8
    field: forbidden_paths_touched / out_of_scope_writes / files_added / files_modified / owned_paths_writes_only
    severity: P2
    issue: >
      结果文件缺失 `forbidden_paths_touched`、`out_of_scope_writes`、`files_added`、
      `files_modified`、`owned_paths_writes_only` 五个 YAML 字段。
      交付物信息在 Markdown 表格（"## 2. 交付物清单"）中，不可机读。

  - task_id: t8
    field: handoff
    severity: P2
    issue: >
      `handoff_output` 块（非规定的 `handoff:` 字段名）字段命名不合规，同 T4/T6 问题。
      `result_path` 指向文件实际存在，`summary` 非空，但顶层字段名不符合规范。

  # ── T9 ──────────────────────────────────────────────────────────────────
  - task_id: t9
    field: exec_status
    severity: P2
    issue: >
      顶层 YAML frontmatter 使用 `status: completed` 而非 `exec_status: completed`。
      模板前缀字段全部缺失，`exec_status` 枚举字段不存在。

  - task_id: t9
    field: sc_acceptance
    severity: P2
    issue: >
      结果文件没有顶层 `sc_acceptance` YAML 块。SC 验收以 Markdown 表格
      （"## 成功标准验收"表格段，含 SC-9.1 ~ SC-9.6 和 pass 文字）呈现，
      缺少规定的结构化数组字段。

  - task_id: t9
    field: forbidden_paths_touched / out_of_scope_writes / files_added / files_modified / owned_paths_writes_only
    severity: P2
    issue: >
      结果文件缺失所有路径权限字段。交付内容（`.deploy-manifest.jsonl` 修改）
      在散文段落和 Markdown 表格中描述，不可机读。

  - task_id: t9
    field: handoff
    severity: P2
    issue: >
      `handoff_output` 块（非规定的 `handoff:` 字段名）字段命名不合规，同 T4/T6/T8 问题。
      `result_path` 指向文件实际存在，`summary` 非空，但顶层字段名不符合规范。

  # ── 跨任务模式（NF，不阻塞 APPROVED，仅供记录）──────────────────────────
  - task_id: t2
    field: template_kind
    severity: NF
    issue: >
      T2 结果文件未声明 `template_kind: gd-execution-result`，是七个非标准格式任务
      （T2/T4/T6/T7/T8/T9）中格式偏差最大的一个（无任何 YAML frontmatter 块结构）。
      T1/T3/T5 使用了规定的 gd-execution-result 模板，其余任务均未使用。

compliance_summary:
  fully_compliant: [t1, t3, t5]
  partially_compliant: []
  non_compliant: [t2, t4, t6, t7, t8, t9]
  notes: >
    T1、T3、T5 完全符合 gd-execution-result 模板格式（含 template_kind / exec_status 枚举 /
    sc_acceptance YAML 块 / files_added|modified / forbidden_paths_touched / out_of_scope_writes /
    owned_paths_writes_only / handoff.result_path + summary）。

    T2、T4、T6、T7、T8、T9 采用了 Markdown 散文格式，SC 验收和路径合规信息仅以人类可读方式
    呈现，缺少机器可读的规定字段。所有 6 个非合规任务的 handoff.result_path 指向的文件
    实际存在，sc 验收证据实质内容完整，无 REV_VERDICT 字段污染，无 forbidden_paths 写入
    声明，无 out_of_scope_writes 声明——内容层面无 P1 阻断项，结构层面存在普遍 P2 偏差。

    deliverables 一致性（规则4）：T6 的 reports/t6-router-target-trace.md 路径在 packet
    owned_paths 中已通过 `reports/` 目录显式授权（packet line 107："reports/ 为本 packet
    显式产出目录"），不构成越界。其余 T1/T3/T5 的 files_added + files_modified 均在
    对应 owned_paths 范围内。T2/T4/T6/T7/T8/T9 因缺少 files_added/modified YAML 字段，
    无法做自动 owned_paths 交叉验证，但散文中描述的交付物路径均与 packet owned_paths 一致。
```
