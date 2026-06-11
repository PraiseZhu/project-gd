# Step A: GD 插件面脚手架与 setup 预设 v1

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-step-plan

日期：2026-06-11
状态：draft
负责人：Claude 执行；Codex 可选 cross-review

> 来源：child_planner（track-a-plugin-surface）草稿，由主 agent 持久化。

---

## 1. 目标链（继承 + 当前 task goal）

```text
PROJECT_GOAL: <ref Project GD/docs/gd-v7-project-goal.md §1>
CHAIN_GOAL:   <ref Project GD/docs/gd-v7-project-goal.md §1>
PHASE_GOAL:   把 /review1 /review2 /gd 三命令封装为可分发 macOS 插件（零硬编码路径、bundle 完整、传输栈前置分两段、setup 选项制预设、跨目录冒烟）
TASK_GOAL:    建出 .claude-plugin 脚手架（plugin.json 省略 version + marketplace.json）、安装/前置/更新 README（一行装插件命令与 codex 传输栈前置分两段）、与三链路并列的 setup 命令 + 选项制持久化脚本（4 字段、可重跑、零内置 key），覆盖 SC-001/SC-005/SC-008/SC-009/SC-010
```

---

## 2. Review 对齐

- REVIEW_DOMAIN：`docs_content`（产物以分发脚手架 + README + setup 命令/脚本为主，无链路运行语义改动）
- REVIEW_FOCUS（分号分隔）：单行安装命令可成立且 plugin.json 省略 version；README 两段式（一行装插件 vs codex 传输栈三件套前置）不混淆且不宣称「一条命令即得完整功能」；setup 四字段全选项制零自由填且零内置 key；手动更新命令 ≤3 条 + 传输层改动加 install-transport.sh；零 pip 第三方包
- Domain-specific notes：本 step 只产出「插件面」分发与配置脚手架文件，**不改任何链路运行代码**（gd.md/review1.md/review2.md/vendor/l3-transport 均为只读引用）；setup 预设 4 字段不含 `HANDOFF_ROOT`（由插件管理，属 track-b）；README 必须把「仅 macOS + 私有 GitLab 访问权」列为第 0 步前提。

---

## 3. 前置条件

- blocked_by：`—`（本 step 是插件面起点；track-b 路径解耦/冒烟另立 step，与本 step owned_paths 不重叠）
- 必须的 baseline / artifact：
  - `specs/gd-plugin-packaging/spec.md`（FR/SC 权威）
  - `docs/constitution-plugin.md`（P1–P6）
  - `commands/gd.md` 头部 frontmatter 形态（setup 命令 frontmatter 须与之并列一致，只读）
  - `vendor/l3-transport/README.md`（传输栈三件套背景，写 SC-009 README 前置时引用，只读）
- Hard-stop 条件：若 spec 与 constitution 对「plugin.json 是否省略 version」「setup 字段是否全选项制」出现冲突表述则停止——经核对二者一致（spec FR-018/SC-010 + constitution P6/P5），无 hard-stop。

---

## 4. 成功标准（SC，本 step 内的）

> Anti-fill 规则 A：每条 SC 绑定命令/路径/输出断言之一。

- [ ] SC-001：安装 README 含**单行**安装命令（`claude plugin marketplace add … && claude plugin install …@…`），`plugin.json` **省略** version 字段，且 `plugin.json` **声明三链路命令入口**（review1 / review2 / gd），使安装 reload 后命令可见。
  - verify (method: command): 三段断言全过 →
    1. `python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert 'version' not in d; print('NO_VERSION')"` → `NO_VERSION`
    2. `grep -REq 'claude plugin marketplace add .+&&.+claude plugin install .+@' .claude-plugin/README.md && echo HAS_ONELINE` → `HAS_ONELINE`
    3. `python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); s=json.dumps(d); assert all(c in s for c in ['review1','review2','gd']); print('CMDS_DECLARED')"` → `CMDS_DECLARED`（plugin.json 声明三链路命令入口，作为「命令可见」的可脚本化代理）
  - expect: 三段全过（NO_VERSION + HAS_ONELINE + CMDS_DECLARED）
  - 说明（应对 Codex F1）：「安装者实际能在会话里触发命令」无法在 plan 期脚本断言（需真实 Claude Code reload）；本 SC 在 plan 期验证可脚本化代理（manifest 声明命令入口 + README 单行命令 + 无 version），**端到端命令可见**由 SC-003 跨目录冒烟 + README 明示的一次 reload 步骤覆盖。

