# 三省六部 UI 组件库选型调研 - 2026-06

## 1. 项目背景

- 产品名：三省六部
- 产品目标：AI 项目主管 / 多 Agent 调度工作台
- 前端目标：形成长期可维护的 React UI 组件体系，支撑项目管理、执行中心、成果中心、治理、审批、运行观测、Prompt 输入与对话式任务推进。
- 关键界面方向：ChatGPT 风格两栏布局，左侧固定 Sidebar，右侧主工作区，不采用传统后台的重顶部导航 + 多层卡片堆叠形态。
- 本次边界：只新增隐藏实验页，不改正式 Workbench 页面，不改后端、数据库或真实执行器。

## 1.1 最终视觉收敛结论

最终视觉方向收敛为 **三省六部 Minimal Dark Tokens**，而不是 shadcn/ui 默认 dashboard 风格，也不是彩色数据看板风格。

组件栈仍保持：

**shadcn-style + Radix UI + Tailwind CSS + lucide-react**

视觉规范明确为：

- page-bg / sidebar-bg / main-bg：`#000000`
- hover-bg：`#1F1F1F`
- active-bg：`#2A2A2A`
- modal-bg / popover-bg：`#303030`
- input-bg：`#1A1A1A`
- border-subtle：`#2A2A2A`
- border-strong：`#3A3A3A`
- text-primary：`#FFFFFF`
- text-secondary：`#C7C7C7`
- text-muted：`#8A8A8A`
- text-disabled：`#5F5F5F`

长期 UI 原则：

- 不使用彩色 dashboard 作为默认表达。
- 不堆大卡片，默认使用轻量行级入口和分隔线。
- 常规状态全部使用黑白灰表达，待审批数量、运行状态、菜单、Tab、输入框都走灰阶 token。
- hover 时才出现灰色圆角背景。
- Dialog 和 Dropdown 参考 ChatGPT 用户菜单风格，使用深灰浮层、较大圆角、灰阶 hover。
- 图标统一使用 lucide-react 白灰线性图标。
- 危险态作为极低频例外保留语义，但默认实验区不使用高饱和红色抢占视觉。

## 1.2 响应式设计基准

`1440x900` 只是设计参考尺寸，不是页面固定尺寸。正式 Workbench 与当前隐藏实验页都应以真实浏览器窗口为准，优先适配 MacBook Air 13.6 寸常见浏览器视口。

本轮实验页响应式基准：

- Workbench Preview 使用 `height: 100dvh`，并保留 `min-height: 720px`，避免在中等屏上被固定 900px 画布撑出不必要滚动。
- Sidebar 使用响应式宽度 `clamp(248px, 20.5vw, 300px)`：大屏接近 300px，中等屏约 280px，较窄屏收敛到 248px。
- Main 区域使用 `flex: 1`、`min-width: 0`、`overflow: hidden`，不允许横向撑破页面。
- PromptBox 使用 `min(760px, calc(100vw - sidebarWidth - 64px))` 的等价策略，确保不溢出视口。
- 小于 1200px 宽度时，快捷操作描述文字可隐藏，保留主动作和入口箭头。
- 组件选型试验区允许纵向滚动，但不得横向滚动。

响应式验收尺寸：

- `1440x900`
- `1366x768`
- `MacBook Air 13.6 browser window`
- `1280x800`

## 1.3 高频组件补充结论

隐藏实验页已补充后续高频会用到的组件样张，并继续遵守 Minimal Dark Tokens，不恢复彩色 dashboard 风格：

