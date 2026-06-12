# Runbook: AKB2 Plan 1 多 target 全量 Codex 审查

**用途**：将 master-plan + 6 个 step plan 全部送入 Codex cross-review（suite-mode）。

## 前置条件

- codex-watch daemon 在线：`launchctl list | grep com.praise.codex-watch`
- 在 Project GD 根目录执行（`cd /Users/praise/AI-Agent/Claude/projects/Project GD`）

## 命令

```bash
python3 scripts/gd-review-suite-controller.py \
  --target-set-id akb2-plan1-full-$(date +%Y%m%dT%H%M%S) \
  --kind plan \
  --cwd /Users/praise/AI-Agent/Claude/projects/Project\ AKB2 \
  --max-parallel 2 \
  --compat-v1 \
  --target role=master_plan,path=/Users/praise/AI-Agent/Claude/projects/Project\ AKB2/plans/gd/2026-06-12-content-quality-loop/master-plan.md \
  --target role=step_1,path=/Users/praise/AI-Agent/Claude/projects/Project\ AKB2/plans/gd/2026-06-12-content-quality-loop/step-1-loop7-skeleton.md \
  --target role=step_2,path=/Users/praise/AI-Agent/Claude/projects/Project\ AKB2/plans/gd/2026-06-12-content-quality-loop/step-2-intake-raw.md \
  --target role=step_3,path=/Users/praise/AI-Agent/Claude/projects/Project\ AKB2/plans/gd/2026-06-12-content-quality-loop/step-3-admission-distill.md \
  --target role=step_4,path=/Users/praise/AI-Agent/Claude/projects/Project\ AKB2/plans/gd/2026-06-12-content-quality-loop/step-4-quality-repair.md \
  --target role=step_5,path=/Users/praise/AI-Agent/Claude/projects/Project\ AKB2/plans/gd/2026-06-12-content-quality-loop/step-5-promote.md \
  --target role=step_6,path=/Users/praise/AI-Agent/Claude/projects/Project\ AKB2/plans/gd/2026-06-12-content-quality-loop/step-6-runner-calibration.md
```

## 说明

| 参数 | 说明 |
|------|------|
| `--max-parallel 2` | 同时最多 2 个 Codex 任务（GD 合同硬上限） |
| `--compat-v1` | AKB2 Plan 1 计划文件使用 v1 review 格式 |
| `role=master_plan` | 主计划，bridge 使用 master_plan target_role |
| `role=step_N` | 各 step 文件，bridge 映射为 subplan target_role |
| `--target-set-id` | 稳定 ID 用于 run 追踪；建议含时间戳 |

## 产物位置

- 审查结果写入 `~/.claude/review-baselines/` 下以 `gd-plan-*` 为前缀的目录
- 日志：codex-watch daemon stdout（`~/Library/Logs/codex-watch.log`）

## dry-run 验证（不实跑 Codex）

```bash
python3 scripts/gd-review-suite-controller.py \
  --selftest-bridge-argv
```

退出码 0 = controller → bridge 参数映射正确，可用于 7 target 场景。
