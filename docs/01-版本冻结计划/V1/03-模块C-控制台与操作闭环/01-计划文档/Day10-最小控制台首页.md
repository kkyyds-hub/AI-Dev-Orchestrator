
# Day10 最小控制台首页

- 版本：`V1`
- 模块 / 提案：`模块C：控制台与操作闭环`
- 原始日期：`2026-03-18`
- 原始来源：`历史标签/每日计划/2026-03-18-V1最小控制台首页/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

完成 Day 10 的最小控制台首页，让用户第一次可以在页面里看到任务列表、状态和成本。

---

## 当日交付

1. `runtime/orchestrator/app/repositories/task_repository.py`
2. `runtime/orchestrator/app/services/console_service.py`
3. `runtime/orchestrator/app/api/routes/tasks.py`
4. `apps/web/package.json`
5. `apps/web/vite.config.ts`
6. `apps/web/tailwind.config.ts`
7. `apps/web/src/app/*`
8. `apps/web/src/app/App.tsx`
---

## 验收点

1. 首页一次请求即可拿到任务列表、状态计数和成本汇总
2. 每条任务都能带出最新一次 `Run` 的最小摘要
3. `npm.cmd install` 可以成功
4. `npm.cmd run build` 可以通过
5. 开发环境默认可以代理到本地后端
6. 页面能展示任务总数、运行状态和成本
7. 页面能展示每条任务最新 `Run` 的状态、日志路径和估算成本
8. 已完成最小烟测，验证首页数据源可用
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已新增 `GET /tasks/console`
2. 已在 `ConsoleService` 汇总任务状态和 Day 9 成本字段
3. 已保留 Day 5 原有任务接口不受影响
4. 已新增 `apps/web/README.md`
5. 已完成 `npm.cmd install`
6. 已完成 `npm.cmd run build`
7. 已在 `App.tsx` 展示任务表格、状态徽标、概览卡和成本卡片
8. 已通过 Day 10 后端烟测验证 `ConsoleService` 汇总结果
---

## 关键产物路径

1. `runtime/orchestrator/app/repositories/task_repository.py`
2. `runtime/orchestrator/app/services/console_service.py`
3. `runtime/orchestrator/app/api/routes/tasks.py`
4. `apps/web/package.json`
5. `apps/web/vite.config.ts`
6. `apps/web/tailwind.config.ts`
7. `apps/web/src/app/*`
8. `apps/web/src/app/App.tsx`
---

## 上下游衔接

- 前一日：Day09 日志与成本记录
- 后一日：Day11 任务详情与运行历史
- 对应测试文档：`docs/01-版本冻结计划/V1/03-模块C-控制台与操作闭环/02-测试验证/Day10-最小控制台首页-测试.md`

---

## 顺延与备注

### 顺延项
1. 后续可把日志详情、任务详情抽屉和运行历史接到首页
2. 后续可把首页构建产物正式接入后端托管
### 备注
1. Day 10 的价值不是做完整前端平台，而是给 V1 最小闭环提供第一个“看得见”的入口
2. 只要 Day 10 完成，后续 Day 11+ 就可以围绕这个首页继续加过滤、详情和观测能力
