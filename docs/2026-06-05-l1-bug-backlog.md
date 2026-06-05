# L1 链路完整 Bug 优先级清单（合并版 backlog）

> 日期：2026-06-05 · 窗口：2026-05-06 ~ 06-05（30 天）· 样本：574 次 /review（=L1），412 repo
> 来源：review-baselines（纯 L1 结果）+ handoff（传输健康）+ codex-watch daemon log，三源互证
> 本清单合并：初版 7 行问题清单 + 超时 RCA + 非超时 P1/P2 深挖，**初版问题一个不漏，已全部归账到根因**

---

## 根因总览（关键洞察）

近乎所有失败收敛到 **2 大根因 + 3 个配置缺陷**：

1. **tapsvc 单 provider 间歇故障（GAP-1，最深根因）**：超时(33) + auth-401(7) + rate-429(6) 全源于此，且坏日子同时爆发。
2. **daemon TAPTAP_API_KEY 缺失（BUG-4，本会话已修）**：8 个 exit=1（06-03/04）。
3. 配置缺陷 BUG-1（超时窗口错配）/ BUG-2（.exit 不一致）/ BUG-3（重试无 backoff）。

**铁证**：05-16 一天 18 次失败（9 超时 + 9 exit=1 的 auth/rate）——provider bad day 时 latency 和 auth/throttle 一起崩。

**健康基线**：完成率 84.7%，15.3%（88）无结果。

---

## 完整 Bug 清单

| ID | 优先级 | Bug | 证据（30天） | 深层根因 | 状态 | 修复 | 置信 |
|----|:--:|------|------|------|:--:|------|:--:|
| **BUG-1** | **P1** | send-wait/daemon 超时窗口错配 → 重试成功成孤儿 | exec 240×2=480s vs send-wait 300s；18/33 超时 job attempt2 成功但 .exit=124 | 客户端 300s 放弃，daemon 480s 才出结果，没人接 | 待修 | send-wait 300→**540s** | 高 |
| **GAP-1** | **P1** | tapsvc 单 provider，无降级 | 超时扎堆 05-16(9)/05-27(7)=48%；exit=1 含 auth-401×7 + rate-429×6；05-16 一天 18 失败 | 第三方代理间歇拥塞+认证+限流,单点 | 待修（大） | 接 D2：provider 可配置 + 降级/备用 + 限流退避 | 高 |
| **BUG-4** | **P1** | daemon 缺 TAPTAP_API_KEY → codex exec 直接报错 | exit=1 中 **8 个**(06-03/04)stderr=`Missing env TAPTAP_API_KEY` | daemon plist EnvironmentVariables 未含 key | **本会话已修**（plist+launchctl setenv+kickstart） | 验证无复发 | 高 |
| **BUG-2** | **P2** | `.exit` 记非最终 attempt | 18 个 attempt2 exit=0 但 .exit=124 | 退出码写首次而非最终 attempt | 待修 | .exit 写最终 attempt | 高 |
| **GAP-2** | **P2** | `/review1` 运行层未解耦 | vendor writer 内引 ~/.claude；writer 路径含 `<GD_ROOT>` 占位 | 收编只到入口,运行层未改造 | 待修（封装阶段） | vendor writer 内部→vendor 副本 + HANDOFF_ROOT 隔离 + 解析 `<GD_ROOT>` | 高 |
| **BUG-3** | **P3** | 重试无 backoff/熔断 | sustained 期 15 个 job 两次 attempt 都失败 | 立即重试,坏日子照失败 | 待修 | 重试加 backoff 或 tapsvc 熔断 | 中 |
| **ISSUE-1** | P3·待定 | 108 baseline 卡 pending | review_status=pending ×108 | 部分正常(plan-only)部分疑丢结果 | 待验证 | 查 reviewed_at 是否 null（null=真丢） | — |
| **ISSUE-2** | P3·待定 | 3 result malformed | 3 个 baseline malformed | 结果文件缺失/路径失效,本轮判定不出缺哪字段 | 待验证 | 手查这 3 个 result 实际内容 | 低 |
| **ISSUE-3** | 非bug | REQUIRES_CHANGES 57% | RC 279 : APPROVED 207 | 指标非缺陷 | 监控 | 抽样看 RC 是否多非阻塞 | — |

---

## 初版问题归账（证明无遗漏）

| 初版 7 行问题 | 优先级 | 归到哪 |
|------|:--:|------|
| 15% 无结果(88) | P1 | 症状 = BUG-1(孤儿) + GAP-1(超时/auth/rate) + BUG-4(key,已修) |
| 超时头号(exit=124 ×33) | P1 | BUG-1 + GAP-1（已 RCA：capsule 体积排除） |
| codex exec 硬失败(exit=1 ×21) | P1 | 拆解：BUG-4 key×8（已修）+ GAP-1 auth401×7 + rate429×6 |
| ~9% 重试(54) | P2 | = 超时重试33 + exit1重试21；是上述失败的响应,非独立 bug；受 BUG-1/BUG-3 管辖 |
| 41 repo 不可用(failed 38 + malformed 3) | P2 | failed 38 = 上述传输失败的下游影响；malformed 3 = ISSUE-2 |
| 108 pending | P3 | ISSUE-1 |
| 57% RC | P3 | ISSUE-3 |
| WATCH_REVIEW_FAILED ×35 | （证据项） | = 20 exec exit=1 + 15 exec timeout 的包装标记,非独立失败,已去重 |

---

## 修复排序建议

1. **BUG-1**（改 1 个超时值，砍 ~55% 可见超时，最高杠杆）
2. **BUG-4 验证**（确认 key 修复后 exit=1/key 类归零）
3. **BUG-2**（修统计可信，避免误判）
4. **GAP-1**（provider 韧性——最深根因，但工程量大，绑 D2/Q1 决策）
5. **GAP-2**（封装解耦，与"一键装"目标强相关）
6. **BUG-3 + ISSUE-1/2 收尾**

> 注：88 无结果的精确归账受限（非全部 job 有 .exit 文件）；BUG-1 孤儿结果为结构推断（480>300 + 18 矛盾指纹），client 放弃时刻日志未记。
