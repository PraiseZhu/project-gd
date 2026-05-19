# mirrors/ — 外部链路只读快照

## 用途

本目录存放 codex exec 调用链 L1/L2 层的工程文件快照，供 Project GD git 版本审计。

**不包含运行时职责**：codex 运行时仍读取原始路径（`~/.npm-global/`、`~/.codex/`），镜像仅用于变更可见性。

## 禁止手动编辑

镜像内容由 `../bin/gd-sync-codex-chain.sh` 负责维护。**不要直接编辑此目录下的任何文件**，手动改动会在下次 sync 时被覆盖，且污染 git 变更审计。

## 目录结构

```
mirrors/codex-chain/
├── SYNC.log                   ← 同步审计轨迹（仅在镜像有变更时追加）
├── l1-binary/                 ← L1: @openai/codex npm 包入口文件
│   ├── codex.js               ← 主执行脚本
│   ├── rg                     ← 内置 ripgrep
│   └── package.json           ← 版本锁（当前 v0.130.0）
├── l2-config/                 ← L2: ~/.codex/ 全局策略配置
│   ├── config.toml            ← model/sandbox/approval_policy 等
│   ├── AGENTS.md              ← 全局 agent 指令
│   ├── rules/default.rules    ← 全局规则
│   └── ...
├── l2-automations/            ← L2: 用户自定义自动化任务
├── l2-memories/               ← L2: codex 记忆快照
├── l2-system-skills/          ← L2: codex 内置 system skill（5 个）
└── l2-skills-manifest.json    ← 288 个用户安装 skill 的索引（不含全文）
```

## 更新方式

```bash
# 在 Project GD 根目录执行
bash bin/gd-sync-codex-chain.sh              # dry-run 预览
bash bin/gd-sync-codex-chain.sh --apply      # 实际同步
```

同步完成后手动喊「提交代码」触发 commit-projects skill 提交变更。

## 排除项说明

| 排除项 | 原因 |
|--------|------|
| `~/.codex/auth.json` | 含 API 密钥 |
| `node_modules/` (188MB) | 平台编译产物，package.json 已锁版本 |
| `~/.codex/plugins/cache/` (76MB) | marketplace 下载缓存，可再生 |
| `~/.codex/vendor_imports/` (7.7MB) | 社区 skill 缓存，可再生 |
| cc-* skill 全文 (10MB/288 个) | 改用 l2-skills-manifest.json 索引 |
| sessions/logs/sqlite/cache | 运行时产物 |
