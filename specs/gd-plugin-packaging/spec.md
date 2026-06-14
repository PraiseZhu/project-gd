# Feature Specification: GD 三条链路插件封装与分发

**Created**: 2026-06-10 | **Last Updated**: 2026-06-11
**Status**: Draft
**Input**: 用户描述："把 GD 项目封装成插件，分享给他人只需要一条终端命令就能把所有依赖自动安装，保证安装完立即就能使用 3 条链路的所有命令"
**Governing Constitution**: [`docs/constitution-plugin.md`](../../docs/constitution-plugin.md) v1.1.0（P1–P6）

> **2026-06-11 修订说明**：① 订正架构事实错误——三条链路是**三个独立命令**（`/review1` L1 / `/review2` L2 / `/gd` L3），不是「`/gd` 四阶段」；早期草稿把 L3 内部四阶段误当成三链路，并完全漏列 `/review1`。② 回填两项已澄清决策（命令范围 = 三命令全集；分发 = 私有 GitLab）。③ 补全 codex 传输层（`vendor/l3-transport` + codex-watch daemon）这一此前缺失的关键范围——它是三链路 cross-review 的命脉。

## 背景与目标 *(Why)*

Project GD 的**三条 review 链路是三个独立命令**：
- **L1 = `/review1`**：codex 交叉讨论 + 轻量 review
- **L2 = `/review2`**：profile-aware Codex 工作台
- **L3 = `/gd`**：四阶段（计划 → 审计划 → 执行 → 审代码）多 agent 链

（注意：「四阶段」是 `/gd` 一个命令的**内部阶段**，不是三条链路。）

这三条链路目前**只能在开发者本机运行**：命令文件里写死了开发者绝对路径，cross-review 依赖一套写入 `~/.claude/` 的 codex 传输层（daemon + 二进制），且依赖外部 codex CLI 与开发者自己的认证 key。**任何其他人都无法获得并使用这三条链路。**

本 feature 的目标：把这三条链路打包成一个标准 Claude Code 插件，使**任何拿到分发地址且具备 codex 前置的人，用一行终端命令完成插件安装、reload 后即可使用全部链路命令**，且开发者后续改动能通过手动命令被安装者更新到。

> **范围诚实边界（核心）**：一行命令交付的是「插件命令 + 框架内文件」。链路的 **cross-review 完整功能**额外依赖 **codex 传输栈**（codex CLI + 安装者自备 key + codex-watch daemon 部署），这部分**插件装不了、密钥也不能分享**——因此「复制一条命令即得三链路完整功能」**不成立**。真实交付是两段式：① 一行装插件命令；② 安装者一次性自备 codex 传输栈前置。本 spec 据此定义范围（见 FR-015~FR-017、SC-009）。

## Clarifications

### Session 2026-06-11
- Q: 目标平台范围（仅 macOS / +Windows / 跨平台）？ → A: **仅支持 macOS**；Windows / Linux 明确 out-of-scope（传输层基于 macOS LaunchAgent + launchctl，跨平台需重做 daemon，本期不纳入）。
- Q: 链路运行产物默认放哪 / 预设怎么配？ → A: 不硬编码默认；插件 MUST 提供一个**专门的 setup 命令**（随插件分发，与三链路命令并列），安装后由安装者运行来配置安装者预设（字段集见 FR-018）。该命令**非一次性**——安装者可**随时重新运行 setup 命令**进入配置、单独修改任一项，无需重装。预设存于更新安全位置、跨更新保留（见 FR-018）。
- Q: 输出位置是否影响 handoff 传输层？预设字段怎么收集？ → A: ① 区分两类位置：**handoff 传输目录**（`state-paths.sh:8` 的 `HANDOFF_ROOT`，默认 `~/.claude/handoff`，env 可覆盖）是 daemon↔client 必须一致的**协调位置**，MUST 由插件管理（封装设插件内目录），**不进安装者预设、不让自由填**（填错即断链）；安装者预设只管**审查产物输出位置**。② 预设所有字段 MUST 以**选项**提供，MUST NOT 自由填路径/值。③ key 须支持**官方 key 与第三方(代理) key 两类选项**；codex **模型**与**模型强度(effort)** 也各给选项。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 安装者一行命令装完插件命令即出现 (Priority: P1)

