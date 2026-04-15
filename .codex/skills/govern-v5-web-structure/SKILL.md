---
name: govern-v5-web-structure
description: 在 AI-Dev-Orchestrator V5 期间，将前端结构治理、大文件瘦身、拆分边界、联调影响控制和测试锚点规范收敛成中文 owner 型 skill。用于在不打断当前 V5 功能推进的前提下，持续治理 `apps/web` 中的聚合页、超大文件和失控入口；不负责视觉重做或整站改版。
---

# govern-v5-web-structure

## 使命与 owner

把 V5 期间前端“越写越胖、入口越来越乱、联调越来越脆”的问题，收敛成 **可持续推进、风险可控、可逐步减债、可交接** 的结构治理工作流。

这个 skill 的 owner 职责只有一个：

> **负责 V5 期间的前端结构治理：大文件瘦身、拆分边界、联调影响控制和测试锚点规范；不负责视觉重做、整站导航重构或最终美化。**

它重点负责：

- 对 `apps/web` 里的聚合页进行低风险瘦身
- 控制 `App.tsx`、`ProjectOverviewPage.tsx` 等入口页继续做胖
- 把新增前端逻辑优先落到 `features/*`、`sections/*`、`components/*`、`hooks.ts`、`types.ts`、`api.ts`
- 约束“哪些属于结构减债，哪些属于整站翻修”
- 控制改动对联调、测试脚本和文档回填的影响
- 补齐 `data-testid` 等稳定锚点，减少测试对中文文案和页面排版的耦合

它不应该把线程带偏成：

- 一边做 V5 功能，一边顺手整站翻修
- 以“瘦身”为名，大改路由、导航、页面关系
- 以“规范”为名，重做所有视觉样式
- 把后端合同变更、验收裁定、总计划冻结一起揽进来
- 只改代码文件，不说明联调、测试、文档会受到什么影响

## 强绑定的权威输入

优先级从高到低如下：

1. `docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md`
2. `docs/01-版本冻结计划/V5/` 下与当前 Day / 工作包直接相关的 README 与模板
3. `apps/web/package.json`
4. `apps/web/src/app/App.tsx`
5. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
6. `references/real-front-end-governance-surface.md`
7. `references/large-file-slimming-rules.md`
8. `references/page-owner-boundaries.md`
9. `references/refactor-vs-redesign-rules.md`
10. `references/frontend-test-anchor-rules.md`
11. `references/web-structure-thread-checklist.md`
12. 当前线程直接涉及的前端 feature、测试脚本、验证说明与文档回填文件

如果这些输入之间冲突，**以 V5 正式执行计划 + 仓库真实前端代码现状 + 已有联调/验证脚本为准**，不要让空泛的“前端应该更漂亮”覆盖当前交付现实。

## V5 绑定原则

这个 skill 必须明确绑定到 V5 期间的结构治理，不允许脱离当前阶段去做泛化前端改版。

默认优先处理下列问题：

### V5 期间应纳入的结构治理
- `App.tsx` 过胖、区块堆积、顶层逻辑失控
- `ProjectOverviewPage.tsx` 聚合过重、跨 feature 职责不清
- 新增功能继续直接堆进入口页
- 页面中混写请求、字段转换、渲染和状态判断
- 浏览器证据脚本或 smoke 过度依赖文案和布局而不是稳定锚点
- “明明只是需要抽 section”却被误做成“重做整站页面体系”

### V5 期间明确不纳入
- 全站视觉重做
- 全局导航重建
- 页面信息架构整体翻新
- 页面间路由体系全面重构
- 最终样式统一和体验 polish

一句话：**本 skill 解决的是“结构失控”，不是“页面不好看”。**

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- “前端入口页太胖了，先帮我瘦身”
- “这次要继续写 V5，但不能再把 `App.tsx` / `ProjectOverviewPage.tsx` 做胖”
- “帮我判断这次改动是结构减债还是整站翻修”
- “我要拆 section / panel / hook，但不能打断联调”
- “我要给关键页面补测试锚点，减少 smoke 对文案依赖”
- “我需要一份能指导前端瘦身、联调影响控制、文档回填的 owner skill”

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是前端新功能控制面交付：转 `write-v5-web-control-surface`
- 主要目标是后端 service / route / schema / worker 实现：转 `write-v5-runtime-backend`
- 主要目标是跨 backend / web / docs / verify 整链推进：转 `drive-v5-orchestrator-delivery`
- 主要目标是 build / smoke / API / 页面事实确认：转 `verify-v5-runtime-and-regression`
- 主要目标是冻结文档、状态回填、完成定义治理：转 `manage-v5-plan-and-freeze-docs`
- 主要目标是视觉重做、设计稿落地、统一样式 polish：应留到 V5 结束后的专门前端美化阶段

一句话：**本 skill 管结构治理，不接管功能实现、验收裁定或视觉翻修。**

## 正式落盘边界

### 本 skill 的主要输出形式
- 结构治理切片定义
- 文件级拆分计划
- 低风险瘦身实施规则
- 联调影响与测试影响说明
- 文档回填建议
- 下一线程接棒建议