- Chart / 图表组件：先使用 SVG / div mock 表达极简折线图和柱状图，不新增 chart 依赖。后续若进入真实数据可视化，再优先单独评估 Recharts，避免同时引入多个 chart 库。
- Metric / 指标组件：运行次数、成功率、平均耗时、成本估算使用行级或轻量灰阶块。
- Data List / 数据列表：任务行、执行记录行、审批记录行支持状态、时间和操作入口，hover 使用 `#1F1F1F`。
- Status / 状态组件：pending、running、partial、passed、blocked 全部灰阶表达，通过文字、点和边框深浅区分。
- Alert / Toast / Inline Notice：普通、警告、失败提示都使用灰阶，失败态不使用鲜红。
- Confirm Dialog：删除、放行、重新执行使用同一套深灰弹窗层级。
- Sheet / Drawer：作为任务详情、运行详情、审批详情的临时右侧面板样张，不作为固定常驻右栏。
- Timeline / Activity Feed：运行事件、审查记录、任务推进历史使用灰阶线条和节点。
- Code / Log Block：执行日志、错误片段、Git diff 摘要使用黑底灰边、等宽字体，并允许内容区横向滚动但不撑破页面。

## 2. 候选组件库对比表

| 方案 | React / TS / Vite | 暗色 AI 工作台适配 | Tailwind | dark mode | 源码可控 | 关键组件覆盖 | 图标体系 | 依赖重量 | 维护活跃 | License | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shadcn/ui + Radix UI + Tailwind CSS + lucide-react | 很适合 | 很适合 | 原生适配 | 很好 | 很高，组件源码进入项目 | Button、Input、Textarea、Card、Badge、Dialog、Dropdown、Tabs、ScrollArea、Avatar、Separator 等可按需生成 | lucide-react 清晰统一 | 可控，按需引入 Radix primitives | 活跃 | shadcn/ui MIT；Radix MIT；lucide-react ISC | 推荐作为长期主方案 |
| Mantine | 很适合 | 适合 | 非 Tailwind 原生，但可共存 | 很好 | 中等，主要依赖库组件 | 覆盖完整 | 自带生态，可配 Tabler/Lucide | 中等偏重 | 活跃 | MIT | 可作为备选，但会引入另一套样式系统 |
| Ant Design | 很适合 | 中等 | 非 Tailwind 原生 | 支持 | 中等偏低 | 企业后台组件非常完整 | Ant Design Icons | 偏重 | 活跃 | MIT | 不推荐作为主方案，气质偏传统后台 |
| HeroUI / NextUI | 适合 | 适合 | 基于 Tailwind 思路 | 支持 | 中等 | 常用应用组件完整 | 可配 lucide-react | 中等 | 活跃 | MIT | 可作为备选，但源码可控性弱于 shadcn/ui |
| Radix Themes | 适合 | 适合 | 非 Tailwind 主导 | 支持 | 中等 | 常用基础组件较好 | 需外接图标 | 中等 | 活跃 | MIT | 适合作为 Radix 官方主题参考，不作为主方案 |
| Tremor | 适合 | 仪表盘局部适合 | Tailwind 友好 | 支持 | 中等 | dashboard / chart / KPI 强，通用应用组件不足 | 需外接图标 | 中等 | 活跃 | Apache-2.0 | 适合作为数据看板参考，不作为全局 UI 体系 |

## 3. 每个候选方案的优点

### shadcn/ui + Radix UI + Tailwind CSS + lucide-react

- 组件源码进入仓库，Codex 后续可以直接读、改、拆、治理。
- Radix primitives 提供 Dialog、Dropdown、Tabs、Avatar、ScrollArea 等可访问性基础。
- Tailwind 与当前 `apps/web` 已有技术栈一致，不需要引入另一套 CSS-in-JS 或主题系统。
- lucide-react 图标风格统一，适合工作台按钮、菜单、状态和空态。
- 按需引入，适合本项目“先实验、后迁移、可回滚”的节奏。

### Mantine

- React / TypeScript 支持成熟，组件覆盖非常完整。
- dark mode、表单、Overlay、Combobox 等能力完整，上手速度快。
- 文档完善，适合快速构建中后台或工具型应用。

### Ant Design

- 企业后台场景沉淀深，表格、表单、树、上传、通知等复杂组件很强。
- 中文社区和生态成熟，长期维护稳定。
- 对高密度管理系统友好。

### HeroUI / NextUI

