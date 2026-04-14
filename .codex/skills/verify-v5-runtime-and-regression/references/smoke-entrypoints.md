# V5 最小 smoke 入口清单

## 1. 目的

为 `verify-v5-runtime-and-regression` 提供“从哪里开始跑最小验证”的稳定入口。

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

建议：

- 优先复用与当前工作包最接近的 smoke 脚本
- 如果已有脚本能覆盖，就不要先写新脚本

## 3. 前端最小 smoke

优先看：

- `apps/web/package.json`
- `apps/web/src/app/App.tsx`
- `apps/web/src/app/main.tsx`

最低动作：

- `npm run build`
- 关键页面是否存在入口
- 与当前改动相关的页面是否至少可达

## 4. V5 高频对象的 smoke 起点

### provider / token / strategy

- 后端：`strategy.py`、`workers.py`、`runs.py`
- 前端：`strategy/*`、`budget/*`、`console-metrics/*`

### memory / checkpoint

- 后端：`task_worker.py`、`project_memory_service.py`
- 前端：`projects/ProjectMemoryPanel.tsx`、`projects/MemorySearchPanel.tsx`

### team control / role policy

- 后端：`roles.py`、相关 service / domain
- 前端：`roles/*`、`projects/ProjectOverviewPage.tsx`、`strategy/*`

### skill / prompt registry

- 后端：`skills.py`
- 前端：`skills/*`

## 5. 线程结束前至少回答

- 这次 smoke 跑了哪一层
- 为什么选这一层
- 得到了什么强证据
- 哪些还没验证
- 下一线程该接 `backend`、`web`、`review`、`docs` 还是 `accept`
