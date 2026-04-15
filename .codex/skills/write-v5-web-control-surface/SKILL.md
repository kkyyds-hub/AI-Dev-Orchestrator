---
name: write-v5-web-control-surface
description: 将 AI-Dev-Orchestrator V5 母本中的前端控制面工作包真正落到 `apps/web` 的中文实现型 skill。它负责把项目总览、角色策略、技能绑定、团队控制、记忆治理、成本可视化、运行观测等能力做成真实控制面，同时在落地过程中主动防止前端结构继续长歪；一旦主问题转为结构治理，必须让位给 `govern-v5-web-structure`。
---

# write-v5-web-control-surface

## 使命与 owner

把 `AI-Dev-Orchestrator-V5-Plan.md` 里的 V5 Web 控制面能力，收敛成 **看得见、改得动、状态真实、口径一致、可交接验证** 的 `apps/web` 改动。

这个 skill 的 owner 职责只有一个：

> **对 V5 前端控制面切片的真实落地负责，并在落地过程中守住结构边界；但它不是前端结构治理 owner。**

这句话要同时满足两层意思：

1. 本 skill 不能只会“做功能页”，必须主动防止前端继续被硬塞、乱挂、乱起 feature。
2. 但当主问题已经变成“该怎么瘦身、怎么拆分、怎么守住入口页 owner、怎么补稳定测试锚点”时，owner 必须切回 `govern-v5-web-structure`。

它重点负责：

- 把后端能力转成老板和操作者可用的控制面
- 把 V5 的 team / role / policy / memory / skill / cost / run 等能力变成真实前端入口
- 保证页面文案、状态、字段与后端及 V5 母本口径一致
- 补齐 loading / empty / error / disabled / submit feedback / success feedback
- 在实现前先判断控制面应该挂到哪个现有 feature，避免把页面继续写歪
- 给兄弟 skill 留下清晰的验证、联动与文档回填入口

它不应该把线程带偏成：

- 只做页面好看但没有真实交互入口
- 用静态假数据冒充“功能已接入”
- 去接管后端 service / route / schema 落地
- 去写冻结文档或宣布阶段已通过
- 明知入口页已经失控，仍继续把大块控制面硬塞进去
- 把本应由 `govern-v5-web-structure` 决定的结构治理问题抢成自己的 owner

## 先判 owner：本 skill 与 `govern-v5-web-structure` 怎么分工

### 本 skill 该接的主问题

当主问题是下面这些时，使用本 skill：

- 新增或补完一个真实的 V5 前端控制面切片
- 给既有控制面补字段对齐、交互动作、状态反馈、最小验证
- 为 `projects / roles / strategy / skills / budget / console / console-metrics / run-log` 增加真实控制入口
- 让已有观察页变成可操作、可反馈、可交接的控制面

一句话：**本 skill 负责“把控制能力做出来”。**

### 必须让位给 `govern-v5-web-structure` 的主问题

当主问题是下面这些时，不要继续留在本 skill：

- 要先判断代码该落在哪个 section / hook / component / feature，结构 owner 还没收口
- `App.tsx` / `ProjectOverviewPage.tsx` 已经过胖，需要先瘦身或抽区块
- 这次主要工作其实是拆 section、下沉 hooks / types / api / lib，而不是新增控制能力
- 这次主要工作是补 `data-testid`、稳住 smoke / 浏览器证据脚本、减少对中文文案的耦合
- 需要判断“这是结构减债还是整站翻修”
- 为了接这个控制面，现有 feature 明显装不下，但新 feature 的 owner 归属仍不清楚

一句话：**`govern-v5-web-structure` 负责“把前端别再写歪”。**

### 两个 skill 同时出现时的顺序

如果一个线程同时出现“要落控制面”和“结构已经失控”两类信号，默认按下面顺序处理：

1. 先由 `govern-v5-web-structure` 收口结构边界、拆分策略和落位规则
2. 再由本 skill 在已经收口的 feature / section / hook 边界内交付控制面切片

