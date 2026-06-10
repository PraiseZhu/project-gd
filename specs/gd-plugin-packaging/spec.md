# Feature Specification: GD 三条链路插件封装与分发

**Created**: 2026-06-10
**Status**: Draft
**Input**: 用户描述："把 GD 项目封装成插件，分享给他人只需要一条终端命令就能把所有依赖自动安装，保证安装完立即就能使用 3 条链路的所有命令"
**Governing Constitution**: [`docs/constitution-plugin.md`](../../docs/constitution-plugin.md) v1.0.0（P1–P6）

## 背景与目标 *(Why)*

Project GD 的三条链路（L1 planning dispatch / L2 plan cross-review / L3 execution review，统归 `/gd` 四阶段命令）目前**只能在开发者本机运行**：命令文件里写死了开发者绝对路径，安装依赖一套需 ledger 授权、写入 `~/.claude/` 的本地脚本。**任何其他人都无法获得并使用这三条链路。**

本 feature 的目标：把这三条链路打包成一个标准 Claude Code 插件，使**任何拿到分发地址的人，用一行终端命令完成安装、reload 后即可使用全部链路命令**，且开发者后续改动能通过手动命令被安装者更新到。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 安装者一行命令装完即用 (Priority: P1)

一个从未接触过 GD 内部结构的人，拿到分发地址后，在终端粘贴**一行命令**完成安装，按提示 reload（或重启）一次，随后在自己的 Claude Code 会话里就能调用链路命令，无需手动配置路径、无需 pip 安装任何包。

**Why this priority**：这是本 feature 的北极星（constitution P1）。装不上或装完用不了，其余一切无意义。

**Independent Test**：在一台**未配置过 GD**的环境（或干净目录）执行那一行安装命令 + 一次 reload，确认链路命令出现在命令列表并能被触发，即完整验证本故事并交付"可分发"价值。

**Acceptance Scenarios**:
1. **Given** 安装者已具备前置外部依赖（见 FR-008 所列），**When** 执行单行安装命令并 reload 一次，**Then** 链路命令出现在可用命令列表且可触发。
2. **Given** 安装过程未要求安装者手动编辑任何路径或配置文件，**When** 安装完成，**Then** 链路引用的全部框架内文件都能被正确解析（无 "file not found"）。
3. **Given** 安装者从未运行过 GD 的旧 `install` 脚本，**When** 安装完成，**Then** 安装者的 `~/.claude/commands/` 未被写入任何命令副本（安装完全由插件机制接管）。

### User Story 2 - 在自己的项目里跑通链路 (Priority: P1)

安装者在**自己的某个项目目录**（不是 Project GD 本身）发起链路命令，对自己的项目做 plan / review，链路把产物写到正确位置，不污染插件自身、也不误写回 GD。

**Why this priority**：链路的价值在于作用于"目标项目"。若只能在 GD 自身目录跑，等于没分发出去（constitution P2 目标项目解析 + P4 写入隔离）。

**Independent Test**：在一个非 GD 的目标项目里跑链路的 happy path，确认产物落到安装者指定/隔离位置，且目标项目根被正确识别（未与插件根混淆）。

**Acceptance Scenarios**:
1. **Given** 安装者 cwd 在自己的项目，**When** 发起链路命令，**Then** 链路识别该项目为目标，产物写入隔离区或目标项目内，而非插件安装目录。
2. **Given** 插件随后被更新，**When** 更新完成，**Then** 安装者上一次运行产生的运行时数据（如 baselines）未丢失。

### User Story 3 - 缺外部依赖时得到中文人话提示 (Priority: P2)

安装者环境缺少链路所需的外部依赖（最典型：未安装或未认证 codex CLI；或 Python 版本过低）时，链路**不假装成功**，而是明确告诉安装者"缺什么、怎么补"，且用中文。

**Why this priority**：插件机制装不了 codex 这类外部二进制（constitution P5）。缺依赖若只吐英文报错或静默降级，安装者会误判"插件坏了"，分发体验崩塌。

**Independent Test**：在缺 codex 的环境跑需要 codex 的链路阶段，确认得到 fail-closed + 中文提示，且不产生伪通过结论。

**Acceptance Scenarios**:
1. **Given** 环境无可用 codex，**When** 触发依赖 codex 的 cross-review 阶段，**Then** 该阶段 fail-closed、给中文缺失提示，且**不**输出仅 Claude 的 APPROVED。
2. **Given** 不依赖 codex 的链路阶段（L1 planning），**When** 在无 codex 环境触发，**Then** 该阶段仍可正常运行。

### User Story 4 - 维护者 push 即发布、安装者手动更新 (Priority: P2)

维护者改完链路、`git push` 即视为发布新版本；安装者运行少量固定的手动命令即可更新到新版，无需任何自动更新机制。

**Why this priority**：用户明确——只要手动更新命令，不要 auto-update（constitution P6）。不写清更新方式，安装者拿不到后续改进。

**Independent Test**：维护者发布一处可见改动后，安装者按文档执行手动更新命令，确认改动生效。

**Acceptance Scenarios**:
1. **Given** 维护者已 push 一处链路改动，**When** 安装者执行文档所列的手动更新命令并 reload，**Then** 新改动在安装者环境生效。
2. **Given** 安装者未执行更新命令，**When** 维护者已 push，**Then** 安装者环境保持旧版本（不自动变化）。

