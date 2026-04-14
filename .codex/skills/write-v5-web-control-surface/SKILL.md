---
name: write-v5-web-control-surface
description: 将 AI-Dev-Orchestrator V5 母本中的前端控制面工作包真正落到 `apps/web` 的中文实现型 skill。用于推进项目总览、角色策略、技能绑定、团队控制、记忆治理、成本可视化、运行观测等页面、面板、抽屉、表单与状态反馈，并明确与后端、文档、验证、验收线程的交接边界。
---

# write-v5-web-control-surface

## 使命与 owner

把 `AI-Dev-Orchestrator-V5-Plan.md` 里的 V5 Web 控制面能力，收敛成 **看得见、改得动、状态真实、口径一致、可交接验证** 的 `apps/web` 改动。

这个 skill 的 owner 职责只有一个：

> **对 V5 前端控制面落地负责，而不是对后端执行链、冻结文档、风险裁定或阶段验收负责。**

它重点负责：

- 把后端能力转成老板和操作者可用的控制面
- 把 V5 的 team / role / policy / memory / skill / cost / run 等能力变成真实前端入口
- 保证页面文案、状态、字段与后端及 V5 母本口径一致
- 补齐加载、空态、错误态、禁用态、提交反馈和可观察性
- 给兄弟 skill 留下清晰的验证、联动与文档回填入口

它不应该把线程带偏成：

- 只做页面好看但没有真实交互入口
- 用静态假数据冒充“功能已接入”
- 去接管后端 service / route / schema 落地
- 去写冻结文档或宣布阶段已通过
- 不做状态面和失败态，就声称控制面已完成

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
4. `C:\Users\Administrator\Desktop\ai-skills草案\write-v5-web-control-surface-skill-草案.md`
5. `references/web-control-surface-map.md`
6. `references/control-state-and-contract-checklist.md`
7. `references/boss-control-surface-routing.md`
8. 为核对真实现状而最小读取的仓库代码文件

如果这些输入之间冲突，**以 V5 母本 + 仓库真实前端代码现状为准**，不要让桌面草案覆盖仓库事实。

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
- 为 run logs / token usage / recall evidence / checkpoint timeline 增加观察视图
- 为老板端配置、筛选、干预团队增加交互与状态反馈
- 对某个 V5 前端工作包做增量实现、字段对齐和最小验证

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

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
- 新增 feature 目录（仅在现有结构明显装不下时）

### 默认不越权的面

- `runtime/orchestrator/`：后端 owner 面，接口或字段缺口交给 `write-v5-runtime-backend`
- `docs/01-版本冻结计划/`：文档 owner 面，状态回填交给 `manage-v5-plan-and-freeze-docs`
- 阶段裁定与 pass/block 结论：交给 `accept-v5-milestone-gate`

## 开始入口

