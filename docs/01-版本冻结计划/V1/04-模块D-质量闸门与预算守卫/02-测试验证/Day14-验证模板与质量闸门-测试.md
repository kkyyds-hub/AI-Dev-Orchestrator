
# Day14 验证模板与质量闸门 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V1/04-模块D-质量闸门与预算守卫/01-计划文档/Day14-验证模板与质量闸门.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 新任务可以显式指定验证模板
2. 没有模板时仍能兼容旧任务输入
3. 失败类型可被区分和展示
4. 质量闸门逻辑对成功 / 失败路径一致生效
5. 用户能区分“执行失败”和“验证失败”
6. 首页 / 详情视图里能看到验证阶段信息
---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/task.py`
3.    - `runtime/orchestrator/app/services/verifier_service.py`
4.    - `runtime/orchestrator/app/services/task_instruction_parser.py`
5.    - `runtime/orchestrator/app/workers/task_worker.py`
6.    - `runtime/orchestrator/app/domain/run.py`
7. 检查前端视图是否能看到对应面板、交互或状态提示。
8. 检查后端路由、服务或 Worker 链路是否已接通。
---

## 当前回填结果

- 结果：**通过**
- 状态口径：原日计划已完成并已回填。
- 证据：
1. `runtime/orchestrator/app/services/task_instruction_parser.py` 已支持 `verify_template:` / `verify-template:` / `verification_template:` 解析，并兼容模板别名
2. `runtime/orchestrator/app/services/verifier_service.py` 已内置 `pytest`、`npm-test`、`npm-build`、`python-compileall` 模板，同时保留 `verify:` / `check:` 兜底路径
3. `runtime/orchestrator/app/domain/run.py`、`runtime/orchestrator/app/repositories/run_repository.py` 已补充 `verification_*` 字段、`failure_category` 与 `quality_gate_passed`
4. `runtime/orchestrator/app/workers/task_worker.py` 已把执行失败、验证失败、验证配置失败映射为结构化失败分类，并把质量闸门接入最终 `Task / Run` 状态判定
5. `apps/web/src/features/task-detail/TaskDetailPanel.tsx` 已展示验证模式、模板、命令、摘要、失败分类和质量闸门状态
6. `apps/web/src/app/App.tsx`、`apps/web/src/lib/status.ts` 已在首页和详情侧板中补齐失败分类与质量闸门可见性
---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做完整烟测。
2. 若当前状态为“未开始”，先创建关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
