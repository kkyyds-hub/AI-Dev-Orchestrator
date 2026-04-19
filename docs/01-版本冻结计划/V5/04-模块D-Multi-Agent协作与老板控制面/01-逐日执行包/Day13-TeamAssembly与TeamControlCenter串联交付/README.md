# Day13：team assembly 与 team control center 串联交付

- 版本：`V5`
- Phase：`Phase 4`
- 模块：`模块D：Multi-Agent 协作与老板控制面`
- 工作包：`team-assembly-and-control-center`
- 当前状态：**已实现待验证**
- owner skill：`drive-v5-orchestrator-delivery`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 本日定位

Day13 负责把 Day12 的 agent thread 入口提升为 team assembly、role policy、budget policy 可保存、可回显、可进入运行消费边界的正式执行包。

## 当前真实状态

- 已新增 `apps/web/src/features/agent-teams/`，并完成 Day13 最小承载面（`sections/components/hooks/types/api`）。
- 已新增后端合同入口：`GET/PUT /projects/{project_id}/team-control-center`，支持 team assembly / team policy / budget policy 保存与回显。
- role model policy 已通过 Day13 保存路径串联到 `/strategy/rules`，由 strategy preview 与 worker 路由消费。
- Day12 入口已升级为 Day13 串联入口，但仍未宣称 Phase 4 通过。

## 本日纳入范围

1. 冻结 team assembly / team policy 保存与回显合同。
2. 冻结 role model / budget policy 的运行时消费边界。
3. 冻结 Day14 成本聚合所依赖的 team / policy / budget 数据前提。

## 本日明确不纳入

1. 不展开 Day14 dashboard 细节实现。
2. 不进入 Day15 verify 材料执行线程。
3. 不承诺完整多人组织后台与长期运营功能。

## 当日产物

1. team assembly / team policy 保存与回显合同说明
2. role model / budget policy 运行时消费边界说明
3. Day14 可直接消费的 team / policy / budget 数据前提
4. Phase 4 控制中心风险与缺证说明

## 重点改动面

1. apps/web/src/features/agent-teams/（计划新增）
2. apps/web/src/features/projects/ProjectOverviewPage.tsx
3. apps/web/src/features/roles/RoleCatalogPage.tsx
4. apps/web/src/features/strategy/StrategyDecisionPanel.tsx

## 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/00-模块说明.md
4. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day12-AgentThread页面与BossIntervention前端入口/README.md
5. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day12-AgentThread页面与BossIntervention前端入口/04-交接模板.md
6. apps/web/src/features/projects/ProjectOverviewPage.tsx

## 完成定义

1. team assembly / team policy 的保存与回显闭环已落地（前后端真实合同）。
2. role model policy 已经进入运行时消费链路（strategy rules -> strategy preview / workers）。
3. budget policy 已完成保存/回显合同并形成 Day14 聚合前提，运行时强制执行仍沿用现有 budget guard 主链。
4. 风险与缺证已诚实回填，没有把老板控制中心写成已全面完成。

## 非完成定义

1. 只有配置表单，没有运行时消费合同。
2. 只有后端字段，没有前端入口或回显规则。
3. 把 Day13 写成 team control center 全量产品完成。
4. 提前把 Day14 dashboard 或 Day15 verify 材料写成已具备。

## 最低验证

1. 至少 1 条 team policy 保存/回显合同说明。
2. 至少 1 条 role model / budget policy 影响运行的证据入口。
3. Day14 所需聚合字段与来源已冻结。
4. 若 team / policy 仍不能影响运行，必须诚实写成缺口。

## 风险与接力

- budget policy 当前以 Day13 合同冻结为主，尚未新增 project 级强制拦截逻辑。
- 控制中心入口与现有 RoleCatalog / Strategy 面板存在路径重复风险，需要 Day14 延续收敛。
- Day12 独立页面/API 联调证据仍建议由 verify 线程补证，不阻断 Day13 主包推进。

- 下一日接力：`drive-v5-orchestrator-delivery` → `Day14：cache、成本聚合与 dashboard 联调`
- 当前不要误判为完成：`Day13` 当前为 **已实现待验证**，并非 Phase 4 已通过。