不要两个 skill 抢同一个 owner 决策；尤其不要一边声称自己在做控制面，一边偷偷接管结构治理。

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
4. `C:\Users\Administrator\Desktop\ai-skills草案\write-v5-web-control-surface-skill-草案.md`
5. `references/web-control-surface-map.md`
6. `references/control-state-and-contract-checklist.md`
7. `references/boss-control-surface-routing.md`
8. `references/control-surface-structure-routing.md`
9. **当出现结构风险信号时，补读** `../govern-v5-web-structure/SKILL.md`
10. **当出现结构风险信号时，补读** `../govern-v5-web-structure/references/page-owner-boundaries.md`
11. **当出现结构风险信号时，补读** `../govern-v5-web-structure/references/large-file-slimming-rules.md`
12. 为核对真实现状而最小读取的仓库代码文件

如果这些输入之间冲突，**以 V5 母本 + 仓库真实前端代码现状 + 已经存在的结构治理规则为准**，不要让桌面草案覆盖仓库事实，也不要让“先把功能做出来再说”覆盖结构边界。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许脱离主背景自由发挥。

默认优先按下面方式理解 V5 前端控制面的阶段重点：

### Phase 1 相关的前端增强

- `Role model policy v1` 的展示与编辑面
- Provider / token / prompt 相关的最小观察入口
- 与 `project memory recall` 接入后相匹配的上下文 / 记忆可见性

### Phase 2 相关的前端增强

- thread checkpoint 时间线
- memory governance 面板
- rolling summary / rehydrate / bad context detection 的观察与动作入口

### Phase 3 相关的前端增强

- agent session / message / review-rework 的线程页
- boss intervention 的前端入口

### Phase 4 相关的前端增强

- team assembly
- team control center
- cost dashboard
- prompt / response cache 命中与治理入口

如果任务明显跨到后续阶段，也要先说明：

- 当前属于哪一阶段
- 为什么现在可以推进这个控制面
- 依赖的后端能力是否已经存在，还是需要并行交接

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- 把 `apps/web` 的项目总览、角色页、策略页、技能页做成 V5 控制面
- 为 team assembly / team control center / role model policy 增加前端入口
- 为 prompt registry / memory governance / cost dashboard 增加页面、面板或抽屉
- 为 run logs / token usage / recall evidence / checkpoint timeline 增加观察视图与控制动作
- 为老板端配置、筛选、干预团队增加交互与状态反馈
- 对某个 V5 前端工作包做增量实现、字段对齐和最小验证

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是前端结构治理、大文件瘦身、页面 owner 收口、锚点规范：转 `govern-v5-web-structure`
- 主要目标是改后端 service / worker / route / schema：转 `write-v5-runtime-backend`
- 主要目标是拆规划、冻结文档、回填状态：转 `manage-v5-plan-and-freeze-docs`
- 主要目标是跨 backend / web / docs / verify 一起推进：转 `drive-v5-orchestrator-delivery`
- 主要目标是查页面能否打开、构建是否通过、联调是否成功：转 `verify-v5-runtime-and-regression`
- 主要目标是审查字段契约、口径风险、实现偏差：转 `review-v5-code-and-risk`
- 主要目标是宣布阶段通过、部分通过或阻塞：转 `accept-v5-milestone-gate`

## 正式落盘边界

### 本 skill 的主要输出目录

- `apps/web/src/features/`
- `apps/web/src/components/`
- `apps/web/src/lib/`
- `apps/web/package.json`

### 默认可改动的前端面

- `src/features/projects/`
- `src/features/roles/`
- `src/features/strategy/`
- `src/features/skills/`
- `src/features/budget/`
- `src/features/console/`
- `src/features/console-metrics/`
- `src/features/run-log/`
- 新增 feature 目录（仅在现有结构明显装不下且 owner 明确时）

### 对聚合页的硬纪律

- `App.tsx` 与 `ProjectOverviewPage.tsx` 只允许做**最小入口挂载、上下文协调、事件转发**
- 如果一个控制面切片需要在这些聚合页里新增完整区块、大量 JSX、复杂字段映射、复杂状态逻辑，先停下并转 `govern-v5-web-structure`
- 如果为了接这个控制面，必须先抽 `sections/`、下沉 `hooks.ts / types.ts / api.ts / lib`、补稳定测试锚点，先转 `govern-v5-web-structure`

### 默认不越权的面