一个从未接触过 GD 内部结构的人，拿到分发地址（且具备私有 GitLab 访问权）后，在终端粘贴**一行命令**完成插件安装，按提示 reload 一次，随后在自己的 Claude Code 会话里就能看到并触发三条链路命令（`/review1` / `/review2` / `/gd`），无需手动配置路径、无需 pip 安装任何包。

**Why this priority**：这是本 feature 的北极星（constitution P1）。命令装不上或装完不出现，其余一切无意义。

**Independent Test**：在一台**未配置过 GD**的环境执行那一行安装命令 + 一次 reload，确认三条链路命令出现在命令列表并能被触发，即完整验证本故事。

**Acceptance Scenarios**:
1. **Given** 安装者具备私有 GitLab 访问权，**When** 执行单行安装命令并 reload 一次，**Then** `/review1` / `/review2` / `/gd` 出现在可用命令列表且可触发。
2. **Given** 安装过程未要求安装者手动编辑任何路径或配置文件，**When** 安装完成，**Then** 链路引用的全部框架内文件（含 `vendor/l3-transport`）都能被正确解析（无 "file not found"）。
3. **Given** 安装者从未运行过 GD 的旧 `install-gd-command.sh`，**When** 安装完成，**Then** 安装者的 `~/.claude/commands/` 未被写入任何命令副本（命令安装完全由插件机制接管）。

### User Story 2 - 自备 codex 传输栈后 cross-review 完整可用 (Priority: P1)

安装者按 README 一次性完成 codex 传输栈前置（装 codex CLI + 配自己的认证 key + 跑 `install-transport.sh` 部署 daemon）后，三条链路的 cross-review 完整跑通，而非 fail-closed。

**Why this priority**：cross-review 是三条链路的核心价值；不交代清传输栈前置，安装者会拿到「命令在、审查全 fail-closed」的假完整（constitution P5）。

**Independent Test**：在已备齐 codex 传输栈的环境，对一个非 GD 项目跑三链路 cross-review 的 happy path，确认得到真实 codex 审查结论（非 fail-closed、非仅 Claude 的 APPROVED）。

**Acceptance Scenarios**:
1. **Given** codex CLI + key + daemon 均就位，**When** 触发 `/review2` 或 `/gd` 的 cross-review 阶段，**Then** 产出含 codex 侧意见的真实审查结论。
2. **Given** README 已逐项列出传输栈三件套（CLI / key / daemon 部署），**When** 安装者照做，**Then** 无需阅读 GD 内部代码即可完成前置。
3. **Given** 安装者已配过预设，**When** 之后想换 codex 模型、更新 key 或改产物位置，**Then** 重新运行 setup 命令即可单独修改任一项，无需重装插件、不丢其他配置。

### User Story 3 - 在自己的项目里跑通链路、产物不污染插件 (Priority: P1)

安装者在**自己的某个项目目录**（不是 Project GD 本身）发起链路命令，对自己的项目做 plan / review，链路把产物写到正确位置，不污染插件自身、也不误写回 GD。

**Why this priority**：链路的价值在于作用于「目标项目」。若只能在 GD 自身目录跑，等于没分发出去（constitution P2 目标项目解析 + P4 写入隔离）。

**Independent Test**：在一个非 GD 的目标项目里跑链路 happy path，确认产物落到隔离位置，且目标项目根被正确识别（未与插件根混淆）。

**Acceptance Scenarios**:
1. **Given** 安装者 cwd 在自己的项目，**When** 发起链路命令，**Then** 链路识别该项目为目标，产物写入隔离区或目标项目内，而非插件安装目录。
2. **Given** 插件随后被更新，**When** 更新完成，**Then** 安装者上一次运行产生的运行时数据（如 baselines）未丢失。

### User Story 4 - 缺 codex 传输栈时得到中文人话提示 (Priority: P2)

安装者环境缺少传输栈任一环（codex CLI 未装/未认证、daemon 未部署、key 未注入）时，链路**不假装成功**，而是明确告诉安装者「缺什么、怎么补」，且用中文。

**Why this priority**：插件装不了 codex 二进制/daemon/密钥（constitution P5）。缺依赖若只吐英文 `transport_failed` 或静默降级，安装者会误判「插件坏了」，分发体验崩塌。

**Independent Test**：在缺 codex 的环境跑需要 codex 的链路阶段，确认得到 fail-closed + 中文提示，且不产生伪通过结论。

