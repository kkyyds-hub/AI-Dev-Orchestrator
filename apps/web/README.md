# Day 10-15 控制台首页、任务详情、日志、实时状态流、质量闸门与预算守卫

## 本地开发

```powershell
npm.cmd install
npm.cmd run dev
```

默认会通过 `vite.config.ts` 代理到 `http://127.0.0.1:8000`。

当前页面能力：

- 首页轮询 `GET /tasks/console`
- 点击任务后加载 `GET /tasks/{task_id}/detail`
- 在右侧详情面板查看任务摘要、最新运行和历史运行列表
- 详情侧板展示验收标准、依赖任务、风险等级、人工状态和暂停说明
- 详情侧板展示 Worker 执行前构建的最小上下文包与阻塞信号
- 手动执行结果和运行详情会展示 `route_reason` / `routing_score`
- 首页与详情页展示验证模板、失败分类和质量闸门状态
- 首页展示 Day 15 日预算 / 会话预算 / 最大重试次数
- 详情侧板展示执行次数、已用重试和剩余重试
- 手动触发 `POST /workers/run-once`
- 对失败 / 阻塞任务触发 `POST /tasks/{task_id}/retry`
- 按运行读取 `GET /runs/{run_id}/logs` 结构化日志事件
- 订阅 `GET /events/console` 的 `SSE` 实时状态流
- 在 `SSE` 不可用时自动退回轮询

当前 Day 14 / Day 15 会在前端重点展示：

- `verification_mode`、`verification_template`、`verification_command`
- `verification_summary`
- `failure_category`
- `quality_gate_passed`
- `daily_budget_usd`、`session_budget_usd`
- `daily_cost_used`、`session_cost_used`
- `max_task_retries`

## 构建

```powershell
npm.cmd run build
```
