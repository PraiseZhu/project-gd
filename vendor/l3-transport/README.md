# vendor/l3-transport — L3 codex 通信传输层(收编暂存区)

> 收编日期：2026-06-04
> 来源：从 `~/.claude/` 拷入的 L3 review→codex 通信链路 ②-⑤ 环节
> 性质：**收编暂存,尚未解耦**。脚本内路径仍指向 `~/.claude`/`$HOME`，封装时需改造。
> 区别于：`archive/`(死代码) / `mirrors/`(只读快照)。这里是**要实际运行**的传输层。
> ⑥⑦(codex CLI / provider / key)的封装边界决策见 [`../../docs/2026-06-04-plugin-packaging-decisions.md`](../../docs/2026-06-04-plugin-packaging-decisions.md)(不打包,声明依赖+引导)。

## 为什么收编这些

GD 的 codex 通信链共 7 跳，其中 ②-⑤ 原本在 `~/.claude/` 系统目录、不在 GD 工程内：

```
① gd-codex-bridge-review.py   ← GD scripts/(已在 GD)
② review-result-writer.sh     ← 本目录 scripts/        (原 ~/.claude/scripts/)
③ codex-send-wait             ← 本目录 handoff/bin/    (原 ~/.claude/handoff/bin/)
④ codex-send                  ← 本目录 handoff/bin/
⑤ codex-watch daemon          ← 本目录 handoff/bin/ + launchagents/
⑥ codex exec                  ← L1 二进制(codex 自身,不收编)
⑦ tapsvc gpt-5.5 + key        ← L2 配置(~/.codex,不收编)
```

daemon 是 L3 多 agent 并发架构的承重墙：worker pool(max_parallel=2)+ 队列 +
单实例锁，接住 `/gd` 四阶段并发子 agent 发来的多个 codex review 请求。直接
`codex exec` 无此并发控制，撑不住多 agent 场景，故必须收编而非替换。

## 收编内容清单

| 环节 | 文件 | 原始路径 |
|------|------|---------|
| ② writer | `scripts/review-result-writer.sh` | `~/.claude/scripts/` |
| ③ | `handoff/bin/codex-send-wait` | `~/.claude/handoff/bin/` |
| ④ | `handoff/bin/codex-send` | 同上 |
| ⑤ daemon | `handoff/bin/codex-watch` | 同上 |
| ⑤ 辅助 | `handoff/bin/{codex-status,codex-watch-healthcheck,watcher-alive}` | 同上 |
| 依赖库 | `handoff/lib/{state-paths.sh,watch-state.sh}` | `~/.claude/handoff/lib/` |
| daemon 常驻 | `launchagents/com.praise.codex-watch{,-healthcheck}.plist` | `~/Library/LaunchAgents/` |
| skill 入口壳 | `skills/goal-gd/SKILL.md`、`skills/gd-review/SKILL.md` | `~/.claude/skills/` |

> skill 壳是 `/gd` 的 skill 注册入口(薄壳,各单个 SKILL.md),非链路运行代码;
> 封装时进插件 `skills/`。gd.md/review2.md 不引用它们。

## 未拷入(运行时产生,非代码)

- `~/.claude/handoff/{active,archive,state}/` — 队列/运行态目录，由 daemon 运行时创建
- `~/.claude/review-baselines/` — writer 产出的 baseline/result（运行态）
- `~/.claude/state/review-writer-required/` — writer marker（运行态）
  这些由 `HANDOFF_ROOT` 等环境变量定位，运行时自动创建。

## 安全

- 2 个 plist 的 `TAPTAP_API_KEY` 已 **redact** 为 `<REDACTED-...>`占位。
  真实 key 通过 `launchctl setenv` 或安装脚本注入，**禁止明文入 git**。

## 待解耦清单(封装时改造,本次未做)

1. **路径解耦**：
   - `review-result-writer.sh`：`$HOME/.claude/handoff/bin/codex-send-wait`(:88)、
     `$HOME/.claude/review-baselines/`(:51)、`$HOME/.claude/state/`(:60) → 改为插件相对/可配置
   - `bridge` `WRITER_PATH` 已改指 vendor 副本(2026-06-16）；`SEND_WAIT_PATH`（原 dead code）已移除
2. **HANDOFF_ROOT 隔离**：handoff 脚本支持 `HANDOFF_ROOT` 环境变量覆盖
   (`state-paths.sh:8` `:=` 默认值)，封装时设为插件内目录，避免与系统 `~/.claude/handoff` 冲突
3. **daemon 常驻机制**：plist `ProgramArguments` 指向本目录副本 + 提供 launchctl
   安装脚本(插件 install 阶段注册)
