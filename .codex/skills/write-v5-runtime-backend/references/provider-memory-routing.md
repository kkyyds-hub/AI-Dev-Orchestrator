# V5 Provider / Memory / Token 接线图

## 1. 目的

V5 后端线程最常见的三类核心任务是：

1. Provider 抽象与真实模型调用
2. Worker 默认接入 memory recall
3. Token / cost 从启发式估算升级为真实 usage 口径

这三个方向经常互相影响，所以这里给出推荐接线图。

## 2. Provider 抽象推荐接线

### 当前现实

- `StrategyEngineService` 已能给出模型层级和路由偏好。
- `ExecutorService` 仍主要执行 `shell` / `simulate`。
- 因此“策略层能算”与“执行层真调用”之间还缺一层真实 runtime 接线。

### 推荐接线

```text
TaskWorker
  -> Strategy / routing decision
  -> ModelRoutingService
  -> ProviderRegistryService
  -> ProviderAdapter(LLMProvider)
  -> LLM API
  -> normalized LLMResponse
  -> ExecutionResult / Run persistence / log events
```

### 设计要求

- 保留 `simulate` 作为降级或兼容路径
- Provider 响应要标准化，避免每个 provider 直接污染 worker
- usage / finish_reason / error category 要能被日志与 `Run` 消费
- 重试、超时、fallback 的策略要落在统一层，而不是散落在 worker

## 3. Memory recall 推荐接线

### 当前现实

- `ContextBuilderService.build_context_package()` 已有 `include_project_memory` 参数
- `TaskWorker` 当前默认没有显式传 `include_project_memory=True`
- `ProjectMemoryService` 已有记忆构建与快照存储能力

### 推荐接线

```text
TaskWorker
  -> ContextBuilderService.build_context_package(include_project_memory=True)
  -> ProjectMemoryService.build_task_memory_context(...)
  -> context_summary / structured log
  -> ExecutorService / Provider prompt render
```

### 设计要求

- 不要只把 memory 做成独立查询能力，要接到执行主链
- 要明确 recall 结果进入哪里：`context_summary`、prompt render、structured logs 还是三者都有
- 要考虑 recall 数量、截断、缺 memory 时的降级逻辑

## 4. Token accounting 推荐接线

### 当前现实

- `CostEstimatorService` 当前是启发式估算
- `RunTable` 已有 `prompt_tokens`、`completion_tokens`、`estimated_cost`
- 真实 provider usage 还没有成为主口径

### 推荐接线

```text
Provider response
  -> normalized usage payload
  -> ExecutionResult / LLMResponse
  -> Run persistence
  -> run log / console metrics / API response
  -> fallback to heuristic only when provider usage missing
```

### 设计要求

- 真实 usage 优先，启发式估算只作 fallback
- 要说明 usage 字段落在哪里、谁来读、旧数据如何兼容
- 如果成本看板要依赖这些字段，先确保 runs API 能稳定输出

## 5. 一个安全的 Phase 1 落地顺序

如果用户没有特别指定，推荐按下面顺序做最小闭环：

1. 先把 provider 抽象层最小接通
2. 再把 token / usage 接到 `Run`
3. 再把 memory recall 默认接入 worker
4. 最后再考虑 prompt registry 与更复杂的 policy / session 扩展

这样做的原因是：

- 没有真实 provider，就没有真实 usage
- 没有 usage，token accounting 很容易停留在“看起来像有”
- memory recall 接入 worker 后，才能判断 prompt render / context trace 的真实需求

## 6. 线程结束前至少回答

- 这次到底接通了哪一段链路
- 结果保存在哪里
- 旧链路如何兼容
- 最小验证做了什么
- 下一线程应该接 `review`、`verify`、`web` 还是 `docs`