- `runtime/orchestrator/`：后端 owner 面，接口或字段缺口交给 `write-v5-runtime-backend`
- `docs/01-版本冻结计划/`：文档 owner 面，状态回填交给 `manage-v5-plan-and-freeze-docs`
- `App.tsx` / `ProjectOverviewPage.tsx` 的结构瘦身、拆分策略、测试锚点规则：交给 `govern-v5-web-structure`
- 阶段裁定与 pass/block 结论：交给 `accept-v5-milestone-gate`

## 开始入口

每次接手 V5 前端控制面任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/web-control-surface-map.md`
   - `references/control-state-and-contract-checklist.md`
   - `references/boss-control-surface-routing.md`
   - `references/control-surface-structure-routing.md`
4. 打开 `apps/web/package.json`，确认当前前端栈与构建命令
5. 按任务类型只打开最相关的 feature 文件
6. **如果出现结构风险信号，再补读**：
   - `../govern-v5-web-structure/SKILL.md`
   - `../govern-v5-web-structure/references/page-owner-boundaries.md`
   - `../govern-v5-web-structure/references/large-file-slimming-rules.md`

### 最小必读代码入口

- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- `apps/web/src/features/roles/RoleCatalogPage.tsx`
- `apps/web/src/features/roles/RoleEditorDrawer.tsx`
- `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
- `apps/web/src/features/strategy/StrategyRuleEditor.tsx`
- `apps/web/src/features/skills/SkillRegistryPage.tsx`
- `apps/web/src/features/skills/RoleSkillBindingPanel.tsx`
- `apps/web/src/lib/http.ts`

### 按工作包补读

#### 团队 / 角色 / 老板控制类

- `src/features/projects/ProjectOverviewPage.tsx`
- `src/features/roles/*`
- `src/features/strategy/*`
- 相关 `hooks.ts` / `types.ts` / `api.ts`

#### skill / prompt / registry 类

- `src/features/skills/*`
- 相关 `hooks.ts` / `types.ts` / `api.ts`

#### memory / checkpoint / evidence 类

- `src/features/projects/ProjectMemoryPanel.tsx`
- `src/features/projects/MemorySearchPanel.tsx`
- `src/features/run-log/*`
- `src/features/console*/*`

#### budget / cost / observability 类

- `src/features/budget/*`
- `src/features/console-metrics/*`
- `src/features/projects/ProjectOverviewPage.tsx`

## 如何处理模糊请求

遇到“继续做 V5 控制台”“把老板控制面补上”“把前端这一块做出来”这类模糊请求时：

1. 先把请求翻译成 **一个工作包 + 一个控制面切片**。
2. 先判断主问题是“控制面交付”还是“结构治理”。
3. 默认优先选择已存在 feature 里的最小安全扩展。
4. 明确说出你选择的页面 / 面板 / feature 和原因。
5. 如果主要阻塞其实是结构 owner 不清、聚合页过胖、需要先拆 section / hooks / anchors，就立刻让位给 `govern-v5-web-structure`。
6. 如果主要阻塞是后端合同不存在，要立刻说明并交接，不要拿静态假数据硬撑完成。

例如：

- “继续做老板控制” → 先落 `ProjectOverviewPage / roles / strategy` 上的团队控制入口
- “把 token / cost 做到前端” → 先落 `budget / console-metrics / project overview` 的观察与拆账入口
- “把记忆治理做起来” → 先落 `projects` 下的 memory 面板与 recall evidence
- “这块别再堆进 ProjectOverviewPage 了，但功能还得继续做” → 先转 `govern-v5-web-structure` 收口落位，再回本 skill 交付控制面

## 核心工作流

### 0. 先判 owner，再判实现

先回答三个问题：

1. 这次主目标是新增 / 补完控制能力，还是先治理结构风险？
2. 现有 feature 是否已经有明确 owner 可以承接？
3. 若直接动手，是否会把 `App.tsx` / `ProjectOverviewPage.tsx` 或某个聚合页继续做胖？

如果第 1 问偏向结构治理，或第 2、3 问答不清楚，先交给 `govern-v5-web-structure`。

### 1. 先判断这是控制面问题还是普通展示页问题

先明确：

- 用户需要的是查看结果，还是配置、筛选、审批、干预
- 页面是老板控制位、操作者工作台，还是普通结果页
- 这次前端是为了“做出控制能力”，还是只是补一个展示区块