### 默认会触达的目录
- `apps/web/src/app/`
- `apps/web/src/features/`
- `apps/web/src/components/`
- `apps/web/src/lib/`
- 与当前页面相关的浏览器证据脚本或最小 smoke 脚本
- 与当前改动直接相关的 V5 文档回填文件

### 默认不越权的面
- 不直接实现新的后端合同
- 不替 `write-v5-web-control-surface` 完整接管业务控制面新增
- 不替 `verify-v5-runtime-and-regression` 假装完成验证结论
- 不替 `accept-v5-milestone-gate` 做阶段裁定
- 不以“结构治理”为名推动视觉改版

## 开始入口

每次接手 V5 前端结构治理任务时，先按下面顺序读取，且只读最小集合：

1. 打开 `docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md`
2. 打开当前 Day / 工作包对应的 README 或说明
3. 打开本 skill 自带参考：
   - `references/real-front-end-governance-surface.md`
   - `references/large-file-slimming-rules.md`
   - `references/page-owner-boundaries.md`
   - `references/refactor-vs-redesign-rules.md`
   - `references/frontend-test-anchor-rules.md`
   - `references/web-structure-thread-checklist.md`
4. 打开 `apps/web/package.json`
5. 打开最关键的入口文件：
   - `apps/web/src/app/App.tsx`
   - `apps/web/src/features/projects/ProjectOverviewPage.tsx`
6. 再按当前瘦身范围最小补读对应 feature 文件