每次接手 V5 前端控制面任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/web-control-surface-map.md`
   - `references/control-state-and-contract-checklist.md`
   - `references/boss-control-surface-routing.md`
4. 打开 `apps/web/package.json`，确认当前前端栈与构建命令
5. 按任务类型只打开最相关的 feature 文件

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
2. 默认优先选择已存在 feature 里的最小安全扩展。
3. 明确说出你选择的页面 / 面板 / feature 和原因。
4. 如果主要阻塞其实是后端合同不存在，要立刻说明并交接，不要拿静态假数据硬撑完成。

例如：

- “继续做老板控制” → 先落 `ProjectOverviewPage / roles / strategy` 上的团队控制入口
- “把 token / cost 做到前端” → 先落 `budget / console-metrics / project overview` 的观察与拆账入口
- “把记忆治理做起来” → 先落 `projects` 下的 memory 面板与 recall evidence

## 核心工作流

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

### 3. 优先挂到已有 feature，不要乱开新岛

优先扩展当前已有目录：

- 项目总览与老板入口 → `projects`
- 角色与策略配置 → `roles` / `strategy`
- Skill 与绑定 → `skills`
- 预算与成本 → `budget`
- 运行观测 → `console` / `console-metrics` / `run-log`

只有在现有 feature 明显装不下时，才考虑新增：

- `apps/web/src/features/agent-teams/`
- `apps/web/src/features/agents/`
- `apps/web/src/features/prompts/`
- `apps/web/src/features/costs/`
- `apps/web/src/features/memory-governance/`

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

### 6. 实现时把状态、反馈和可观察性做完整

至少要覆盖：

- loading
- empty
- error
- disabled
- submit pending
- success feedback
- 对当前依赖前提的诚实说明

不要只写 happy path。

### 7. 做最小验证，不要只靠肉眼觉得差不多

最低建议：

- 如有意义改动，运行 `apps/web` 的 `npm run build`
- 如改了关键页面，至少说明推荐的手工验证路径
- 如改了字段契约，至少核对对应 hooks / types / api / 页面是否一致
- 如缺后端合同，明确记录“未验证项”和原因

### 8. 明确交接路线

线程结束时必须明确下一棒是谁：

- 需要补后端接口、字段、动作 → `write-v5-runtime-backend`
- 需要把状态写回冻结文档 / 计划文档 → `manage-v5-plan-and-freeze-docs`
- 需要做构建、页面打开、联调、回归证据 → `verify-v5-runtime-and-regression`
- 需要审查前后端字段契约、风险或边界 → `review-v5-code-and-risk`
- 需要阶段裁定 → `accept-v5-milestone-gate`
- 如果线程已经自然跨层 → 直接升级 `drive-v5-orchestrator-delivery`

## 与兄弟 skill 的协作契约

- 本 skill 负责：**前端控制面、页面、抽屉、表单、可视化、状态反馈、最小验证、交接说明**
- `write-v5-runtime-backend` 负责：**后端 domain / service / repository / route / worker / schema 落地**
- `manage-v5-plan-and-freeze-docs` 负责：**阶段定位、冻结文档、状态回填、交接治理**
- `drive-v5-orchestrator-delivery` 负责：**跨 backend / web / docs / verify 的整链推进**
- `verify-v5-runtime-and-regression` 负责：**运行事实、构建、页面验证、联调与回归证据**
- `review-v5-code-and-risk` 负责：**字段口径、边界、实现质量与风险识别**
- `accept-v5-milestone-gate` 负责：**阶段 pass / partial / blocked 裁定**

不要越权替兄弟 skill 宣布“后端已就绪”或“阶段已验收通过”；本 skill 只能对当前控制面切片的实现与验证事实负责。

## 推荐输出骨架

优先使用下面骨架汇报当前线程结果：

```md
# 本轮前端控制面切片

## 背景归属
- Phase：
- 工作包：
- 所属 feature：
- 关联母本章节：

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
- 本质上是跨层任务，却不升级交接

## 红线

1. 不要脱离 `AI-Dev-Orchestrator-V5-Plan.md` 把控制台做成无关紧要的小功能页。
2. 不要拿静态假数据冒充“功能已接入”。
3. 不要乱造新的 feature 结构，导致 `apps/web` 边界失控。
4. 不要忽略失败态、空态、禁用态和反馈路径。
5. 不要把后端尚未提供的合同假装成前端已完成。
6. 不要在没有最小验证的情况下写“前端控制面已完成”。

## Done checklist

- 已明确当前任务属于哪个 V5 Phase / 工作包。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已最小核对 `apps/web` 真实代码现状。
- 已把任务收敛成一个明确的控制面切片，而不是空泛大任务。
- 已优先扩展现有 feature，或明确说明为什么必须新增 feature。
- 已写清页面入口、交互项、依赖接口、状态反馈与当前可用程度。
- 已保证字段、枚举、文案与后端及母本口径一致。
- 已做至少一级最小验证，或明确说明缺证原因。
- 已给出下一线程应接的 owner skill。
- 已让后续新线程可以直接调用本 skill 接手同类前端工作包。

## References

- `references/web-control-surface-map.md`
- `references/control-state-and-contract-checklist.md`
- `references/boss-control-surface-routing.md`

- `playbooks/web-control-delivery-playbook.md`
- `references/web-control-thread-checklist.md`
- `templates/web-control-handoff-template.md`