- 视觉现代，适合暗色应用、SaaS 工具和轻量控制台。
- 与 Tailwind 体系关系较近，主题能力比传统组件库更贴近现代 React 应用。
- 常用组件覆盖较完整。

### Radix Themes

- Radix 官方主题层，与 Radix primitives 设计理念一致。
- 可访问性基础好，dark mode 支持自然。
- 比直接使用 primitives 更快形成统一视觉。

### Tremor

- KPI、图表、数据看板类组件方向明确。
- Tailwind 友好，适合运行观测、成本可视化、指标面板。
- Apache-2.0 license 对商业和开源项目都较安全。

## 4. 每个候选方案的风险

### shadcn/ui + Radix UI + Tailwind CSS + lucide-react

- 不是传统 npm 安装即用的黑盒组件库，需要维护本地组件代码。
- 设计一致性依赖项目内部约束，如果没有治理，容易出现多个变体分叉。
- Tailwind class 较多，需要用 `cn`、variant 和组件边界控制复杂度。

### Mantine

- 会引入 Mantine 自身样式、主题和组件心智模型，和现有 Tailwind 项目存在双体系风险。
- 组件源码不可像 shadcn/ui 那样直接纳入项目改造。
- 长期如果深度定制 ChatGPT 风格两栏工作台，可能需要较多样式覆盖。

### Ant Design

- 默认产品气质偏传统后台，容易把“三省六部”推回重表格、重顶部导航、重卡片后台风格。
- 依赖和样式体系较重。
- 与当前暗色 AI 工作台目标存在视觉方向差异。

### HeroUI / NextUI

- 组件源码可控性弱于 shadcn/ui。
- 未来如果需要非常细的工作台语义组件，仍然会在库组件外再包一层。
- 生态规模和企业复杂场景沉淀弱于 Ant Design / Mantine。

### Radix Themes

- 主题系统相对固定，不如 shadcn/ui 直接贴合 Tailwind 和本地组件治理。
- 作为完整 UI 体系时，项目仍需自己补足较多产品语义组件。

### Tremor

- 定位更偏 dashboard，不适合作为 Dialog、Sidebar、Command、PromptBox、Dropdown 等全局交互组件体系。
- 如果作为主 UI 库，会导致应用组件覆盖不足。

## 5. 推荐结论

推荐长期采用：

**shadcn/ui + Radix UI + Tailwind CSS + lucide-react**

本次实验页实际采用这一方向的最小组件栈：Radix primitives、Tailwind CSS、lucide-react、class-variance-authority、clsx、tailwind-merge，并在 `apps/web/src/features/ui-selection-lab/components/ui.tsx` 中落地本地 shadcn-style 组件。

需要强调：推荐的是 shadcn-style 的源码可控组件体系，不是照搬 shadcn/ui 默认 dashboard 视觉。三省六部的正式视觉应以 Minimal Dark Tokens 为准。

## 6. 为什么推荐这个方案

- 与现有 `apps/web` 技术栈匹配：项目已经使用 React、TypeScript、Vite、Tailwind CSS。
- 适合暗色 AI 工作台：可以自然实现 ChatGPT 风格两栏布局、Prompt 输入框、轻量 Sidebar、灰阶状态 pill、弹窗和菜单。
- 组件源码可控：适合 Codex 后续按项目语义持续修改，而不是围绕大型组件库做样式覆盖。
- 依赖克制：按需引入 primitives，避免一次性安装大型 UI 框架并改造正式页面。
- license 安全：核心栈为 MIT / ISC 等宽松许可，没有 GPL / AGPL 污染风险。
- 迁移路径清晰：可以先做实验页，再抽基础组件，再迁移正式 Workbench，最后沉淀设计规范。

## 7. 不推荐哪些方案，以及为什么

- 不推荐 Ant Design 作为主方案：它非常适合传统企业后台，但“三省六部”需要对话式 AI 项目主管工作台，不应被默认表格后台气质牵引。
- 不推荐 Tremor 作为主方案：它适合作为数据看板补充，不覆盖全局应用交互组件。
- 不推荐 Radix Themes 作为主方案：可作为主题参考，但不如 shadcn/ui 适合本项目的 Tailwind、本地源码和长期治理模式。
- Mantine 与 HeroUI 保留为备选：两者都可用，但都会降低本地组件源码可控性，或引入额外样式体系。

