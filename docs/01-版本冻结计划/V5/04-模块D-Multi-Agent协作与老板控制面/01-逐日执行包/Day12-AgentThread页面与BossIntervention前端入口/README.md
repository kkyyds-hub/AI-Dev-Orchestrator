# Day12：agent thread 页面与 boss intervention 前端入口

- 版本：`V5`
- Phase：`Phase 3`
- 模块：`模块D：Multi-Agent 协作与老板控制面`
- 工作包：`agent-thread-control-surface`
- 当前状态：**已规划**
- owner skill：`write-v5-web-control-surface`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day12 是 Phase 3 的前端入口冻结日，负责把 Day11 的 agent thread 后端主链变成可查看、可干预、可回填的最小前端入口包。

## 2. 背景归属

- Phase：Phase 3
- 模块：模块D：Multi-Agent 协作与老板控制面
- 工作包：`agent-thread-control-surface`
- 关联母本章节：`2.1`、`2.2`、`2.5`、`#6`、`#9`、`#12`
- 下一线程第一顺位：`write-v5-web-control-surface`
- 下一线程第二顺位：`drive-v5-orchestrator-delivery`

## 3. 当前真实状态

- `apps/web/src/features/agents/` 当前不存在。
- `ProjectOverviewPage.tsx` 目前已有老板入口基座，但没有 agent thread 页面。
- Day12 必须消费 Day11 已冻结的字段合同，不能自行重新定义 thread 数据结构。

## 4. 本日纳入范围

1. 冻结 agent thread 页面、message timeline、boss intervention 提交入口的最小前端边界。
2. 冻结页面如何消费 Day11 的 session / message / review-rework 合同。
3. 冻结 Day13 进入 team assembly 之前的 UI 接力前提。

## 5. 本日明确不纳入

1. 不展开 Day13 team assembly / control center。
2. 不把成本 dashboard、cache 可视性提前写进 Day12。
3. 不把完整多页面信息架构重构提前吞进本日。

## 6. 当日产物与改动焦点

- 预期产物：
1. agent thread 页面最小结构说明
2. message timeline / boss intervention 交互合同
3. Day13 可直接接手的前端状态与入口清单
4. 前端观察面风险与缺证说明
- 重点改动面：
1. apps/web/src/features/agents/（计划新增）
2. apps/web/src/features/projects/ProjectOverviewPage.tsx
3. apps/web/src/features/strategy/StrategyDecisionPanel.tsx
4. apps/web/src/features/roles/RoleCatalogPage.tsx

## 7. 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/00-模块说明.md
4. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day11-AgentSessionMessageReviewRework后端主链/README.md
5. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day11-AgentSessionMessageReviewRework后端主链/04-交接模板.md
6. apps/web/src/features/projects/ProjectOverviewPage.tsx
7. apps/web/src/features/strategy/StrategyDecisionPanel.tsx

## 8. 完成定义 / 非完成定义

### 完成定义
1. 老板可在前端看到最小 agent thread 页面与 message timeline 入口。
2. boss intervention 提交入口有明确交互合同，而不是只停留在按钮占位。
3. Day13 已拿到前端入口、状态与路由前提。
4. 当前缺证与未完成项已诚实回填，没有把 Day12 写成整条 Phase 3 已完成。

### 非完成定义
1. 只有静态 mock timeline，没有真实数据合同。
2. 页面不接 Day11 冻结的字段合同。
3. 只出现按钮占位，没有 boss intervention 提交规则。
4. 提前把 Day13 团队控制中心写成已准备完成。

## 9. 最低验证与证据要求

1. `npm run build` 或等价页面 smoke 入口已列明。
2. 至少 1 条 message timeline / boss intervention 回显链路。
3. Day13 要消费的前端状态、路由或入口清单已冻结。
4. 若 Day11 合同不足，必须明确写成阻塞或 partial。

## 10. 风险与接力

- 当前风险：
- 前端自己猜 API 结构，导致 Day13 之前就出现合同漂移。
- boss intervention 只有 UI 壳子，没有真实动作语义。
- Day12 把 Day13 内容提前吞掉，破坏逐日边界。
- 线程收尾后必须留下：
1. Day12 实际涉及的页面/组件/路由列表
2. message timeline / boss intervention 的状态与交互合同
3. Day13 可直接接手的前端入口清单
4. 当前缺证与阻塞说明
5. 不要误判为 Phase 3 已整体完成的点
- 下一日接力：`drive-v5-orchestrator-delivery` 接手 `Day13：team assembly 与 team control center 串联交付（本轮不展开）`
- 当前不要误判为完成：`Day12` 仍处于 **已规划**，必须由后续真实线程回填状态。