V5 里的很多页面不是普通 CRUD，而是控制与治理面。

### 2. 把任务翻译成一个前端工作包

先明确：

- 属于哪个 Phase / 工作包
- 对应哪个 feature
- 涉及哪些状态：加载、空态、错误态、禁用态、提交中、已保存、已阻塞
- 依赖哪些后端字段或接口

如果工作包不对齐，UI 很容易做成一堆没有治理意义的按钮和卡片。

### 3. 先决定落位，再写控制面

优先扩展当前已有目录：

- 项目总览与老板入口 → `projects`
- 角色与策略配置 → `roles` / `strategy`
- Skill 与绑定 → `skills`
- 预算与成本 → `budget`
- 运行观测 → `console` / `console-metrics` / `run-log`

只有在现有 feature 明显装不下、且 owner 归属清晰时，才考虑新增：

- `apps/web/src/features/agent-teams/`
- `apps/web/src/features/agents/`
- `apps/web/src/features/prompts/`
- `apps/web/src/features/costs/`
- `apps/web/src/features/memory-governance/`

如果需要先回答“到底放哪、怎么拆、是否该新增 feature”，先转 `govern-v5-web-structure`。

### 4. 先回答四个状态面问题，再动手

每个控制面至少回答：

1. 用户能看见什么
2. 用户能改什么
3. 触发哪个接口
4. 成功、失败、禁用、缺数据时怎么反馈

如果这四个问题都没答清楚，就还不适合开始堆 UI。

### 5. 保证字段契约与文案口径一致

必须确认：

- 字段名与后端接口一致
- 枚举值和状态文案与主背景一致
- `Phase / 工作包 / role / model tier / budget / memory / skill` 口径不乱写
- 页面上“已接入”“已完成”“推荐”“可用”这些词不夸大事实

详细检查项见：`references/control-state-and-contract-checklist.md`

### 6. 同时执行结构守门

本 skill 在实现控制面时，必须顺手做下面的结构守门判断：

- 是否优先复用现有 feature，而不是发明新岛
- 是否把复杂请求、字段映射、状态逻辑继续塞进聚合页
- 是否让 `App.tsx` / `ProjectOverviewPage.tsx` 增长了新的大型区块
- 是否需要先补 `data-testid` / `sections` / `hooks.ts` / `types.ts` / `api.ts` 才能安全落地

一旦这些判断指向“主问题已变成结构治理”，马上停手并交回 `govern-v5-web-structure`，不要硬写。

### 7. 实现时把状态、反馈和可观察性做完整

至少要覆盖：

- loading
- empty
- error
- disabled
- submit pending
- success feedback
- 对当前依赖前提的诚实说明

不要只写 happy path。

### 8. 做最小验证，不要只靠肉眼觉得差不多

最低建议：

- 如有意义改动，运行 `apps/web` 的 `npm run build`
- 如改了关键页面，至少说明推荐的手工验证路径
- 如改了字段契约，至少核对对应 hooks / types / api / 页面是否一致
- 如缺后端合同，明确记录“未验证项”和原因

### 9. 明确交接路线

线程结束时必须明确下一棒是谁：

- 需要先收口页面 owner、瘦身、落位、稳定锚点 → `govern-v5-web-structure`
- 需要补后端接口、字段、动作 → `write-v5-runtime-backend`
- 需要把状态写回冻结文档 / 计划文档 → `manage-v5-plan-and-freeze-docs`
- 需要做构建、页面打开、联调、回归证据 → `verify-v5-runtime-and-regression`
- 需要审查前后端字段契约、风险或边界 → `review-v5-code-and-risk`
- 需要阶段裁定 → `accept-v5-milestone-gate`
- 如果线程已经自然跨层 → 直接升级 `drive-v5-orchestrator-delivery`

## 与兄弟 skill 的协作契约

- 本 skill 负责：**前端控制面、页面、抽屉、表单、可视化、状态反馈、最小验证、交接说明**
- `govern-v5-web-structure` 负责：**前端结构治理、大文件瘦身、页面 owner 边界、测试锚点规范、落位规则**
- `write-v5-runtime-backend` 负责：**后端 domain / service / repository / route / worker / schema 落地**
- `manage-v5-plan-and-freeze-docs` 负责：**阶段定位、冻结文档、状态回填、交接治理**
- `drive-v5-orchestrator-delivery` 负责：**跨 backend / web / docs / verify 的整链推进**
- `verify-v5-runtime-and-regression` 负责：**运行事实、构建、页面验证、联调与回归证据**
- `review-v5-code-and-risk` 负责：**字段口径、边界、实现质量与风险识别**
- `accept-v5-milestone-gate` 负责：**阶段 pass / partial / blocked 裁定**