**Acceptance Scenarios**:
1. **Given** 环境无可用 codex 传输栈，**When** 触发依赖 codex 的 cross-review 阶段，**Then** 该阶段 fail-closed、给中文缺失提示，且**不**输出仅 Claude 的 APPROVED。
2. **Given** 不依赖 codex 的链路阶段（如 `/gd` 的纯 planning dispatch），**When** 在无 codex 环境触发，**Then** 该阶段仍可正常运行。

### User Story 5 - 维护者 push 即发布、安装者手动更新 (Priority: P2)

维护者改完链路、`git push` 即视为发布新版本；安装者运行少量固定的手动命令即可更新到新版，无需任何自动更新机制。

**Why this priority**：用户明确——只要手动更新命令，不要 auto-update（constitution P6）。

**Independent Test**：维护者发布一处可见改动后，安装者按文档执行手动更新命令，确认改动生效。

**Acceptance Scenarios**:
1. **Given** 维护者已 push 一处链路改动，**When** 安装者执行文档所列手动更新命令并 reload（传输层改动时还需重跑 `install-transport.sh`），**Then** 新改动在安装者环境生效。
2. **Given** 安装者未执行更新命令，**When** 维护者已 push，**Then** 安装者环境保持旧版本（不自动变化）。

### Edge Cases
- 安装者在非 macOS（Windows / Linux）：明确 out-of-scope；README MUST 把「仅支持 macOS」列为前提，安装文档 MUST NOT 暗示其他平台可用。
- 安装者无私有 GitLab 访问权：连分发源都拉不到——README MUST 把「需先有 repo 访问权」列为第 0 步前提。
- 安装者环境缺 codex 传输栈任一环：L1 纯 planning 可用，cross-review fail-closed + 中文提示（不伪 APPROVED）。
- 安装者 Python 版本低于支持下限：链路启动即给出明确版本要求提示，而非中途崩溃。
- 安装者 cwd 恰好在 Project GD 自身目录 vs 在其他项目目录：目标项目识别必须都正确，不能把他人项目误写回插件目录。
- 插件被 `update` 覆盖后：安装者既有运行时数据（baselines 等）必须仍在；若传输层有更新，需提示重跑 `install-transport.sh`。
- 安装者重复执行安装命令：应幂等或给出已安装提示，不产生损坏状态。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 分发产物 MUST 让安装者通过**单行终端命令**完成**插件**安装（注册 marketplace + 安装插件）。
- **FR-002**: 安装并 reload 后，三条链路命令（`/review1` / `/review2` / `/gd`）MUST 出现在安装者可用命令列表并可触发。
- **FR-003**: 三条链路引用的所有框架内文件 MUST 随插件一并分发，使任一引用在安装者机器上都能解析；bundle 完整性范围 MUST 至少含：`commands`（含 `review1.md` / `review2.md` / `gd.md` 三命令文件）/ `scripts`（含 `scripts/lib/`）/ `prompts` / `templates` / `schema` / `docs` / `fixtures` / **`vendor/l3-transport`**。
- **FR-004**: 分发产物 MUST NOT 含任何开发者机器专属的绝对路径；路径解析对安装者机器透明。
- **FR-005**: 链路 MUST 能识别安装者的**目标项目**（被 plan/review 的项目），且 MUST NOT 把目标项目与插件自身位置混淆。
- **FR-006**: 链路运行时产物 MUST 写入**安装者在预设（FR-018）中选定的输出位置**（默认更新安全的隔离位置，可选目标项目内），MUST NOT 写入会被更新覆盖的插件安装目录。
- **FR-007**: 安装 MUST NOT 向安装者的 `~/.claude/commands/` 写入命令副本；命令安装完全由插件机制承担。（注：codex 传输 daemon 部署到 `~/.claude/handoff` 属 FR-016 前置，不在此禁区——二者路径与性质不同。）
- **FR-008**: 分发产物 MUST 在面向安装者的说明中**逐项列出无法自动安装的外部前置依赖**，其中 codex 传输栈 MUST 拆成三件套明示：(a) codex CLI 二进制 + 认证；(b) 安装者**自备的** codex/认证 key（密钥不随插件分发）；(c) codex-watch daemon 部署。其余含 Python 最低版本、链路调用的其他命令行工具（git / shasum 等）。
- **FR-009**: 当外部依赖缺失时，相关链路阶段 MUST fail-closed 并给出**中文**可读提示（缺什么、如何补），MUST NOT 静默降级，MUST NOT 产出伪造的通过结论。
- **FR-010**: 链路 MUST NOT 要求安装者 `pip install` 任何第三方包（仅依赖语言标准库 + 随插件分发的本地模块）。
- **FR-011**: 分发产物 MUST 提供面向安装者的**手动更新命令文档**；MUST NOT 包含任何自动更新机制。
- **FR-012**: 维护者发布新版本 MUST NOT 要求独立构建步骤（push 即发布）。
- **FR-013**: 「装完即用」的说明 MUST 显式包含一次 reload/重启步骤（不得暗示 install 后无需重载即生效）。
- **FR-014**: 「他人可装可用」MUST 经一次跨机/跨目录冒烟证明，MUST NOT 仅凭本仓自身目录的自测断言成立。
- **FR-015**（v1.1.0 新增）: bundle MUST 包含 `vendor/l3-transport/`（含 `codex-consult.sh` / `review-result-writer.sh` / `codex-send-wait` / `codex-watch` / lib / plist / `install-transport.sh`）；打包完整性校验 MUST 把它列为 blocking。理由：L1/L3 cross-review 直接从此目录运行，缺则三链路 cross-review 全部 fail-closed。
- **FR-016**（v1.1.0 新增）: 分发产物 MUST 提供 codex 传输栈的**前置部署文档**——安装者一次性执行 `vendor/l3-transport/scripts/install-transport.sh`（部署 daemon 到 handoff 目录 + LaunchAgent）并注入自己的 key。此步骤 MUST 与「一行装插件命令」**分两段**清楚呈现，MUST NOT 暗示其包含在一行命令内。传输的 `HANDOFF_ROOT`（`state-paths.sh:8`，env 可覆盖，默认 `~/.claude/handoff`）MUST 被设为**插件管理的、daemon↔client 一致的协调位置**（封装时设插件内目录），MUST NOT 让安装者自由填写——它是传输协调路径，两端对不上即断链；故 `HANDOFF_ROOT` 不属安装者预设（FR-018）。
- **FR-017**（v1.1.0 新增）: 分发产物 MUST NOT 内置任何 API key/密钥，MUST NOT 尝试代装 codex CLI 等外部二进制；这两类前置由安装者自备（与 FR-008 一致）。
- **FR-018**（2026-06-11 新增/细化，setup 命令 + 可重配预设）: 分发产物 MUST 提供一个**专门的 setup 命令**（随插件分发，与三链路命令并列在 bundle 内），收集并持久化安装者预设。**所有预设字段 MUST 以「选项」提供，MUST NOT 让安装者自由填路径/值**（自由填易破坏传输协同与隔离）。字段：
  - (a) **审查产物输出位置**——选项制（如 `${CLAUDE_PLUGIN_DATA}` / 目标项目内 / 其他受控选项），驱动 FR-006 默认值；
  - (b) **codex key**——MUST 同时支持「官方 key」与「第三方(代理) key」两类选项 + key 值输入；不同类型对应不同 codex 配置（provider / base_url / env_key）。key 写入 daemon 运行环境，MUST NOT 入 git / 不进 bundle / 不设内置默认 key；
  - (c) **codex 模型**——选项制（如 gpt-5.5 / gpt-5.5-pro / gpt-5.4 / gpt-5.4-mini / gpt-5）；
  - (d) **codex 模型强度（effort）**——选项制（如 none / low / medium / high / xhigh；`none` 为 gpt-5.5 显式无推理路径）。
  该 setup 命令 **MUST NOT 是一次性的**——安装者 MUST 能**随时重新运行**它进入配置、单独修改任一项，无需重装插件、不丢其他项。预设结果 MUST 存于更新安全位置（如 `${CLAUDE_PLUGIN_DATA}`），插件 `update` MUST NOT 清除。注：传输 `HANDOFF_ROOT` **不属**安装者预设（见 FR-016，插件管理）。命令名与首次引导形态属 `/gd plan` 阶段决定。