## 8. 本次实验页实际使用的组件栈

- 路由：`/__lab/sansheng-liubu-ui`
- 实验页：`apps/web/src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx`
- 本地 UI 组件：`apps/web/src/features/ui-selection-lab/components/ui.tsx`
- 工具函数：`apps/web/src/lib/cn.ts`
- 视觉 token：`apps/web/src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx` 中的 `minimalDarkTokens`
- 高频样张组件：
  - `apps/web/src/features/ui-selection-lab/components/ChartPreview.tsx`
  - `apps/web/src/features/ui-selection-lab/components/DataListPreview.tsx`
  - `apps/web/src/features/ui-selection-lab/components/FeedbackPreview.tsx`
  - `apps/web/src/features/ui-selection-lab/components/ResponsiveNotes.tsx`
- 新增依赖：
  - `@radix-ui/react-avatar`
  - `@radix-ui/react-dialog`
  - `@radix-ui/react-dropdown-menu`
  - `@radix-ui/react-scroll-area`
  - `@radix-ui/react-separator`
  - `@radix-ui/react-tabs`
  - `lucide-react`
  - `class-variance-authority`
  - `clsx`
  - `tailwind-merge`

## 9. 后续正式接入迁移步骤

1. 保留隐藏实验页，先由产品侧确认 Sidebar、PromptBox、Badge、Dialog、Dropdown、Tabs 的 Minimal Dark 视觉方向。
2. 将实验页中的通用组件从 `features/ui-selection-lab/components` 提升到正式 `src/components/ui`，并补组件命名、variant、状态规范。
3. 只迁移正式 Workbench 的外壳和基础输入体验，不同时改业务数据流。
4. 再逐步迁移审批、执行中心、成果中心、治理等页面的局部组件。
5. 为关键组件补 Story / Lab 样张 / smoke 测试锚点，避免后续视觉和交互漂移。
6. 最后删除或归档实验页，或保留为内部设计回归页。

## 10. 参考链接列表

### shadcn/ui + Radix UI + Tailwind CSS + lucide-react

- shadcn/ui Docs: https://ui.shadcn.com/docs
- shadcn/ui GitHub: https://github.com/shadcn-ui/ui
- shadcn npm: https://www.npmjs.com/package/shadcn
- Radix UI Primitives Docs: https://www.radix-ui.com/primitives
- Radix UI Primitives GitHub: https://github.com/radix-ui/primitives
- Radix Dialog npm: https://www.npmjs.com/package/@radix-ui/react-dialog
- lucide Docs: https://lucide.dev
- lucide GitHub: https://github.com/lucide-icons/lucide
- lucide-react npm: https://www.npmjs.com/package/lucide-react

### Mantine

- Mantine Docs: https://mantine.dev
- Mantine GitHub: https://github.com/mantinedev/mantine
- Mantine npm: https://www.npmjs.com/package/@mantine/core

### Ant Design

- Ant Design Docs: https://ant.design
- Ant Design GitHub: https://github.com/ant-design/ant-design
- Ant Design npm: https://www.npmjs.com/package/antd

### HeroUI / NextUI

- HeroUI Docs: https://www.heroui.com
- HeroUI GitHub: https://github.com/heroui-inc/heroui
- HeroUI npm: https://www.npmjs.com/package/@heroui/react

### Radix Themes

- Radix Themes Docs: https://www.radix-ui.com/themes
- Radix Themes GitHub: https://github.com/radix-ui/themes
- Radix Themes npm: https://www.npmjs.com/package/@radix-ui/themes

### Tremor

- Tremor Docs: https://www.tremor.so
- Tremor GitHub: https://github.com/tremorlabs/tremor-npm
- Tremor npm: https://www.npmjs.com/package/@tremor/react