- [ ] SC-005：安装 README 明列维护者→安装者的手动更新链 **≤3 条命令**（marketplace update → plugin update → reload），并注明传输层改动时另加 `install-transport.sh`。更新命令块用稳定 marker `<!-- gd-update-commands:start -->` … `<!-- gd-update-commands:end -->` 包裹，verify 统计块内命令数 ≤3。
  - verify (method: command)（应对 Codex F3，把"≤3 条"变成可执行计数而非只查关键词）→
    1. `awk '/<!-- gd-update-commands:start -->/{f=1;next} /<!-- gd-update-commands:end -->/{f=0} f' .claude-plugin/README.md | grep -cE '^\s*(claude|/)' ` → 输出 ≤ `3`（统计 marker 块内以 `claude`/`/` 开头的命令行数）
    2. `f=.claude-plugin/README.md; grep -q 'marketplace update' "$f" && grep -q 'plugin update' "$f" && grep -Eq 'reload|重启|restart' "$f" && grep -q 'install-transport.sh' "$f" && echo PASS` → `PASS`
  - expect: marker 块内命令计数 ≤3 且四要素关键词齐 → `PASS`

- [ ] SC-008：setup 脚本与脚手架声明零 pip 第三方包（脚本仅 bash/stdlib），分发物不含任何 API key/密钥。
  - verify (method: command): `! grep -rEn 'pip install|pip3 install' scripts/gd-plugin-setup.sh commands/setup.md && ! grep -rEn 'sk-[A-Za-z0-9]{16,}' .claude-plugin scripts/gd-plugin-setup.sh commands/setup.md && echo PASS`
  - expect: `PASS`

- [ ] SC-009：安装 README 用**两个固定小节 marker** 把「一行装插件命令」段与「codex 传输栈三件套前置」段**分开且不混淆**：`<!-- gd-install-section -->`（一行装插件段）与 `<!-- gd-transport-prereq-section -->`（传输栈前置段）；三件套（① codex CLI+认证 ② 安装者自备 key 官方/第三方 ③ install-transport.sh 部署 daemon）**只出现在前置段**；并把「仅 macOS + 私有 GitLab 访问权」列为第 0 步前提。
  - verify (method: command)（应对 Codex F4，断言两段都存在 + 三件套只在前置段 + 无虚假完整宣称）→
    1. `f=.claude-plugin/README.md; grep -q '<!-- gd-install-section -->' "$f" && grep -q '<!-- gd-transport-prereq-section -->' "$f" && echo TWO_SECTIONS` → `TWO_SECTIONS`
    2. 三件套只在前置段：`awk '/<!-- gd-transport-prereq-section -->/{f=1} f' .claude-plugin/README.md | grep -q 'codex CLI' && awk '/<!-- gd-transport-prereq-section -->/{f=1} f' .claude-plugin/README.md | grep -q 'install-transport.sh'` 为真，且安装段不含 `install-transport.sh`：`! (awk '/<!-- gd-install-section -->/{f=1} /<!-- gd-transport-prereq-section -->/{f=0} f' .claude-plugin/README.md | grep -q 'install-transport.sh')` 为真
    3. `f=.claude-plugin/README.md; grep -Eq 'macOS' "$f" && grep -Eq 'GitLab' "$f" && grep -Eq '自备.*key|官方.*第三方|第三方.*key' "$f" && ! grep -Eq '一条命令.*完整功能|一行.*即得.*完整' "$f" && echo PASS` → `PASS`
  - expect: 两段 marker 存在 + 三件套仅在前置段 + 第 0 步前提齐 + 无虚假完整宣称

