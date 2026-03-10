# V1 后端骨架

这是 `AI-Dev-Orchestrator` 的后端最小骨架，当前目标是先跑通一个可以启动、可以访问、可以继续扩展的 `FastAPI` 服务。

## 1. 当前包含的内容

- 一个 `FastAPI` 应用入口
- 一个统一路由入口
- 一个健康检查接口 `GET /health`
- 一个任务创建接口 `POST /tasks`
- 一个规划草案生成接口 `POST /planning/drafts`
- 一个规划草案应用接口 `POST /planning/apply`
- 一个任务列表接口 `GET /tasks`
- 一个任务详情接口 `GET /tasks/{task_id}`
- 一个任务运行历史接口 `GET /tasks/{task_id}/runs`
- 一个任务详情聚合接口 `GET /tasks/{task_id}/detail`
- 一个任务重试接口 `POST /tasks/{task_id}/retry`
- 一个任务暂停接口 `POST /tasks/{task_id}/pause`
- 一个任务恢复接口 `POST /tasks/{task_id}/resume`
- 一个任务请求人工接口 `POST /tasks/{task_id}/request-human`
- 一个任务人工恢复接口 `POST /tasks/{task_id}/resolve-human`
- 一个运行日志读取接口 `GET /runs/{run_id}/logs`
- 一个控制台实时事件流接口 `GET /events/console`
- 一个 Worker 单轮触发接口 `POST /workers/run-once`
- 一个最小 `Executor`，支持本地命令执行与模拟执行
- 一个最小 `Verifier`，支持本地命令验证与模拟验证
- 一个最小 `Context Builder`，在执行前组装任务级上下文包
- 一套最小运行日志落盘能力
- 一套最小 token / 成本估算能力
- 一组 `Task / Run` 最小领域模型定义
- 一组带验收标准、依赖、风险等级和人工状态的任务元数据
- 一套 `SQLite` 最小持久化基础设施
- 一组最小任务仓储与服务层
- 一个最小 `Worker` 循环
- 一套适合后续继续扩展的基础目录

## 2. 目录说明

```text
runtime/orchestrator/
  app/
    api/
      routes/
    core/
      db.py
      db_tables.py
    domain/
      _base.py
      task.py
      run.py
    repositories/
    services/
    workers/
  pyproject.toml
  README.md
```

### Java 后端类比

- `app/main.py`：相当于 Spring Boot 的应用启动入口
- `app/api/`：相当于 Controller 层
- `app/core/`：放配置、基础设施、公共能力
- `app/domain/`：放核心业务对象
- `app/repositories/`：放数据库读写封装
- `app/services/`：放业务服务逻辑
- `app/workers/`：放后台执行单元

当前 `app/domain/` 已先定义：

- `Task`：任务本体和整体推进状态
- `Run`：某次执行尝试及结果摘要

当前 `app/core/` 已先定义：

- `db.py`：数据库连接、目录初始化、建表入口
- `db_tables.py`：`Task / Run` 的最小表结构

当前 Day 4 / Day 5 已新增：

- `POST /tasks`：创建一条最小任务
- `GET /tasks`：查看当前任务列表
- `GET /tasks/{task_id}`：查看单条任务详情
- `TaskRepository`：封装 `Task` 持久化写入
- `TaskService`：封装任务创建、列表和详情业务逻辑

当前 Day 6 已新增：

- `POST /workers/run-once`：显式触发一次最小 `Worker` 循环
- `RunRepository`：封装 `Run` 最小持久化写入
- `TaskWorker`：负责取一条待执行任务并推进状态

当前 Day 7 已新增：

- `ExecutorService`：支持本地命令执行与模拟执行
- `Worker` 会在取到任务后真正执行任务，并回写 `Task / Run` 最终状态

当前 Day 8 已新增：

- `VerifierService`：支持本地命令验证与模拟验证
- `Worker` 会在执行成功后继续做最小验证，并回写验证结果

当前 Day 9 已新增：

- `RunLoggingService`：把单次运行过程写入 `runtime/data/logs/task-runs/*.jsonl`
- `CostEstimatorService`：为每次运行记录最小 token 估算与成本估算
- `Worker` 会把日志路径、token 统计和 `estimated_cost` 一起回写到 `Run`

当前 Day 10 已新增：

