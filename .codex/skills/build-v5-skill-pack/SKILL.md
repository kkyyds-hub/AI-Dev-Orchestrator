---
name: build-v5-skill-pack
description: 将 AI-Dev-Orchestrator V5 的 skill-pack 体检、修复、补强、正式化包装与联动治理收敛成中文维护型 skill。用于当主任务是维护 `.codex/skills/` 里的 V5 skills 本身，而不是直接推进 `apps/web`、`runtime/orchestrator`、冻结文档或运行验证时，持续修复乱码、结构缺口、边界混乱、路由失真与配套缺失，让后续线程能稳定调用正确的 owner skill。
---

# build-v5-skill-pack

## 使命与 owner

把 V5 的 skill 体系本身，从“能看懂一点的草案集合”，持续推进成 **正式可用、边界清楚、配套完整、可直接接力** 的 `.codex/skills/` 技能库。

这个 skill 的 owner 职责只有一个：

> **负责维护 V5 skill pack 本身的质量、边界、包装与协作契约，不替兄弟 skill 直接做业务交付。**

它重点负责：

- 对一个 V5 skill 或一个紧密相关的 skill-pack 切片做体检、修复、补强
- 修复 `SKILL.md`、`agents/openai.yaml`、`references/*`、`playbooks/*`、`templates/*` 的可读性、完整性与一致性
- 把“桌面草案 / 半成品 skill / 乱码文件 / 失真 prompt”转成正式可调用的 owner skill 包
- 收口 skill 与 skill 之间的路由、边界、协作链与交接契约
- 明确什么时候应该先调用 `build-v5-skill-pack`，什么时候必须让位给真正的业务 owner skill
- 让后续线程拿到的是可直接调用的 skill，而不是还要二次解释的技能草稿

它不应该把线程带偏成：

- 借“修 skill”之名直接改 `apps/web`、`runtime/orchestrator`、冻结文档或验证脚本
- 把 skill 维护线程偷换成业务实现线程、验证线程或验收线程
- 一次性扩写大量空 skeleton，制造看起来很全但无法执行的 skill 包
- 把抽象能力词硬写成 workflow owner，导致与兄弟 skills 抢 owner
- 在本轮范围未授权时，静默改写多个兄弟 skill 本体
- 把维护结果写成架构宣言，而不是落到可调用的正式 skill 文件

## 先判 owner：本 skill 与 4 个关键兄弟 skill 怎么分工

### `write-v5-web-control-surface`

它负责：**把 V5 前端控制面真实落到 `apps/web`。**

本 skill 只在下面情况先介入：

- `write-v5-web-control-surface` 本身写得不可读、边界失真、触发条件不清
- 前端线程连续出现“到底该写页面还是先治理结构”的路由混乱
- `write-v5-web-control-surface` 缺少必要 references / prompt / handoff 配套

本 skill 绝不替它做：

- 控制面页面、hooks、types、api、组件、交互实现
- 前端字段对齐、状态反馈、页面联调与构建处理

### `govern-v5-web-structure`

它负责：**治理 `apps/web` 的结构失控、大文件瘦身、页面 owner 收口与稳定测试锚点。**

本 skill 只在下面情况先介入：

- `govern-v5-web-structure` 自己的 owner 边界、入口页纪律、与控制面 skill 的分界不够硬
- 前端线程连续把“结构治理”误路由到“功能实现”，或反过来
- 结构治理 skill 的参考规则、路由语句、默认 prompt 已经失真

本 skill 绝不替它做：

- `App.tsx` / `ProjectOverviewPage.tsx` 的实际瘦身拆分
- `data-testid` 落地、结构减债实施、前端文件改造

### `drive-v5-orchestrator-delivery`

它负责：**把跨 backend / web / docs / verify 的 V5 工作包推进到整链可交付。**

本 skill 只在下面情况先介入：

