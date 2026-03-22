# Day02 老板首页与项目总览看板 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/01-计划文档/Day02-老板首页与项目总览看板.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 首页能展示项目总数、阶段分布、预算摘要和阻塞项目数
2. 每个项目都能展示最新进度、关键风险和任务聚合状态
3. 用户可以从项目卡片进入项目详情
4. 项目看板与现有任务/运行数据能共存，不破坏 V1/V2 控制台能力
5. 页面具备最小可读性与信息层级

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/console_service.py`
3.    - `runtime/orchestrator/app/api/routes/console.py`
4.    - `apps/web/src/features/projects/ProjectOverviewPage.tsx`
5.    - `apps/web/src/features/projects/components/ProjectSummaryCards.tsx`
6.    - `apps/web/src/features/projects/components/ProjectTable.tsx`
7.    - `apps/web/src/app/App.tsx`

8. 检查后端路由、服务或 Worker 链路是否已接通。
9. 检查前端页面、侧板或时间线是否能展示对应信息。
10. 若当日涉及状态流、审批或回退，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day02 范围已完成并已补最小烟测，老板首页与原任务控制台可同时工作。
- 证据：
1. `GET /console/project-overview` 已返回项目总数、阶段分布、预算快照、阻塞项目数和项目级最新进度/风险摘要
2. `apps/web/src/features/projects/ProjectOverviewPage.tsx` 已展示重点项目卡片、项目列表与项目详情侧板，满足“先看项目再看任务”
3. `apps/web/src/app/App.tsx` 已把项目总览置于首页顶部，原 Day10-Day15 任务控制台仍保留在下方
4. `runtime/orchestrator/scripts/v3a_day02_boss_home_smoke.py` 已验证：
   - 3 个项目可在老板首页读到
   - 阻塞项目数为 2
   - 阶段分布为 planning/execution/verification 各 1
   - 未归属任务数为 1
   - 旧 `/tasks/console` 仍可返回 5 条任务聚合数据
5. `npm.cmd exec -- tsc --noEmit -p tsconfig.app.json` 已通过，前端类型检查正常
6. `npm.cmd exec -- vite build --outDir .tmp-build-check` 已通过，前端可完成生产构建

---

## 后续补测建议

1. Day03 开始如果引入真正的项目级规划入口，补一轮“从项目到任务映射”的回归测试。
2. Day04 如补项目阶段守卫，继续回归老板首页中的阶段分布、风险摘要与阻塞项目口径。
3. 若后续增加完整项目详情页或路由，保持 Day02 这个最小老板入口仍能在首页首屏快速读取核心信息。
