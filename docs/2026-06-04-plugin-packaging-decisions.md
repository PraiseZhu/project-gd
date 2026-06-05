# GD 插件封装决策记录

> 日期：2026-06-04
> 用途：封装 GD 为可分发插件时**必须照此执行**的边界决策。后续封装方案直接引用本文件。
> 配套：L3 收编与解耦清单见 [`../vendor/l3-transport/README.md`](../vendor/l3-transport/README.md)

---

## 决策 D1：⑥ codex CLI —— 不打包,安装脚本检测+引导

**结论**：codex 二进制**不进插件包**,作为外部依赖声明 + 安装脚本检测。

**理由**：
- codex 是 **Mach-O arm64 原生二进制**(`~/.codex/packages/standalone/releases/0.136.0-aarch64-apple-darwin/bin/codex`),打包会平台锁定——别人 Intel Mac / Linux 直接跑不了
- 重新分发 OpenAI Codex 二进制可能违反许可
- 体积 + 版本僵化
- **参照**：OpenAI 官方 codex 插件 1.6M，**不含二进制**,只声明依赖

**封装时要加**：
1. `plugin.json` / README 声明依赖：`需要 codex CLI >= 0.136`
2. 安装脚本检测：`command -v codex` + `codex --version` ≥ 最低版本
3. 缺失/版本低 → 打印官方安装命令引导用户自行安装,**不替他打包/安装二进制**

---

## 决策 D2：⑦ provider / key —— 绝不打包,provider 可配置,引导配 key

**结论**：provider 配置和 API key **绝不进插件包**;provider 做成**可配置**,key 由用户自填。

**理由**：
- key 是**密钥 + 私人**(当前 `TAPTAP_API_KEY`),打包 = 泄露 + 别人也用不了你的 key
- ⚠️ **可分发性硬伤**：当前 codex 绑死第三方代理 `tapsvc`(`base_url = https://llm-proxy.tapsvc.com/v1`)。别人没有 tapsvc 账号/key → 装了插件也**跑不起来**

**封装时要加**：
1. provider **不硬编码 tapsvc**——让用户配自己的 `base_url` + provider(OpenAI 官方 / 任意兼容服务)
2. 提供 `config.toml` **模板**(占位符,非真实值),引导用户填
3. 安装脚本引导用户设置 key(交互输入 or 环境变量),key **绝不写进插件包/git**
4. plist / writer 里的 key 一律 redact 占位(已在 vendor/ 收编时处理)

---

## 待确认 Q1：provider 分发策略(A / B)

封装前需用户最终拍板:

| 方案 | 含义 | 影响 |
|------|------|------|
| **A. 通用化(倾向)** | 插件让用户自配任意 provider,不绑 tapsvc | 真正可公开分发;安装脚本需引导配 provider |
| **B. 绑定 tapsvc** | 仅给有 tapsvc 的人用(团队内部) | 分发范围受限;安装脚本可预设 tapsvc base_url |

> 2026-06-04 状态：用户认可 D1/D2 决策方向,A/B 策略**尚未最终选定**,倾向 A(可分发性最好)。

---

## 封装边界总览(①-⑦)

| 跳 | 进插件包? | 封装动作 |
|----|----------|---------|
| ①-⑤(bridge+writer+daemon+skill壳) | ✅ 打包 | 已收编 vendor/,封装时解耦路径(见 vendor README) |
| ⑥ codex CLI | ❌ | D1：声明依赖 + 检测引导 |
| ⑦ provider | ❌ | D2：可配置 + 模板 |
| ⑦ key | ❌ 绝不 | D2：引导自填,绝不入包 |

---

## L1 / L2 隔离完整性审计(2026-06-04)

> 背景：L3 收编时发现「live 传输层 ②-⑤ 是 GD 自己派发执行、却物理散在 `~/.claude` 之外」的真缺口,靠复制进 `vendor/l3-transport/` 补齐。本节用**同款逻辑**核查 L1/L2 是否存在类似「可复制收编的 live 能力缺口」。

**结论:L1/L2 不存在 L3 式的可复制缺口。** 不是同类问题,无需新增收编。

**判定依据(6 项只读核查,全部通过):**

| 核查项 | 命令/位置 | 结果 |
|--------|----------|------|
| GD 链路是否引用 codex 侧 skill | `grep 设计方案评审\|plan-design-review\|design-review\|--skill` 全 `commands/`+`scripts/` | 零命中 |
| daemon 调 codex 的实参 | `vendor/l3-transport/handoff/bin/codex-watch:403` | `codex exec --sandbox --skip-git-repo-check --ephemeral --cd` —— 不传 `--skill`/config 路径/AGENTS |
| GD 是否运行时读 `~/.codex` 配置 | `grep .codex\|AGENTS.md\|config.toml\|default.rules` 链路代码 | 仅 audit/parity/sync 工具引用,**无运行时消费** |
| AGENTS.md 是否含 GD/评审专属指令 | `grep gd\|review2\|评审 ~/.codex/AGENTS.md` | 零命中(纯 codex 隐藏根只读规则) |
| default.rules 是否含 GD 规则 | `grep gd\|评审 ~/.codex/rules/default.rules` | 零命中 |
| L1/L2 mirror 释放门 | `bash scripts/gd-codex-chain-release-status.sh` | `L1_RELEASE_STATUS: READY` / `L2_RELEASE_STATUS: READY` |