- 总控 skill 的触发条件过宽、过空，已经开始抢单一 owner skill 的活
- 跨层路由描述失真，导致线程不知道何时该升级为总控、何时该降级回单一 owner
- 总控 skill 的 handoff / evidence / routing 包装不足，无法稳定支撑后续线程

本 skill 绝不替它做：

- 实际编排 backend + web + docs + verify 的跨层交付
- 在一个工作包里直接代做业务实现、验证与状态回填

### `verify-v5-runtime-and-regression`

它负责：**确认运行事实、构建事实、页面事实与最小回归事实。**

本 skill 只在下面情况先介入：

- verify skill 本身不可读、证据分级不清、验证入口和非目标范围写得太虚
- 线程不断把“需要查事实”误路由成“继续写实现”
- verify skill 缺少最小可执行的证据包装与交接模板

本 skill 绝不替它做：

- 实际运行构建、页面冒烟、API 验证、日志核对
- 根据运行结果下验证结论

### 一句话路由原则

- **主问题是修 skill 本身** → 先用本 skill
- **主问题是做前端控制面** → `write-v5-web-control-surface`
- **主问题是治前端结构** → `govern-v5-web-structure`
- **主问题是跨层交付** → `drive-v5-orchestrator-delivery`
- **主问题是查运行事实 / 回归事实** → `verify-v5-runtime-and-regression`

如果线程一开始连“该叫哪个 owner”都说不清，而且问题根源在 skill 描述失真、边界混乱、配套缺失，就应该先调用 `build-v5-skill-pack` 把 skill 本身修好，再进入业务线程。

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 当前已正式落地的 `.codex/skills/*/SKILL.md`
4. 本次要维护的目标 skill 正式目录：
   - `SKILL.md`
   - `agents/openai.yaml`
   - `references/*`
   - `playbooks/*`
   - `templates/*`
5. 与目标 skill 最容易发生路由冲突的兄弟 skill，尤其是：
   - `.codex/skills/write-v5-web-control-surface/SKILL.md`
   - `.codex/skills/govern-v5-web-structure/SKILL.md`
   - `.codex/skills/drive-v5-orchestrator-delivery/SKILL.md`
   - `.codex/skills/verify-v5-runtime-and-regression/SKILL.md`
6. `C:\Users\Administrator\.codex\skills\.system\skill-creator\SKILL.md`
7. 本 skill 自带 references / playbook / template
8. 仅为核对真实目录、文件名与现状而最小读取的仓库代码或文档文件

如果这些输入之间冲突，**以 V5 母本 + 当前正式 skill 库事实 + 仓库真实目录结构为准**，不要让桌面草案、旧 prompt 或想当然的能力词覆盖正式 owner 边界。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许退化成“泛化写 skill 教程”。

默认优先维护下列内容：

- V5 workflow owner 型 skills
- V5 skill 之间的路由与协作链
- 与 V5 Phase / 工作包 / verify / accept 直接相关的 references、playbook 与 handoff 模板
- 已正式落地但仍存在乱码、失真、缺章、包装残缺的 skill 包

默认不优先：

- 与 V5 无关的通用 skill 扩写
- 只谈能力分类、不形成 owner 边界的抽象材料
- 不准备正式落到 `.codex/skills/` 的临时头脑风暴
- 与当前任务无关的大范围技能库重命名或风格翻修

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- “这个 V5 skill 本身写坏了 / 乱码了 / 不可直接调用，先修它”
- “这个 skill 不再只是会写文档，需要能做体检、修复、补强、联动治理”
- “某个 skill 的 owner、边界、开始入口、工作流、交接规则不够清楚”
- “`SKILL.md`、agent metadata、references、playbook、template 之间已经脱节”
- “兄弟 skill 之间开始互相抢 owner，需要先收口 skill 路由”
- “我要把桌面草案或半成品 pack 转成正式可复用的 skill 包”
- “在继续修别的 skill 之前，我怀疑那个 skill 本身已经不足以稳定带路”

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是改 `apps/web` 控制面：转 `write-v5-web-control-surface`
- 主要目标是治理 `apps/web` 结构：转 `govern-v5-web-structure`
- 主要目标是跨 backend / web / docs / verify 推工作包：转 `drive-v5-orchestrator-delivery`
- 主要目标是验证运行事实、build、API、页面、回归：转 `verify-v5-runtime-and-regression`
- 主要目标是冻结文档、状态回填、执行计划治理：转 `manage-v5-plan-and-freeze-docs`
- 主要目标是代码/口径风险审查：转 `review-v5-code-and-risk`
- 主要目标是阶段通过/部分通过/阻塞裁定：转 `accept-v5-milestone-gate`

