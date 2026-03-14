# Day08 成本指标与失败分布接口

- 版本：`V2`
- 模块 / 提案：`模块B：路由预算与观测增强`
- 原始日期：`2026-03-31`
- 原始来源：`历史标签/每日计划/2026-03-31-V2B成本指标与失败分布接口/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：已结合现有仓库实现回填为完成，控制台指标接口和聚合服务已落地。

---

## 今日目标

为控制台补齐稳定的成本指标和失败分布接口，让观测面板有清晰数据来源。

---

## 当日交付

1. `runtime/orchestrator/app/services/console_metrics_service.py`
2. `runtime/orchestrator/app/domain/run.py`
3. 指标 DTO 设计说明
4. `runtime/orchestrator/app/api/routes/console.py`
5. `GET /console/metrics`
6. `GET /console/budget-health`
7. `GET /console/failure-distribution`
8. `GET /console/routing-distribution`

---

## 验收点

1. 指标字段命名清晰。
2. 后续前端可直接消费。
3. 控制台指标接口归属清晰。
4. 返回结构适合前端直接显示。
5. 失败类型可聚合展示。
6. 路由分布具备可扩展接口。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已结合现有仓库实现回填为完成，控制台指标接口和聚合服务已落地。
- 回填证据：
1. `runtime/orchestrator/app/services/console_metrics_service.py` 已实现控制台指标聚合模型与服务。
2. `runtime/orchestrator/app/api/routes/console.py` 已提供 `/console/metrics`、`/console/budget-health`、`/console/failure-distribution`、`/console/routing-distribution`。
3. `runtime/orchestrator/app/repositories/run_repository.py` 已补齐指标聚合所需的数据查询方法。
4. `runtime/orchestrator/app/domain/run.py` 已包含支撑失败分类与路由统计的字段。

---

## 关键产物路径

1. `runtime/orchestrator/app/services/console_metrics_service.py`
2. `runtime/orchestrator/app/api/routes/console.py`
3. `runtime/orchestrator/app/repositories/run_repository.py`
4. `runtime/orchestrator/app/domain/run.py`

---

## 上下游衔接

- 前一日：Day07 预算降级策略与守卫增强
- 后一日：Day09 观测面板与管理视图
- 对应测试文档：`docs/01-版本冻结计划/V2/02-模块B-路由预算与观测增强/02-测试验证/Day08-成本指标与失败分布接口-测试.md`

---

## 顺延与备注

### 顺延项
1. 趋势图或更复杂的可视化样式可顺延到 Day09，不影响本日完成判定。

### 备注
1. 这一天的重点是把“观测数据从哪来”一次性理顺。