**为什么 L1/L2 与 L3 性质不同:**

- **L3 ②-⑤** = GD 亲自编写、GD 代码直接 invoke 的脚本 → 属于 GD 可执行面,散在外部是真缺口 → 复制正确。
- **L1**(codex 二进制)+ **L2**(config.toml / AGENTS.md / rules / skills / memories)= 全是 **codex 自身 / 第三方 / 用户私有**,由 codex 二进制自己 bootstrap 读取,**GD 代码一行都不碰**。GD 经干净接口 `codex exec + capsule(prompt)` 调用,不注入 AGENTS、不调 `--skill`、不自读 config。
- L2 唯一功能依赖 = config.toml 的 `model_provider=tapsvc + model=gpt-5.5` 块 → 已被 **D2** 覆盖(可配置 + 模板)。AGENTS.md/rules/memories/automations/codex-skills 对 GD review **非依赖**,排除正确。

**L1/L2 的"收编"等价物不是复制,而是 D1/D2 的可分发产物:**

| 层 | 可复制收编? | 正确的可分发形态 | 当前状态 |
|----|------------|----------------|---------|
| L1 二进制 | ❌(Mach-O 平台锁 + 许可,D1) | 声明依赖 + `command -v codex` 检测脚本 | 版本锁快照 `codex-package.json` 已 mirror + READY;检测脚本属封装阶段(未建) |
| L2 config | ❌ 明文(含 key + 绑 tapsvc,D2) | redact 占位 config.toml 模板 + provider 可配置 | audit mirror(key 已 redact)READY;**可安装的模板未建**,属封装阶段 |

**唯一前瞻动作**(均属封装阶段非目标,且 config 模板形态依赖 Q1 的 A/B 决策):

1. **L2 config.toml 可安装模板**(占位符,非 audit mirror)—— 因为:别人装插件时 `~/.codex/config.toml` 可能不存在或 provider 不同,无模板则无从配 provider/model,装了跑不起来 [价值: 高,但卡在 Q1 未定 A/B]
2. **L1 codex 检测引导脚本**(`command -v codex` + 版本校验)—— 因为:别人机器可能无 codex 或版本 < 0.136,无检测则链路静默失败、报错难定位 [价值: 中,封装阶段标准动作]

> 即:L1/L2 已达「自洽 + audit READY」;通往「他人一键装」缺的是 D1/D2 的封装产物,**不是**散在外部待复制的 live 能力。L3 那种「核查出真缺口→复制」在 L1/L2 不复现。

---

## 决策 D3:发布治理脚本不进插件包(2026-06-04)

> 触发:用户提醒"目标是让他人一键安装"。判据从"是否被 command 引用"修正为"**终端用户跑 `/gd`、`/review2` 做 review 时是否需要**"。

**结论:GD 的"自检/发布/安装 parity"治理脚本是开发者治理动作,不是用户 review 运行时 → 移入 `tools/`,封装时打包白名单排除 `tools/`。**

**已隔离的发布治理家族(5,scripts/ → tools/):**

| 脚本 | 职责 | 用户 review 要用 |
|------|------|:---:|
| `gd-final-closure-status.sh` | GD 最终发布门(READY_FOR_HANDTEST aggregator) | ❌ |
| `gd-codex-chain-release-status.sh` | L1/L2/L3 发布闸 | ❌ |
| `gd-root-parity-status.sh` | 上者 helper | ❌ |
| `gd-parity-verify.sh` | 安装后 source==installed parity 校验 | ❌ |
| `check-gd-command-parity.sh` | /gd install hash 闸 | ❌ |

**判定证据:** 命令层引用(`gd.md:8/304/492`、`review2.md:14/116`)全是**安装/parity 治理文本 + 权威边界说明**,非用户运行时硬调用;唯一可执行耦合是 `gd-build-review2-capsule.py` 为 `/review2 --profile release_closure` 执行 release-status/final-closure 取 **GD 自己的**发布事实——该 profile 即"GD 够不够格发布"自检,非通用用户特性。

**搬迁已处理的耦合:** moved 脚本内部互调(final-closure→release-status/parity-verify/root-parity、release-status→parity-verify、check-route-preflight→check-parity)+ capsule builder 的 mandatory-read & exec 路径 + 命令 prose 引用,全部 `scripts/` → `tools/`。capsule builder 对缺失脚本已有 graceful degrade(`(not found)` fallback)——故插件不打包 `tools/` 时,`release_closure` profile 干净降级,其余 profile 不受影响。

**`release_closure` profile 的封装姿态(待封装时确认):** 当前实现是 GD 自指(校验 GD 自己的 mirror/parity)。选项:① 插件保留该 profile,用户用时 graceful degrade(不改命令面,最省);② 封装时从 shipped `review2.md` 显式标注该 profile 为 GD-internal。倾向 ①。

> 仍留在 `scripts/` 的 install/uninstall(`install-gd-command.sh`/`install-review-route-command.sh`/`uninstall-gd-command.sh`)属"安装机制",封装时由 plugin.json/marketplace 接管 → 封装阶段再定去留,非本次范围。