一句话：**本 skill 管的是“skill 是否健康可用”，不是“业务工作包是否已经交付”。**

## 正式落盘边界

### 本 skill 的主要输出目录

- `.codex/skills/<skill-name>/SKILL.md`
- `.codex/skills/<skill-name>/agents/openai.yaml`
- `.codex/skills/<skill-name>/references/*`
- `.codex/skills/<skill-name>/playbooks/*`
- `.codex/skills/<skill-name>/templates/*`

### 默认可改动的面

- 本次被明确纳入维护范围的 skill-pack 配套文件
- 与目标 skill 直接相关、且属于正式 skill 包包装层的文件
- 用于澄清边界、路由、体检、交接的最小参考文件

### 默认不越权的面

- `apps/web/` 里的业务功能与结构代码
- `runtime/orchestrator/` 里的实现、接口、worker 与脚本
- `docs/01-版本冻结计划/` 里的正式冻结文档内容
- 验证线程的真实运行命令与结论
- 未被当前范围授权的其他兄弟 skill 本体

### 本轮维护纪律

如果本轮目标只是修复某个 skill-pack 自身，就只修这个 pack；不要顺手把其它 owner skill 也改掉。需要联动治理时，优先通过：

- 本 skill 自身的 routing 规则
- 本 skill references 的协作矩阵
- 本 skill playbook / template 的接棒规范

来把边界讲清，而不是跨出本轮范围到处改文件。

## 开始入口

