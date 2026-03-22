# Day04 仓库首页与项目入口整合

- 版本：`V4`
- 模块 / 提案：`模块A：仓库接入与工作区基座`
- 原始日期：`2026-04-25`
- 原始来源：`V4 正式版总纲 / 模块A：仓库接入与工作区基座 / Day04`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day04 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

把仓库绑定、目录快照和变更会话整合到老板入口与项目详情页，让仓库视角成为 V4 的第一层可见能力。

---

## 当日交付

1. `runtime/orchestrator/app/api/routes/console.py`
2. `runtime/orchestrator/app/api/routes/projects.py`
3. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
4. `apps/web/src/features/repositories/RepositoryHomeCard.tsx`
5. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
6. `runtime/orchestrator/scripts/v4a_day04_repository_home_smoke.py`

---

## 验收点

1. 老板入口和项目详情都能看见仓库是否已绑定、最新快照与当前变更会话
2. 未绑定仓库时，页面会明确提示下一步操作，而不是展示空白区域
3. 项目阶段统计、任务概览和仓库摘要可以在同一视图中联动查看
4. 仓库首页保留最小入口，不在 Day04 提前扩展到文件级编辑或验证证据视图
5. 页面字段、接口返回和领域对象命名保持统一

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day04 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day04 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/api/routes/console.py`
2. `runtime/orchestrator/app/api/routes/projects.py`
3. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
4. `apps/web/src/features/repositories/RepositoryHomeCard.tsx`
5. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
6. `runtime/orchestrator/scripts/v4a_day04_repository_home_smoke.py`

---

## 上下游衔接

- 前一日：Day03 分支会话与仓库状态快照
- 后一日：Day05 文件定位索引与代码上下文包
- 对应测试文档：`docs/01-版本冻结计划/V4/01-模块A-仓库接入与工作区基座/02-测试验证/Day04-仓库首页与项目入口整合-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day04 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day04 只做仓库入口整合，不提前进入 Day05 的文件定位与代码上下文包。