### Edge Cases
- 安装者环境无 codex：L1 可用，L2/L3 cross-review fail-closed + 中文提示（不伪 APPROVED）。
- 安装者 Python 版本低于支持下限：链路启动即给出明确的版本要求提示，而非中途崩溃。
- 安装者 cwd 恰好在 Project GD 自身目录 vs 在其他项目目录：目标项目识别必须都正确，不能把他人项目误写回插件目录。
- 插件被 `update` 覆盖后：安装者既有运行时数据（baselines 等）必须仍在。
- 安装者重复执行安装命令：应幂等或给出已安装提示，不产生损坏状态。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 分发产物 MUST 让安装者通过**单行终端命令**完成安装（注册 marketplace + 安装插件）。
- **FR-002**: 安装并 reload 后，链路命令 MUST 出现在安装者可用命令列表并可触发。
- **FR-003**: 链路引用的所有框架内文件（命令、脚本、prompts、模板、schema、docs、fixtures）MUST 随插件一并分发，使任一引用在安装者机器上都能解析。
- **FR-004**: 分发产物 MUST NOT 含任何开发者机器专属的绝对路径；路径解析对安装者机器透明。
- **FR-005**: 链路 MUST 能识别安装者的**目标项目**（被 plan/review 的项目），且 MUST NOT 把目标项目与插件自身位置混淆。
- **FR-006**: 链路运行时产物 MUST 写入更新安全的隔离位置或目标项目内，MUST NOT 写入会被更新覆盖的插件安装目录。
- **FR-007**: 安装 MUST NOT 向安装者的 `~/.claude/commands/` 写入命令副本；安装完全由插件机制承担（旧的"装到 ~/.claude + ledger 授权"模型不随插件分发）。
- **FR-008**: 分发产物 MUST 在面向安装者的说明中**逐项列出无法自动安装的外部前置依赖**（至少含 codex CLI 及其认证、Python 最低版本、链路实际调用的其他命令行工具）。
- **FR-009**: 当外部依赖缺失时，相关链路阶段 MUST fail-closed 并给出**中文**可读提示（缺什么、如何补），MUST NOT 静默降级，MUST NOT 产出伪造的通过结论。
- **FR-010**: 链路 MUST NOT 要求安装者 `pip install` 任何第三方包（仅依赖语言标准库 + 随插件分发的本地模块）。
- **FR-011**: 分发产物 MUST 提供面向安装者的**手动更新命令文档**；MUST NOT 包含任何自动更新机制。
- **FR-012**: 维护者发布新版本 MUST NOT 要求独立构建步骤（push 即发布）。
- **FR-013**: 「装完即用」的说明 MUST 显式包含一次 reload/重启步骤（不得暗示 install 后无需重载即生效）。
- **FR-014**: 「他人可装可用」MUST 经一次跨机/跨目录冒烟证明，MUST NOT 仅凭本仓自身目录的自测断言成立。

*[NEEDS CLARIFICATION: 插件交付范围 —— "3 条链路所有命令"具体指哪些命令文件？(a) 仅 `/gd`（四阶段三档全在 gd.md 内）；(b) `/gd` + `/goal-gd`（执行提示词生成辅助）；(c) `/gd` + `/goal-gd` + `/review2`（独立 L2 链路，constitution 称其为"另一套命令"）。此项决定 bundle 内容与"使用全部链路"的边界。]*

### Key Entities *(涉及数据时)*

- **分发包（Plugin Bundle）**：交付给安装者的插件单元，含链路命令 + 运行所需的全部框架内文件 + 面向安装者的安装/前置/更新说明。
- **分发源（Marketplace/Repo）**：安装者注册并从中安装插件的来源地址。
- **目标项目（Target Project）**：安装者用链路去 plan/review 的项目，与插件自身位置相互独立。
- **运行时数据（Runtime State）**：链路执行产生、需跨更新保留的产物（如 baselines、运行报告）。
- **外部前置依赖（External Prerequisites）**：插件无法自动安装、需安装者自备的工具（codex、Python 运行时等）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 新安装者从零到成功触发第一条链路命令，所需终端命令 ≤ **1 行** + **1 次** reload。
- **SC-002**: 安装后链路 runtime 引用的文件，可解析率 = **100%**（"file not found" 计数 = 0）。
- **SC-003**: 在**非 Project-GD** 的项目目录中，链路 happy path 端到端可跑通（跨目录冒烟 = 通过）。
- **SC-004**: 缺 codex 环境下，依赖 codex 的链路阶段产生伪 APPROVED 数 = **0**，且中文缺失提示出现率 = **100%**。
- **SC-005**: 维护者发布更新到安装者获取生效，所需安装者手动命令 ≤ **3 条**。
- **SC-006**: 插件更新后，安装者既有运行时数据保留率 = **100%**（丢失计数 = 0）。
- **SC-007**: 分发产物中开发者机器专属绝对路径出现次数 = **0**。
- **SC-008**: 安装过程要求安装者 `pip install` 的第三方包数量 = **0**。

## Assumptions

- 安装者已自行安装并认证好链路所需的外部工具（codex CLI 等）；插件只负责声明前置、不负责代装（constitution P5）。
- 分发采用 git-subdir 同仓布局、`plugin.json` 省略 version（SHA 即版本），与 constitution P6 一致。
- 「3 条链路」指 `/gd` 四阶段内的 L1/L2/L3；`/review2` 是否纳入由上方 NEEDS CLARIFICATION 决定。
- *[NEEDS CLARIFICATION: 分发源平台与可见性 —— 插件 repo 发布在哪、对安装者是否可直接访问？(a) GitHub 公开 repo（`owner/repo` 形式，外部人可直接一行安装）；(b) 私有/企业 Git（如 GitLab，安装者需先有访问权与凭据，"一行命令"对外人不成立）；(c) 仅本地路径分享（不走 marketplace）。此项决定"对他人一行命令"是否真能成立、以及安装文档怎么写。]*
- 安装者使用的 Claude Code 版本支持 `claude plugin marketplace add` / `install` / `update` 命令族。