> **已澄清决策（2026-06-11 回填，原 NEEDS CLARIFICATION 已解析）**：
> - **插件交付范围**：= 三条链路的**全部命令** = `/review1`（L1）+ `/review2`（L2）+ `/gd`（L3）三个独立命令文件及其依赖；**非**仅 `/gd`。
> - **分发源平台与可见性**：= **私有 GitLab**。安装者 MUST 先具备该 repo 访问权与凭据；「一行命令」对**无访问权的外部人不直接成立**，README MUST 把「需 repo 访问权」列为第 0 步前提（对应 Edge Case 与 P6）。

### Key Entities *(涉及数据时)*

- **分发包（Plugin Bundle）**：交付给安装者的插件单元，含三条链路命令 + 运行所需全部框架内文件（含 `vendor/l3-transport`）+ 面向安装者的安装/前置/更新说明。
- **分发源（Marketplace/Repo）**：安装者注册并从中安装插件的来源地址（私有 GitLab，需访问权）。
- **codex 传输栈（Codex Transport Stack）**：cross-review 命脉——codex CLI + 安装者自备 key + codex-watch daemon（经 `install-transport.sh` 部署）。插件无法自动安装，由安装者自备。
- **目标项目（Target Project）**：安装者用链路去 plan/review 的项目，与插件自身位置相互独立。
- **运行时数据（Runtime State）**：链路执行产生、需跨更新保留的产物（如 baselines、运行报告）。
- **安装者预设（Setup Config）**：由 setup 命令以**选项制**收集的安装者级配置——审查产物输出位置 / codex key（官方 或 第三方 + 值）/ codex 模型 / 模型强度(effort)；存于更新安全位置，跨更新保留；随时重跑 setup 命令可单独修改任一项。传输 `HANDOFF_ROOT` **不在**此预设内（由插件管理，见 Codex 传输栈 / FR-016）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 新安装者从零到三条链路命令出现在命令列表，所需终端命令 ≤ **1 行** + **1 次** reload。*（此指标仅覆盖「插件命令可见可触发」；cross-review 完整功能受 codex 传输栈前置限制，见 SC-009——故 MUST NOT 被解读为「一行命令即得完整功能」。）*
- **SC-002**: 安装后链路 runtime 引用的文件（含 `vendor/l3-transport`），可解析率 = **100%**（"file not found" 计数 = 0）。
- **SC-003**: 在**非 Project-GD** 的项目目录中，链路 happy path 端到端可跑通（跨目录冒烟 = 通过）。
- **SC-004**: 缺 codex 环境下，依赖 codex 的链路阶段产生伪 APPROVED 数 = **0**，且中文缺失提示出现率 = **100%**。
- **SC-005**: 维护者发布更新到安装者获取生效，所需安装者手动命令 ≤ **3 条**（传输层有改动时另加一次 `install-transport.sh`）。
- **SC-006**: 插件更新后，安装者既有运行时数据保留率 = **100%**（丢失计数 = 0）。
- **SC-007**: 分发产物中开发者机器专属绝对路径出现次数 = **0**。
- **SC-008**: 安装过程要求安装者 `pip install` 的第三方包数量 = **0**；分发物中内置 API key/密钥数量 = **0**。
- **SC-009**（v1.1.0 新增）: 在备齐 codex 传输栈（CLI + key + daemon）的环境，三条链路各自的 cross-review happy path 真实跑通率 = **100%**（即「命令可见」之外，cross-review 完整功能可达）；README 对传输栈三件套的前置声明完整度 = 三件套全列。
- **SC-010**（2026-06-11 新增/细化）: setup 命令收集的预设四项（输出位置 / codex key / codex 模型 / 模型强度）完整度 = **4/4**，每项均以选项呈现（自由填空字段数 = **0**）；key 类型选项覆盖 官方 + 第三方 = **2/2**；setup 命令可随时重跑修改任一项；预设结果在插件 `update` 后保留率 = **100%**；预设中内置默认 key 数量 = **0**。

## Assumptions

- **平台仅 macOS**：安装者在 macOS 上使用；传输层 daemon 经 macOS LaunchAgent + launchctl 部署。Windows / Linux 本期 out-of-scope。
- 安装者已具备私有 GitLab repo 的访问权与凭据（否则连分发源都拉不到）。
- 安装者自行安装并认证 codex CLI、自备认证 key、并按 README 跑 `install-transport.sh` 部署 daemon；插件只声明前置、不代装、不分享密钥（constitution P5/P6）。
- 分发采用 git-subdir 同仓布局、`plugin.json` 省略 version（SHA 即版本），与 constitution P6 一致。
- 「三条链路」= `/review1` + `/review2` + `/gd` 三个独立命令；`/gd` 的「四阶段」是其内部阶段，不另计为链路。
- 安装者使用的 Claude Code 版本支持 `claude plugin marketplace add` / `install` / `update` 命令族。