每次接手 V5 skill-pack 维护任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 suite map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/skill-pack-governance-rules.md`
   - `references/workflow-owner-shaping-checklist.md`
   - `references/formalization-packaging-rules.md`
   - `references/skill-pack-maintenance-checklist.md`
   - `references/skill-pack-routing-matrix.md`
4. 打开本 skill 的 playbook 与模板：
   - `playbooks/skill-formalization-playbook.md`
   - `templates/skill-formalization-handoff-template.md`
5. 打开 1~2 个最相关的正式兄弟 skill，优先读取：
   - `.codex/skills/write-v5-web-control-surface/SKILL.md`
   - `.codex/skills/govern-v5-web-structure/SKILL.md`
   - `.codex/skills/drive-v5-orchestrator-delivery/SKILL.md`
   - `.codex/skills/verify-v5-runtime-and-regression/SKILL.md`
6. 再打开本次要维护的目标 skill 或目标配套文件
7. 只有在需要核对真实目录、真实入口名时，才最小读取仓库业务代码或文档

### 最小必读正式 skills

- `.codex/skills/build-v5-skill-pack/SKILL.md`
- `.codex/skills/write-v5-web-control-surface/SKILL.md`
- `.codex/skills/govern-v5-web-structure/SKILL.md`
- `.codex/skills/drive-v5-orchestrator-delivery/SKILL.md`
- `.codex/skills/verify-v5-runtime-and-regression/SKILL.md`

### 按维护类型补读

#### 体检 / 修复

补读：

- 当前损坏或失真的正式 skill 文件
- `references/skill-pack-maintenance-checklist.md`
- `references/formalization-packaging-rules.md`

重点回答：

- 是否有乱码、缺章、语义断裂、包装缺失
- 是否还能直接指导下一线程

#### 补强 / 正式化

补读：

- 对应桌面草案或半成品材料
- `references/workflow-owner-shaping-checklist.md`
- `playbooks/skill-formalization-playbook.md`

重点回答：

- 是否已经形成真正的 workflow owner
- 是否已经有最小可用的 references / playbook / template 配套

#### 联动治理 / 路由收口

补读：

- 与目标 skill 最易冲突的 1~2 个兄弟 skill
- `references/skill-pack-routing-matrix.md`
- `references/skill-pack-governance-rules.md`

重点回答：

- 当前主问题到底属于哪个 owner
- 是应该先修 skill 本身，还是应该直接转去业务 skill

## 如何处理模糊请求

遇到“继续补 V5 skills”“把这个 skill 修成可用”“先把技能库整理一下”“我怀疑现在 skill 会把线程带歪”这类模糊请求时：

1. 先判定这次属于：**体检**、**修复**、**补强**、**正式化**、还是 **联动治理**。
2. 默认一次只处理一个 skill，或一个紧密相关的配套切片。
3. 明确说出本轮维护对象、损坏点、目标状态与正式落点。
4. 如果问题其实不在 skill-pack，而在业务交付本身，就立即转给正确的兄弟 skill，不要继续留在本 skill。
5. 如果只是因为 skill 文本失真导致 owner 路由错误，应先修 skill，再进入业务线程。

## 核心工作流

### 1. 先判断这是“skill 自身损坏”还是“业务 owner 选错了”

先回答：

- 当前主问题是文件不可读、边界不清、prompt 失真、包装缺失吗？
- 还是其实已经明确属于前端控制面、前端结构治理、跨层交付、运行验证？
- 如果不修 skill 本身，下一线程是否会继续被错误 owner 带偏？

如果根因在 skill 自身，就先修 pack；如果根因已是业务任务，就立即切 owner。

### 2. 先做体检，再决定修复力度

至少按下面维度快速体检：

- 可读性：是否乱码、断句坏掉、语义缺失
- owner：是否说得清“它负责什么 / 不负责什么”
- 路由：是否说得清与兄弟 skill 的边界和切换条件
- 工作流：是否写出开始入口、标准步骤、交接规则
- 包装：`SKILL.md`、`agents/openai.yaml`、`references/*`、`playbooks/*`、`templates/*` 是否同步
- 可接力性：新线程能否拿着这个 skill 直接开工

不要一上来就大改；先知道问题属于“坏文件”“缺规则”还是“边界失真”。

### 3. 把抽象能力改写成真正的 workflow owner

每次修 skill 都要追问：

- 它到底管哪类线程，而不是只会描述一个能力主题
- 它的上游输入、下游交接和默认产物是什么
- 它与最容易冲突的兄弟 skill 怎么分界
- 线程结束时它应该留下什么，才算对后续线程真的有帮助

如果这些问题答不出来，就还不算正式 owner skill。

### 4. 同步修 packaging，而不是只修正文

正式 skill 的最低要求不是“有一份 `SKILL.md`”，而是：

- `SKILL.md` 可读、可路由、可接力
- `agents/openai.yaml` 能准确触发 owner 行为
- `references/*` 真能辅助判断边界、工作流与交接
- `playbooks/*` 和 `templates/*` 能支持重复维护任务

任何一层长期失真，都会让 skill 看起来存在、实际上不好用。

### 5. 通过 references 做联动治理，但不越权接管兄弟 skill

当本轮目标是澄清与其他 skill 的边界时，优先：

- 在本 skill 的 references 里写清路由矩阵
- 在本 skill 的 `SKILL.md` 里写清“什么时候先调本 skill”
- 在本 skill 的 playbook / template 里固化接棒规则

除非本轮范围明确授权，否则不要顺手去重写兄弟 skill 本体。

### 6. 让输出可直接复用到下一线程

每次维护结束时，至少要留下：

- 本轮维护对象与类型
- 修复了哪些损坏点、补强了哪些规则
- 与哪些兄弟 skill 的分工更清楚了
- 下一线程什么时候应该先调用 `build-v5-skill-pack`
- 如果不需要再调本 skill，接下来应该转给哪个 owner

## 与兄弟 skill 的协作契约

- 本 skill 负责：**skill-pack 体检、修复、补强、正式化包装、联动治理**
- `write-v5-web-control-surface` 负责：**前端控制面真实落地**
- `govern-v5-web-structure` 负责：**前端结构治理与稳定锚点**
- `drive-v5-orchestrator-delivery` 负责：**跨层工作包整链推进**
- `verify-v5-runtime-and-regression` 负责：**运行事实与回归事实确认**
- `manage-v5-plan-and-freeze-docs` 负责：**V5 文档冻结与状态回填治理**
- `review-v5-code-and-risk` 负责：**实现质量与风险审查**
- `accept-v5-milestone-gate` 负责：**阶段裁定**

本 skill 不替这些 owner 做业务交付；它只负责让这些 owner skills 本身更清楚、更完整、更能接棒。

## 推荐输出骨架

优先使用下面骨架汇报本轮 skill-pack 维护：

```md
# 本次 V5 skill-pack 维护

## 维护对象
- skill 名称：
- 维护类型：体检 / 修复 / 补强 / 正式化 / 联动治理
- 本轮范围：

## 诊断
- 发现的损坏点：
- 发现的边界/路由问题：
- 为什么这轮应该先调用 `build-v5-skill-pack`：

## 改动结果
- 修改文件：
- 每个文件补了什么：
- 与哪些兄弟 skill 的分工更清楚了：

## 后续调用建议
- 之后哪些情况应先调 `build-v5-skill-pack`：
- 如果继续推进业务，应切到哪个 owner skill：

## 风险与遗留
- 仍未覆盖的范围：
- 下一线程建议：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 只说“应该怎么维护 skill”，却没有落到正式文件
- 只修 `SKILL.md`，不修已明显失真的 agent / references / playbook / template
- 仍然让人看不清它与 4 个关键兄弟 skill 的边界
- 仍然无法回答“什么时候应该先调用 `build-v5-skill-pack`”
- 借修 skill 之名越权改了业务目录
- 一次性摊大很多 skill，却没有把任何一个维护到可直接调用

## 红线

1. 不要把 skill 维护线程写回抽象方法论文档。
2. 不要把能力主题词硬当成 workflow owner。
3. 不要脱离 V5 母本和现有正式 skill 库乱扩技能体系。
4. 不要把本 skill 用成业务代码施工入口。
5. 不要在未授权时改写其他兄弟 skill 本体。
6. 不要保留乱码、问号占位、断裂语义或无法接力的配套文件。

## Done checklist

- 已明确本轮维护对象是哪个 skill 或哪个 skill-pack 切片。
- 已明确本轮属于体检 / 修复 / 补强 / 正式化 / 联动治理中的哪一种。
- 已修复可读性问题：无乱码、无问号占位、语义完整。
- 已写清 owner、边界、开始入口、工作流、交接规则与 done checklist。
- 已写清与 `write-v5-web-control-surface`、`govern-v5-web-structure`、`drive-v5-orchestrator-delivery`、`verify-v5-runtime-and-regression` 的分工。
- 已说明什么时候应该先调用 `build-v5-skill-pack`。
- 已同步修好 `SKILL.md`、`agents/openai.yaml`、最小必要 `references/*`、相关 `playbooks/*`、相关 `templates/*`。
- 已保持改动只落在 skill-pack 范围，没有越权改业务目录。
- 已让后续线程可以直接调用本 skill 接手同类维护任务。

## References

- `references/skill-pack-governance-rules.md`
- `references/workflow-owner-shaping-checklist.md`
- `references/formalization-packaging-rules.md`
- `references/skill-pack-maintenance-checklist.md`
- `references/skill-pack-routing-matrix.md`
- `playbooks/skill-formalization-playbook.md`
- `templates/skill-formalization-handoff-template.md`