# V5 最小 smoke 入口清单

## 1. 目的

为 `verify-v5-runtime-and-regression` 提供“从哪里开始跑最小验证”的稳定入口，并把高频场景压成可直接落手的最小切口。

## 2. 后端最小 smoke

### 启动与健康检查

优先看：

- `runtime/orchestrator/README.md`
- `runtime/orchestrator/app/main.py`
- `runtime/orchestrator/app/api/routes/health.py`

最低动作：

- 后端是否可启动
- `health` 是否可返回

### worker / run / log 链路

优先看：

- `runtime/orchestrator/app/api/routes/workers.py`
- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/services/run_logging_service.py`

最低动作：

- 能否触发一次最小 worker
- 是否生成 run 记录或日志痕迹
- run log 是否可读取

### 脚本 smoke

优先看：

- `runtime/orchestrator/scripts/*_smoke.py`
- 尤其是与当前工作包最接近的脚本
- 如涉及 V5 day07 控制面 / 连续回归，可优先看：
  - `runtime/orchestrator/scripts/v5_day07_control_surface_degraded_smoke.py`
  - `runtime/orchestrator/scripts/v5_day07_minimal_continuous_regression_pack.py`

建议：

- 优先复用与当前工作包最接近的 smoke 脚本
- 如果已有脚本能覆盖，就不要先写新脚本

## 3. 前端最小 smoke

优先看：

- `apps/web/package.json`
- `apps/web/src/app/App.tsx`
- `apps/web/src/app/main.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`

最低动作：

- `npm run build`
- 关键页面是否存在入口
- 与当前改动相关的页面是否至少可达

## 4. 前端结构治理后的最小 smoke

优先看：

- `apps/web/src/app/App.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- 本轮拆出的 `sections/*`、`panel/*`、`hooks.ts`、`types.ts`、`api.ts`
- 受影响的页面入口

最低动作：

- build 是否仍通过
- 入口页是否仍能挂载 / 导航
- 原有页面或旧入口是否至少有一条还能到达

说明：

- 这里验证的是“结构治理有没有明显打坏联调”，不是“结构方案是否最优”。

## 5. 测试锚点变更后的最小 smoke

优先看：

- 当前改动涉及的 `data-testid`
- `apps/web/scripts/day07_manual_run_card_evidence.spec.mjs`
- `apps/web/scripts/day07_negative_sample_page_consistency.spec.mjs`
- `apps/web/scripts/day07_same_sample_page_consistency.spec.mjs`

最低动作：

- 列出受影响锚点
- 列出受影响脚本
- 至少确认脚本、锚点、页面中的一层同步情况

说明：

- 如果没跑脚本，就不要把结果写成“验证通过”；应写“仅代码核对，未实际运行”。

## 6. V5 高频对象的 smoke 起点

### provider / token / strategy

- 后端：`strategy.py`、`workers.py`、`runs.py`
- 前端：`strategy/*`、`budget/*`、`console-metrics/*`

### memory / checkpoint

- 后端：`task_worker.py`、相关 memory service
- 前端：`projects/*`、memory / project 相关页面与面板

### team control / role policy

- 后端：`roles.py`、相关 service / domain
- 前端：`roles/*`、`projects/ProjectOverviewPage.tsx`、`strategy/*`

### skill / prompt registry

- 后端：`skills.py`
- 前端：`skills/*`

## 7. 线程结束前至少回答

- 这次 smoke 跑了哪一层
- 为什么选这一层
- 得到了什么强证据
- 哪些还没验证
- 本次来源于哪个上游 skill
- 下一线程该接 `backend`、`web`、`structure`、`docs`、`review` 还是 `accept`
