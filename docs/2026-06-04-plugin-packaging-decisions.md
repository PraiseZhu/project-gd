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