特别纪律：

- 本 skill 有结构守门义务，但没有结构治理 owner 权限。
- `govern-v5-web-structure` 有边界裁定权，但不接管业务控制面交付结果。
- 不要越权替兄弟 skill 宣布“后端已就绪”“结构已收口”“阶段已验收通过”；本 skill 只能对当前控制面切片的实现与验证事实负责。

## 推荐输出骨架

优先使用下面骨架汇报当前线程结果：

```md
# 本轮前端控制面切片

## 背景归属
- Phase：
- 工作包：
- 所属 feature：
- 关联母本章节：

## owner 判定
- 本轮主 owner 仍为 `write-v5-web-control-surface` 的原因：
- 是否触发 `govern-v5-web-structure`：
- 如未触发，说明为什么当前结构仍可安全承接：

## 当前真实状态
- 已有页面 / 面板：
- 本轮补的入口：
- 明确未动：

## 文件级改动
- pages / panels / drawers：
- hooks / api / types：
- shared lib / components：
- 新增 feature（如有）：

## 契约与状态说明
- 依赖的后端字段 / 接口：
- loading / empty / error / disabled：
- 当前可用程度：
- 尚未完成部分：

## 验证与证据
- 已执行：
- 结果：
- 未执行：

## 交接路线
- 下一线程建议：
- 如需 structure governance：
- 如需 backend：
- 如需 verify：
- 如需 docs：
- 如需 acceptance：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 只做了静态页面，没有真实数据或动作入口
- 只做了 happy path，没有空态、错误态、禁用态
- 页面字段与后端接口对不上
- 用“推荐”“可用”“已完成”等文案夸大真实状态
- 明显依赖后端却不写清前提，直接伪造完成面
- 明显出现结构风险信号，却仍继续往聚合页硬塞代码
- 本质上是结构治理任务，却不让位给 `govern-v5-web-structure`
- 本质上是跨层任务，却不升级交接

## 红线

1. 不要脱离 `AI-Dev-Orchestrator-V5-Plan.md` 把控制台做成无关紧要的小功能页。
2. 不要拿静态假数据冒充“功能已接入”。
3. 不要乱造新的 feature 结构，导致 `apps/web` 边界失控。
4. 不要忽略失败态、空态、禁用态和反馈路径。
5. 不要把后端尚未提供的合同假装成前端已完成。
6. 不要在没有最小验证的情况下写“前端控制面已完成”。
7. 不要发现结构 owner 未收口，还硬把控制面塞进 `App.tsx` / `ProjectOverviewPage.tsx`。
8. 不要抢 `govern-v5-web-structure` 的 owner，把结构治理伪装成功能实现的一部分。

## Done checklist

- 已明确当前任务属于哪个 V5 Phase / 工作包。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已最小核对 `apps/web` 真实代码现状。
- 已先完成 owner 判定，确认这仍是控制面交付任务而不是结构治理任务。
- 已把任务收敛成一个明确的控制面切片，而不是空泛大任务。
- 已优先扩展现有 feature，或明确说明为什么必须新增 feature。
- 已写清页面入口、交互项、依赖接口、状态反馈与当前可用程度。
- 已保证字段、枚举、文案与后端及母本口径一致。
- 已检查本轮是否触发 `govern-v5-web-structure` 的让位信号，并给出结论。
- 已做至少一级最小验证，或明确说明缺证原因。
- 已给出下一线程应接的 owner skill。
- 已让后续新线程可以直接调用本 skill 接手同类前端工作包。

## References

- `references/web-control-surface-map.md`
- `references/control-state-and-contract-checklist.md`
- `references/boss-control-surface-routing.md`
- `references/control-surface-structure-routing.md`
- `references/web-control-thread-checklist.md`
- `playbooks/web-control-delivery-playbook.md`
- `templates/web-control-handoff-template.md`