- `GET /tasks/console`：为最小控制台首页提供任务、状态和成本聚合数据
- `apps/web`：提供 Day 10 控制台首页前端骨架

当前 Day 11 已新增：

- `GET /tasks/{task_id}/runs`：按任务查看完整运行历史
- `GET /tasks/{task_id}/detail`：按任务查看详情聚合数据
- 控制台首页支持点击任务并在右侧查看任务详情与运行历史

当前 Day 12 已新增：

- `GET /runs/{run_id}/logs`：按运行读取结构化日志事件
- `POST /tasks/{task_id}/retry`：把 `failed / blocked` 任务重新置回 `pending`
- 控制台支持手动触发一次 Worker、重试任务并阅读结构化日志

当前 Day 13 已新增：

- `GET /events/console`：通过 `SSE` 推送 `task_updated / run_updated / log_event / heartbeat`
- `EventSource` 订阅逻辑：把事件映射到控制台 Query 缓存
- 控制台在实时连接断开时会自动退回轮询模式

当前 Day 14 已新增：

- `verify_template:`：支持优先选择内置验证模板，再回退到 `verify:` / `check:`
- 内置模板：`pytest`、`npm-test`、`npm-build`、`python-compileall`
- `Run` 新增 `verification_mode`、`verification_template`、`verification_command`、`verification_summary`
- `Run` 新增 `failure_category` 与 `quality_gate_passed`，用于区分执行失败、验证失败、验证配置失败
- 质量闸门只控制任务是否允许进入 `completed`，不会替代已有执行与验证链路

当前 Day 15 已新增：

- `DAILY_BUDGET_USD`、`SESSION_BUDGET_USD`、`MAX_TASK_RETRIES` 三个最小预算 / 重试配置
- `BudgetGuardService`：在执行前检查日预算、会话预算和单任务重试上限
- 超限任务会进入 `blocked`，并生成一条 `cancelled` 的运行记录保留阻塞原因
- `Run.failure_category` 追加 `daily_budget_exceeded`、`session_budget_exceeded`、`retry_limit_exceeded`
- 控制台首页会额外展示预算快照，详情侧板会展示已执行次数、重试剩余和预算健康状态

当前 Day 16 已新增：

- `POST /planning/drafts`：把一个项目 brief 展开为最小任务草案
- `POST /planning/apply`：按依赖顺序把草案批量落库为真实任务
- `PlannerService`：提供本地启发式的 `brief -> draft -> apply` 最小闭环

当前 Day 17 已新增：

- `ContextBuilderService`：在 Worker 真正执行前组装最小上下文包
- 上下文包默认包含任务目标、验收标准、依赖状态、最近运行摘要和阻塞信号
- `Worker` 会把上下文包写入结构化运行日志，详情侧板也会展示当前上下文预览

当前 Day 18 已新增：

- `TaskRouterService`：在领取任务前按优先级、风险、最近失败和人工状态选择下一条任务
- `Run` 会额外记录 `route_reason` 与 `routing_score`
- 结构化日志会新增 `task_routed` 事件，详情页和手动执行结果会展示路由原因

当前 V2-A 已新增：

- `TaskStateMachineService`：统一任务状态转移守卫和非法转移错误口径
- `TaskReadinessService`：统一就绪判断与阻塞原因结构化输出
- 显式动作接口：`retry / pause / resume / request-human / resolve-human`
- 非法状态动作统一返回 `HTTP 409 Conflict`

## 3. 推荐运行方式

由于当前 PowerShell 执行策略可能会拦截激活脚本，推荐直接使用虚拟环境中的 `python.exe`，这样最稳定。

### 第一步：创建虚拟环境

```powershell
py -3.11 -m venv .venv
```

### 第二步：安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

可选的 Day 15 预算配置：

```powershell
$env:DAILY_BUDGET_USD = '0.05'
$env:SESSION_BUDGET_USD = '0.20'
$env:MAX_TASK_RETRIES = '2'
```

### 第三步：启动服务

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### 第四步：打开接口文档

启动成功后，访问以下地址：