- [ ] SC-010：setup 命令收 4 个字段（审查产物输出位置 / codex key 官方+第三方两类 / codex 模型 / 模型强度 effort），全选项制（零自由填路径/值），持久化到 `${CLAUDE_PLUGIN_DATA}`，可重跑改任一项，零内置默认 key。
  - verify (method: command): `bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FIELDS=4' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FREEFORM=0' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'KEY_TYPES=2' && bash scripts/gd-plugin-setup.sh --self-check | grep -Eq 'PERSIST=.*CLAUDE_PLUGIN_DATA' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'BUILTIN_KEY=0' && echo PASS`
  - expect: `PASS`
  - 备注：`--self-check` 为 setup 脚本必须实现的只读自检子命令（不写文件、不交互），输出上述断言行供 verify 抓取——把「全选项制/可重跑/零内置 key」变成可执行验证，而非目视确认。

---

## 5. 非目标

- 不改 `commands/gd.md` / `commands/review1.md` / `commands/review2.md`（track-b 的路径解耦负责）。
- 不改 `vendor/l3-transport/**`（含 install-transport.sh 内部路径解耦——属 track-b）。
- 不写打包完整性校验脚本、不写跨目录冒烟脚本（track-b owned）。
- 不部署 daemon、不注册 LaunchAgent、不 `launchctl setenv`、不写 `~/.claude/**`。
- setup 只负责采集+持久化预设，不触发链路。

---

## 6. 实现步骤

```text
Step.1
  WHERE: .claude-plugin/plugin.json
  WHAT:  创建 plugin manifest——含 name/description/author/commands 入口声明（指向 bundle 内 commands/），显式省略 version 字段（git SHA 即版本，constitution P6）
  WHY:   SC-001 要求安装者一行命令可装且看到三链路命令；plugin.json 是 /plugin 机制识别命令的根
  VERIFY: python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert 'version' not in d; assert 'name' in d; print('OK')"

Step.2
  WHERE: .claude-plugin/marketplace.json
  WHAT:  创建 marketplace 清单——声明本仓为 git-subdir 同仓布局的 marketplace，列出 gd 插件条目（plugin 名 + source 指向同仓子目录），供 claude plugin marketplace add <repo> 注册
  WHY:   SC-001 单行命令的前半段 marketplace add 依赖此清单；无它安装者注册不了来源
  VERIFY: python3 -m json.tool .claude-plugin/marketplace.json >/dev/null && echo OK

Step.3
  WHERE: 安装 README（落点 .claude-plugin/README.md，理由见 §11 Assumptions）
  WHAT:  写两段式安装文档，**用固定 marker 分段以便可验证**：
         - 【第 0 步前提】仅 macOS + 私有 GitLab 访问权；
         - 【安装段，marker `<!-- gd-install-section -->`】一行装插件命令（marketplace add && plugin install）+ 一次 reload；此段**不得**出现 install-transport.sh；
         - 【传输栈前置段，marker `<!-- gd-transport-prereq-section -->`】codex 传输栈三件套（① codex CLI+认证 ② 安装者自备 key：官方/第三方两类 ③ 跑 vendor/l3-transport/scripts/install-transport.sh 部署 daemon）——三件套**只在本段**出现；
         - 【更新段，marker `<!-- gd-update-commands:start -->` … `<!-- gd-update-commands:end -->`】手动更新 ≤3 条命令（marketplace update → plugin update → reload）+ 传输层改动加 install-transport.sh 的说明（说明文字可在 marker 块外）；
         - 显式声明绝不「一条命令即得三链路完整功能」
  WHY:   SC-009/SC-005 要求「两段不混淆」「≤3 条命令」可被脚本断言（Codex F3/F4）；marker 把不可计数的散文变成可计数结构；constitution P1 范围诚实/P5 外部依赖声明/P6 更新可控全靠此文件落地
  VERIFY: bash -c 'f=.claude-plugin/README.md; grep -q "<!-- gd-install-section -->" "$f" && grep -q "<!-- gd-transport-prereq-section -->" "$f" && grep -q "<!-- gd-update-commands:start -->" "$f" && grep -Eq "claude plugin marketplace add .+&&.+claude plugin install .+@" "$f" && grep -q "codex CLI" "$f" && grep -q "install-transport.sh" "$f" && grep -Eq "macOS" "$f" && grep -Eq "GitLab" "$f" && ! grep -Eq "一条命令.*完整功能" "$f" && echo OK'

Step.4
  WHERE: commands/setup.md
  WHAT:  创建与三链路并列的 setup 命令文件——frontmatter 形态与 commands/gd.md 一致；正文调用 scripts/gd-plugin-setup.sh，向安装者呈现 4 个选项制字段（a 审查产物输出位置 b codex key 官方/第三方两类+值 c codex 模型 d 模型强度 effort），说明可随时重跑改任一项、不进 HANDOFF_ROOT
  WHY:   SC-010 要求 setup 命令存在且与三链路并列；FR-018 要求全选项制、可重跑
  VERIFY: bash -c 'head -3 commands/setup.md | grep -q "^---" && grep -Eq "选项|option" commands/setup.md && grep -q "gd-plugin-setup.sh" commands/setup.md && echo OK'

Step.5
  WHERE: scripts/gd-plugin-setup.sh
  WHAT:  创建 setup 持久化脚本（bash + stdlib，零 pip）——以选项菜单（非自由填）采集 4 字段，key 区分官方/第三方两类选项映射不同 codex provider/base_url/env_key，写入 ${CLAUDE_PLUGIN_DATA}/gd-setup-config.json；幂等可重跑单改任一项；不内置任何默认 key；提供 --self-check 只读子命令输出 FIELDS=4/FREEFORM=0/KEY_TYPES=2/PERSIST=${CLAUDE_PLUGIN_DATA}/.../BUILTIN_KEY=0 供 verify
  WHY:   SC-010 + SC-008 要求选项制/可重跑/零 pip/零内置 key 可被验证；--self-check 把这些断言变成可执行验证
  VERIFY: bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FIELDS=4' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'BUILTIN_KEY=0' && echo OK
```

