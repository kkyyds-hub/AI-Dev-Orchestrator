# V5 后端落地表面图

## 1. 目的

把 `write-v5-runtime-backend` 绑定到仓库里真实存在的后端入口，避免线程一上来就脱离现实谈抽象架构。

这个参考文件回答四个问题：

1. 当前 V5 后端最重要的代码入口在哪
2. 哪些文件已经有基础能力
3. 哪些能力仍然只是“半落地”或“展示先行”
4. 一个后端线程通常应该先从哪里切进去

## 2. 当前最关键的后端入口

### worker 主链

- `runtime/orchestrator/app/workers/task_worker.py`

当前已确认：

- Worker 会领取任务、创建 `Run`、写运行日志、构造上下文、执行、验证、估算成本、再回写结果。
- 当前主链里是 `context_builder_service.build_context_package(task=task)`，默认没有显式打开 `include_project_memory=True`。
- 因此“Worker 默认接入 project memory recall”仍然是 V5 的真实后端缺口，而不是已完成能力。

### 执行层

- `runtime/orchestrator/app/services/executor_service.py`

当前已确认：

- 执行模式仍以 `shell` / `simulate` 为主。
- 这意味着 V5 母本中说的真实 Provider 抽象层，还没有在执行层真正落地。

### 策略层

- `runtime/orchestrator/app/services/strategy_engine_service.py`
- `runtime/orchestrator/app/api/routes/strategy.py`

当前已确认：

- 已存在模型层级、技能偏好、预算压力等策略能力。
- 策略层可以产出 `model_name` / `model_tier` 一类决策信息。
- 但“策略能算出来”不等于“Executor 已真实调用 provider”。

### 上下文与记忆

- `runtime/orchestrator/app/services/context_builder_service.py`
- `runtime/orchestrator/app/services/project_memory_service.py`

当前已确认：

- `ContextBuilderService.build_context_package(..., include_project_memory=False)` 已支持记忆开关，但默认关闭。
- `ProjectMemoryService` 会把快照存到 `settings.runtime_data_dir / project-memories / <prefix> / <project_id>.json`。
- 因此涉及 memory recall、checkpoint、上下文回放时，既要看 worker 链，也要看文件存储口径。

### 成本与运行记录

- `runtime/orchestrator/app/services/cost_estimator_service.py`
- `runtime/orchestrator/app/services/run_logging_service.py`
- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/core/db_tables.py`

当前已确认：

- `CostEstimatorService` 仍是启发式 token/cost 估算。
- `RunTable` 已有 `model_name`、`prompt_tokens`、`completion_tokens`、`estimated_cost`、`log_path` 等字段。
- 但在新增 `provider_name`、`model_tier`、真实 usage 回执字段前，必须先确认 domain / repository / route DTO 是否也要同步。

### skill / role / team 相关

- `runtime/orchestrator/app/services/skill_registry_service.py`
- `runtime/orchestrator/app/api/routes/skills.py`
- `runtime/orchestrator/app/services/role_catalog_service.py`

当前已确认：

- Skill registry 已经有 V3 Day13 的注册与绑定基础。
- 它可以是 V5 “运行时 skill 能力”或“prompt / policy 挂载点”的起点。
- 但不能把“有 registry”误写成“V5 runtime skill orchestration 已完成”。

## 3. 与 V5 母本最强相关的优先切面

按 V5 Phase 1 最小闭环，后端线程优先从下面几个切面切入：

1. **Provider 抽象层**
   - 入口：`strategy_engine_service.py`、`executor_service.py`
   - 结果：真实 provider 调用链、回执、失败回退

2. **Prompt registry v1**
   - 入口：`skill_registry_service.py`、相关 domain / route / runtime 配置
   - 结果：prompt 资产可查、可渲染、可被执行链消费

3. **Token accounting v1**
   - 入口：`cost_estimator_service.py`、`runs.py`、`db_tables.py`
   - 结果：从启发式估算升级为真实 usage / 成本口径

4. **Worker 默认接入 memory recall**
   - 入口：`task_worker.py`、`context_builder_service.py`、`project_memory_service.py`
   - 结果：执行上下文默认纳入 project memory，而不是只存在独立查询能力

## 4. 一个典型后端线程的切入顺序

建议顺序：

1. 找到用户要推进的 V5 工作包
2. 在本图里确认对应入口文件
3. 用最少文件确认现状
4. 先想清楚“入口 -> 主链 -> 持久化 -> 读取方 -> 验证”
5. 再动代码

如果你还没回答清楚这五个点，就还不适合开始大改。