- Swagger UI：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- 任务创建：`POST http://127.0.0.1:8000/tasks`
- 任务列表：`GET http://127.0.0.1:8000/tasks`
- 任务详情：`GET http://127.0.0.1:8000/tasks/{task_id}`
- 任务运行历史：`GET http://127.0.0.1:8000/tasks/{task_id}/runs`
- 任务详情聚合：`GET http://127.0.0.1:8000/tasks/{task_id}/detail`
- 任务重试：`POST http://127.0.0.1:8000/tasks/{task_id}/retry`
- 任务暂停：`POST http://127.0.0.1:8000/tasks/{task_id}/pause`
- 任务恢复：`POST http://127.0.0.1:8000/tasks/{task_id}/resume`
- 请求人工处理：`POST http://127.0.0.1:8000/tasks/{task_id}/request-human`
- 人工处理完成：`POST http://127.0.0.1:8000/tasks/{task_id}/resolve-human`
- 运行日志：`GET http://127.0.0.1:8000/runs/{run_id}/logs`
- 实时事件流：`GET http://127.0.0.1:8000/events/console`
- Worker 单轮触发：`POST http://127.0.0.1:8000/workers/run-once`

### 第五步：试一次任务创建

可以在 Swagger UI 中直接调用，也可以用命令行发送一个最小请求：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks' `
  -ContentType 'application/json' `
  -Body '{"title":"实现 Day4 创建接口","input_summary":"完成 Task 最小创建闭环","priority":"high"}'

`POST /tasks` 现在也支持这些可选字段：

- `acceptance_criteria`: 字符串列表，描述最小验收标准
- `depends_on_task_ids`: 依赖任务 ID 列表；只有前置任务进入 `completed` 后，Worker 才会领取当前任务
- `risk_level`: `low / normal / high`
- `human_status`: `none / requested / in_progress / resolved`
- `paused_reason`: 为后续暂停 / 恢复能力预留的说明

例如：

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/tasks" `
  -ContentType "application/json" `
  -Body '{"title":"补齐调度元数据","input_summary":"为任务补充验收标准、依赖和风险信息","priority":"high","acceptance_criteria":["接口返回新字段","详情页可以看到验收标准","依赖任务未完成时不被 Worker 领取"],"risk_level":"high"}'
```

如果你想先从 brief 生成一份任务草案，再决定是否批量创建任务，可以先调用：

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/planning/drafts" `
  -ContentType "application/json" `
  -Body '{"brief":"我要给本地 AI 开发调度系统补一个最小 Planner。它需要先把 brief 拆成任务草案，再支持人工调整后批量创建任务，同时保留依赖关系和验收标准。","max_tasks":5}'
```

拿到草案后，可以把返回的 `project_summary` 和 `tasks` 原样或人工调整后提交到：

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/planning/apply" `
  -ContentType "application/json" `
  -Body (@{
    project_summary = "给本地 AI 开发调度系统补一个最小 Planner，支持 brief -> draft -> apply。"
    tasks = @(
      @{
        draft_id = "draft-1"
        title = "整理范围与验收标准"
        input_summary = "基于 brief 整理目标、边界和验收标准。"
        priority = "high"
        acceptance_criteria = @("明确目标边界", "列出验收标准")
        depends_on_draft_ids = @()
        risk_level = "normal"
        human_status = "none"
      },
      @{
        draft_id = "draft-2"
        title = "实现最小 Planner 服务"
        input_summary = "新增本地启发式 Planner，支持 draft 和 apply。"
        priority = "high"
        acceptance_criteria = @("能生成草案", "能应用草案")
        depends_on_draft_ids = @("draft-1")
        risk_level = "high"
        human_status = "none"
      },
      @{
        draft_id = "draft-3"
        title = "整体验证与收尾"
        input_summary = "验证规划链路可用，并补齐必要说明。"
        priority = "normal"
        acceptance_criteria = @("草案可生成", "任务可批量创建")
        depends_on_draft_ids = @("draft-2")
        risk_level = "normal"
        human_status = "none"
      }
    )
  } | ConvertTo-Json -Depth 5)
```
```

如果你想显式创建一个本地命令任务，可以把 `input_summary` 写成命令前缀形式：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks' `
  -ContentType 'application/json' `
  -Body '{"title":"执行本地命令","input_summary":"shell: Write-Output ''executor ok''","priority":"normal"}'
```

如果你想显式创建一个“执行 + 验证”任务，可以在 `input_summary` 里继续写验证指令：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks' `
  -ContentType 'application/json' `
  -Body '{"title":"执行并验证","input_summary":"shell: Write-Output ''executor ok''\nverify: Write-Output ''verify ok''","priority":"normal"}'
```