禁止用「完善/优化/系统性/全面/增强」作为唯一动作描述（本 step 全部步骤动词为「创建/写/调用」具体动作）。

---

## 7. Task Packet 拆分

> 应对 Codex F2：本节为每个 task packet 列全 7 个强制字段（owned_paths / forbidden_paths / required_context / blocked_by / can_parallel_with / deliverables / verify）。每个 packet 的**完整自包含定义见同目录 `task-packets/<task_id>.md`**（含目标链、范围禁令、handoff），本表为派发用摘要，二者字段一致。

### t1 · gd-plugin-scaffold-manifests
- agent_role: implementer ｜ blocked_by: — ｜ can_parallel_with: gd-plugin-install-readme, gd-plugin-setup-command
- owned_paths: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- forbidden_paths: `.claude-plugin/README.md`, `commands/setup.md`, `scripts/gd-plugin-setup.sh`, `commands/gd.md`, `commands/review1.md`, `commands/review2.md`, `vendor/l3-transport/**`, `/Users/praise/.claude/**`
- required_context: `specs/gd-plugin-packaging/spec.md`, `docs/constitution-plugin.md`, `commands/gd.md`
- deliverables: `.claude-plugin/plugin.json`(file, must_exist)、`.claude-plugin/marketplace.json`(file, must_exist)
- verify(SC-001): `python3 -c "import json;d=json.load(open('.claude-plugin/plugin.json'));assert 'version' not in d;assert 'name' in d;print('OK')"` && `python3 -m json.tool .claude-plugin/marketplace.json` → `OK`；verify(SC-008): `! grep -rEn 'sk-[A-Za-z0-9]{16,}' .claude-plugin/plugin.json .claude-plugin/marketplace.json && echo NO_KEY` → `NO_KEY`

