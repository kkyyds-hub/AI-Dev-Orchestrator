# V1 后端骨架

这是 `AI-Dev-Orchestrator` 的后端最小骨架，当前目标是先跑通一个可以启动、可以访问、可以继续扩展的 `FastAPI` 服务。

## 1. 当前包含的内容

- 一个 `FastAPI` 应用入口
- 一个统一路由入口
- 一个健康检查接口 `GET /health`
- 一个任务创建接口 `POST /tasks`
- 一个任务列表接口 `GET /tasks`
- 一个任务详情接口 `GET /tasks/{task_id}`
- 一个 Worker 单轮触发接口 `POST /workers/run-once`
- 一个最小 `Executor`，支持本地命令执行与模拟执行
- 一个最小 `Verifier`，支持本地命令验证与模拟验证
- 一套最小运行日志落盘能力
- 一套最小 token / 成本估算能力
- 一组 `Task / Run` 最小领域模型定义
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
- Worker 单轮触发：`POST http://127.0.0.1:8000/workers/run-once`

### 第五步：试一次任务创建

可以在 Swagger UI 中直接调用，也可以用命令行发送一个最小请求：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/tasks' `
  -ContentType 'application/json' `
  -Body '{"title":"实现 Day4 创建接口","input_summary":"完成 Task 最小创建闭环","priority":"high"}'
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

### 第七步：触发一次 Worker 最小循环

如果当前还有 `pending` 状态的任务，可以手动触发一次单轮 `Worker`：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/workers/run-once'
```

Day 9 触发成功后：

- 一条 `pending` 任务会被取走并执行
- 数据库中会新增一条关联的 `Run` 记录
- 默认情况下，普通任务会走模拟执行并成功完成
- 当 `input_summary` 以 `shell:`、`cmd:` 或 `command:` 开头时，会改为执行本地命令
- 执行成功后，如果存在 `verify:` / `check:` 指令，还会继续执行本地验证命令
- 没有显式验证指令时，会走最小模拟验证
- 执行与验证都成功时，任务会进入 `completed`，运行记录会进入 `succeeded`
- 执行失败或验证失败时，任务会进入 `failed`，运行记录会进入 `failed`
- 本次运行会在 `runtime/data/logs/task-runs/{task_id}/{run_id}.jsonl` 下留下结构化日志
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
