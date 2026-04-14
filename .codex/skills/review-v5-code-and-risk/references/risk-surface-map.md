# V5 风险表面图

## 1. 目的

把 `review-v5-code-and-risk` 绑定到仓库里最容易出高风险问题的真实表面，避免线程一上来就做空泛点评。

这个参考文件回答四个问题：

1. 当前 V5 最常见的高风险面在哪里
2. 哪些风险在后端更容易出现
3. 哪些风险在前端 / 文档口径更容易出现
4. 一个审查线程通常应该先从哪里下手

## 2. 当前后端高风险面

### worker 与执行主链

- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/app/services/executor_service.py`
- `runtime/orchestrator/app/services/context_builder_service.py`

当前已确认：

- `task_worker.py` 是判断能力是否真正接入执行主链的核心入口。
- `executor_service.py` 当前仍以 `shell / simulate` 为基础。
- `context_builder_service.py` 虽有 `include_project_memory` 开关，但历史上默认关闭就是典型“看起来有能力、主链未默认接入”的风险点。

### token / cost / provider 口径

- `runtime/orchestrator/app/services/cost_estimator_service.py`
- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/core/db_tables.py`

当前已确认：

- 成本统计长期存在“启发式估算”与“真实 usage”混淆风险。
- `RunTable` 的字段存在，不等于口径已经真实闭环。
- runs API 与前端页面如果没有同步，就会形成“后端有字段、前端没概念”或反过来的风险。

### memory / snapshot / persistence 边界

- `runtime/orchestrator/app/services/project_memory_service.py`
- `runtime/orchestrator/app/core/db_tables.py`

当前已确认：

- project memory 使用文件快照是现有现实。
- 只要 V5 新能力同时引入数据库字段、文件快照或日志三套落点，就容易出现双口径或三口径冲突。

## 3. 当前前端与合同高风险面

### 老板控制面与策略面

- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
- `apps/web/src/features/roles/*`

当前已确认：

- 页面已经很像控制中心，但“像控制中心”不等于后端合同闭环。
- 审查时要防止把展示态增强误判成运行态能力完成。

### 请求层与字段口径

- `apps/web/src/lib/http.ts`
- 各 feature 的 `hooks.ts / types.ts / api.ts`

当前已确认：

- 请求层很轻，字段适配多在 feature 内部完成。
- 这意味着前后端字段一旦漂移，很容易散落出多处隐性风险。

## 4. 当前文档与状态口径高风险面

- 线程交付说明
- freeze 文档
- verify 结论

当前已确认：

- V5 最容易出现的不是“完全没做”，而是“做了一部分，却被写成全完成”。
- 审查线程必须特别关注：实现范围、验证范围、冻结口径是否真的一致。

## 5. 推荐审查顺序

建议顺序：

1. 先看母本目标与当前工作包是否匹配
2. 再看主链是否真的接上
3. 再看 schema / persistence / compatibility
4. 再看前后端和文档口径
5. 最后输出风险分级与交接建议

如果方向都不对，就不要先陷入代码细节。
