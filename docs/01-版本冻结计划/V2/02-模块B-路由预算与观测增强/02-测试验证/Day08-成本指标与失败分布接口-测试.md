# Day08 成本指标与失败分布接口 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V2/02-模块B-路由预算与观测增强/01-计划文档/Day08-成本指标与失败分布接口.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 指标字段命名清晰。
2. 后续前端可直接消费。
3. 控制台指标接口归属清晰。
4. 返回结构适合前端直接显示。
5. 失败类型可聚合展示。
6. 路由分布具备可扩展接口。

---

## 建议验证动作

1. 检查 `runtime/orchestrator/app/services/console_metrics_service.py` 是否输出稳定字段结构。
2. 检查 `runtime/orchestrator/app/api/routes/console.py` 是否已暴露四个控制台指标接口。
3. 检查 `runtime/orchestrator/app/repositories/run_repository.py` 是否提供聚合查询能力。
4. 对四个指标接口执行最小烟测，确认返回结构稳定。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已结合现有仓库实现回填为完成，控制台指标接口和聚合服务已落地。
- 证据：
1. `runtime/orchestrator/app/services/console_metrics_service.py` 已实现控制台指标聚合模型与服务。
2. `runtime/orchestrator/app/api/routes/console.py` 已提供四个控制台指标接口。
3. `runtime/orchestrator/app/repositories/run_repository.py` 已补齐聚合查询方法。
4. `runtime/orchestrator/app/domain/run.py` 已包含支撑失败分类与路由统计的字段。

---

## 后续补测建议

1. 后续若新增更多指标卡片，只需要补接口回归验证。
2. 若前端消费字段变更，优先回归检查接口契约一致性。
