
# Day11 任务详情与运行历史

- 版本：`V1`
- 模块 / 提案：`模块C：控制台与操作闭环`
- 原始日期：`2026-03-19`
- 原始来源：`历史标签/每日计划/2026-03-19-V1任务详情与运行历史/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

补齐任务详情和运行历史能力，让 Day 10 首页从“看列表”升级到“看上下文”。

---

## 当日交付

1. `runtime/orchestrator/app/repositories/run_repository.py`
2. `runtime/orchestrator/app/api/routes/runs.py` 或等价路由文件
3. `runtime/orchestrator/app/services/console_service.py`
4. `runtime/orchestrator/app/api/routes/tasks.py`
5. `apps/web/src/app/App.tsx`
6. `apps/web/src/features/task-detail/*`
7. `apps/web/src/components/*`
---

## 验收点

1. 单任务可以查到历史运行记录
2. 结果里保留状态、成本、摘要、时间、日志路径
3. 一个接口足以支撑最小详情视图
4. 前端不需要再自行拼接多个后端响应
5. 首页可以打开单任务详情
6. 用户可以在不离开首页的情况下看见运行历史
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已在 `runtime/orchestrator/app/repositories/run_repository.py` 增加 `list_by_task_id()`
2. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 新增 `GET /tasks/{task_id}/runs`
3. 历史运行结果已统一按“最新在前”返回，并保留状态、成本、摘要、时间和日志路径
4. 已在 `runtime/orchestrator/app/services/console_service.py` 增加 Day 11 详情聚合能力
5. 已在 `runtime/orchestrator/app/api/routes/tasks.py` 新增 `GET /tasks/{task_id}/detail`
6. 详情接口已一次返回任务基本信息、最新运行摘要和历史运行列表
7. 已在 `apps/web/src/app/App.tsx` 为任务行接入点击交互和选中态
8. 已新增 `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 详情侧板
---

## 关键产物路径

1. `runtime/orchestrator/app/repositories/run_repository.py`
2. `runtime/orchestrator/app/api/routes/runs.py`
3. `runtime/orchestrator/app/services/console_service.py`
4. `runtime/orchestrator/app/api/routes/tasks.py`
5. `apps/web/src/app/App.tsx`
6. `apps/web/src/features/task-detail/*`
7. `apps/web/src/components/*`
8. `apps/web/src/features/task-detail/TaskDetailPanel.tsx`
---

## 上下游衔接

- 前一日：Day10 最小控制台首页
- 后一日：Day12 日志查看与任务操作
- 对应测试文档：`docs/01-版本冻结计划/V1/03-模块C-控制台与操作闭环/02-测试验证/Day11-任务详情与运行历史-测试.md`

---

## 顺延与备注

### 顺延项
1. 完整日志查看顺延到 Day 12
2. 实时刷新顺延到 Day 13
### 备注
1. 今天的重点不是做漂亮页面，而是把“任务详情上下文”第一次补完整