### t2 · gd-plugin-install-readme
- agent_role: implementer ｜ blocked_by: — ｜ can_parallel_with: gd-plugin-scaffold-manifests, gd-plugin-setup-command
- owned_paths: `.claude-plugin/README.md`
- forbidden_paths: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `commands/setup.md`, `scripts/gd-plugin-setup.sh`, `commands/gd.md`, `commands/review1.md`, `commands/review2.md`, `vendor/l3-transport/**`, `/Users/praise/.claude/**`
- required_context: `specs/gd-plugin-packaging/spec.md`, `docs/constitution-plugin.md`, `vendor/l3-transport/README.md`
- deliverables: `.claude-plugin/README.md`(file, must_exist)
- verify(SC-009): 见 §4 SC-009 两段 marker 断言；verify(SC-001 README 侧): `grep -Eq 'claude plugin marketplace add .+&&.+claude plugin install .+@' .claude-plugin/README.md && echo PASS`；verify(SC-005): 见 §4 SC-005 marker 块 ≤3 计数断言

### t3 · gd-plugin-setup-command
- agent_role: implementer ｜ blocked_by: — ｜ can_parallel_with: gd-plugin-scaffold-manifests, gd-plugin-install-readme
- owned_paths: `commands/setup.md`, `scripts/gd-plugin-setup.sh`
- forbidden_paths: `.claude-plugin/**`, `commands/gd.md`, `commands/review1.md`, `commands/review2.md`, `vendor/l3-transport/**`, `/Users/praise/.claude/**`
- required_context: `specs/gd-plugin-packaging/spec.md`, `docs/constitution-plugin.md`, `commands/gd.md`
- deliverables: `commands/setup.md`(file, must_exist)、`scripts/gd-plugin-setup.sh`(file, must_exist)
- verify(SC-010): `head -3 commands/setup.md | grep -q '^---' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FIELDS=4' && … | grep -q 'FREEFORM=0' && … | grep -q 'KEY_TYPES=2' && … | grep -Eq 'PERSIST=.*CLAUDE_PLUGIN_DATA' && … | grep -q 'BUILTIN_KEY=0' && echo PASS`；verify(SC-008): `! grep -rEn 'pip install|pip3 install' scripts/gd-plugin-setup.sh commands/setup.md && echo PASS`

> 三个 packet owned_paths 互不重叠，可并行。受全局 `max_parallel=2` 硬上限，执行阶段最多同时跑 2 个，第 3 个排队。完整 packet 文件：`task-packets/gd-plugin-scaffold-manifests.md`、`task-packets/gd-plugin-install-readme.md`、`task-packets/gd-plugin-setup-command.md`。

---

## 8. 边界（修改 / 不修改）