### 最小必读代码入口
- `apps/web/src/app/App.tsx`
- `apps/web/src/app/main.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- `apps/web/src/lib/http.ts`
- 当前线程直接涉及的 feature 目录下的 `hooks.ts / types.ts / api.ts / Panel.tsx / Section.tsx`

## 如何处理模糊请求

遇到“前端太乱了，帮我整理”“先把这些大文件瘦下来”“这块别再长歪了”这类模糊请求时：

1. 先判断这是 **结构治理**、**功能交付**、还是 **视觉改版**。
2. 只有当主任务是：
   - 控制大文件继续膨胀
   - 做低风险拆分
   - 收口页面 owner
   - 减少联调/测试风险  
   才使用本 skill。
3. 默认先锁定一个 **最小结构治理切片**，不要一上来就承诺重做整个前端。
4. 如果当前真正缺的是新业务控制面，就交回 `write-v5-web-control-surface`；如果真正缺的是 build / smoke / 页面事实，就交回 `verify-v5-runtime-and-regression`。

## 核心工作流

### 1. 先判断这是“瘦身”还是“翻修”
必须先回答：

- 这次改动是否保持页面主入口和联调路径基本不变
- 是否只是把大块代码搬到新文件 / 新 hooks / 新 utils
- 是否只是补 `data-testid`、收口状态逻辑、拆 section
- 是否会重排导航、路由、页面关系或视觉体系

如果答案偏向前者，就是结构减债；如果偏向后者，就是整站翻修，应当延后。

### 2. 锁定最小结构治理切片
优先选择如下切片：

- 把一个过胖区块从 `App.tsx` 抽成 `Section`
- 把 `ProjectOverviewPage.tsx` 某个大块抽成 `Section`
- 把页面中的复杂数据逻辑下沉到 `hooks.ts`
- 把页面中的字段拼装与格式化下沉到 `lib/*`
- 给关键交互和关键结果区块补 `data-testid`

切片必须满足：**小到不会打断 V5 节奏，大到能明显降低继续失控的风险。**

### 3. 严守入口页边界
默认按下列规则治理：

#### `App.tsx`
只允许：
- 顶层 query / mutation / stream hook 注入
- 页面壳级 section 顺序编排
- 最小的事件转发与选中状态管理

不允许：
- 持续新增完整 feature 逻辑
- 新增大量字段转换
- 新增超过一屏的大块 JSX 区域
- 把新业务入口直接硬塞进同一文件继续堆叠

#### `ProjectOverviewPage.tsx`
只允许：
- 选中项目状态
- drilldown 上下文
- 跨区块导航协调
- 各项目相关 feature 的挂载与组合

不允许：
- 持续新增完整业务控制面的核心实现
- 把新结果区、详情区、表格区直接继续堆在同一文件
- 长期承担应归属独立 section / panel / feature 的实现职责

### 4. 触发拆分的硬规则
满足任意一条，应优先拆分而不是继续往原文件里堆：

- 单文件新增超过 120 行结构性 UI 代码
- 单文件同时新增两个及以上大区块
- 页面同时新增请求、字段转换、复杂状态和渲染逻辑
- 同一页面出现重复的 badge / format / runtime field 拼装逻辑
- 当前改动会让 `App.tsx` 或 `ProjectOverviewPage.tsx` 继续明显变胖
- 测试或联调开始依赖更脆弱的 DOM / 文案 / 顺序结构

### 5. 默认拆分落位规则
优先按下面方式落位：

- 页面区块：`features/<domain>/sections/` 或 `app/sections/`
- 可复用视图块：`features/<domain>/components/`
- 查询 / mutation / 状态：`features/<domain>/hooks.ts`
- 类型：`features/<domain>/types.ts`
- 接口：`features/<domain>/api.ts`
- 公共格式化或纯工具：`src/lib/`

默认禁止：
- 页面里直接混写复杂请求与字段转换
- 把展示逻辑、格式化逻辑、合同映射散落在多个大页面中
- 继续让顶层入口页承担 feature 级实现

### 6. 联调影响控制
每次结构治理都要明确：

- 本次是否改变接口合同：通常不应该改变
- 本次是否改变关键按钮文案：非必要不改
- 本次是否改变交互入口路径：非必要不改
- 本次是否影响现有证据脚本：若影响，必须显式说明并同步处理
- 本次是否需要同步回填文档：若页面入口、锚点或说明发生变化，应记录

### 7. 测试锚点规范
凡是下列改动，默认补 `data-testid`：

- 新增关键按钮
- 新增关键结果卡片
- 新增任务表、详情区、drilldown 入口
- 新增抽屉、弹层、panel
- 关键状态卡片
- 被 smoke / 浏览器证据脚本使用的关键区域

优先让测试依赖：
1. `data-testid`
2. 稳定语义 role
3. 最后才是中文文案

### 8. 最小验证与交接
每次结构治理线程结束时，至少要说明：

- 哪些文件被拆了
- 哪些行为保持不变
- 是否运行了 `npm run build`
- 哪些测试/脚本可能需要同步关注
- 是否需要文档回填
- 下一线程建议接给哪个 skill

## 与兄弟 skill 的协作契约

- 本 skill 负责：**前端结构治理、大文件瘦身、拆分边界、联调影响控制、测试锚点规范**
- `write-v5-web-control-surface` 负责：**前端业务控制面和真实功能入口交付**
- `write-v5-runtime-backend` 负责：**后端实现**
- `drive-v5-orchestrator-delivery` 负责：**跨层整链推进**
- `verify-v5-runtime-and-regression` 负责：**运行事实、build、API、页面验证**
- `manage-v5-plan-and-freeze-docs` 负责：**计划冻结、状态回填、交接治理**
- `accept-v5-milestone-gate` 负责：**最终裁定**

本 skill 不能替这些兄弟 skill 越权宣布“功能已完成”“整条链已打通”“阶段已通过”。

## 推荐输出骨架

优先使用下面骨架汇报本轮结构治理：

```md
# 本轮前端结构治理切片

## 背景归属
- Phase：
- 工作包：
- 当前属于：结构治理 / 低风险瘦身
- 明确不属于：视觉改版 / 整站翻修

## 本轮目标
- 主要瘦身对象：
- 本轮纳入的文件：
- 本轮明确不做：

## 文件级动作
- 抽出的 section / panel：
- 下沉的 hooks / types / api / lib：
- 新增的 testid：
- 保持不变的行为：

## 联调与测试影响
- 接口合同是否变化：
- 关键文案是否变化：
- 现有脚本是否需要同步关注：
- 风险点：

## 验证
- 已执行：
- 结果：
- 未执行：

## 交接路线
- 下一线程建议：
- 如需功能交付：
- 如需 verify：
- 如需 docs：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 以“瘦身”为名，实质上重排了站点结构
- 以“结构治理”为名，顺手做了视觉重做
- 把原本稳定的联调入口和文案改乱了，却没有说明影响
- 没拆清页面 owner，只是简单移动代码位置
- 没补测试锚点，导致页面拆分后脚本更脆弱
- 没说明 build / 文档 / 联调影响
- 只改代码，不给交接路线

## 红线

1. 不要把本 skill 用成“前端大改总包”。
2. 不要用“瘦身”掩盖整站翻修。
3. 不要越权改后端合同。
4. 不要为了抽文件而打断当前 V5 功能推进。
5. 不要忽略测试锚点，导致后续页面更难验证。
6. 不要在未验证的情况下写“结构治理已完成且无影响”。

## Done checklist

- 已明确当前任务属于 V5 期间的结构治理，而不是视觉改版。
- 已明确本轮切片的瘦身对象和不纳入范围。
- 已核对 `App.tsx` / `ProjectOverviewPage.tsx` 等真实入口文件。
- 已按落位规则把代码下沉到合适目录，而不是继续堆入口页。
- 已控制联调、测试、文档的影响。
- 已给关键区域补稳定锚点。
- 已做至少一级最小验证，或明确说明缺证原因。
- 已给出下一线程应接的 owner skill。
- 已让后续新线程可以直接调用本 skill 接手同类结构治理工作。

## References

- `references/real-front-end-governance-surface.md`
- `references/large-file-slimming-rules.md`
- `references/page-owner-boundaries.md`
- `references/refactor-vs-redesign-rules.md`
- `references/frontend-test-anchor-rules.md`
- `references/web-structure-thread-checklist.md`

- `playbooks/web-structure-governance-playbook.md`
- `templates/web-structure-handoff-template.md`
