
# Day10 最小控制台首页 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V1/03-模块C-控制台与操作闭环/01-计划文档/Day10-最小控制台首页.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 首页一次请求即可拿到任务列表、状态计数和成本汇总
2. 每条任务都能带出最新一次 `Run` 的最小摘要
3. `npm.cmd install` 可以成功
4. `npm.cmd run build` 可以通过
5. 开发环境默认可以代理到本地后端
6. 页面能展示任务总数、运行状态和成本
7. 页面能展示每条任务最新 `Run` 的状态、日志路径和估算成本
8. 已完成最小烟测，验证首页数据源可用
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/repositories/task_repository.py`
3.    - `runtime/orchestrator/app/services/console_service.py`
4.    - `runtime/orchestrator/app/api/routes/tasks.py`
5.    - `apps/web/package.json`
6.    - `apps/web/vite.config.ts`
7. 检查前端视图是否能看到对应面板、交互或状态提示。
8. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. 已新增 `GET /tasks/console`
2. 已在 `ConsoleService` 汇总任务状态和 Day 9 成本字段
3. 已保留 Day 5 原有任务接口不受影响
4. 已新增 `apps/web/README.md`
5. 已完成 `npm.cmd install`
6. 已完成 `npm.cmd run build`
7. 已在 `App.tsx` 展示任务表格、状态徽标、概览卡和成本卡片
8. 已通过 Day 10 后端烟测验证 `ConsoleService` 汇总结果
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
