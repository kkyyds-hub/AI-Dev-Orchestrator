
# Day14 验证模板与质量闸门

- 版本：`V1`
- 模块 / 提案：`模块D：质量闸门与预算守卫`
- 原始日期：`2026-03-22`
- 原始来源：`历史标签/每日计划/2026-03-22-V1验证模板与质量闸门/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

把当前偏自由文本的验证方式，升级为更结构化、更可复用的验证模板与质量闸门。

---

## 当日交付

1. `runtime/orchestrator/app/domain/task.py`（如需扩字段）
2. `runtime/orchestrator/app/services/verifier_service.py`
3. `runtime/orchestrator/app/services/task_instruction_parser.py`
4. `runtime/orchestrator/app/workers/task_worker.py`
5. `runtime/orchestrator/app/domain/run.py`
6. `runtime/orchestrator/app/repositories/run_repository.py`
7. `apps/web/src/features/task-detail/*`
8. `apps/web/src/components/*`
---

## 验收点

1. 新任务可以显式指定验证模板
2. 没有模板时仍能兼容旧任务输入
3. 失败类型可被区分和展示
4. 质量闸门逻辑对成功 / 失败路径一致生效
5. 用户能区分“执行失败”和“验证失败”
6. 首页 / 详情视图里能看到验证阶段信息
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. `runtime/orchestrator/app/services/task_instruction_parser.py` 已支持 `verify_template:` / `verify-template:` / `verification_template:` 解析，并兼容模板别名
2. `runtime/orchestrator/app/services/verifier_service.py` 已内置 `pytest`、`npm-test`、`npm-build`、`python-compileall` 模板，同时保留 `verify:` / `check:` 兜底路径
3. `runtime/orchestrator/app/domain/run.py`、`runtime/orchestrator/app/repositories/run_repository.py` 已补充 `verification_*` 字段、`failure_category` 与 `quality_gate_passed`
4. `runtime/orchestrator/app/workers/task_worker.py` 已把执行失败、验证失败、验证配置失败映射为结构化失败分类，并把质量闸门接入最终 `Task / Run` 状态判定
5. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已展示验证模式、模板、命令、摘要、失败分类和质量闸门状态
6. `apps/web/src/app/App.tsx`、`apps/web/src/lib/status.ts` 已在首页和详情侧板中补齐失败分类与质量闸门可见性
---

## 关键产物路径

1. `runtime/orchestrator/app/domain/task.py`
2. `runtime/orchestrator/app/services/verifier_service.py`
3. `runtime/orchestrator/app/services/task_instruction_parser.py`
4. `runtime/orchestrator/app/workers/task_worker.py`
5. `runtime/orchestrator/app/domain/run.py`
6. `runtime/orchestrator/app/repositories/run_repository.py`
7. `apps/web/src/features/task-detail/*`
8. `apps/web/src/components/*`
---

## 上下游衔接

- 前一日：Day13 SSE状态流与实时刷新
- 后一日：Day15 预算守卫与失败重试
- 对应测试文档：`docs/01-版本冻结计划/V1/04-模块D-质量闸门与预算守卫/02-测试验证/Day14-验证模板与质量闸门-测试.md`

---

## 顺延与备注

### 顺延项
1. 更复杂的验证流水线顺延到后续阶段
2. 覆盖率与工件分析顺延到更后面的质量增强阶段
### 备注
1. 今天的重点是把验证从“能跑”提升到“可复用、可解释、可做闸门”
2. 已完成 Day 14 烟测：`verify_template: python-compileall` 放行、`verify_template: unknown-template` 触发 `verification_configuration_failed`、`shell: exit 1` 触发 `execution_failed`，并确认 `GET /tasks/{task_id}/detail` 可读回运行历史