如果你想复用 Day 14 的内置验证模板，可以直接写 `verify_template:`：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks' `
  -ContentType 'application/json' `
  -Body '{"title":"内置编译验证","input_summary":"simulate: 先完成最小实现\nverify_template: python-compileall","priority":"normal"}'
```

当前内置模板包括：

- `verify_template: pytest`
- `verify_template: npm-test`
- `verify_template: npm-build`
- `verify_template: python-compileall`

### 第六步：查看任务列表与详情

创建完成后，可以继续查看任务列表：

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri 'http://127.0.0.1:8000/tasks'
```

如果你已经拿到某条任务的 `id`，还可以继续查看单条详情：

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>'
```

如果你想继续查看这条任务的运行历史：

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>/runs'
```

如果你想一次拿到 Day 11 详情侧板所需的聚合数据：

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>/detail'
```

如果你想把失败或阻塞任务重新推进到下一次尝试：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>/retry'
```

如果你想手动暂停、恢复或转人工：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>/pause' `
  -ContentType 'application/json' `
  -Body '{"reason":"需要人工确认"}'

Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>/resume'

Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>/request-human'

Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks/<task_id>/resolve-human'
```

如果你已经拿到某次运行的 `run_id`，还可以查看结构化日志事件：

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri 'http://127.0.0.1:8000/runs/<run_id>/logs?limit=100'
```

如果你想在浏览器或客户端里订阅 Day 13 的实时状态流：

```powershell
Invoke-WebRequest `
  -Method Get `
  -Uri 'http://127.0.0.1:8000/events/console' `
  -Headers @{ Accept = 'text/event-stream' }
```

### 第七步：触发一次 Worker 最小循环

如果当前还有 `pending` 状态的任务，可以手动触发一次单轮 `Worker`：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/workers/run-once'
```

Day 9 触发成功后：

- 一条满足依赖条件的 `pending` 任务会被取走并执行
- Worker 在执行前会先构建当前任务的最小上下文包
- Worker 不再简单领取最早 `pending` 任务，而是先通过本地 Router 选择下一条可执行任务
- 数据库中会新增一条关联的 `Run` 记录
- 默认情况下，普通任务会走模拟执行并成功完成
- 当 `input_summary` 以 `shell:`、`cmd:` 或 `command:` 开头时，会改为执行本地命令
- 当 `input_summary` 包含 `verify_template:` 时，会优先使用内置验证模板
- 执行成功后，如果存在 `verify:` / `check:` 指令，还会继续执行本地验证命令
- 没有显式验证指令时，会走最小模拟验证
- 执行与验证都成功时，质量闸门放行，任务会进入 `completed`，运行记录会进入 `succeeded`
- 执行失败、验证失败或验证模板配置失败时，质量闸门拦截，任务会进入 `failed`，运行记录会进入 `failed`
- 当日预算、会话预算或单任务重试上限已耗尽时，`Worker` 会在真正执行前阻止任务继续运行
- 被 Day 15 守卫拦截的任务会进入 `blocked`，运行记录会进入 `cancelled`
- 运行记录会额外保存 `failure_category` 与 `quality_gate_passed`，便于控制台展示失败原因
- 本次运行会在 `runtime/data/logs/task-runs/{task_id}/{run_id}.jsonl` 下留下结构化日志
- 结构化日志中会新增 `context_built` 事件，便于回看执行前使用的上下文快照
- 结构化日志中会新增 `task_routed` 事件，记录候选任务评分和最终路由原因
- `POST /workers/run-once` 响应里会额外返回 `log_path`、`prompt_tokens`、`completion_tokens` 和 `estimated_cost`

### 第八步：确认数据库文件

Day 3 完成后，应用启动时会自动初始化本地数据库：

- 数据目录：`runtime/data/db/`
- 数据库文件：`runtime/data/db/orchestrator.db`

## 4. 当前阶段刻意不做的事情

为了保持当前 `V1` 最小闭环范围，目前先不引入：

- 鉴权
- 复杂迁移系统
- 任务更新、删除与复杂筛选接口
- 流式日志、工件归档与复杂执行编排
- 覆盖率、复杂测试矩阵与高级验证编排

先把最小骨架、领域模型、持久化、任务创建、任务查询、最小 `Worker` 循环、最小 `Executor` 和最小 `Verifier` 跑通，再继续做下一步。