修改（本 step owned，具体文件）：
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.claude-plugin/README.md`
- `commands/setup.md`
- `scripts/gd-plugin-setup.sh`

不修改（只读引用）：
- `commands/gd.md` / `commands/review1.md` / `commands/review2.md`（track-b）
- `vendor/l3-transport/**`（含 install-transport.sh，track-b）
- 打包完整性校验脚本 / 跨目录冒烟脚本（track-b）
- 旧 `/rev` 任何 artifact
- `/Users/praise/.claude/**`

---

## 9. 风险与防护

| 风险 | 防护 |
|------|------|
| `${CLAUDE_PLUGIN_DATA}` 在 setup 运行环境未注入 → 预设无处落盘 | setup 脚本对未设变量 fail-closed 给中文提示，不静默写 `~`；`--self-check` 不依赖该变量已设值（只校验脚本目标路径模板含 `${CLAUDE_PLUGIN_DATA}`） |
| README 把传输栈前置混进「一行命令」叙述 → SC-009 失败、信任崩塌 | SC-009 verify 显式断言无「一条命令即完整功能」措辞 + 三件套全列 |
| setup 出现自由填字段 → SC-010 FREEFORM≠0 | 脚本只用选项菜单 + `--self-check` 报 FREEFORM=0；review 据此抓取 |
| 误把 `HANDOFF_ROOT` 写进 setup 预设 → 与 track-b 冲突、断链 | 4 字段白名单固定为 a/b/c/d，setup.md 与脚本均显式注明 HANDOFF_ROOT 由插件管理、不进预设 |
| plugin.json 误带 version → 违反 P6 | SC-001 verify 断言 `'version' not in d` |
| 脚本引入 pip 依赖 → SC-008 失败 | 纯 bash + python3 stdlib；SC-008 verify grep 无 `pip install` |

---

## 10. 测试计划

```bash
# SC-001：单行安装命令 + plugin.json 无 version
python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert 'version' not in d; print('NO_VERSION')"
grep -Eq 'claude plugin marketplace add .+&&.+claude plugin install .+@' .claude-plugin/README.md && echo HAS_ONELINE

# SC-005：手动更新链 ≤3 条 + 传输层补丁
grep -q 'marketplace update' .claude-plugin/README.md && grep -q 'plugin update' .claude-plugin/README.md && grep -Eq 'reload|重启|restart' .claude-plugin/README.md && grep -q 'install-transport.sh' .claude-plugin/README.md && echo UPDATE_OK

# SC-008：零 pip + 零明文 key
! grep -rEn 'pip install|pip3 install' scripts/gd-plugin-setup.sh commands/setup.md && echo NO_PIP
! grep -rEn 'sk-[A-Za-z0-9]{16,}' .claude-plugin scripts/gd-plugin-setup.sh commands/setup.md && echo NO_KEY

# SC-009：两段式前置 + 第 0 步前提 + 无虚假完整宣称
bash -c 'f=.claude-plugin/README.md; grep -q "codex CLI" "$f" && grep -q "install-transport.sh" "$f" && grep -Eq "macOS" "$f" && grep -Eq "GitLab" "$f" && ! grep -Eq "一条命令.*完整功能" "$f" && echo TRANSPORT_OK'

# SC-010：setup 四字段全选项制可重跑零内置 key
bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FIELDS=4' && echo SETUP_FIELDS_OK
bash scripts/gd-plugin-setup.sh --self-check | grep -q 'FREEFORM=0' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'KEY_TYPES=2' && bash scripts/gd-plugin-setup.sh --self-check | grep -q 'BUILTIN_KEY=0' && echo SETUP_OPTIONS_OK

# JSON 结构合法
python3 -m json.tool .claude-plugin/plugin.json >/dev/null && python3 -m json.tool .claude-plugin/marketplace.json >/dev/null && echo JSON_OK
```

---

## 11. Assumptions

- 安装 README 落点 = `.claude-plugin/README.md`（不选 `docs/INSTALL.md`）。理由：README 是分发包面向安装者的第一入口，与 plugin.json/marketplace.json 同处 `.claude-plugin/` 便于安装者「打开插件目录即见安装说明」；constitution P3 的 bundle 完整性范围已含 `docs/`，把安装说明放 `.claude-plugin/` 可避免与 `docs/` 内项目级文档混淆。SC verify 用 `.claude-plugin/README.md`。
- setup 命令 frontmatter 仅含 `description:`（与 `commands/gd.md` 实测一致，无 `name`/`allowed-tools` 字段）。
- `${CLAUDE_PLUGIN_DATA}` 是 Claude Code 插件机制提供的更新安全数据目录，跨 `/plugin update` 保留（constitution P4 + spec FR-018 已锁此前提）。
- setup 的 codex key「官方/第三方两类选项」分别映射 codex 配置的 provider/base_url/env_key（spec FR-018b）；本 step 只采集+持久化，daemon 侧 key 注入由安装者按 README 跑 install-transport.sh 完成（track-b/前置范畴）。
- 三链路命令文件（review1/review2/gd）已存在于 bundle 内，本 step 不创建也不改它们，只在 marketplace/plugin 清单中声明命令入口由 `/plugin` 机制接管（不写 `~/.claude/commands/`）。
- `HANDOFF_ROOT` 不进 setup 预设（spec FR-016/FR-018 + track-b 边界）。
