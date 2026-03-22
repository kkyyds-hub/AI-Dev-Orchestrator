# Day02 老板首页与项目总览看板

- 版本：`V3`
- 模块 / 提案：`模块A：项目级编排与老板入口`
- 原始日期：`2026-04-07`
- 原始来源：`V3 正式版总纲 / 模块A：项目级编排与老板入口 / Day02`
- 当前回填状态：**已完成**
- 回填口径：已按 Day02 范围完成老板首页、项目总览聚合接口、前端项目看板与最小项目详情下钻，并保留 V1/V2 任务控制台能力。

---

## 今日目标

让用户一进入控制台就先看到“项目视角”的总览，而不是先陷入任务列表细节。

---

## 当日交付

1. `runtime/orchestrator/app/services/console_service.py`
2. `runtime/orchestrator/app/api/routes/console.py`
3. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
4. `apps/web/src/features/projects/components/ProjectSummaryCards.tsx`
5. `apps/web/src/features/projects/components/ProjectTable.tsx`
6. `apps/web/src/app/App.tsx`

---

## 验收点

1. 首页能展示项目总数、阶段分布、预算摘要和阻塞项目数
2. 每个项目都能展示最新进度、关键风险和任务聚合状态
3. 用户可以从项目卡片进入项目详情
4. 项目看板与现有任务/运行数据能共存，不破坏 V1/V2 控制台能力
5. 页面具备最小可读性与信息层级

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已新增 `/console/project-overview` 聚合接口，把项目级阶段分布、预算快照、阻塞项目数、项目最新进展与关键风险统一收敛到老板首页；前端新增项目总览页、重点项目卡片、项目列表和最小项目详情面板，并在原控制台首页顶部接入该页面，保证原任务/运行能力继续可用。
- 回填证据：
1. `runtime/orchestrator/app/services/console_service.py` 已新增项目级聚合模型、阶段分布、最新进展、风险摘要与阻塞项目计算
2. `runtime/orchestrator/app/api/routes/console.py` 已新增 `GET /console/project-overview`，并保留原有 `/console/*` 指标接口
3. `runtime/orchestrator/app/api/routes/tasks.py` 已更新 `ConsoleService` 依赖装配，保证老板首页与旧任务控制台共用同一服务对象
4. `apps/web/src/features/projects/ProjectOverviewPage.tsx` 已新增老板首页，包含汇总卡片、重点项目卡片、项目列表与最小项目详情面板
5. `apps/web/src/features/projects/components/ProjectSummaryCards.tsx` 与 `ProjectTable.tsx` 已完成阶段分布、预算摘要、项目聚合状态与风险展示
6. `apps/web/src/app/App.tsx` 已把项目首页放到最顶部，原 Day10-Day15 任务控制台继续保留在其后
7. `runtime/orchestrator/scripts/v3a_day02_boss_home_smoke.py` 已完成最小烟测，验证项目首页聚合数据与旧 `/tasks/console` 能力共存

---

## 关键产物路径

1. `runtime/orchestrator/app/services/console_service.py`
2. `runtime/orchestrator/app/api/routes/console.py`
3. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
4. `apps/web/src/features/projects/components/ProjectSummaryCards.tsx`
5. `apps/web/src/features/projects/components/ProjectTable.tsx`
6. `apps/web/src/app/App.tsx`

---

## 上下游衔接

- 前一日：Day01 项目实体与生命周期建模
- 后一日：Day03 项目级规划入口与任务映射
- 对应测试文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/02-测试验证/Day02-老板首页与项目总览看板-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；Day02 已按老板首页范围收口，没有提前扩展到 Day03 规划流或 Day04 里程碑守卫。

### 备注
1. 本次“项目详情”仅指老板首页内的最小详情下钻，不包含完整项目详情系统与项目级规划链路。
