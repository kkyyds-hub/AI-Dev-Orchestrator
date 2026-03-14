
# Day10 失败复盘结构与记录模板

- 版本：`V2`
- 模块 / 提案：`模块C：复盘与有限并行`
- 原始日期：`2026-04-02`
- 原始来源：`历史标签/每日计划/2026-04-02-V2C失败复盘结构与记录模板/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：已结合现有仓库实现回填为完成，失败复盘服务、仓储、Worker 回填链路和复盘模板已落地。

---

## 今日目标

建立一套最小失败复盘结构，让系统能够沉淀失败原因、处理动作和结论。

---

## 当日交付

1. `历史标签/V2阶段文档/24-V2-复盘与有限并行方案.md`
2. `docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/01-计划文档/Day10-失败复盘模板.md`
3. 复盘字段说明
4. `runtime/orchestrator/app/services/failure_review_service.py`
5. `runtime/orchestrator/app/repositories/failure_review_repository.py`
6. `runtime/data/failure-reviews/`
7. `runtime/orchestrator/app/workers/task_worker.py`
8. `runtime/orchestrator/app/services/run_logging_service.py`
---

## 验收点

1. 模板结构简洁但足够复用
2. 同类失败可以用同一模板记录
3. 复盘文件与服务命名清晰
4. 复盘记录后续可被查询
5. 失败后能产生可复盘的最小记录
6. 失败记录与任务、运行可关联
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已结合现有仓库实现回填为完成，失败复盘服务、仓储、Worker 回填链路和复盘模板已落地。
- 回填证据：
1. `runtime/orchestrator/app/services/failure_review_service.py` 已定义 `FailureReviewRecord / FailureReviewCluster` 及 `ensure_review / list_clusters`。
2. `runtime/orchestrator/app/repositories/failure_review_repository.py` 已实现 file-backed 复盘存取。
3. `runtime/orchestrator/app/workers/task_worker.py` 已在失败/阻断路径执行 `_record_failure_review_if_needed`。
4. `runtime/orchestrator/app/api/routes/console.py` 已提供 `GET /console/review-clusters` 复盘聚类查询。
5. `runtime/orchestrator/app/api/routes/runs.py` 已提供 `GET /runs/{run_id}/failure-review` 单运行复盘查询。
6. `docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/01-计划文档/Day10-失败复盘模板.md` 已新增并冻结模板。
---

## 关键产物路径

1. `历史标签/V2阶段文档/24-V2-复盘与有限并行方案.md`
2. `docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/01-计划文档/Day10-失败复盘模板.md`
3. `runtime/orchestrator/app/services/failure_review_service.py`
4. `runtime/orchestrator/app/repositories/failure_review_repository.py`
5. `runtime/data/failure-reviews`
6. `runtime/orchestrator/app/workers/task_worker.py`
7. `runtime/orchestrator/app/services/run_logging_service.py`
8. `runtime/orchestrator/app/api/routes/runs.py`
---

## 上下游衔接

- 前一日：Day09 观测面板与管理视图
- 后一日：Day11 历史决策回放与问题聚类
- 对应测试文档：`docs/01-版本冻结计划/V2/03-模块C-复盘与有限并行/02-测试验证/Day10-失败复盘结构与记录模板-测试.md`

---

## 顺延与备注

### 顺延项
1. 高级复盘可视化和多人协作流程顺延到后续版本，不影响 Day10 完成判定。
### 备注
1. 今天的重点是让失败可被“系统性记录”，并能通过接口查询与聚类复用。
